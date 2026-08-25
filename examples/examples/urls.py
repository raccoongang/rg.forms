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
    # Additional examples.
    path("account/edit/", views.account_edit, name="account_edit"),
    path("account/edit/validate/", views.account_edit_validate, name="account_edit_validate"),
    path("users/create/", views.user_create, name="user_create"),
    path("wizard/", views.wizard, name="wizard"),
    path("tampering/", views.tampering_lab, name="tampering_lab"),
    path("form-errors/", views.form_errors, name="form_errors"),
    path("datetime/", views.datetime_localization, name="datetime_localization"),
    path("widget-gallery/", views.widget_gallery, name="widget_gallery"),
    # Retained feature demos.
    path("cascading/", views.cascading_form, name="cascading_form"),
    path("sse-validation/", views.sse_validation, name="sse_validation"),
]
