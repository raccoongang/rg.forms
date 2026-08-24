# Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
# NOTE: this competitor (RHF useFieldArray) supports dynamic add/remove of rows at runtime, unlike the rg.forms slice, which is a *static* Django formset (fixed rows). This server accepts a variable-length list accordingly.
#
# Django backend counterpart. It RE-VALIDATES every row against the same rules
# the client declares in schema.ts: full name present, valid role, email
# required + well-formed for owners/admins. Per-row errors are returned under
# dotted keys ("members.<i>.<field>") so the RHF form can target the exact row.
from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

ROLES = ["owner", "admin", "editor", "viewer"]


class TeamMemberForm(forms.Form):
    full_name = forms.CharField()
    role = forms.ChoiceField(choices=[(r, r.title()) for r in ROLES])
    email = forms.CharField(required=False)
    admin_note = forms.CharField(required=False)

    def clean_full_name(self) -> str:
        value = (self.cleaned_data.get("full_name") or "").strip()
        if not value:
            raise ValidationError("Full name is required.")
        return value

    def clean(self) -> dict:
        cleaned = super().clean()
        role = cleaned.get("role")
        if role in ("owner", "admin"):
            email = (cleaned.get("email") or "").strip()
            if not email:
                self.add_error("email", "Owners and admins must provide an email.")
            else:
                try:
                    validate_email(email)
                except ValidationError:
                    self.add_error("email", "Enter a valid email address.")
        return cleaned


# The client sends camelCase per-row keys; map to the snake_case form fields.
_CLIENT_TO_SERVER = {
    "fullName": "full_name",
    "role": "role",
    "email": "email",
    "adminNote": "admin_note",
}
_SERVER_TO_CLIENT = {v: k for k, v in _CLIENT_TO_SERVER.items()}


@require_POST
def save_roster(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    rows = payload.get("members")
    if not isinstance(rows, list) or len(rows) == 0:
        return JsonResponse({"errors": {"members": ["Add at least one team member."]}}, status=400)

    errors: dict[str, list[str]] = {}
    cleaned_rows: list[dict] = []

    for index, raw in enumerate(rows):
        data = {server: (raw or {}).get(client) for client, server in _CLIENT_TO_SERVER.items()}
        form = TeamMemberForm(data)
        if form.is_valid():
            cleaned_rows.append(form.cleaned_data)
        else:
            for server_field, messages in form.errors.items():
                client_field = _SERVER_TO_CLIENT.get(server_field, server_field)
                key = "members" if server_field == "__all__" else f"members.{index}.{client_field}"
                errors.setdefault(key, []).extend(messages)

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    # ... persist cleaned_rows here ...
    return JsonResponse({"ok": True}, status=201)
