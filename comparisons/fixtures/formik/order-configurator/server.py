# Illustrative comparison fixture — not executed. Idiomatic Formik (v2.x, React 18) per official docs, as of 2026-08. Written for the rg.forms comparison (docs/comparisons/methodology.md).
"""Django counterpart for the Formik order configurator.

The server owns the pricing. It recomputes the total as an exact ``Decimal`` from
the plan's real unit price and the submitted seat count, ignoring any client-side
preview total, and it validates the coupon against the authoritative catalog.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django import forms
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST

# Plan codes stay strings — "001" must never collapse to the int 1.
PLANS = {
    "001": {"name": "Starter", "unit_price": Decimal("9.00")},
    "010": {"name": "Team", "unit_price": Decimal("29.00")},
    "100": {"name": "Enterprise", "unit_price": Decimal("99.00")},
}

COUPONS = {
    "WELCOME10": {"discount": 10},
    "SAVE20": {"discount": 20},
    "LAUNCH50": {"discount": 50},
}


def lookup_coupon(code: str) -> dict | None:
    return COUPONS.get(code.strip().upper())


class OrderForm(forms.Form):
    plan = forms.ChoiceField(choices=[(c, PLANS[c]["name"]) for c in PLANS])
    enterprise_contact = forms.CharField(required=False)
    seats = forms.IntegerField(min_value=1)
    coupon = forms.CharField(required=False)

    def clean_coupon(self) -> str:
        code = (self.cleaned_data.get("coupon") or "").strip().upper()
        if code and lookup_coupon(code) is None:
            raise forms.ValidationError(f"Coupon '{code}' is not valid.")
        return code

    def clean(self) -> dict:
        cleaned = super().clean()
        if cleaned.get("plan") == "100" and not (cleaned.get("enterprise_contact") or "").strip():
            self.add_error("enterprise_contact", "Enterprise orders need a contact name.")
        # Starter is single-seat; silently clamp rather than trust the client.
        if cleaned.get("plan") == "001":
            cleaned["seats"] = 1
        return cleaned

    def totals(self) -> dict:
        """Authoritative Decimal recompute — never trust a submitted total."""
        plan = PLANS[self.cleaned_data["plan"]]
        seats = self.cleaned_data["seats"]
        total = (plan["unit_price"] * seats).quantize(Decimal("0.01"))
        coupon = lookup_coupon(self.cleaned_data.get("coupon") or "")
        discounted = total
        if coupon:
            discounted = (
                total * (Decimal(100) - Decimal(coupon["discount"])) / Decimal(100)
            ).quantize(Decimal("0.01"))
        return {
            "plan": self.cleaned_data["plan"],
            "seats": seats,
            "unit_price": str(plan["unit_price"]),
            "total": str(total),
            "discounted_total": str(discounted),
        }


@require_GET
def validate_coupon(request: HttpRequest) -> JsonResponse:
    code = request.GET.get("code", "").strip().upper()
    coupon = lookup_coupon(code)
    if coupon is None:
        return JsonResponse(
            {"valid": False, "discountPercent": 0, "message": f"Coupon '{code}' is not valid."}
        )
    return JsonResponse({"valid": True, "discountPercent": coupon["discount"], "message": None})


@require_POST
def place_order(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"errors": {"__all__": ["Malformed request body."]}}, status=400)

    form = OrderForm(
        {
            "plan": payload.get("plan", ""),
            "enterprise_contact": payload.get("enterpriseContact", ""),
            "seats": payload.get("seats", ""),
            "coupon": payload.get("coupon", ""),
        }
    )
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)

    return JsonResponse({"ok": True, **form.totals()})
