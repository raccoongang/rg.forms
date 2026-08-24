"""Template tags for rendering reactive forms with Datastar integration.

Every author-written expression is **compiled** to a Datastar/JS string before
it reaches an attribute (ADR-0002: transmitted compiled, never raw) and, inside
a prefixed form or formset row, field references are **scoped** to that row's
signal namespace (ADR-0003). Compilation and scoping share one service
(``scoping.compile_expression``); for an unprefixed form the scope mapping is
the identity.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template
from django.core.exceptions import ImproperlyConfigured
from django.forms import BoundField
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..scoping import RESERVED_NAMESPACE, compile_expression, encode_scope, signal_path

# Sentinel distinguishing "validate_action omitted" (inherit action) from an
# explicit ``validate_action=""`` (validate against the current URL) — ADR-0004 §4.
_UNSET = object()

register = template.Library()

# Widget class names (lowercased) the shipped reference template renders as a
# single HTML ``<input>``. Anything not here — and not select/checkbox/textarea
# — falls back to Django's native widget rendering rather than a wrong input.
_SIMPLE_INPUT_WIDGETS = frozenset(
    {
        "textinput",
        "numberinput",
        "emailinput",
        "urlinput",
        "dateinput",
        "timeinput",
        "datetimeinput",
        "passwordinput",
    }
)

# Maps a Django widget class name (lowercased) to the HTML ``<input type>``
# attribute an override template should render.
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
_WIDGET_ATTRS_EXCLUDE = frozenset(
    {"id", "name", "required", "disabled", "readonly", "maxlength", "minlength", "min", "max"}
)


# --------------------------------------------------------------------------- #
# Scope + compilation helpers
# --------------------------------------------------------------------------- #
def _field_scope(bound_field: BoundField) -> tuple[str | None, set[str]]:
    """Return ``(scope, field_names)`` for a bound field's form.

    The scope is the Base32 encoding of the form prefix (``None`` when
    unprefixed); ``field_names`` are the form's declared fields, used so only
    real field references are rewritten to the scoped path.
    """
    form = bound_field.form
    prefix = getattr(form, "prefix", "") or ""
    scope = encode_scope(prefix) if prefix else None
    field_names = set(getattr(form, "fields", {}) or {})
    return scope, field_names


def _make_compiler(bound_field: BoundField) -> Callable[[str], str]:
    """A ``compile(expr) -> js`` closure bound to the field's scope."""
    scope, field_names = _field_scope(bound_field)

    def compile_expr(expr: str) -> str:
        return compile_expression(expr, scope=scope, field_names=field_names)

    return compile_expr


def _js_string(value) -> str:
    """Render ``value`` as a JS string literal for an expression."""
    return json.dumps(str(value))


def _required_expr(
    visible_when: str | None,
    required_when: str | None,
    is_required: bool,
    compile_expr: Callable[[str], str],
) -> str | None:
    """Build the compiled ``data-attr:required`` expression.

    Composed at the DSL level then compiled once, so the derived expression is
    scoped exactly like its sources (ADR-0003 §2 — derived expressions are built
    from already-scoped sources). A field hidden by ``visible_when`` is never
    required, so an invisible empty input cannot block submission.
    """
    if visible_when and required_when:
        return compile_expr(f"({visible_when}) && ({required_when})")
    if required_when:
        return compile_expr(required_when)
    if visible_when and is_required:
        return compile_expr(visible_when)
    return None


def _string_when_expr(when: dict | None, compile_expr: Callable[[str], str]) -> str | None:
    """First-match ternary yielding a string (placeholder_when), conditions compiled."""
    if not when:
        return None
    expr = "''"
    for cond, val in reversed(list(when.items())):
        expr = f"({compile_expr(cond)}) ? {_js_string(val)} : {expr}"
    return expr


def _number_when_expr(when: dict | None, compile_expr: Callable[[str], str]) -> str | None:
    """First-match ternary yielding a number (min_when/max_when), conditions compiled."""
    if not when:
        return None
    expr = "null"
    for cond, val in reversed(list(when.items())):
        expr = f"({compile_expr(cond)}) ? {val} : {expr}"
    return expr


def _bind_attr(bound_field: BoundField, scope: str | None) -> str:
    """The ``data-bind`` attribute for a field's control.

    Scoped forms use the attribute *value* form (``data-bind="rgForms.<scope>.
    role"``) because the browser lowercases attribute *names* and would corrupt
    the camelCase ``rgForms`` path in the keyed form. Unprefixed forms keep the
    byte-identical keyed form ``data-bind:role`` (ADR-0003 §1).
    """
    name = bound_field.name
    if scope:
        return format_html('data-bind="{}.{}.{}"', RESERVED_NAMESPACE, scope, name)
    return mark_safe(f"data-bind:{name}")


