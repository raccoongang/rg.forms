"""Views for Example 2 — order configurator."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..forms import OrderConfiguratorForm


def order_configurator(request: HttpRequest) -> HttpResponse:
    result = None
    if request.method == "POST":
        form = OrderConfiguratorForm(request.POST)
        if form.is_valid():
            result = {
                "plan": form.cleaned_data.get("plan"),
                "seats": form.cleaned_data.get("seats"),
                "unit_price": form.cleaned_data.get("unit_price"),
                "total": form.cleaned_data.get("total"),          # authoritative Decimal
                "discounted": form.discounted_total(),
            }
    else:
        form = OrderConfiguratorForm()
    return render(request, "examples/order_configurator/page.html", {"form": form, "result": result})
