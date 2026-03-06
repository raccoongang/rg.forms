# ReactiveForm Reference

`ReactiveForm` extends `django.forms.Form` with reactive capabilities.

## Class

```python
from rg.forms import ReactiveForm
```

Inherits all standard Django form behavior — `is_valid()`, `cleaned_data`, `errors`, custom `clean()` methods, widgets, etc.

## View Utilities

### `reactive_form_response(request, form, fragment_template, *, success_url=None, on_success=None, context=None)`

Handles form POST with SSE support. Returns an SSE patch on validation errors (Datastar request) or a redirect on success.

```python
from rg.forms import reactive_form_response

def my_view(request):
    if request.method == "POST":
        form = MyForm(request.POST)
        response = reactive_form_response(
            request, form, "_fragment.html",
            success_url="/done/",
            context={"action_url": request.build_absolute_uri()},
        )
        if response:
            return response
    else:
        form = MyForm()
    return render(request, "page.html", {"form": form})
```

**Returns**: `HttpResponseRedirect | DatastarResponse | None`

| Scenario | Datastar request | Regular request |
|----------|-----------------|-----------------|
| Valid form | SSE redirect to `success_url` | `HttpResponseRedirect` |
| Invalid form | SSE patch with re-rendered fragment | `None` (view renders full page) |

See the [SSE Validation guide](../guide/sse-validation.md) for full details.

## Methods

### `get_signals() -> dict`

Returns a dict of initial signal values for Datastar. Values come from (in priority order): bound data, initial data, field initial, or empty string.

```python
form = OrderForm(initial={'quantity': 5})
form.get_signals()
# {'order_type': '', 'quantity': 5, 'unit_price': ''}
```

### `get_signals_json() -> str`

Returns `get_signals()` as a JSON string, ready for `data-signals`:

```html
<form data-signals='{% reactive_signals form %}'>
```

### `get_field_reactive_attrs(field_name: str) -> dict`

Returns reactive attributes for a field (only non-None values):

```python
form.get_field_reactive_attrs('priority')
# {'visible_when': "$order_type == 'urgent'"}
```

### `is_field_visible(field_name: str) -> bool`

Server-side evaluation of `visible_when`. Returns `True` if:

- The field has no `visible_when`, or
- The expression evaluates to `True`

Returns `True` on evaluation error (fail-open).

### `is_field_required(field_name: str) -> bool`

Server-side evaluation of requirement. Returns `True` if:

- `field.required` is `True`, or
- `required_when` evaluates to `True`

### `get_computed_value(field_name: str)`

Evaluates a computed field's expression and returns the result.

### `get_visible_fields() -> list[str]`

Returns names of fields that have `visible_when` set.

### `get_computed_fields() -> list[str]`

Returns names of fields that have `computed` set.

### `populate(field_name, queryset, ...)`

Populate a ChoiceField's choices from a queryset. See [Cascading Dropdowns](../guide/cascading.md#populate-method).

## Field Group Methods

### `get_field_groups() -> dict[str, FieldGroup]`

Returns all field groups from `Meta.field_groups`.

### `get_group(group_name: str) -> FieldGroup | None`

Returns a specific field group.

### `get_fields_in_group(group_name: str) -> list[tuple[str, BoundField]]`

Returns `(name, bound_field)` tuples for fields in a group.

### `is_group_visible(group_name: str) -> bool`

Server-side evaluation of group's `visible_when`.

## Validation behavior

`ReactiveForm` overrides `_clean_fields()`:

1. Hidden fields (`visible_when` is `False`) are set to `None` — no validation
2. Computed fields are recalculated from their expression
3. `required_when` is evaluated and enforced
4. Standard Django `clean_<fieldname>()` runs for visible fields
5. Standard Django `clean()` runs for cross-field validation

## Meta options

```python
class MyForm(ReactiveForm):
    # ... fields ...

    class Meta:
        field_groups = {
            'group_name': FieldGroup(
                fields=['field1', 'field2'],
                label='Group Label',
                visible_when="$some_field == 'value'",
                description='Optional description',
                css_class='custom-class',
            ),
        }
```
