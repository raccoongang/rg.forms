"""Tests for reactive_forms template tags."""

import pytest
from django.template import Context, Template

from rg.forms import ReactiveCharField, ReactiveChoiceField, ReactiveForm


class VisibilityForm(ReactiveForm):
    """Test form with visibility rules."""

    order_type = ReactiveChoiceField(
        choices=[("standard", "Standard"), ("urgent", "Urgent")]
    )
    priority = ReactiveCharField(
        visible_when="$order_type == 'urgent'",
        required=False,
    )


class ComputedForm(ReactiveForm):
    """Test form with computed field."""

    quantity = ReactiveCharField()
    price = ReactiveCharField()
    total = ReactiveCharField(
        computed="$quantity * $price",
        required=False,
    )


class RequiredWhenForm(ReactiveForm):
    """Test form with required_when."""

    contact_method = ReactiveChoiceField(choices=[("email", "Email"), ("phone", "Phone")])
    email = ReactiveCharField(
        required_when="$contact_method == 'email'",
        required=False,
    )


class TestReactiveWrapperAttrs:
    """Tests for reactive_wrapper_attrs tag."""

    def test_visible_when_generates_data_show(self):
        """visible_when should generate data-show attribute."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_wrapper_attrs form.priority %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert 'data-show="$order_type == \'urgent\'"' in result

    def test_no_visible_when_returns_empty(self):
        """Field without visible_when should return empty string."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_wrapper_attrs form.order_type %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == ""


class TestReactiveInputAttrs:
    """Tests for reactive_input_attrs tag."""

    def test_generates_data_bind(self):
        """Should generate data-bind for field signal (key-based syntax, no $ prefix)."""
        form = VisibilityForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_input_attrs form.order_type %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        # Datastar uses data-bind:fieldname syntax (no $ prefix)
        assert "data-bind:order_type" in result

    def test_computed_generates_data_computed(self):
        """Computed field should generate data-computed and readonly."""
        form = ComputedForm()
        template = Template(
            "{% load reactive_forms %}{% reactive_input_attrs form.total %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert 'data-computed="$quantity * $price"' in result
        assert "readonly" in result


class TestReactiveSignals:
    """Tests for reactive_signals tag."""

    def test_generates_json_signals(self):
        """Should generate JSON signals from form."""
        form = VisibilityForm(initial={"order_type": "urgent"})
        # Use single quotes for attribute since JSON uses double quotes
        template = Template(
            "{% load reactive_forms %}<form data-signals='{% reactive_signals form %}'>"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert '"order_type": "urgent"' in result


class TestSignalNameFilter:
    """Tests for signal_name filter."""

    def test_converts_to_signal_reference(self):
        """Should convert field name to $-prefixed signal."""
        template = Template(
            '{% load reactive_forms %}{{ "my_field"|signal_name }}'
        )
        context = Context({})
        result = template.render(context)

        assert result == "$my_field"


class TestRequiredIndicator:
    """Tests for required_indicator tag."""

    def test_required_when_generates_data_show(self):
        """required_when should generate indicator with data-show."""
        form = RequiredWhenForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.email %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" in result
        # Check for the expression (may be HTML-encoded)
        assert "$contact_method" in result
        assert "email" in result

    def test_static_required_no_data_show(self):
        """Static required should generate indicator without data-show."""
        form = RequiredWhenForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.contact_method %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert "data-show" not in result
        assert "*" in result

    def test_not_required_returns_empty(self):
        """Non-required field without required_when returns empty."""

        class OptionalForm(ReactiveForm):
            optional = ReactiveCharField(required=False)

        form = OptionalForm()
        template = Template(
            "{% load reactive_forms %}{% required_indicator form.optional %}"
        )
        context = Context({"form": form})
        result = template.render(context)

        assert result.strip() == ""


class TestFormMethods:
    """Tests for ReactiveForm helper methods."""

    def test_get_field_reactive_attrs(self):
        """get_field_reactive_attrs should return field's reactive attributes."""
        form = VisibilityForm()
        attrs = form.get_field_reactive_attrs("priority")

        assert attrs["visible_when"] == "$order_type == 'urgent'"

    def test_get_visible_fields(self):
        """get_visible_fields should return fields with visibility rules."""
        form = VisibilityForm()
        visible_fields = form.get_visible_fields()

        assert "priority" in visible_fields
        assert "order_type" not in visible_fields

    def test_get_computed_fields(self):
        """get_computed_fields should return computed field names."""
        form = ComputedForm()
        computed_fields = form.get_computed_fields()

        assert "total" in computed_fields
        assert "quantity" not in computed_fields
