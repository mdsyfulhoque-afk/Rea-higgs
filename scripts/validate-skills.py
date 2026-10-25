#!/usr/bin/env python3
"""Local mirror of the CI skill gate. Run before every push.

Checks: frontmatter (name, version, description, 'Use when', 'NOT for', <=1024
chars), version sync across VERSION and manifests, marketplace lists every
skill, references resolve with no orphans, no parent-dir paths, scripts parse,
SKILL.md length (warning above 300 lines, matching CLAUDE.md).

  python3 scripts/validate-skills.py [--strict]   # --strict: warnings fail
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML required (pip install pyyaml)")

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []
warnings: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def main() -> int:
    strict = "--strict" in sys.argv
    version = (ROOT / "VERSION").read_text().strip()
    skills = sorted(p for p in ROOT.glob("higgsfield-*") if p.is_dir())

    for sd in skills:
        md = sd / "SKILL.md"
        if not md.is_file():
            err(f"{md.relative_to(ROOT)} missing")
            continue
        text = md.read_text()
        m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        if not m:
            err(f"{md.relative_to(ROOT)}: no YAML frontmatter")
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        rel = md.relative_to(ROOT)
        if fm.get("name") != sd.name:
            err(f"{rel}: name {fm.get('name')!r} != directory {sd.name!r}")
        if str(fm.get("version")) != version:
            err(f"{rel}: version {fm.get('version')} != VERSION {version}")
        desc = fm.get("description") or ""
        if not desc:
            err(f"{rel}: description missing")
        if len(desc) > 1024:
            err(f"{rel}: description {len(desc)} chars > 1024")
        if "Use when" not in desc:
            err(f"{rel}: description lacks 'Use when'")
        if "NOT for" not in desc:
            err(f"{rel}: description lacks 'NOT for'")
        lines = text.count("\n") + 1
        if lines > 300:
            warnings.append(f"{rel}: {lines} lines > 300-line rule")
        if re.search(r"(^|[^./])\.\./", text, re.M):
            err(f"{rel}: parent-dir (../) reference; skills must be self-contained")

        refs_dir = sd / "references"
        if refs_dir.is_dir():
            linked = set(re.findall(r"references/[A-Za-z0-9_./-]+\.md", text))
            for ref in linked:
                if not (sd / ref).is_file():
                    err(f"{rel}: links {ref} but file is missing")
            for f in refs_dir.glob("*.md"):
                if f.name not in text:
                    err(f"{f.relative_to(ROOT)}: orphaned reference")
            for f in refs_dir.rglob("*.md"):
                if re.search(r"(^|[^./])\.\./\.\./", f.read_text()):
                    err(f"{f.relative_to(ROOT)}: ../../ path breaks installed bundles")

        for py in sd.glob("scripts/*.py"):
            try:
                ast.parse(py.read_text())
            except SyntaxError as e:
                err(f"{py.relative_to(ROOT)}: syntax error line {e.lineno}")

    for f in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"):
        v = json.loads((ROOT / f).read_text()).get("version")
        if v != version:
            err(f"{f}: version {v} != VERSION {version}")
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())["plugins"][0]
    if market["version"] != version:
        err(f".claude-plugin/marketplace.json: version {market['version']} != VERSION {version}")
    listed = {s.removeprefix("./").rstrip("/") for s in market["skills"]}
    for sd in skills:
        if sd.name not in listed:
            err(f"marketplace.json does not list {sd.name}")
    for name in listed - {s.name for s in skills}:
        err(f"marketplace.json lists {name} but no such folder")

    setup = (ROOT / "setup").read_text()
    m = re.search(r"^SKILLS=\((.*?)\)", setup, re.M)
    if m:
        for sd in skills:
            if sd.name not in m.group(1).split():
                err(f"setup SKILLS array lacks {sd.name}")

    for w in warnings:
        print(f"warn: {w}")
    for e in errors:
        print(f"error: {e}")
    if errors or (strict and warnings):
        print(f"FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        return 1
    print(f"OK: {len(skills)} skills, version {version}, {len(warnings)} warnings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
