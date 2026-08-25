"""View utilities for reactive forms with Datastar SSE support.

Provides helpers to return partial form re-renders via SSE instead of
full-page reloads on validation errors.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Mapping, Sequence
from typing import Any

from datastar_py.django import DatastarResponse, read_signals
from datastar_py.sse import DatastarEvent, ServerSentEventGenerator
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
    HttpResponseBase,
    HttpResponseRedirect,
)
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
) -> HttpResponseBase | None:
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
    # Delegate to the N-form helper (ADR-0005 D8): the single-form contract is a
    # one-member sequence with a ``{"form": form}`` context shim and an
    # ``on_success`` adapter that re-supplies the validated form.
    return reactive_forms_response(
        request,
        [form],
        fragment_template,
        context={"form": form, **(context or {})},
        success_url=success_url,
        on_success=(lambda: on_success(form)) if on_success is not None else None,
    )


def reactive_forms_response(
    request: HttpRequest,
    forms: Sequence[Any],
    fragment_template: str,
    *,
    context: Mapping[str, Any],
    success_url: str | None = None,
    on_success: Callable[[], HttpResponseBase | None] | None = None,
) -> HttpResponseBase | None:
    """Handle an N-form/formset POST with SSE support for Datastar (ADR-0005).

    Owns only the request/response plumbing for submitting **several forms
    and/or a formset together** on one page. Validation-of-aggregates and
    persistence stay with the caller (D3/D5).

    Every member of ``forms`` is validated (non-short-circuit, in order) so a
    single error patch shows all errors at once. On any error the shared
    ``fragment_template`` is patched (Datastar) or ``None`` is returned (native,
    full-page fallback). On all-valid, ``on_success()`` runs (it closes over the
    forms it already holds), then the ``success_url`` redirect.

    Args:
        request: The Django HttpRequest.
        forms: A **non-empty** ordered sequence of already-bound members, each
            exposing ``is_valid()`` (Django ``Form``/``ModelForm``/``BaseFormSet``
            all qualify). The helper never inspects ``request.POST``/``FILES``.
        fragment_template: Template path for the shared fragment (SSE patch).
        context: The exact template context for the error fragment. Required and
            keyword-only — with N forms there is no canonical single-form name to
            inject, and a wrong/empty context would render a broken fragment (D4).
        success_url: URL to redirect to when every member is valid.
        on_success: Callback taking no argument (D3). Returning an
            ``HttpResponseBase`` short-circuits and is returned as-is; returning
            ``None`` falls through to the ``success_url`` redirect. The caller
            owns atomicity/audit inside it.

    Returns:
        A response object, or ``None`` if the view should handle rendering.

    Raises:
        ValueError: If ``forms`` is empty (``all([])`` is ``True``, so silently
            treating "no forms" as valid would run ``on_success``/redirect
            without validating anything — D1a).

    Usage::

        def user_create(request):
            if request.method == "POST":
                user_form = StaffUserForm(request.POST)
                profile_form = UserProfileForm(request.POST)
                formset = WorkExperienceFormSet(request.POST)

                def _on_success():
                    with transaction.atomic():        # caller owns atomicity
                        create_staff_user(user_form, profile_form, formset)
                    return None                        # fall through to redirect

                response = reactive_forms_response(
                    request,
                    [user_form, profile_form, formset],
                    "users/_user_form.html",
                    context={"form": user_form, "profile_form": profile_form,
                             "formset": formset},
                    success_url=reverse("user_list"),
                    on_success=_on_success,
                )
                if response:
                    return response
            else:
                ...
            return render(request, "users/user_form.html", {...})
    """
    if not forms:
        raise ValueError("forms must contain at least one bound form or formset")

    datastar = is_datastar_request(request)
    all_valid = all([f.is_valid() for f in forms])  # list → validate every member, in order

    if all_valid:
        if on_success is not None:
            result = on_success()
            if result is not None:
                return result
        if success_url:
            return sse_redirect(success_url) if datastar else HttpResponseRedirect(success_url)
        return None

    # At least one member is invalid.
    if datastar:
        return _sse_patch(render_to_string(fragment_template, dict(context), request))
    return None


def _sse_patch(html: str) -> DatastarResponse:
    """Wrap pre-rendered HTML in a single SSE ``patch-elements`` event."""

    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.patch_elements(html)

    return DatastarResponse(events())


def sse_redirect(url: str) -> DatastarResponse:
    """Return a Datastar SSE redirect that navigates the client to ``url``.

    Use this from an ``on_success`` callback when the redirect target is only
    known after the save (e.g. a freshly-created object's detail page) and the
    request is a Datastar request. For a static target, prefer returning ``None``
    and passing ``success_url`` — :func:`reactive_form_response` /
    :func:`reactive_forms_response` then encode the redirect correctly for both
    native and Datastar requests. Under a native (non-Datastar) request, return a
    plain :class:`~django.http.HttpResponseRedirect` instead.

    Usage::

        def on_success():
            obj = save_everything(...)
            url = reverse("thing_detail", args=[obj.pk])
            return sse_redirect(url) if is_datastar_request(request) else redirect(url)
    """

    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.redirect(url)

    return DatastarResponse(events())
