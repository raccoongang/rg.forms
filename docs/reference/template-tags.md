# Template Tags Reference

Load with:

```html
{% load reactive_forms %}
```

## `{% reactive_signals form %}`

Generates JSON for `data-signals` attribute:

```html
<form data-signals='{% reactive_signals form %}'>
```

Output:

```html
<form data-signals='{"order_type": "", "quantity": 1, "price": "10.00"}'>
```

## `{% render_reactive_form form %}`

Renders a complete form with all fields, signals, and a submit button:

```html
{% render_reactive_form form %}
{% render_reactive_form form submit_label="Save Order" %}
```

Uses the `rg_forms/form.html` template.

### `action` parameter

When `action` is provided, the form submits via Datastar `@post` instead of a native HTML form submit. This enables [SSE validation](../guide/sse-validation.md) — only the form re-renders on validation errors, not the entire page.

```html
{% render_reactive_form form "Save" action="/my-url/" %}
{% render_reactive_form form "Register" action=action_url %}
```

What changes when `action` is set:

- The form is wrapped in `<div id="reactive-form-container">` (SSE patch target)
- The form gets `data-on:submit__prevent="@post('...', {contentType: 'form'})"` — Datastar intercepts submit (both button click and Enter key) and sends via SSE instead of a native page-reloading POST

### `validate_action` parameter

Supplies the URL for [declarative incremental validation](../guide/incremental-validation.md)
(fields declared with `validate_on`). The tag is context-aware and forwards the
request's CSRF token to each field's validate handler.

```html
{% render_reactive_form form action="/submit/" validate_action="/validate/" %}
```

| `validate_action` | Meaning |
|---|---|
| omitted | inherit `action` |
| `""` | validate against the **current URL** (intentional) |
| a URL | validate against that URL |

If a field declares `validate_on` but no validation action can be resolved, the
tag raises a render-time configuration error rather than silently no-op'ing.

## `{% render_reactive_field bound_field %}`

Renders a single field with its label, input, errors, and reactive attributes:

```html
{% render_reactive_field form.order_type %}
{% render_reactive_field form.priority label="Custom Label" %}
```

Uses the `rg_forms/field.html` template. Generates:

- Wrapper `<div>` with `data-show` if `visible_when` is set
- `<label>` with required indicator
- Input with `data-bind`, or a `data-text` span for a computed field
- Error messages
- Help text (static and dynamic `help_text_when`)

### Context contract (stable, overridable API) {#context-contract}

`rg_forms/field.html` is a **reference example** meant to be overridden so
rg.forms adopts your design system (see the
[Bring your own design system](../guide/custom-rendering.md) guide). The
context passed to that template is a **supported, semver-relevant surface**:
new keys may be added in minor releases, but existing keys will not be renamed,
removed, or change meaning/type without a major version.

!!! note "Expressions are compiled and scoped"
    Every `*_when` / `computed` / `*_expr` value below is a **compiled
    Datastar/JS expression** (ADR-0002), not the raw rg.forms DSL you wrote —
    e.g. `$order_type == 'urgent'` is emitted as `($order_type === "urgent")`.
    Inside a **prefixed form or formset row** field references are additionally
    **scoped** to that row's signal namespace
    (`$rgForms.<scope>.order_type`, ADR-0003). Drop these values straight into
    `data-*` attributes; do not re-parse them. For two-way binding use
    `bind_attr` (below) rather than hand-building `data-bind:{{ field_name }}`,
    which is not scope-safe.

