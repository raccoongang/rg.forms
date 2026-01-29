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
    """

    visible_when: str | None = None
    required_when: str | None = None
    computed: str | None = None
    depends_on: list[str] | None = None

    def __init__(
        self,
        *args,
        visible_when: str | None = None,
        required_when: str | None = None,
        computed: str | None = None,
        depends_on: list[str] | None = None,
        **kwargs,
    ):
        self.visible_when = visible_when
        self.required_when = required_when
        self.computed = computed
        self.depends_on = depends_on or []
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
    """Reactive version of ChoiceField."""

    pass


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
