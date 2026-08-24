# Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
"""Django counterpart for the Formik team roster.

Each submitted row is validated independently with the same rules the client
declared: full name and role are required, email is required for owners/admins,
and adminNote is only meaningful for admins. Per-row errors are returned aligned
by index so the client can attach them to the right FieldArray row.
"""

from __future__ import annotations

import json

from django import forms
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

ROLES = [("owner", "Owner"), ("admin", "Admin"), ("editor", "Editor"), ("viewer", "Viewer")]
EMAIL_REQUIRED_ROLES = {"owner", "admin"}


class TeamMemberForm(forms.Form):
    full_name = forms.CharField()
    role = forms.ChoiceField(choices=ROLES)
    email = forms.EmailField(required=False)
    admin_note = forms.CharField(required=False)

    def clean(self) -> dict:
        cleaned = super().clean()
        role = cleaned.get("role")
        if role in EMAIL_REQUIRED_ROLES and not (cleaned.get("email") or "").strip():
            self.add_error("email", "Owners and admins must have an email.")
        # adminNote only applies to admins; drop it otherwise.
        if role != "admin":
            cleaned["admin_note"] = ""
        return cleaned


@require_POST
def save_roster(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    rows = payload.get("members", [])
    if not isinstance(rows, list) or not rows:
        return JsonResponse({"errors": {"__all__": ["Add at least one team member."]}}, status=400)

    # Validate each row independently; collect per-row error dicts by index.
    row_errors: list[dict] = []
    cleaned_rows: list[dict] = []
    has_errors = False
    for row in rows:
        form = TeamMemberForm(
            {
                "full_name": row.get("fullName", ""),
                "role": row.get("role", ""),
                "email": row.get("email", ""),
                "admin_note": row.get("adminNote", ""),
            }
        )
        if form.is_valid():
            row_errors.append({})
            cleaned_rows.append(form.cleaned_data)
        else:
            has_errors = True
            row_errors.append(form.errors)

    if has_errors:
        return JsonResponse({"errors": {"members": row_errors}}, status=400)

    # Persist cleaned_rows here in a real app.
    return JsonResponse({"ok": True, "count": len(cleaned_rows)})
