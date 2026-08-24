"""Example 4 — Multi-form settings dashboard (ADR-0003/0004).

Two independent, *prefixed* standalone forms on one page. They deliberately
share logical field names (``email``, ``enabled``, ``name``) to prove scoping is
not merely a formset feature: each form's signals live under its own scope and
cannot affect the other.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveEmailField,
    ReactiveForm,
)

from .. import services


class ProfileForm(ReactiveForm):
    """Rendered with prefix="profile"."""

    name = ReactiveCharField(label="Display name")
    email = ReactiveEmailField(label="Email", validate_on="blur", help_text="Try 'taken@example.com'.")
    bio = ReactiveCharField(label="Bio", required=False)

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip()
        if value and services.email_is_registered(value):
            raise ValidationError("That email is already used by another account.")
        return value


class NotificationsForm(ReactiveForm):
    """Rendered with prefix="notifications" — same field names, different form."""

    enabled = ReactiveBooleanField(label="Enable notifications", required=False)
    email = ReactiveEmailField(
        label="Notification email",
        required=False,
        # Independent per-form rule: only relevant/required when enabled.
        visible_when="$enabled",
        required_when="$enabled",
    )
    frequency = ReactiveChoiceField(
        label="Frequency",
        required=False,
        visible_when="$enabled",
        choices=[("daily", "Daily"), ("weekly", "Weekly")],
    )
    name = ReactiveCharField(label="Sender name", required=False, visible_when="$enabled")
