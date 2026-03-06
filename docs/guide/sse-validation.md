# SSE Validation

By default, Django forms re-render the entire page when validation fails. With `reactive_form_response()`, validation errors are patched into the page via Datastar SSE — only the form re-renders, the rest of the page stays untouched.

This is especially useful when:

- The page is expensive to render (dashboards, complex layouts)
- You want to preserve client-side state outside the form
- You want a smoother UX without full page flashes

## How it works

```
User submits form via Datastar @post
        ↓
Server validates (same as normal Django)
        ↓
┌─ Valid:   SSE redirect → browser navigates
└─ Invalid: SSE patch → only the form HTML is replaced
```

Datastar handles both cases transparently. The user sees instant feedback without any page reload.

## Setup

### 1. Split your template into page + fragment

**Page template** (`order.html`) — loaded once on GET:

```html
{% extends "base.html" %}
{% load reactive_forms %}

{% block content %}
<h1>Place Order</h1>

<!-- This wrapper is what SSE patches -->
{% include "_order_fragment.html" %}
{% endblock %}
```

**Fragment template** (`_order_fragment.html`) — re-rendered on validation:

```html
{% load reactive_forms %}

{% render_reactive_form form "Submit" action=action_url %}
```

The `action` parameter on `render_reactive_form` switches the form from native submit to Datastar `@post`. It also wraps the form in a `<div id="reactive-form-container">` that Datastar uses as the SSE patch target.

### 2. Use `reactive_form_response()` in the view

```python
from django.shortcuts import render
from rg.forms import reactive_form_response
from .forms import OrderForm

def order_view(request):
    action_url = request.build_absolute_uri()

    if request.method == "POST":
        form = OrderForm(request.POST)
        response = reactive_form_response(
            request,
            form,
            "_order_fragment.html",
            success_url="/orders/thanks/",
            context={"action_url": action_url},
        )
        if response:
            return response
    else:
        form = OrderForm()

    return render(request, "order.html", {
        "form": form,
        "action_url": action_url,
    })
```

That's it. The function handles everything:

| Scenario | Datastar request | Regular request |
|----------|-----------------|-----------------|
| **Valid** | SSE redirect | `HttpResponseRedirect` |
| **Invalid** | SSE patch (form fragment) | Returns `None` → view renders full page |

### 3. No changes to the form class

`reactive_form_response()` works with any `ReactiveForm`. Your form definition stays exactly the same — all `visible_when`, `required_when`, `computed`, and custom `clean_*` methods work as before.

## API Reference

```python
reactive_form_response(
    request,              # HttpRequest
    form,                 # Bound ReactiveForm instance
    fragment_template,    # Template path for the form fragment
    *,
    success_url=None,     # URL to redirect to on valid form
    on_success=None,      # Callback(form) → response (alternative to redirect)
    context=None,         # Extra template context for fragment rendering
)
```

**Returns**: `HttpResponseRedirect`, `DatastarResponse`, or `None`

### Parameters

`request`
:   The Django `HttpRequest`. Used to detect Datastar requests (via `Datastar-Request` header) and as context for `render_to_string`.

`form`
:   A bound form instance (constructed with `request.POST`). The function calls `form.is_valid()` internally.

`fragment_template`
:   Path to the template that renders just the form (not the full page). This template is rendered and sent as an SSE patch when validation fails.

`success_url`
:   Where to redirect after successful validation. For Datastar requests, this becomes an SSE redirect. For regular requests, it returns `HttpResponseRedirect`.

`on_success`
:   Optional callback receiving the valid form. Should return a response object. Useful when you need to process form data before deciding the redirect URL:

    ```python
    def handle_success(form):
        order = Order.objects.create(**form.cleaned_data)
        return redirect("order_detail", pk=order.pk)

    response = reactive_form_response(
        request, form, "_fragment.html",
        on_success=handle_success,
    )
    ```

    !!! note
        When using `on_success` with Datastar requests, return an SSE redirect from the callback:

        ```python
        from rg.forms.views import _sse_redirect

        def handle_success(form):
            order = Order.objects.create(**form.cleaned_data)
            if is_datastar_request(request):
                return _sse_redirect(f"/orders/{order.pk}/")
            return redirect("order_detail", pk=order.pk)
        ```

`context`
:   Extra context dict merged into `{"form": form}` when rendering the fragment template. Common use: passing `action_url` so the fragment template can set the `@post` target.

## Backend-heavy validation example

SSE validation really shines for validations that **cannot be done on the frontend** — database lookups, external API calls, and complex cross-field business rules:

```python
import re
from django.core.exceptions import ValidationError
from rg.forms import ReactiveForm, ReactiveCharField, ReactiveEmailField, ReactiveChoiceField

class RegistrationForm(ReactiveForm):
    username = ReactiveCharField(max_length=30)
    email = ReactiveEmailField()
    account_type = ReactiveChoiceField(choices=[
        ("personal", "Personal"),
        ("business", "Business"),
    ])
    company_name = ReactiveCharField(
        required=False,
        visible_when="$account_type == 'business'",
        required_when="$account_type == 'business'",
    )
    coupon_code = ReactiveCharField(required=False)

    def clean_username(self):
        username = self.cleaned_data["username"]
        # Database uniqueness check — can't do this on the frontend
        if User.objects.filter(username=username).exists():
            raise ValidationError(f'"{username}" is already taken.')
        return username

    def clean_coupon_code(self):
        code = self.cleaned_data.get("coupon_code", "")
        if not code:
            return code
        # Server-side coupon lookup
        if not Coupon.objects.filter(code=code, active=True).exists():
            raise ValidationError(f'Coupon "{code}" is not valid.')
        return code.upper()

    def clean(self):
        cleaned = super().clean()
        # Cross-field: business accounts need company email
        if cleaned.get("account_type") == "business":
            email = cleaned.get("email", "")
            domain = email.rsplit("@", 1)[-1].lower()
            if domain in {"gmail.com", "yahoo.com", "hotmail.com"}:
                self.add_error("email", "Business accounts require a company email.")
        return cleaned
```

With SSE validation, users see these errors instantly without a full page reload. The form preserves its reactive state (`visible_when` fields stay toggled correctly), and the rest of the page remains untouched.

## How it differs from standard form submission

| Aspect | Standard (`<form method="post">`) | SSE (`@post` + `reactive_form_response`) |
|--------|-----------------------------------|------------------------------------------|
| On error | Full page reload, scroll to top | Only form HTML replaced in-place |
| Page state | Lost (counters, scroll, other components reset) | Preserved |
| Network | Full HTML document transferred | Only the form fragment |
| UX | Page flash | Seamless update |
| Fallback | Works without JavaScript | Requires Datastar |

## Tips

- **Fragment template**: Keep it minimal — just the form rendering. Don't include page chrome, headers, or sidebars.
- **Template reuse**: The fragment is `{% include %}`-d in the full page template and rendered standalone for SSE patches. Write it once, use it in both places.
- **`action_url`**: Pass it via `context` so the fragment knows where to `@post`. Using `request.build_absolute_uri()` handles reverse proxies and port forwarding.
- **Success handling**: For simple redirects, use `success_url`. For cases where you need the saved object's ID (e.g., redirect to detail page), use `on_success`.
