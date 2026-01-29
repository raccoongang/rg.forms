# rg.forms

Reactive Django Forms with Datastar integration.

## Features

- **Declarative field visibility**: Show/hide fields based on other field values
- **Dynamic requirements**: Make fields required conditionally
- **Computed fields**: Automatic calculation based on other fields
- **Remote data**: Fetch choices from server based on dependencies
- **Cross-field validation**: Validate with visibility awareness
- **Multi-framework skins**: Bootstrap, Bulma, Tailwind, Carbon support

## Installation

```bash
pip install rg-forms
```

## Quick Start

```python
from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])

    # Only visible when order_type is 'urgent'
    priority = ReactiveChoiceField(
        choices=[('low', 'Low'), ('high', 'High')],
        visible_when="$order_type == 'urgent'"
    )

    # Computed field
    total = ReactiveCharField(
        computed="$quantity * $price",
        required=False,
    )
```

## Django Setup

```python
INSTALLED_APPS = [
    # ...
    'rg.forms',
]
```

## Documentation

See [plan.org](plan.org) for detailed architecture and implementation plan.

## License

MIT
