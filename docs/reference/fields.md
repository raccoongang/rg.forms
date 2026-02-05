# Fields Reference

All reactive fields extend their Django counterparts with reactive attributes.

## Available fields

| Reactive field                | Django base           | Notes                  |
|-------------------------------|-----------------------|------------------------|
| `ReactiveCharField`           | `CharField`           |                        |
| `ReactiveIntegerField`        | `IntegerField`        |                        |
| `ReactiveFloatField`          | `FloatField`          |                        |
| `ReactiveDecimalField`        | `DecimalField`        |                        |
| `ReactiveBooleanField`        | `BooleanField`        |                        |
| `ReactiveChoiceField`         | `ChoiceField`         | Adds cascading support |
| `ReactiveMultipleChoiceField` | `MultipleChoiceField` |                        |
| `ReactiveEmailField`          | `EmailField`          |                        |
| `ReactiveURLField`            | `URLField`            |                        |
| `ReactiveDateField`           | `DateField`           |                        |
| `ReactiveDateTimeField`       | `DateTimeField`       |                        |
| `ReactiveTimeField`           | `TimeField`           |                        |

All standard Django field arguments (`required`, `label`, `initial`, `help_text`, `widget`, `validators`, etc.) work as usual.

## Reactive attributes

These are the additional keyword arguments available on all reactive fields:

### `visible_when`

:   **Type**: `str | None`

    Datastar expression controlling field visibility. When it evaluates to `False`, the field is hidden on the frontend and skipped during backend validation.

    ```python
    priority = ReactiveChoiceField(
        visible_when="$order_type == 'urgent'",
    )
    ```

### `required_when`

:   **Type**: `str | None`

    Datastar expression for dynamic requirement. Evaluated on the backend — if `True` and the field is empty, validation fails.

    ```python
    email = ReactiveEmailField(
        required=False,
        required_when="$contact_method == 'email'",
    )
    ```

### `computed`

:   **Type**: `str | None`

    Datastar expression for computed value. The field becomes read-only on the frontend. On submit, the server recalculates the value from this expression.

    ```python
    total = ReactiveDecimalField(
        computed="$quantity * $unit_price",
    )
    ```

### `depends_on`

:   **Type**: `list[str] | None`

    List of field names this field depends on. Used with `choices_from` on `ReactiveChoiceField` for cascading dropdowns.

    ```python
    product = ReactiveChoiceField(
        depends_on=["category"],
        choices_from=get_products,
    )
    ```

### `disabled_when`

:   **Type**: `str | None`

    Expression to conditionally disable the field.

    ```python
    max_users = ReactiveIntegerField(
        disabled_when="$plan == 'free'",
    )
    ```

### `read_only_when`

:   **Type**: `str | None`

    Expression to conditionally make the field read-only.

    ```python
    api_key = ReactiveCharField(
        read_only_when="$plan != 'premium'",
    )
    ```

### `help_text_when`

:   **Type**: `dict[str, str] | None`

    Dict mapping expressions to help text strings. Only the matching help text is shown.

    ```python
    max_users = ReactiveIntegerField(
        help_text_when={
            "$plan == 'free'": "Upgrade to customize",
            "$plan == 'premium'": "Unlimited users",
        },
    )
    ```

### `placeholder_when`

:   **Type**: `dict[str, str] | None`

    Dict mapping expressions to placeholder strings.

### `min_when`

:   **Type**: `dict[str, int | float] | None`

    Dict mapping expressions to minimum values.

### `max_when`

:   **Type**: `dict[str, int | float] | None`

    Dict mapping expressions to maximum values.

## ReactiveChoiceField extras

`ReactiveChoiceField` has additional attributes for declarative cascading:

| Attribute                | Type               | Default | Description                                      |
|--------------------------|--------------------|---------|--------------------------------------------------|
| `choices_from`           | `Callable \| None` | `None`  | Callable returning objects for choices           |
| `value_field`            | `str`              | `"pk"`  | Attribute for option value                       |
| `label_field`            | `str \| None`      | `None`  | Attribute for option label (default: `str(obj)`) |
| `label_template`         | `str \| None`      | `None`  | Format string, e.g. `"{name} (${price})"`        |
| `empty_choice`           | `str \| None`      | `None`  | Label for empty option                           |
| `empty_choice_no_parent` | `str \| None`      | `None`  | Label when parent not selected                   |

## Import

All fields are exported from the package root:

```python
from rg.forms import (
    ReactiveCharField,
    ReactiveIntegerField,
    ReactiveChoiceField,
    # ... etc
)
```
