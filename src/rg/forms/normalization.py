"""Reactive value normalization (ADR-0002 §1/§2).

Normalization is the *loss-minimizing* layer that maps a field's raw source
(a ``QueryDict`` value, a widget-extracted value, or a native ``initial``
object) to its **canonical reactive value**. The same function feeds both the
client seed (``get_client_signals``) and server-side expression evaluation
(``get_signals``), so the two sides evaluate identical values — the canonical
value is anchored to ``get_signals_json``. The one deliberate exception is a
write-only widget (see :func:`is_write_only`), whose value the client seed
replaces with :func:`canonical_empty` while the server keeps the real one.

Normalization is **not** validation: it never calls ``field.clean()`` (which
would reject *temporarily-invalid* in-progress input such as ``"-"`` or
``"1."``). It is total — it always yields a canonical value.

Canonical types (JS level): ``string``, ``number``, ``boolean``, ``array``,
``null``. ``decimal`` and the temporal/uuid kinds are canonical **strings**.
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from decimal import Decimal
from typing import Any

from django import forms

# A "complete" (not in-progress) number: normalization keeps anything that does
# not match as the original string so typing (``"-"``, ``"1."``) is never
# destroyed, while a clean number becomes a real JS number.
_COMPLETE_INT = re.compile(r"[+-]?\d+$")
_COMPLETE_NUM = re.compile(r"[+-]?(\d+(\.\d+)?|\.\d+)([eE][+-]?\d+)?$")

# Canonical JS-level type per field kind. Used by the ADR-0002 §5 system check
# (only ``array`` is rejected in v1) and documents the seed's typing.
_CANONICAL_TYPE = {
    "string": "string",
    "choice": "string",
    "decimal": "string",
    "date": "string",
    "time": "string",
    "datetime": "string",
    "uuid": "string",
    "number": "number",
    "boolean": "boolean",
    "multiple_choice": "array",
    "file": "null",
}


def field_kind(field: forms.Field) -> str:
    """Classify a Django/reactive field into a normalization kind.

    Order matters because of Django's field inheritance (``FloatField`` and
    ``DecimalField`` subclass ``IntegerField``; ``UUIDField``/``EmailField``/
    ``URLField`` subclass ``CharField``; ``MultipleChoiceField`` subclasses
    ``ChoiceField``; ``ImageField`` subclasses ``FileField``).
    """
    if isinstance(field, forms.FileField):
        return "file"
    if isinstance(field, forms.BooleanField):  # incl. NullBooleanField
        return "boolean"
    if isinstance(field, forms.MultipleChoiceField):
        return "multiple_choice"
    if isinstance(field, forms.ChoiceField):  # incl. TypedChoiceField
        return "choice"
    if isinstance(field, forms.DecimalField):
        return "decimal"
    if isinstance(field, (forms.FloatField, forms.IntegerField)):
        return "number"
    if isinstance(field, forms.DateTimeField):
        return "datetime"
    if isinstance(field, forms.DateField):
        return "date"
    if isinstance(field, forms.TimeField):
        return "time"
    if isinstance(field, forms.UUIDField):
        return "uuid"
    return "string"  # CharField / EmailField / URLField / SlugField / ...


def canonical_type(field: forms.Field) -> str:
    """The canonical JS-level type (``string``/``number``/``boolean``/``array``/``null``)."""
    return _CANONICAL_TYPE[field_kind(field)]


def canonical_empty(field: forms.Field) -> Any:
    """The canonical *empty* value for a field kind (ADR-0002 §2 table).

    Datastar preserves a predefined signal's type on bind, so the empty value's
    type must match the field's canonical type.
    """
    kind = field_kind(field)
    if kind == "number":
        return None
    if kind == "boolean":
        return False
    if kind == "multiple_choice":
        return []
    if kind == "file":
        return None
    return ""  # string / choice / decimal / date / time / datetime / uuid


def is_write_only(widget: forms.Widget) -> bool:
    """Whether a widget opts out of round-tripping its value back to the client.

    ``PasswordInput`` sets ``render_value = False`` by default; Django honors it
    in ``Widget.get_context``, which the reactive render path bypasses on both
    sides (the client seed builds values from the field, and the shipped
    templates write the ``value`` attribute themselves). The predicate lives
    beside :func:`canonical_empty` because the two are always used together —
    a write-only field is seeded with its canonical empty value — and because
    both the form (seed) and the template tag (rendered value) must agree on
    what counts as write-only or the suppression would apply on one side only.

    Duck-typed rather than ``isinstance(widget, forms.PasswordInput)`` so a
    custom widget can opt out with the same flag.
    """
    return getattr(widget, "render_value", True) is False


# --------------------------------------------------------------------------- #
# Per-kind converters
# --------------------------------------------------------------------------- #
def _norm_number(raw: Any) -> Any:
    """valid -> int/float; empty -> None; in-progress/invalid -> original string.

    Never emits a non-finite float (``NaN``/``Infinity``), which is not valid
    JSON and would fail at Datastar's parse boundary: a non-finite native float
    or overflowing ``Decimal`` maps to the canonical empty (``None``), and an
    overflowing numeric string (``"1e9999"``) is kept as its original string
    (representable, and coerced to ``null`` by arithmetic on both sides).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return raw if math.isfinite(raw) else None
    if isinstance(raw, Decimal):
        f = float(raw)
        return f if math.isfinite(f) else None
    s = str(raw).strip()
    if s == "":
        return None
    if _COMPLETE_INT.match(s):
        return int(s)
    if _COMPLETE_NUM.match(s):
        f = float(s)
        return f if math.isfinite(f) else str(raw)  # overflow -> keep representable
    return str(raw)  # temporarily-invalid — keep representable, do not null


