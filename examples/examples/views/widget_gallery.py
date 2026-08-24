"""Views for the widget compatibility gallery example."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from ..forms import WidgetGalleryForm
from ._helpers import form_page


def widget_gallery(request: HttpRequest) -> HttpResponse:
    return form_page(request, WidgetGalleryForm, "examples/widget_gallery/page.html")
