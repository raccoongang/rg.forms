"""Views for the retained whole-form SSE-submit demo."""

from __future__ import annotations

from datastar_py.django import DatastarResponse
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rg.forms import reactive_form_response

from ..forms import SSEValidationForm


def sse_validation(request: HttpRequest) -> HttpResponse | DatastarResponse:
    action_url = request.build_absolute_uri()
    if request.method == "POST":
        form = SSEValidationForm(request.POST)
        response = reactive_form_response(
            request,
            form,
            "examples/_sse_validation_fragment.html",
            success_url=request.path + "?success=1",
            context={"action_url": action_url},
        )
        if response:
            return response
    else:
        form = SSEValidationForm()

    return render(
        request,
        "examples/sse_validation.html",
        {"form": form, "action_url": action_url, "success": request.GET.get("success")},
    )
