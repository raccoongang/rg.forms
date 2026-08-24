"""Views for Example 4 — multi-form settings dashboard."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms import reactive_validate

from ..forms import NotificationsForm, ProfileForm

_PROFILE_PREFIX = "profile"
_NOTIFICATIONS_PREFIX = "notifications"


def settings_dashboard(request: HttpRequest) -> HttpResponse:
    saved = None
    # Each form is bound only when its own submit button fired, so the two
    # prefixed forms are fully independent.
    if request.method == "POST" and request.POST.get("which") == "profile":
        profile = ProfileForm(request.POST, prefix=_PROFILE_PREFIX)
        notifications = NotificationsForm(prefix=_NOTIFICATIONS_PREFIX)
        if profile.is_valid():
            saved = ("profile", profile.cleaned_data)
    elif request.method == "POST" and request.POST.get("which") == "notifications":
        profile = ProfileForm(prefix=_PROFILE_PREFIX)
        notifications = NotificationsForm(request.POST, prefix=_NOTIFICATIONS_PREFIX)
        if notifications.is_valid():
            saved = ("notifications", notifications.cleaned_data)
    else:
        profile = ProfileForm(prefix=_PROFILE_PREFIX)
        notifications = NotificationsForm(prefix=_NOTIFICATIONS_PREFIX)

    return render(
        request,
        "examples/settings_dashboard/page.html",
        {"profile": profile, "notifications": notifications, "saved": saved},
    )


def profile_validate(request: HttpRequest) -> HttpResponse:
    return reactive_validate(request, ProfileForm, prefix=_PROFILE_PREFIX)