def _norm_decimal(raw: Any) -> str:
    """Decimal is a canonical *string* (JS numbers can't hold it exactly)."""
    if raw is None:
        return ""
    if isinstance(raw, Decimal):
        return str(raw)
    return str(raw).strip()


def _norm_boolean(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "on", "1", "yes")
    return bool(raw)


def _norm_array(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(v) for v in raw]
    return [str(raw)]


def _norm_string(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw)


def _norm_date(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    if isinstance(raw, _dt.datetime):
        raw = raw.date()
    if isinstance(raw, _dt.date):
        return raw.isoformat()
    return str(raw)


def _norm_time(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    if isinstance(raw, _dt.datetime):
        raw = raw.time()
    if isinstance(raw, _dt.time):
        return raw.strftime("%H:%M")
    return str(raw)


def _norm_datetime(raw: Any) -> str:
    if raw is None or raw == "":
        return ""
    if isinstance(raw, _dt.datetime):
        from django.utils.timezone import is_aware, localtime

        if is_aware(raw):
            raw = localtime(raw)
        # datetime-local inputs require YYYY-MM-DDTHH:MM (no tz offset).
        return str(raw.strftime("%Y-%m-%dT%H:%M"))
    return str(raw)


def normalize_field_value(field: forms.Field, raw: Any) -> Any:
    """Map a raw value to its canonical reactive value for ``field``."""
    kind = field_kind(field)
    if kind == "number":
        return _norm_number(raw)
    if kind == "decimal":
        return _norm_decimal(raw)
    if kind == "boolean":
        return _norm_boolean(raw)
    if kind == "multiple_choice":
        return _norm_array(raw)
    if kind == "date":
        return _norm_date(raw)
    if kind == "time":
        return _norm_time(raw)
    if kind == "datetime":
        return _norm_datetime(raw)
    if kind == "file":
        return None
    return _norm_string(raw)


def extract_raw(field: forms.Field, data: Any, files: Any, html_name: str) -> Any:
    """Extract a field's raw submitted value via its widget (not ``clean``).

    Uses ``widget.value_from_datadict`` so multi-value widgets return a list
    (``getlist`` semantics — ADR-0002 P2) and checkboxes return a real bool
    (P4), before kind-specific normalization.
    """
    return field.widget.value_from_datadict(data, files, html_name)


def normalize_from_datadict(field: forms.Field, data: Any, files: Any, html_name: str) -> Any:
    """Extract + normalize a bound field's value from request data."""
    return normalize_field_value(field, extract_raw(field, data, files, html_name))


__all__ = [
    "field_kind",
    "canonical_type",
    "canonical_empty",
    "is_write_only",
    "normalize_field_value",
    "extract_raw",
    "normalize_from_datadict",
]
