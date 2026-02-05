# Quick Start

Build a reactive order form in 5 minutes.

## 1. Define the form

```python
# forms.py
from rg.forms import (
    ReactiveForm,
    ReactiveChoiceField,
    ReactiveCharField,
    ReactiveIntegerField,
    ReactiveDecimalField,
)

class OrderForm(ReactiveForm):
    order_type = ReactiveChoiceField(
        label="Order Type",
        choices=[
            ('', '-- Select --'),
            ('standard', 'Standard'),
            ('urgent', 'Urgent'),
            ('bulk', 'Bulk'),
        ],
    )

    # Only shown for urgent orders
    priority = ReactiveChoiceField(
        label="Priority",
        choices=[('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical')],
        visible_when="$order_type == 'urgent'",
        required=False,
    )

    # Only shown for bulk orders
    quantity = ReactiveIntegerField(
        label="Bulk Quantity",
        visible_when="$order_type == 'bulk'",
        required=False,
        min_value=10,
    )

    unit_price = ReactiveDecimalField(
        label="Unit Price",
        min_value=0,
        decimal_places=2,
        initial="10.00",
    )
```

## 2. Write the view

Standard Django FBV — nothing special required:

```python
# views.py
from django.shortcuts import render
from .forms import OrderForm

def order_view(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Hidden fields are automatically excluded from cleaned_data
            return render(request, 'success.html', {'data': form.cleaned_data})
    else:
        form = OrderForm()
    return render(request, 'order.html', {'form': form})
```

## 3. Create the template

Load Datastar and use the provided template tags:

```html
{% load reactive_forms %}
<!DOCTYPE html>
<html>
<head>
    <script src="https://cdn.jsdelivr.net/npm/@starfederation/datastar"></script>
</head>
<body>
    <form method="post" data-signals='{% reactive_signals form %}'>
        {% csrf_token %}
        {% render_reactive_form form %}
    </form>
</body>
</html>
```

That's it. The `priority` field appears only when "Urgent" is selected. The `quantity` field appears only for "Bulk". On submit, hidden fields are skipped in validation.

## What happened?

- **`{% reactive_signals form %}`** generates initial signal values as JSON for Datastar
- **`{% render_reactive_form form %}`** renders all fields with proper `data-bind`, `data-show`, and `data-computed` attributes
- **`visible_when="$order_type == 'urgent'"`** becomes `data-show="$order_type == 'urgent'"` on the field wrapper
- On the backend, `ReactiveForm._clean_fields()` evaluates `visible_when` and skips hidden fields

## Manual rendering

For more control, render fields individually:

```html
{% load reactive_forms %}

<form method="post" data-signals='{% reactive_signals form %}'>
    {% csrf_token %}

    <div class="field">
        <label>{{ form.order_type.label }}</label>
        <select {% reactive_input_attrs form.order_type %}>
            {% for value, label in form.order_type.field.choices %}
                <option value="{{ value }}">{{ label }}</option>
            {% endfor %}
        </select>
    </div>

    <div class="field" {% reactive_wrapper_attrs form.priority %}>
        <label>{{ form.priority.label }}</label>
        <select {% reactive_input_attrs form.priority %}>
            {% for value, label in form.priority.field.choices %}
                <option value="{{ value }}">{{ label }}</option>
            {% endfor %}
        </select>
    </div>
</form>
```

- **`{% reactive_wrapper_attrs form.priority %}`** adds `data-show="$order_type == 'urgent'"` to the wrapper div
- **`{% reactive_input_attrs form.priority %}`** adds `data-bind:priority` to the input

## Next steps

- [Visibility rules](guide/visibility.md) — `visible_when` and `required_when` in depth
- [Computed fields](guide/computed.md) — automatic calculations
- [Cascading dropdowns](guide/cascading.md) — dependent field choices
