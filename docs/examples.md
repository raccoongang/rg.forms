# Examples

The `examples/` directory is a runnable Django project demonstrating the
capabilities delivered by [ADR-0001](adr/0001-design-system-agnostic-field-rendering.md)
through [ADR-0004](adr/0004-declarative-incremental-server-validation.md). Every
example is a real, interactive form — not documentation pseudocode — with all
validation and business rules **server-authoritative**.

## Running the example project

```bash
git clone https://github.com/raccoongang/rg.forms.git
cd rg.forms/examples

uv venv
source .venv/bin/activate
uv pip install -e "..[all]"

python manage.py migrate
python manage.py runserver
```

Visit [http://localhost:8000/](http://localhost:8000/) for the example index.

## Example matrix

Each example maps a realistic scenario to the ADRs and rg.forms features it
exercises, the client-library pattern it corresponds to, whether it has a full
side-by-side [comparison](comparison.md), and the limitations it exposes.

| # | Example | Scenario | ADRs | rg.forms features | Client-lib analogue | Full comparison | Limitations exposed |
|---|---|---|---|---|---|:---:|---|
| 1 | **Account registration** | Sign up with live username/email availability | 0001, 0004 | `validate_on`, `debounce`, pending indicator, CSRF, `clean_<field>`, cross-field `clean()`, aria ids | Formik async validation · RHF async field validation · TanStack `onChangeAsync` | ✅ | file-field incremental validation not supported |
| 2 | **Order configurator** | Plan/product order with conditional fields & pricing | 0001, 0002 | `visible_when`, `required_when`, `disabled_when`, `read_only_when`, `help_text_when`, `computed`, exact `Decimal`, canonical string codes | Formik dependent fields + Yup `.when()` · RHF `watch()` · TanStack listeners | ✅ | `disabled_when`/`min_when`/`max_when` are client-only |
| 3 | **Team roster** | A static formset of team-member rows | 0001, 0002, 0003 | scoped signals, `reactive_formset_signals`, per-row `visible_when`/`required_when`, prefixed names | Formik `FieldArray` · RHF `useFieldArray` · TanStack array fields | ✅ | **static rows only** — no add/remove/reorder yet |
| 4 | **Settings dashboard** | Several prefixed forms on one page | 0003, 0004 | per-form scope, overlapping logical names, independent incremental validation | (multiple independent `useForm` instances) | — | forms must use distinct prefixes |
| 5 | **Feature-flagged form** | Permission/plan-aware visibility | 0002 | `Meta.external_signals`, `get_external_signal_values()`, field-wins-on-collision | server-provided props gating client render | — | external signals in arithmetic aren't statically typed |
| 6 | **Canonical values lab** | Educational tour of the value model | 0002 | string codes, number/decimal split, checkbox=`false`, array, per-field empty, `/0`→`null`, non-finite→`null` | (n/a — semantics reference) | — | arrays are not expression-addressable in v1 |
| 7 | **Design-system override** | One form, two renderers | 0001 | `bind_attr`, `control_attrs`, `widget_attrs`, `control_id`/`wrapper_id`/`help_id`/`error_id`, widget fallback | a `<Field>` component library | ✅ | — |
| 8 | **Business onboarding** | A larger multi-section form | 0001, 0002, 0004 | field groups + group `visible_when`, conditional attrs, cross-field `clean()`, one incremental field, exact computed limit | a multi-step wizard | — | non-field errors are submit-time in v1 |
| 9 | **Edit an account** | A real edit/CRUD workflow | 0001, 0004 | `initial=` from the store, input preserved on error, server permission-gated field, email availability | edit form + async check | — | — |
| 10 | **Multi-step wizard** | Server-held state across 3 steps | — | session state, validate-before-advance, conditional step skip, back nav | Formik/RHF/TanStack wizard patterns | — | wizard state kept server-side |
| 11 | **Tampering lab** | Server-authority made tangible | 0002, 0003, 0004 | crafted hostile submissions → authoritative outcomes (total, seats, hidden, scope, external signal, CSRF) | (n/a) | — | — |
| 12 | **Form-level errors** | Rules spanning fields | 0004 | non-field `clean()` errors (date range, budget split), live computed preview | schema cross-field refine | — | non-field errors are submit-time in v1 |
| 13 | **Date / time & localization** | Temporal canonical values | 0002 | canonical `date`/`time`/`datetime` strings, lossless round-trip, server validation | (n/a — semantics) | — | — |
| 14 | **Widget gallery** | Widget compatibility | 0001 | first-class reactive widgets vs. correct Django native fallback | a component library | — | radio/multi-checkbox/file are fallback-rendered |
| 15 | **Cascading dropdowns** | country → region → city | — | `choices_from` + `depends_on`, server re-render, `data-indicator` pending, invalid-child reset | client fetch/cache/option-state | ✅ (architectural, [page](comparisons/cascading.md)) | large client-side-filtered lists |

### Retained feature demo

- **Whole-form SSE submit** — `reactive_form_response()` patches the entire form
  fragment on submit (contrast with the *per-field* incremental validation in #1).

`risks` documents the honest trade-offs of the backend-first approach.

## What each example teaches

1. **Account registration** — incremental validation is *ordinary Django
   validation invoked earlier and returned over SSE*: one `validate_on` field
   declaration and one `reactive_validate` endpoint, no per-field wiring.
2. **Order configurator** — one Python schema drives conditional visibility,
   requiredness, disabled/read-only state, dynamic help, and an exact-`Decimal`
   total that the server recomputes authoritatively (a tampered total is
   ignored). A choice code `"001"` stays a string on both sides.
3. **Team roster** — standard Django formset rows behave independently: typing
   in row 0 does not affect row 1, and per-row conditionals fire per row.
4. **Settings dashboard** — scoping is not only a formset feature: several
   prefixed forms with overlapping field names coexist without collision.
5. **Feature-flagged form** — a server-owned signal (permission/plan/flag)
   drives the same rule on client and server; a client cannot forge it.
6. **Canonical values lab** — the exact canonical type of every field kind, and
   the total, divergence-free arithmetic rules.
7. **Design-system override** — the same form contract rendered by two
   presentation adapters with zero form-class changes.
8. **Business onboarding** — the approach scales to a realistic multi-section
   form with grouped visibility and one database-backed incremental check.

## Source layout

Examples are organized one module per scenario for readability:

```text
examples/examples/
    forms/          # one module per example (registration.py, order_configurator.py, …)
    views/          # matching view modules + shared GET/POST helpers
    services.py     # deterministic, clearly-labeled fake "database" services
    templates/examples/<example>/
```

- **Shared renderer**: `src/rg/forms/templates/rg_forms/` (the reference Bulma
  adapter; overridden in the design-system example).
- **Base template**: `examples/templates/base.html`.
