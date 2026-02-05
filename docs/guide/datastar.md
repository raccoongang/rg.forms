# Datastar Integration

rg.forms generates [Datastar](https://data-star.dev) attributes for reactive frontend behavior. This page covers the Datastar-specific details.

## Loading Datastar

Add Datastar to your base template:

```html
<script type="module" src="https://cdn.jsdelivr.net/gh/starfederation/datastar@1.0.0-RC.7/bundles/datastar.js"></script>
```

Please note that recommended way to add datastar is always use versioned URL, to avoid issues with internal API changes. When
new version is released, please verify the changes from the changelog before bumping the release.

## Generated attributes

rg.forms maps reactive field properties to Datastar attributes:

| Field property | Generated attribute                 | Example                               |
|----------------|-------------------------------------|---------------------------------------|
| (all fields)   | `data-bind:fieldname`               | `data-bind:order_type`                |
| `visible_when` | `data-show="expr"`                  | `data-show="$order_type == 'urgent'"` |
| `computed`     | `data-computed="expr"` + `readonly` | `data-computed="$quantity * $price"`  |

## Signals

Datastar uses **signals** for reactive state. rg.forms generates the initial signals from form data:

```html
<form data-signals='{% reactive_signals form %}'>
```

This outputs something like:

```html
<form data-signals='{"order_type": "standard", "quantity": 1, "unit_price": "10.00"}'>
```

### Signal syntax rules

- In **expressions** (`data-show`, `data-text`, `data-computed`): use `$fieldname`
- In **`data-bind`**: use the field name directly, no `$` prefix
- In **`data-signals`**: JSON object with field names as keys, no `$` prefix

## Event handling

Use `data-on` for Datastar event handlers. Common pattern for cascading updates:

```html
<select data-bind:category
        data-on:change="@post('/update/', {contentType: 'form'})">
```

!!! warning
    Use `{contentType: 'form'}` with `@post` for Django forms. This sends data as form-encoded (including CSRF token) instead of JSON.

## SSE responses

For server-side updates (cascading dropdowns, partial re-rendering), use `datastar-py`:

```python
from datastar_py.django import DatastarResponse

def update_view(request):
    form = MyForm(request.POST)
    response = DatastarResponse()
    response.merge_fragments(
        render_to_string('_form_fragment.html', {'form': form}, request)
    )
    return response
```

## Useful Datastar attributes

These can be used directly in templates alongside rg.forms:

```html
<!-- Computed display (non-input) -->
<span data-text="$quantity * $unit_price"></span>

<!-- Named computed signal -->
<div data-computed:total="$quantity * $price"></div>

<!-- Event with debounce -->
<input data-on:input__debounce.300ms="@post('/search/')">

<!-- Event with prevent default -->
<form data-on:submit__prevent="@post('/save/', {contentType: 'form'})">
```

## Reference

Full Datastar documentation: [data-star.dev/reference/attributes](https://data-star.dev/reference/attributes)
