"""Views for the date/time & localization example."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from ..forms import EventForm
from ._helpers import form_page


def datetime_localization(request: HttpRequest) -> HttpResponse:
    return form_page(request, EventForm, "examples/datetime_localization/page.html")
