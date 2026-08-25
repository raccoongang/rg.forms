"""rg.forms - Reactive Django Forms with Datastar integration."""

__version__ = "0.2.0"

# Reactive fields
from rg.forms.fields import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDateField,
    ReactiveDateTimeField,
    ReactiveDecimalField,
    ReactiveEmailField,
    ReactiveFloatField,
    ReactiveIntegerField,
    ReactiveMultipleChoiceField,
    ReactiveTimeField,
    ReactiveURLField,
)

# Core form class and utilities
from rg.forms.forms import FieldGroup, ReactiveForm

# View utilities
from rg.forms.views import (
    is_datastar_request,
    reactive_form_response,
    reactive_forms_response,
    reactive_validate,
    reactive_validate_response,
    sse_redirect,
)

__all__ = [
    # Version
    "__version__",
    # Form
    "ReactiveForm",
    "FieldGroup",
    # View utilities
    "is_datastar_request",
    "reactive_form_response",
    "reactive_forms_response",
    "reactive_validate",
    "reactive_validate_response",
    "sse_redirect",
    # Fields
    "ReactiveBooleanField",
    "ReactiveCharField",
    "ReactiveChoiceField",
    "ReactiveDateField",
    "ReactiveDateTimeField",
    "ReactiveDecimalField",
    "ReactiveEmailField",
    "ReactiveFloatField",
    "ReactiveIntegerField",
    "ReactiveMultipleChoiceField",
    "ReactiveTimeField",
    "ReactiveURLField",
]
