"""ReactiveForm - Base class for reactive Django forms with Datastar integration."""

from django import forms


class ReactiveForm(forms.Form):
    """Base class for reactive Django forms.

    Extends django.forms.Form to add:
    - Automatic Datastar signal generation
    - Field visibility rules (visible_when)
    - Field requirement rules (required_when)
    - Computed field support
    - Remote data fetching
    - Cross-field validation with visibility awareness

    Usage:
        class OrderForm(ReactiveForm):
            order_type = ReactiveChoiceField(choices=[...])
            priority = ReactiveChoiceField(
                choices=[...],
                visible_when="$order_type == 'urgent'"
            )
    """

    def get_signals(self) -> dict:
        """Generate initial signals dict for Datastar.

        Returns signal values from form.data if bound, else from form.initial.
        """
        signals = {}
        for name, field in self.fields.items():
            if self.is_bound and name in self.data:
                signals[name] = self.data.get(name)
            elif name in self.initial:
                signals[name] = self.initial[name]
            elif hasattr(field, "initial") and field.initial is not None:
                signals[name] = field.initial
            else:
                signals[name] = ""
        return signals

    def get_signals_json(self) -> str:
        """Return signals as JSON string for data-signals attribute."""
        import json

        return json.dumps(self.get_signals())

    def get_field_reactive_attrs(self, field_name: str) -> dict:
        """Get reactive attributes for a specific field.

        Returns a dict with keys like 'visible_when', 'required_when', 'computed'.
        Only includes attributes that are set (not None).
        """
        field = self.fields.get(field_name)
        if not field:
            return {}

        attrs = {}
        for attr in ("visible_when", "required_when", "computed", "depends_on"):
            value = getattr(field, attr, None)
            if value is not None:
                attrs[attr] = value

        return attrs

    def get_visible_fields(self) -> list[str]:
        """Get list of field names that have visibility rules."""
        return [
            name for name, field in self.fields.items()
            if getattr(field, "visible_when", None)
        ]

    def get_computed_fields(self) -> list[str]:
        """Get list of field names that are computed."""
        return [
            name for name, field in self.fields.items()
            if getattr(field, "computed", None)
        ]

    def is_field_visible(self, field_name: str, data: dict | None = None) -> bool:
        """Evaluate if a field should be visible based on current data.

        Server-side evaluation of visible_when rules.
        For now, returns True - full AST evaluation will be implemented.
        """
        field = self.fields.get(field_name)
        if not field:
            return False

        visible_when = getattr(field, "visible_when", None)
        if visible_when is None:
            return True

        # TODO: Implement AST-based rule evaluation
        # For now, always visible on server side
        return True
