#!/usr/bin/env python3
"""Validate paper-deep-reader ingestion or final deliverables."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MODULES = [
    "01-论文总结.md",
    "02-问题定义.md",
    "03-核心原理.md",
    "04-模型或研究方法.md",
    "05-数据与输入输出.md",
    "06-训练与推理或实验流程.md",
    "07-张量维度或变量尺度.md",
    "08-图表解读.md",
    "09-局限与研究问题.md",
]
PLACEHOLDERS = re.compile(r"(?:xxxxx|xxxx|TODO|TBD|待补充|待确认)", re.I)
ANCHOR = re.compile(r"\[证据:\s*p\.\s*\d+(?:[^\]]*)\]", re.I)
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"invalid JSON {path.name}: {exc}")
        return {}


def validate_bibliography(path: Path, kind: str, metadata: dict, pdf_path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing bibliography file: {path}")
        return
    text = path.read_text(encoding="utf-8-sig")
    title = metadata.get("title", "")
    if title and title not in text:
        errors.append(f"{kind} title differs from metadata")
    author_count = len(metadata.get("authors", []))
    if kind == "RIS":
        if not text.startswith("TY  - ") or "\nER  -" not in text.replace("\r\n", "\n"):
            errors.append("RIS missing TY or ER record marker")
        if text.count("AU  - ") != author_count:
            errors.append("RIS author count differs from metadata")
        if f"L1  - {pdf_path.as_uri()}" not in text:
            errors.append("RIS attachment path is missing or invalid")
    else:
        if not text.startswith("%0 ") or "%T " not in text:
            errors.append("ENW missing %0 or %T")
        if text.count("%A ") != author_count:
            errors.append("ENW author count differs from metadata")
        if f"%> {pdf_path}" not in text:
            errors.append("ENW attachment path is missing or invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--stage", choices=["ingest", "final"], default="final")
    parser.add_argument("--min-chinese-chars", type=int, default=12000)
    args = parser.parse_args()
    run_dir = Path(args.run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    metadata_path = run_dir / "metadata.json"
    manifest_path = run_dir / "source_manifest.json"
    if not metadata_path.exists(): errors.append("missing metadata.json")
    if not manifest_path.exists(): errors.append("missing source_manifest.json")
    metadata = load_json(metadata_path, errors) if metadata_path.exists() else {}
    manifest = load_json(manifest_path, errors) if manifest_path.exists() else {}
    pdf_path = Path(manifest.get("canonical_pdf", "")) if manifest.get("canonical_pdf") else Path()
    if not pdf_path.is_file():
        errors.append(f"canonical PDF does not exist: {pdf_path}")
    elif digest(pdf_path) != manifest.get("sha256"):
        errors.append("canonical PDF SHA-256 differs from manifest")
    for key in ["title", "authors", "year", "sha256", "page_count"]:
        if metadata.get(key) in (None, "", []): errors.append(f"metadata missing {key}")

    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", metadata.get("title", "")).strip(" .")[:180].rstrip(" .")
    if stem:
        validate_bibliography(run_dir / "reference" / f"{stem}.ris", "RIS", metadata, pdf_path, errors)
        validate_bibliography(run_dir / "reference" / f"{stem}.enw", "ENW", metadata, pdf_path, errors)

    evidence = run_dir / "evidence"
    for name in ["full_text.md", "sections.jsonl", "evidence_index.jsonl", "extraction_report.json"]:
        path = evidence / name
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"missing or empty evidence/{name}")
    if (evidence / "extraction_report.json").exists():
        report = load_json(evidence / "extraction_report.json", errors)
        if report.get("page_count") != metadata.get("page_count"):
            errors.append("page count differs between metadata and extraction report")
        if report.get("nonempty_page_ratio", 0) < 0.8:
            errors.append("insufficient extractable page coverage")

    if args.stage == "final":
        modules_dir = run_dir / "modules"
        module_texts = []
        for name in MODULES:
            path = modules_dir / name
            if not path.exists() or path.stat().st_size < 300:
                errors.append(f"missing or too short module: {name}")
                continue
            text = path.read_text(encoding="utf-8")
            module_texts.append(text)
            if PLACEHOLDERS.search(text): errors.append(f"unresolved placeholder in {name}")
            if "不适用" not in text and len(ANCHOR.findall(text)) < 2:
                errors.append(f"too few evidence anchors in {name}")
        finals = list(run_dir.glob("*--中文深度解读.md"))
        if len(finals) != 1:
            errors.append(f"expected exactly one final article, found {len(finals)}")
        else:
            final_path = finals[0]
            text = final_path.read_text(encoding="utf-8")
            if PLACEHOLDERS.search(text): errors.append("unresolved placeholder in final article")
            chinese_chars = len(re.findall(r"[\u3400-\u9fff]", text))
            if chinese_chars < args.min_chinese_chars:
                errors.append(f"final article has {chinese_chars} Chinese characters; minimum is {args.min_chinese_chars}")
            anchor_count = len(ANCHOR.findall(text))
            if anchor_count < 20:
                errors.append(f"final article has only {anchor_count} page evidence anchors; minimum is 20")
            headings = re.findall(r"^#{1,3}\s+.+$", text, re.M)
            if len(headings) < 15:
                errors.append("final article has too few structured headings")
            for target in MARKDOWN_LINK.findall(text):
                if re.match(r"(?:https?|mailto):", target):
                    continue
                local = (final_path.parent / urllib_unquote(target.split("#", 1)[0])).resolve()
                if target and not local.exists():
                    errors.append(f"broken Markdown link: {target}")
            if not re.search(r"^##\s+证据索引", text, re.M):
                warnings.append("final article has no dedicated 证据索引 heading")

    result = {
        "status": "passed" if not errors else "failed",
        "stage": args.stage,
        "run_dir": str(run_dir),
        "errors": errors,
        "warnings": warnings,
    }
    report_path = run_dir / f"validation_{args.stage}.json"
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["report"] = str(report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def urllib_unquote(value: str) -> str:
    from urllib.parse import unquote
    return unquote(value)


if __name__ == "__main__":
    raise SystemExit(main())
