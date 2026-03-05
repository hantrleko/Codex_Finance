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
    assert "内容概述" in text
    assert "方法线索" in text


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


def test_fetch_openalex_handles_null_primary_location(monkeypatch):
    from src import digest as d

    class DummyResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            payload = {
                "results": [
                    {
                        "title": "Test Paper",
                        "authorships": [{"author": {"display_name": "Alice"}}],
                        "primary_location": None,
                        "publication_date": "2026-01-01",
                        "doi": "10.1000/test",
                        "id": "https://openalex.org/W1",
                        "cited_by_count": 5,
                        "abstract_inverted_index": None,
                        "concepts": [],
                    }
                ]
            }
            return json.dumps(payload).encode("utf-8")

    monkeypatch.setattr(d, "urlopen", lambda *args, **kwargs: DummyResponse())
    papers = d.fetch_openalex_papers(dt.date(2026, 1, 1), dt.date(2026, 1, 1))

    assert len(papers) == 1
    assert papers[0].venue == "Unknown"
    assert papers[0].authors == ["Alice"]


def test_dedupe_and_relevance_filter_removes_noise():
    from src.digest import _dedupe_and_filter

    papers = [
        Paper(
            title="SENTINEL: Symbiotic Ecosystem Networks for Transparent, Intelligent, and Ecologically-Locked Trading",
            authors=["A"],
            venue="Zenodo",
            published_date="2026-03-05",
            doi_url="",
            openalex_url="https://openalex.org/W1",
            cited_by_count=0,
            abstract="A framework for financial market risk monitoring.",
            summary_zh="",
            topics=["Algorithmic trading", "Financial market"],
            source="openalex",
        ),
        Paper(
            title="SENTINEL: Symbiotic Ecosystem Networks for Transparent, Intelligent, and Ecologically-Locked Trading",
            authors=["A"],
            venue="Zenodo",
            published_date="2026-03-05",
            doi_url="",
            openalex_url="https://openalex.org/W2",
            cited_by_count=0,
            abstract="Duplicate title should be removed.",
            summary_zh="",
            topics=["Algorithmic trading", "Financial market"],
            source="openalex",
        ),
        Paper(
            title="Free Dice Links for Monopoly GO – Claim Daily Rewards Instantly [23gfOu]",
            authors=["Spam"],
            venue="Unknown",
            published_date="2026-03-05",
            doi_url="",
            openalex_url="https://openalex.org/W3",
            cited_by_count=0,
            abstract="",
            summary_zh="",
            topics=["Economics"],
            source="openalex",
        ),
    ]

    filtered = _dedupe_and_filter(
        papers,
        topic_whitelist={"financial", "market", "trading", "economics"},
        topic_blacklist={"free dice", "monopoly go"},
        min_quality_score=2,
    )
    assert len(filtered) == 1
    assert "SENTINEL" in filtered[0].title


def test_relevance_filter_drops_irrelevant_openalex_paper(monkeypatch, tmp_path: Path):
    from src import digest as d

    noisy = Paper(
        title="The Groundskeeper's Treatise: A Diagnostic Reading of Platform Stewardship Theory",
        authors=["L"],
        venue="Zenodo",
        published_date="2026-03-05",
        doi_url="",
        openalex_url="https://openalex.org/W9",
        cited_by_count=0,
        abstract="Discussion of semantic reading process.",
        summary_zh="",
        topics=["Reading (process)", "Semantic theory of truth"],
        source="openalex",
    )

    monkeypatch.setattr(d, "fetch_openalex_papers", lambda *_args, **_kwargs: [noisy])
    monkeypatch.setattr(d, "fetch_arxiv_finance_econ_papers", lambda *_args, **_kwargs: [])

    cfg = DigestConfig(output_dir=tmp_path / "out")
    result = build_digest(cfg, llm_cfg=LLMConfig(), run_date=dt.date(2026, 3, 5))

    assert result["count"] == 0


def test_relevance_filter_respects_custom_whitelist_threshold(monkeypatch, tmp_path: Path):
    from src import digest as d

    candidate = Paper(
        title="Credit risk pricing in banking markets",
        authors=["A"],
        venue="Journal",
        published_date="2026-03-05",
        doi_url="",
        openalex_url="https://openalex.org/W10",
        cited_by_count=0,
        abstract="We run panel regression models to estimate default risk.",
        summary_zh="",
        topics=["Risk", "Banking"],
        source="openalex",
    )

    monkeypatch.setattr(d, "fetch_openalex_papers", lambda *_args, **_kwargs: [candidate])
    monkeypatch.setattr(d, "fetch_arxiv_finance_econ_papers", lambda *_args, **_kwargs: [])

    strict_cfg = DigestConfig(
        output_dir=tmp_path / "strict",
        topic_whitelist={"credit"},
        min_quality_score=4,
    )
    strict_result = build_digest(strict_cfg, llm_cfg=LLMConfig(), run_date=dt.date(2026, 3, 5))
    assert strict_result["count"] == 0

    relaxed_cfg = DigestConfig(
        output_dir=tmp_path / "relaxed",
        topic_whitelist={"credit", "risk", "banking"},
        min_quality_score=3,
    )
    relaxed_result = build_digest(relaxed_cfg, llm_cfg=LLMConfig(), run_date=dt.date(2026, 3, 5))
    assert relaxed_result["count"] == 1
