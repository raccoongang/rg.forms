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
    widget = field.widget

    # Collect HTML5 validation attributes
    html5_attrs = {}
    if field.required:
        html5_attrs["required"] = True
    if hasattr(field, "min_value") and field.min_value is not None:
        html5_attrs["min"] = field.min_value
    if hasattr(field, "max_value") and field.max_value is not None:
        html5_attrs["max"] = field.max_value
    if hasattr(field, "max_length") and field.max_length is not None:
        html5_attrs["maxlength"] = field.max_length
    if hasattr(field, "min_length") and field.min_length is not None:
        html5_attrs["minlength"] = field.min_length

    return {
        "field": bound_field,
        "label": kwargs.get("label", bound_field.label),
        "help_text": kwargs.get("help_text", bound_field.help_text),
        "visible_when": getattr(field, "visible_when", None),
        "required_when": getattr(field, "required_when", None),
        "computed": getattr(field, "computed", None),
        "disabled_when": getattr(field, "disabled_when", None),
        "read_only_when": getattr(field, "read_only_when", None),
        "help_text_when": getattr(field, "help_text_when", None),
        "placeholder_when": getattr(field, "placeholder_when", None),
        "min_when": getattr(field, "min_when", None),
        "max_when": getattr(field, "max_when", None),
        "is_required": field.required,
        "field_name": bound_field.name,
        "widget_type": widget.__class__.__name__.lower(),
        "errors": bound_field.errors,
        "html5_attrs": html5_attrs,
        "choices": getattr(field, "choices", None),
    }


@register.inclusion_tag("rg_forms/form.html")
def render_reactive_form(form, submit_label="Submit", action=""):
    """Render a complete reactive form with all fields.

    When ``action`` is provided, the form submits via Datastar ``@post``
    instead of native form submit. Validation errors are patched in via
    SSE without a full page reload.

    Usage:
        {# Standard form submission (full page reload) #}
        {% render_reactive_form form %}

        {# SSE submission (partial update via Datastar) #}
        {% render_reactive_form form action="/my-url/" %}
        {% render_reactive_form form submit_label="Register" action=action_url %}
    """
    return {
        "form": form,
        "submit_label": submit_label,
        "action": action,
    }


@register.inclusion_tag("rg_forms/field_group.html")
def render_field_group(form, group_name: str):
    """Render a field group with its fields.

    Usage:
        {% render_field_group form "personal_info" %}
    """
    group = form.get_group(group_name)
    if not group:
        return {"group": None, "fields": []}

    fields = form.get_fields_in_group(group_name)

    return {
        "form": form,
        "group": group,
        "group_name": group_name,
        "fields": fields,
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
