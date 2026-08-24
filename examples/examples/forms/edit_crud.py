"""Additional example — edit an existing object (CRUD).

Most examples read as "create"; this one edits a stored record: fields are
pre-filled from the "database", validation failures preserve input, and a
permission-dependent field only exists when the server says the viewer may see
it (a server gate, not a client `visible_when`).
"""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveEmailField,
    ReactiveForm,
)

from .. import services

_PLAN_CHOICES = [(p["code"], p["name"]) for p in services.get_plans()]


class AccountEditForm(ReactiveForm):
    display_name = ReactiveCharField(label="Display name")
    email = ReactiveEmailField(label="Email", validate_on="blur")
    plan = ReactiveChoiceField(label="Plan", choices=_PLAN_CHOICES)
    marketing_opt_in = ReactiveBooleanField(label="Send me product news", required=False)
    # Business-only note, shown when the plan is Enterprise (client UX) …
    account_manager = ReactiveCharField(
        label="Account manager",
        required=False,
        visible_when="$plan == '100'",
    )

    def __init__(self, *args, can_see_internal: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        # … and a *permission-gated* field that only exists server-side when the
        # viewer is allowed to see it. This is authorization, not visibility:
        # a non-staff user's request never contains the field at all.
        if can_see_internal:
            self.fields["internal_notes"] = ReactiveCharField(
                label="Internal notes (staff only)",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
            )

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip()
        # Uniqueness against *other* accounts; keeping the current email is fine.
        if value and value != services.get_account()["email"] and services.email_is_registered(value):
            raise ValidationError("That email is already used by another account.")
        return value
