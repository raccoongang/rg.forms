# ADR 0002 — Canonical client/server expression semantics and reactive value normalization

- Status: Proposed — Revision 2 (resolves review blockers; ready to implement on sign-off)
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Supersedes the "render on Django widget context" idea as the *next* ADR: that rendering refactor is still
  wanted, but it is downstream of this one and is deferred to a later ADR.

## Revision 2 — decisions resolved

The first draft left six boundaries implicit. They are now decided in this document:

- **Decimal** stays a canonical **string** signal; `integer`/`float` are JS numbers; exact arithmetic is a server
  concern (Decision §2, §3).
- **Empty values are field-specific**, not a single `null` (Decision §2, empty-value table).
- **date / time / datetime / UUID** are supported canonical **strings** (Decision §2).
- **Arrays** support equality, inequality, and truthiness only; **membership/length are deferred** until an explicit
  grammar exists (Decision §3).
- **External signals** are allowed only when declared in `Meta.external_signals`; the system check enforces this
  (Decision §5).
- **Normalization ≠ validation**: extraction/normalization is a distinct, loss-minimizing layer that never calls
  `field.clean()` (Decision §1).

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

### P7 — Invalid expressions fail silently, and the fail-open/closed behavior is inconsistent

`_evaluate_expression` returns `None` on any parse/eval error, and each caller interprets that differently. The actual
matrix today is:

| Rule | On evaluation error | Effect |
|---|---|---|
| `visible_when` (field) | defaults **visible** | fail-open |
| group `visible_when` | defaults **visible** | fail-open |
| `required_when` | defaults **not required** | fail-open |
| `computed` | leaves the **submitted value** unchanged | passthrough |

So a typo, an unknown field reference, or an unsupported operator degrades silently — usually fail-open — rather than
surfacing. For a correctness-critical layer that is the wrong default for *authoring* errors: they should be caught at
build time, not swallowed at runtime. This ADR keeps the runtime behavior fail-open (a broken rule must not hide a
field or silently drop a value) **but logs it**, and moves detection of malformed/unknown expressions to a
build-time system check (Decision §5) so they never reach runtime in the first place.

## Decision

Define a **canonical reactive value model** shared by the client seed, the server evaluator, and validation, plus a
normalization step and conformance tests that keep them in lock-step.

### §1 — Two layers: reactive normalization vs authoritative cleaning

Separate the two responsibilities that the current code conflates:

- **Reactive normalization** — a single, *loss-minimizing* function that maps a field's raw source to its canonical
  reactive value, used identically for the client seed and for server-side expression evaluation. Extraction is via
  the widget, not the field's full clean:

  ```python
  raw = field.widget.value_from_datadict(data, files, html_name)
  # then a field-kind-specific conversion to the canonical type (see §2)
  ```

  Conversion may use field-specific logic or a careful `to_python()`, but **never `field.clean()`** — `clean()` runs
  required checks and validators and would reject *temporarily invalid* input. While a number field holds `"-"`,
  normalization must keep it representable (not coerce to `null` merely because `IntegerField.to_python("-")` raises).
  Normalization is total: it always yields a canonical value, even for in-progress input.

- **Authoritative cleaning** — Django's `field.clean()` / `Form.clean()` during validation, unchanged. This is where
  correctness and precision live (e.g. exact `Decimal` totals).

Both the bound (`QueryDict`) and unbound (`initial`) server paths run through reactive normalization, eliminating the
render-time/submit-time type split (P3). The canonical value is **anchored to `get_signals_json`**: whatever the
client is seeded with is, by definition, what the server normalizes to.

### §2 — Explicit supported types and per-field canonical values

The reactive language supports exactly: **string**, **boolean**, **number**, **null**, and **array**. Each field maps
to one canonical type, and each field kind has a defined *empty* value (Datastar preserves a predefined signal's type
on bind, so the initial type and the empty value must be correct):

| Field kind | Canonical type | Canonical empty | Notes |
|---|---|---|---|
| char / choice / email / url / text | string | `""` | **never numeric-coerced** — fixes P1 (`"001"` stays `"001"`) |
| integer / float | number | `null` | JS number semantics |
| decimal | **string** | `""` | exact; see §3 — not a JS number |
| boolean | boolean | `false` | `"on"`/absent → `true`/`false` — fixes P4 |
| multiple choice | array | `[]` | via `QueryDict.getlist()` — fixes P2 |
| date | string | `""` | `YYYY-MM-DD` |
| time | string | `""` | widget precision (e.g. `HH:MM`) |
| datetime | string | `""` | local `YYYY-MM-DDTHH:MM` |
| UUID | string | `""` | canonical string form |
| optional file | null | `null` | not expression-addressable beyond presence |

