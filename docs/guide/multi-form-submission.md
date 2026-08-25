# Multi-form Submission

[`reactive_form_response()`](sse-validation.md) handles exactly one form. Real screens routinely submit **several forms
and/or a formset together** on one page, persisted atomically — an aggregate root and its related rows: a user plus a
profile plus a set of work-experience entries.

`reactive_forms_response()` (plural) is the sibling helper for that case. It owns only the request/response plumbing —
validate every member, patch one shared fragment on any error, redirect on all-valid — and leaves
validation-of-aggregates and persistence to your view, where they belong. See
[ADR-0005](../adr/0005-multi-form-reactive-submission.md) for the full rationale.

## How it works

```
User submits the combined form via Datastar @post
        ↓
Server validates every member (non-short-circuit, in order)
        ↓
┌─ All valid: on_success() runs your atomic save → SSE redirect
└─ Any invalid: SSE patch → the one shared fragment is replaced, showing every member's errors at once
```

The key difference from the single-form helper: with N forms there is no single form to save and no canonical fragment
context, so **you** supply both.

## Setup

### 1. Bind every member in the view

```python
from django.db import transaction
from django.shortcuts import render
from django.urls import reverse
from rg.forms import reactive_forms_response

from .forms import StaffUserForm, UserProfileForm, WorkExperienceFormSet


def user_create(request):
    action_url = request.build_absolute_uri()

    if request.method == "POST":
        user_form = StaffUserForm(request.POST, prefix="user")
        profile_form = UserProfileForm(request.POST, prefix="profile")
        formset = WorkExperienceFormSet(request.POST, prefix="work")

        def on_success():
            with transaction.atomic():          # the caller owns atomicity + audit
                user = user_form.save()
                profile = profile_form.save(user=user)
                formset.save(profile=profile)
            return None                          # fall through to the success_url redirect

        response = reactive_forms_response(
            request,
            [user_form, profile_form, formset],
            "users/_user_form.html",
            context={
                "user_form": user_form,
                "profile_form": profile_form,
                "formset": formset,
                # merged_signals() is defined in step 2 below.
                "signals_json": merged_signals(user_form, profile_form, formset),
                "action": action_url,
            },
            success_url=reverse("user_list"),
            on_success=on_success,
        )
        if response:
            return response
    else:
        user_form = StaffUserForm(prefix="user")
        profile_form = UserProfileForm(prefix="profile")
        formset = WorkExperienceFormSet(prefix="work")

    return render(request, "users/user_form.html", {
        "user_form": user_form,
        "profile_form": profile_form,
        "formset": formset,
        "signals_json": merged_signals(user_form, profile_form, formset),
        "action": action_url,
    })
```

### 2. Render one shared fragment for all members

