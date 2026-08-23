# Bring Your Own Design System

rg.forms keeps **form metadata in Python** and treats **rendering as a swappable
concern**. The `rg_forms/*.html` templates the package ships are *reference
examples* (Bulma CSS) — they demonstrate the [context contract](../reference/template-tags.md#context-contract),
not a design system you are expected to keep. To adopt your host app's design
language, override one template.

## Presentational metadata in Python

You rarely need to hand-build a `widget=…` just to set a placeholder or
autocomplete hint. Reactive fields accept first-class presentational kwargs that
are merged into the widget's `attrs` and surfaced to the template as
`widget_attrs`:

```python
from rg.forms import ReactiveForm, ReactiveCharField, ReactiveEmailField

class ContactForm(ReactiveForm):
    full_name = ReactiveCharField(
        placeholder="Jane Doe",
        autocomplete="name",
        autofocus=True,
    )
    email = ReactiveEmailField(
        placeholder="jane@example.com",
        autocomplete="email",
    )
```

Precedence: an explicit kwarg (`placeholder="…"`) overrides the same key set via
`widget=forms.TextInput(attrs={...})`. Managed attributes (`id`, `name`,
`required`, `disabled`, `readonly`, `min`, `max`, `maxlength`, `minlength`) are
computed by the library and are **not** part of `widget_attrs`, so your template
can spread `widget_attrs` without double-rendering them.

## Overriding `rg_forms/field.html`

Django resolves `rg_forms/field.html` from your project's template dirs before
the one shipped by rg.forms. Create `templates/rg_forms/field.html` in a
directory that appears **earlier** in `TEMPLATES['DIRS']` (or in an app listed
before `rg.forms` in `INSTALLED_APPS`).

The overriding template receives the full [context contract](../reference/template-tags.md#context-contract).
A clean override is a *thin dispatcher* on `widget_type` that forwards the
context to your own components:

```html
{# templates/rg_forms/field.html — dispatches to host design-system components #}
{% if field.is_hidden %}
{{ field }}
{% elif widget_type == 'select' %}
    {% include "myui/fields/select.html" %}
{% elif widget_type == 'checkboxinput' %}
    {% include "myui/fields/checkbox.html" %}
{% elif widget_type == 'textarea' %}
    {% include "myui/fields/textarea.html" %}
{% else %}
    {% include "myui/fields/input.html" %}
{% endif %}
```

A host input component then reads the contract keys directly:

```html
{# templates/myui/fields/input.html #}
<div class="my-field"{% if visible_when %} data-show="{{ visible_when }}"{% endif %}>
    <label class="my-field__label" for="{{ field.id_for_label }}">
        {{ label }}{% if is_required %} <span class="my-field__req">*</span>{% endif %}
    </label>
    <input class="my-field__input{% if errors %} my-field__input--error{% endif %}"
           type="{{ input_type }}"
           name="{{ field.html_name }}"
           id="{{ field.id_for_label }}"
           data-bind:{{ field_name }}
           {% if disabled_when %}data-attr:disabled="{{ disabled_when }}"{% endif %}
           {% if read_only_when %}data-attr:readonly="{{ read_only_when }}"{% endif %}
           {% for attr, val in widget_attrs.items %}{{ attr }}="{{ val }}" {% endfor %}
           {% if required_expr %}data-attr:required="{{ required_expr }}"{% elif is_required %}required{% endif %}
           value="{{ formatted_value|default:'' }}">
    {% if errors %}<p class="my-field__error">{{ errors.0 }}</p>{% endif %}
</div>
```

Key points that keep the override correct and portable:

- **`input_type`, not `widget_type`, goes on the element.** `input_type` already
  maps `datetimeinput → "datetime-local"`, `emailinput → "email"`, etc. Deriving
  it yourself from `widget_type` is fragile (`datetimeinput` naively becomes
  `"datetime"`).
- **`formatted_value`, not `field.value`, for the rendered value.** It is the
  widget-formatted string the input expects (e.g. `YYYY-MM-DDTHH:MM` for
  `datetime-local`, localized numbers). `field.value` is the raw Python value and
  will mis-render dates/times and localized values.
- **`field.html_name` / `field.id_for_label` for `name` / `id`.** These are
  formset-safe. `field_name` is the *unprefixed* name — use it only for the
  Datastar signal (`data-bind:{{ field_name }}`).
- **Spread `widget_attrs`** to forward placeholder/autocomplete/`data-*` declared
  in Python.
- **Prefer the reactive `*_expr` bindings over static attributes.** Use
  `data-attr:required="{{ required_expr }}"` (falling back to a static `required`
  only when `required_expr` is empty), and likewise `placeholder_expr`,
  `min_expr`, `max_expr` for `data-attr:placeholder` / `min` / `max`. This keeps
  the browser's native validation in step with the field's visibility and
  conditions — a field hidden by `visible_when` will not block submission.

## Feature parity: where each rule is enforced

rg.forms is backend-authoritative, but not every rule is enforced in all three
layers. The table states, per feature, whether it acts in the **browser**
(native HTML), via **Datastar** (client reactivity), and in **server**
validation. Use it to avoid assuming a client-only rule is also enforced on
submit.

| Feature | Browser (native) | Datastar (client) | Server validation |
|---|:---:|:---:|:---:|
| `visible_when` | — | `data-show` | yes — hidden fields skipped in `clean` |
| static `required` | yes (reactive w/ visibility) | via `required_expr` when hideable | yes |
| `required_when` | — | `data-attr:required` | yes — enforced in `clean` |
| `computed` | — | `data-text` / `data-computed` | yes — recomputed in `clean` |
| `disabled_when` | — | `data-attr:disabled` | **no** dynamic parity |
| `read_only_when` | — | `data-attr:readonly` | **no** dynamic parity |
| `placeholder_when` | — | `data-attr:placeholder` | n/a (presentational) |
| static `min` / `max` | yes | — | yes (Django field validators) |
| `min_when` / `max_when` | — | `data-attr:min` / `max` | **no** — Django validates static bounds only |

The gaps (`disabled_when`, `read_only_when`, `min_when`, `max_when` server-side)
are deliberate for now: a disabled/read-only control still round-trips its value,
and dynamic bounds are not yet evaluated during `clean`. Do not rely on them as a
security boundary — enforce anything authoritative with a `clean_<field>` /
`clean()` method or a static validator.

## Formsets

Because the override uses `field.html_name` and `field.id_for_label`, the tag
works inside a Django formset — each row renders prefixed, non-colliding names
(`form-0-role`, `form-1-role`) that round-trip a POST:

```html
{% load reactive_forms %}
<form method="post">
    {% csrf_token %}
    {{ formset.management_form }}
    {% for f in formset.forms %}
        <fieldset>
            {% render_reactive_field f.role %}
            {% render_reactive_field f.email %}
        </fieldset>
    {% endfor %}
    <button type="submit">Save</button>
</form>
```

Each rendered field carries its prefixed `name`/`id`, so the view's
`formset.is_valid()` binds the POST back to the right row with no extra work.
