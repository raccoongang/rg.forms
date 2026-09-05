# ModelForms

`ReactiveModelForm` is `ReactiveForm` bound to a model instance.

```python
from django import forms
from rg.forms import ReactiveModelForm, ReactiveBooleanField, ReactiveCharField

class ProviderForm(ReactiveModelForm):
    enabled = ReactiveBooleanField(required=False)
    client_id = ReactiveCharField(required=False, visible_when="$enabled")
    token_url = ReactiveCharField(required=False, visible_when="$enabled")
    secret = ReactiveCharField(required=False, widget=forms.PasswordInput, visible_when="$enabled")

    class Meta:
        model = Provider
        fields = ["name", "enabled", "client_id", "token_url", "secret"]
```

Everything reactive comes from `ReactiveForm` — signals, `visible_when` /
`required_when`, computed fields, cascading choices, field groups — and
everything model-shaped comes from Django's `ModelForm`: `instance`, fields
generated from `Meta.model`, `_post_clean()`, `save()`. Views, templates and
template tags treat it exactly like any other reactive form.

## `Meta` carries both vocabularies

Django reads `model`, `fields`, `exclude`, `widgets`, `labels` and friends;
rg.forms reads `field_groups` and `external_signals`. Each ignores the other's
keys, so one `Meta` covers both:

```python
class Meta:
    model = Provider
    fields = ["name", "enabled", "client_id", "token_url", "secret"]
    field_groups = {
        "config": FieldGroup(
            fields=["client_id", "token_url", "secret"],
            label="OAuth configuration",
            visible_when="$enabled",
        ),
    }
```

A field declared on the class wins over the one Django would generate from the
model — which is how a model field acquires a `visible_when` in the first place.

## Hidden fields are not written to the instance

This is the one behavior that differs from a plain `ReactiveForm`, and it is the
reason to use `ReactiveModelForm` rather than compose the two base classes by
hand.

`ReactiveForm._clean_fields()` sets a hidden field's `cleaned_data` to `None`: a
hidden control still posts, and honoring what it posted would let a rule the
user cannot see decide the outcome. For a plain `Form` that is the whole story.
For a `ModelForm` it would not be — `_post_clean()` writes `cleaned_data` onto
the instance and `save()` persists it, so **collapsing a section would erase the
stored configuration it was only meant to hide**:

```python
# The admin unticks "enabled" and saves. Intent: keep the stored client id,
# endpoints and secret, just stop using them.
form = ProviderForm(data={"name": "id.gov.ua"}, instance=provider)
form.is_valid()
form.save()

provider.refresh_from_db()
provider.enabled      # False   — the change the admin made
provider.client_id    # 'stored-client'  — untouched
provider.secret       # 'stored-secret'  — untouched
```

`ReactiveModelForm._post_clean()` withholds the hidden field names from
`construct_instance()` for the duration of the call, so those model attributes
keep their stored values. The keys go back afterwards, so `cleaned_data` still
reads `None` for a hidden field exactly as it does on a plain `ReactiveForm`:

```python
form.cleaned_data["client_id"]   # None       — the form asserted nothing
form.instance.client_id          # 'stored-client'  — storage is unchanged
```

Withholding rather than restoring each field's `initial` is deliberate: it
writes nothing at all, so a form whose `initial` differs from what is stored (an
override in `__init__`, a value computed for display) cannot quietly push that
difference into the database. A write-only secret's "leave blank to keep the
stored value" path keeps working for the same reason.

Model-level validation still runs on the resulting instance, and a hidden field
is never validated against a `None` the form did not ask for. Whether it is
validated *at all* stays Django's call: `_get_validation_exclusions()` drops a
field whose model column is `blank=False` and whose form field is optional when
its cleaned value reads empty, which is exactly what withholding makes it. When
the field is not excluded, it is the stored value that gets checked.

!!! warning "Composing the base classes by hand does not get this"
    `class MyForm(ReactiveForm, forms.ModelForm)` produces a working reactive
    ModelForm in every other respect, which is what makes the data loss easy to
    miss. Use `ReactiveModelForm`.

## Asking what actually changed

Because a hidden control still submits, Django's `changed_data` reports edits
made *before* a section was collapsed — edits `_clean_fields()` then discards.
`visible_changed_data` is the same list with the hidden fields removed:

```python
form.changed_data          # ['enabled', 'client_id', 'token_url', 'secret']
form.visible_changed_data  # ['enabled']
```

Use it for "was anything actually saved?" A `PasswordInput` submits blank on
every render, so it always reads as changed; ask about it separately if that
matters.

`get_hidden_field_names()` exposes the underlying set if you need it directly.

## No flash of visible

A field or group whose rule is *already* false renders hidden on the server, so
a collapsed section does not paint into view and then vanish when Datastar
boots. See [Visibility Rules](visibility.md#initial-visibility).
