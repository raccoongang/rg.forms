"""URL configuration for examples app."""

from django.urls import path

from . import views

app_name = "examples"

urlpatterns = [
    path("", views.index, name="index"),
    path("risks/", views.risks, name="risks"),
    # The eight matrix examples.
    path("registration/", views.registration, name="registration"),
    path("registration/validate/", views.registration_validate, name="registration_validate"),
    path("order-configurator/", views.order_configurator, name="order_configurator"),
    path("team-roster/", views.team_roster, name="team_roster"),
    path("settings-dashboard/", views.settings_dashboard, name="settings_dashboard"),
    path("settings-dashboard/validate/", views.profile_validate, name="settings_profile_validate"),
    path("feature-flags/", views.feature_flags, name="feature_flags"),
    path("canonical-values/", views.canonical_values, name="canonical_values"),
    path("design-systems/", views.design_systems, name="design_systems"),
    path("design-systems/validate/", views.design_systems_validate, name="design_systems_validate"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("onboarding/validate/", views.onboarding_validate, name="onboarding_validate"),
    # Retained feature demos.
    path("cascading/", views.cascading_form, name="cascading_form"),
    path("sse-validation/", views.sse_validation, name="sse_validation"),
]
