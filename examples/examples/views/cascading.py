"""Views for the (modernized) cascading dropdowns demo — country/region/city."""

from __future__ import annotations

from collections.abc import Generator

from datastar_py.django import DatastarResponse, ServerSentEventGenerator
from datastar_py.sse import DatastarEvent
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .. import services
from ..forms import GeoCascadingForm


def cascading_form(request: HttpRequest) -> HttpResponse | DatastarResponse:
    is_datastar = request.headers.get("Datastar-Request") == "true"

    if request.method == "POST" and is_datastar:
        # Re-render the fragment with child options for the current parents,
        # resetting any child selection that is no longer valid.
        country = request.POST.get("country", "")
        region = request.POST.get("region", "")
        city = request.POST.get("city", "")
        if region and not services.region_belongs_to(region, country):
            region = ""
        if city and not services.city_belongs_to(city, region):
            city = ""
        form = GeoCascadingForm(initial={"country": country, "region": region, "city": city})
        html = render_to_string("examples/_cascading_form_fragment.html", {"form": form}, request)

        def updates() -> Generator[DatastarEvent, None, None]:
            yield ServerSentEventGenerator.patch_elements(html)

        return DatastarResponse(updates())

    if request.method == "POST":
        form = GeoCascadingForm(request.POST)
        form.is_valid()
    else:
        form = GeoCascadingForm()
    return render(request, "examples/cascading_form.html", {"form": form})
