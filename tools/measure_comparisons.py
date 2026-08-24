#!/usr/bin/env python
"""Reproducible line-count measurement for the rg.forms comparison fixtures.

Reads an explicit manifest (``docs/comparisons/manifest.json``) that maps each
scenario and stack to the files that make up its *complete vertical slice*, and
counts **non-blank, non-comment source lines** (docstrings and header comments
excluded) per layer, per stack, and in total. Results are written to
``docs/comparisons/measurements.json`` (checked in) and can be verified in CI.

The manifest also carries a small set of **declared architectural counts**
(transport boundaries, rule declaration sites, per-field renderers, places a
business rule must change). These are structural facts about each slice, not
auto-derived from source, and are labeled as such in the output.

Usage:
    python tools/measure_comparisons.py            # write measurements.json
    python tools/measure_comparisons.py --check     # fail if out of date / files missing
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "docs" / "comparisons" / "manifest.json"
OUTPUT = ROOT / "docs" / "comparisons" / "measurements.json"


# --------------------------------------------------------------------------- #
# Source-line counting (non-blank, non-comment; docstrings excluded)
# --------------------------------------------------------------------------- #
def _python_sloc(text: str) -> int:
    """Count Python source lines, excluding blanks, comments, and docstrings."""
    docstring_lines: set[int] = set()
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(getattr(body[0], "value", None), ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    doc = body[0]
                    for ln in range(doc.lineno, (doc.end_lineno or doc.lineno) + 1):
                        docstring_lines.add(ln)
    except SyntaxError:
        pass

    comment_lines: set[int] = set()
    try:
        import io

        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                comment_lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        pass

    count = 0
    for i, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        if i in docstring_lines:
            continue
        if i in comment_lines and not raw.split("#", 1)[0].strip():
            continue  # comment-only line
        count += 1
    return count


def _strip_block_comments(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _c_like_sloc(text: str) -> int:
    """Count TS/TSX/JS source lines, excluding blanks and // and /* */ comments."""
    text = _strip_block_comments(text)
    count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        count += 1
    return count


def _html_sloc(text: str) -> int:
    """Count template lines, excluding blanks and {# #} / <!-- --> comments."""
    for opener, closer in (("{#", "#}"), ("<!--", "-->")):
        while opener in text:
            start = text.find(opener)
            end = text.find(closer, start + len(opener))
            if end == -1:
                text = text[:start]
                break
            text = text[:start] + text[end + len(closer) :]
    return sum(1 for raw in text.splitlines() if raw.strip())


def count_sloc(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".py":
        return _python_sloc(text)
    if suffix in (".ts", ".tsx", ".js", ".jsx"):
        return _c_like_sloc(text)
    if suffix in (".html", ".htm"):
        return _html_sloc(text)
    # Fallback: non-blank lines.
    return sum(1 for raw in text.splitlines() if raw.strip())


# --------------------------------------------------------------------------- #
# Measurement
# --------------------------------------------------------------------------- #
def measure() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    missing: list[str] = []
    scenarios: dict = {}

    for scenario, stacks in manifest["scenarios"].items():
        scenarios[scenario] = {"title": stacks.get("title", scenario), "stacks": {}}
        for stack, spec in stacks.items():
            if stack == "title":
                continue
            layers = spec["layers"]
            layer_counts: dict[str, int] = {}
            for layer, files in layers.items():
                total = 0
                for rel in files:
                    path = ROOT / rel
                    if not path.exists():
                        missing.append(rel)
                        continue
                    total += count_sloc(path)
                layer_counts[layer] = total
            scenarios[scenario]["stacks"][stack] = {
                "runnable": spec.get("runnable", False),
                "layers": layer_counts,
                "total_sloc": sum(layer_counts.values()),
                "architecture": spec.get("architecture", {}),
            }

    if missing:
        raise SystemExit("Manifest references missing files:\n  " + "\n  ".join(sorted(set(missing))))

    return {
        "note": (
            "LOC are auto-measured (non-blank, non-comment, docstrings excluded) by "
            "tools/measure_comparisons.py. Architectural counts are declared structural "
            "facts of each slice (see docs/comparisons/methodology.md). rg.forms slices are "
            "the runnable example app; competitor slices are illustrative fixtures."
        ),
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if measurements.json is stale")
    args = parser.parse_args()

    result = measure()
    serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"

    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != serialized:
            print("measurements.json is out of date — run: python tools/measure_comparisons.py", file=sys.stderr)
            return 1
        print("measurements.json is up to date.")
        return 0

    OUTPUT.write_text(serialized)
    for scenario, data in result["scenarios"].items():
        print(f"\n{scenario}:")
        for stack, s in data["stacks"].items():
            print(f"  {stack:18s} {s['total_sloc']:4d} SLOC  {'(runnable)' if s['runnable'] else '(illustrative)'}")
    print(f"\nWrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
