"""Views for Example 8 — business onboarding."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from rg.forms import reactive_validate

from ..forms import OnboardingForm
from ._helpers import form_page


def onboarding(request: HttpRequest) -> HttpResponse:
    return form_page(
        request,
        OnboardingForm,
        "examples/onboarding/page.html",
        context={"validate_action": "/onboarding/validate/"},
    )


def onboarding_validate(request: HttpRequest) -> HttpResponse:
    return reactive_validate(request, OnboardingForm)
