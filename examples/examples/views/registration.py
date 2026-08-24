"""Views for Example 1 — account registration + incremental validation."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from rg.forms import reactive_validate

from ..forms import RegistrationForm
from ._helpers import form_page


def registration(request: HttpRequest) -> HttpResponse:
    # A small latency makes the pending indicator visible in a browser; tests
    # construct the form directly with the default latency=0.
    return form_page(
        request,
        RegistrationForm,
        "examples/registration/page.html",
        form_kwargs={"latency": 0.15},
        context={"validate_action": "/registration/validate/"},
    )


def registration_validate(request: HttpRequest) -> HttpResponse:
    return reactive_validate(request, RegistrationForm)
