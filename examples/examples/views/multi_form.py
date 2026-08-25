"""Example 9 — Multi-form reactive submission (ADR-0005).

Three members — a staff-user form, a profile form, and a work-experience formset
— are validated and submitted together with a single ``reactive_forms_response``
call. On any error the shared fragment is patched via SSE (every member's errors
at once, non-short-circuit); on all-valid the caller's ``on_success`` runs the
persistence and the view redirects.

Signal seeding: each member is prefixed, so its ``data-signals`` seed is nested
under its own scope (ADR-0003). The seeds are merged in the view into one JSON
object on the wrapping ``<form>`` (the merge is the caller's concern — a single
form or formset tag cannot see its siblings).
"""

from __future__ import annotations

import json
from typing import Any

from datastar_py.django import DatastarResponse
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms import reactive_forms_response

from ..forms import StaffUserForm, UserProfileForm, WorkExperienceFormSet
from ..forms.multi_form import MIN_WORKING_AGE


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge ``overlay`` into ``base`` (nested scope dicts don't clobber)."""
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _merged_signals(user_form: Any, profile_form: Any, formset: Any) -> str:
    """One ``data-signals`` JSON seed spanning both forms and every formset row."""
    merged: dict = {}
    _deep_merge(merged, user_form.get_seed_signals())
    _deep_merge(merged, profile_form.get_seed_signals())
    for row in formset.forms:
        _deep_merge(merged, row.get_seed_signals())
    return json.dumps(merged)


def _check_working_age(profile_form: Any, formset: Any) -> None:
    """Cross-form invariant (D5): work history must not predate a plausible age.

    Attached *before* ``reactive_forms_response`` runs its success branch — the
    helper re-checks ``is_valid()`` (cached), so the attached error routes to the
    error patch and blocks the redirect.
    """
    birth_year = profile_form.cleaned_data.get("birth_year")
    start_years = [f.cleaned_data.get("start_year") for f in formset.forms if f.cleaned_data.get("start_year")]
    if birth_year and start_years:
        earliest = min(start_years)
        if earliest < birth_year + MIN_WORKING_AGE:
            profile_form.add_error(
                "birth_year",
                f"Work history starts in {earliest}, before age {MIN_WORKING_AGE} for someone born in {birth_year}.",
            )


def user_create(request: HttpRequest) -> HttpResponse | DatastarResponse:
    action_url = request.build_absolute_uri()

    if request.method == "POST":
        user_form = StaffUserForm(request.POST, prefix="user")
        profile_form = UserProfileForm(request.POST, prefix="profile")
        formset = WorkExperienceFormSet(request.POST, prefix="work")

        # Populate cleaned_data + cache errors for every member, then attach the
        # cross-form error while all three are still individually valid (D5).
        if user_form.is_valid() & profile_form.is_valid() & formset.is_valid():
            _check_working_age(profile_form, formset)

        def _on_success() -> None:
            # A production view would persist all three atomically here:
            #     with transaction.atomic():
            #         create_staff_user(user_form, profile_form, formset)
            # The example only demonstrates the plumbing, so it saves nothing and
            # falls through to the success redirect.
            return None

        response = reactive_forms_response(
            request,
            [user_form, profile_form, formset],
            "examples/multi_form/_form.html",
            context={
                "user_form": user_form,
                "profile_form": profile_form,
                "formset": formset,
                "signals_json": _merged_signals(user_form, profile_form, formset),
                "action": action_url,
            },
            success_url=request.path + "?created=1",
            on_success=_on_success,
        )
        if response:
            return response
    else:
        user_form = StaffUserForm(prefix="user")
        profile_form = UserProfileForm(prefix="profile")
        formset = WorkExperienceFormSet(prefix="work")

    return render(
        request,
        "examples/multi_form/page.html",
        {
            "user_form": user_form,
            "profile_form": profile_form,
            "formset": formset,
            "signals_json": _merged_signals(user_form, profile_form, formset),
            "action": action_url,
            "created": request.GET.get("created"),
        },
    )
