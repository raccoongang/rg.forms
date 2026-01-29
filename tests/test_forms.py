"""Tests for ReactiveForm."""

import pytest

from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField


class TestReactiveForm:
    """Tests for ReactiveForm base class."""

    def test_empty_form_signals(self):
        """Empty form should return empty signals dict."""

        class EmptyForm(ReactiveForm):
            pass

        form = EmptyForm()
        assert form.get_signals() == {}

    def test_form_signals_from_initial(self):
        """Form signals should include initial values."""

        class SimpleForm(ReactiveForm):
            name = ReactiveCharField()

        form = SimpleForm(initial={"name": "test"})
        signals = form.get_signals()
        assert signals["name"] == "test"

    def test_form_signals_from_bound_data(self):
        """Bound form signals should prefer data over initial."""

        class SimpleForm(ReactiveForm):
            name = ReactiveCharField()

        form = SimpleForm(data={"name": "from_data"}, initial={"name": "from_initial"})
        signals = form.get_signals()
        assert signals["name"] == "from_data"

    def test_form_signals_json(self):
        """get_signals_json should return valid JSON."""

        class SimpleForm(ReactiveForm):
            name = ReactiveCharField()

        form = SimpleForm(initial={"name": "test"})
        json_str = form.get_signals_json()
        assert '"name": "test"' in json_str


class TestReactiveFields:
    """Tests for reactive field classes."""

    def test_visible_when_attribute(self):
        """Field should store visible_when expression."""
        field = ReactiveCharField(visible_when="$order_type == 'urgent'")
        assert field.visible_when == "$order_type == 'urgent'"

    def test_required_when_attribute(self):
        """Field should store required_when expression."""
        field = ReactiveCharField(required_when="$needs_details == true")
        assert field.required_when == "$needs_details == true"

    def test_computed_attribute(self):
        """Field should store computed expression."""
        field = ReactiveCharField(computed="$quantity * $price")
        assert field.computed == "$quantity * $price"

    def test_depends_on_attribute(self):
        """Field should store depends_on list."""
        field = ReactiveChoiceField(
            choices=[("a", "A")],
            depends_on=["category", "region"],
        )
        assert field.depends_on == ["category", "region"]

    def test_default_depends_on_empty(self):
        """depends_on should default to empty list."""
        field = ReactiveCharField()
        assert field.depends_on == []
