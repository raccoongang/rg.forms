"""Views for the edit/CRUD workflow example."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms import reactive_validate

from .. import services
from ..forms import AccountEditForm


def account_edit(request: HttpRequest) -> HttpResponse:
    # ?staff=1 stands in for a server-side permission check (request.user.is_staff).
    can_see_internal = request.GET.get("staff") == "1"
    saved = False
    if request.method == "POST":
        form = AccountEditForm(request.POST, can_see_internal=can_see_internal)
        if form.is_valid():
            services.save_account(form.cleaned_data)
            saved = True
            # Re-bind from the freshly saved record (post-save view).
            form = AccountEditForm(initial=services.get_account(), can_see_internal=can_see_internal)
    else:
        form = AccountEditForm(initial=services.get_account(), can_see_internal=can_see_internal)
    return render(
        request,
        "examples/edit_crud/page.html",
        {"form": form, "saved": saved, "can_see_internal": can_see_internal},
    )


def account_edit_validate(request: HttpRequest) -> HttpResponse:
    return reactive_validate(request, AccountEditForm)
