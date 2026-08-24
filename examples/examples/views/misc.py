"""Index and static informational pages."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# The example catalog, with the ADR/feature tags shown on each index card.
EXAMPLES = [
    {
        "title": "Account registration",
        "subtitle": "Incremental validation on blur",
        "blurb": "Live username/email availability checks; the same Django rules run on submit.",
        "tags": ["ADR-0001", "ADR-0004", "validate_on", "CSRF"],
        "url": "examples:registration",
    },
    {
        "title": "Order configurator",
        "subtitle": "Conditional fields + exact Decimal",
        "blurb": "visible/required/disabled/read-only + a server-recomputed Decimal total; string code '001'.",
        "tags": ["ADR-0001", "ADR-0002", "computed", "Decimal"],
        "url": "examples:order_configurator",
    },
    {
        "title": "Team roster",
        "subtitle": "Static formset, per-row reactivity",
        "blurb": "Each row's rules fire independently via scoped signals. Static rows (no add/remove yet).",
        "tags": ["ADR-0003", "formset", "scoped signals"],
        "url": "examples:team_roster",
    },
    {
        "title": "Settings dashboard",
        "subtitle": "Several prefixed forms, one page",
        "blurb": "Overlapping field names, independent scopes, per-form incremental validation.",
        "tags": ["ADR-0003", "ADR-0004", "prefixes"],
        "url": "examples:settings_dashboard",
    },
    {
        "title": "Feature-flagged form",
        "subtitle": "Server-owned external signals",
        "blurb": "A permission/plan/flag drives the same rule on client and server; clients can't forge it.",
        "tags": ["ADR-0002", "external_signals"],
        "url": "examples:feature_flags",
    },
    {
        "title": "Canonical values lab",
        "subtitle": "The value model, explained",
        "blurb": "String codes, number/decimal split, checkbox=false, arrays, /0→null, non-finite→null.",
        "tags": ["ADR-0002", "semantics"],
        "url": "examples:canonical_values",
    },
    {
        "title": "Design-system override",
        "subtitle": "One form, two renderers",
        "blurb": "The same contract rendered by the shipped Bulma adapter and a minimal utility adapter.",
        "tags": ["ADR-0001", "bind_attr", "control_attrs"],
        "url": "examples:design_systems",
    },
    {
        "title": "Business onboarding",
        "subtitle": "A larger grouped form",
        "blurb": "Grouped visibility, cross-field rules, one incremental field, an exact computed total.",
        "tags": ["ADR-0001", "ADR-0002", "ADR-0004", "field groups"],
        "url": "examples:onboarding",
    },
    {
        "title": "Cascading dropdowns",
        "subtitle": "Dependent selects (retained)",
        "blurb": "choices_from + depends_on with server re-render — a distinct feature.",
        "tags": ["choices_from", "depends_on"],
        "url": "examples:cascading_form",
    },
    {
        "title": "Whole-form SSE submit",
        "subtitle": "Fragment patch on submit (retained)",
        "blurb": "reactive_form_response() patches the entire form fragment — contrast with per-field #1.",
        "tags": ["SSE", "reactive_form_response"],
        "url": "examples:sse_validation",
    },
]


def index(request: HttpRequest) -> HttpResponse:
    return render(request, "examples/index.html", {"examples": EXAMPLES})


def risks(request: HttpRequest) -> HttpResponse:
    return render(request, "examples/risks.html")
