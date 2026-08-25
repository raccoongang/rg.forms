"""Additional example — widget compatibility gallery (ADR-0001).

Shows which widgets the shipped reference template renders as *first-class
reactive* controls (text-family inputs, select, multi-select, checkbox,
textarea) versus those it renders via Django's *native fallback* (radio,
multi-checkbox, file, and custom widgets) — correct, but without reactive attrs
until you override the template for your design system.
"""

from __future__ import annotations

from django import forms

from rg.forms import (
    ReactiveBooleanField,
    ReactiveCharField,
    ReactiveChoiceField,
    ReactiveDateField,
    ReactiveForm,
    ReactiveMultipleChoiceField,
)

_COLORS = [("r", "Red"), ("g", "Green"), ("b", "Blue")]


class WidgetGalleryForm(ReactiveForm):
    # --- first-class reactive widgets ---
    text = ReactiveCharField(label="Text (first-class)", required=False, placeholder="reactive input")
    dropdown = ReactiveChoiceField(label="Select (first-class)", required=False, choices=[("", "--")] + _COLORS)
    multi = ReactiveMultipleChoiceField(label="Multi-select (first-class)", required=False, choices=_COLORS)
    agree = ReactiveBooleanField(label="Checkbox (first-class)", required=False)
    note = ReactiveCharField(label="Textarea (first-class)", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    day = ReactiveDateField(label="Date (first-class)", required=False)

    # --- native fallback widgets (rendered by Django, no reactive attrs) ---
    radio = ReactiveChoiceField(label="Radio (fallback)", required=False, choices=_COLORS, widget=forms.RadioSelect)
    checkboxes = ReactiveMultipleChoiceField(
        label="Checkbox group (fallback)", required=False, choices=_COLORS, widget=forms.CheckboxSelectMultiple
    )
    attachment = ReactiveCharField(label="File (fallback)", required=False, widget=forms.FileInput)
