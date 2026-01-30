# CLAUDE.md - rg.forms

## Project Overview

**rg.forms** is a Django package providing reactive forms with Datastar integration. It enables:
- Declarative field visibility (`visible_when`)
- Dynamic field requirements (`required_when`)
- Computed fields with automatic updates
- Remote data fetching with dependencies
- Cross-field validation with visibility awareness
- Multi-framework skin support (Bootstrap, Bulma, Tailwind, Carbon)

## Tech Stack

- **Python**: 3.12+
- **Django**: 5.0+
- **Package Manager**: uv
- **Core Dependencies**: django (>=5.0)
- **Frontend**: Datastar (https://data-star.dev)
- **Testing**: pytest, pytest-django
- **Linting/Formatting**: ruff
- **Type Checking**: mypy with django-stubs

## Package Structure

This is a **PEP 420 namespace package** under the `rg` namespace:

```
src/
└── rg/                     # NO __init__.py (namespace package)
    └── forms/
        ├── __init__.py     # Package exports
        ├── apps.py         # Django app config
        ├── forms.py        # ReactiveForm base class
        ├── fields.py       # Reactive field classes
        ├── py.typed        # PEP 561 marker
        └── (future modules)
```

**IMPORTANT**: The `src/rg/` directory must NOT contain `__init__.py` for namespace packages to work correctly with other `rg.*` packages.

## Key Classes and APIs

### ReactiveForm (forms.py)
Base form class extending `django.forms.Form`:
```python
from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])
    priority = ReactiveChoiceField(
        choices=[('low', 'Low'), ('high', 'High')],
        visible_when="$order_type == 'urgent'"
    )
```

### Reactive Fields (fields.py)
All standard Django fields have reactive versions:
- `ReactiveCharField`, `ReactiveIntegerField`, `ReactiveFloatField`
- `ReactiveChoiceField`, `ReactiveMultipleChoiceField`
- `ReactiveBooleanField`, `ReactiveEmailField`, `ReactiveURLField`
- `ReactiveDateField`, `ReactiveDateTimeField`, `ReactiveTimeField`
- `ReactiveDecimalField`

### Field Attributes
- `visible_when`: Datastar expression for visibility
- `required_when`: Expression for dynamic requirement
- `computed`: Expression for computed values
- `depends_on`: List of field names this field depends on

## Development Commands

```bash
# Setup
cd /home/oleksii/dev/rg.forms
uv venv && source .venv/bin/activate
uv pip install -e ".[all]"

# Testing
pytest
pytest --cov=src/rg/forms

# Linting
ruff check src/ tests/
ruff format src/ tests/

# Type checking
mypy src/

# Build
uv build
```

## Django Settings Integration

Add to INSTALLED_APPS:
```python
INSTALLED_APPS = [
    # ...
    'rg.forms',
]
```

## Conventions

- Use type hints everywhere (strict mypy)
- Follow ruff formatting/linting rules
- Signal names match field names in snake_case: `$order_type`
- Import from package root: `from rg.forms import ReactiveForm`
- All reactive logic lives in form class, not views (FBV-friendly)

## Architecture Notes

- **Backend is source of truth**: All rules defined in Python, frontend reflects them
- **Datastar-first**: We use Datastar, no abstraction layer for other frameworks
- **JavaScript required**: No progressive enhancement / fallback for disabled JS
- **View-agnostic**: Works with both FBVs and CBVs, no special view classes required

## Datastar Syntax Reference

**IMPORTANT**: Datastar syntax rules for generating attributes:

### Signal References
- Use `$fieldname` only in **expressions** (data-show, data-text, data-computed)
- Example: `data-show="$order_type == 'urgent'"`

### data-bind (Two-way binding)
- Use `data-bind:fieldname` (key-based, preferred) or `data-bind="fieldname"`
- **NO $ prefix** - the signal name is the field name directly
- Example: `<input data-bind:order_type>` or `<input data-bind="order_type">`

### data-signals (Initial values)
- JSON object with field names as keys (no $ prefix)
- **IMPORTANT**: Use single quotes for the HTML attribute (JSON uses double quotes)
- Example: `data-signals='{"order_type": "standard", "quantity": 1}'`
- In templates: `<form data-signals='{% reactive_signals form %}'>`

### data-show (Visibility)
- Expression with $ prefix for signal references
- Example: `data-show="$order_type == 'urgent'"`

### data-text (Computed display)
- Expression with $ prefix for signal references
- **Use on non-input elements** (span, div, p) - NOT on inputs
- Example: `<span data-text="$quantity * $unit_price"></span>`

### data-computed (Create computed signal)
- Creates a read-only signal from an expression
- Syntax: `data-computed:signalname="expression"`
- Example: `<div data-computed:total="$quantity * $price"></div>`
- Then use: `<span data-text="$total"></span>`

### data-on (Event handlers)
- Attaches event listeners to elements
- Syntax: `data-on:eventname="expression"`
- Use `@action()` syntax to call backend actions
- Example: `<select data-on:change="@post('/update/')">`
- Example: `<button data-on:click="@get('/refresh/')">`
- Modifiers: `__debounce.500ms`, `__throttle.1s`, `__once`, `__prevent`, `__stop`
- Example with debounce: `<input data-on:input__debounce.300ms="@post('/search/')">`

### @post / @get actions
- By default sends JSON body
- **For Django forms with CSRF**: use `contentType: 'form'` to send as form data
- Example: `@post('/update/', {contentType: 'form'})`
- This includes the CSRF token from the form's `{% csrf_token %}`

### Common Mistakes to Avoid
```html
<!-- WRONG: $ in data-bind -->
<input data-bind="$order_type">

<!-- CORRECT: no $ in data-bind -->
<input data-bind:order_type>
<input data-bind="order_type">

<!-- CORRECT: $ in expressions -->
<div data-show="$order_type == 'urgent'">

<!-- WRONG: @change shorthand doesn't exist -->
<select @change="@post('/update/')">

<!-- CORRECT: use data-on:change -->
<select data-on:change="@post('/update/')">
```

Reference: https://data-star.dev/reference/attributes

## Related Projects

- `rg.table4`: Reactive tables with django-tables2 and Datastar
- `rg.forms-testsite`: Django project with usage examples
