"""Example views, one module per scenario (see docs/examples.md)."""

from .canonical_values import canonical_values
from .cascading import cascading_form
from .datetime_localization import datetime_localization
from .design_systems import design_systems, design_systems_validate
from .edit_crud import account_edit, account_edit_validate
from .external_signals import feature_flags
from .form_errors import form_errors
from .misc import index, risks
from .multi_form import user_create
from .onboarding import onboarding, onboarding_validate
from .order_configurator import order_configurator
from .registration import registration, registration_validate
from .settings_dashboard import profile_validate, settings_dashboard
from .sse import sse_validation
from .tampering import tampering_lab
from .team_formset import team_roster
from .widget_gallery import widget_gallery
from .wizard import wizard

__all__ = [
    "account_edit",
    "account_edit_validate",
    "canonical_values",
    "cascading_form",
    "datetime_localization",
    "design_systems",
    "design_systems_validate",
    "feature_flags",
    "form_errors",
    "index",
    "onboarding",
    "onboarding_validate",
    "order_configurator",
    "profile_validate",
    "registration",
    "registration_validate",
    "risks",
    "settings_dashboard",
    "sse_validation",
    "tampering_lab",
    "user_create",
    "team_roster",
    "widget_gallery",
    "wizard",
]
