# Incremental server validation

Some rules can only be checked on the server — "is this username taken?", "is
this coupon valid?", VAT/format lookups, cross-field rules that need database
state. rg.forms lets you validate a **single field early** (as the user leaves
it or types) with ordinary Django validation returned over SSE — no client-side
validation engine, no bespoke wiring per field (ADR-0004).

## Declaring the trigger

Add `validate_on` to any reactive field:

```python
from rg.forms import ReactiveForm, ReactiveCharField

class SignupForm(ReactiveForm):
    username = ReactiveCharField(validate_on="blur")
    coupon = ReactiveCharField(required=False, validate_on="change", debounce=400)

    def clean_username(self):
        value = self.cleaned_data["username"]
        if User.objects.filter(username=value).exists():
            raise forms.ValidationError("That username is taken.")
        return value
```

- `validate_on`: `"blur"` (validate when the field loses focus) or `"change"`.
- `debounce`: milliseconds to wait for `"change"` (ignored for `"blur"`).
- Unset → submit-only validation (today's behavior; nothing changes).

## Wiring the view

Point the template at a validation URL and add a view:

```html
{% render_reactive_form form action="/signup/" validate_action="/validate/" %}
```

```python
from rg.forms import reactive_validate

def validate(request):
    return reactive_validate(request, SignupForm)
```

That is the whole server side. `reactive_validate`:

1. reads the canonical Datastar signals from the request (ADR-0002);
2. adapts them into Django form data for this form's scope (arrays, booleans,
   null, scoped/formset paths) — dropping external and reserved signals;
3. runs the **whole form's** `is_valid()` (exact final-submit semantics, so
   cross-field rules run for free);
4. patches back **only the triggered field's** fragment over SSE.

The view is a normal, **CSRF-protected** Django view. The generated request
sends the token as an `X-CSRFToken` header; do not use `csrf_exempt`.

## What happens on the client

The renderer emits, for each `validate_on` field:

- a `data-on:blur` / `data-on:change__debounce.<n>ms` handler that fires a
  **JSON-signal** request (not `contentType: 'form'`, which would send no
  signals and be blocked by native form validity on a partially-filled form);
- a per-field URL discriminator `?__rg_field=<path>` so Datastar's method+URL
  cancellation cancels a stale check for the *same* field while letting
  *different* fields validate concurrently;
- an `X-RG-Validate-Field` header carrying the field path (verified server-side —
  the field must exist, have `validate_on`, and its scope must belong to the form);
- a native `data-indicator` pending signal `_rgForms.…validating.<field>` you can
  bind a spinner to (the leading `_` keeps it local, never sent to the backend).

## Displaying the pending state

```html
<span data-show="$_rgForms.validating.username" class="is-loading">Checking…</span>
```

(Inside a formset row the path is `$_rgForms.<scope>.validating.<field>`.)

## Scope and limits (v1)

- **Only errors attached to the triggering field** are shown incrementally.
  `Form.clean()` non-field errors are computed (the full form runs) but surface
  on final submit, not mid-typing.
- Unrelated fields' DOM — including their current errors — is never touched: the
  response patches only the triggered field's wrapper.
- **File fields** are skipped in incremental validation (they validate on submit).
- Put multiple *unprefixed* reactive forms on one page under **distinct Django
  prefixes** so their signals do not collide.

## Accessibility

The single-field fragment carries a stable wrapper id plus `aria-invalid` and
`aria-describedby` linking the control to its error/help text, from the first
render. Broader accessibility (focus-first-invalid, error summaries) is a
separate concern.
