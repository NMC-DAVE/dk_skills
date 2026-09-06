#!/usr/bin/env python3
"""Validate the repository's top-level Agent Skills catalog."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def frontmatter_value(frontmatter: str, key: str) -> str | None:
    """Read a required top-level scalar without adding a YAML dependency."""
    lines = frontmatter.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf"^{re.escape(key)}:\s*(.*)$", line)
        if not match:
            continue
        value = match.group(1).strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            block: list[str] = []
            for following in lines[index + 1 :]:
                if following.startswith((" ", "\t")):
                    block.append(following.strip())
                else:
                    break
            return " ".join(part for part in block if part)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return None


def local_links(skill_file: Path, text: str) -> list[tuple[str, Path]]:
    links: list[tuple[str, Path]] = []
    for raw_target in LINK_RE.findall(text):
        raw_target = raw_target.strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")]
        else:
            target = raw_target.split(maxsplit=1)[0]
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = unquote(target.split("#", 1)[0])
        links.append((target, (skill_file.parent / target).resolve()))
    return links


def validate_skill(skill_dir: Path) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file():
        return None, [f"{skill_dir.relative_to(ROOT)}: missing SKILL.md"]

    text = skill_file.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, [f"{skill_file.relative_to(ROOT)}: missing YAML frontmatter"]

    frontmatter = match.group(1)
    name = frontmatter_value(frontmatter, "name")
    description = frontmatter_value(frontmatter, "description")

    if not name:
        errors.append(f"{skill_file.relative_to(ROOT)}: missing frontmatter name")
    elif not NAME_RE.fullmatch(name):
        errors.append(f"{skill_file.relative_to(ROOT)}: invalid skill name {name!r}")
    elif name != skill_dir.name:
        errors.append(
            f"{skill_file.relative_to(ROOT)}: name {name!r} does not match directory {skill_dir.name!r}"
        )

    if not description:
        errors.append(f"{skill_file.relative_to(ROOT)}: missing frontmatter description")

    skill_root = skill_dir.resolve()
    for target, link in local_links(skill_file, text):
        try:
            link.relative_to(skill_root)
        except ValueError:
            errors.append(
                f"{skill_file.relative_to(ROOT)}: local link escapes the skill directory: {target}"
            )
            continue
        if not link.exists():
            errors.append(f"{skill_file.relative_to(ROOT)}: broken local link to {target}")

    agent_file = skill_dir / "agents" / "openai.yaml"
    if agent_file.exists():
        agent_text = agent_file.read_text(encoding="utf-8")
        for field in ("display_name", "short_description", "default_prompt"):
            if not re.search(rf"^\s*{field}:\s*\S", agent_text, re.MULTILINE):
                errors.append(f"{agent_file.relative_to(ROOT)}: missing {field}")

    return name, errors


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print("ERROR: skills/ directory is missing", file=sys.stderr)
        return 1

    skill_dirs = sorted(
        path for path in SKILLS_DIR.iterdir() if path.is_dir() and not path.name.startswith(".")
    )
    if not skill_dirs:
        print("ERROR: no skill directories found", file=sys.stderr)
        return 1

    names: list[str] = []
    errors: list[str] = []
    for skill_dir in skill_dirs:
        name, skill_errors = validate_skill(skill_dir)
        if name:
            names.append(name)
        errors.extend(skill_errors)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        errors.append(f"duplicate skill name: {name}")

    if errors:
        print("Skill catalog validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(names)} skills:")
    for name in names:
        print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
