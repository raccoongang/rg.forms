"""Example 8 — Business onboarding with field groups (ADR-0001/0002/0004).

A larger, multi-section form: grouped visibility (personal vs business vs
billing), conditional attributes, a cross-field server rule, one database-backed
incremental check (the workspace subdomain), and an exact computed seat total.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError

from rg.forms import (
    FieldGroup,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDecimalField,
    ReactiveEmailField,
    ReactiveForm,
    ReactiveIntegerField,
)

from .. import services


class OnboardingForm(ReactiveForm):
    account_type = ReactiveChoiceField(
        label="Account type",
        choices=[("", "-- Select --"), ("personal", "Personal"), ("business", "Business")],
    )

    # Personal (always shown)
    first_name = ReactiveCharField(label="First name")
    last_name = ReactiveCharField(label="Last name")
    email = ReactiveEmailField(label="Email")

    # Business (shown only for business accounts)
    company_name = ReactiveCharField(
        label="Company name", required=False, required_when="$account_type == 'business'"
    )
    workspace = ReactiveCharField(
        label="Workspace subdomain",
        required=False,
        required_when="$account_type == 'business'",
        validate_on="blur",
        help_text="Checked for availability. Try 'admin' or 'demo'.",
    )
    seats = ReactiveIntegerField(
        label="Seats", required=False, min_value=1, initial=1,
        help_text_when={"$account_type == 'business'": "Billed per seat."},
    )
    price_per_seat = ReactiveDecimalField(
        label="Price per seat", required=False, decimal_places=2, initial="29.00",
        read_only_when="true",
    )
    monthly_total = ReactiveDecimalField(
        label="Monthly total (computed)",
        required=False,
        decimal_places=2,
        computed="$seats * $price_per_seat",
    )

    # Billing (shown only for business accounts)
    billing_country = ReactiveChoiceField(
        label="Country",
        required=False,
        required_when="$account_type == 'business'",
        choices=[("", "-- Select --"), ("us", "United States"), ("de", "Germany"), ("ua", "Ukraine")],
    )

    class Meta:
        field_groups = {
            "personal": FieldGroup(
                fields=["account_type", "first_name", "last_name", "email"],
                label="Your details",
            ),
            "business": FieldGroup(
                fields=["company_name", "workspace", "seats", "price_per_seat", "monthly_total"],
                label="Company",
                visible_when="$account_type == 'business'",
            ),
            "billing": FieldGroup(
                fields=["billing_country"],
                label="Billing",
                visible_when="$account_type == 'business'",
            ),
        }

    def clean_workspace(self):
        value = (self.cleaned_data.get("workspace") or "").strip().lower()
        # A subdomain collides with any taken username in this toy service.
        if value and services.username_is_taken(value):
            raise ValidationError(f"The workspace '{value}' is already in use.")
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("account_type") == "business" and cleaned.get("email"):
            if services.is_free_email_domain(cleaned["email"]):
                self.add_error("email", "Business accounts require a company email.")
        return cleaned
