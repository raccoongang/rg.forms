"""Views for the form-level (non-field) errors example."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from ..forms import ProjectTimelineForm
from ._helpers import form_page


def form_errors(request: HttpRequest) -> HttpResponse:
    return form_page(request, ProjectTimelineForm, "examples/form_errors/page.html")
