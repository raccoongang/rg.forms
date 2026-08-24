"""Example 3 — Team roster, a static Django formset (ADR-0001/0002/0003).

Every row renders the same logical field names, yet each row's reactive rules
fire independently thanks to scoped signals. This demonstrates *static* rows;
dynamic add/remove/reorder is deliberately out of scope for now.
"""

from __future__ import annotations

from rg.forms import ReactiveCharField, ReactiveChoiceField, ReactiveEmailField, ReactiveForm


class TeamMemberForm(ReactiveForm):
    full_name = ReactiveCharField(label="Full name", placeholder="Jane Doe", autocomplete="name")
    role = ReactiveChoiceField(
        label="Role",
        choices=[
            ("", "-- Select --"),
            ("owner", "Owner"),
            ("admin", "Admin"),
            ("editor", "Editor"),
            ("viewer", "Viewer"),
        ],
    )
    # Per-row conditional requirement: owners/admins must give an email.
    email = ReactiveEmailField(
        label="Email",
        required=False,
        placeholder="jane@example.com",
        autocomplete="email",
        required_when="$role == 'owner' || $role == 'admin'",
    )
    # Per-row conditional visibility: only admins get an escalation note.
    admin_note = ReactiveCharField(
        label="Admin note",
        required=False,
        visible_when="$role == 'admin'",
        help_text="Only shown for admins — and only for this row.",
    )
