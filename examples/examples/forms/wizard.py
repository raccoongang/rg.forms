"""Additional example — a server-driven multi-step wizard.

State is held on the server (session) between steps; each step validates with
ordinary Django validation before advancing; the organization step is skipped
for personal accounts (conditional step). No client state engine.
"""

from __future__ import annotations

from rg.forms import ReactiveCharField, ReactiveChoiceField, ReactiveEmailField, ReactiveForm


class WizardAccountForm(ReactiveForm):
    """Step 1 — account."""

    account_type = ReactiveChoiceField(
        label="Account type",
        choices=[("personal", "Personal"), ("business", "Business")],
    )
    full_name = ReactiveCharField(label="Full name")
    email = ReactiveEmailField(label="Email")


class WizardOrgForm(ReactiveForm):
    """Step 2 — organization (only reached for business accounts)."""

    company_name = ReactiveCharField(label="Company name")
    company_size = ReactiveChoiceField(
        label="Company size",
        choices=[("1-10", "1–10"), ("11-50", "11–50"), ("51-200", "51–200"), ("200+", "200+")],
    )
    vat_number = ReactiveCharField(
        label="VAT number",
        required=False,
        help_text="Optional; validated only if provided.",
    )
