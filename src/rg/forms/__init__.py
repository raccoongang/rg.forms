"""rg.forms - Reactive Django Forms with Datastar integration."""

__version__ = "0.1.0"

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
from rg.forms.views import reactive_form_response

__all__ = [
    # Version
    "__version__",
    # Form
    "ReactiveForm",
    "FieldGroup",
    # View utilities
    "reactive_form_response",
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
