# Field Groups

Organize fields into logical sections with shared visibility and styling.

## Defining groups

Use `Meta.field_groups` to define groups:

```python
from rg.forms import ReactiveForm, ReactiveChoiceField, ReactiveCharField, ReactiveEmailField, FieldGroup

class RegistrationForm(ReactiveForm):
    account_type = ReactiveChoiceField(choices=[
        ('', '-- Select --'),
        ('personal', 'Personal'),
        ('business', 'Business'),
    ])

    first_name = ReactiveCharField()
    last_name = ReactiveCharField()
    email = ReactiveEmailField()

    company_name = ReactiveCharField()
    company_size = ReactiveChoiceField(choices=[
        ('1-10', '1-10'), ('11-50', '11-50'), ('51-200', '51-200'),
    ])
    tax_id = ReactiveCharField(required=False)

    class Meta:
        field_groups = {
            'personal': FieldGroup(
                fields=['first_name', 'last_name', 'email'],
                label='Personal Information',
            ),
            'business': FieldGroup(
                fields=['company_name', 'company_size', 'tax_id'],
                label='Business Information',
                description='Required for business accounts.',
                visible_when="$account_type == 'business'",
            ),
        }
```

When `account_type` is "personal", the entire business group is hidden.

## `FieldGroup` attributes

| Attribute      | Type          | Description                                  |
|----------------|---------------|----------------------------------------------|
| `fields`       | `list[str]`   | Field names in this group                    |
| `label`        | `str \| None` | Display label for the group header           |
| `visible_when` | `str \| None` | Datastar expression for group visibility     |
| `description`  | `str \| None` | Help text shown below the group header       |
| `css_class`    | `str \| None` | Additional CSS class for the group container |

## Rendering groups

Use the `{% render_field_group %}` template tag:

```html
{% load reactive_forms %}

<form method="post" data-signals='{% reactive_signals form %}'>
    {% csrf_token %}

    {% render_field_group form "personal" %}
    {% render_field_group form "business" %}

    <button type="submit">Register</button>
</form>
```

The tag renders the group container with `data-show` if `visible_when` is set, a header with the label, and all fields in the group.

## Programmatic access

```python
form = RegistrationForm()

# Get all groups
groups = form.get_field_groups()  # dict[str, FieldGroup]

# Get a specific group
group = form.get_group('business')  # FieldGroup | None

# Get bound fields in a group
fields = form.get_fields_in_group('business')  # list[(name, BoundField)]

# Check visibility (server-side evaluation)
is_visible = form.is_group_visible('business')  # bool
```

## Groups and validation

Group `visible_when` works like field-level `visible_when`:

- If a group is hidden, all its fields are skipped during validation
- `is_group_visible()` evaluates the expression server-side using form data
