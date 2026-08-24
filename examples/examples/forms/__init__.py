"""Example reactive forms, one module per scenario (see docs/examples.md)."""

from .canonical_values import CanonicalValuesForm
from .cascading import CascadingForm, GeoCascadingForm
from .datetime_localization import EventForm
from .design_systems import ProfileCardForm
from .edit_crud import AccountEditForm
from .external_signals import FeatureFlaggedForm
from .form_errors import ProjectTimelineForm
from .onboarding import OnboardingForm
from .order_configurator import OrderConfiguratorForm
from .registration import RegistrationForm
from .settings_dashboard import NotificationsForm, ProfileForm
from .sse import SSEValidationForm
from .team_formset import TeamMemberForm
from .wizard import WizardAccountForm, WizardOrgForm
from .widget_gallery import WidgetGalleryForm

__all__ = [
    "AccountEditForm",
    "CanonicalValuesForm",
    "CascadingForm",
    "EventForm",
    "FeatureFlaggedForm",
    "GeoCascadingForm",
    "NotificationsForm",
    "OnboardingForm",
    "OrderConfiguratorForm",
    "ProfileCardForm",
    "ProfileForm",
    "ProjectTimelineForm",
    "RegistrationForm",
    "SSEValidationForm",
    "TeamMemberForm",
    "WidgetGalleryForm",
    "WizardAccountForm",
    "WizardOrgForm",
]
