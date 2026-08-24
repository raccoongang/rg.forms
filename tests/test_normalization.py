"""Tests for reactive value normalization (ADR-0002 §1/§2)."""

from datetime import date, datetime, time
from decimal import Decimal

from django.http import QueryDict

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDateField,
    ReactiveDateTimeField,
    ReactiveDecimalField,
    ReactiveFloatField,
    ReactiveForm,
    ReactiveIntegerField,
    ReactiveMultipleChoiceField,
    ReactiveTimeField,
)
from rg.forms.normalization import (
    canonical_empty,
    canonical_type,
    normalize_field_value,
    normalize_from_datadict,
)


class TestCanonicalType:
    def test_types(self):
        assert canonical_type(ReactiveCharField()) == "string"
        assert canonical_type(ReactiveChoiceField(choices=[])) == "string"
        assert canonical_type(ReactiveIntegerField()) == "number"
        assert canonical_type(ReactiveDecimalField()) == "string"
        assert canonical_type(ReactiveBooleanField()) == "boolean"
        assert canonical_type(ReactiveMultipleChoiceField(choices=[])) == "array"
        assert canonical_type(ReactiveDateField()) == "string"


class TestCanonicalEmpty:
    """The per-field empty-value table (ADR-0002 §2)."""

    def test_empty_values(self):
        assert canonical_empty(ReactiveCharField()) == ""
        assert canonical_empty(ReactiveIntegerField()) is None
        assert canonical_empty(ReactiveDecimalField()) == ""
        assert canonical_empty(ReactiveBooleanField()) is False
        assert canonical_empty(ReactiveMultipleChoiceField(choices=[])) == []
        assert canonical_empty(ReactiveDateField()) == ""


class TestNormalizeValue:
    def test_char_never_numeric_coerced(self):
        """P1: a leading-zero string stays a string."""
        assert normalize_field_value(ReactiveCharField(), "001") == "001"
        assert normalize_field_value(ReactiveChoiceField(choices=[]), "001") == "001"

    def test_integer_valid_and_empty(self):
        assert normalize_field_value(ReactiveIntegerField(), "10") == 10
        assert normalize_field_value(ReactiveIntegerField(), "") is None
        assert normalize_field_value(ReactiveIntegerField(), 42) == 42

    def test_integer_in_progress_kept_as_string(self):
        """Temporarily-invalid input is representable, not nulled."""
        assert normalize_field_value(ReactiveIntegerField(), "-") == "-"
        assert normalize_field_value(ReactiveIntegerField(), "1.") == "1."

    def test_non_finite_native_float_maps_to_empty(self):
        """NaN/Infinity are not valid JSON — normalize to the canonical empty."""
        assert normalize_field_value(ReactiveFloatField(), float("nan")) is None
        assert normalize_field_value(ReactiveFloatField(), float("inf")) is None
        assert normalize_field_value(ReactiveFloatField(), float("-inf")) is None

    def test_overflowing_numeric_string_kept_as_string(self):
        """An overflowing string stays representable (never emits Infinity)."""
        assert normalize_field_value(ReactiveFloatField(), "1e9999") == "1e9999"

    def test_non_finite_decimal_maps_to_empty(self):
        from decimal import Decimal as D

        assert normalize_field_value(ReactiveIntegerField(), D("NaN")) is None
        assert normalize_field_value(ReactiveIntegerField(), D("Infinity")) is None

    def test_decimal_is_canonical_string(self):
        assert normalize_field_value(ReactiveDecimalField(), Decimal("19.99")) == "19.99"
        assert normalize_field_value(ReactiveDecimalField(), "5.00") == "5.00"
        assert normalize_field_value(ReactiveDecimalField(), None) == ""

    def test_boolean(self):
        assert normalize_field_value(ReactiveBooleanField(), True) is True
        assert normalize_field_value(ReactiveBooleanField(), "on") is True
        assert normalize_field_value(ReactiveBooleanField(), None) is False

    def test_multiple_choice_array(self):
        f = ReactiveMultipleChoiceField(choices=[("a", "A"), ("b", "B")])
        assert normalize_field_value(f, ["a", "b"]) == ["a", "b"]
        assert normalize_field_value(f, None) == []

    def test_date_time_datetime_strings(self):
        assert normalize_field_value(ReactiveDateField(), date(2026, 1, 2)) == "2026-01-02"
        assert normalize_field_value(ReactiveTimeField(), time(13, 45)) == "13:45"
        assert normalize_field_value(ReactiveDateTimeField(), datetime(2026, 1, 2, 13, 45)) == "2026-01-02T13:45"


class TestSignalsJsonIsValid:
    """get_signals_json must always emit valid JSON (no bare NaN/Infinity)."""

    def test_nan_initial_produces_valid_json(self):
        import json

        class F(ReactiveForm):
            n = ReactiveFloatField(required=False)

        form = F(initial={"n": float("nan")})
        text = form.get_signals_json()
        # Parses as valid JSON (would be `{"n": NaN}` — invalid — without the fix).
        assert json.loads(text) == {"n": None}


class TestNormalizeFromDatadict:
    def test_multi_value_uses_getlist(self):
        """P2: a multi-value field yields the full array, not the last value."""
        f = ReactiveMultipleChoiceField(choices=[("a", "A"), ("b", "B"), ("c", "C")])
        qd = QueryDict(mutable=True)
        qd.setlist("choices", ["a", "c"])
        assert normalize_from_datadict(f, qd, {}, "choices") == ["a", "c"]

    def test_unchecked_checkbox_is_false(self):
        """P4: an absent checkbox normalizes to boolean false."""
        f = ReactiveBooleanField()
        qd = QueryDict("")  # key absent
        assert normalize_from_datadict(f, qd, {}, "agree") is False

    def test_checked_checkbox_is_true(self):
        f = ReactiveBooleanField()
        qd = QueryDict("agree=on")
        assert normalize_from_datadict(f, qd, {}, "agree") is True
