"""Example reactive forms, one module per scenario (see docs/examples.md)."""

from .canonical_values import CanonicalValuesForm
from .cascading import CascadingForm
from .design_systems import ProfileCardForm
from .external_signals import FeatureFlaggedForm
from .onboarding import OnboardingForm
from .order_configurator import OrderConfiguratorForm
from .registration import RegistrationForm
from .settings_dashboard import NotificationsForm, ProfileForm
from .sse import SSEValidationForm
from .team_formset import TeamMemberForm

__all__ = [
    "CanonicalValuesForm",
    "CascadingForm",
    "FeatureFlaggedForm",
    "NotificationsForm",
    "OnboardingForm",
    "OrderConfiguratorForm",
    "ProfileCardForm",
    "ProfileForm",
    "RegistrationForm",
    "SSEValidationForm",
    "TeamMemberForm",
]
