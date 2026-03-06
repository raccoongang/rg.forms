# rg.forms

**Reactive Django Forms with Datastar integration.**

rg.forms lets you build dynamic Django forms where fields react to each other — visibility, requirements, computed values, and cascading dropdowns — all declared in Python.

## Features

- **`visible_when`** — show/hide fields based on other field values
- **`required_when`** — make fields conditionally required
- **`computed`** — automatic calculations from other fields
- **`disabled_when` / `read_only_when`** — conditional field states
- **`choices_from` + `depends_on`** — declarative cascading dropdowns
- **Field groups** — organize fields into sections with shared visibility
- **Backend validation** — hidden fields are skipped, dynamic requirements enforced
- **SSE validation** — re-render only the form on errors, no full page reload
- **Datastar-powered** — reactive UI with minimal JavaScript

## How it works

1. You define reactive rules in Python on your form fields
2. rg.forms generates [Datastar](https://data-star.dev) attributes (`data-show`, `data-bind`, `data-computed`, etc.)
3. The frontend reacts instantly — no page reloads
4. On submit, the backend re-evaluates all rules for security

```python
from rg.forms import ReactiveForm, ReactiveChoiceField, ReactiveCharField

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])
    priority = ReactiveChoiceField(
        choices=[('low', 'Low'), ('high', 'High')],
        visible_when="$order_type == 'urgent'",
    )
```

The `priority` field only appears when the user selects "Urgent". On form submission, if `order_type` is not "urgent", the `priority` field is skipped during validation.

## Installation

```bash
pip install rg-forms
```

Add to your Django settings:

```python
INSTALLED_APPS = [
    # ...
    'rg.forms',
]
```

## Requirements

- Python 3.12+
- Django 5.0+
- [Datastar](https://data-star.dev) loaded on the frontend

## Next steps

- [Quick Start](quickstart.md) — build your first reactive form
- [Guide](guide/visibility.md) — learn all reactive features
- [Reference](reference/fields.md) — full API reference
