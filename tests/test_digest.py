import datetime as dt
import json
from pathlib import Path

from src.digest import DigestConfig, LLMConfig, Paper, _extract_abstract, _simple_zh_summary, build_digest


def test_extract_abstract_rebuilds_word_order():
    indexed = {"InvertedIndex": {"hello": [0], "world": [1], "finance": [2]}}
    assert _extract_abstract(indexed) == "hello world finance"


def test_simple_summary_contains_title():
    text = _simple_zh_summary("Asset Pricing", "This paper studies risk premiums.", ["Economics", "Finance"])
    assert "Asset Pricing" in text
    assert "Finance" in text


def test_build_digest_writes_files(monkeypatch, tmp_path: Path):
    from src import digest as d

    dummy = Paper(
        title="A",
        authors=["B"],
        venue="C",
        published_date="2024-01-01",
        doi_url="",
        openalex_url="https://openalex.org/W123",
        cited_by_count=1,
        abstract="x",
        summary_zh="",
        topics=["Economics"],
        source="openalex",
    )

    monkeypatch.setattr(d, "fetch_openalex_papers", lambda *_args, **_kwargs: [dummy])
    monkeypatch.setattr(d, "fetch_arxiv_finance_econ_papers", lambda *_args, **_kwargs: [])

    cfg = DigestConfig(output_dir=tmp_path / "out")
    result = build_digest(cfg, llm_cfg=LLMConfig(), run_date=dt.date(2024, 1, 2))

    assert result["json"].exists()
    assert result["markdown"].exists()
    assert result["html"].exists()
    assert result["count"] == 1
    assert result["latest_updated"] is True


def test_keep_latest_when_empty(monkeypatch, tmp_path: Path):
    from src import digest as d

    monkeypatch.setattr(d, "fetch_openalex_papers", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(d, "fetch_arxiv_finance_econ_papers", lambda *_args, **_kwargs: [])

    out = tmp_path / "out"
    latest = out / "latest"
    latest.mkdir(parents=True)
    (latest / "digest.json").write_text(json.dumps({"count": 3}, ensure_ascii=False), encoding="utf-8")
    (latest / "digest.md").write_text("old", encoding="utf-8")

    cfg = DigestConfig(output_dir=out, keep_latest_when_empty=True)
    result = build_digest(cfg, llm_cfg=LLMConfig(), run_date=dt.date(2024, 1, 3))

    assert result["count"] == 0
    assert result["latest_updated"] is False
    assert (latest / "digest.md").read_text(encoding="utf-8") == "old"
    assert (out / "alerts" / "2024-01-03.json").exists()
