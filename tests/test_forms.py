"""Tests for ReactiveForm."""

import json
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

import pytest

from rg.forms import (
    ReactiveForm,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDateField,
    ReactiveDateTimeField,
    ReactiveDecimalField,
    ReactiveTimeField,
)


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


class TestSignalsJsonSerialization:
    """Tests for JSON serialization of non-string initial values (edit mode bug)."""

    def test_date_field_in_initial(self):
        """Date object from model instance should serialize to ISO string."""

        class EventForm(ReactiveForm):
            name = ReactiveCharField()
            event_date = ReactiveDateField()

        form = EventForm(initial={"name": "Conference", "event_date": date(2025, 6, 15)})
        json_str = form.get_signals_json()
        data = json.loads(json_str)
        assert data["event_date"] == "2025-06-15"
        assert data["name"] == "Conference"

    def test_datetime_field_in_initial(self):
        """Datetime object should serialize to ISO string."""

        class LogForm(ReactiveForm):
            created_at = ReactiveDateTimeField()

        form = LogForm(initial={"created_at": datetime(2025, 3, 11, 14, 30, 0)})
        data = json.loads(form.get_signals_json())
        assert data["created_at"] == "2025-03-11T14:30:00"

    def test_time_field_in_initial(self):
        """Time object should serialize to ISO string."""

        class ScheduleForm(ReactiveForm):
            start_time = ReactiveTimeField()

        form = ScheduleForm(initial={"start_time": time(9, 30)})
        data = json.loads(form.get_signals_json())
        assert data["start_time"] == "09:30:00"

    def test_decimal_field_in_initial(self):
        """Decimal from model instance should serialize to string."""

        class PriceForm(ReactiveForm):
            price = ReactiveDecimalField(decimal_places=2)

        form = PriceForm(initial={"price": Decimal("19.99")})
        data = json.loads(form.get_signals_json())
        assert data["price"] == "19.99"

    def test_mixed_types_in_initial(self):
        """Form with multiple non-string types should all serialize correctly."""

        class FullForm(ReactiveForm):
            name = ReactiveCharField()
            birth_date = ReactiveDateField()
            created_at = ReactiveDateTimeField(required=False)
            price = ReactiveDecimalField(decimal_places=2, required=False)

        form = FullForm(initial={
            "name": "Alice",
            "birth_date": date(1990, 1, 15),
            "created_at": datetime(2025, 3, 11, 10, 0),
            "price": Decimal("42.50"),
        })
        data = json.loads(form.get_signals_json())
        assert data["name"] == "Alice"
        assert data["birth_date"] == "1990-01-15"
        assert data["created_at"] == "2025-03-11T10:00:00"
        assert data["price"] == "42.50"


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


class TestPopulate:
    """Tests for ReactiveForm.populate() method."""

    def test_populate_from_list(self):
        """populate should fill choices from a list of objects."""

        class Item:
            def __init__(self, pk, name):
                self.pk = pk
                self.name = name

        class ItemForm(ReactiveForm):
            item = ReactiveChoiceField(choices=[])

        items = [Item(1, "Apple"), Item(2, "Banana"), Item(3, "Cherry")]
        form = ItemForm()
        form.populate("item", items, label_field="name")

        assert form.fields["item"].choices == [
            ("1", "Apple"),
            ("2", "Banana"),
            ("3", "Cherry"),
        ]

    def test_populate_with_empty_choice(self):
        """populate with add_empty should prepend empty option."""

        class Item:
            def __init__(self, pk, name):
                self.pk = pk
                self.name = name

        class ItemForm(ReactiveForm):
            item = ReactiveChoiceField(choices=[])

        items = [Item(1, "Apple")]
        form = ItemForm()
        form.populate("item", items, label_field="name", add_empty=True)

        assert form.fields["item"].choices[0] == ("", "-- Select --")
        assert form.fields["item"].choices[1] == ("1", "Apple")

    def test_populate_uses_str_when_no_label_field(self):
        """populate without label_field should use str(obj)."""

        class Item:
            def __init__(self, pk, name):
                self.pk = pk
                self.name = name

            def __str__(self):
                return f"Item: {self.name}"

        class ItemForm(ReactiveForm):
            item = ReactiveChoiceField(choices=[])

        items = [Item(1, "Apple")]
        form = ItemForm()
        form.populate("item", items)

        assert form.fields["item"].choices == [("1", "Item: Apple")]


