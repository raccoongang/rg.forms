"""Views for Example 3 — team roster (static formset)."""

from __future__ import annotations

from django.forms import formset_factory
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..forms import TeamMemberForm

TeamFormSet = formset_factory(TeamMemberForm, extra=2)


def team_roster(request: HttpRequest) -> HttpResponse:
    saved = None
    if request.method == "POST":
        formset = TeamFormSet(request.POST)
        if formset.is_valid():
            saved = [f.cleaned_data for f in formset.forms if f.cleaned_data]
    else:
        formset = TeamFormSet()
    return render(request, "examples/team_formset/page.html", {"formset": formset, "saved": saved})
