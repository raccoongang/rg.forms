"""Example 1 — Account registration with incremental validation (ADR-0001/0004).

The username and email are checked against the "database" as the user leaves the
field (``validate_on="blur"``); the same rules run again on final submit. All
validation is ordinary Django server-side validation — there is no client-side
validation engine.
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


class RegistrationForm(ReactiveForm):
    username = ReactiveCharField(
        label="Username",
        min_length=3,
        max_length=30,
        placeholder="pick a username",
        validate_on="blur",
        help_text="Checked for availability when you leave the field. Try 'admin' or 'alice'.",
    )
    email = ReactiveEmailField(
        label="Email",
        placeholder="you@example.com",
        validate_on="blur",
        help_text="Try 'taken@example.com' to see the availability check.",
    )
    password = ReactiveCharField(label="Password", min_length=8, widget=forms.PasswordInput)
    password_confirm = ReactiveCharField(label="Confirm password", widget=forms.PasswordInput)

    account_type = ReactiveChoiceField(
        label="Account type",
        choices=[("personal", "Personal"), ("business", "Business")],
    )
    company_email_domain = ReactiveCharField(
        label="Company email",
        required=False,
        visible_when="$account_type == 'business'",
        required_when="$account_type == 'business'",
        help_text="Business accounts must register a company email (not a free provider).",
    )
    agree_terms = ReactiveBooleanField(label="I agree to the Terms of Service")

    # --- server-authoritative validation (also runs during incremental checks) --
    def clean_username(self):
        value = (self.cleaned_data.get("username") or "").strip()
        if value and services.username_is_taken(value, latency=self._latency):
            raise ValidationError(f"The username '{value}' is already taken.")
        return value

    def clean_email(self):
        value = (self.cleaned_data.get("email") or "").strip()
        if value and services.email_is_registered(value, latency=self._latency):
            raise ValidationError("An account with this email already exists.")
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")
        company_email = cleaned.get("company_email_domain", "")
        if company_email and services.is_free_email_domain(company_email):
            self.add_error("company_email_domain", "Use a company email, not a free provider.")
        return cleaned

    # Latency is injected so tests stay fast; the demo view sets a small value
    # only to make the pending indicator visible in a browser.
    _latency: float = 0.0

    def __init__(self, *args, latency: float = 0.0, **kwargs):
        super().__init__(*args, **kwargs)
        self._latency = latency
