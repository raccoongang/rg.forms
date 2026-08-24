"""Example 5 — Feature-flagged / permission-aware form (ADR-0002 §5).

A server-owned signal (here a plan tier and a beta flag) drives the *same*
visibility/requiredness rule on the client and the server. The values come from
``get_external_signal_values()`` — they are *external* signals, so the server
never reads them from the submitted form data (a crafted form POST cannot set
them), and a form field always wins over an external value on a name collision.
In this demo the values are chosen by a query parameter standing in for real
server policy (``request.user`` / tenant / a flag service).
"""

from __future__ import annotations

from rg.forms import ReactiveBooleanField, ReactiveCharField, ReactiveChoiceField, ReactiveForm


class FeatureFlaggedForm(ReactiveForm):
    name = ReactiveCharField(label="Project name")

    # Visible only when the server says the tenant is on a paid plan.
    priority_support = ReactiveBooleanField(
        label="Enable priority support",
        required=False,
        visible_when="$plan_tier == 'paid'",
        help_text="Available on paid plans (decided by the server).",
    )
    # Visible + required only when the server has enabled the beta flag.
    beta_feature_opt_in = ReactiveChoiceField(
        label="Beta channel",
        required=False,
        visible_when="$can_use_beta",
        required_when="$can_use_beta",
        choices=[("", "-- Select --"), ("stable", "Stable"), ("edge", "Edge")],
    )

    class Meta:
        # Declaring these authorizes the references; it does not provide values.
        external_signals = {"plan_tier", "can_use_beta"}

    def __init__(self, *args, plan_tier: str = "free", can_use_beta: bool = False, **kwargs):
        self._external = {"plan_tier": plan_tier, "can_use_beta": can_use_beta}
        super().__init__(*args, **kwargs)

    def get_external_signal_values(self) -> dict:
        # Server-owned values, e.g. from request.user / tenant / a flag service.
        return dict(self._external)

    def external_signals_json(self) -> str:
        """Seed the external signals into the page so the client evaluates the
        same rule. (In a real app these come from the page context, never from
        untrusted client input.)"""
        import json

        return json.dumps(self._external)
