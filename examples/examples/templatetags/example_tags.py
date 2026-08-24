"""Example-only template tags.

``render_minimal_field`` demonstrates a *second* design-system adapter (ADR-0001):
it reuses the exact same rendering **context** that the shipped ``field.html``
gets — by calling the library's ``render_reactive_field`` inclusion tag as a
plain function (it returns its context dict) — and renders it through a
different, minimal template. Same contract, different markup, full fidelity
(binding, visibility, incremental-validation handler, and aria all survive).
"""

from __future__ import annotations

from django import template
from django.forms import BoundField
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from rg.forms.templatetags.reactive_forms import render_reactive_field

register = template.Library()


@register.simple_tag
def render_minimal_field(bound_field: BoundField, **kwargs) -> str:
    context = render_reactive_field(bound_field, **kwargs)
    return mark_safe(render_to_string("examples/design_systems/_minimal_field.html", context))
