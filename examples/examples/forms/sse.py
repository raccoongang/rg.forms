"""Retained feature demo — whole-form SSE submit.

Contrast with Example 1 (per-field incremental validation): here the *entire*
form fragment is patched back on submit via ``reactive_form_response()``.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveEmailField,
    ReactiveForm,
)

from .. import services


class SSEValidationForm(ReactiveForm):
    username = ReactiveCharField(
        label="Username", max_length=30, min_length=3,
        help_text="Letters, numbers, underscores. Try 'admin' or 'test'.",
    )
    email = ReactiveEmailField(label="Email", help_text="Business accounts require a company email.")
    account_type = ReactiveChoiceField(
        label="Account Type", choices=[("personal", "Personal"), ("business", "Business")]
    )
    company_name = ReactiveCharField(
        label="Company Name", required=False,
        visible_when="$account_type == 'business'", required_when="$account_type == 'business'",
    )
    vat_number = ReactiveCharField(
        label="VAT Number", required=False,
        visible_when="$account_type == 'business'", required_when="$account_type == 'business'",
        help_text="EU VAT number, e.g. DE123456789",
    )
    coupon_code = ReactiveCharField(label="Coupon Code", required=False, help_text="Try WELCOME10 or SAVE20.")
    agree_terms = ReactiveBooleanField(label="I agree to the Terms of Service")

    def clean_username(self):
        username = self.cleaned_data.get("username", "")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValidationError("Username may only contain letters, numbers, and underscores.")
        if services.username_is_taken(username):
            raise ValidationError(f'The username "{username}" is already taken.')
        return username

    def clean_vat_number(self):
        vat = self.cleaned_data.get("vat_number", "")
        if vat and not re.match(r"^[A-Z]{2}\d{6,12}$", vat):
            raise ValidationError("Invalid VAT format. Expected e.g. DE123456789.")
        return vat

    def clean_coupon_code(self):
        code = self.cleaned_data.get("coupon_code", "")
        if code and services.lookup_coupon(code) is None:
            raise ValidationError(f'Coupon code "{code}" is not valid or has expired.')
        return code.upper()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("account_type") == "business" and cleaned.get("email"):
            if services.is_free_email_domain(cleaned["email"]):
                self.add_error("email", "Business accounts require a company email address.")
        return cleaned
