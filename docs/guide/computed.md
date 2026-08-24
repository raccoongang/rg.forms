# Computed Fields

Automatically calculate field values from other fields.

## Basic usage

```python
from rg.forms import ReactiveForm, ReactiveIntegerField, ReactiveDecimalField

class PriceCalculatorForm(ReactiveForm):
    quantity = ReactiveIntegerField(
        label="Quantity",
        min_value=1,
        initial=1,
    )
    unit_price = ReactiveDecimalField(
        label="Unit Price",
        min_value=0,
        decimal_places=2,
        initial="10.00",
    )
    total = ReactiveDecimalField(
        label="Total",
        computed="$quantity * $unit_price",
        required=False,
        decimal_places=2,
    )
```

## How it works

- **Frontend**: the field gets `data-computed="$quantity * $unit_price"` and `readonly` — Datastar evaluates the expression and updates the field value in real time
- **Backend**: on form submission, the server **recalculates** the computed value from the expression, ignoring whatever the client submitted. This prevents tampering

## Expression syntax

Computed expressions support arithmetic:

```python
# Multiplication
computed="$quantity * $unit_price"

# Addition
computed="$subtotal + $tax"

# Complex
computed="$quantity * $unit_price * (1 - $discount / 100)"
```

## Server-side recalculation

This is a key security feature. Even if a user manipulates the DOM to change a computed field's value, the backend recalculates it:

```python
def order_view(request):
    if request.method == 'POST':
        form = PriceCalculatorForm(request.POST)
        if form.is_valid():
            # form.cleaned_data['total'] is ALWAYS quantity * unit_price
            # regardless of what the client submitted
            total = form.cleaned_data['total']
```

## Display-only computed values

For computed values that are display-only (not form fields), use `data-text` directly in your template:

```html
<span data-text="$quantity * $unit_price"></span>
```

Or use `data-computed` to create a named signal:

```html
<div data-computed:total="$quantity * $unit_price"></div>
<p>Total: <span data-text="$total"></span></p>
```

## Compare: derived state vs a declared computed value

In React you derive a value with `watch()` + `useEffect` (or a `useMemo`) and
write it back into form state, then recompute (or trust the client) on the
server. In rg.forms `computed="$qty * $price"` is declared on the field: the
browser shows a live **preview**, and the server **recomputes the authoritative
value exactly** (with `Decimal`) during validation, ignoring any tampered
submission. See the order-configurator slice in the
[comparison](../comparison.md).
