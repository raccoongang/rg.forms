"""Example 6 — Canonical value semantics laboratory (ADR-0002).

An educational tour of the canonical reactive value model: how each field kind
is typed in the seed, and how the total, divergence-free operator rules behave.
"""

from __future__ import annotations

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDecimalField,
    ReactiveFloatField,
    ReactiveForm,
    ReactiveIntegerField,
    ReactiveMultipleChoiceField,
)


class CanonicalValuesForm(ReactiveForm):
    # string: a numeric-looking code stays a string ("001" != 1).
    code = ReactiveCharField(label="Choice code", initial="001", required=False)

    # number: integer/float signals are JS numbers.
    quantity = ReactiveIntegerField(label="Quantity", initial=3, required=False)
    ratio = ReactiveFloatField(label="Ratio", initial=1.5, required=False)

    # decimal: a canonical string signal, computed authoritatively with Decimal.
    unit_price = ReactiveDecimalField(label="Unit price", initial="19.99", required=False, decimal_places=2)

    # boolean: unchecked -> false.
    agree = ReactiveBooleanField(label="Agree", required=False)

    # array: multiple choice is an array signal (not expression-addressable in v1).
    tags = ReactiveMultipleChoiceField(
        label="Tags",
        required=False,
        choices=[("a", "Alpha"), ("b", "Beta"), ("c", "Gamma")],
    )

    # empty is field-specific (see the page for the per-kind table).
    note = ReactiveCharField(label="Note", required=False)
    picked = ReactiveChoiceField(
        label="Pick", required=False, choices=[("", "--"), ("x", "X"), ("y", "Y")]
    )

    # computed: exact decimal * number; a division demonstrates /0 -> null.
    line_total = ReactiveDecimalField(
        label="Line total (computed)", required=False, decimal_places=2,
        computed="$quantity * $unit_price",
    )
