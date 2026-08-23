# ADR 0003 — Scoped signals and reactive formsets

- Status: Proposed
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Depends on: [ADR-0002](0002-canonical-expression-semantics.md) (the expression parser it introduces is reused here
  to rewrite field references safely).

## Context

ADR-0001 (P4) made `render_reactive_field` **submit-safe** inside a Django formset: each row renders prefixed
`name`/`id` (`form-0-role`, `form-1-role`) via `field.html_name` / `field.id_for_label`, and a POST round-trips to
the right form. That fixed the server side.

It did **not** fix the reactive side. The shipped field template still binds the Datastar signal by the *unprefixed*
logical name — `data-bind:{{ field_name }}` → `data-bind:role` — and `ReactiveForm.get_signals_json()` keys signals
by the unprefixed name too. So every row's `role` input binds to a single shared `$role` signal, and every row's
`visible_when` / `required_when` / `computed` expression references that same shared signal. Two rows cannot behave
independently: typing in row 0 changes row 1, and a per-row conditional fires for all rows at once.

This is not Formik-style feature chasing. Reactive independence per row is required for the *existing* reactive
abstraction to remain correct when used with standard Django formsets — which are the natural Django analogue of
Formik/RHF field arrays. The current documentation only *acknowledges* the limitation; this ADR removes it.

## Problems

### P1 — Signal names are not row-scoped

`data-bind:role` and `$role` collide across rows. Binding, `data-show`, `data-attr:*`, and computed values are all
shared. Correct behavior requires a distinct signal per (row, field).

### P2 — Expressions reference sibling fields by logical name

An author writes `visible_when="$role == 'admin'"` once on the field. Inside a formset each row's expression must
resolve `$role` to *that row's* signal, not a global one. Naive string substitution is unsafe (it would also rewrite
occurrences inside string literals, or partial matches like `$role_id`).

### P3 — Signal seeding is not formset-aware

`get_signals_json()` emits `{"role": …}`, not per-row entries, so initial values for row 1+ are missing or wrong, and
the seeded object does not match the per-row signal names the inputs bind to.

### P4 — No add / remove / reorder

Standard formsets grow via `TOTAL_FORMS` and an empty-form template. There is no reactive way to add, remove, or
reorder rows, keep stable row identity, or keep the management form in sync.

## Decision

Introduce a **row-scoped signal model** and make the tag, the signal seeding, and expression rewriting all agree on
it. Deliver reactive independence first; add/remove/reorder second.

### 1. A three-plus-one naming model

For a field inside a formset, distinguish:

| Concept | Example | Source |
|---|---|---|
| Logical field name (what the author writes in expressions) | `role` | field definition |
| Submitted HTML name | `form-0-role` | `BoundField.html_name` (already used) |
| Datastar signal name (must be identifier-safe) | `form_0_role` | derived from the prefix |
| Optional row-local alias (readability inside expressions) | `$row.role` | see below |

The signal name is derived from the HTML name with a defined, reversible mangling (`-` → `_`) chosen to be a valid
Datastar/JS identifier. Whether the signals are **flat** (`$form_0_role`) or **nested** (`$form.0.role`, a Datastar
nested-signal object) is the main open decision — nested reads better in expressions and seeds as one object per row,
flat is simpler to mangle. The implementing ADR revision must verify the choice against Datastar's actual signal-name
and nesting rules before committing. Non-formset forms are unchanged: no prefix → signal name == logical name.

### 2. Per-row expression rewriting via the ADR-0002 parser

At render time, the tag knows the field's form and prefix (`bound_field.form.prefix`). It parses each reactive
expression (using the parser from ADR-0002), rewrites every `$field` **reference** that resolves to a declared field
of that form to the row-scoped signal name, and leaves literals and unknown tokens untouched. Because this operates
on the parsed AST/token stream — not raw strings — it fixes P2 safely. Outside a formset the rewrite is the identity.

### 3. Formset-aware signal seeding

`get_signals`/`get_signals_json` gains a formset-aware form that emits one entry per (row, field) under the same
scoped names the inputs bind to, so initial values line up for every row (fixes P3). A template helper renders the
combined `data-signals` for a whole formset.

### 4. Add / remove / reorder (second phase)

A small set of Datastar-driven actions clone the empty-form template into a new row, increment `TOTAL_FORMS`, seed the
new row's signals, and support removing/reordering with **stable row keys** so signals and expressions track the row,
not the index. This phase is explicitly deferred until (1)–(3) land and two static rows are proven independent.

## Backward compatibility

- **Non-formset forms are byte-identical.** With no prefix, scoped name == logical name, the expression rewrite is the
  identity, and seeding is unchanged.
- **Formset rendering changes** from shared to per-row signals — a behavior fix for anyone already rendering formset
  rows with `render_reactive_field` (previously broken). Call out in the CHANGELOG.
- The field API is unchanged; authors keep writing `$role`.

## Consequences

- Standard Django formsets become fully reactive per row, closing the one remaining "acknowledged but broken" item in
  the parity matrix.
- rg.forms gains the field-array capability of client form libraries, expressed the Django way (formsets), without a
  client state engine.
- Expression rewriting couples this feature to ADR-0002's parser — a deliberate, load-bearing reuse.

## Scope boundaries

- Canonical value semantics — [ADR-0002](0002-canonical-expression-semantics.md).
- Incremental server validation — ADR-0004.
- Nested/related formsets and drag-drop reordering UI — out of scope; only flat add/remove/reorder with stable keys is
  considered, and only in the second phase.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/templatetags/reactive_forms.py` (derive prefix, scope `data-bind` and every
  `data-attr:*`/`data-show` expression per row), `src/rg/forms/forms.py` (formset-aware `get_signals`), the parser
  from ADR-0002 (reference-rewriting transform), and a formset signals template tag.
- Tests: two static rows evaluate independently (visibility/required/computed per row); scoped names appear in
  `data-bind` and in seeded signals; expression rewriting does not touch literals or `$role_id`-style near-matches;
  non-formset output is unchanged. Add/remove/reorder tests follow in the second phase.
- Resolve the flat-vs-nested signal-name decision against Datastar's documented rules before implementing.
