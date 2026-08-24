# Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django counterpart for the team roster. It RE-VALIDATES every row's rules that
# the client declares: full name required, a role selected, email required (and
# well-formed) for owners/admins. Because the client sends a variable-length JSON
# array, the server validates each row with a per-row form and returns errors
# indexed by row position.

from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

ROLE_CHOICES = [("owner", "Owner"), ("admin", "Admin"), ("editor", "Editor"), ("viewer", "Viewer")]
EMAIL_REQUIRED_ROLES = {"owner", "admin"}


class TeamMemberForm(forms.Form):
    full_name = forms.CharField()
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    email = forms.EmailField(required=False)
    admin_note = forms.CharField(required=False)

    def clean(self) -> dict:
        cleaned = super().clean()
        role = cleaned.get("role")
        if role in EMAIL_REQUIRED_ROLES and not (cleaned.get("email") or "").strip():
            self.add_error("email", "Email is required for owners and admins.")
        return cleaned


# Client sends camelCase per-row keys.
_KEY_MAP = {"fullName": "full_name", "adminNote": "admin_note"}
_INVERSE = {v: k for k, v in _KEY_MAP.items()}


def _row_to_form_data(row: dict) -> dict:
    return {_KEY_MAP.get(k, k): v for k, v in row.items()}


def _row_errors(errors: forms.utils.ErrorDict) -> dict[str, list[str]]:
    return {_INVERSE.get(field, field): list(msgs) for field, msgs in errors.items()}


@require_POST
def save_roster(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body or "{}")
    members = payload.get("members") or []

    if not members:
        return JsonResponse(
            {"ok": False, "errors": {"members": {}, "_": ["Add at least one team member."]}},
            status=400,
        )

    row_errors: dict[str, dict[str, list[str]]] = {}
    for index, row in enumerate(members):
        form = TeamMemberForm(_row_to_form_data(row))
        if not form.is_valid():
            row_errors[str(index)] = _row_errors(form.errors)

    if row_errors:
        return JsonResponse({"ok": False, "errors": {"members": row_errors}}, status=400)

    # ... persist the roster ...
    return JsonResponse({"ok": True})
