# Changelog

All notable changes to rg.forms are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-08-24

Implements ADR-0002 (canonical expression semantics), ADR-0003 (scoped signals /
reactive formsets), and ADR-0004 (declarative incremental server validation).

### Added

- **Compiled expression DSL (ADR-0002).** rg.forms expressions are now parsed to
  one AST and compiled to two targets — a Python evaluator (server) and a
  Datastar/JS expression string (client) — so both sides interpret the same
  expression against the same values identically. New: `serialize_js` /
  `serialize_expression`, a typed operator matrix, and a client/server
  conformance test suite (Python + Node).
- **Reactive value normalization (ADR-0002).** A loss-minimizing normalization
  layer (`rg.forms.normalization`) maps each field to its canonical reactive
  value (string / number / boolean / null / array) with a defined empty value
  per field kind. It feeds both the client seed and server evaluation.
- **Build-time expression check (ADR-0002 §5).** A Django system check
  (`rg_forms.W001`) validates every expression against the form's fields,
  `Meta.external_signals`, and the reserved `rgForms` namespace; it flags unknown
  references, string operands to arithmetic, and array-typed field references.
- **Scoped signals & reactive formsets (ADR-0003).** Prefixed forms and formset
  rows now get an independent nested signal namespace `rgForms.<scope>`. New
  `{% reactive_formset_signals formset %}` tag seeds all rows; `data-bind`,
  expressions, and seeding all agree on the scope. Standard Django formsets are
  now fully reactive per row.
- **Declarative incremental server validation (ADR-0004).** New `validate_on`
  (`"blur"`/`"change"`) and `debounce` field kwargs; `reactive_validate` /
  `reactive_validate_response` view helpers; a JSON-signals → form-data adapter
  (`rg.forms.adapters.signals_to_querydict`) with scope authorization and
  signal-scope filtering; a `validate_action` tag argument; stable field ids
  (`control_id`/`wrapper_id`/`help_id`/`error_id`) and a minimal `aria-*`
  contract in the field context.

### Security

- **Signal seeding is escaped for the single-quoted `data-signals` attribute.**
  `reactive_signals` / `reactive_formset_signals` previously marked raw JSON
  containing form values as safe, so an apostrophe (or `<`/`&`) in bound/initial
  data could break out of the attribute (HTML injection). The value is now
  escaped for the documented single-quoted context (`"` kept for readable JSON).

### Changed

- **Falsy reactive rules now hide / de-require on the server.** A `visible_when`
  / `required_when` that *evaluates to a falsy value* (e.g. an undefined external
  signal, or `null`) now hides the field / makes it not-required, matching client
  truthiness. Only a genuine evaluation **error** fails open (visible / not
  required). Previously any `None` result — error or legitimate null — defaulted
  to visible, which could diverge from the browser.
- **Numeric-only arithmetic is enforced at build time via type inference.** The
  system check rejects any non-numeric arithmetic operand — string/boolean
  literals, references to string/boolean/date/uuid *fields*, **and
  boolean-valued subexpressions** such as `($name == 'x') * 2`. Only
  `number`/`decimal` (and untyped external) operands qualify.
- **Non-finite values never reach the client.** Arithmetic `NaN`/`Infinity`
  operands (including `"NaN"`/`"Infinity"` strings) and overflowing results are
  `null` identically on client and server; **normalization** also refuses to
  seed a non-finite float (mapping it to the canonical empty and keeping an
  overflowing numeric string as-is), and `get_signals_json` asserts valid JSON
  (`allow_nan=False`) so a bare `NaN`/`Infinity` can never break Datastar's parser.
- **Computed fields no longer need `required=False`.** A computed field is
  recomputed and its result cleaned directly, so a default-required computed
  field validates without an editable input.
- **New `ReactiveForm.get_external_signal_values()` hook** supplies server-side
  values for declared `external_signals`, so expressions mixing external signals
  and fields evaluate the same on the server as in the browser.

- **Expressions are transmitted compiled, not raw (ADR-0002/0003).** Emitted
  `data-*` attributes now contain compiled Datastar/JS
  (`$order_type == 'urgent'` → `($order_type === "urgent")`) and, inside a
  prefixed form, scoped references (`$rgForms.<scope>.order_type`). Context keys
  such as `visible_when`, `required_when`, `computed`, and the `*_expr` values
  now hold compiled expressions. `field.get_field_reactive_attrs()` still returns
  the raw declared expressions for introspection.
- **Strict typed semantics (ADR-0002 §3) — behavior corrections.** Equality is
  strict and typed (no numeric coercion of strings, so a choice code `"001"`
  compares as the string `"001"` on both sides); `&&`/`||`/`!` are
  boolean-returning; arithmetic is numeric-only; division by zero and invalid
  numeric operands yield `null` identically on client and server. Forms that
  relied on the previous loose coercion or on multi-value collapse will evaluate
  differently — these are bug fixes.
- **Computed fields are recomputed authoritatively (ADR-0002 §3).** The server
  recomputes computed values with exact `Decimal` arithmetic and runs the result
  through the target field's conversion/validation before it enters
  `cleaned_data`, instead of storing the browser's float preview.
- **Multi-value fields (ADR-0002 P2).** Server-side signals and expression data
  now use `getlist` semantics for multiple-choice fields (previously collapsed to
  the last value).
- **Any prefixed form receives scoped signals (ADR-0003).** A standalone
  *prefixed* form changes from shared to scoped signals, not only formsets.
- **Runtime expression errors are logged, not swallowed (ADR-0002 P7).**
  Evaluation stays fail-open but now logs to the `rg.forms` logger.

### Unchanged / compatible

- Unprefixed, non-formset forms remain byte-compatible with the previous release
  apart from the compiled-expression syntax noted above.
- Fields without `validate_on` behave exactly as before (submit-only validation).
- The `render_reactive_field` context keys from ADR-0001 remain a stable,
  additive surface.
