# Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
"""Django counterpart for the Formik registration form.

The server re-validates every rule the client declared: field formats, password
match, username/email uniqueness, and the business-account free-domain check.
None of this trusts the client — the JSON body is treated as untrusted input.
"""

from __future__ import annotations

import json

from django import forms
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

# --- Stand-in "database" (a real app would query the User model) ------------
TAKEN_USERNAMES = {"admin", "root", "test", "user", "demo", "alice", "bob", "support"}
REGISTERED_EMAILS = {"taken@example.com", "admin@acme.co"}
FREE_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "mail.com"}


def username_is_taken(username: str) -> bool:
    return username.strip().lower() in TAKEN_USERNAMES


def email_is_registered(email: str) -> bool:
    return email.strip().lower() in REGISTERED_EMAILS


def is_free_email_domain(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    return domain in FREE_EMAIL_DOMAINS


class RegistrationForm(forms.Form):
    username = forms.CharField(min_length=3, max_length=30)
    email = forms.EmailField()
    password = forms.CharField(min_length=8)
    password_confirm = forms.CharField()
    account_type = forms.ChoiceField(choices=[("personal", "Personal"), ("business", "Business")])
    company_email = forms.CharField(required=False)
    agree_terms = forms.BooleanField()

    def clean_username(self) -> str:
        value = self.cleaned_data["username"].strip()
        if username_is_taken(value):
            raise forms.ValidationError(f"The username '{value}' is already taken.")
        return value

    def clean_email(self) -> str:
        value = self.cleaned_data["email"].strip()
        if email_is_registered(value):
            raise forms.ValidationError("An account with this email already exists.")
        return value

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")

        if cleaned.get("account_type") == "business":
            company_email = (cleaned.get("company_email") or "").strip()
            if not company_email:
                self.add_error("company_email", "Business accounts must register a company email.")
            elif is_free_email_domain(company_email):
                self.add_error("company_email", "Use a company email, not a free provider.")
        return cleaned


# --- Async availability endpoints (called onBlur by the client) ------------
@require_GET
def check_username(request: HttpRequest) -> JsonResponse:
    username = request.GET.get("username", "")
    return JsonResponse({"available": not username_is_taken(username)})


@require_GET
def check_email(request: HttpRequest) -> JsonResponse:
    email = request.GET.get("email", "")
    return JsonResponse({"available": not email_is_registered(email)})


@require_POST
def register(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    # Map the client's camelCase keys onto the form's snake_case field names.
    form = RegistrationForm(
        {
            "username": payload.get("username", ""),
            "email": payload.get("email", ""),
            "password": payload.get("password", ""),
            "password_confirm": payload.get("passwordConfirm", ""),
            "account_type": payload.get("accountType", ""),
            "company_email": payload.get("companyEmail", ""),
            "agree_terms": payload.get("agreeTerms", False),
        }
    )
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    # Persist the account here in a real app.
    return JsonResponse({"ok": True})