| Key | Type | Meaning |
|---|---|---|
| `field` | `BoundField` | The bound field. Use `field.html_name`, `field.id_for_label` — these are formset-safe. |
| `formatted_value` | `str` | Widget-formatted value (HTML5-friendly for date/time inputs). **Render this, not `field.value`**, as the input's `value` / textarea content. |
| `label` | `str` | Field label (overridable via the `label=` tag kwarg). |
| `help_text` | `str` | Static help text. |
| `visible_when` | `str \| None` | Datastar expression for `data-show`. |
| `initially_hidden` | `bool` | The server's answer to the same question `data-show` answers in the browser: `True` when the field has a `visible_when` and it is **already false** for the data the form holds. `data-show` only takes effect once Datastar has booted, so without acting on this a field whose rule is already false paints visible for a frame and then vanishes. Render it as an inline `display: none` **in addition to** `data-show`, not instead of it — Datastar clears the inline value when the rule turns true. Always `False` for a field with no rule, and for a bound field of a non-`ReactiveForm`. |
| `required_when` | `str \| None` | Datastar expression for the dynamic required indicator. |
| `computed` | `str \| None` | Datastar expression for a read-only computed value. |
| `disabled_when` | `str \| None` | Datastar expression for `data-attr:disabled`. |
| `read_only_when` | `str \| None` | Datastar expression for `data-attr:readonly`. |
| `help_text_when` | `dict \| None` | `{expression: help_text}` for dynamic help text. |
| `placeholder_when` | `dict \| None` | `{expression: placeholder}` for dynamic placeholder. |
| `min_when` | `dict \| None` | `{expression: min_value}` for dynamic minimum. |
| `max_when` | `dict \| None` | `{expression: max_value}` for dynamic maximum. |
| `is_required` | `bool` | Static required flag. |
| `field_name` | `str` | Unprefixed logical field name. Use `bind_attr` for `data-bind` (it is scope-safe); use `field_name` only for introspection, **not** for the submitted `name`. |
| `bind_attr` | `SafeString` | The ready-to-emit `data-bind` attribute for the control. Unprefixed forms emit the keyed form `data-bind:role`; prefixed forms/formset rows emit the scoped value form `data-bind="rgForms.<scope>.role"` (ADR-0003). |
| `widget_type` | `str` | Lowercased widget class name (e.g. `"emailinput"`, `"select"`) — use for branching. |
| `input_type` | `str` | HTML `<input type>` value (`"email"`, `"datetime-local"`, `"number"`, …; defaults to `"text"`). Put this on the element. |
| `is_simple_input` | `bool` | True when the widget is a text-family input the reference template renders as a single `<input>` (text/number/email/url/date/time/datetime-local/password). False for select/checkbox/textarea and for widgets that should fall back to Django's native rendering (radio, multi-checkbox, file, multi-widget, custom). |
| `widget_attrs` | `dict` | Presentational widget attrs (`placeholder`, `autocomplete`, `autofocus`, `inputmode`, custom `data-*`). Managed attrs (`id`, `name`, `required`, `disabled`, `readonly`, `min`, `max`, `maxlength`, `minlength`) are excluded so you can spread it without double-rendering. |
| `required_expr` | `str \| None` | Datastar expression for `data-attr:required`, combining `visible_when` and `required_when`. `None` when the field is unconditionally required (render static `required`) or never required. Keeps native validation in step with visibility. |
| `placeholder_expr` | `str \| None` | Datastar expression for `data-attr:placeholder`, built from `placeholder_when`. `None` when unset. |
| `min_expr` / `max_expr` | `str \| None` | Datastar expressions for `data-attr:min` / `data-attr:max`, built from `min_when` / `max_when`. `None` when unset; fall back to static `html5_attrs.min` / `max`. |
| `errors` | `ErrorList` | Field errors. |
| `html5_attrs` | `dict` | HTML5 validation attrs derived from the field (`required`, `min`, `max`, `maxlength`, `minlength`). |
| `choices` | `list \| None` | Choices for `select`/choice widgets. |
| `control_id` | `str` | Stable, formset-safe id for the control (`id_for_label`, with an injective fallback for incrementally-validated fields when `auto_id=False`). Empty for non-incremental fields with no `auto_id`. (ADR-0004 §6) |
| `wrapper_id` | `str` | Id of the field wrapper — the **patch target** for incremental validation (`{control_id}_field`). |
| `help_id` / `error_id` | `str` | Ids for the help / error elements (`{control_id}_help` / `_error`), used by `aria-describedby`. |
| `control_attrs` | `SafeString` | Extra attributes for the control: the incremental-validation `data-on:*` handler + `data-indicator` pending signal (when `validate_on` is set), plus `aria-invalid` / `aria-describedby`. Spread onto the control element. (ADR-0004) |

