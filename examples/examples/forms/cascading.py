"""Retained feature demo — cascading / dependent dropdowns.

A distinct feature from the reactive-expression model: dependent selects via
``choices_from`` + ``depends_on`` with server-side re-render.
"""

from __future__ import annotations

from django import forms

from rg.forms import ReactiveChoiceField, ReactiveDecimalField, ReactiveForm, ReactiveIntegerField

from .. import services


class CascadingForm(ReactiveForm):
    category = ReactiveChoiceField(
        label="Category",
        choices_from=services.get_categories,
        value_field="id",
        label_field="name",
        empty_choice="-- Select Category --",
    )
    product = ReactiveChoiceField(
        label="Product",
        choices_from=services.get_products_for_category,
        depends_on=["category"],
        value_field="id",
        label_template="{name} (${price})",
        empty_choice="-- Select Product --",
        empty_choice_no_parent="-- Select Category First --",
    )
    quantity = ReactiveIntegerField(label="Quantity", min_value=1, initial=1)
    unit_price = ReactiveDecimalField(widget=forms.HiddenInput(), required=False, initial=0)

    def clean(self):
        cleaned = super().clean()
        category_id = cleaned.get("category")
        product_id = cleaned.get("product")
        if product_id and category_id:
            product = services.get_product_by_id(product_id)
            if product and str(product["category_id"]) != str(category_id):
                self.add_error("product", "This product does not belong to the selected category.")
        return cleaned