This replaces the earlier contradictory "empty → `null`, distinct from `''`/`false`/`0`": the empty value is
**field-specific** (fixes P5), matching HTML/Datastar behavior.

### §3 — Decimal contract, and exact operator/equality semantics

**Decimal stays a string signal.** JavaScript numbers cannot represent arbitrary decimals exactly, and the signal
serializer already emits `Decimal` as a string. Therefore:

- `integer` / `float` → reactive **number** (IEEE-754 / JS semantics);
- `decimal` → canonical **decimal string**;
- arithmetic on a Decimal-backed signal is **not** exact in the browser — it is either explicitly converted or
  documented as unsuitable for precision-sensitive math. Display-only totals may use JS number arithmetic, but must
  not be presented as authoritative;
- the server **always recomputes** authoritative totals from Django `Decimal` values during cleaning (§1).

Specify, in one table (in the implementation), how each operator behaves for the supported types, chosen to match
Datastar/JavaScript for that subset (fixes P6):

- `==` / `!=`: string equality for strings; numeric for numbers; element-wise for arrays; `null` compared explicitly.
- `<` `>` `<=` `>=`: numbers and comparable strings; `null` comparisons are false (except `==`/`!=`).
- `&&` `||` `!`: JS truthiness over the canonical types (`""`, `null`, `false`, `0`, `[]` are falsy).
- `+` `-` `*` `/`: numeric only; division-by-zero semantics documented to match the chosen contract.
- **Arrays**: equality, inequality, and truthiness are defined. **Membership and length are deferred** — the grammar
  has no `in` operator, property access, or function calls today, so this ADR does **not** promise `contains`/
  `length`. Those require an explicit grammar addition in a follow-up.

### §4 — Client/server conformance tests (two levels)

The executable definition of "the two sides agree":

1. **Expression fixture** — a large table of `(expression, signals) → expected`, evaluated by **both** the Python
   evaluator and a JavaScript evaluation of the same expressions. Fast; runs in CI without a browser. This covers the
   expression grammar and operator semantics.
2. **Browser integration suite** — a smaller set exercised against the **actual pinned Datastar bundle**, since
   Datastar owns signal parsing and attribute binding, which a bare JS `eval` harness does not reproduce. This
   verifies the real boundary (type preservation on bind, empty-value typing, array binding).

### §5 — Early rejection, and the external-signal policy

Validate expressions when the form class is constructed and via a Django **system check**: parse each expression, and
require every `$reference` to resolve to one of:

- a declared **field** of the form,
- a signal declared in `Meta.external_signals` (for intentional page-level signals), or
- a library-**reserved** signal.

```python
class MyForm(ReactiveForm):
    class Meta:
        external_signals = {"feature_enabled"}
```

Genuinely unknown references, unsupported operators, and unsupported types are rejected. To ease adoption this can
land first as a **warning**, graduating to an error in a later minor release. Runtime evaluation errors remain
fail-open per the P7 matrix but are **logged**, never silently swallowed.

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
  `_binary_op`), `src/rg/forms/forms.py` (`_get_form_data` and `get_signals` → route through reactive normalization;
  use `widget.value_from_datadict` for extraction and `getlist()` semantics for multi-value), a normalization helper
  (new module or extend `expressions`) that is field-kind-aware per §2 and never calls `field.clean()`, a Django
  system check for expression validity + `Meta.external_signals`, and tests under `tests/`.
- Add tests: (a) the level-1 expression fixture (Python vs JS) and the level-2 browser suite against the pinned
  Datastar bundle; (b) the P1–P6 divergence cases as regression tests, including `"001"` choice-code equality,
  multi-value arrays, and the per-field empty-value table; (c) normalization keeps in-progress input (`"-"`)
  representable rather than nulling it; (d) system-check rejection of unknown references and acceptance of declared
  `external_signals`.
- The level-1 fixture is the contract — write it first and make both evaluators pass it. Do **not** implement
  array membership/length until a grammar addition is designed.