Because every member is prefixed, its signals live under its own scope
([ADR-0003](../adr/0003-scoped-signals-and-reactive-formsets.md)) — the seeds don't collide. Merge them into one
`data-signals` seed on the wrapping `<form>` (a single form or formset tag cannot see its siblings, so the merge is the
view's job):

```python
import json


def merged_signals(*members):
    """One data-signals seed spanning every form and formset row."""
    def deep_merge(base, overlay):
        for key, value in overlay.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    merged = {}
    for member in members:
        rows = getattr(member, "forms", [member])   # a formset exposes .forms; a form is its own single row
        for row in rows:
            deep_merge(merged, row.get_seed_signals())
    return json.dumps(merged)
```

Pass `signals_json=merged_signals(user_form, profile_form, formset)` in the context, then the fragment
(`users/_user_form.html`) wraps everything in one patch target:

```html
{% load reactive_forms %}

<div id="multi-form-container">
<form method="post" data-signals='{{ signals_json }}'
      data-on:submit__prevent="@post('{{ action }}', {contentType: 'form'})">
    {% csrf_token %}
    {{ formset.management_form }}

    <fieldset>
        <legend>Account</legend>
        {% render_reactive_field user_form.username %}
        {% render_reactive_field user_form.email %}
    </fieldset>

    <fieldset>
        <legend>Profile</legend>
        {% render_reactive_field profile_form.full_name %}
        {% render_reactive_field profile_form.birth_year %}
    </fieldset>

    <fieldset>
        <legend>Work experience</legend>
        {% for row in formset.forms %}
            {% render_reactive_field row.company %}
            {% render_reactive_field row.title %}
        {% endfor %}
    </fieldset>

    <button type="submit">Create user</button>
</form>
</div>
```

The full page template `{% include %}`-s this same fragment so it renders identically on GET and on an SSE patch.

## Cross-form validation

Some invariants can only be checked by comparing **valid** forms — "the earliest work-experience year must not predate a
plausible working age", "these two amounts must sum to the third". Those are your view's responsibility, and they must be
attached **before** the helper runs its success branch — not inside `on_success` (which runs only when every member is
already individually valid, and whose added errors would arrive after the redirect decision).

The idiom relies on Django caching validation:

```python
forms = [user_form, profile_form, formset]
if all([f.is_valid() for f in forms]):                 # populate cleaned_data + cache errors
    birth_year = profile_form.cleaned_data["birth_year"]
    starts = [f.cleaned_data.get("start_year") for f in formset.forms if f.cleaned_data.get("start_year")]
    if starts and min(starts) < birth_year + 16:
        profile_form.add_error("birth_year", "Work history predates age 16.")

# The helper re-checks is_valid() — cached, so no second full_clean; the attached error routes to the patch.
response = reactive_forms_response(request, forms, "users/_user_form.html", context={...}, ...)
```

`add_error` keeps the form bound-and-invalid and Django caches `full_clean`, so the helper's `all([...])` reflects the
attached error without re-running validation.

## API Reference

```python
reactive_forms_response(
    request,              # HttpRequest
    forms,                # Non-empty, ordered sequence of already-bound members (Form / ModelForm / FormSet)
    fragment_template,    # Template path for the shared fragment
    *,
    context,              # Required — the exact template context for the error fragment
    success_url=None,     # URL to redirect to when every member is valid
    on_success=None,      # Callback() → HttpResponseBase | None (no form argument)
)
```

**Returns**: an `HttpResponseBase | None` — concretely an `HttpResponseRedirect`, a `DatastarResponse`, whatever
`on_success` returned, or `None`.

| Scenario | Datastar request | Regular request |
|----------|------------------|-----------------|
| **All valid** | `on_success()`, then SSE redirect to `success_url` | `on_success()`, then `HttpResponseRedirect` |
| **Any invalid** | SSE patch of `fragment_template` (rendered with `context`) — every member's errors | `None` → the view renders the full page |

### Parameters

`forms`
:   A **non-empty** ordered sequence. Every member is validated with a **list** comprehension, so validation never
    short-circuits — an early failure still validates later members, and the single error patch shows all errors at once.
    An empty sequence raises `ValueError` (silently treating "no forms" as valid would run `on_success`/redirect without
    validating anything).

`context`
:   Keyword-only and **required**. With N forms there is no canonical `{"form": form}` to inject, so you pass the exact
    context the fragment needs (each form and formset under the names the template uses). A wrong or empty context would
    render a broken fragment on the error path.

`on_success`
:   Takes **no argument** — it closes over the forms it already holds. Run your `transaction.atomic()` (and any
    service/audit logic) inside it. Returning an `HttpResponseBase` short-circuits and is returned as-is; returning
    `None` falls through to the `success_url` redirect.

    !!! warning "Datastar success returns"
        Under a Datastar request, returning a plain `HttpResponseRedirect` from `on_success` is returned verbatim and
        will **not** navigate the Datastar client. For a static target, return `None` and let `success_url` become the
        SSE redirect (it is encoded correctly for both native and Datastar requests). When the target is only known
        after the save — a freshly-created object's detail page — return `sse_redirect(url)` under a Datastar request
        and a plain redirect otherwise:

        ```python
        from django.shortcuts import redirect
        from rg.forms import is_datastar_request, sse_redirect

        def on_success():
            user = create_staff_user(user_form, profile_form, formset)
            url = reverse("user_detail", args=[user.pk])
            return sse_redirect(url) if is_datastar_request(request) else redirect(url)
        ```

## What it does not do

`reactive_forms_response()` is submission *plumbing*, never a save engine. It deliberately does not own persistence,
transactions, or audit (that is your `on_success`); does not perform cross-form validation (you attach aggregate errors
before the call); and does not decide whether a given multi-form page *should* be converted — a page may still be
correctly left bespoke, e.g. when a single consolidated audit event per aggregate write is a design requirement. See the
[ADR-0005 non-goals](../adr/0005-multi-form-reactive-submission.md) for the full boundary.

## See also

- [SSE Validation](sse-validation.md) — the single-form `reactive_form_response()`.
- [Formsets & Scoped Signals](formsets.md) — how prefixed members get non-colliding signal scopes.
- [Incremental Validation](incremental-validation.md) — per-field server validation, orthogonal and composable.
