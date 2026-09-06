#!/usr/bin/env python3
"""Dependency-light ingestion pipeline for the paper-deep-reader skill.

The script acquires one paper, resolves metadata, creates a canonical run folder,
generates RIS/ENW records, and extracts page-addressable evidence. It deliberately
does not generate the interpretation: that remains a model-led reading task.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "paper-deep-reader/1.0 (research workflow; contact local user)"
ARXIV_RE = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v(\d+))?(?!\d)", re.I)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
CAPTION_RE = re.compile(r"^(Figure|Fig\.|Table)\s+([A-Z]?\d+(?:\.\d+)?)\s*[|:.-]\s*(.*)", re.I)
HEADING_RE = re.compile(r"^(?:(\d+(?:\.\d+)*)|([A-Z](?:\.\d+)*))\.?\s+(.{2,160})$")
INVALID_WINDOWS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def http_get(url: str, accept: str = "*/*", timeout: int = 45) -> tuple[bytes, dict[str, str], str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read()
        headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers, response.geturl()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_space(value: str) -> str:
    return " ".join(html.unescape(value or "").split())


def normalize_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", normalize_space(value)).lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def safe_filename(title: str, max_length: int = 180) -> str:
    cleaned = unicodedata.normalize("NFKC", title)
    cleaned = INVALID_WINDOWS.sub("_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "paper"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(" .")
    return cleaned


def slugify(title: str, max_length: int = 80) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_title).strip("-").lower()
    return (slug or "paper")[:max_length].rstrip("-")


def looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    except OSError:
        return False


def extract_pdf(path: Path) -> tuple[list[str], dict, object | None]:
    """Return page texts, embedded metadata, and an openable backend marker."""
    try:
        import fitz  # type: ignore

        doc = fitz.open(path)
        if doc.needs_pass:
            doc.close()
            raise RuntimeError("PDF is encrypted and requires a password")
        pages = [page.get_text("text") for page in doc]
        metadata = dict(doc.metadata or {})
        doc.close()
        return pages, metadata, "fitz"
    except ImportError:
        pdftotext = shutil.which("pdftotext")
        pdfinfo = shutil.which("pdfinfo")
        if not pdftotext:
            raise RuntimeError("PDF extraction requires PyMuPDF or the pdftotext executable")
        proc = subprocess.run([pdftotext, "-layout", str(path), "-"], capture_output=True, check=True)
        raw = proc.stdout.decode("utf-8", errors="replace")
        pages = raw.split("\f")
        metadata: dict[str, str] = {}
        if pdfinfo:
            info = subprocess.run([pdfinfo, str(path)], capture_output=True, text=True, errors="replace")
            for line in info.stdout.splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    metadata[key.strip().lower()] = value.strip()
        return pages, metadata, "pdftotext"


def infer_title_from_pdf(path: Path, first_page_text: str) -> str:
    try:
        import fitz  # type: ignore

        doc = fitz.open(path)
        blocks = doc[0].get_text("dict").get("blocks", [])
        spans: list[tuple[float, float, float, str]] = []
        height = doc[0].rect.height
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = normalize_space(span.get("text", ""))
                    x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                    if text and y0 < height * 0.42 and not re.fullmatch(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", text):
                        spans.append((float(span.get("size", 0)), y0, x0, text))
        doc.close()
        if spans:
            largest = max(size for size, _, _, _ in spans)
            selected = [(y, x, text) for size, y, x, text in spans if size >= largest - 0.5]
            selected.sort()
            title = normalize_space(" ".join(text for _, _, text in selected))
            if 8 <= len(title) <= 350:
                return title
    except Exception:
        pass

    lines = [normalize_space(x) for x in first_page_text.splitlines() if normalize_space(x)]
    lines = [x for x in lines if not re.fullmatch(r"20\d{2}[-/.]\d{1,2}[-/.]\d{1,2}", x)]
    title_lines: list[str] = []
    for line in lines[:12]:
        if title_lines and ("," in line and re.search(r"\d[*†‡]?", line)):
            break
        if re.search(r"\b(abstract|introduction)\b", line, re.I):
            break
        title_lines.append(line)
        if len(" ".join(title_lines)) > 250:
            break
    return normalize_space(" ".join(title_lines))


def arxiv_metadata(arxiv_id: str) -> dict:
    clean_id = ARXIV_RE.search(arxiv_id)
    if not clean_id:
        raise ValueError(f"Invalid arXiv identifier: {arxiv_id}")
    base = clean_id.group(1)
    query = urllib.parse.urlencode({"id_list": base, "max_results": 1})
    body, _, _ = http_get(f"https://export.arxiv.org/api/query?{query}", "application/atom+xml")
    root = ET.fromstring(body)
    entry = root.find("a:entry", ATOM)
    if entry is None:
        raise RuntimeError(f"arXiv record not found: {base}")
    links = {node.attrib.get("type", ""): node.attrib.get("href", "") for node in entry.findall("a:link", ATOM)}
    categories = [node.attrib.get("term", "") for node in entry.findall("a:category", ATOM)]
    doi_node = entry.find("arxiv:doi", ATOM)
    journal_node = entry.find("arxiv:journal_ref", ATOM)
    published = normalize_space(entry.findtext("a:published", default="", namespaces=ATOM))
    versioned = entry.findtext("a:id", default="", namespaces=ATOM).rsplit("/", 1)[-1]
    return {
        "title": normalize_space(entry.findtext("a:title", default="", namespaces=ATOM)),
        "authors": [normalize_space(a.findtext("a:name", default="", namespaces=ATOM)) for a in entry.findall("a:author", ATOM)],
        "abstract": normalize_space(entry.findtext("a:summary", default="", namespaces=ATOM)),
        "published": published,
        "updated": normalize_space(entry.findtext("a:updated", default="", namespaces=ATOM)),
        "year": published[:4] if published else "",
        "arxiv_id": base,
        "arxiv_version": versioned if versioned else base,
        "doi": normalize_space(doi_node.text if doi_node is not None else ""),
        "journal": normalize_space(journal_node.text if journal_node is not None else ""),
        "categories": [x for x in categories if x],
        "primary_category": categories[0] if categories else "",
        "abs_url": f"https://arxiv.org/abs/{versioned or base}",
        "pdf_url": links.get("application/pdf") or f"https://arxiv.org/pdf/{versioned or base}",
        "record_type": "Preprint",
        "metadata_source": "arXiv API",
    }


def arxiv_search_title(title: str) -> dict | None:
    query = urllib.parse.urlencode({"search_query": f'ti:"{title}"', "start": 0, "max_results": 5})
    body, _, _ = http_get(f"https://export.arxiv.org/api/query?{query}", "application/atom+xml")
    root = ET.fromstring(body)
    candidates: list[tuple[float, str]] = []
    for entry in root.findall("a:entry", ATOM):
        candidate_title = normalize_space(entry.findtext("a:title", default="", namespaces=ATOM))
        candidate_id = entry.findtext("a:id", default="", namespaces=ATOM).rsplit("/", 1)[-1]
        score = difflib.SequenceMatcher(None, normalize_title(title), normalize_title(candidate_title)).ratio()
        candidates.append((score, candidate_id))
    if not candidates:
        return None
    score, candidate_id = max(candidates)
    if score < 0.92:
        return None
    result = arxiv_metadata(candidate_id)
    result["title_match_score"] = round(score, 4)
    return result


def crossref_metadata(doi: str) -> dict:
    clean = DOI_RE.search(doi)
    if not clean:
        raise ValueError(f"Invalid DOI: {doi}")
    doi_value = clean.group(0).rstrip(".,;)")
    body, _, _ = http_get(f"https://api.crossref.org/works/{urllib.parse.quote(doi_value, safe='')}", "application/json")
    message = json.loads(body.decode("utf-8"))["message"]
    authors = []
    for author in message.get("author", []):
        name = normalize_space(" ".join(x for x in [author.get("given", ""), author.get("family", "")] if x))
        if name:
            authors.append(name)
    dates = message.get("published-print") or message.get("published-online") or message.get("issued") or {}
    parts = dates.get("date-parts", [[""]])[0]
    year = str(parts[0]) if parts and parts[0] else ""
    pdf_links = [
        link.get("URL", "") for link in message.get("link", [])
        if "pdf" in str(link.get("content-type", "")).lower() and link.get("URL")
    ]
    return {
        "title": normalize_space((message.get("title") or [""])[0]),
        "authors": authors,
        "abstract": normalize_space(re.sub(r"<[^>]+>", " ", message.get("abstract", ""))),
        "published": "-".join(str(x) for x in parts) if parts else "",
        "year": year,
        "doi": message.get("DOI", doi_value),
        "journal": normalize_space((message.get("container-title") or [""])[0]),
        "volume": str(message.get("volume", "")),
        "issue": str(message.get("issue", "")),
        "pages": str(message.get("page", "")),
        "url": message.get("URL", f"https://doi.org/{doi_value}"),
        "pdf_url": pdf_links[0] if pdf_links else "",
        "record_type": normalize_space(message.get("type", "Journal Article")),
        "metadata_source": "Crossref API",
    }


def openalex_oa_pdf(doi: str) -> str:
    clean = DOI_RE.search(doi)
    if not clean:
        return ""
    work_id = "https://doi.org/" + clean.group(0).rstrip(".,;)")
    body, _, _ = http_get(
        "https://api.openalex.org/works/" + urllib.parse.quote(work_id, safe=""),
        "application/json",
    )
    work = json.loads(body.decode("utf-8"))
    locations = [work.get("best_oa_location") or {}, work.get("primary_location") or {}]
    locations.extend(work.get("locations") or [])
    for location in locations:
        url = location.get("pdf_url") if isinstance(location, dict) else ""
        if url:
            return url
    return ""


def metadata_from_html(source_url: str) -> tuple[dict, str | None]:
    body, headers, final_url = http_get(source_url, "text/html,application/pdf")
    if body[:5] == b"%PDF-" or "application/pdf" in headers.get("content-type", "").lower():
        return {"source_url": final_url}, final_url
    text = body.decode(headers.get("charset", "utf-8"), errors="replace")
    meta_pairs = re.findall(r'<meta\s+[^>]*(?:name|property)=["\']([^"\']+)["\'][^>]*content=["\']([^"\']*)["\'][^>]*>', text, re.I)
    meta = {name.lower(): html.unescape(value) for name, value in meta_pairs}
    authors = [html.unescape(x) for x in re.findall(r'<meta\s+[^>]*name=["\']citation_author["\'][^>]*content=["\']([^"\']+)', text, re.I)]
    result = {
        "title": normalize_space(meta.get("citation_title") or meta.get("og:title") or ""),
        "authors": [normalize_space(x) for x in authors],
        "doi": normalize_space(meta.get("citation_doi", "")),
        "published": normalize_space(meta.get("citation_publication_date", "")),
        "journal": normalize_space(meta.get("citation_journal_title", "")),
        "source_url": final_url,
        "metadata_source": "HTML citation metadata",
    }
    pdf_url = meta.get("citation_pdf_url")
    if pdf_url:
        pdf_url = urllib.parse.urljoin(final_url, pdf_url)
    return result, pdf_url


def acquire_source(source: str, temp_dir: Path) -> tuple[Path, dict, bool]:
    path = Path(source).expanduser()
    if path.exists():
        if not path.is_file() or not looks_like_pdf(path):
            raise RuntimeError(f"Local input is not a readable PDF: {path}")
        return path.resolve(), {"source_kind": "local", "source_url": ""}, True

    arxiv = ARXIV_RE.search(source)
    if arxiv and ("arxiv" in source.lower() or re.fullmatch(r"\d{4}\.\d{4,5}(?:v\d+)?", source.strip(), re.I)):
        metadata = arxiv_metadata(arxiv.group(0))
        pdf_url = metadata["pdf_url"]
        body, _, final_url = http_get(pdf_url, "application/pdf")
        temp_path = temp_dir / "download.pdf"
        temp_path.write_bytes(body)
        metadata.update({"source_kind": "arxiv", "source_url": metadata["abs_url"], "download_url": final_url})
        return temp_path, metadata, False

    if source.lower().startswith(("http://", "https://")):
        metadata, pdf_url = metadata_from_html(source)
        target_url = pdf_url or source
        body, headers, final_url = http_get(target_url, "application/pdf,text/html")
        if body[:5] != b"%PDF-" and "application/pdf" not in headers.get("content-type", "").lower():
            raise RuntimeError("The URL did not resolve unambiguously to a PDF; provide a direct PDF URL")
        temp_path = temp_dir / "download.pdf"
        temp_path.write_bytes(body)
        metadata.update({"source_kind": "url", "source_url": source, "download_url": final_url})
        return temp_path, metadata, False

    if DOI_RE.search(source):
        metadata = crossref_metadata(source)
        pdf_url = metadata.get("pdf_url", "")
        if not pdf_url:
            try:
                pdf_url = openalex_oa_pdf(source)
            except Exception:
                pdf_url = ""
        if not pdf_url:
            raise RuntimeError(
                "DOI metadata was resolved, but no open PDF URL was established. "
                f"Provide the PDF or an open-access URL. Resolved title: {metadata.get('title')}"
            )
        body, headers, final_url = http_get(pdf_url, "application/pdf")
        if body[:5] != b"%PDF-" and "application/pdf" not in headers.get("content-type", "").lower():
            raise RuntimeError("The DOI open-access location did not return a PDF")
        temp_path = temp_dir / "download.pdf"
        temp_path.write_bytes(body)
        metadata.update({"source_kind": "doi", "source_url": metadata.get("url", ""), "download_url": final_url})
        return temp_path, metadata, False
    raise RuntimeError(f"Input is not a local PDF, supported URL, arXiv ID, or DOI: {source}")


def merge_metadata(primary: dict, secondary: dict) -> dict:
    result = dict(secondary)
    for key, value in primary.items():
        if value not in (None, "", [], {}):
            result[key] = value
    return result


def resolve_metadata(pdf_path: Path, pages: list[str], embedded: dict, supplied: dict, arxiv_id: str = "") -> dict:
    inferred_title = normalize_space(embedded.get("title", "")) or infer_title_from_pdf(pdf_path, pages[0] if pages else "")
    authority: dict = {}
    if arxiv_id:
        authority = arxiv_metadata(arxiv_id)
    elif supplied.get("arxiv_id"):
        authority = arxiv_metadata(supplied["arxiv_id"])
    elif supplied.get("title") and supplied.get("authors"):
        authority = supplied
    elif inferred_title:
        try:
            authority = arxiv_search_title(inferred_title) or {}
        except Exception:
            authority = {}
    if not authority and supplied.get("doi"):
        authority = crossref_metadata(supplied["doi"])
    if not authority and DOI_RE.search("\n".join(pages[:3])):
        # Do not automatically use a DOI found in body text; it may cite another work.
        pass
    metadata = merge_metadata(authority, supplied)
    metadata.setdefault("title", inferred_title)
    metadata.setdefault("authors", [])
    metadata.setdefault("abstract", "")
    metadata.setdefault("year", str(metadata.get("published", ""))[:4])
    metadata.setdefault("record_type", "Preprint" if metadata.get("arxiv_id") else "Research Paper")
    metadata["pdf_embedded_metadata"] = embedded
    metadata["inferred_pdf_title"] = inferred_title
    if not metadata.get("title") or len(metadata["title"]) < 8:
        raise RuntimeError("Could not resolve a credible paper title")
    if not metadata.get("authors"):
        raise RuntimeError("Could not resolve an author list; provide an arXiv ID or DOI")
    if authority.get("title") and inferred_title:
        score = difflib.SequenceMatcher(None, normalize_title(authority["title"]), normalize_title(inferred_title)).ratio()
        metadata["identity_title_score"] = round(score, 4)
        if score < 0.92:
            raise RuntimeError(f"Metadata/PDF title conflict (similarity={score:.3f}); manual confirmation required")
    metadata["resolved_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    return metadata


def unique_destination(directory: Path, stem: str, suffix: str, source_hash: str, identity_suffix: str = "") -> Path:
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    if sha256(candidate) == source_hash:
        return candidate
    extra = safe_filename(identity_suffix, 32) if identity_suffix else source_hash[:8]
    return directory / f"{stem} - {extra}{suffix}"


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ris_type(metadata: dict) -> str:
    return "JOUR" if metadata.get("journal") and metadata.get("doi") else "PREPRINT"


def generate_ris(metadata: dict, pdf_path: Path) -> str:
    lines = [f"TY  - {ris_type(metadata)}", f"TI  - {metadata['title']}"]
    for author in metadata.get("authors", []):
        lines.append(f"AU  - {author}")
    mapping = [
        ("PY", metadata.get("year")), ("DA", metadata.get("published")),
        ("JO", metadata.get("journal")), ("VL", metadata.get("volume")),
        ("IS", metadata.get("issue")), ("SP", metadata.get("pages")),
        ("DO", metadata.get("doi")), ("UR", metadata.get("abs_url") or metadata.get("url") or metadata.get("source_url")),
        ("AB", metadata.get("abstract")),
    ]
    for tag, value in mapping:
        if value:
            lines.append(f"{tag}  - {normalize_space(str(value))}")
    for keyword in metadata.get("categories", []):
        lines.append(f"KW  - {keyword}")
    lines.extend([f"L1  - {pdf_path.as_uri()}", "ER  - ", ""])
    return "\r\n".join(lines)


def generate_enw(metadata: dict, pdf_path: Path) -> str:
    record_type = "Journal Article" if ris_type(metadata) == "JOUR" else "Preprint"
    lines = [f"%0 {record_type}", f"%T {metadata['title']}"]
    for author in metadata.get("authors", []):
        lines.append(f"%A {author}")
    mapping = [
        ("%D", metadata.get("year")), ("%J", metadata.get("journal")),
        ("%V", metadata.get("volume")), ("%N", metadata.get("issue")),
        ("%P", metadata.get("pages")), ("%R", metadata.get("doi")),
        ("%U", metadata.get("abs_url") or metadata.get("url") or metadata.get("source_url")),
        ("%X", metadata.get("abstract")),
    ]
    for tag, value in mapping:
        if value:
            lines.append(f"{tag} {normalize_space(str(value))}")
    for keyword in metadata.get("categories", []):
        lines.append(f"%K {keyword}")
    lines.extend([f"%> {pdf_path}", ""])
    return "\r\n".join(lines)


def capture_caption(lines: list[str], start: int) -> tuple[str, int]:
    match = CAPTION_RE.match(normalize_space(lines[start]))
    if not match:
        return "", start
    chunks = [normalize_space(match.group(3))]
    index = start + 1
    while index < len(lines) and len(" ".join(chunks)) < 1800:
        candidate = normalize_space(lines[index])
        if not candidate or CAPTION_RE.match(candidate) or HEADING_RE.match(candidate):
            break
        if re.fullmatch(r"\d+", candidate):
            break
        chunks.append(candidate)
        index += 1
    return normalize_space(" ".join(chunks)), index


def build_evidence(run_dir: Path, pdf_path: Path, pages: list[str], backend: object) -> dict:
    evidence_dir = run_dir / "evidence"
    figures_dir = evidence_dir / "figures"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    full_text = []
    section_records = []
    index_records = []
    caption_pages: set[int] = set()
    current_section = "Front matter"
    for page_no, text in enumerate(pages, 1):
        full_text.extend([f"## Page {page_no}", "", text.rstrip(), ""])
        lines = text.splitlines()
        headings = []
        for line_no, raw in enumerate(lines, 1):
            line = normalize_space(raw)
            heading = HEADING_RE.match(line)
            if heading and len(line) <= 170 and not line.endswith((".", ",", ";")):
                current_section = line
                headings.append(line)
                index_records.append({"type": "section", "page": page_no, "line": line_no, "section": line, "text": line, "source_status": "paper-explicit"})
            caption = CAPTION_RE.match(line)
            if caption:
                caption_text, _ = capture_caption(lines, line_no - 1)
                kind = "figure" if caption.group(1).lower().startswith("fig") else "table"
                identifier = caption.group(2)
                index_records.append({"type": kind, "page": page_no, "line": line_no, "section": current_section, "figure_or_table_id": f"{kind.title()} {identifier}", "text": caption_text, "source_status": "paper-explicit"})
                caption_pages.add(page_no)
        section_records.append({"page": page_no, "section": current_section, "headings": headings, "text": text})

    (evidence_dir / "full_text.md").write_text("\n".join(full_text), encoding="utf-8")
    with (evidence_dir / "sections.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in section_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with (evidence_dir / "evidence_index.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in index_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    rendered = []
    if backend == "fitz" and caption_pages:
        import fitz  # type: ignore

        doc = fitz.open(pdf_path)
        for page_no in sorted(caption_pages):
            target = figures_dir / f"page-{page_no:02d}.png"
            pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            pix.save(target)
            rendered.append(str(target.relative_to(run_dir)).replace("\\", "/"))
        doc.close()
    return {
        "page_count": len(pages),
        "character_count": sum(len(x) for x in pages),
        "nonempty_page_ratio": round(sum(bool(x.strip()) for x in pages) / max(1, len(pages)), 4),
        "index_record_count": len(index_records),
        "caption_pages": sorted(caption_pages),
        "rendered_pages": rendered,
        "backend": backend,
    }


def ingest(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else Path.cwd().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="paper-deep-reader-") as tmp:
        temp_dir = Path(tmp)
        acquired, supplied, is_local = acquire_source(args.source, temp_dir)
        source_hash = sha256(acquired)
        pages, embedded, backend = extract_pdf(acquired)
        if not pages or not any(x.strip() for x in pages):
            raise RuntimeError("PDF contains no extractable text")
        nonempty_ratio = sum(bool(x.strip()) for x in pages) / len(pages)
        median_chars = sorted(len(x.strip()) for x in pages)[len(pages) // 2]
        if nonempty_ratio < 0.8 or median_chars < 300:
            raise RuntimeError("PDF text extraction quality is too low; OCR is required but not available in this pipeline")
        metadata = resolve_metadata(acquired, pages, embedded, supplied, args.arxiv_id)
        title = metadata["title"]
        stem = safe_filename(title)
        run_dir = output_root / slugify(title)
        source_dir = run_dir / "source"
        reference_dir = run_dir / "reference"
        source_dir.mkdir(parents=True, exist_ok=True)
        reference_dir.mkdir(parents=True, exist_ok=True)
        identity_suffix = metadata.get("arxiv_id") or metadata.get("doi", "").replace("/", "_")
        destination = unique_destination(source_dir, stem, ".pdf", source_hash, identity_suffix)
        if not destination.exists():
            if is_local and not args.copy_local:
                shutil.move(str(acquired), str(destination))
            else:
                shutil.copy2(acquired, destination)
        elif is_local and acquired.resolve() != destination.resolve() and not args.copy_local:
            acquired.unlink()
        metadata["local_pdf"] = str(destination)
        metadata["sha256"] = source_hash
        metadata["page_count"] = len(pages)
        write_json(run_dir / "metadata.json", metadata)
        manifest = {
            "schema": "paper-deep-reader.source-manifest.v1",
            "input": args.source,
            "input_was_local": is_local,
            "copy_local": bool(args.copy_local),
            "canonical_pdf": str(destination),
            "sha256": source_hash,
            "identity": {k: metadata.get(k) for k in ["title", "authors", "year", "doi", "arxiv_id", "metadata_source", "identity_title_score"]},
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        write_json(run_dir / "source_manifest.json", manifest)
        ris_path = reference_dir / f"{stem}.ris"
        enw_path = reference_dir / f"{stem}.enw"
        ris_path.write_text(generate_ris(metadata, destination), encoding="utf-8", newline="")
        enw_path.write_text(generate_enw(metadata, destination), encoding="utf-8", newline="")
        extraction = build_evidence(run_dir, destination, pages, backend)
        write_json(run_dir / "evidence" / "extraction_report.json", extraction)
        print(json.dumps({
            "status": "ok", "run_dir": str(run_dir), "pdf": str(destination),
            "metadata": str(run_dir / "metadata.json"), "ris": str(ris_path), "enw": str(enw_path),
            "evidence": str(run_dir / "evidence"), "extraction": extraction,
        }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Acquire, organize, and extract one research paper")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_parser = sub.add_parser("ingest", help="Run acquisition, metadata, bibliography, and evidence extraction")
    ingest_parser.add_argument("source", help="Local PDF, PDF/landing-page URL, arXiv ID/URL, or DOI")
    ingest_parser.add_argument("--output-root", default="", help="Parent directory for the canonical paper run")
    ingest_parser.add_argument("--arxiv-id", default="", help="Authoritative arXiv identifier for a local PDF")
    ingest_parser.add_argument("--copy-local", action="store_true", help="Copy rather than move a local PDF")
    ingest_parser.set_defaults(func=ingest)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (RuntimeError, ValueError, urllib.error.URLError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
