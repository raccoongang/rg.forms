"""ReactiveForm - Base class for reactive Django forms with Datastar integration."""

from django import forms
from django.core.exceptions import ValidationError

from .expressions import ExpressionError, evaluate_expression


class FieldGroup:
    """Defines a group of fields with shared attributes.

    Attributes:
        fields: List of field names in this group
        label: Display label for the group (optional)
        visible_when: Datastar expression for group visibility
        description: Help text for the group (optional)
        css_class: Additional CSS class for the group container
    """

    def __init__(
        self,
        fields: list[str],
        label: str | None = None,
        visible_when: str | None = None,
        description: str | None = None,
        css_class: str | None = None,
    ):
        self.fields = fields
        self.label = label
        self.visible_when = visible_when
        self.description = description
        self.css_class = css_class


class ReactiveFormMeta:
    """Meta options for ReactiveForm.

    Attributes:
        field_groups: Dict of group_name -> FieldGroup for organizing fields
    """

    field_groups: dict[str, FieldGroup] | None = None


class ReactiveForm(forms.Form):
    """Base class for reactive Django forms.

    Extends django.forms.Form to add:
    - Automatic Datastar signal generation
    - Field visibility rules (visible_when)
    - Field requirement rules (required_when)
    - Computed field support
    - Declarative cascading choices (choices_from + depends_on)
    - Cross-field validation with visibility awareness
    - Field groups with shared visibility

    Usage:
        class OrderForm(ReactiveForm):
            order_type = ReactiveChoiceField(choices=[...])
            priority = ReactiveChoiceField(
                choices=[...],
                visible_when="$order_type == 'urgent'"
            )

    Cascading example:
        class CascadingForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
                empty_choice="-- Select Category --",
            )
            product = ReactiveChoiceField(
                choices_from=get_products_for_category,
                depends_on=["category"],
                value_field="id",
                label_field="name",
                empty_choice="-- Select Product --",
                empty_choice_no_parent="-- Select Category First --",
            )

    Field groups example:
        class RegistrationForm(ReactiveForm):
            account_type = ReactiveChoiceField(choices=[...])
            username = ReactiveCharField()
            email = ReactiveEmailField()
            company_name = ReactiveCharField()
            company_size = ReactiveIntegerField()

            class Meta:
                field_groups = {
                    'account': FieldGroup(
                        fields=['account_type', 'username', 'email'],
                        label='Account Information',
                    ),
                    'company': FieldGroup(
                        fields=['company_name', 'company_size'],
                        label='Company Details',
                        visible_when="$account_type == 'business'",
                    ),
                }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._populate_cascading_fields()

    def _get_field_value(self, field_name: str) -> str | None:
        """Get current value of a field from bound data or initial."""
        if self.is_bound and self.data.get(field_name):
            return self.data.get(field_name)
        elif self.initial.get(field_name):
            return self.initial.get(field_name)
        return None

    def _build_choices_from_data(
        self,
        data,
        field,
    ) -> list[tuple[str, str]]:
        """Build choices list from data using field's configuration.

        Args:
            data: Iterable of objects (queryset, list of dicts, list of objects)
            field: The ReactiveChoiceField with configuration
        """
        choices = []
        value_field = getattr(field, "value_field", "pk")
        label_field = getattr(field, "label_field", None)
        label_template = getattr(field, "label_template", None)

        for obj in data:
            # Get value - support both dict and object access
            if isinstance(obj, dict):
                value = obj.get(value_field)
            else:
                value = getattr(obj, value_field)
                if callable(value):
                    value = value()

            # Get label
            if label_template:
                # Format template with object attributes
                if isinstance(obj, dict):
                    label = label_template.format(**obj)
                else:
                    label = label_template.format(**obj.__dict__)
            elif label_field:
                if isinstance(obj, dict):
                    label = obj.get(label_field)
                else:
                    label = getattr(obj, label_field)
                    if callable(label):
                        label = label()
            else:
                label = str(obj)

            choices.append((str(value), label))

        return choices

    def _populate_cascading_fields(self) -> None:
        """Auto-populate fields that have choices_from defined.

        Processes fields in order:
        1. Fields without depends_on (root fields) - call choices_from()
        2. Fields with depends_on (dependent fields) - call choices_from(parent_value)
        """
        for field_name, field in self.fields.items():
            choices_from = getattr(field, "choices_from", None)
            if not choices_from:
                continue

            depends_on = getattr(field, "depends_on", None) or []
            empty_choice = getattr(field, "empty_choice", None)
            empty_choice_no_parent = getattr(field, "empty_choice_no_parent", None)

            # Build choices list
            choices = []

            if depends_on:
                # Dependent field - get parent value first
                # Support single string or list for depends_on
                if isinstance(depends_on, str):
                    parent_field = depends_on
                else:
                    parent_field = depends_on[0]  # Use first dependency

                parent_value = self._get_field_value(parent_field)

                if parent_value:
                    # Parent has value - populate from choices_from(parent_value)
                    if empty_choice:
                        choices.append(("", empty_choice))
                    data = choices_from(parent_value)
                    choices.extend(self._build_choices_from_data(data, field))

                    # Check if current value is valid for new parent
                    if self.is_bound:
                        current_value = self.data.get(field_name)
                        if current_value:
                            valid_values = [c[0] for c in choices]
                            if current_value not in valid_values:
                                # Reset invalid value
                                self.data = self.data.copy()
                                self.data[field_name] = ""
                else:
                    # No parent value - show placeholder
                    placeholder = empty_choice_no_parent or empty_choice or "-- Select --"
                    choices.append(("", placeholder))
            else:
                # Root field - call choices_from() without arguments
                if empty_choice:
                    choices.append(("", empty_choice))
                data = choices_from()
                choices.extend(self._build_choices_from_data(data, field))

            field.choices = choices

    def get_field_groups(self) -> dict[str, "FieldGroup"]:
        """Get field groups defined in Meta.

        Returns empty dict if no groups defined.
        """
        meta = getattr(self, "Meta", None)
        if meta is None:
            return {}
        return getattr(meta, "field_groups", {}) or {}

    def get_group(self, group_name: str) -> "FieldGroup | None":
        """Get a specific field group by name."""
        return self.get_field_groups().get(group_name)

    def get_fields_in_group(self, group_name: str) -> list:
        """Get BoundField objects for fields in a group.

        Returns list of (field_name, bound_field) tuples.
        """
        group = self.get_group(group_name)
        if not group:
            return []
        return [(name, self[name]) for name in group.fields if name in self.fields]

    def is_group_visible(self, group_name: str) -> bool:
        """Evaluate if a group should be visible.

        Server-side evaluation of group's visible_when.
        """
        group = self.get_group(group_name)
        if not group:
            return False

        if group.visible_when is None:
            return True

        result = self._evaluate_expression(group.visible_when)
        if result is None:
            return True
        return bool(result)

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
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        def default(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, time):
                return obj.isoformat()
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, UUID):
                return str(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        return json.dumps(self.get_signals(), default=default)

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

    def _get_form_data(self) -> dict:
        """Get current form data for expression evaluation.

        Uses .get() to extract scalar values from QueryDict (which
        stores values as lists internally).
        """
        if self.is_bound:
            return {key: self.data.get(key) for key in self.data}
        return dict(self.initial)

    def _evaluate_expression(self, expression: str) -> bool | None:
        """Safely evaluate an expression, returning None on error."""
        try:
            return evaluate_expression(expression, self._get_form_data())
        except ExpressionError:
            # Log error in debug mode, but don't break form
            return None

    def is_field_visible(self, field_name: str, data: dict | None = None) -> bool:
        """Evaluate if a field should be visible based on current data.

        Server-side evaluation of visible_when rules.
        """
        field = self.fields.get(field_name)
        if not field:
            return False

        visible_when = getattr(field, "visible_when", None)
        if visible_when is None:
            return True

        result = self._evaluate_expression(visible_when)
        if result is None:
            # On error, default to visible
            return True
        return bool(result)

    def is_field_required(self, field_name: str) -> bool:
        """Evaluate if a field is required based on required_when.

        Combines static required and dynamic required_when.
        """
        field = self.fields.get(field_name)
        if not field:
            return False

        # Static required
        if field.required:
            return True

        # Dynamic required_when
        required_when = getattr(field, "required_when", None)
        if required_when is None:
            return False

        result = self._evaluate_expression(required_when)
        if result is None:
            return False
        return bool(result)

    def get_computed_value(self, field_name: str):
        """Compute a field's value from its expression."""
        field = self.fields.get(field_name)
        if not field:
            return None

        computed = getattr(field, "computed", None)
        if computed is None:
            return None

        return self._evaluate_expression(computed)

    def _clean_fields(self):
        """Override to skip hidden fields and enforce required_when."""
        for name, bf in self._bound_items():
            field = bf.field

            # Skip hidden fields (visible_when=false)
            if not self.is_field_visible(name):
                # Set to None/empty in cleaned_data
                self.cleaned_data[name] = None
                continue

            # Get raw value
            value = bf.initial if field.disabled else bf.data
            try:
                if isinstance(field, forms.FileField):
                    value = field.clean(value, bf.initial)
                else:
                    value = field.clean(value)

                # Handle computed fields - recalculate on server
                computed = getattr(field, "computed", None)
                if computed is not None:
                    computed_value = self.get_computed_value(name)
                    if computed_value is not None:
                        value = computed_value

                self.cleaned_data[name] = value

                # Check required_when
                required_when = getattr(field, "required_when", None)
                if required_when is not None:
                    is_required = self._evaluate_expression(required_when)
                    if is_required and not value and value != 0:
                        raise ValidationError(
                            field.error_messages.get("required", "This field is required."),
                            code="required",
                        )

                # Call clean_<fieldname> if exists
                if hasattr(self, "clean_%s" % name):
                    value = getattr(self, "clean_%s" % name)()
                    self.cleaned_data[name] = value

            except ValidationError as e:
                self.add_error(name, e)

    def populate(
        self,
        field_name: str,
        queryset,
        label_field: str | None = None,
        value_field: str = "pk",
        add_empty: bool = False,
        empty_label: str = "-- Select --",
        empty_value: str = "",
    ) -> None:
        """Populate a ChoiceField's choices from a queryset.

        Use this in __init__ to dynamically set choices based on context
        (related objects, user permissions, current state, etc.)

        Args:
            field_name: Name of the ChoiceField to populate
            queryset: QuerySet or iterable of model instances
            label_field: Model field/property/method for display label (default: str(obj))
            value_field: Model field for option value (default: 'pk')
            add_empty: Prepend an empty choice option
            empty_label: Label for empty choice
            empty_value: Value for empty choice

        Example:
            def __init__(self, supplier=None, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if supplier:
                    items = Item.objects.filter(supplier=supplier)
                    self.populate('item', items, label_field='name')
        """
        field = self.fields.get(field_name)
        if field is None:
            raise ValueError(f"Field '{field_name}' not found in form")

        choices = []
        if add_empty:
            choices.append((empty_value, empty_label))

        for obj in queryset:
            # Get value
            value = getattr(obj, value_field)
            if callable(value):
                value = value()

            # Get label
            if label_field:
                label = getattr(obj, label_field)
                if callable(label):
                    label = label()
            else:
                label = str(obj)

            choices.append((str(value), label))

        field.choices = choices
