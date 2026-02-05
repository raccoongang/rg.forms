# Validation

rg.forms extends Django's form validation to respect reactive rules.

## How validation works

`ReactiveForm` overrides `_clean_fields()` to add three behaviors:

1. **Hidden fields are skipped** — if `visible_when` evaluates to `False`, the field is set to `None` in `cleaned_data` and no validation runs
2. **Dynamic requirements are enforced** — if `required_when` evaluates to `True` and the field is empty, a `ValidationError` is raised
3. **Computed values are recalculated** — the server ignores the submitted value and recomputes from the expression

## Visibility skipping

```python
class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(choices=[
        ('standard', 'Standard'),
        ('urgent', 'Urgent'),
    ])
    priority = ReactiveChoiceField(
        choices=[('high', 'High'), ('critical', 'Critical')],
        visible_when="$order_type == 'urgent'",
        required=True,  # Required, but only when visible
    )
```

If `order_type` is "standard":

- `priority` is not visible
- `cleaned_data['priority']` is `None`
- No validation error, even though `required=True`

## Dynamic requirements

```python
class ContactForm(ReactiveForm):
    method = ReactiveChoiceField(choices=[('email', 'Email'), ('phone', 'Phone')])
    email = ReactiveEmailField(
        required=False,
        required_when="$method == 'email'",
    )
```

If `method` is "email" and `email` is empty:

- `required_when` evaluates to `True`
- A `ValidationError` with code `"required"` is raised

## Computed recalculation

```python
class PriceForm(ReactiveForm):
    quantity = ReactiveIntegerField(initial=1)
    price = ReactiveDecimalField(initial="10.00")
    total = ReactiveDecimalField(
        computed="$quantity * $price",
        required=False,
    )
```

On submit, even if the client sends `total=999999`, the backend recalculates:

```python
form.cleaned_data['total']  # Always quantity * price
```

## Custom validation

Standard Django `clean_<fieldname>()` and `clean()` methods work as expected:

```python
class OrderForm(ReactiveForm):
    # ... fields ...

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty and qty > 10000:
            raise ValidationError("Maximum 10,000 units per order.")
        return qty

    def clean(self):
        cleaned_data = super().clean()
        # Cross-field validation here
        return cleaned_data
```

!!! note
    `clean_<fieldname>()` is only called for visible fields. If a field is hidden by `visible_when`, its clean method is skipped.

## Validation order

1. For each field (in declaration order):
    1. Check `visible_when` — skip if hidden
    2. Run `field.clean()` (Django's standard field validation)
    3. If `computed`, recalculate and override the value
    4. Check `required_when` — raise if required and empty
    5. Call `clean_<fieldname>()` if it exists
2. Call `clean()` for cross-field validation
