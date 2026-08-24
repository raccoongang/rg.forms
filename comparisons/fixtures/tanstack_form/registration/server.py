# Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django counterpart. It RE-VALIDATES every rule the TypeScript client declares:
# username/email length + uniqueness, password match, ToS acceptance, and the
# business-account "no free email provider" rule. This duplication (Zod on the
# client, Django on the server) is exactly the cost the comparison measures.

from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

# Stand-in "database" — the same fixtures the rg.forms example uses.
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
    agree_terms = forms.BooleanField(required=False)

    def clean_username(self) -> str:
        value = (self.cleaned_data.get("username") or "").strip()
        if value and username_is_taken(value):
            raise ValidationError(f"The username '{value}' is already taken.")
        return value

    def clean_email(self) -> str:
        value = (self.cleaned_data.get("email") or "").strip()
        if value and email_is_registered(value):
            raise ValidationError("An account with this email already exists.")
        return value

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")
        if not cleaned.get("agree_terms"):
            self.add_error("agree_terms", "You must accept the Terms of Service.")
        if cleaned.get("account_type") == "business":
            company_email = (cleaned.get("company_email") or "").strip()
            if not company_email:
                self.add_error("company_email", "A company email is required for business accounts.")
            elif is_free_email_domain(company_email):
                self.add_error("company_email", "Use a company email, not a free provider.")
        return cleaned


# The client sends camelCase keys; Django uses snake_case field names.
_KEY_MAP = {
    "passwordConfirm": "password_confirm",
    "accountType": "account_type",
    "companyEmail": "company_email",
    "agreeTerms": "agree_terms",
}


def _to_form_data(payload: dict) -> dict:
    return {_KEY_MAP.get(k, k): v for k, v in payload.items()}


def _to_client_errors(errors: forms.utils.ErrorDict) -> dict[str, list[str]]:
    inverse = {v: k for k, v in _KEY_MAP.items()}
    return {inverse.get(field, field): list(msgs) for field, msgs in errors.items()}


@require_POST
def register(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body or "{}")
    form = RegistrationForm(_to_form_data(payload))
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _to_client_errors(form.errors)}, status=400)
    # ... create the account from form.cleaned_data ...
    return JsonResponse({"ok": True})


@require_GET
def check_username(request: HttpRequest) -> HttpResponse:
    username = (request.GET.get("username") or "").strip()
    return JsonResponse({"available": bool(username) and not username_is_taken(username)})


@require_GET
def check_email(request: HttpRequest) -> HttpResponse:
    email = (request.GET.get("email") or "").strip()
    return JsonResponse({"available": bool(email) and not email_is_registered(email)})
