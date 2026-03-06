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

## `{% render_reactive_field bound_field %}`

Renders a single field with its label, input, errors, and reactive attributes:

```html
{% render_reactive_field form.order_type %}
{% render_reactive_field form.priority label="Custom Label" %}
```

Uses the `rg_forms/field.html` template. Generates:

- Wrapper `<div>` with `data-show` if `visible_when` is set
- `<label>` with required indicator
- Input with `data-bind`, `data-computed` as needed
- Error messages
- Help text (static and dynamic `help_text_when`)

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

For computed fields:

```html
<input type="text" data-bind:total data-computed="$quantity * $price" readonly>
```

## `{% required_indicator bound_field %}`

Generates a required indicator (`*`) that respects `required_when`:

```html
<label>{{ form.email.label }} {% required_indicator form.email %}</label>
```

- Static required: `<span class="has-text-danger">*</span>`
- Dynamic required: `<span class="has-text-danger" data-show="$method == 'email'">*</span>`
- Not required: empty string

## `{{ field_name|signal_name }}`

Filter that converts a field name to a Datastar signal reference:

```html
{{ "my_field"|signal_name }}
```

Output: `$my_field`
