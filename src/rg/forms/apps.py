"""Django app configuration for rg.forms."""

from django.apps import AppConfig


class RgFormsConfig(AppConfig):
    """Django app config for rg.forms."""

    name = "rg.forms"
    label = "rg_forms"
    verbose_name = "Reactive Forms"
    default_auto_field = "django.db.models.BigAutoField"
