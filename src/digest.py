from __future__ import annotations

import dataclasses
import datetime as dt
import html
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import URLError
from urllib.request import urlopen


OPENALEX_URL = "https://api.openalex.org/works"


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


@dataclasses.dataclass
class DigestConfig:
    max_papers: int = 12
    min_citations: int = 0
    output_dir: Path = Path("output")


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
    names: list[str] = []
    for c in concepts[:5]:
        name = c.get("display_name")
        if name:
            names.append(name)
    return names


def _simple_zh_summary(title: str, abstract: str, topics: list[str]) -> str:
    short_abs = abstract.strip().replace("\n", " ")
    if len(short_abs) > 180:
        short_abs = short_abs[:177] + "..."

    topic_text = "、".join(topics[:3]) if topics else "金融经济学"
    if short_abs:
        return f"这篇论文围绕“{title}”展开，主题涉及{topic_text}。核心内容：{short_abs}"
    return f"这篇论文围绕“{title}”展开，主题涉及{topic_text}。可进一步阅读全文获取研究方法与结论。"


def _render_markdown(date: str, papers: list[Paper]) -> str:
    lines = [f"# 金融经济学每日文献速递（{date}）", "", f"共筛选到 **{len(papers)}** 篇文献。", ""]
    for idx, p in enumerate(papers, start=1):
        links = []
        if p.doi_url:
            links.append(f"[DOI]({p.doi_url})")
        if p.openalex_url:
            links.append(f"[OpenAlex]({p.openalex_url})")
        lines.extend(
            [
                f"## {idx}. {p.title}",
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


def _render_html(date: str, papers: list[Paper]) -> str:
    cards = []
    for idx, p in enumerate(papers, start=1):
        doi_link = f'<a href="{html.escape(p.doi_url)}" target="_blank" rel="noopener noreferrer">DOI</a>' if p.doi_url else ""
        oa_link = f'<a href="{html.escape(p.openalex_url)}" target="_blank" rel="noopener noreferrer">OpenAlex</a>' if p.openalex_url else ""
        sep = " | " if doi_link and oa_link else ""
        cards.append(
            f"""
  <article class=\"card\"> 
    <h2>{idx}. {html.escape(p.title)}</h2>
    <p class=\"meta\">作者：{html.escape(', '.join(p.authors) if p.authors else 'N/A')}</p>
    <p class=\"meta\">来源：{html.escape(p.venue)}｜发表：{html.escape(p.published_date)}｜引用数：{p.cited_by_count}</p>
    <p class=\"meta\">主题：{html.escape(', '.join(p.topics) if p.topics else 'N/A')}</p>
    <p>{doi_link}{sep}{oa_link}</p>
    <p class=\"summary\"><strong>中文摘要（自动生成）:</strong> {html.escape(p.summary_zh)}</p>
  </article>
            """.strip()
        )

    cards_html = "\n".join(cards)
    return f"""<!doctype html>
<html lang=\"zh-CN\"> 
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>金融经济学每日文献速递 - {html.escape(date)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem auto; max-width: 900px; line-height: 1.6; color: #111; padding: 0 1rem; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .card {{ border: 1px solid #e6e6e6; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }}
    .meta {{ color: #666; font-size: 0.95rem; }}
    .summary {{ background: #f8f8f8; padding: 0.8rem; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>金融经济学每日文献速递</h1>
  <p class=\"meta\">日期：{html.escape(date)}｜篇数：{len(papers)}</p>
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

    params = urlencode(
        {
            "filter": ",".join(filters),
            "sort": "cited_by_count:desc",
            "per-page": per_page,
        }
    )

    try:
        with urlopen(f"{OPENALEX_URL}?{params}", timeout=30) as response:
            data = json.loads(response.read().decode("utf-8")).get("results", [])
    except URLError:
        return []

    papers: list[Paper] = []
    for item in data:
        title = item.get("title") or "Untitled"
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in item.get("authorships", [])[:5]
            if a.get("author", {}).get("display_name")
        ]
        venue = item.get("primary_location", {}).get("source", {}).get("display_name") or "Unknown"
        published_date = item.get("publication_date") or ""
        doi = item.get("doi") or ""
        doi_url = doi if doi.startswith("http") else (f"https://doi.org/{doi}" if doi else "")
        openalex_url = item.get("id", "")
        cited_by_count = item.get("cited_by_count", 0)
        abstract = _extract_abstract(item.get("abstract_inverted_index"))
        topics = _topic_names(item.get("concepts", []))
        summary_zh = _simple_zh_summary(title, abstract, topics)

        papers.append(
            Paper(
                title=title,
                authors=authors,
                venue=venue,
                published_date=published_date,
                doi_url=doi_url,
                openalex_url=openalex_url,
                cited_by_count=cited_by_count,
                abstract=abstract,
                summary_zh=summary_zh,
                topics=topics,
            )
        )

    return papers


def build_digest(config: DigestConfig, run_date: dt.date | None = None) -> dict[str, Path]:
    run_date = run_date or dt.date.today()
    papers = fetch_openalex_papers(run_date, run_date)
    papers = [p for p in papers if p.cited_by_count >= config.min_citations][: config.max_papers]

    config.output_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = config.output_dir / run_date.isoformat()
    daily_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "date": run_date.isoformat(),
        "count": len(papers),
        "papers": [dataclasses.asdict(p) for p in papers],
    }
    json_path = daily_dir / "digest.json"
    json_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    md_text = _render_markdown(run_date.isoformat(), papers)
    html_text = _render_html(run_date.isoformat(), papers)

    md_path = daily_dir / "digest.md"
    html_path = daily_dir / "index.html"
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")

    latest_dir = config.output_dir / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "digest.md").write_text(md_text, encoding="utf-8")
    (latest_dir / "index.html").write_text(html_text, encoding="utf-8")

    return {"json": json_path, "markdown": md_path, "html": html_path}


def main() -> None:
    max_papers = int(os.getenv("DIGEST_MAX_PAPERS", "12"))
    min_citations = int(os.getenv("DIGEST_MIN_CITATIONS", "0"))
    output_dir = Path(os.getenv("DIGEST_OUTPUT_DIR", "output"))

    config = DigestConfig(
        max_papers=max_papers,
        min_citations=min_citations,
        output_dir=output_dir,
    )

    result = build_digest(config)
    print(f"Generated digest: {result['markdown']}")


if __name__ == "__main__":
    main()