class TestDeclarativeCascading:
    """Tests for declarative cascading (choices_from + depends_on)."""

    def test_choices_from_root_field(self):
        """Root field with choices_from should auto-populate."""

        def get_items():
            return [
                {"id": 1, "name": "Apple"},
                {"id": 2, "name": "Banana"},
            ]

        class ItemForm(ReactiveForm):
            item = ReactiveChoiceField(
                choices_from=get_items,
                value_field="id",
                label_field="name",
            )

        form = ItemForm()
        assert form.fields["item"].choices == [
            ("1", "Apple"),
            ("2", "Banana"),
        ]

    def test_choices_from_with_empty_choice(self):
        """Root field with empty_choice should prepend empty option."""

        def get_items():
            return [{"id": 1, "name": "Apple"}]

        class ItemForm(ReactiveForm):
            item = ReactiveChoiceField(
                choices_from=get_items,
                value_field="id",
                label_field="name",
                empty_choice="-- Select Item --",
            )

        form = ItemForm()
        assert form.fields["item"].choices[0] == ("", "-- Select Item --")
        assert form.fields["item"].choices[1] == ("1", "Apple")

    def test_dependent_field_no_parent_value(self):
        """Dependent field without parent value shows placeholder."""

        def get_categories():
            return [{"id": 1, "name": "Electronics"}]

        def get_products(category_id):
            return [{"id": 101, "name": "Laptop"}]

        class CascadeForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
                empty_choice="-- Select --",
            )
            product = ReactiveChoiceField(
                choices_from=get_products,
                depends_on=["category"],
                value_field="id",
                label_field="name",
                empty_choice="-- Select Product --",
                empty_choice_no_parent="-- Select Category First --",
            )

        form = CascadeForm()
        # Product should show placeholder since category not selected
        assert form.fields["product"].choices == [("", "-- Select Category First --")]

    def test_dependent_field_with_parent_value_initial(self):
        """Dependent field with parent in initial should populate."""

        def get_categories():
            return [{"id": 1, "name": "Electronics"}]

        def get_products(category_id):
            return [
                {"id": 101, "name": "Laptop"},
                {"id": 102, "name": "Phone"},
            ]

        class CascadeForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
                empty_choice="-- Select --",
            )
            product = ReactiveChoiceField(
                choices_from=get_products,
                depends_on=["category"],
                value_field="id",
                label_field="name",
                empty_choice="-- Select Product --",
            )

        form = CascadeForm(initial={"category": "1"})
        assert ("", "-- Select Product --") in form.fields["product"].choices
        assert ("101", "Laptop") in form.fields["product"].choices
        assert ("102", "Phone") in form.fields["product"].choices

    def test_dependent_field_with_parent_value_bound(self):
        """Dependent field with parent in POST data should populate."""

        def get_categories():
            return [{"id": 1, "name": "Electronics"}]

        def get_products(category_id):
            return [{"id": 101, "name": "Laptop"}]

        class CascadeForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
            )
            product = ReactiveChoiceField(
                choices_from=get_products,
                depends_on=["category"],
                value_field="id",
                label_field="name",
            )

        form = CascadeForm(data={"category": "1", "product": "101"})
        assert ("101", "Laptop") in form.fields["product"].choices

    def test_dependent_field_resets_invalid_value(self):
        """Dependent field should reset when value invalid for new parent."""

        def get_categories():
            return [
                {"id": 1, "name": "Electronics"},
                {"id": 2, "name": "Clothing"},
            ]

        def get_products(category_id):
            if category_id == "1":
                return [{"id": 101, "name": "Laptop"}]
            else:
                return [{"id": 201, "name": "Shirt"}]

        class CascadeForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
            )
            product = ReactiveChoiceField(
                choices_from=get_products,
                depends_on=["category"],
                value_field="id",
                label_field="name",
            )

        # User had product 101 (Electronics), then changed to Clothing
        form = CascadeForm(data={"category": "2", "product": "101"})
        # Product should be reset because 101 is not valid for category 2
        assert form.data.get("product") == ""

    def test_label_template(self):
        """label_template should format labels from object attributes."""

        def get_products():
            return [
                {"id": 1, "name": "Laptop", "price": 999},
                {"id": 2, "name": "Phone", "price": 699},
            ]

        class ProductForm(ReactiveForm):
            product = ReactiveChoiceField(
                choices_from=get_products,
                value_field="id",
                label_template="{name} (${price})",
            )

        form = ProductForm()
        assert ("1", "Laptop ($999)") in form.fields["product"].choices
        assert ("2", "Phone ($699)") in form.fields["product"].choices

    def test_depends_on_as_string(self):
        """depends_on can be a single string instead of list."""

        def get_categories():
            return [{"id": 1, "name": "Cat"}]

        def get_items(cat_id):
            return [{"id": 10, "name": "Item"}]

        class TestForm(ReactiveForm):
            category = ReactiveChoiceField(
                choices_from=get_categories,
                value_field="id",
                label_field="name",
            )
            item = ReactiveChoiceField(
                choices_from=get_items,
                depends_on="category",  # string, not list
                value_field="id",
                label_field="name",
            )

        form = TestForm(initial={"category": "1"})
        assert ("10", "Item") in form.fields["item"].choices


