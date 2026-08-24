"""Scoped signals for prefixed forms and static formsets (ADR-0003).

Inside a Django formset every row renders the *same* logical field name, so
binding a Datastar signal by the unprefixed name collides across rows: typing in
row 0 changes row 1. This module gives each prefixed form its own nested signal
scope under the reserved ``rgForms`` namespace so rows behave independently.

Three surfaces agree on the scope (ADR-0003 §1):

===============  =============================================
Surface          Form
===============  =============================================
Scoped binding   ``data-bind="rgForms.<scope>.role"`` (value form — preserves
                 case; the keyed form would be lowercased by the browser)
Seeding          nested object ``{"rgForms": {"<scope>": {"role": ...}}}``
Expression ref   compiled ``$rgForms.<scope>.role``
===============  =============================================

The scope key is an **injective** Base32 encoding of the Django form prefix
(the rejected ``-``->``_`` idea is not injective: ``a-b_c`` and ``a_b-c`` both
collapse to ``a_b_c``).
"""

from __future__ import annotations

import base64
from collections.abc import Callable

from .expressions import parse_expression, serialize_js

#: The reserved top-level signal namespace (ADR-0002 §5). Authors may not
#: reference it directly and ``Meta.external_signals`` may not declare it.
RESERVED_NAMESPACE = "rgForms"


def encode_scope(prefix: str) -> str:
    """Encode a form prefix into an injective, identifier-safe scope key.

    Properties: injective (Base32 is reversible), always starts with a letter
    (the ``p`` prefix), no ``.``/``-``/leading-``_`` delimiters, Unicode-safe.
    """
    encoded = base64.b32encode(prefix.encode("utf-8")).decode("ascii").rstrip("=").lower()
    return "p" + encoded


def decode_scope(scope: str) -> str:
    """Inverse of :func:`encode_scope`.

    Used by the ADR-0004 adapter to map a scope back to a prefix. **Decoding is
    not authorization** — a decoded scope must still be resolved against the
    actual form/formset being validated.
    """
    if not scope.startswith("p"):
        raise ValueError(f"Not a valid rg.forms scope: {scope!r}")
    body = scope[1:].upper()
    padding = "=" * (-len(body) % 8)
    return base64.b32decode(body + padding).decode("utf-8")


def signal_path(scope: str | None, name: str) -> str:
    """The nested Datastar signal path for a (scope, logical name).

    Unscoped forms use the logical name directly, exactly as before.
    """
    if scope:
        return f"{RESERVED_NAMESPACE}.{scope}.{name}"
    return name


def make_signal_ref(
    scope: str | None,
    field_names: frozenset[str] | set[str],
) -> Callable[[str], str]:
    """Build a serializer ``signal_ref`` that scopes *declared field* references.

    Declared fields become ``$rgForms.<scope>.<name>``; everything else
    (declared external signals, reserved signals, and — fail-soft — genuinely
    unknown references that the build-time check surfaces separately) is emitted
    unchanged as ``$<name>``. Outside a prefixed form the mapping is the
    identity, so unprefixed output is unchanged.
    """

    def ref(name: str) -> str:
        if scope and name in field_names:
            return f"${RESERVED_NAMESPACE}.{scope}.{name}"
        return f"${name}"

    return ref


def compile_expression(
    expression: str,
    *,
    scope: str | None = None,
    field_names: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Parse an rg.forms expression and compile it to a Datastar/JS string.

    Field references that resolve to declared fields are rewritten to the scoped
    signal path (ADR-0003 §2) as part of serialization — operating on the AST,
    never the raw string, so literals and ``$role_id``-style near-matches are
    never touched. With no scope this is just ADR-0002 compilation.
    """
    ast = parse_expression(expression)
    return serialize_js(ast, make_signal_ref(scope, field_names))


__all__ = [
    "RESERVED_NAMESPACE",
    "encode_scope",
    "decode_scope",
    "signal_path",
    "make_signal_ref",
    "compile_expression",
]
