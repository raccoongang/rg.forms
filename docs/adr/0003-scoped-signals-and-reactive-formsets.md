# ADR 0003 — Scoped signals and reactive formsets

- Status: Proposed — Revision 2 (resolves review blockers)
- Date: 2026-08-24
- Deciders: Oleksii Koval (author of rg.forms)
- Depends on: [ADR-0002](0002-canonical-expression-semantics.md) (the expression parser it introduces is reused here
  to rewrite field references safely, and its external-signal policy governs unknown references).

## Revisions 2–3 — decisions resolved

- **Signal namespace is nested Datastar signals** under the reserved `rgForms` top-level namespace (Datastar supports
  dot-notation nested signals and `data-bind:foo.bar`). The scope key comes from a **decided Base32 encoder** of the
  form prefix — injective, identifier-safe, leading-letter — replacing the rejected non-injective `-`→`_` idea and the
  earlier "verify and choose" placeholder (Decision §1).
- **`rgForms` is reserved in [ADR-0002 §5](0002-canonical-expression-semantics.md)** so external signals cannot
  collide with the scoping object.
- **Scoped bindings use the attribute-*value* form** (`data-bind="rgForms.<scope>.role"`), not the keyed form, because
  HTML lowercases attribute names and would corrupt the camelCase path; seeding uses object syntax; expressions use
  `$rgForms.<scope>.role` (Decision §1).
- **Decoding an encoded scope is not authorization** — the server resolves it against the actual form/formset being
  validated (Decision §1; enforced by ADR-0004's adapter).
- **Scope applies to any prefixed form**, not only formsets. The compatibility guarantee is corrected accordingly.
- **Expression rewriting** is fully specified: parse → rewrite field references → **canonical re-serialization**
  (precedence-preserving, escaping), applied to **every** expression-bearing metadata slot (including group
  `visible_when`), before derived expressions like `required_expr` are composed. Unknown references follow ADR-0002's
  external-signal policy.
- **Formset seeding** gets a dedicated owner — a `{% reactive_formset_signals formset %}` tag — because a single
  form instance cannot see its siblings.
- **Add / remove / reorder is removed from this ADR** and split into a separate dynamic-formset-mutation ADR. This
  ADR covers **scoped signals for prefixed forms and static formsets** only.

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

### P4 — No add / remove / reorder *(deferred — separate ADR)*

Standard formsets grow via `TOTAL_FORMS` and an empty-form template, with no reactive way to add, remove, or reorder
rows. This is a genuinely separate problem — indexed submission names, `DELETE`/`ORDER` handling, management-form
counts, stable-key-vs-Django-index divergence, and server re-rendering all need their own decisions — so it is
**out of scope here** and moves to a dedicated dynamic-formset-mutation ADR. This ADR delivers only the invariant
that makes any of that possible: **static rows that behave independently**.

## Decision

Introduce a **scoped signal model** for prefixed forms and make the tag, the signal seeding, and expression rewriting
all agree on it. Scope applies to any prefixed form (standalone prefixed forms and each row of a static formset).

### §1 — Nested signal namespace with an injective scope encoder

For a scoped field, distinguish:

| Concept | Example | Source |
|---|---|---|
| Logical field name (what the author writes) | `role` | field definition |
| Submitted HTML name | `form-0-role` | `BoundField.html_name` (already used) |
| Datastar signal path (nested) | `rgForms.<scope>.role` | see below |

Signals are **nested**, using Datastar's dot-notation object signals under the **reserved `rgForms` top-level
namespace** (reserved in [ADR-0002 §5](0002-canonical-expression-semantics.md), so an external signal cannot collide
with it). This reads far better than a flat mangled key and seeds as one object per scope.

**Scoped bindings use the attribute-*value* form, never the keyed form.** HTML attribute *names* are
case-insensitive and the browser lowercases them, so `data-bind:rgForms.<scope>.role` would degrade to a
`rgforms…` path while seeds/expressions use `$rgForms…` — a silent mismatch. Datastar supports the signal name in the
attribute value, which preserves casing exactly. The three surfaces are therefore:

| Surface | Form |
|---|---|
| Scoped binding | `data-bind="rgForms.<scope>.role"` (value form — preserves case) |
| Seeding | Datastar **object** signal syntax under `rgForms.<scope>` (not per-attribute keys) |
| Expression reference | compiled `$rgForms.<scope>.role` |

Unprefixed simple bindings stay byte-identical in the keyed form: `data-bind:role`.

**The scope encoder is decided** (not left to implementation). The HTML name with `-`→`_` is rejected: it is not
injective — Django allows custom prefixes, and both `a-b_c` and `a_b-c` collapse to `a_b_c`. The encoder is a
Base32 of the prefix:

```python
def encode_scope(prefix: str) -> str:
    # injective, identifier-safe, deterministic, Unicode-safe; always starts with a letter
    return "p" + base64.b32encode(prefix.encode("utf-8")).decode("ascii").rstrip("=").lower()

signal_path = f"rgForms.{encode_scope(bound_field.form.prefix)}.{logical_name}"
```

Properties: injective (Base32 is reversible and the `p` prefix guarantees a leading letter), identifier-safe (no dot,
hyphen, or `_`-prefix delimiter), no numeric leading path component (so it sidesteps any numeric-key ambiguity in
Datastar expression paths), and trivially testable. Human readability of the encoded scope does not matter — authors
keep writing `$role`.

**Decoding is not authorization.** The scope is reversible, but on an incoming request the server must **resolve** the
encoded scope against the *actual* form/formset it is validating and reject a scope that does not belong to it — never
blindly decode a client-supplied scope into arbitrary form keys. ADR-0004's adapter owns this check.

Unprefixed forms are unchanged: no prefix → the signal name is the logical name, exactly as today.

### §2 — Expression rewriting: parse, rewrite references, re-serialize

At render time the tag knows the field's form and prefix (`bound_field.form.prefix`). For each expression it:

1. **parses** to an AST (ADR-0002 parser);
2. **rewrites** every `$reference` node that resolves to a declared field of that form to the scoped signal path,
   **preserving** references that ADR-0002 classifies as declared external / reserved signals, and treating genuinely
   unknown references per ADR-0002's policy (warn/error, not silent);
3. **re-serializes** the AST back to an expression with a canonical, **precedence-preserving** serializer that
   correctly escapes string literals.

This must run on **every** expression-bearing metadata slot, and it must happen **before** derived expressions are
composed (so `required_expr`, `placeholder_expr`, `min_expr`, `max_expr` are built from already-scoped sources):

- `visible_when`, `required_when`, `computed`, `disabled_when`, `read_only_when`
- the **keys** of `help_text_when`, `placeholder_when`, `min_when`, `max_when`
- group `visible_when` expressions

Operating on the AST — not raw strings — is what makes this safe (no rewriting inside literals, no `$role_id`
near-match). Outside a prefixed form the rewrite is the identity. Fixes P2.

### §3 — Formset-aware signal seeding

A single `ReactiveForm` instance cannot see its sibling rows, so it cannot emit the combined seed. Add a dedicated
template tag that owns this:

```django
<form data-signals='{% reactive_formset_signals formset %}'>
```

It emits one nested `rgForms.<scope>.<field>` entry per (scope, field) under the same signal paths the inputs bind
to, so initial values line up for every row (fixes P3). Seed using Datastar's **object** signal syntax (not
individual `data-bind` attribute names) to avoid attribute-name casing surprises with the `rgForms` key. (A
`ReactiveFormSetMixin.get_signals_json()` is an alternative owner; the tag is the smaller addition.)

