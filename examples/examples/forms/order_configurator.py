"""Example 2 — Order configurator (ADR-0001/0002).

One Python schema drives conditional visibility, requiredness, disabled/read-only
state, dynamic help text, and an exact-``Decimal`` total the server recomputes
authoritatively. The plan ``code`` is a numeric-looking string with a leading
zero ("001") to demonstrate strict canonical string semantics.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from rg.forms import (
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDecimalField,
    ReactiveForm,
    ReactiveIntegerField,
)

from .. import services

_PLAN_CHOICES = [("", "-- Select a plan --")] + [(p["code"], p["name"]) for p in services.get_plans()]


class OrderConfiguratorForm(ReactiveForm):
    plan = ReactiveChoiceField(label="Plan", choices=_PLAN_CHOICES)

    # Numeric-looking codes: "001" must compare as the string "001", not int 1.
    # visible_when on a leading-zero code proves strict canonical semantics.
    enterprise_contact = ReactiveCharField(
        label="Enterprise contact",
        required=False,
        visible_when="$plan == '100'",
        required_when="$plan == '100'",
        help_text="Enterprise (code 100) orders are handled by an account manager.",
    )

    seats = ReactiveIntegerField(
        label="Seats",
        min_value=1,
        initial=1,
        # Starter (001) is single-seat: disabled so it can't be changed.
        disabled_when="$plan == '001'",
        help_text_when={
            "$plan == '001'": "Starter is a single-seat plan.",
            "$plan == '010'": "Team plans start at 1 seat.",
            "$plan == '100'": "Enterprise seats are negotiated with your manager.",
        },
    )

    unit_price = ReactiveDecimalField(
        label="Unit price",
        decimal_places=2,
        min_value=0,
        read_only_when="true",  # always display-only; set from the chosen plan
        required=False,
        initial="0.00",
    )

    coupon = ReactiveCharField(label="Coupon", required=False, help_text="Try WELCOME10 or SAVE20.")

    # Exact Decimal total. The client shows a float *preview*; the server
    # recomputes authoritatively (a tampered submitted total is ignored).
    total = ReactiveDecimalField(
        label="Total (computed)",
        computed="$seats * $unit_price",
        required=False,
        decimal_places=2,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Reflect the selected plan's price into the (read-only) unit_price so
        # both the preview and the authoritative recompute use the real price.
        code = self._get_field_value("plan")
        plan = services.get_plan(code) if code else None
        if plan:
            self.fields["unit_price"].initial = plan["unit_price"]
            if self.is_bound:
                self.data = self.data.copy()
                # Server-owned unit price (never trust the read-only client field).
                self.data[self.add_prefix("unit_price")] = plan["unit_price"]
                # Starter (001) is single-seat: disabled_when is client-only UX, so
                # enforce the seat count on the server too — a crafted POST that
                # bumps seats is corrected before the total is computed.
                if code == "001":
                    self.data[self.add_prefix("seats")] = "1"

    def clean_coupon(self):
        code = (self.cleaned_data.get("coupon") or "").strip()
        if code and services.lookup_coupon(code) is None:
            raise ValidationError(f"Coupon '{code}' is not valid.")
        return code.upper()

    def discounted_total(self) -> Decimal | None:
        """Convenience for the view/report: apply any coupon to the exact total."""
        total = self.cleaned_data.get("total")
        if total is None:
            return None
        coupon = services.lookup_coupon(self.cleaned_data.get("coupon") or "")
        if not coupon:
            return total
        return (total * (Decimal(100) - Decimal(coupon["discount"])) / Decimal(100)).quantize(Decimal("0.01"))
