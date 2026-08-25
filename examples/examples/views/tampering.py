"""Views for the security / tampering laboratory.

Each row runs a *crafted* submission server-side and shows the authoritative
outcome, making "the server decides" tangible rather than asserted.
"""

from __future__ import annotations

from decimal import Decimal

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms.scoping import encode_scope
from rg.forms.views import resolve_validate_field

from ..forms import FeatureFlaggedForm, OrderConfiguratorForm, ProfileForm


def _scenarios() -> list[dict]:
    results: list[dict] = []

    # 1. Tampered computed total is ignored (server recomputes exactly).
    f = OrderConfiguratorForm(data={"plan": "010", "seats": "3", "total": "9999", "coupon": ""})
    f.is_valid()
    results.append(
        {
            "title": "Tampered computed total",
            "attempt": "POST total=9999 for plan 010 × 3 seats",
            "result": f"server total = {f.cleaned_data.get('total')}",
            "ok": f.cleaned_data.get("total") == Decimal("87.00"),
        }
    )

    # 2. Client-disabled field enforced (Starter is single-seat).
    f = OrderConfiguratorForm(data={"plan": "001", "seats": "99", "total": "0", "coupon": ""})
    f.is_valid()
    results.append(
        {
            "title": "Client-disabled seats forged",
            "attempt": "POST seats=99 for Starter (seats disabled in the browser)",
            "result": f"server seats = {f.cleaned_data.get('seats')}, total = {f.cleaned_data.get('total')}",
            "ok": f.cleaned_data.get("seats") == 1,
        }
    )

    # 3. Hidden field skipped server-side (not required while hidden).
    f = OrderConfiguratorForm(data={"plan": "001", "seats": "1", "enterprise_contact": "sneaked"})
    valid = f.is_valid()
    results.append(
        {
            "title": "Hidden field submitted",
            "attempt": "POST enterprise_contact while it is hidden (plan≠100)",
            "result": f"form valid={valid}; enterprise_contact skipped = {f.cleaned_data.get('enterprise_contact')!r}",
            "ok": valid and not f.cleaned_data.get("enterprise_contact"),
        }
    )

    # 4. Forged requiredness cannot bypass the server rule.
    f = OrderConfiguratorForm(data={"plan": "100", "seats": "1", "enterprise_contact": ""})
    valid = f.is_valid()
    results.append(
        {
            "title": "Forged requiredness",
            "attempt": "Strip the required attr and POST empty enterprise_contact for Enterprise",
            "result": f"form valid={valid}; error = {f.errors.get('enterprise_contact', ['—'])[0]}",
            "ok": (not valid) and "enterprise_contact" in f.errors,
        }
    )

    # 5. Wrong scope rejected (a scope for another form does not resolve).
    profile = ProfileForm(prefix="profile")
    wrong = f"rgForms.{encode_scope('notifications')}.email"
    resolved = resolve_validate_field(profile, wrong)
    results.append(
        {
            "title": "Wrong validation scope",
            "attempt": "Send an incremental-validate trigger scoped to another form",
            "result": f"resolve_validate_field → {resolved!r} (rejected → HTTP 400)",
            "ok": resolved is None,
        }
    )

    # 6. Forged external signal ignored (not read from form data).
    forged = FeatureFlaggedForm(data={"name": "x", "plan_tier": "paid", "priority_support": "on"}, plan_tier="free")
    forged.is_valid()
    results.append(
        {
            "title": "Forged external signal",
            "attempt": "POST plan_tier=paid in the form body (server policy = free)",
            "result": f"priority_support visible on server = {forged.is_field_visible('priority_support')}",
            "ok": forged.is_field_visible("priority_support") is False,
        }
    )

    return results


def tampering_lab(request: HttpRequest) -> HttpResponse:
    return render(request, "examples/tampering/page.html", {"scenarios": _scenarios()})
