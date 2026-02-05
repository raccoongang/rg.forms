# Cascading Dropdowns

Build dependent dropdowns declaratively — no `__init__` override needed.

## Basic example

```python
from rg.forms import ReactiveForm, ReactiveChoiceField, ReactiveIntegerField

def get_categories():
    return Category.objects.all()

def get_products_for_category(category_id):
    return Product.objects.filter(category_id=category_id)

class OrderForm(ReactiveForm):
    category = ReactiveChoiceField(
        label="Category",
        choices_from=get_categories,
        value_field="id",
        label_field="name",
        empty_choice="-- Select Category --",
    )

    product = ReactiveChoiceField(
        label="Product",
        choices_from=get_products_for_category,
        depends_on=["category"],
        value_field="id",
        label_field="name",
        empty_choice="-- Select Product --",
        empty_choice_no_parent="-- Select Category First --",
    )
```

## How it works

1. **Root fields** (`choices_from` without `depends_on`): `choices_from()` is called with no arguments
2. **Dependent fields** (`choices_from` + `depends_on`): `choices_from(parent_value)` is called with the parent's current value
3. When the parent has no value, the dependent field shows `empty_choice_no_parent`
4. When the parent value changes, the form is re-rendered server-side and the dependent field's choices update

## Choice field attributes

| Attribute                | Description                               | Default    |
|--------------------------|-------------------------------------------|------------|
| `choices_from`           | Callable returning objects for choices    | `None`     |
| `depends_on`             | List of parent field names                | `[]`       |
| `value_field`            | Attribute name for option value           | `"pk"`     |
| `label_field`            | Attribute name for option label           | `str(obj)` |
| `label_template`         | Format string, e.g. `"{name} (${price})"` | `None`     |
| `empty_choice`           | Label for empty option                    | `None`     |
| `empty_choice_no_parent` | Label when parent not selected            | `None`     |

## Data sources

`choices_from` works with any iterable of objects or dicts:

=== "QuerySet"

    ```python
    def get_categories():
        return Category.objects.all()
    ```

=== "List of dicts"

    ```python
    def get_categories():
        return [
            {"id": 1, "name": "Electronics"},
            {"id": 2, "name": "Clothing"},
        ]
    ```

=== "List of objects"

    ```python
    def get_categories():
        return [
            SimpleNamespace(id=1, name="Electronics"),
            SimpleNamespace(id=2, name="Clothing"),
        ]
    ```

## Label templates

Use `label_template` to format labels with multiple fields:

```python
product = ReactiveChoiceField(
    choices_from=get_products_for_category,
    depends_on=["category"],
    value_field="id",
    label_template="{name} (${price})",  # "Laptop ($999.99)"
)
```

## Server-side re-rendering with Datastar

To update dependent choices when the parent changes, use Datastar's `@post` with SSE:

```html
<select data-bind:category
        data-on:change="@post('/order/update/', {contentType: 'form'})">
    ...
</select>
```

In the view, re-instantiate the form with new data and return the updated fragment:

```python
from datastar_py.django import DatastarResponse

def order_update(request):
    form = OrderForm(request.POST)
    response = DatastarResponse()
    response.merge_fragments(
        render_to_string('_order_fragment.html', {'form': form}, request)
    )
    return response
```

## `populate()` method

For cases where you need to set choices in `__init__` (e.g., based on the request user), use `populate()`:

```python
class OrderForm(ReactiveForm):
    item = ReactiveChoiceField(label="Item")

    def __init__(self, supplier=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if supplier:
            self.populate(
                'item',
                Item.objects.filter(supplier=supplier),
                label_field='name',
                add_empty=True,
            )
```

`populate()` parameters:

| Parameter     | Description                 | Default          |
|---------------|-----------------------------|------------------|
| `field_name`  | Name of the ChoiceField     | required         |
| `queryset`    | QuerySet or iterable        | required         |
| `label_field` | Attribute for display label | `str(obj)`       |
| `value_field` | Attribute for option value  | `"pk"`           |
| `add_empty`   | Prepend an empty option     | `False`          |
| `empty_label` | Label for empty option      | `"-- Select --"` |
| `empty_value` | Value for empty option      | `""`             |
