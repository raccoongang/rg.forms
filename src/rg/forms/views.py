"""View utilities for reactive forms with Datastar SSE support.

Provides helpers to return partial form re-renders via SSE instead of
full-page reloads on validation errors.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from typing import Any

from datastar_py.django import DatastarResponse
from datastar_py.sse import DatastarEvent, ServerSentEventGenerator
from django.http import HttpRequest, HttpResponseRedirect
from django.template.loader import render_to_string


def is_datastar_request(request: HttpRequest) -> bool:
    """Check if the request was made by Datastar."""
    return request.headers.get("Datastar-Request") == "true"


def reactive_form_response(
    request: HttpRequest,
    form: Any,
    fragment_template: str,
    *,
    success_url: str | None = None,
    on_success: Callable | None = None,
    context: dict | None = None,
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
    context: dict | None = None,
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
