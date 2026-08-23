# ADR 0001 — Design-system-agnostic field rendering driven by Python metadata

- Status: Accepted
- Date: 2026-08-23
- Implemented: 2026-08-23 (P1–P4 + docs + example + tests)
- Deciders: Oleksii Koval (author of rg.forms)
- Motivating consumer: a downstream Django project adopting rg.forms as its form-rendering layer.

## Context

rg.forms' thesis is that **form metadata lives in Python and rendering is a central, swappable
concern**: a developer declares fields (with `visible_when`, `required_when`, `computed`,
cascading `choices_from`, and ordinary presentational hints) once in Python, and every form
renders with no per-form HTML. The `rg_forms/*.html` templates the package ships are **reference
examples** (Bulma CSS), meant to be overridden per project so the library adopts the host app's
design system.

A consuming project tried to realize this and hit friction. Its real design language is a bespoke
component set (a composed input control with a title element, floating labels, icon/prefix/suffix
slots, and dedicated error/disabled state classes), not plain Bulma `.input`. The
project overrode `templates/rg_forms/field.html` to **delegate** to those components. That works,
but three gaps in the library made the override harder than it should be, and a fourth is a latent
correctness bug for any consumer using formsets.

In its first migration step the project delegated only the text-family widgets
(`textinput`/`emailinput`/`urlinput`/`numberinput`) to its components; the remaining widgets still
fall through to the shipped Bulma markup. The gaps below block a clean, complete delegation.

Current `render_reactive_field` inclusion-tag context (from
`src/rg/forms/templatetags/reactive_forms.py`) passes: `field` (BoundField), `formatted_value`,
`label`, `help_text`, `visible_when`, `required_when`, `computed`, `disabled_when`,
`read_only_when`, `help_text_when`, `placeholder_when`, `min_when`, `max_when`, `is_required`,
`field_name`, `widget_type`, `errors`, `html5_attrs`, `choices`.

## Problems

### P1 — No mapped HTML input type in the context

The context exposes `widget_type` (e.g. `"emailinput"`, `"datetimeinput"`) but not the HTML
`type` attribute an `<input>` needs (`"email"`, `"datetime-local"`). A design-system override that
routes several widget types through one input component must re-derive this itself. The naive
`widget_type|cut:"input"` template trick gives the wrong answer for `datetimeinput`
(→ `"datetime"`, not `"datetime-local"`) and is fragile in general.

### P2 — Presentational widget attrs are not surfaced (the main blocker)

The whole point is "presentation as Python metadata," yet the tag ignores
`field.field.widget.attrs`. Placeholder, autocomplete, autofocus, inputmode, and any custom
`data-*` a developer declared on the widget never reach the template context. A consumer template
can reach into `field.field.widget.attrs.placeholder` manually, but:

- it is undocumented and easy to get wrong,
- it bypasses the library's own `placeholder_when` / dynamic-attr story, and
- there is no single, blessed way to pass "render this field with this placeholder/autocomplete"
  from Python without dropping to `widget=forms.TextInput(attrs=…)`, which is exactly the
  boilerplate rg.forms exists to remove.

### P3 — The override contract is undocumented and unstable

`rg_forms/field.html` is intended to be overridden, but nothing documents the **context contract**
(the list of variables above) as a stable, supported surface. A consumer overriding the template is
coding against internals that could change silently. There is also no guide for "bring your own
design system," and the shipped templates are not clearly labeled as examples rather than product.

### P4 — Formset prefixes are dropped (latent correctness bug)

The shipped `field.html` renders `name="{{ field_name }}"` and `id="id_{{ field_name }}"`, where
`field_name` is the **unprefixed** `bound_field.name`. Inside a Django formset the submitted name
must be the **prefixed** `bound_field.html_name` (e.g. `form-0-role`) and the id must be
`bound_field.id_for_label`. As shipped, `render_reactive_field` produces colliding, unsubmittable
fields in a formset. A consumer hit this and abandoned `render_reactive_field` for a formset,
rendering native `{{ field }}` output instead. (Delegating to components that use
`field.html_name`/`field.id_for_label` sidesteps it, but the shipped template and the documented
contract must not encourage the unprefixed form.)

## Decision

Make the field-rendering layer design-system-agnostic and metadata-complete, without changing
rg.forms' Python-first API:

1. **P1 — Add `input_type` to the `render_reactive_field` context.** Compute the correct HTML
   input type from the widget (map `datetimeinput → "datetime-local"`, `dateinput → "date"`,
   `timeinput → "time"`, `emailinput → "email"`, `urlinput → "url"`, `numberinput → "number"`,
   password → `"password"`, default `"text"`). Keep `widget_type` for branching; add `input_type`
   for the `<input>`.

