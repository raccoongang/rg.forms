"""rg.forms - Reactive Django Forms with Datastar integration."""

__version__ = "0.1.0"

# Core form class
from rg.forms.forms import ReactiveForm

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

__all__ = [
    # Version
    "__version__",
    # Form
    "ReactiveForm",
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
