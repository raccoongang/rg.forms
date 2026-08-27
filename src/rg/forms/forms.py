"""ReactiveForm - Base class for reactive Django forms with Datastar integration."""

import logging

from django import forms
from django.core.exceptions import ValidationError

from .expressions import ExpressionError, evaluate_expression, is_truthy
from .normalization import normalize_field_value, normalize_from_datadict
from .scoping import RESERVED_NAMESPACE, encode_scope

logger = logging.getLogger("rg.forms")

# Sentinel distinguishing a genuine evaluation error (fail-open) from an
# expression that legitimately evaluated to None/falsy (ADR-0002 P7).
EVAL_ERROR = object()


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
        external_signals: Set of signal names an expression may reference that
            are not form fields (intentional page-level signals). The reserved
            ``rgForms`` namespace may not be declared here (ADR-0002 §5).
    """

    field_groups: dict[str, FieldGroup] | None = None
    external_signals: set[str] | None = None


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

    @property
    def reactive_scope(self) -> str | None:
        """The Base32 signal scope for this form, or ``None`` when unprefixed.

        A prefixed form (a standalone prefixed form, or each row of a formset)
        gets its own nested ``rgForms.<scope>`` signal namespace (ADR-0003 §1).
        """
        if self.prefix:
            return encode_scope(self.prefix)
        return None

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

    def get_external_signals(self) -> set[str]:
        """Return the declared ``Meta.external_signals`` set (empty if none)."""
        meta = getattr(self, "Meta", None)
        if meta is None:
            return set()
        return set(getattr(meta, "external_signals", None) or set())

    def get_external_signal_values(self) -> dict:
        """Server-side values for the form's declared external signals.

        ``Meta.external_signals`` only *authorizes* a reference; the server has
        no value for it unless the application supplies one. Override this to
        provide those values (e.g. from the request, session, or feature flags)
        so an expression like ``$feature_enabled && $email`` evaluates the same
        on the server as in the browser. Unprovided external signals default to
        ``None`` (falsy) during server evaluation.

        Returns an empty dict by default.
        """
        return {}

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
        if result is EVAL_ERROR:
            return True  # fail-open only on error
        return is_truthy(result)

    def get_signals(self) -> dict:
        """Generate the initial canonical signals dict for Datastar.

        Every field is run through reactive normalization (ADR-0002 §1/§2), so
        the seed the client receives is, by definition, what the server
        normalizes to. Bound forms read the submitted value via the widget
        (``getlist``/checkbox semantics); unbound forms read ``initial``. The
        result holds only canonical types (string, number, boolean, null, array)
        keyed by the logical field name.
        """
        signals: dict = {}
        files = getattr(self, "files", None) or {}
        for name, field in self.fields.items():
            if self.is_bound:
                html_name = self[name].html_name
                signals[name] = normalize_from_datadict(field, self.data, files, html_name)
            else:
                raw = self.get_initial_for_field(field, name)
                signals[name] = normalize_field_value(field, raw)
        return signals

    def get_seed_signals(self) -> dict:
        """The client-facing seed structure for ``data-signals``.

        For an unprefixed form this is the flat canonical dict. For a prefixed
        form the values are nested under ``rgForms.<scope>`` so they line up with
        the scoped ``data-bind`` paths and compiled ``$rgForms.<scope>.<field>``
        expression references (ADR-0003). Server-side expression evaluation keeps
        using the flat, logical-keyed :meth:`get_signals`.
        """
        signals = self.get_signals()
        scope = self.reactive_scope
        if scope:
            return {RESERVED_NAMESPACE: {scope: signals}}
        return signals

    def get_signals_json(self) -> str:
        """Return signals as a JSON string for the ``data-signals`` attribute.

        Normalization already reduces every value to a JSON-native canonical
        type; the ``default`` hook is a defensive fallback only.
        """
        import json
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        def default(obj):
            if isinstance(obj, datetime):
                from django.utils.timezone import is_aware, localtime

                if is_aware(obj):
                    obj = localtime(obj)
                # datetime-local inputs require YYYY-MM-DDTHH:MM (no tz offset).
                return obj.strftime("%Y-%m-%dT%H:%M")
            if isinstance(obj, date):
                return obj.isoformat()
            if isinstance(obj, time):
                return obj.strftime("%H:%M")
            if isinstance(obj, Decimal):
                return str(obj)
            if isinstance(obj, UUID):
                return str(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        # allow_nan=False is a defensive invariant: normalization already strips
        # non-finite floats, so a NaN/Infinity here indicates a bug rather than
        # emitting invalid JSON that would break Datastar's parser.
        return json.dumps(self.get_seed_signals(), default=default, allow_nan=False)

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
        return [name for name, field in self.fields.items() if getattr(field, "visible_when", None)]

    def get_computed_fields(self) -> list[str]:
        """Get list of field names that are computed."""
        return [name for name, field in self.fields.items() if getattr(field, "computed", None)]

    def _get_form_data(self) -> dict:
        """Canonical form data for expression evaluation (ADR-0002 §1).

        This is the same normalized, canonical dict the client is seeded with
        (``get_signals``), keyed by logical field name, plus any declared
        external-signal values (``get_external_signal_values``). Using one source
        for the seed and for server evaluation keeps the two evaluators in
        lock-step and eliminates the bound/unbound type split (P3). Fields always
        win over external values on a name clash.
        """
        data = dict(self.get_external_signal_values())
        data.update(self.get_signals())
        return data

    def _evaluate_expression(self, expression: str, *, decimal_mode: bool = False):
        """Safely evaluate an expression against canonical data.

        Returns the evaluated value (which may legitimately be ``None``/falsy),
        or the ``EVAL_ERROR`` sentinel on a parse/eval error — so callers can
        distinguish "the rule evaluated to false/null" from "the rule is broken"
        and apply the fail-open policy only to genuine errors (ADR-0002 P7).
        Errors are logged, never silently swallowed; the build-time system check
        (§5) is meant to catch malformed/unknown expressions earlier.
        """
        try:
            return evaluate_expression(expression, self._get_form_data(), decimal_mode=decimal_mode)
        except ExpressionError:
            logger.warning(
                "rg.forms: failed to evaluate expression %r on %s",
                expression,
                type(self).__name__,
                exc_info=True,
            )
            return EVAL_ERROR

    def is_field_visible(self, field_name: str, data: dict | None = None) -> bool:
        """Evaluate if a field should be visible based on current data.

        Server-side evaluation of visible_when rules. A rule that evaluates to a
        falsy value hides the field (matching client truthiness); only a genuine
        evaluation *error* fails open to visible.
        """
        field = self.fields.get(field_name)
        if not field:
            return False

        visible_when = getattr(field, "visible_when", None)
        if visible_when is None:
            return True

        result = self._evaluate_expression(visible_when)
        if result is EVAL_ERROR:
            return True  # fail-open only on error
        return is_truthy(result)

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
        if result is EVAL_ERROR:
            return False  # fail-open: not required on error
        return is_truthy(result)

    def get_computed_value(self, field_name: str, *, authoritative: bool = False):
        """Compute a field's value from its ``computed`` expression.

        With ``authoritative=True`` the arithmetic runs in exact ``Decimal``
        mode (ADR-0002 §3) so the server never stores the browser's float
        preview as the cleaned value.
        """
        field = self.fields.get(field_name)
        if not field:
            return None

        computed = getattr(field, "computed", None)
        if computed is None:
            return None

        result = self._evaluate_expression(computed, decimal_mode=authoritative)
        return None if result is EVAL_ERROR else result

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
                computed = getattr(field, "computed", None)
                if computed is not None:
                    # Computed fields have no editable input (the reference
                    # template renders a display-only element), so the submitted
                    # value is empty. Recompute authoritatively (exact Decimal)
                    # and clean the *computed* result — never require a submitted
                    # value first, so a computed field needs no `required=False`
                    # boilerplate (ADR-0002 §3 / reviewer #5).
                    computed_value = self.get_computed_value(name, authoritative=True)
                    value = field.clean(computed_value)
                elif isinstance(field, forms.FileField):
                    value = field.clean(value, bf.initial)
                else:
                    value = field.clean(value)

                self.cleaned_data[name] = value

                # Check required_when
                required_when = getattr(field, "required_when", None)
                if required_when is not None:
                    result = self._evaluate_expression(required_when)
                    is_required = result is not EVAL_ERROR and is_truthy(result)
                    if is_required and not value and value != 0:
                        raise ValidationError(
                            field.error_messages.get("required", "This field is required."),
                            code="required",
                        )

                # Call clean_<fieldname> if exists
                if hasattr(self, f"clean_{name}"):
                    value = getattr(self, f"clean_{name}")()
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
