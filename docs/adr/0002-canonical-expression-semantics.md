# ADR 0002 — Canonical client/server expression semantics and reactive value normalization

- Status: Proposed
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Supersedes the "render on Django widget context" idea as the *next* ADR: that rendering refactor is still
  wanted, but it is downstream of this one and is deferred to a later ADR.

## Context

rg.forms' central promise (see [comparison.md](../comparison.md) and
[the feature-parity matrix](../guide/custom-rendering.md#feature-parity-where-each-rule-is-enforced)) is:

> A rule is declared once in Python, evaluated in the browser for UX and re-evaluated on the server for
> correctness.

That promise only holds if **both evaluators interpret the same expression against the same values identically**.
Today they can diverge. The client evaluates JavaScript over Datastar signals (typed: boolean, number, string,
array); the server evaluates a custom AST (`src/rg/forms/expressions.py`) over values produced by
`ReactiveForm._get_form_data()` (`src/rg/forms/forms.py`), which are raw POST strings when the form is bound and
native Python objects (from `initial`) when it is unbound. The two paths coerce values differently, and neither is
anchored to the JSON signal representation the client actually sees (`get_signals_json`).

When client and server disagree, the developer is pushed back toward defensive `clean()` logic on every field —
which erodes the very code-saving benefit that justifies the architecture. Making the small shared reactive language
rigorous is therefore more important than any additional feature.

## Problems (concrete divergences, verified in the current code)

### P1 — Numeric-looking values are silently coerced

`_get_field_value` converts any numeric-looking string to `int`/`Decimal`
(`expressions.py`: `"001"` → `int("001")` → `1`). `_compare_equal` then stringifies when either side is a string.
So for a choice code `"001"`:

- Client: `$code == '001'` → `"001" == "001"` → **true**.
- Server: field coerced to `1`, literal stays `"001"` → `str(1) == str("001")` → `"1" == "001"` → **false**.

Leading zeros, ZIP codes, phone prefixes, and ID-like choice values all break this way.

### P2 — Multi-value signals collapse

`_get_form_data()` builds `{key: self.data.get(key)}`, taking a single value from the `QueryDict`. A
`SelectMultiple` / `ReactiveMultipleChoiceField` submits several values under one name; the server sees only the
last. Any expression over a multi-value field (membership, length, "contains") cannot be evaluated correctly, and
array semantics are undefined on both sides.

### P3 — Bound vs unbound type split

Unbound (`GET`/initial render): `_get_form_data()` returns `dict(self.initial)` — native `bool`, `date`, `Decimal`.
Bound (`POST`): the same method returns POST **strings**. The identical expression therefore evaluates different
types at render-time versus submit-time on the server alone, independent of the client.

### P4 — Boolean / checkbox semantics

A Datastar checkbox signal is boolean `true`/`false`. A native checkbox POSTs `"on"` when checked and is **absent**
when unchecked; `_get_field_value` maps `""`/missing to `None`. So `$agree == true` and `$agree` (truthiness) do not
line up across client and server.

### P5 — `null` / empty / `false` conflation

`self.data.get(field_name, "")` plus "`""` → `None`" means missing key, empty string, and cleared value all become
`None`, while the client distinguishes `null`, `''`, `false`, and `0`. Comparisons against these differ.

### P6 — Operator and evaluation-semantics mismatch

The Python evaluator does not match JavaScript for: `+` (numeric add vs string concat), truthiness, `==` loose
equality/coercion, and division by zero (server returns `Decimal(0)`; JS yields `Infinity`/`NaN`). Any expression
mixing types or using arithmetic can diverge.

### P7 — Invalid expressions fail silently

`_evaluate_expression` returns `None` on any parse/eval error, which downstream treats as false/hidden. A typo, an
unknown field reference, or an unsupported operator therefore degrades silently to "field hidden / not required"
instead of surfacing — the most dangerous possible default for a correctness-critical layer.

## Decision

Define a **canonical reactive value model** shared by the client seed, the server evaluator, and validation, plus a
normalization step and conformance tests that keep them in lock-step.

1. **Field-aware value normalization.** Introduce a single normalization function that maps a field's value —
   whether from `initial` (unbound) or the `QueryDict` (bound) — to a canonical typed value, using the Django
   field/widget as the authority. This function is the one place that decides types, and it must produce values that
   compare identically to what `get_signals_json` seeds into the client. Both the bound and unbound server paths use
   it, eliminating P3.

2. **Explicit supported value types.** The reactive language supports exactly: `string`, `boolean`,
   `number` (int/Decimal), `null`, and `array` (for multi-value fields). Each field maps to one canonical type:
   - choice/char/email/url/text → **string** (never numeric-coerced — fixes P1);
   - integer/float/decimal → **number**;
   - boolean → **boolean** (`"on"`/absent normalized to `true`/`false` — fixes P4);
   - multiple-choice → **array** via `QueryDict.getlist()` (fixes P2);
   - empty/missing → **null**, kept distinct from `''`, `false`, `0` (fixes P5).

3. **Exact coercion and equality semantics.** Specify, in one table, how each operator (`==`, `!=`, `<`, `>`, `&&`,
   `||`, `+`, `-`, `*`, `/`, `!`) behaves for the supported types, chosen to match Datastar/JavaScript for that
   subset (fixes P6). Equality on strings is string equality; on numbers, numeric; arrays support membership/length;
   `null` comparisons are explicit.

4. **Client/server conformance tests.** A shared fixture of `(expression, signals) → expected` cases, evaluated by
   **both** the Python evaluator and a JavaScript/Datastar evaluation harness, asserting identical results. This
   fixture is the executable definition of "the two sides agree" and guards every future change.

5. **Early rejection of unsupported expressions.** Validate expressions when the form class is constructed and via a
   Django **system check**: parse them, verify every `$field` reference resolves to a declared field, and reject
   unsupported operators/types. Authoring errors fail loudly at startup, not silently as "hidden" at runtime
   (fixes P7). Runtime evaluation errors are logged rather than swallowed to a bare `None`.

The canonical representation is **anchored to `get_signals_json`**: whatever the client is seeded with is, by
definition, the value the server normalizes to. That single anchor is what makes "declare once, behave on both
sides" true rather than aspirational.

## Backward compatibility

- **Expression syntax is unchanged** for the supported subset; existing valid expressions keep parsing.
- **Some results change — as corrections.** Forms that (unknowingly) depended on the buggy numeric coercion of choice
  codes, or on multi-value collapse, will evaluate differently. These are bug fixes; they must be called out in the
  CHANGELOG, and the conformance fixture documents the new, correct behavior.
- **Early rejection may surface latent authoring bugs** (typos, stale field references) as system-check errors. To
  ease adoption, this can land first as a **warning**, then graduate to an error in a subsequent minor release.
- No change to the field API or to the `render_reactive_field` context is required by this ADR.

## Consequences

- The reactive language becomes small, explicit, and testable, and the backend-first thesis becomes dependable
  rather than best-effort.
- `min_when` / `max_when` server enforcement (currently client-only) becomes *possible* once normalization exists,
  but is out of scope here — it belongs to a later validation ADR. Until then their client-only status stays
  documented (see the parity matrix). Renaming them is an alternative if server parity is not pursued.
- A JavaScript conformance harness is a new (small) test dependency. It runs the same fixture the Python tests run.

## Scope boundaries (explicitly *not* in this ADR)

- Rendering on Django's `widget.get_context()` and a semantic `control` object — separate, later ADR.
- Scoped signals and reactive formsets (`role` / `form-0-role` / `form_0_role`) — ADR-0003.
- Declarative incremental server validation (`validate_on="blur"`) — ADR-0004.
- Accessibility contract (`aria-invalid`/`aria-describedby`, focus-first-invalid) — later ADR.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/expressions.py` (evaluator coercion in `_get_field_value`, `_compare_equal`,
  `_binary_op`), `src/rg/forms/forms.py` (`_get_form_data` → per-field normalization; use `getlist()` for
  multi-value; align with `get_signals`/`get_signals_json`), a normalization helper (new module or extend
  `expressions`), a Django system check for expression validity, and tests under `tests/`.
- Add tests: (a) the client/server conformance fixture; (b) the P1–P6 divergence cases as regression tests;
  (c) system-check rejection of unknown-field and unsupported-operator expressions.
- The conformance fixture is the contract — write it first and make both evaluators pass it.
