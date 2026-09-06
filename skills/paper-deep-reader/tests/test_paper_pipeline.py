from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "paper_pipeline.py"
SPEC = importlib.util.spec_from_file_location("paper_pipeline", SCRIPT)
assert SPEC and SPEC.loader
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


def test_safe_filename_windows_and_length():
    value = pipeline.safe_filename('A <paper>: weather/AI? *results* | 2026.', max_length=40)
    assert value == "A _paper__ weather_AI_ _results_ _ 2026"
    assert len(value) <= 40
    assert not any(char in value for char in '<>:"/\\|?*')


def test_slugify_is_stable():
    assert pipeline.slugify("WeatherNext 3: Raw Observations") == "weathernext-3-raw-observations"


def test_ris_and_enw_author_mapping(tmp_path: Path):
    pdf = tmp_path / "Paper.pdf"
    pdf.write_bytes(b"%PDF-test")
    metadata = {
        "title": "Paper Title",
        "authors": ["Ada Lovelace", "Grace Hopper"],
        "year": "2026",
        "published": "2026-09-03",
        "arxiv_id": "2609.00001",
        "abs_url": "https://arxiv.org/abs/2609.00001",
        "abstract": "Abstract text.",
        "categories": ["cs.LG"],
    }
    ris = pipeline.generate_ris(metadata, pdf)
    enw = pipeline.generate_enw(metadata, pdf)
    assert ris.startswith("TY  - PREPRINT")
    assert ris.count("AU  - ") == 2
    assert "ER  - " in ris
    assert pdf.as_uri() in ris
    assert enw.startswith("%0 Preprint")
    assert enw.count("%A ") == 2
    assert f"%> {pdf}" in enw


def test_caption_capture():
    lines = [
        "Figure 2 | Main result.",
        "Lower values are better for all lead times.",
        "",
        "2. Methods",
    ]
    text, stop = pipeline.capture_caption(lines, 0)
    assert text == "Main result. Lower values are better for all lead times."
    assert stop == 2


def test_arxiv_and_doi_detection():
    assert pipeline.ARXIV_RE.search("https://arxiv.org/abs/2609.03582v1").group(1) == "2609.03582"
    assert pipeline.DOI_RE.search("doi:10.1000/example.1").group(0) == "10.1000/example.1"


def test_acquire_direct_pdf_url(monkeypatch, tmp_path: Path):
    def fake_html(url, accept="*/*", timeout=45):
        return ({"title": "Remote Paper"}, url)

    def fake_get(url, accept="*/*", timeout=45):
        return b"%PDF-1.7\nmock", {"content-type": "application/pdf"}, url

    monkeypatch.setattr(pipeline, "metadata_from_html", fake_html)
    monkeypatch.setattr(pipeline, "http_get", fake_get)
    path, metadata, is_local = pipeline.acquire_source("https://example.org/paper.pdf", tmp_path)
    assert path.read_bytes().startswith(b"%PDF-")
    assert metadata["source_kind"] == "url"
    assert is_local is False


def test_acquire_doi_from_open_pdf(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(pipeline, "crossref_metadata", lambda doi: {
        "title": "DOI Paper", "authors": ["A. Author"], "doi": doi,
        "url": f"https://doi.org/{doi}", "pdf_url": "https://example.org/oa.pdf",
    })
    monkeypatch.setattr(pipeline, "http_get", lambda url, accept="*/*", timeout=45: (
        b"%PDF-1.7\nmock", {"content-type": "application/pdf"}, url
    ))
    path, metadata, is_local = pipeline.acquire_source("10.1000/example.1", tmp_path)
    assert path.read_bytes().startswith(b"%PDF-")
    assert metadata["source_kind"] == "doi"
    assert is_local is False
