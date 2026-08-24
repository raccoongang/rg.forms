# Illustrative comparison fixture — not executed. Idiomatic TanStack Form (@tanstack/react-form v0.x/1.x), React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django counterpart for the order configurator. It RE-VALIDATES the same rules
# the client declares (plan required, enterprise contact required for plan 100,
# seats >= 1, coupon validity) and — crucially — RECOMPUTES the exact Decimal
# total server-side. Any total the client sends is ignored; the server total is
# authoritative.

from __future__ import annotations

import json
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST

PLANS = {
    "001": {"name": "Starter", "unit_price": Decimal("9.00")},
    "010": {"name": "Team", "unit_price": Decimal("29.00")},
    "100": {"name": "Enterprise", "unit_price": Decimal("99.00")},
}

VALID_COUPONS = {"WELCOME10": 10, "SAVE20": 20, "LAUNCH50": 50}


def lookup_coupon(code: str) -> int | None:
    return VALID_COUPONS.get(code.strip().upper())


class OrderForm(forms.Form):
    plan = forms.ChoiceField(choices=[(c, p["name"]) for c, p in PLANS.items()])
    enterprise_contact = forms.CharField(required=False)
    seats = forms.IntegerField(min_value=1)
    coupon = forms.CharField(required=False)

    def clean_coupon(self) -> str:
        code = (self.cleaned_data.get("coupon") or "").strip()
        if code and lookup_coupon(code) is None:
            raise ValidationError(f"Coupon '{code}' is not valid.")
        return code.upper()

    def clean(self) -> dict:
        cleaned = super().clean()
        plan = cleaned.get("plan")
        if plan == "100" and not (cleaned.get("enterprise_contact") or "").strip():
            self.add_error("enterprise_contact", "Enterprise orders need an account-manager contact.")
        # Starter is single-seat: force it regardless of what the client sent.
        if plan == "001":
            cleaned["seats"] = 1
        return cleaned

    def total(self) -> Decimal:
        plan = PLANS[self.cleaned_data["plan"]]
        return (plan["unit_price"] * self.cleaned_data["seats"]).quantize(Decimal("0.01"))

    def discounted_total(self) -> Decimal:
        total = self.total()
        discount = lookup_coupon(self.cleaned_data.get("coupon") or "")
        if not discount:
            return total
        return (total * (Decimal(100) - Decimal(discount)) / Decimal(100)).quantize(Decimal("0.01"))


_KEY_MAP = {"enterpriseContact": "enterprise_contact"}


def _to_form_data(payload: dict) -> dict:
    return {_KEY_MAP.get(k, k): v for k, v in payload.items()}


def _to_client_errors(errors: forms.utils.ErrorDict) -> dict[str, list[str]]:
    inverse = {v: k for k, v in _KEY_MAP.items()}
    return {inverse.get(field, field): list(msgs) for field, msgs in errors.items()}


@require_POST
def place_order(request: HttpRequest) -> HttpResponse:
    payload = json.loads(request.body or "{}")
    form = OrderForm(_to_form_data(payload))
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": _to_client_errors(form.errors)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "total": str(form.total()),
            "discounted_total": str(form.discounted_total()),
        }
    )


@require_GET
def check_coupon(request: HttpRequest) -> HttpResponse:
    code = (request.GET.get("code") or "").strip()
    return JsonResponse({"valid": bool(code) and lookup_coupon(code) is not None})