class TestBackendValidation:
    """Tests for backend expression evaluation in validation."""

    def test_hidden_field_skipped(self):
        """Hidden field (visible_when=false) is skipped in validation."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            order_type = ReactiveChoiceField(
                choices=[("standard", "Standard"), ("urgent", "Urgent")]
            )
            priority = ReactiveCharField(
                visible_when="$order_type == 'urgent'",
                required=True,  # Would fail if validated
            )

        # Standard order - priority is hidden, should not fail validation
        form = TestForm(data={"order_type": "standard", "priority": ""})
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert form.cleaned_data["priority"] is None  # Skipped

    def test_visible_field_validated(self):
        """Visible field (visible_when=true) is validated normally."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            order_type = ReactiveChoiceField(
                choices=[("standard", "Standard"), ("urgent", "Urgent")]
            )
            priority = ReactiveCharField(
                visible_when="$order_type == 'urgent'",
                required=True,
            )

        # Urgent order - priority is visible and required
        form = TestForm(data={"order_type": "urgent", "priority": ""})
        assert not form.is_valid()
        assert "priority" in form.errors

    def test_required_when_enforced(self):
        """required_when is enforced on backend."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            contact_method = ReactiveChoiceField(
                choices=[("email", "Email"), ("phone", "Phone")]
            )
            email = ReactiveCharField(
                required=False,
                required_when="$contact_method == 'email'",
            )

        # Email selected but empty - should fail
        form = TestForm(data={"contact_method": "email", "email": ""})
        assert not form.is_valid()
        assert "email" in form.errors

    def test_required_when_not_triggered(self):
        """required_when not triggered when condition is false."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            contact_method = ReactiveChoiceField(
                choices=[("email", "Email"), ("phone", "Phone")]
            )
            email = ReactiveCharField(
                required=False,
                required_when="$contact_method == 'email'",
            )

        # Phone selected - email not required
        form = TestForm(data={"contact_method": "phone", "email": ""})
        assert form.is_valid()

    def test_computed_field_recalculated(self):
        """Computed field value is recalculated on backend."""
        from rg.forms import ReactiveForm, ReactiveIntegerField, ReactiveDecimalField

        class TestForm(ReactiveForm):
            quantity = ReactiveIntegerField()
            price = ReactiveDecimalField()
            total = ReactiveDecimalField(
                required=False,
                computed="$quantity * $price",
            )

        # User submits with wrong total - backend recalculates
        form = TestForm(data={
            "quantity": "5",
            "price": "10.00",
            "total": "999.99",  # Wrong value
        })
        assert form.is_valid()
        # Backend recalculates to correct value
        from decimal import Decimal
        assert form.cleaned_data["total"] == Decimal("50.00")

    def test_is_field_visible_method(self):
        """is_field_visible returns correct result."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            order_type = ReactiveChoiceField(
                choices=[("standard", "Standard"), ("urgent", "Urgent")]
            )
            priority = ReactiveCharField(
                visible_when="$order_type == 'urgent'",
                required=False,
            )

        form = TestForm(data={"order_type": "standard"})
        assert not form.is_field_visible("priority")

        form = TestForm(data={"order_type": "urgent"})
        assert form.is_field_visible("priority")

    def test_is_field_required_method(self):
        """is_field_required returns correct result."""
        from rg.forms import ReactiveForm, ReactiveCharField, ReactiveChoiceField

        class TestForm(ReactiveForm):
            contact_method = ReactiveChoiceField(
                choices=[("email", "Email"), ("phone", "Phone")]
            )
            email = ReactiveCharField(
                required=False,
                required_when="$contact_method == 'email'",
            )

        form = TestForm(data={"contact_method": "phone"})
        assert not form.is_field_required("email")

        form = TestForm(data={"contact_method": "email"})
        assert form.is_field_required("email")
