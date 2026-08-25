"""Example 9 — Multi-form reactive submission (ADR-0005).

An aggregate "create staff user" screen: three members submitted together and
persisted atomically — a :class:`StaffUserForm`, a :class:`UserProfileForm`, and
a formset of :class:`WorkExperienceForm` rows. The view drives them with a single
``reactive_forms_response()`` call (see ``views/multi_form.py``).

Each member is prefixed, so its signals live under its own scope (ADR-0003) and
the three seed dicts merge without collision. The cross-form rule below — a work
history that predates a plausible working age — is a genuine aggregate invariant
that can only be checked once *both* the profile form and the formset are valid,
so it is attached by the caller **before** the success branch (ADR-0005 D5).
"""

from __future__ import annotations

from django.forms import formset_factory

from rg.forms import (
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveEmailField,
    ReactiveForm,
    ReactiveIntegerField,
)

MIN_WORKING_AGE = 16


class StaffUserForm(ReactiveForm):
    """The account itself. Rendered with ``prefix="user"``."""

    username = ReactiveCharField(label="Username", min_length=3, max_length=30, autocomplete="username")
    email = ReactiveEmailField(label="Email", autocomplete="email")
    role = ReactiveChoiceField(
        label="Role",
        choices=[("staff", "Staff"), ("manager", "Manager")],
    )


class UserProfileForm(ReactiveForm):
    """Personal profile for the account. Rendered with ``prefix="profile"``."""

    full_name = ReactiveCharField(label="Full name", placeholder="Jane Doe", autocomplete="name")
    birth_year = ReactiveIntegerField(label="Birth year", min_value=1900, max_value=2025)
    bio = ReactiveCharField(label="Bio", required=False)


class WorkExperienceForm(ReactiveForm):
    """One work-history row. The formset is rendered with ``prefix="work"``."""

    company = ReactiveCharField(label="Company", required=False)
    title = ReactiveCharField(label="Title", required=False)
    start_year = ReactiveIntegerField(label="Start year", required=False, min_value=1900, max_value=2025)


WorkExperienceFormSet = formset_factory(WorkExperienceForm, extra=2)
