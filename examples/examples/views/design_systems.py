"""Views for Example 7 — design-system override showcase."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms import reactive_validate

from ..forms import ProfileCardForm


def design_systems(request: HttpRequest) -> HttpResponse:
    # One form contract, two adapters, chosen by ?style= (only one renders at a
    # time, so ids never collide). Both adapters consume the same context.
    style = "minimal" if request.GET.get("style") == "minimal" else "bulma"
    submitted = None
    if request.method == "POST":
        form = ProfileCardForm(request.POST)
        if form.is_valid():
            submitted = form.cleaned_data
    else:
        form = ProfileCardForm()
    return render(
        request,
        "examples/design_systems/page.html",
        {"form": form, "submitted": submitted, "style": style},
    )


def design_systems_validate(request: HttpRequest) -> HttpResponse:
    return reactive_validate(request, ProfileCardForm)
