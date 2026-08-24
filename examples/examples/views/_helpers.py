"""Shared GET/POST rendering helper for the example views.

Kept intentionally small so it does not hide the rg.forms API from readers: the
views still construct ordinary Django forms and render ordinary templates.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def form_page(
    request: HttpRequest,
    form_class: type,
    template: str,
    *,
    form_kwargs: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> HttpResponse:
    """Render a standard reactive-form page.

    GET renders an unbound form; POST binds and validates and, on success,
    exposes the cleaned data as ``submitted`` for the template to echo.
    """
    form_kwargs = form_kwargs or {}
    submitted = None
    if request.method == "POST":
        form = form_class(request.POST, **form_kwargs)
        if form.is_valid():
            submitted = form.cleaned_data
    else:
        form = form_class(**form_kwargs)

    ctx: dict[str, Any] = {"form": form, "submitted": submitted}
    if context:
        ctx.update(context)
    return render(request, template, ctx)
