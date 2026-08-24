"""Views for the retained cascading-dropdowns demo."""

from __future__ import annotations

from collections.abc import Generator

from datastar_py.django import DatastarResponse, ServerSentEventGenerator
from datastar_py.sse import DatastarEvent
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from .. import services
from ..forms import CascadingForm


def cascading_form(request: HttpRequest) -> HttpResponse | DatastarResponse:
    is_datastar = request.headers.get("Datastar-Request") == "true"

    if request.method == "POST":
        if is_datastar:
            category_id = request.POST.get("category", "")
            product_id = request.POST.get("product", "")
            product = services.get_product_by_id(product_id) if product_id else None
            product_valid = bool(product and category_id and str(product["category_id"]) == str(category_id))
            initial = {
                "category": category_id,
                "product": product_id if product_valid else "",
                "quantity": request.POST.get("quantity", 1),
                "unit_price": product["price"] if product_valid else 0,
            }
            form = CascadingForm(initial=initial)
            form_html = render_to_string("examples/_cascading_form_fragment.html", {"form": form}, request)

            def updates() -> Generator[DatastarEvent, None, None]:
                yield ServerSentEventGenerator.patch_elements(form_html)

            return DatastarResponse(updates())

        form = CascadingForm(request.POST)
        if form.is_valid():
            pass
    else:
        form = CascadingForm()

    return render(request, "examples/cascading_form.html", {"form": form})
