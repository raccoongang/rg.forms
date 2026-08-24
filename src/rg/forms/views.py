"""View utilities for reactive forms with Datastar SSE support.

Provides helpers to return partial form re-renders via SSE instead of
full-page reloads on validation errors.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

from datastar_py.django import DatastarResponse, read_signals
from datastar_py.sse import DatastarEvent, ServerSentEventGenerator
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.template.loader import render_to_string

from .adapters import signals_to_querydict
from .scoping import RESERVED_NAMESPACE

_VALIDATE_FRAGMENT = "rg_forms/_validate_field.html"


def is_datastar_request(request: HttpRequest) -> bool:
    """Check if the request was made by Datastar."""
    return request.headers.get("Datastar-Request") == "true"


def _parse_field_path(field_path: str) -> tuple[str, str | None]:
    """Split a trigger path into ``(logical_name, scope)``.

    A scoped path must be *exactly* ``rgForms.<scope>.<name>`` (three
    components — field names and the Base32 scope never contain dots), so a
    malformed path like ``rgForms.<scope>.email.injected`` does not resolve to a
    field. An unscoped path is a bare ``name``; anything else returns a name
    that will fail the field-existence check in :func:`resolve_validate_field`.
    """
    parts = field_path.split(".")
    if len(parts) == 3 and parts[0] == RESERVED_NAMESPACE:
        return parts[2], parts[1]  # (logical_name, scope)
    return field_path, None


def resolve_validate_field(form: Any, field_path: str) -> str | None:
    """Verify an untrusted trigger path against ``form`` (ADR-0004 §5).

    Returns the logical field name only when the field exists, has incremental
    validation enabled, and the path's scope belongs to ``form``. Otherwise
    ``None`` — never dispatch to a method named by arbitrary client input.
    """
    name, scope = _parse_field_path(field_path)
    if scope != getattr(form, "reactive_scope", None):
        return None  # decoding a scope is not authorizing it
    field = form.fields.get(name)
    if field is None:
        return None
    if not getattr(field, "validate_on", None):
        return None
    return name


def reactive_validate_response(
    request: HttpRequest,
    form: Any,
    *,
    fragment_template: str = _VALIDATE_FRAGMENT,
    context: dict[str, Any] | None = None,
) -> DatastarResponse | HttpResponseBadRequest:
    """Run full validation and patch back only the triggered field (ADR-0004 §2).

    Verifies the trigger header against the ``?__rg_field`` URL discriminator
    (§3/§5), runs the whole form's ``is_valid()`` (exact final-submit semantics,
    cross-field rules included), and returns an SSE patch of only the triggering
    field's fragment. Only errors attached to that field surface incrementally;
    non-field errors remain submit-time feedback in v1.

    ``form`` must already be bound (see :func:`reactive_validate`). The caller's
    view stays a normal, CSRF-protected Django view.
    """
    field_path = request.headers.get("X-RG-Validate-Field")
    discriminator = request.GET.get("__rg_field")
    if not field_path or field_path != discriminator:
        return HttpResponseBadRequest("Missing or mismatched validation trigger.")

    name = resolve_validate_field(form, field_path)
    if name is None:
        return HttpResponseBadRequest("Unknown or non-validatable field.")

    form.is_valid()  # full form run; we select only the triggered fragment

    from django.middleware.csrf import get_token

    ctx: dict[str, Any] = {
        "field": form[name],
        "form": form,
        # Re-render keeps the validate handler alive after the patch. The
        # fragment posts back to the current URL (base for ?__rg_field).
        "validate_action": request.path,
        "csrf_token": get_token(request),
    }
    if context:
        ctx.update(context)

    html = render_to_string(fragment_template, ctx, request)

    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.patch_elements(html)

    return DatastarResponse(events())


def reactive_validate(
    request: HttpRequest,
    form_class: type,
    *,
    prefix: str | None = None,
    fragment_template: str = _VALIDATE_FRAGMENT,
    context: dict[str, Any] | None = None,
    **form_kwargs: Any,
) -> DatastarResponse | HttpResponseBadRequest:
    """One-call declarative incremental validation from a JSON-signal request.

    Reads the canonical signals, adapts them into form data for the current
    form's scope (ADR-0004 §2a), binds ``form_class`` (with ``prefix`` and any
    extra ``form_kwargs``), and delegates to :func:`reactive_validate_response`.

    Usage::

        def validate(request):
            return reactive_validate(request, MyForm)
    """
    signals = read_signals(request) or {}
    probe = form_class(prefix=prefix, **form_kwargs)
    data = signals_to_querydict(probe, signals)
    form = form_class(data, prefix=prefix, **form_kwargs)
    return reactive_validate_response(request, form, fragment_template=fragment_template, context=context)


def reactive_form_response(
    request: HttpRequest,
    form: Any,
    fragment_template: str,
    *,
    success_url: str | None = None,
    on_success: Callable[[Any], Any] | None = None,
    context: dict[str, Any] | None = None,
) -> HttpResponseRedirect | DatastarResponse | None:
    """Handle form POST with SSE support for Datastar.

    For Datastar requests:
    - Invalid form: renders fragment_template and returns SSE patch
    - Valid form: returns SSE redirect (or calls on_success)

    For regular requests:
    - Invalid form: returns None (let the view render the full page)
    - Valid form: returns HttpResponseRedirect (or calls on_success)

    Args:
        request: The Django HttpRequest
        form: A bound ReactiveForm instance (already constructed with request.POST)
        fragment_template: Template path for the form fragment (used for SSE patch)
        success_url: URL to redirect to on success
        on_success: Callback receiving the valid form, should return a response.
            Called instead of redirect when provided. If it returns None,
            falls through to success_url redirect.
        context: Extra template context for fragment rendering

    Returns:
        A response object, or None if the view should handle rendering.

    Usage::

        def my_view(request):
            if request.method == "POST":
                form = MyForm(request.POST)
                response = reactive_form_response(
                    request, form,
                    "myapp/_form_fragment.html",
                    success_url="/success/",
                )
                if response:
                    return response
            else:
                form = MyForm()
            return render(request, "myapp/form.html", {"form": form})
    """
    datastar = is_datastar_request(request)

    if form.is_valid():
        if on_success:
            result = on_success(form)
            if result is not None:
                return result

        if success_url:
            if datastar:
                return _sse_redirect(success_url)
            return HttpResponseRedirect(success_url)

        return None

    # Form is invalid
    if datastar:
        return _sse_patch_form(request, form, fragment_template, context)

    return None


def _sse_patch_form(
    request: HttpRequest,
    form: Any,
    fragment_template: str,
    context: dict[str, Any] | None = None,
) -> DatastarResponse:
    """Render form fragment and return as SSE patch."""
    ctx: dict[str, Any] = {"form": form}
    if context:
        ctx.update(context)

    html = render_to_string(fragment_template, ctx, request)

    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.patch_elements(html)

    return DatastarResponse(events())


def _sse_redirect(url: str) -> DatastarResponse:
    """Return an SSE redirect response."""

    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.redirect(url)

    return DatastarResponse(events())
