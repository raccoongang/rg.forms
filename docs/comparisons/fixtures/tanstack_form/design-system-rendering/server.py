# Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django counterpart for the profile form. It RE-VALIDATES the rules the client
# declares: display name required, email well-formed + not already registered,
# and a valid public handle that is required only for public profiles.

from __future__ import annotations

import json
import re

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

REGISTERED_EMAILS = {"taken@example.com", "admin@acme.co"}
HANDLE_RE = re.compile(r"^[a-zA-Z0-9_]+$")


def email_is_registered(email: str) -> bool:
    return email.strip().lower() in REGISTERED_EMAILS


class ProfileForm(forms.Form):
    display_name = forms.CharField()
    email = forms.EmailField()
    visibility = forms.ChoiceField(choices=[("public", "Public"), ("private", "Private")])
    handle = forms.CharField(required=False)

    def clean_email(self) -> str:
        value = (self.cleaned_data.get("email") or "").strip()
        if value and email_is_registered(value):
            raise ValidationError("That email is already registered.")
        return value

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("visibility") == "public":
            handle = (cleaned.get("handle") or "").strip()
            if not handle:
                self.add_error("handle", "A public handle is required.")
            elif len(handle) < 3:
                self.add_error("handle", "Handle must be at least 3 characters.")
            elif not HANDLE_RE.match(handle):
                self.add_error("handle", "Use letters, digits and underscores only.")
        return cleaned


_KEY_MAP = {"displayName": "display_name"}
_INVERSE = {v: k for k, v in _KEY_MAP.items()}


def _to_form_data(payload: dict) -> dict:
    return {_KEY_MAP.get(k, k): v for k, v in payload.items()}


def _to_client_errors(errors: forms.utils.ErrorDict) -> dict[str, list[str]]:
    return {_INVERSE.get(field, field): list(msgs) for field, msgs in errors.items()}


@require_POST
def save_profile(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body or "{}")
    form = ProfileForm(_to_form_data(payload))
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _to_client_errors(form.errors)}, status=400)
    # ... persist the profile ...
    return JsonResponse({"ok": True})


@require_GET
def check_email(request: HttpRequest) -> HttpResponse:
    email = (request.GET.get("email") or "").strip()
    return JsonResponse({"available": bool(email) and not email_is_registered(email)})
