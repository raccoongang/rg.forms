"""Template tags for rendering reactive forms with Datastar integration."""

from django import template
from django.forms import BoundField
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


def get_reactive_field(bound_field: BoundField):
    """Get the underlying reactive field from a BoundField."""
    return bound_field.field


def has_reactive_attrs(field) -> bool:
    """Check if a field has any reactive attributes."""
    return any([
        getattr(field, "visible_when", None),
        getattr(field, "required_when", None),
        getattr(field, "computed", None),
    ])


@register.simple_tag
def reactive_wrapper_attrs(bound_field: BoundField) -> str:
    """Generate wrapper div attributes for a reactive field.

    Returns attributes like data-show for the field container.

    Usage:
        <div class="field" {% reactive_wrapper_attrs form.my_field %}>
            ...
        </div>
    """
    field = get_reactive_field(bound_field)
    attrs = []

    # visible_when -> data-show
    visible_when = getattr(field, "visible_when", None)
    if visible_when:
        attrs.append(f'data-show="{visible_when}"')

    return mark_safe(" ".join(attrs))


@register.simple_tag
def reactive_input_attrs(bound_field: BoundField) -> str:
    """Generate input element attributes for a reactive field.

    Returns attributes like data-bind, data-computed for the input element.

    Usage:
        <input {% reactive_input_attrs form.my_field %} ...>
    """
    field = get_reactive_field(bound_field)
    field_name = bound_field.name
    attrs = []

    # Always add data-bind for two-way binding (no $ prefix in data-bind)
    attrs.append(f"data-bind:{field_name}")

    # computed -> data-computed (for readonly computed fields)
    computed = getattr(field, "computed", None)
    if computed:
        attrs.append(f'data-computed="{computed}"')
        attrs.append("readonly")

    return mark_safe(" ".join(attrs))


@register.simple_tag
def reactive_signals(form) -> str:
    """Generate data-signals attribute value for a form.

    Usage:
        <form data-signals="{% reactive_signals form %}">
    """
    if hasattr(form, "get_signals_json"):
        return mark_safe(form.get_signals_json())
    return "{}"


@register.inclusion_tag("rg_forms/field.html")
def render_reactive_field(bound_field: BoundField, **kwargs):
    """Render a complete reactive field with wrapper and input.

    Usage:
        {% render_reactive_field form.my_field %}
        {% render_reactive_field form.my_field label="Custom Label" %}
    """
    field = get_reactive_field(bound_field)

    return {
        "field": bound_field,
        "label": kwargs.get("label", bound_field.label),
        "help_text": kwargs.get("help_text", bound_field.help_text),
        "visible_when": getattr(field, "visible_when", None),
        "required_when": getattr(field, "required_when", None),
        "computed": getattr(field, "computed", None),
        "is_required": bound_field.field.required,
        "field_name": bound_field.name,
        "widget_type": bound_field.field.widget.__class__.__name__.lower(),
        "errors": bound_field.errors,
    }


@register.filter
def signal_name(field_name: str) -> str:
    """Convert a field name to a Datastar signal reference.

    Usage:
        {{ "my_field"|signal_name }} -> $my_field
    """
    return f"${field_name}"


@register.simple_tag
def required_indicator(bound_field: BoundField) -> str:
    """Generate a required indicator that respects required_when.

    Returns a span with data-show if required_when is set.

    Usage:
        {% required_indicator form.my_field %}
    """
    field = get_reactive_field(bound_field)
    required_when = getattr(field, "required_when", None)

    if required_when:
        # Dynamic required indicator
        return format_html(
            '<span class="has-text-danger" data-show="{}">*</span>',
            required_when
        )
    elif bound_field.field.required:
        # Static required indicator
        return mark_safe('<span class="has-text-danger">*</span>')

    return ""
