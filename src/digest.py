from __future__ import annotations

import dataclasses
import datetime as dt
import html
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

OPENALEX_URL = "https://api.openalex.org/works"
ARXIV_API_URL = "https://export.arxiv.org/api/query"


@dataclasses.dataclass
class Paper:
    title: str
    authors: list[str]
    venue: str
    published_date: str
    doi_url: str
    openalex_url: str
    cited_by_count: int
    abstract: str
    summary_zh: str
    topics: list[str]
    source: str = "openalex"


@dataclasses.dataclass
class DigestConfig:
    max_papers: int = 12
    min_citations: int = 0
    output_dir: Path = Path("output")
    keep_latest_when_empty: bool = True


@dataclasses.dataclass
class LLMConfig:
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    timeout_seconds: int = 30

    @property
    def enabled(self) -> bool:
        return bool(self.api_base and self.api_key and self.model)


def _extract_abstract(indexed_abstract: dict[str, Any] | None) -> str:
    if not indexed_abstract:
        return ""
    inverted = indexed_abstract.get("InvertedIndex", {})
    if not inverted:
        return ""

    max_pos = -1
    words: list[str | None] = []
    for word, positions in inverted.items():
        for pos in positions:
            if pos > max_pos:
                max_pos = pos
                words.extend([None] * (max_pos - len(words) + 1))
            words[pos] = word
    return " ".join([w for w in words if w])


def _topic_names(concepts: list[dict[str, Any]]) -> list[str]:
    return [c.get("display_name") for c in concepts[:5] if c.get("display_name")]


def _simple_zh_summary(title: str, abstract: str, topics: list[str]) -> str:
    short_abs = abstract.strip().replace("\n", " ")
    if len(short_abs) > 180:
        short_abs = short_abs[:177] + "..."

    topic_text = "、".join(topics[:3]) if topics else "金融经济学"
    if short_abs:
        return f"这篇论文围绕“{title}”展开，主题涉及{topic_text}。核心内容：{short_abs}"
    return f"这篇论文围绕“{title}”展开，主题涉及{topic_text}。可进一步阅读全文获取研究方法与结论。"


