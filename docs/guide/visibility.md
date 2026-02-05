# Visibility Rules

Control when fields are shown and when they're required.

## `visible_when`

Makes a field conditionally visible. The expression is evaluated client-side by Datastar and server-side during validation.

```python
from rg.forms import ReactiveForm, ReactiveChoiceField, ReactiveCharField

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])

    # Only visible when order_type is 'urgent'
    priority = ReactiveChoiceField(
        choices=[('normal', 'Normal'), ('high', 'High')],
        visible_when="$order_type == 'urgent'",
    )
```

**How it works:**

- **Frontend**: generates `data-show="$order_type == 'urgent'"` — Datastar hides/shows the field wrapper
- **Backend**: during `_clean_fields()`, the expression is evaluated. If the field is not visible, it's set to `None` in `cleaned_data` and validation is skipped — even if the field has `required=True`

### Expression syntax

Expressions use Datastar syntax with `$` prefix for signal references:

```python
# Equality
visible_when="$order_type == 'urgent'"

# Not equal
visible_when="$order_type != 'standard'"

# Multiple conditions (OR)
visible_when="$order_type == 'urgent' || $order_type == 'bulk'"

# Multiple conditions (AND)
visible_when="$order_type == 'urgent' && $quantity > 10"

# Comparison operators
visible_when="$quantity > 100"
visible_when="$amount >= 1000"
```

## `required_when`

Makes a field conditionally required. Unlike `visible_when`, the field stays visible — only its requirement changes.

```python
class ContactForm(ReactiveForm):
    contact_method = ReactiveChoiceField(choices=[
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('both', 'Both'),
    ])

    email = ReactiveEmailField(
        required=False,  # Not statically required
        required_when="$contact_method == 'email' || $contact_method == 'both'",
    )

    phone = ReactiveCharField(
        required=False,
        required_when="$contact_method == 'phone' || $contact_method == 'both'",
    )
```

**Backend behavior**: during validation, if `required_when` evaluates to true and the field is empty, a `ValidationError` with code `"required"` is raised.

## Combining `visible_when` and `required_when`

A common pattern — show a field and make it required at the same time:

```python
bulk_discount_code = ReactiveCharField(
    required=False,
    visible_when="$order_type == 'bulk'",
    required_when="$order_type == 'bulk'",
)
```

!!! note
    If a field is hidden (`visible_when` is false), it's skipped during validation regardless of `required_when`. Visibility takes precedence.

## Server-side evaluation

All expressions are evaluated on the backend during form validation. This means:

1. **Hidden fields are safe** — even if a malicious user submits data for a hidden field, it's set to `None`
2. **Required rules are enforced** — client-side required indicators are cosmetic, the backend is the authority
3. **No client-side bypassing** — JavaScript disabled? The backend still validates correctly
