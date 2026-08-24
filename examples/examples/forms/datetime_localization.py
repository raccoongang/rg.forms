"""Additional example — date / time / datetime canonical values (ADR-0002).

Exercises the temporal canonical types: each is a canonical **string** signal
(``YYYY-MM-DD``, ``HH:MM``, ``YYYY-MM-DDTHH:MM``), seeded and round-tripped
losslessly, and validated on the server (an event may not start in the past).
"""

from __future__ import annotations

import datetime as _dt

from rg.forms import (
    ReactiveCharField,
    ReactiveDateField,
    ReactiveDateTimeField,
    ReactiveForm,
    ReactiveTimeField,
)


class EventForm(ReactiveForm):
    title = ReactiveCharField(label="Event title")
    event_date = ReactiveDateField(label="Date")
    doors_open = ReactiveTimeField(label="Doors open")
    starts_at = ReactiveDateTimeField(
        label="Starts at",
        help_text="Local datetime; must not be in the past.",
    )

    def clean_starts_at(self):
        value = self.cleaned_data.get("starts_at")
        if value is not None:
            now = _dt.datetime.now(tz=value.tzinfo) if value.tzinfo else _dt.datetime.now()
            if value < now:
                from django.core.exceptions import ValidationError

                raise ValidationError("The event cannot start in the past.")
        return value
