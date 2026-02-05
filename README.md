# rg.forms

Reactive Django Forms with [Datastar](https://data-star.dev) integration.

Declare visibility rules, dynamic requirements, computed fields, and cascading dropdowns — all in Python. The frontend reacts instantly, the backend validates securely.

## Installation

```bash
pip install rg-forms
```

```python
INSTALLED_APPS = [
    # ...
    'rg.forms',
]
```

## Quick example

```python
from rg.forms import ReactiveForm, ReactiveChoiceField, ReactiveIntegerField, ReactiveDecimalField

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])

    # Only visible when order_type is 'urgent'
    priority = ReactiveChoiceField(
        choices=[('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')],
        visible_when="$order_type == 'urgent'",
    )

    quantity = ReactiveIntegerField(min_value=1, initial=1)
    unit_price = ReactiveDecimalField(decimal_places=2, initial="10.00")

    # Computed on both frontend and backend
    total = ReactiveDecimalField(
        computed="$quantity * $unit_price",
        required=False,
    )
```

```html
{% load reactive_forms %}
<form method="post" data-signals='{% reactive_signals form %}'>
    {% csrf_token %}
    {% render_reactive_form form %}
</form>
```

## Features

| Feature | Attribute | Description |
|---------|-----------|-------------|
| Conditional visibility | `visible_when` | Show/hide fields based on expressions |
| Dynamic requirements | `required_when` | Make fields conditionally required |
| Computed fields | `computed` | Auto-calculate from other fields |
| Conditional disable | `disabled_when` | Disable fields based on conditions |
| Read-only toggle | `read_only_when` | Make fields conditionally read-only |
| Dynamic help text | `help_text_when` | Show different help text per condition |
| Cascading dropdowns | `choices_from` + `depends_on` | Dependent field choices |
| Field groups | `FieldGroup` + `Meta` | Sections with shared visibility |

## Documentation

Full docs: [raccoongang.github.io/rg.forms](https://raccoongang.github.io/rg.forms)

## Requirements

- Python 3.12+
- Django 5.0+
- [Datastar](https://data-star.dev) on the frontend

## License

MIT