# --------------------------------------------------------------------------- #
# Incremental validation (ADR-0004)
# --------------------------------------------------------------------------- #
def control_ids(bound_field: BoundField) -> dict[str, str]:
    """Deterministic, formset-safe ids for a field's parts (ADR-0004 §6).

    ``control_id`` is ``id_for_label`` when available; when it is empty (e.g.
    ``auto_id=False``) *and the field is incrementally validated*, it falls back
    to an injective, id-safe Base32 of the HTML name so "patch only this field"
    stays implementable. A non-incremental field with an empty id keeps its
    (empty) id — output is unchanged for it.
    """
    field = bound_field.field
    base = bound_field.id_for_label or ""
    if not base and getattr(field, "validate_on", None):
        token = base64.b32encode(bound_field.html_name.encode("utf-8")).decode("ascii")
        base = "rg_field_" + token.rstrip("=").lower()
    if not base:
        return {"control_id": "", "wrapper_id": "", "help_id": "", "error_id": ""}
    return {
        "control_id": base,
        "wrapper_id": f"{base}_field",
        "help_id": f"{base}_help",
        "error_id": f"{base}_error",
    }


def _js_str(value: str) -> str:
    """A safe JS string literal for an expression.

    Uses ``json.dumps`` (a JSON string is a valid JS string literal) with the
    default ``ensure_ascii=True``, which escapes all non-ASCII — including the
    JS-hostile line separators U+2028/U+2029 and control/newline characters — so
    the value is safe inside a ``data-on`` attribute (ADR-0004 §1a: proper
    JS-string encoding, never hand-built quoting).
    """
    return json.dumps(str(value))


def append_field_discriminator(url: str, field_path: str) -> str:
    """Append ``?__rg_field=<path>`` via real URL parsing (ADR-0004 §3).

    Preserves any existing query string and fragment. ``url=""`` yields
    ``?__rg_field=<path>`` — a request against the current URL.
    """
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.append(("__rg_field", field_path))
    return urlunsplit(parts._replace(query=urlencode(query)))


def _resolve_validate_action(kwargs: dict):
    """Resolve the validation URL per the ADR-0004 §4 unset/empty/inherit rules."""
    action = kwargs.get("action", "")
    if "validate_action" not in kwargs or kwargs["validate_action"] is _UNSET:
        return action  # omitted -> inherit action (which may be "" = current URL)
    return kwargs["validate_action"]  # "" (current URL) | a URL | None (unresolvable)


def _validate_attr(
    bound_field: BoundField,
    scope: str | None,
    kwargs: dict,
) -> str:
    """Build the ``data-on:*`` validate handler + ``data-indicator`` for a field.

    Emits a **default Datastar JSON-signal request** (not ``contentType:'form'``)
    to ``<action>?__rg_field=<path>`` carrying ``X-CSRFToken`` and
    ``X-RG-Validate-Field`` headers (ADR-0004 §1/§1a/§3/§5). The pending signal
    is a local, ``_``-prefixed nested path so it never enters backend requests.
    """
    field = bound_field.field
    validate_on = getattr(field, "validate_on", None)
    if not validate_on:
        return ""

    resolved = _resolve_validate_action(kwargs)
    if resolved is None:
        raise ImproperlyConfigured(
            f"Field {bound_field.name!r} has validate_on={validate_on!r} but no "
            "resolvable validation action. Pass validate_action to "
            "render_reactive_form/render_reactive_field."
        )

    name = bound_field.name
    path = signal_path(scope, name)
    url = append_field_discriminator(resolved, path)
    token = kwargs.get("csrf_token") or ""

    event = "blur" if validate_on == "blur" else "change"
    debounce = getattr(field, "debounce", None)
    mods = f"__debounce.{debounce}ms" if (validate_on == "change" and debounce) else ""

    handler = (
        f"@post({_js_str(url)}, {{headers: {{"
        f"{_js_str('X-CSRFToken')}: {_js_str(token)}, "
        f"{_js_str('X-RG-Validate-Field')}: {_js_str(path)}"
        f"}}}})"
    )
    if scope:
        indicator = f"_{RESERVED_NAMESPACE}.{scope}.validating.{name}"
    else:
        indicator = f"_{RESERVED_NAMESPACE}.validating.{name}"

    return format_html('data-on:{}{}="{}" data-indicator="{}"', event, mods, handler, indicator)


# --------------------------------------------------------------------------- #
# Public helpers
# --------------------------------------------------------------------------- #
def get_reactive_field(bound_field: BoundField):
    """Get the underlying reactive field from a BoundField."""
    return bound_field.field


def has_reactive_attrs(field) -> bool:
    """Check if a field has any reactive attributes."""
    return any(
        [
            getattr(field, "visible_when", None),
            getattr(field, "required_when", None),
            getattr(field, "computed", None),
        ]
    )


