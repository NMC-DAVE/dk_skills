#!/usr/bin/env python3
"""Extract the small IDL discovery index from an upstream vscode-idl checkout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TYPES = {"f": "Function", "p": "Procedure", "fm": "FunctionMethod",
         "pm": "ProcedureMethod", "s": "StructureOrClassDefinition", "sv": "SystemVariable"}


def build_catalog(upstream: Path) -> dict:
    source = upstream / "resources/idl/routines/routines.json"
    content = source.read_bytes()
    rows = json.loads(content)
    routines = {}
    for row in rows:
        name = row.get("name")
        if (not name or row.get("source") not in {"idl", "internal"}
                or not row.get("link", "").startswith("/idl/") or row.get("type") not in TYPES):
            continue
        key = (name.lower(), TYPES[row["type"]])
        routines[key] = {"name": name, "type": key[1], "source": row["source"], "link": row["link"]}
    return {
        "upstream": "https://github.com/interactive-data-language/vscode-idl",
        "upstream_version": json.loads((upstream / "package.json").read_text(encoding="utf-8"))["version"],
        "source_file": "resources/idl/routines/routines.json",
        "source_sha256": hashlib.sha256(content).hexdigest(),
        "rule": "Named idl/internal entries with /idl/ links; deduplicate by lowercase name and routine type.",
        "routines": [routines[key] for key in sorted(routines)],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    catalog = build_catalog(args.upstream)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(catalog['routines'])} IDL entries")
