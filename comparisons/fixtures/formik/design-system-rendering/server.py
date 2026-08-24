# Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
"""Django counterpart for the Formik profile form.

The server re-validates the same rules the field-component library declared:
required display name and email, email availability, and a required handle for
public profiles. Presentation lives entirely on the client; the server only
cares about the contract.
"""

from __future__ import annotations

import json

from django import forms
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

REGISTERED_EMAILS = {"taken@example.com", "admin@acme.co"}


def email_is_registered(email: str) -> bool:
    return email.strip().lower() in REGISTERED_EMAILS


class ProfileForm(forms.Form):
    display_name = forms.CharField()
    email = forms.EmailField()
    visibility = forms.ChoiceField(choices=[("public", "Public"), ("private", "Private")])
    handle = forms.CharField(required=False)

    def clean_email(self) -> str:
        value = self.cleaned_data["email"].strip()
        if email_is_registered(value):
            raise forms.ValidationError("That email is already registered.")
        return value

    def clean_handle(self) -> str:
        value = (self.cleaned_data.get("handle") or "").strip()
        if value and not value.replace("_", "").isalnum():
            raise forms.ValidationError("Handle may only contain letters, digits, and underscores.")
        return value

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("visibility") == "public" and not (cleaned.get("handle") or "").strip():
            self.add_error("handle", "Public profiles need a handle.")
        return cleaned


@require_GET
def check_email(request: HttpRequest) -> JsonResponse:
    email = request.GET.get("email", "")
    return JsonResponse({"available": not email_is_registered(email)})


@require_POST
def save_profile(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    form = ProfileForm(
        {
            "display_name": payload.get("displayName", ""),
            "email": payload.get("email", ""),
            "visibility": payload.get("visibility", ""),
            "handle": payload.get("handle", ""),
        }
    )
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    return JsonResponse({"ok": True})
