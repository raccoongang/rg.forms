"""Example views, one module per scenario (see docs/examples.md)."""

from .canonical_values import canonical_values
from .cascading import cascading_form
from .design_systems import design_systems, design_systems_validate
from .external_signals import feature_flags
from .misc import index, risks
from .onboarding import onboarding, onboarding_validate
from .order_configurator import order_configurator
from .registration import registration, registration_validate
from .settings_dashboard import profile_validate, settings_dashboard
from .sse import sse_validation
from .team_formset import team_roster

__all__ = [
    "canonical_values",
    "cascading_form",
    "design_systems",
    "design_systems_validate",
    "feature_flags",
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
    "team_roster",
]