The `render_reactive_field` tag also accepts `validate_action` and `csrf_token`
kwargs (normally threaded automatically by `render_reactive_form`) used to build
the incremental-validation request — see
[Incremental validation](../guide/incremental-validation.md).

!!! note "`widget_attrs` and `control_attrs` can both carry `aria-*`"
    `control_attrs` emits `aria-invalid` when the field has errors and
    `aria-describedby` when there is an error or help text to point at.
    `aria-invalid` / `aria-describedby` are deliberately **not** in the
    `widget_attrs` exclude list, because a form that sets them in
    `widget.attrs` (a common way to associate errors for a template that
    renders bare `{{ field }}`) would otherwise lose them entirely on a
    template that does not spread `control_attrs`. The cost is that a template
    spreading **both** emits them twice. Pick one source per attribute: keep
    the ARIA in `widget.attrs` and drop `control_attrs`, or leave `widget.attrs`
    free of ARIA and let `control_attrs` own it. HTML resolves a duplicate
    attribute first-wins, silently.

!!! warning "Use `field.html_name` / `field.id_for_label`, never `field_name` for `name`/`id`"
    Inside a Django formset the submitted name is prefixed (`form-0-role`).
    Rendering `name="{{ field_name }}"` produces colliding, unsubmittable
    fields. Always render `name="{{ field.html_name }}"` and
    `id="{{ field.id_for_label }}"`.

## `{% render_field_group form group_name %}`

Renders a field group with its header, description, and all fields:

```html
{% render_field_group form "personal" %}
{% render_field_group form "business" %}
```

Uses the `rg_forms/field_group.html` template. Generates:

- Group container with `data-show` if the group has `visible_when`
- Group label as heading
- Group description
- All fields in the group via `{% render_reactive_field %}`

Group context keys:

| Key | Type | Meaning |
|---|---|---|
| `form` | `ReactiveForm` | The form the group belongs to. |
| `group` | `FieldGroup` | The group definition (`label`, `description`, `css_class`, `fields`). |
| `group_name` | `str` | The group's key in `Meta.field_groups`. |
| `group_visible_when` | `str \| None` | Compiled + scoped expression for `data-show` on the group container. |
| `group_initially_hidden` | `bool` | The group-level counterpart of `initially_hidden` — `True` when the group's rule is already false. Render as an inline `display: none` on the container. |
| `fields` | `list[tuple[str, BoundField]]` | The group's fields, in declaration order. |
| `validate_action` / `csrf_token` | | Threaded through to each field for incremental validation. |

## `{% reactive_wrapper_attrs bound_field %}`

Generates wrapper div attributes (for manual rendering):

```html
<div class="field" {% reactive_wrapper_attrs form.priority %}>
    ...
</div>
```

Output:

```html
<div class="field" data-show="$order_type == 'urgent'">
```

## `{% reactive_input_attrs bound_field %}`

Generates input element attributes (for manual rendering):

```html
<input type="text" {% reactive_input_attrs form.quantity %}>
```

Output:

```html
<input type="text" data-bind:quantity>
```

Computed fields get nothing beyond the binding, and should not be rendered as an
input at all — see [Computed fields](../guide/computed.md#rendering-a-computed-field).

## `{% required_indicator bound_field %}`

Generates a required indicator (`*`) that respects `required_when`:

```html
<label>{{ form.email.label }} {% required_indicator form.email %}</label>
```

- Static required: `<span class="has-text-danger">*</span>`
- Dynamic required: `<span class="has-text-danger" data-show="$method == 'email'">*</span>`
- Not required: empty output

The markup comes from `rg_forms/_required_indicator.html`, so override that
template to render the indicator in your own design system. Its context is
`required_when` (a compiled expression, or `None`) and `is_required` (a bool).

## `{{ field_name|signal_name }}`

Filter that converts a field name to a Datastar signal reference:

```html
{{ "my_field"|signal_name }}
```

Output: `$my_field`
