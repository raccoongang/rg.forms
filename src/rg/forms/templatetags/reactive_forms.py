"""Template tags for rendering reactive forms with Datastar integration."""

from django import template
from django.forms import BoundField
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# Widget class names (lowercased) the shipped reference template renders as a
# single HTML ``<input>``. Anything not here — and not select/checkbox/textarea
# — falls back to Django's native widget rendering rather than a wrong input.
_SIMPLE_INPUT_WIDGETS = frozenset({
    "textinput",
    "numberinput",
    "emailinput",
    "urlinput",
    "dateinput",
    "timeinput",
    "datetimeinput",
    "passwordinput",
})

# Maps a Django widget class name (lowercased) to the HTML ``<input type>``
# attribute an override template should render. ``widget_type`` remains
# available for branching; ``input_type`` is the value to put on the element.
_INPUT_TYPE_MAP = {
    "numberinput": "number",
    "emailinput": "email",
    "urlinput": "url",
    "dateinput": "date",
    "timeinput": "time",
    "datetimeinput": "datetime-local",
    "passwordinput": "password",
}

# Widget attrs managed elsewhere in the render context; excluded from
# ``widget_attrs`` so a consumer that spreads it cannot double-render them.
_WIDGET_ATTRS_EXCLUDE = frozenset({
    "id",
    "name",
    "required",
    "disabled",
    "readonly",
    "maxlength",
    "minlength",
    "min",
    "max",
})


def _required_expr(visible_when: str | None, required_when: str | None, is_required: bool) -> str | None:
    """Build a Datastar expression for the reactive ``required`` attribute.

    Returns ``None`` when the field is unconditionally required (the caller
    renders a static ``required``) or never required. Otherwise returns a JS
    expression suitable for ``data-attr:required``. A field hidden by
    ``visible_when`` is never required, so an invisible empty input cannot
    block native form submission — matching the server, which skips hidden
    fields during validation.
    """
    if visible_when and required_when:
        return f"({visible_when}) && ({required_when})"
    if required_when:
        return required_when
    if visible_when and is_required:
        # Statically required but hideable: required only while visible.
        return visible_when
    return None


def _js_string(value) -> str:
    """Render ``value`` as a single-quoted JS string literal for an expression."""
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _string_when_expr(when: dict | None) -> str | None:
    """Build a first-match ternary yielding a string, e.g. for placeholder_when.

    ``{"$a": "x", "$b": "y"}`` -> ``($a) ? 'x' : (($b) ? 'y' : '')``.
    """
    if not when:
        return None
    expr = "''"
    for cond, val in reversed(list(when.items())):
        expr = f"({cond}) ? {_js_string(val)} : {expr}"
    return expr


def _number_when_expr(when: dict | None) -> str | None:
    """Build a first-match ternary yielding a number, e.g. for min_when/max_when.

    ``{"$a": 1, "$b": 2}`` -> ``($a) ? 1 : (($b) ? 2 : null)``.
    """
    if not when:
        return None
    expr = "null"
    for cond, val in reversed(list(when.items())):
        expr = f"({cond}) ? {val} : {expr}"
    return expr


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

    # Use widget.format_value() so HTML5 inputs (date, datetime-local, time)
    # get values in the format the browser expects (e.g. YYYY-MM-DDTHH:MM).
    raw_value = bound_field.value()
    formatted_value = widget.format_value(raw_value)

    widget_type = widget.__class__.__name__.lower()

    # Sanitized copy of presentational widget attrs (placeholder, autocomplete,
    # autofocus, inputmode, custom data-* …). First-class field kwargs have
    # already been merged into widget.attrs by ReactiveFieldMixin, so they are
    # carried here too. Keys managed elsewhere in this context are dropped.
    widget_attrs = {
        key: value
        for key, value in widget.attrs.items()
        if key not in _WIDGET_ATTRS_EXCLUDE
    }

    visible_when = getattr(field, "visible_when", None)
    required_when = getattr(field, "required_when", None)
    placeholder_when = getattr(field, "placeholder_when", None)
    min_when = getattr(field, "min_when", None)
    max_when = getattr(field, "max_when", None)

    return {
        "field": bound_field,
        "formatted_value": formatted_value,
        "label": kwargs.get("label", bound_field.label),
        "help_text": kwargs.get("help_text", bound_field.help_text),
        "visible_when": visible_when,
        "required_when": required_when,
        "computed": getattr(field, "computed", None),
        "disabled_when": getattr(field, "disabled_when", None),
        "read_only_when": getattr(field, "read_only_when", None),
        "help_text_when": getattr(field, "help_text_when", None),
        "placeholder_when": placeholder_when,
        "min_when": min_when,
        "max_when": max_when,
        "is_required": field.required,
        "field_name": bound_field.name,
        "widget_type": widget_type,
        "input_type": _INPUT_TYPE_MAP.get(widget_type, "text"),
        "is_simple_input": widget_type in _SIMPLE_INPUT_WIDGETS,
        "widget_attrs": widget_attrs,
        # Reactive-attribute expressions derived from the *_when metadata,
        # ready to drop into data-attr:* bindings. None when not applicable.
        "required_expr": _required_expr(visible_when, required_when, field.required),
        "placeholder_expr": _string_when_expr(placeholder_when),
        "min_expr": _number_when_expr(min_when),
        "max_expr": _number_when_expr(max_when),
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
