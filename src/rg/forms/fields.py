"""Reactive field classes for rg.forms.

Each reactive field wraps a standard Django form field and adds:
- visible_when: Expression controlling field visibility
- required_when: Expression controlling field requirement
- computed: Expression for computed field values
- depends_on: Fields that trigger re-evaluation
"""

from django import forms


class ReactiveFieldMixin:
    """Mixin adding reactive capabilities to Django form fields.

    Attributes:
        visible_when: Datastar expression for visibility (e.g., "$order_type == 'urgent'")
        required_when: Datastar expression for dynamic requirement
        computed: Datastar expression for computed values
        depends_on: List of field names this field depends on
        disabled_when: Datastar expression for disabling field
        read_only_when: Datastar expression for making field read-only
        help_text_when: Dict of {expression: help_text} for dynamic help text
        placeholder_when: Dict of {expression: placeholder} for dynamic placeholder
        min_when: Dict of {expression: min_value} for dynamic minimum
        max_when: Dict of {expression: max_value} for dynamic maximum
    """

    visible_when: str | None = None
    required_when: str | None = None
    computed: str | None = None
    depends_on: list[str] | None = None
    disabled_when: str | None = None
    read_only_when: str | None = None
    help_text_when: dict[str, str] | None = None
    placeholder_when: dict[str, str] | None = None
    min_when: dict[str, int | float] | None = None
    max_when: dict[str, int | float] | None = None

    def __init__(
        self,
        *args,
        visible_when: str | None = None,
        required_when: str | None = None,
        computed: str | None = None,
        depends_on: list[str] | None = None,
        disabled_when: str | None = None,
        read_only_when: str | None = None,
        help_text_when: dict[str, str] | None = None,
        placeholder_when: dict[str, str] | None = None,
        min_when: dict[str, int | float] | None = None,
        max_when: dict[str, int | float] | None = None,
        **kwargs,
    ):
        self.visible_when = visible_when
        self.required_when = required_when
        self.computed = computed
        self.depends_on = depends_on or []
        self.disabled_when = disabled_when
        self.read_only_when = read_only_when
        self.help_text_when = help_text_when
        self.placeholder_when = placeholder_when
        self.min_when = min_when
        self.max_when = max_when
        super().__init__(*args, **kwargs)

    def is_visible(self, form_data: dict) -> bool:
        """Evaluate visibility on server side.

        For now, returns True. Full AST-based evaluation will be implemented.
        """
        if self.visible_when is None:
            return True
        # TODO: Implement AST-based rule evaluation
        return True

    def is_required_dynamic(self, form_data: dict) -> bool:
        """Evaluate dynamic requirement on server side.

        For now, returns the static required value. Full AST-based evaluation will be implemented.
        """
        if self.required_when is None:
            return getattr(self, "required", False)
        # TODO: Implement AST-based rule evaluation
        return getattr(self, "required", False)


class ReactiveCharField(ReactiveFieldMixin, forms.CharField):
    """Reactive version of CharField."""

    pass


class ReactiveIntegerField(ReactiveFieldMixin, forms.IntegerField):
    """Reactive version of IntegerField."""

    pass


class ReactiveFloatField(ReactiveFieldMixin, forms.FloatField):
    """Reactive version of FloatField."""

    pass


class ReactiveDecimalField(ReactiveFieldMixin, forms.DecimalField):
    """Reactive version of DecimalField."""

    pass


class ReactiveBooleanField(ReactiveFieldMixin, forms.BooleanField):
    """Reactive version of BooleanField."""

    pass


class ReactiveChoiceField(ReactiveFieldMixin, forms.ChoiceField):
    """Reactive version of ChoiceField with cascading support.

    Cascading attributes (for declarative dependent dropdowns):
        choices_from: Callable returning list/queryset for choices.
                      For root fields: callable()
                      For dependent fields: callable(parent_value)
        value_field: Attribute name for option value (default: "pk")
        label_field: Attribute name for option label (default: uses str())
        label_template: Format string for label, e.g., "{name} (${price})"
        empty_choice: Label for empty option (default: None = no empty option)
        empty_choice_no_parent: Label when parent not selected (for dependent fields)
    """

    choices_from: "Callable | None" = None
    value_field: str = "pk"
    label_field: str | None = None
    label_template: str | None = None
    empty_choice: str | None = None
    empty_choice_no_parent: str | None = None

    def __init__(
        self,
        *args,
        choices_from: "Callable | None" = None,
        value_field: str = "pk",
        label_field: str | None = None,
        label_template: str | None = None,
        empty_choice: str | None = None,
        empty_choice_no_parent: str | None = None,
        **kwargs,
    ):
        self.choices_from = choices_from
        self.value_field = value_field
        self.label_field = label_field
        self.label_template = label_template
        self.empty_choice = empty_choice
        self.empty_choice_no_parent = empty_choice_no_parent
        super().__init__(*args, **kwargs)


class ReactiveMultipleChoiceField(ReactiveFieldMixin, forms.MultipleChoiceField):
    """Reactive version of MultipleChoiceField."""

    pass


class ReactiveEmailField(ReactiveFieldMixin, forms.EmailField):
    """Reactive version of EmailField."""

    pass


class ReactiveURLField(ReactiveFieldMixin, forms.URLField):
    """Reactive version of URLField."""

    pass


class ReactiveDateField(ReactiveFieldMixin, forms.DateField):
    """Reactive version of DateField."""

    pass


class ReactiveDateTimeField(ReactiveFieldMixin, forms.DateTimeField):
    """Reactive version of DateTimeField."""

    pass


class ReactiveTimeField(ReactiveFieldMixin, forms.TimeField):
    """Reactive version of TimeField."""

    pass