@register.simple_tag
def reactive_wrapper_attrs(bound_field: BoundField) -> str:
    """Generate wrapper div attributes (compiled ``data-show``) for a field."""
    field = get_reactive_field(bound_field)
    compile_expr = _make_compiler(bound_field)
    attrs = []

    visible_when = getattr(field, "visible_when", None)
    if visible_when:
        attrs.append(format_html('data-show="{}"', compile_expr(visible_when)))

    return mark_safe(" ".join(attrs))


@register.simple_tag
def reactive_input_attrs(bound_field: BoundField) -> str:
    """Generate input element attributes (scoped ``data-bind``, compiled ``data-computed``)."""
    field = get_reactive_field(bound_field)
    scope, _ = _field_scope(bound_field)
    compile_expr = _make_compiler(bound_field)
    attrs = [str(_bind_attr(bound_field, scope))]

    computed = getattr(field, "computed", None)
    if computed:
        attrs.append(format_html('data-computed="{}"', compile_expr(computed)))
        attrs.append("readonly")

    return mark_safe(" ".join(attrs))


def _safe_signals_value(json_text: str) -> str:
    """Escape a JSON signals string for a **single-quoted** ``data-signals`` attribute.

    The documented (and required) usage wraps the value in single quotes because
    the JSON itself uses double quotes:
    ``<form data-signals='{% reactive_signals form %}'>``. Form values can contain
    ``'``, ``&`` or ``<`` (from bound/initial data), which would otherwise break
    out of the attribute — an HTML-injection vector. We escape exactly the
    characters dangerous in a single-quoted attribute (``&``, ``'``, ``<``, ``>``)
    and keep ``"`` literal so the JSON stays readable; the browser decodes the
    entities before Datastar parses the attribute.
    """
    escaped = json_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#x27;")
    return mark_safe(escaped)


@register.simple_tag
def reactive_signals(form) -> str:
    """Generate data-signals attribute value for a form."""
    if hasattr(form, "get_signals_json"):
        return _safe_signals_value(form.get_signals_json())
    return "{}"


@register.simple_tag
def reactive_formset_signals(formset) -> str:
    """Generate the combined ``data-signals`` seed for a whole formset.

    A single form cannot see its siblings, so this tag owns the merge: it emits
    one nested ``rgForms.<scope>.<field>`` entry per (row, field) under the same
    paths the row inputs bind to, so initial values line up for every row
    (ADR-0003 §3).

    Usage::

        <form data-signals='{% reactive_formset_signals formset %}'>
    """
    combined: dict = {}
    flat: dict = {}
    for form in formset:
        signals = form.get_signals() if hasattr(form, "get_signals") else {}
        scope = getattr(form, "reactive_scope", None)
        if scope is None and getattr(form, "prefix", None):
            scope = encode_scope(form.prefix)
        if scope:
            combined[scope] = signals
        else:
            flat.update(signals)

    seed: dict = dict(flat)
    if combined:
        seed[RESERVED_NAMESPACE] = combined
    # allow_nan=False: never emit invalid JSON (NaN/Infinity) — normalization
    # already strips non-finite floats.
    return _safe_signals_value(json.dumps(seed, default=str, allow_nan=False))


