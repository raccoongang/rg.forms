# Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django backend counterpart. It RE-VALIDATES the same rules the client declares
# in schema.ts / form.tsx: display name present, valid email, the conditional
# public handle (required + format), and email availability. The design-system
# wrapper components on the client are purely presentational; the authoritative
# rules live here as well, which is the duplication the comparison measures.
from __future__ import annotations

import json
import re

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

REGISTERED_EMAILS = {"taken@example.com", "admin@acme.co"}
_HANDLE_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def email_is_registered(email: str) -> bool:
    return email.strip().lower() in REGISTERED_EMAILS


class ProfileForm(forms.Form):
    display_name = forms.CharField()
    email = forms.EmailField()
    visibility = forms.ChoiceField(choices=[("public", "Public"), ("private", "Private")])
    handle = forms.CharField(required=False)

    def clean_display_name(self) -> str:
        value = (self.cleaned_data.get("display_name") or "").strip()
        if not value:
            raise ValidationError("Display name is required.")
        return value

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
                self.add_error("handle", "Public profiles need a handle.")
            elif not _HANDLE_RE.match(handle):
                self.add_error(
                    "handle",
                    "Handle must be 3–20 chars: lowercase letters, digits, underscore.",
                )
        return cleaned


_CLIENT_TO_SERVER = {
    "displayName": "display_name",
    "email": "email",
    "visibility": "visibility",
    "handle": "handle",
}
_SERVER_TO_CLIENT = {v: k for k, v in _CLIENT_TO_SERVER.items()}


def _to_client_errors(form: ProfileForm) -> dict[str, list[str]]:
    return {_SERVER_TO_CLIENT.get(field, field): list(msgs) for field, msgs in form.errors.items()}


@require_GET
def check_email(request: HttpRequest) -> JsonResponse:
    value = request.GET.get("email", "")
    if email_is_registered(value):
        return JsonResponse({"available": False, "message": "That email is already registered."})
    return JsonResponse({"available": True})


@require_POST
def save_profile(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    data = {server: payload.get(client) for client, server in _CLIENT_TO_SERVER.items()}
    form = ProfileForm(data)
    if not form.is_valid():
        return JsonResponse({"errors": _to_client_errors(form)}, status=400)

    # ... persist the profile here ...
    return JsonResponse({"ok": True}, status=200)
