"""Regression tests for the post-implementation review findings (#4, #5)."""

from decimal import Decimal

from rg.forms import (
    ReactiveCharField,
    ReactiveDecimalField,
    ReactiveForm,
    ReactiveIntegerField,
)


class TestComputedDefaultRequired:
    """#5: a computed field must not need `required=False` boilerplate."""

    def test_required_computed_field_is_valid_without_submitted_value(self):
        class OrderForm(ReactiveForm):
            quantity = ReactiveIntegerField()
            unit_price = ReactiveDecimalField()
            # required by default (no required=False); has no editable input.
            total = ReactiveDecimalField(computed="$quantity * $unit_price")

        form = OrderForm(data={"quantity": "5", "unit_price": "2.00"})
        assert form.is_valid(), form.errors
        # Authoritative exact Decimal recomputation.
        assert form.cleaned_data["total"] == Decimal("10.00")

    def test_computed_uses_server_value_not_submitted(self):
        class OrderForm(ReactiveForm):
            quantity = ReactiveIntegerField()
            unit_price = ReactiveDecimalField()
            total = ReactiveDecimalField(computed="$quantity * $unit_price")

        # A tampered/submitted total is ignored; server recomputes.
        form = OrderForm(data={"quantity": "3", "unit_price": "4.00", "total": "999"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["total"] == Decimal("12.00")


class TestExternalSignalValues:
    """#4: external signals get server-side values via the provider hook."""

    def test_unprovided_external_signal_is_falsy(self):
        class F(ReactiveForm):
            detail = ReactiveCharField(required=False, visible_when="$feature_enabled")

            class Meta:
                external_signals = {"feature_enabled"}

        form = F(data={"detail": "x"})
        # No provider -> external signal is None -> field hidden on the server.
        assert form.is_field_visible("detail") is False

    def test_provided_external_signal_true_makes_field_visible(self):
        class F(ReactiveForm):
            detail = ReactiveCharField(required=False, visible_when="$feature_enabled")

            class Meta:
                external_signals = {"feature_enabled"}

            def get_external_signal_values(self):
                return {"feature_enabled": True}

        form = F(data={"detail": "x"})
        assert form.is_field_visible("detail") is True

    def test_provided_external_signal_false_hides_field(self):
        class F(ReactiveForm):
            detail = ReactiveCharField(required=False, visible_when="$feature_enabled")

            class Meta:
                external_signals = {"feature_enabled"}

            def get_external_signal_values(self):
                return {"feature_enabled": False}

        form = F(data={"detail": "x"})
        assert form.is_field_visible("detail") is False

    def test_field_value_wins_over_external_on_name_clash(self):
        class F(ReactiveForm):
            status = ReactiveCharField(required=False)
            note = ReactiveCharField(required=False, visible_when="$status == 'on'")

            def get_external_signal_values(self):
                return {"status": "off"}  # must not shadow the real field

        form = F(data={"status": "on", "note": "x"})
        assert form.is_field_visible("note") is True