## Backward compatibility

- **Unprefixed forms are byte-identical.** With no prefix, the signal name == logical name, the expression rewrite is
  the identity, and seeding is unchanged.
- **Any prefixed form now receives scoped signals** — standalone prefixed forms as well as formset rows. This is the
  desired behavior, but it does mean a *prefixed standalone* form changes from shared to scoped signals, not only
  formsets. Call it out in the CHANGELOG alongside the formset fix.
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
- **Dynamic formset mutation** (add / remove / reorder, `DELETE`/`ORDER`, `TOTAL_FORMS` management, stable-key vs
  Django-index reconciliation, server re-render) — a separate later ADR, not this one.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/templatetags/reactive_forms.py` (`render_reactive_field` **and** `render_field_group`
  must derive the scope from `bound_field.form.prefix` / the group's form and share one rewrite service; scope
  `data-bind` and rewrite every expression slot listed in §2 *before* composing derived expressions),
  `src/rg/forms/forms.py` (scope-aware `get_signals`), the parser + canonical serializer from ADR-0002, the Base32
  scope encoder (§1), and the `reactive_formset_signals` template tag (§3).
- Tests: the Base32 scope encoder is injective over adversarial prefixes (`a-b_c` vs `a_b-c`, Unicode); two static
  rows evaluate independently (visibility/required/computed per row); scoped paths appear in `data-bind` and in seeded
  signals; rewriting covers *all* metadata slots and does not touch literals or `$role_id`-style near-matches; a
  **field group** (`render_field_group`) inside a prefixed form receives the same scope and its group `visible_when`
  is rewritten (explicit test, not just listed); declared external signals survive rewriting; `rgForms` is rejected as
  an author reference; unprefixed output is unchanged.
- Verify nested `rgForms.<scope>.<field>` binding/seeding against the pinned Datastar bundle before implementing. This
  work targets **Datastar 1.0.2** (stable), upgraded from `1.0.0-RC.7`; 1.0.2 also fixed `data-bind` array-signal bugs
  relevant to multi-value fields.
