"""Views for Example 6 — canonical value semantics lab."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from ..forms import CanonicalValuesForm
from ._helpers import form_page


def canonical_values(request: HttpRequest) -> HttpResponse:
    return form_page(request, CanonicalValuesForm, "examples/canonical_values/page.html")
