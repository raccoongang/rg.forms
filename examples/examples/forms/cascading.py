"""Retained + modernized — cascading / dependent dropdowns.

Country -> region -> city, each level's choices queried server-side. When a
parent changes, the form re-renders via Datastar SSE with the child options
repopulated and any now-invalid child selection reset. Authoritative validation
(region belongs to country, city belongs to region) runs on the server.
"""

from __future__ import annotations

from rg.forms import ReactiveChoiceField, ReactiveForm

from .. import services


class GeoCascadingForm(ReactiveForm):
    country = ReactiveChoiceField(
        label="Country",
        choices_from=services.get_countries,
        value_field="id",
        label_field="name",
        empty_choice="-- Select country --",
    )
    region = ReactiveChoiceField(
        label="Region",
        choices_from=services.get_regions,
        depends_on=["country"],
        value_field="id",
        label_field="name",
        empty_choice="-- Select region --",
        empty_choice_no_parent="-- Select a country first --",
    )
    city = ReactiveChoiceField(
        label="City",
        choices_from=services.get_cities,
        depends_on=["region"],
        value_field="id",
        label_field="name",
        empty_choice="-- Select city --",
        empty_choice_no_parent="-- Select a region first --",
    )

    def clean(self):
        cleaned = super().clean()
        country, region, city = cleaned.get("country"), cleaned.get("region"), cleaned.get("city")
        if region and country and not services.region_belongs_to(region, country):
            self.add_error("region", "This region does not belong to the selected country.")
        if city and region and not services.city_belongs_to(city, region):
            self.add_error("city", "This city does not belong to the selected region.")
        return cleaned


# Back-compat alias (older references / tests).
CascadingForm = GeoCascadingForm
