"""Build-time validation of reactive expressions (ADR-0002 §5).

Every expression a form declares is parsed and validated against the form's
declared fields, its ``Meta.external_signals``, and the reserved ``rgForms``
namespace. Genuinely unknown references, unsupported operands (string operands
to arithmetic), references to array-typed fields, and direct references to the
reserved namespace are reported.

This lands as a Django **system check** emitting *warnings* (``rg_forms.W001``)
to ease adoption; it is intended to graduate to an error in a later minor
release. The pure ``check_form_expressions`` function is also importable for
targeted testing.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from django.core import checks

from .expressions import ExpressionError, parse_expression, validate_ast
from .normalization import field_kind

# Expression slots whose *value* is a single expression string.
_SCALAR_SLOTS = (
    "visible_when",
    "required_when",
    "computed",
    "disabled_when",
    "read_only_when",
)
# Expression slots that are dicts whose *keys* are expression strings.
_DICT_KEY_SLOTS = (
    "help_text_when",
    "placeholder_when",
    "min_when",
    "max_when",
)

_RESERVED = frozenset({"rgForms"})


def iter_form_expressions(form_class: type) -> Iterator[tuple[str, str]]:
    """Yield ``(location_label, expression)`` for every expression on a form.

    Covers per-field scalar and dict-key slots plus group ``visible_when``.
    """
    base_fields = getattr(form_class, "base_fields", {})
    for name, field in base_fields.items():
        for slot in _SCALAR_SLOTS:
            expr = getattr(field, slot, None)
            if expr:
                yield (f"{name}.{slot}", expr)
        for slot in _DICT_KEY_SLOTS:
            mapping = getattr(field, slot, None)
            if mapping:
                for cond in mapping:
                    if cond:
                        yield (f"{name}.{slot}[key]", cond)

    # Group visibility expressions live on Meta.field_groups.
    meta = getattr(form_class, "Meta", None)
    groups = getattr(meta, "field_groups", None) or {}
    for group_name, group in groups.items():
        expr = getattr(group, "visible_when", None)
        if expr:
            yield (f"group:{group_name}.visible_when", expr)


def _external_signals(form_class: type) -> set[str]:
    meta = getattr(form_class, "Meta", None)
    return set(getattr(meta, "external_signals", None) or set())


def check_form_expressions(form_class: type) -> list[str]:
    """Validate all expressions on a form class. Return human-readable errors.

    An empty list means every expression parses and references only declared
    fields / external signals / reserved signals, with no disallowed operands.
    """
    base_fields = getattr(form_class, "base_fields", {})
    field_kinds = {name: field_kind(field) for name, field in base_fields.items()}
    external = _external_signals(form_class)

    problems: list[str] = []

    # A declared external signal may not shadow the reserved namespace.
    for sig in external:
        if sig.split(".")[0] in _RESERVED:
            problems.append(
                f"Meta.external_signals may not declare the reserved '{sig}' ('rgForms' is reserved for the library)."
            )

    for location, expression in iter_form_expressions(form_class):
        try:
            ast = parse_expression(expression)
        except ExpressionError as exc:
            problems.append(f"{location}: could not parse {expression!r}: {exc}")
            continue
        for err in validate_ast(
            ast,
            field_kinds=field_kinds,
            external_signals=external,
            reserved=_RESERVED,
        ):
            problems.append(f"{location}: {err}")

    return problems


def _iter_reactive_form_subclasses() -> Iterator[type]:
    """Best-effort discovery of imported ReactiveForm subclasses."""
    from .forms import ReactiveForm

    seen: set[int] = set()
    stack = list(ReactiveForm.__subclasses__())
    while stack:
        cls = stack.pop()
        if id(cls) in seen:
            continue
        seen.add(id(cls))
        stack.extend(cls.__subclasses__())
        yield cls


def check_reactive_forms(app_configs: Any = None, **kwargs: Any) -> list[checks.CheckMessage]:
    """Django system check over all imported ReactiveForm subclasses."""
    messages: list[checks.CheckMessage] = []
    for form_class in _iter_reactive_form_subclasses():
        for problem in check_form_expressions(form_class):
            messages.append(
                checks.Warning(
                    f"Reactive expression problem in {form_class.__name__}: {problem}",
                    hint=(
                        "Reference only declared fields, Meta.external_signals, or "
                        "reserved signals; '+' is numeric-only; array-typed fields "
                        "cannot be used in expressions in v1."
                    ),
                    obj=form_class,
                    id="rg_forms.W001",
                )
            )
    return messages


__all__ = [
    "iter_form_expressions",
    "check_form_expressions",
    "check_reactive_forms",
]
