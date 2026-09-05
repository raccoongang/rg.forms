# ReactiveForm Reference

`ReactiveForm` extends `django.forms.Form` with reactive capabilities.

## Class

```python
from rg.forms import ReactiveForm
```

Inherits all standard Django form behavior — `is_valid()`, `cleaned_data`, `errors`, custom `clean()` methods, widgets, etc.

### `ReactiveModelForm`

```python
from rg.forms import ReactiveModelForm
```

The same reactive behavior on top of `django.forms.ModelForm` — `instance`,
fields generated from `Meta.model`/`Meta.fields`, `_post_clean()` and `save()`.
Every method below applies to it too. See the
[ModelForms guide](../guide/modelforms.md) for the one behavior that differs:
a hidden field is **not** written onto the model instance.

## View Utilities

### `reactive_form_response(request, form, fragment_template, *, success_url=None, on_success=None, context=None)`

Handles form POST with SSE support. Returns an SSE patch on validation errors (Datastar request) or a redirect on success.

```python
from rg.forms import reactive_form_response

def my_view(request):
    if request.method == "POST":
        form = MyForm(request.POST)
        response = reactive_form_response(
            request, form, "_fragment.html",
            success_url="/done/",
            context={"action_url": request.build_absolute_uri()},
        )
        if response:
            return response
    else:
        form = MyForm()
    return render(request, "page.html", {"form": form})
```

**Returns**: `HttpResponseRedirect | DatastarResponse | None`

| Scenario | Datastar request | Regular request |
|----------|-----------------|-----------------|
| Valid form | SSE redirect to `success_url` | `HttpResponseRedirect` |
| Invalid form | SSE patch with re-rendered fragment | `None` (view renders full page) |

See the [SSE Validation guide](../guide/sse-validation.md) for full details.

## Methods

### `get_signals() -> dict`

Returns a dict of initial signal values for Datastar. Values come from (in priority order): bound data, initial data, field initial, or empty string.

```python
form = OrderForm(initial={'quantity': 5})
form.get_signals()
# {'order_type': '', 'quantity': 5, 'unit_price': ''}
```

`get_signals()` is the **server-side** canonical dict: it is what `visible_when` / `required_when` are evaluated
against, and it always holds the real submitted value. Use `get_client_signals()` for anything the browser will see.

### `get_client_signals() -> dict`

The same dict, minus values a widget refuses to round-trip. A field whose widget sets `render_value = False` — Django's
default for `PasswordInput` — is seeded with its canonical empty value instead of the submitted secret:

```python
form = LoginForm(data={'username': 'bob', 'password': 's3cret'})
form.get_client_signals()
# {'username': 'bob', 'password': ''}
form.get_signals()
# {'username': 'bob', 'password': 's3cret'}
```

The divergence is deliberate. Django enforces the password suppression in `Widget.get_context()`, which the reactive
render path never calls, so without it a bound form would serialise the secret into the `data-signals` attribute and
`data-bind` would restore it into the input. Server-side rule evaluation keeps the real value, because gating on
whether a secret was supplied (`required_when="$password"` on a dependent field) is a legitimate pattern that blanking
would silently disable.

The consequence on the client is intended: after a validation-error re-render the password signal reads empty until the
user retypes, exactly as on a fresh page load. `PasswordInput(render_value=True)` is Django's explicit opt-in and keeps
round-tripping.

### `get_seed_signals() -> dict`

`get_client_signals()` in the shape the client binds to — flat for an unprefixed form, nested under
`rgForms.<scope>` for a prefixed one (see [ADR-0003](../adr/0003-scoped-signals-and-reactive-formsets.md)).

### `get_signals_json() -> str`

Returns `get_seed_signals()` as a JSON string, ready for `data-signals`:

```html
<form data-signals='{% reactive_signals form %}'>
```

### `get_field_reactive_attrs(field_name: str) -> dict`

Returns reactive attributes for a field (only non-None values):

```python
form.get_field_reactive_attrs('priority')
# {'visible_when': "$order_type == 'urgent'"}
```

### `is_field_visible(field_name: str) -> bool`

Server-side evaluation of `visible_when`. Returns `True` if:

- The field has no `visible_when`, or
- The expression evaluates to `True`

Returns `True` on evaluation error (fail-open).

### `is_field_required(field_name: str) -> bool`

Server-side evaluation of requirement. Returns `True` if:

- `field.required` is `True`, or
- `required_when` evaluates to `True`

### `get_hidden_field_names() -> set[str]`

Names of the fields whose `visible_when` currently evaluates false — the same
predicate `_clean_fields()` uses to decide what to skip, exposed so callers do
not re-derive it. Stateless: it answers before validation as well as after, and
for unbound forms as well as bound ones.

Unrelated to Django's `hidden_fields()`, which means widgets rendered as
`<input type="hidden">`.

```python
form = ProviderForm(data={"name": "id.gov.ua"})     # "enabled" unticked
form.get_hidden_field_names()
# {'client_id', 'token_url', 'secret'}
```

### `visible_changed_data -> list[str]`

Django's `changed_data`, minus what the form is hiding.

A hidden field's control is still in the DOM and still submits, so
`changed_data` reports edits the user made *before* a section collapsed — edits
`_clean_fields()` then discards. That makes plain `changed_data` the wrong input
to "did this submission actually change anything?".

```python
form.changed_data
# ['enabled', 'client_id', 'token_url', 'secret']
form.visible_changed_data
# ['enabled']
```

A write-only field (`PasswordInput`) submits blank on every render, so it always
reads as changed; ask about it separately if that matters.

### `get_computed_value(field_name: str)`

Evaluates a computed field's expression and returns the result.

### `get_visible_fields() -> list[str]`

Returns names of fields that have `visible_when` set.

### `get_computed_fields() -> list[str]`

Returns names of fields that have `computed` set.

### `populate(field_name, queryset, ...)`

Populate a ChoiceField's choices from a queryset. See [Cascading Dropdowns](../guide/cascading.md#populate-method).

## Field Group Methods

### `get_field_groups() -> dict[str, FieldGroup]`

Returns all field groups from `Meta.field_groups`.

### `get_group(group_name: str) -> FieldGroup | None`

Returns a specific field group.

### `get_fields_in_group(group_name: str) -> list[tuple[str, BoundField]]`

Returns `(name, bound_field)` tuples for fields in a group.

### `is_group_visible(group_name: str) -> bool`

Server-side evaluation of group's `visible_when`.

## Validation behavior

`ReactiveForm` overrides `_clean_fields()`:

1. Hidden fields (`visible_when` is `False`) are set to `None` — no validation.
   A hidden control still posts, and honoring what it posted would let a rule
   the user cannot see decide the outcome. Under
   [`ReactiveModelForm`](../guide/modelforms.md) that `None` is *not* written to
   the model instance.
2. Computed fields are recalculated from their expression
3. `required_when` is evaluated and enforced
4. Standard Django `clean_<fieldname>()` runs for visible fields
5. Standard Django `clean()` runs for cross-field validation

## Meta options

```python
class MyForm(ReactiveForm):
    # ... fields ...

    class Meta:
        field_groups = {
            'group_name': FieldGroup(
                fields=['field1', 'field2'],
                label='Group Label',
                visible_when="$some_field == 'value'",
                description='Optional description',
                css_class='custom-class',
            ),
        }
```
