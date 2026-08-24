"""Example 7 — Design-system override showcase (ADR-0001).

One form contract, two presentation adapters. The same ``ProfileCardForm`` is
rendered by the shipped Bulma reference template and by a deliberately different
minimal/utility override — with no changes to the form class, and with the
incremental-validation attributes surviving the override.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from rg.forms import ReactiveCharField, ReactiveChoiceField, ReactiveEmailField, ReactiveForm

from .. import services


class ProfileCardForm(ReactiveForm):
    display_name = ReactiveCharField(label="Display name", placeholder="Ada Lovelace", autocomplete="name")
    email = ReactiveEmailField(
        label="Email", placeholder="ada@example.com", autocomplete="email",
        validate_on="blur", help_text="Availability is checked server-side.",
    )
    visibility = ReactiveChoiceField(
        label="Profile visibility",
        choices=[("public", "Public"), ("private", "Private")],
    )
    handle = ReactiveCharField(
        label="Public handle",
        required=False,
        visible_when="$visibility == 'public'",
        required_when="$visibility == 'public'",
        help_text="Shown only for public profiles.",
    )

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip()
        if value and services.email_is_registered(value):
            raise ValidationError("That email is already registered.")
        return value
