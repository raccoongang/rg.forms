# Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django backend counterpart. It RE-VALIDATES every rule the client declares in
# schema.ts / form.tsx — length, email format, password match, the conditional
# company email, free-provider rejection, and username/email availability. The
# duplication of rules across the TS client and this Python server is exactly
# what the rg.forms comparison measures.
from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

# --- Stand-in "database" (mirrors the example services) ----------------------
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
                self.add_error("company_email", "Business accounts require a company email.")
            else:
                try:
                    validate_email(company_email)
                except ValidationError:
                    self.add_error("company_email", "Enter a valid company email address.")
                else:
                    if is_free_email_domain(company_email):
                        self.add_error("company_email", "Use a company email, not a free provider.")
        return cleaned


# The client sends camelCase (schema.ts); Django fields are snake_case. Map both
# ways so field-level errors land on the key the RHF form registered.
_CLIENT_TO_SERVER = {
    "username": "username",
    "email": "email",
    "password": "password",
    "passwordConfirm": "password_confirm",
    "accountType": "account_type",
    "companyEmail": "company_email",
    "agreeTerms": "agree_terms",
}
_SERVER_TO_CLIENT = {v: k for k, v in _CLIENT_TO_SERVER.items()}


def _to_client_errors(form: RegistrationForm) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for server_field, messages in form.errors.items():
        client_field = _SERVER_TO_CLIENT.get(server_field, server_field)
        out[client_field] = list(messages)
    return out


# --- Endpoints ---------------------------------------------------------------
@require_GET
def check_username(request: HttpRequest) -> JsonResponse:
    value = request.GET.get("username", "")
    if username_is_taken(value):
        return JsonResponse({"available": False, "message": f"The username '{value.strip()}' is already taken."})
    return JsonResponse({"available": True})


@require_GET
def check_email(request: HttpRequest) -> JsonResponse:
    value = request.GET.get("email", "")
    if email_is_registered(value):
        return JsonResponse({"available": False, "message": "An account with this email already exists."})
    return JsonResponse({"available": True})


@require_POST
def register(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    data = {server: payload.get(client) for client, server in _CLIENT_TO_SERVER.items()}
    form = RegistrationForm(data)
    if not form.is_valid():
        return JsonResponse({"errors": _to_client_errors(form)}, status=400)

    # ... persist the user here ...
    return JsonResponse({"ok": True}, status=201)