2. **P2 — Surface presentational widget attrs.** Add `widget_attrs` to the context, carrying a
   sanitized copy of `field.field.widget.attrs` (at minimum `placeholder`, `autocomplete`,
   `autofocus`, `inputmode`, plus any `data-*`). Additionally (or alternatively) accept first-class
   presentational kwargs on the reactive fields — `placeholder=`, `autocomplete=`, `autofocus=` —
   stored on the field and merged into `widget_attrs`, so a developer never has to hand-build a
   `widget=…` just to set a placeholder. Document precedence (explicit kwarg > widget.attrs).

3. **P3 — Document and stabilize the override contract.** Publish the context-variable contract as
   a supported API in `docs/reference/template-tags.md`, add a `docs/guide/custom-rendering.md`
   ("bring your own design system") showing a delegating `field.html` that forwards context to a
   host component, and label the shipped Bulma templates as reference examples in-file and in
   docs. Treat the context keys as semver-relevant surface going forward.

4. **P4 — Fix formset-safe naming.** Change the shipped `field.html` (and any doc examples) to use
   `field.html_name` for `name`, `field.id_for_label` for `id`, and the matching `for`/aria ids.
   Add a formset test. This is a bug fix and should ship regardless of the rest.

`reactive_form_response` (SSE submit helper) is already markup-agnostic and needs no change; it is
called from the host view and returns SSE patches/redirects against a host-supplied fragment
template.

## Backward compatibility (hard requirement)

This change MUST NOT force any existing consumer to patch project code. It is additive plus one
bug fix that is a no-op in the common case. The implementing agent must preserve the following:

- **Context keys are additive only.** `render_reactive_field` may ADD keys (`input_type`,
  `widget_attrs`) but must NOT rename, remove, or change the meaning/type of any existing key
  (`field`, `formatted_value`, `label`, `help_text`, `visible_when`, `required_when`, `computed`,
  `disabled_when`, `read_only_when`, `help_text_when`, `placeholder_when`, `min_when`, `max_when`,
  `is_required`, `field_name`, `widget_type`, `errors`, `html5_attrs`, `choices`). This is what
  guarantees existing project template overrides keep working untouched.
- **New field kwargs are optional** (`placeholder=`/`autocomplete=`/`autofocus=` default to
  unset); forms that don't use them behave exactly as before.
- **P4 is a no-op for the common case.** For a non-formset form with the default `auto_id`,
  `field.html_name == field.name` and `field.id_for_label == "id_" + name`, so the generated
  `name`/`id` are byte-identical. Output changes only for formsets (a fix) and custom `auto_id`
  (a correction).

**Migration required:** none, to keep working.
**Opt-in:** consumers adopt the new metadata (`input_type`, `widget_attrs`, first-class kwargs)
only when they want them.
**CHANGELOG-worthy behavior change:** consumers still using the shipped Bulma `field.html`
will see previously-dropped `widget.attrs` (placeholder/autocomplete) begin to render once P2 lands
— benign, but call it out in release notes. Anyone who copied the old shipped template into their
project retains the P4 formset bug until they re-sync; that is their code, not a forced change.

Because the change is backward compatible, it can ship in a minor release. If any of the above
cannot be honored (e.g. a context key must change), that would be a breaking change and belongs in
a separate major-version ADR, not this one.

## Consequences

- Consumers can override one template (`rg_forms/field.html`) into a thin dispatcher that forwards
  `field`, `input_type`, `widget_attrs`, and the reactive-attr set to their own components — no
  per-form HTML, presentation declared in Python.
- `render_reactive_field` becomes safe in formsets (P4), removing the one hard incompatibility that
  pushed a consumer off the tag.
- The Bulma example templates remain, now explicitly as examples; existing users relying on
  them are unaffected (the additions are backward-compatible context keys; P4 changes only the
  generated `name`/`id`, which is a fix, not a breaking change for non-formset forms because the
  prefix is empty there).
- Small ongoing cost: the context contract is now a supported surface to keep stable.

## Implementation notes (for the implementing agent)

- Touch points: `src/rg/forms/templatetags/reactive_forms.py` (context in `render_reactive_field`),
  `src/rg/forms/fields.py` (optional first-class `placeholder`/`autocomplete`/`autofocus` kwargs on
  `ReactiveFieldMixin`), `src/rg/forms/templates/rg_forms/field.html` (P4 naming; label as example),
  `docs/reference/template-tags.md` + new `docs/guide/custom-rendering.md`, and tests under
  `tests/`.
- Keep additions backward-compatible: only ADD context keys; do not rename or remove existing ones.
- Add tests: (a) `input_type` mapping incl. `datetime-local`; (b) `widget_attrs` carries
  placeholder/autocomplete and first-class kwargs override widget.attrs; (c) a formset renders
  prefixed `name`/`id` and round-trips a POST.
- Recommended consumer pattern: the overridden `rg_forms/field.html` is a thin dispatcher on
  `widget_type` that `{% include %}`s the host design-system component, and the host input
  component gains an additive, default-off reactive `bind` mode (emit `data-bind` +
  `visible_when`/`disabled_when`/`read_only_when`/`computed` pass-throughs) so native-submit forms
  render unchanged.
