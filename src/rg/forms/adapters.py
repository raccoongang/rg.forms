"""JSON-signals -> Django form-data adapter (ADR-0004 §2a).

An incremental-validation request sends the canonical Datastar signal JSON
(ADR-0002), not a form POST. This adapter maps that JSON into the ``QueryDict``
a Django form binds, applying the mapping table below, **scope authorization**
(a decoded scope must belong to the form being validated), and **signal-scope
filtering** (only the current form's scope subtree is read).

===========================  =====================================
Signal (canonical)           Django form-data
===========================  =====================================
scoped ``rgForms.<scope>.n``  prefixed HTML name ``form-0-n``
unscoped ``n``                ``n``
array value                   multiple entries (``setlist``)
boolean ``true``              the widget's checked value (``"on"``)
boolean ``false``             key **absent**
``null`` / empty              the field's empty form representation
external / reserved signals   dropped (never become form fields)
file inputs                   skipped (files validate on submit only)
===========================  =====================================
"""

from __future__ import annotations

from typing import Any

from django.http import QueryDict

from .normalization import field_kind
from .scoping import RESERVED_NAMESPACE

_TRUTHY_STRINGS = frozenset({"true", "on", "1", "yes"})


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY_STRINGS
    return bool(value)


def _checkbox_value(field: Any) -> str:
    """The value a checked checkbox submits (Django reads presence -> True)."""
    return "on"


def signals_to_querydict(form: Any, signals: dict[str, Any]) -> QueryDict:
    """Adapt received canonical signals into form data for ``form``.

    Reads **only** the current form's scope subtree (signal-scope filtering) and
    keys every entry by the field's prefixed HTML name. ``form`` supplies the
    field set and prefix; rebind with e.g. ``type(form)(qd, prefix=form.prefix)``.
    """
    qd = QueryDict(mutable=True)
    scope = getattr(form, "reactive_scope", None)
    if scope:
        subtree = (signals.get(RESERVED_NAMESPACE) or {}).get(scope) or {}
    else:
        # Unscoped: read top-level field keys, ignoring any rgForms subtree from
        # other forms on the page (that is not a declared field name).
        subtree = signals or {}

    for name, field in form.fields.items():
        if name not in subtree:
            continue
        value = subtree.get(name)
        html_name = form.add_prefix(name)
        kind = field_kind(field)

        if kind == "file":
            continue  # files validate on submit only
        if kind == "boolean":
            if _is_true(value):
                qd[html_name] = _checkbox_value(field)
            # false -> key absent (native unchecked-checkbox semantics)
            continue
        if kind == "multiple_choice":
            if isinstance(value, (list, tuple)):
                qd.setlist(html_name, [str(v) for v in value])
            elif value in (None, ""):
                qd.setlist(html_name, [])
            else:
                qd.setlist(html_name, [str(value)])
            continue
        if value is None:
            qd[html_name] = ""  # field's empty form representation
        else:
            qd[html_name] = str(value)

    return qd


__all__ = ["signals_to_querydict"]