@register.inclusion_tag("rg_forms/field.html")
def render_reactive_field(bound_field: BoundField, **kwargs):
    """Render a complete reactive field with wrapper and input.

    Usage:
        {% render_reactive_field form.my_field %}
        {% render_reactive_field form.my_field label="Custom Label" %}
    """
    field = get_reactive_field(bound_field)
    widget = field.widget
    scope, _ = _field_scope(bound_field)
    compile_expr = _make_compiler(bound_field)

    def maybe(expr: str | None) -> str | None:
        return compile_expr(expr) if expr else None

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

    widget_attrs = {key: value for key, value in widget.attrs.items() if key not in _WIDGET_ATTRS_EXCLUDE}

    # Raw metadata (kept for introspection / custom templates).
    visible_when = getattr(field, "visible_when", None)
    required_when = getattr(field, "required_when", None)
    placeholder_when = getattr(field, "placeholder_when", None)
    min_when = getattr(field, "min_when", None)
    max_when = getattr(field, "max_when", None)
    help_text_when = getattr(field, "help_text_when", None)

    # Compiled + scoped emittable expressions (what the template drops into
    # data-* attributes). Conditions in help_text_when are compiled in place.
    help_text_when_compiled = (
        {compile_expr(cond): text for cond, text in help_text_when.items()} if help_text_when else None
    )

    # Deterministic ids (ADR-0004 §6) and the minimal a11y contract.
    ids = control_ids(bound_field)
    errors = bound_field.errors
    has_help = bool(bound_field.help_text or help_text_when)
    # The template shows the error OR the help text (mutually exclusive), so
    # aria-describedby points at whichever is actually rendered.
    describedby = []
    if errors and ids["error_id"]:
        describedby.append(ids["error_id"])
    elif has_help and ids["help_id"]:
        describedby.append(ids["help_id"])

    # Per-control attributes: the incremental-validation handler + pending
    # indicator, plus aria-invalid / aria-describedby. Emitted together so the
    # single-field SSE patch re-renders them and the field keeps its behavior.
    validate_attr = _validate_attr(bound_field, scope, kwargs)
    control_attr_parts = []
    if validate_attr:
        control_attr_parts.append(str(validate_attr))
    if errors:
        control_attr_parts.append('aria-invalid="true"')
    if describedby:
        control_attr_parts.append(str(format_html('aria-describedby="{}"', " ".join(describedby))))
    control_attrs = mark_safe(" ".join(control_attr_parts))

    return {
        "field": bound_field,
        "formatted_value": formatted_value,
        "label": kwargs.get("label", bound_field.label),
        "help_text": kwargs.get("help_text", bound_field.help_text),
        # Compiled + scoped expressions used directly by the template.
        "visible_when": maybe(visible_when),
        "required_when": maybe(required_when),
        "computed": maybe(getattr(field, "computed", None)),
        "disabled_when": maybe(getattr(field, "disabled_when", None)),
        "read_only_when": maybe(getattr(field, "read_only_when", None)),
        "help_text_when": help_text_when_compiled,
        "placeholder_when": placeholder_when,
        "min_when": min_when,
        "max_when": max_when,
        "is_required": field.required,
        "field_name": bound_field.name,
        "widget_type": widget_type,
        "input_type": _INPUT_TYPE_MAP.get(widget_type, "text"),
        "is_simple_input": widget_type in _SIMPLE_INPUT_WIDGETS,
        "widget_attrs": widget_attrs,
        # The scoped/keyed data-bind attribute for the control.
        "bind_attr": _bind_attr(bound_field, scope),
        # Reactive-attribute expressions derived from *_when metadata.
        "required_expr": _required_expr(visible_when, required_when, field.required, compile_expr),
        "placeholder_expr": _string_when_expr(placeholder_when, compile_expr),
        "min_expr": _number_when_expr(min_when, compile_expr),
        "max_expr": _number_when_expr(max_when, compile_expr),
        "errors": errors,
        "html5_attrs": html5_attrs,
        "choices": getattr(field, "choices", None),
        # Incremental validation (ADR-0004 §6): stable ids + per-control attrs.
        "control_id": ids["control_id"],
        "wrapper_id": ids["wrapper_id"],
        "help_id": ids["help_id"],
        "error_id": ids["error_id"],
        "control_attrs": control_attrs,
    }


@register.inclusion_tag("rg_forms/form.html", takes_context=True)
def render_reactive_form(context, form, submit_label="Submit", action="", validate_action=_UNSET):
    """Render a complete reactive form with all fields.

    When ``action`` is provided, the form submits via Datastar ``@post``
    instead of native form submit. Validation errors are patched in via
    SSE without a full page reload.

    ``validate_action`` supplies the URL for declarative incremental validation
    (ADR-0004 §4): omitted -> inherit ``action``; ``""`` -> the current URL; a
    URL -> that URL. The tag is context-aware and forwards the request's CSRF
    token to each field's validate handler.

    Usage:
        {# Standard form submission (full page reload) #}
        {% render_reactive_form form %}

        {# SSE submission (partial update via Datastar) #}
        {% render_reactive_form form action="/my-url/" %}

        {# incremental validation posting to a dedicated URL #}
        {% render_reactive_form form action="/submit/" validate_action="/validate/" %}
    """
    return {
        "form": form,
        "submit_label": submit_label,
        "action": action,
        "validate_action": validate_action,
        "csrf_token": context.get("csrf_token"),
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

    # Compile + scope the group's visible_when using the form's scope. A group
    # inside a prefixed form must scope exactly like its fields (ADR-0003 §2).
    group_visible_when = None
    if group.visible_when:
        prefix = getattr(form, "prefix", "") or ""
        scope = encode_scope(prefix) if prefix else None
        field_names = set(getattr(form, "fields", {}) or {})
        group_visible_when = compile_expression(group.visible_when, scope=scope, field_names=field_names)

    return {
        "form": form,
        "group": group,
        "group_name": group_name,
        "group_visible_when": group_visible_when,
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
    """Generate a required indicator that respects required_when (compiled)."""
    field = get_reactive_field(bound_field)
    required_when = getattr(field, "required_when", None)

    if required_when:
        compile_expr = _make_compiler(bound_field)
        return format_html(
            '<span class="has-text-danger" data-show="{}">*</span>',
            compile_expr(required_when),
        )
    elif bound_field.field.required:
        return mark_safe('<span class="has-text-danger">*</span>')

    return ""
