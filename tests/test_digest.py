import datetime as dt
from pathlib import Path

from src.digest import DigestConfig, Paper, _extract_abstract, _simple_zh_summary, build_digest


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
        summary_zh="y",
        topics=["Economics"],
    )

    monkeypatch.setattr(d, "fetch_openalex_papers", lambda *_args, **_kwargs: [dummy])
    cfg = DigestConfig(output_dir=tmp_path / "out")
    result = build_digest(cfg, run_date=dt.date(2024, 1, 2))

    assert result["json"].exists()
    assert result["markdown"].exists()
    assert result["html"].exists()
