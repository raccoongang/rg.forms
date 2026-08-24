"""Views for Example 5 — feature-flagged / permission-aware form."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..forms import FeatureFlaggedForm


def feature_flags(request: HttpRequest) -> HttpResponse:
    # The server owns these signals. Query params let a visitor flip them to see
    # both client and server react identically; a real app reads them from the
    # request user / tenant / a flag service — never from client-submitted data.
    plan_tier = "paid" if request.GET.get("plan") == "paid" else "free"
    can_use_beta = request.GET.get("beta") == "1"
    kwargs = {"plan_tier": plan_tier, "can_use_beta": can_use_beta}

    submitted = None
    if request.method == "POST":
        form = FeatureFlaggedForm(request.POST, **kwargs)
        if form.is_valid():
            submitted = form.cleaned_data
    else:
        form = FeatureFlaggedForm(**kwargs)

    return render(
        request,
        "examples/external_signals/page.html",
        {"form": form, "submitted": submitted, "plan_tier": plan_tier, "can_use_beta": can_use_beta},
    )
