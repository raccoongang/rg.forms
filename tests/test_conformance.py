"""Client/server conformance (ADR-0002 §4, level 1).

Evaluates the shared fixture with both the Python evaluator and a Node
evaluation of the compiled JS, and asserts both agree with the expected value.
The Node leg is skipped automatically when ``node`` is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from rg.forms.expressions import evaluate_expression, parse_expression, serialize_js
from tests.conformance_cases import CASES

_HARNESS = Path(__file__).parent / "js" / "eval_harness.mjs"
_NODE = shutil.which("node")


def _same(a, b) -> bool:
    """Compare results tolerating int/float and float rounding."""
    if a is None or b is None:
        return a is b
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) < 1e-9
    return a == b


@pytest.mark.parametrize("expr,signals,expected", CASES)
def test_python_side(expr, signals, expected):
    """The Python evaluator matches the expected value."""
    result = evaluate_expression(expr, signals)
    assert _same(result, expected), f"{expr} with {signals}: {result!r} != {expected!r}"


def _harness_ref(path: str) -> str:
    return f"__sig({json.dumps(path)})"


@pytest.mark.skipif(_NODE is None, reason="node not available")
def test_js_side_matches_python_and_expected():
    """Node evaluation of the compiled JS matches Python and the fixture."""
    payload = [
        {"js": serialize_js(parse_expression(expr), signal_ref=_harness_ref), "signals": signals}
        for expr, signals, _ in CASES
    ]
    proc = subprocess.run(
        [_NODE, str(_HARNESS)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"node harness failed:\n{proc.stderr}"
    js_results = json.loads(proc.stdout)

    failures = []
    for (expr, signals, expected), js_result in zip(CASES, js_results, strict=True):
        if isinstance(js_result, dict) and "__nonfinite__" in js_result:
            failures.append(f"{expr} with {signals}: JS produced {js_result['__nonfinite__']}")
            continue
        py_result = evaluate_expression(expr, signals)
        if not _same(js_result, expected):
            failures.append(f"{expr} with {signals}: JS {js_result!r} != expected {expected!r}")
        if not _same(js_result, py_result):
            failures.append(f"{expr} with {signals}: JS {js_result!r} != Python {py_result!r}")

    assert not failures, "conformance divergences:\n" + "\n".join(failures)


@pytest.mark.skip(
    reason="ADR-0002 §4 level-2: requires a real browser + the pinned Datastar "
    "bundle (type preservation on bind, empty-value typing, array binding). "
    "Run under a browser driver in CI; the bare-JS level-1 harness above cannot "
    "reproduce Datastar's own signal parsing/attribute binding."
)
def test_browser_integration_against_pinned_datastar():
    """Placeholder for the level-2 browser suite (see skip reason)."""
    raise NotImplementedError