def _llm_zh_summary(title: str, abstract: str, topics: list[str], cfg: LLMConfig) -> str:
    if not cfg.enabled:
        return _simple_zh_summary(title, abstract, topics)

    payload = {
        "model": cfg.model,
        "messages": [
            {
                "role": "system",
                "content": "你是金融经济学研究助手。请用中文输出2-3句摘要，包含研究主题、方法视角和潜在应用价值，不要编造。",
            },
            {
                "role": "user",
                "content": json.dumps({"title": title, "topics": topics, "abstract": abstract[:3000]}, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
    }
    req = Request(
        url=f"{cfg.api_base.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
    )
    try:
        with urlopen(req, timeout=cfg.timeout_seconds) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return content or _simple_zh_summary(title, abstract, topics)
    except Exception:
        return _simple_zh_summary(title, abstract, topics)


def _render_markdown(date: str, papers: list[Paper], note: str = "") -> str:
    lines = [f"# 金融经济学每日文献速递（{date}）", "", f"共筛选到 **{len(papers)}** 篇文献。", ""]
    if note:
        lines.extend([f"> {note}", ""])

    for idx, p in enumerate(papers, start=1):
        links: list[str] = []
        if p.doi_url:
            links.append(f"[DOI]({p.doi_url})")
        if p.openalex_url:
            links.append(f"[链接]({p.openalex_url})")
        lines.extend(
            [
                f"## {idx}. {p.title}",
                f"- 来源：{p.source}",
                f"- 作者：{', '.join(p.authors) if p.authors else 'N/A'}",
                f"- 期刊/来源：{p.venue}",
                f"- 发表日期：{p.published_date}",
                f"- 引用数：{p.cited_by_count}",
                f"- 主题：{', '.join(p.topics) if p.topics else 'N/A'}",
                f"- 链接：{' '.join(links) if links else 'N/A'}",
                "",
                f"**中文摘要（自动生成）**：{p.summary_zh}",
                "",
            ]
        )
    return "\n".join(lines)


def _render_html(date: str, papers: list[Paper], note: str = "") -> str:
    cards: list[str] = []
    for idx, p in enumerate(papers, start=1):
        doi_link = f'<a href="{html.escape(p.doi_url)}" target="_blank" rel="noopener noreferrer">DOI</a>' if p.doi_url else ""
        ext_link = f'<a href="{html.escape(p.openalex_url)}" target="_blank" rel="noopener noreferrer">链接</a>' if p.openalex_url else ""
        sep = " | " if doi_link and ext_link else ""
        cards.append(
            f"""
  <article class=\"card\">
    <h2>{idx}. {html.escape(p.title)}</h2>
    <p class=\"meta\">来源：{html.escape(p.source)}｜作者：{html.escape(', '.join(p.authors) if p.authors else 'N/A')}</p>
    <p class=\"meta\">期刊/来源：{html.escape(p.venue)}｜发表：{html.escape(p.published_date)}｜引用数：{p.cited_by_count}</p>
    <p class=\"meta\">主题：{html.escape(', '.join(p.topics) if p.topics else 'N/A')}</p>
    <p>{doi_link}{sep}{ext_link}</p>
    <p class=\"summary\"><strong>中文摘要（自动生成）:</strong> {html.escape(p.summary_zh)}</p>
  </article>
            """.strip()
        )

    note_html = f'<p class="note">{html.escape(note)}</p>' if note else ""
    cards_html = "\n".join(cards)
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>金融经济学每日文献速递 - {html.escape(date)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 900px; line-height: 1.6; color: #111; padding: 0 1rem; }}
    .card {{ border: 1px solid #e6e6e6; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }}
    .meta {{ color: #666; font-size: 0.95rem; }}
    .summary {{ background: #f8f8f8; padding: 0.8rem; border-radius: 8px; }}
    .note {{ color: #a15d00; background: #fff7e6; border: 1px solid #ffdf99; padding: 0.75rem; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>金融经济学每日文献速递</h1>
  <p class=\"meta\">日期：{html.escape(date)}｜篇数：{len(papers)}</p>
  {note_html}
  {cards_html}
</body>
</html>
"""


def fetch_openalex_papers(date_from: dt.date, date_to: dt.date, per_page: int = 50) -> list[Paper]:
    filters = [
        f"from_publication_date:{date_from.isoformat()}",
        f"to_publication_date:{date_to.isoformat()}",
        "concepts.id:C162324750",
    ]
    params = urlencode({"filter": ",".join(filters), "sort": "cited_by_count:desc", "per-page": per_page})

    try:
        with urlopen(f"{OPENALEX_URL}?{params}", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8")).get("results", [])
    except URLError:
        return []

    papers: list[Paper] = []
    for item in data:
        doi = item.get("doi") or ""
        papers.append(
            Paper(
                title=item.get("title") or "Untitled",
                authors=[
                    a.get("author", {}).get("display_name", "")
                    for a in item.get("authorships", [])[:5]
                    if a.get("author", {}).get("display_name")
                ],
                venue=item.get("primary_location", {}).get("source", {}).get("display_name") or "Unknown",
                published_date=item.get("publication_date") or "",
                doi_url=doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else ""),
                openalex_url=item.get("id", ""),
                cited_by_count=item.get("cited_by_count", 0),
                abstract=_extract_abstract(item.get("abstract_inverted_index")),
                summary_zh="",
                topics=_topic_names(item.get("concepts", [])),
                source="openalex",
            )
        )
    return papers


def fetch_arxiv_finance_econ_papers(date_from: dt.date, max_results: int = 30) -> list[Paper]:
    query = quote_plus("cat:q-fin.* OR cat:econ.*")
    params = f"search_query={query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    try:
        with urlopen(f"{ARXIV_API_URL}?{params}", timeout=30) as response:
            xml_text = response.read().decode("utf-8")
    except URLError:
        return []

    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers: list[Paper] = []
    for entry in root.findall("atom:entry", ns):
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "")[:10]
        if published != date_from.isoformat():
            continue
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
        abstract = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")
        authors = [
            author.findtext("atom:name", default="", namespaces=ns) or ""
            for author in entry.findall("atom:author", ns)
        ]
        papers.append(
            Paper(
                title=title or "Untitled",
                authors=[a for a in authors if a][:5],
                venue="arXiv",
                published_date=published,
                doi_url="",
                openalex_url=entry.findtext("atom:id", default="", namespaces=ns) or "",
                cited_by_count=0,
                abstract=abstract,
                summary_zh="",
                topics=["Economics", "Finance"],
                source="arxiv",
            )
        )
    return papers


def _apply_summaries(papers: list[Paper], llm_cfg: LLMConfig) -> list[Paper]:
    for p in papers:
        p.summary_zh = _llm_zh_summary(p.title, p.abstract, p.topics, llm_cfg)
    return papers


def _load_latest_count(latest_json_path: Path) -> int:
    if not latest_json_path.exists():
        return 0
    try:
        return int(json.loads(latest_json_path.read_text(encoding="utf-8")).get("count", 0))
    except Exception:
        return 0


def build_digest(config: DigestConfig, llm_cfg: LLMConfig, run_date: dt.date | None = None) -> dict[str, Any]:
    run_date = run_date or dt.date.today()

    primary = fetch_openalex_papers(run_date, run_date)
    fallback = fetch_arxiv_finance_econ_papers(run_date) if not primary else []
    source_used = "openalex" if primary else ("arxiv-fallback" if fallback else "none")

    papers = (primary or fallback)
    papers = [p for p in papers if p.source == "arxiv" or p.cited_by_count >= config.min_citations][: config.max_papers]
    papers = _apply_summaries(papers, llm_cfg)

    config.output_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = config.output_dir / run_date.isoformat()
    daily_dir.mkdir(parents=True, exist_ok=True)

    latest_json_path = config.output_dir / "latest" / "digest.json"
    latest_count = _load_latest_count(latest_json_path)
    skip_latest_update = config.keep_latest_when_empty and len(papers) == 0 and latest_count > 0
    note = "今日抓取结果为空，已保留上一期 latest 内容，避免覆盖有效日报。" if skip_latest_update else ""

    metadata = {
        "date": run_date.isoformat(),
        "count": len(papers),
        "source_used": source_used,
        "latest_updated": not skip_latest_update,
        "papers": [dataclasses.asdict(p) for p in papers],
    }

    json_path = daily_dir / "digest.json"
    md_path = daily_dir / "digest.md"
    html_path = daily_dir / "index.html"

    json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(run_date.isoformat(), papers, note=note), encoding="utf-8")
    html_path.write_text(_render_html(run_date.isoformat(), papers, note=note), encoding="utf-8")

    latest_updated = False
    latest_dir = config.output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    if not skip_latest_update:
        (latest_dir / "digest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        (latest_dir / "digest.md").write_text(_render_markdown(run_date.isoformat(), papers), encoding="utf-8")
        (latest_dir / "index.html").write_text(_render_html(run_date.isoformat(), papers), encoding="utf-8")
        latest_updated = True

    if len(papers) == 0:
        alerts_dir = config.output_dir / "alerts"
        alerts_dir.mkdir(parents=True, exist_ok=True)
        alert = {
            "date": run_date.isoformat(),
            "level": "warning",
            "message": "No papers fetched for this run. latest preserved if previous digest exists.",
            "source_used": source_used,
        }
        (alerts_dir / f"{run_date.isoformat()}.json").write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "json": json_path,
        "markdown": md_path,
        "html": html_path,
        "count": len(papers),
        "latest_updated": latest_updated,
        "source_used": source_used,
    }


def main() -> None:
    config = DigestConfig(
        max_papers=int(os.getenv("DIGEST_MAX_PAPERS", "12")),
        min_citations=int(os.getenv("DIGEST_MIN_CITATIONS", "0")),
        output_dir=Path(os.getenv("DIGEST_OUTPUT_DIR", "output")),
        keep_latest_when_empty=os.getenv("DIGEST_KEEP_LATEST_WHEN_EMPTY", "1") == "1",
    )
    llm_cfg = LLMConfig(
        api_base=os.getenv("LLM_API_BASE", ""),
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", ""),
        timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )

    result = build_digest(config, llm_cfg=llm_cfg)
    if result["count"] == 0:
        print("::warning::No papers generated for today.")
    print(
        f"Generated digest: {result['markdown']} | count={result['count']} | "
        f"source={result['source_used']} | latest_updated={result['latest_updated']}"
    )


if __name__ == "__main__":
    main()
