"""Tests for the build-time expression system check (ADR-0002 §5)."""

from rg.forms import (
    ReactiveCharField,
    ReactiveForm,
    ReactiveIntegerField,
    ReactiveMultipleChoiceField,
)
from rg.forms.checks import check_form_expressions


class TestExpressionChecks:
    def test_valid_form_has_no_problems(self):
        class GoodForm(ReactiveForm):
            order_type = ReactiveCharField()
            priority = ReactiveCharField(visible_when="$order_type == 'urgent'")

        assert check_form_expressions(GoodForm) == []

    def test_unknown_reference_is_reported(self):
        class BadForm(ReactiveForm):
            order_type = ReactiveCharField()
            priority = ReactiveCharField(visible_when="$typo == 'urgent'")

        problems = check_form_expressions(BadForm)
        assert any("$typo" in p for p in problems)

    def test_declared_external_signal_is_accepted(self):
        class ExtForm(ReactiveForm):
            priority = ReactiveCharField(visible_when="$feature_enabled")

            class Meta:
                external_signals = {"feature_enabled"}

        assert check_form_expressions(ExtForm) == []

    def test_reserved_namespace_reference_is_rejected(self):
        class ReservedForm(ReactiveForm):
            priority = ReactiveCharField(visible_when="$rgForms.x.y == 'a'")

        problems = check_form_expressions(ReservedForm)
        assert any("reserved" in p.lower() for p in problems)

    def test_external_signals_cannot_declare_reserved(self):
        class ReservedExtForm(ReactiveForm):
            priority = ReactiveCharField(visible_when="$priority == 'a'")

            class Meta:
                external_signals = {"rgForms"}

        problems = check_form_expressions(ReservedExtForm)
        assert any("reserved" in p.lower() for p in problems)

    def test_string_operand_to_arithmetic_is_rejected(self):
        class ArithForm(ReactiveForm):
            total = ReactiveIntegerField(computed="$total + 'x'")

        problems = check_form_expressions(ArithForm)
        assert any("arithmetic" in p.lower() for p in problems)

    def test_string_field_in_arithmetic_is_rejected(self):
        """Reviewer blocker #2: a string-typed field ref in arithmetic is rejected."""

        class Form(ReactiveForm):
            name = ReactiveCharField(computed="$name * 2")

        problems = check_form_expressions(Form)
        assert any("arithmetic" in p.lower() and "$name" in p for p in problems)

    def test_boolean_field_in_arithmetic_is_rejected(self):
        from rg.forms import ReactiveBooleanField

        class Form(ReactiveForm):
            flag = ReactiveBooleanField(required=False)
            n = ReactiveIntegerField(computed="$flag * 2")

        problems = check_form_expressions(Form)
        assert any("arithmetic" in p.lower() and "$flag" in p for p in problems)

    def test_comparison_subexpression_in_arithmetic_is_rejected(self):
        """Composite boolean operand: ($name == 'x') * 2 must be rejected."""

        class Form(ReactiveForm):
            name = ReactiveCharField(required=False)
            n = ReactiveIntegerField(computed="($name == 'x') * 2")

        problems = check_form_expressions(Form)
        assert any("arithmetic" in p.lower() for p in problems)

    def test_logical_subexpression_in_arithmetic_is_rejected(self):
        from rg.forms import ReactiveBooleanField

        class Form(ReactiveForm):
            a = ReactiveBooleanField(required=False)
            n = ReactiveIntegerField(computed="(!$a) + 1")

        problems = check_form_expressions(Form)
        assert any("arithmetic" in p.lower() for p in problems)

    def test_nested_numeric_arithmetic_is_allowed(self):
        class Form(ReactiveForm):
            a = ReactiveIntegerField(required=False)
            b = ReactiveIntegerField(required=False)
            c = ReactiveIntegerField(required=False)
            total = ReactiveIntegerField(required=False, computed="($a + $b) * $c")

        assert check_form_expressions(Form) == []

    def test_decimal_field_in_arithmetic_is_allowed(self):
        from rg.forms import ReactiveDecimalField

        class Form(ReactiveForm):
            qty = ReactiveIntegerField(required=False)
            price = ReactiveDecimalField(required=False)
            total = ReactiveDecimalField(required=False, computed="$qty * $price")

        assert check_form_expressions(Form) == []

    def test_array_field_reference_is_rejected(self):
        class ArrayForm(ReactiveForm):
            tags = ReactiveMultipleChoiceField(choices=[("a", "A")])
            note = ReactiveCharField(visible_when="$tags == 'a'")

        problems = check_form_expressions(ArrayForm)
        assert any("array" in p.lower() for p in problems)

    def test_group_visible_when_is_checked(self):
        from rg.forms import FieldGroup

        class GroupForm(ReactiveForm):
            account_type = ReactiveCharField()
            company = ReactiveCharField()

            class Meta:
                field_groups = {
                    "co": FieldGroup(
                        fields=["company"],
                        visible_when="$nonexistent == 'business'",
                    ),
                }

        problems = check_form_expressions(GroupForm)
        assert any("$nonexistent" in p for p in problems)
