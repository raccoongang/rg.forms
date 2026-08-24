"""Views for the server-driven multi-step wizard example."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from ..forms import WizardAccountForm, WizardOrgForm

_SESSION_KEY = "wizard_state"


def _steps(state: dict) -> list[str]:
    # The organization step is skipped for personal accounts (conditional step).
    if state.get("account_type") == "business":
        return ["account", "org", "confirm"]
    return ["account", "confirm"]


def _redirect(step: str) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{reverse('examples:wizard')}?step={step}")


def wizard(request: HttpRequest) -> HttpResponse:
    state = dict(request.session.get(_SESSION_KEY, {}))
    form = None
    if request.method == "POST":
        step = request.POST.get("step", "account")
        if step == "account":
            form = WizardAccountForm(request.POST)
            if form.is_valid():
                state.update(form.cleaned_data)
                request.session[_SESSION_KEY] = state
                return _redirect("org" if state["account_type"] == "business" else "confirm")
        elif step == "org":
            form = WizardOrgForm(request.POST)
            if form.is_valid():
                state.update(form.cleaned_data)
                request.session[_SESSION_KEY] = state
                return _redirect("confirm")
        elif step == "confirm":
            # Finalize: every step was validated in turn and held server-side.
            request.session.pop(_SESSION_KEY, None)
            return render(request, "examples/wizard/done.html", {"state": state})
        # invalid POST falls through to re-render this step's bound form with errors
    else:
        step = request.GET.get("step", "account")
        # Guards: can't jump ahead without prerequisites; skip org for personal.
        if step in ("org", "confirm") and "account_type" not in state:
            return _redirect("account")
        if step == "org" and state.get("account_type") != "business":
            return _redirect("confirm")
        if step == "account":
            form = WizardAccountForm(initial=state)
        elif step == "org":
            form = WizardOrgForm(initial=state)

    return render(
        request,
        "examples/wizard/page.html",
        {"form": form, "step": step, "steps": _steps(state), "state": state},
    )
