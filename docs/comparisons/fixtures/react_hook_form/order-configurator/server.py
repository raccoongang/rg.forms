# Illustrative comparison fixture — not executed. Idiomatic React Hook Form v7 + Zod, React 18, per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
#
# Django backend counterpart. It RE-VALIDATES the plan/seat/coupon rules the
# client declares in schema.ts and RECOMPUTES the total as an exact Decimal.
# The client only ever shows a float preview; this server value is authoritative
# and any total submitted by the client would be ignored. The duplication of
# rules between the TS client and this Python server is what the comparison
# measures.
from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

# --- Stand-in catalog (mirrors the example services) -------------------------
PLANS = {
    "001": {"code": "001", "name": "Starter", "unit_price": Decimal("9.00")},
    "010": {"code": "010", "name": "Team", "unit_price": Decimal("29.00")},
    "100": {"code": "100", "name": "Enterprise", "unit_price": Decimal("99.00")},
}
VALID_COUPONS = {
    "WELCOME10": {"discount": 10},
    "SAVE20": {"discount": 20},
    "LAUNCH50": {"discount": 50},
}


class OrderForm(forms.Form):
    # Codes stay strings; leading zero must survive ("001" != 1).
    plan = forms.ChoiceField(choices=[(code, p["name"]) for code, p in PLANS.items()])
    enterprise_contact = forms.CharField(required=False)
    seats = forms.IntegerField(min_value=1)
    coupon = forms.CharField(required=False)

    def clean_coupon(self) -> str:
        code = (self.cleaned_data.get("coupon") or "").strip().upper()
        if code and code not in VALID_COUPONS:
            raise ValidationError(f"Coupon '{code}' is not valid.")
        return code

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("plan") == "100" and not (cleaned.get("enterprise_contact") or "").strip():
            self.add_error("enterprise_contact", "Enterprise orders require a contact name.")
        return cleaned

    # --- Authoritative money math (exact Decimal) ----------------------------
    def unit_price(self) -> Decimal:
        return PLANS[self.cleaned_data["plan"]]["unit_price"]

    def total(self) -> Decimal:
        return (self.unit_price() * Decimal(self.cleaned_data["seats"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    def discounted_total(self) -> Decimal:
        total = self.total()
        coupon = VALID_COUPONS.get(self.cleaned_data.get("coupon") or "")
        if not coupon:
            return total
        factor = (Decimal(100) - Decimal(coupon["discount"])) / Decimal(100)
        return (total * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


_CLIENT_TO_SERVER = {
    "plan": "plan",
    "enterpriseContact": "enterprise_contact",
    "seats": "seats",
    "coupon": "coupon",
}
_SERVER_TO_CLIENT = {v: k for k, v in _CLIENT_TO_SERVER.items()}


def _to_client_errors(form: OrderForm) -> dict[str, list[str]]:
    return {_SERVER_TO_CLIENT.get(field, field): list(msgs) for field, msgs in form.errors.items()}


@require_POST
def place_order(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    data = {server: payload.get(client) for client, server in _CLIENT_TO_SERVER.items()}
    form = OrderForm(data)
    if not form.is_valid():
        return JsonResponse({"errors": _to_client_errors(form)}, status=400)

    # ... persist the order here ...
    return JsonResponse(
        {"ok": True, "total": str(form.total()), "discountedTotal": str(form.discounted_total())},
        status=201,
    )
