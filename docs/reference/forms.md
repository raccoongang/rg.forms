# ReactiveForm Reference

`ReactiveForm` extends `django.forms.Form` with reactive capabilities.

## Class

```python
from rg.forms import ReactiveForm
```

Inherits all standard Django form behavior — `is_valid()`, `cleaned_data`, `errors`, custom `clean()` methods, widgets, etc.

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
