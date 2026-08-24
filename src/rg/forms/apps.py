"""Django app configuration for rg.forms."""

from django.apps import AppConfig
from django.core.checks import register


class RgFormsConfig(AppConfig):
    """Django app config for rg.forms."""

    name = "rg.forms"
    label = "rg_forms"
    verbose_name = "Reactive Forms"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Register the reactive-expression system check (ADR-0002 §5).
        from .checks import check_reactive_forms

        register(check_reactive_forms)
