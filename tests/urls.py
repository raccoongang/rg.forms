"""URLconf for the incremental-validation integration tests (ADR-0004)."""

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.template import Context, Template
from django.urls import path

from rg.forms import ReactiveCharField, ReactiveForm, reactive_validate


class DemoValidateForm(ReactiveForm):
    username = ReactiveCharField(validate_on="blur")
    other = ReactiveCharField(required=False)

    def clean_username(self):
        value = self.cleaned_data.get("username", "")
        if value == "taken":
            raise ValidationError("That username is taken.")
        return value


def page(request):
    """Render a form with a CSRF token so the client obtains a masked token."""
    template = Template(
        "{% load reactive_forms %}{% render_reactive_form form action='/submit/' validate_action='/validate/' %}"
    )
    html = template.render(Context({"form": DemoValidateForm(), "csrf_token": get_token(request)}))
    return HttpResponse(html)


def validate(request):
    return reactive_validate(request, DemoValidateForm)


urlpatterns = [
    path("page/", page),
    path("validate/", validate),
]
