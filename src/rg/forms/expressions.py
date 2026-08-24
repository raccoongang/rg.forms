"""The rg.forms reactive expression DSL — parsed once, compiled to two targets.

rg.forms expressions are a small domain-specific language. They are parsed to an
AST and then *compiled* to two targets that must agree bit-for-bit on results
(ADR-0002):

    author writes rg.forms DSL
            |  parse
           AST
            |-- ExpressionEvaluator   (server: correctness)
            \\-- serialize_js          (client: a Datastar/JS expression string)

The DSL defines its **own** semantics; it does *not* inherit JavaScript's
surprising rules (loose ``==``, operand-returning ``&&``/``||``, string ``+``,
truthy ``[]``). The normative operator matrix lives in ADR-0002 §3 and is
reproduced by both the Python evaluator here and the JS serializer:

* ``==`` / ``!=`` -> strict *typed* equality (JS ``===`` / ``!==``); mismatched
  canonical types are never equal (and never an error).
* ``<`` ``>`` ``<=`` ``>=`` -> typed compare over number/number or string/string;
  any ``null``/invalid/cross-type operand yields ``false``.
* ``&&`` ``||`` ``!`` -> boolean-only, boolean-returning (never operand-returning).
* ``+`` ``-`` ``*`` ``/`` -> numeric only; a string *literal* operand is rejected
  at build time; an invalid numeric operand or division by zero yields ``null``
  identically on both sides.

Safety: a hand-written tokenizer + recursive-descent parser. No ``eval``/``exec``.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


class ExpressionError(Exception):
    """Error parsing, validating, or evaluating an expression."""

    pass


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #
@dataclass
class Token:
    type: str
    value: Any
    pos: int


class Tokenizer:
    """Tokenize an rg.forms expression."""

    PATTERNS = [
        ("WHITESPACE", r"\s+"),
        ("NUMBER", r"\d+\.?\d*"),
        ("STRING", r"'[^']*'|\"[^\"]*\""),
        ("BOOL", r"\b(true|false)\b"),
        ("NULL", r"\bnull\b"),
        # A field/signal reference. Dotted paths are accepted so an already
        # scoped reference (ADR-0003, ``$rgForms.<scope>.role``) round-trips
        # through the parser; author-written references are simple identifiers.
        ("FIELD", r"\$[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*"),
        ("OP_AND", r"&&"),
        ("OP_OR", r"\|\|"),
        ("OP_EQ", r"=="),
        ("OP_NE", r"!="),
        ("OP_LE", r"<="),
        ("OP_GE", r">="),
        ("OP_LT", r"<"),
        ("OP_GT", r">"),
        ("OP_NOT", r"!"),
        ("OP_PLUS", r"\+"),
        ("OP_MINUS", r"-"),
        ("OP_MUL", r"\*"),
        ("OP_DIV", r"/"),
        ("LPAREN", r"\("),
        ("RPAREN", r"\)"),
    ]

    _COMPILED = [(name, re.compile(pat)) for name, pat in PATTERNS]

    def __init__(self, expression: str):
        self.expression = expression
        self.pos = 0
        self.tokens: list[Token] = []
        self._tokenize()

    def _tokenize(self) -> None:
        while self.pos < len(self.expression):
            match = None
            for token_type, regex in self._COMPILED:
                match = regex.match(self.expression, self.pos)
                if match:
                    value = match.group(0)
                    if token_type != "WHITESPACE":
                        self.tokens.append(Token(token_type, value, self.pos))
                    self.pos = match.end()
                    break
            if not match:
                raise ExpressionError(f"Unexpected character at position {self.pos}: '{self.expression[self.pos]}'")


# --------------------------------------------------------------------------- #
# Parser -> AST
# --------------------------------------------------------------------------- #
class ExpressionParser:
    """Parse a token stream into an AST.

    AST node shapes (kept stable — external code and tests depend on them):

    * field:   ``{"type": "field", "name": str}``
    * literal: ``{"type": "literal", "value": str | int | Decimal | bool | None}``
    * binary:  ``{"op": <name>, "left": node, "right": node}``
    * unary:   ``{"op": "not" | "neg", "operand": node}``
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> dict[str, Any]:
        if not self.tokens:
            raise ExpressionError("Empty expression")
        result = self._parse_or()
        if self.pos < len(self.tokens):
            raise ExpressionError(f"Unexpected token: {self.tokens[self.pos].value}")
        return result

    def _current(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _consume(self, *types: str) -> Token:
        token = self._current()
        if token is None:
            raise ExpressionError("Unexpected end of expression")
        if token.type not in types:
            raise ExpressionError(f"Expected {types}, got {token.type}: {token.value}")
        self.pos += 1
        return token

    def _match(self, *types: str) -> bool:
        token = self._current()
        return token is not None and token.type in types

    def _parse_or(self) -> dict[str, Any]:
        left = self._parse_and()
        while self._match("OP_OR"):
            self._consume("OP_OR")
            right = self._parse_and()
            left = {"op": "or", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict[str, Any]:
        left = self._parse_comparison()
        while self._match("OP_AND"):
            self._consume("OP_AND")
            right = self._parse_comparison()
            left = {"op": "and", "left": left, "right": right}
        return left

    def _parse_comparison(self) -> dict[str, Any]:
        left = self._parse_additive()
        if self._match("OP_EQ", "OP_NE", "OP_LT", "OP_GT", "OP_LE", "OP_GE"):
            token = self._consume("OP_EQ", "OP_NE", "OP_LT", "OP_GT", "OP_LE", "OP_GE")
            op_map = {
                "OP_EQ": "eq",
                "OP_NE": "ne",
                "OP_LT": "lt",
                "OP_GT": "gt",
                "OP_LE": "le",
                "OP_GE": "ge",
            }
            right = self._parse_additive()
            return {"op": op_map[token.type], "left": left, "right": right}
        return left

    def _parse_additive(self) -> dict[str, Any]:
        left = self._parse_multiplicative()
        while self._match("OP_PLUS", "OP_MINUS"):
            token = self._consume("OP_PLUS", "OP_MINUS")
            op = "add" if token.type == "OP_PLUS" else "sub"
            right = self._parse_multiplicative()
            left = {"op": op, "left": left, "right": right}
        return left

    def _parse_multiplicative(self) -> dict[str, Any]:
        left = self._parse_unary()
        while self._match("OP_MUL", "OP_DIV"):
            token = self._consume("OP_MUL", "OP_DIV")
            op = "mul" if token.type == "OP_MUL" else "div"
            right = self._parse_unary()
            left = {"op": op, "left": left, "right": right}
        return left

    def _parse_unary(self) -> dict[str, Any]:
        if self._match("OP_NOT"):
            self._consume("OP_NOT")
            return {"op": "not", "operand": self._parse_unary()}
        if self._match("OP_MINUS"):
            self._consume("OP_MINUS")
            return {"op": "neg", "operand": self._parse_unary()}
        return self._parse_primary()

    def _parse_primary(self) -> dict[str, Any]:
        token = self._current()
        if token is None:
            raise ExpressionError("Unexpected end of expression")

        if token.type == "LPAREN":
            self._consume("LPAREN")
            expr = self._parse_or()
            self._consume("RPAREN")
            return expr

        if token.type == "FIELD":
            self._consume("FIELD")
            return {"type": "field", "name": token.value[1:]}  # drop the leading $

        if token.type == "NUMBER":
            self._consume("NUMBER")
            value = token.value
            if "." in value:
                return {"type": "literal", "value": Decimal(value)}
            return {"type": "literal", "value": int(value)}

        if token.type == "STRING":
            self._consume("STRING")
            return {"type": "literal", "value": token.value[1:-1]}

        if token.type == "BOOL":
            self._consume("BOOL")
            return {"type": "literal", "value": token.value == "true"}

        if token.type == "NULL":
            self._consume("NULL")
            return {"type": "literal", "value": None}

        raise ExpressionError(f"Unexpected token: {token.type}: {token.value}")


# --------------------------------------------------------------------------- #
# AST helpers (used by the scope-rewriter and the system check)
# --------------------------------------------------------------------------- #
_ARITH_OPS = frozenset({"add", "sub", "mul", "div"})
_COMPARE_OPS = frozenset({"lt", "gt", "le", "ge"})
_EQUALITY_OPS = frozenset({"eq", "ne"})
_LOGICAL_OPS = frozenset({"and", "or"})


def iter_nodes(ast: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield every node in the AST (pre-order)."""
    yield ast
    if "operand" in ast:
        yield from iter_nodes(ast["operand"])
    if "left" in ast:
        yield from iter_nodes(ast["left"])
    if "right" in ast:
        yield from iter_nodes(ast["right"])


def collect_field_names(ast: dict[str, Any]) -> set[str]:
    """Return the set of ``$name`` references in the AST (top-level path token)."""
    return {n["name"] for n in iter_nodes(ast) if n.get("type") == "field"}


def map_field_names(ast: dict[str, Any], fn: Callable[[str], str]) -> dict[str, Any]:
    """Return a copy of the AST with every field name mapped through ``fn``.

    Used by ADR-0003 expression rewriting. Operates on the AST — never on the
    raw string — so it cannot rewrite inside string literals or hit
    ``$role_id``-style near-matches.
    """
    if ast.get("type") == "field":
        return {"type": "field", "name": fn(ast["name"])}
    if ast.get("type") == "literal":
        return {"type": "literal", "value": ast["value"]}
    if "operand" in ast:
        return {"op": ast["op"], "operand": map_field_names(ast["operand"], fn)}
    return {
        "op": ast["op"],
        "left": map_field_names(ast["left"], fn),
        "right": map_field_names(ast["right"], fn),
    }


# --------------------------------------------------------------------------- #
# Evaluator (server target) — ADR-0002 §3 semantics
# --------------------------------------------------------------------------- #
def js_type(value: Any) -> str:
    """The canonical JS type name of a Python value (mirrors ``typeof`` mapping).

    ``bool`` is checked before ``int`` because ``bool`` subclasses ``int``.
    ``Decimal`` (a numeric *literal* like ``3.14``) is a number; a ``decimal``
    *field value* is a canonical string, so it is a ``str`` here (ADR-0002 §2).
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float, Decimal)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "array"
    return "object"


def is_truthy(value: Any) -> bool:
    """JS ``Boolean(x)`` for canonical values: falsy = "", null, false, 0."""
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        return value != ""
    if isinstance(value, (int, float, Decimal)):
        return value != 0
    if isinstance(value, (list, tuple)):
        return True  # JS Boolean([]) === true (arrays are not expression operands)
    return bool(value)


def coerce_number(value: Any) -> float | None:
    """Coerce an arithmetic operand to a **finite** float, or ``None``.

    Mirrors the JS guard (`Number.isFinite`): a finite number stays a number; a
    finite decimal-string is coerced (preview); ``bool``, empty string, invalid
    or **non-finite** string (``"NaN"``/``"Infinity"``), and ``null`` yield
    ``None`` (which propagates to a ``null`` arithmetic result). This keeps the
    client and server identical for non-finite inputs (ADR-0002 §3).
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, Decimal):
        return float(value) if value.is_finite() else None
    if isinstance(value, str):
        if value == "":
            return None
        try:
            result = float(value)
        except ValueError:
            return None
        return result if math.isfinite(result) else None
    return None


def coerce_decimal(value: Any) -> Decimal | None:
    """Coerce an arithmetic operand to an exact, **finite** ``Decimal``, or ``None``.

    Used by the *authoritative* (server) evaluation of computed decimal fields
    (ADR-0002 §3), which must not trust the browser's float preview. Non-finite
    values (``NaN``/``Infinity``) yield ``None``, matching ``coerce_number``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return Decimal(str(value))
    if isinstance(value, str):
        if value.strip() == "":
            return None
        try:
            result = Decimal(value)
        except InvalidOperation:
            return None
        return result if result.is_finite() else None
    return None


class ExpressionEvaluator:
    """Evaluate a parsed AST against a dict of canonical reactive values.

    ``decimal_mode`` switches arithmetic to exact ``Decimal`` math for the
    authoritative server recomputation of computed fields (preview stays float).
    """

    def __init__(self, data: dict[str, Any], *, decimal_mode: bool = False):
        self.data = data
        self.decimal_mode = decimal_mode

    def evaluate(self, ast: dict[str, Any]) -> Any:
        node_type = ast.get("type")
        if node_type == "field":
            return self._get_field_value(ast["name"])
        if node_type == "literal":
            return ast["value"]

        op = ast.get("op")
        if op is None:
            raise ExpressionError(f"Invalid AST node: {ast}")

        if op == "not":
            return not is_truthy(self.evaluate(ast["operand"]))
        if op == "neg":
            n = self._coerce(self.evaluate(ast["operand"]))
            return None if n is None else -n

        if op in _LOGICAL_OPS or op in _EQUALITY_OPS or op in _COMPARE_OPS or op in _ARITH_OPS:
            left = self.evaluate(ast["left"])
            right = self.evaluate(ast["right"])
            return self._binary_op(op, left, right)

        raise ExpressionError(f"Unknown operation: {op}")

    def _get_field_value(self, field_name: str) -> Any:
        """Look up a canonical value. Data is pre-normalized (ADR-0002 §1)."""
        return self.data.get(field_name, None)

    def _binary_op(self, op: str, left: Any, right: Any) -> Any:
        if op == "and":
            return is_truthy(left) and is_truthy(right)
        if op == "or":
            return is_truthy(left) or is_truthy(right)
        if op == "eq":
            return self._eq(left, right)
        if op == "ne":
            return not self._eq(left, right)
        if op in _COMPARE_OPS:
            return self._compare(op, left, right)
        if op in _ARITH_OPS:
            return self._arith(op, left, right)
        raise ExpressionError(f"Unknown binary operation: {op}")

    def _coerce(self, value: Any) -> Any:
        """Coerce an arithmetic operand honoring the evaluator's number mode.

        Returns a ``float`` in preview mode and a ``Decimal`` in decimal mode
        (or ``None``); both operands of an arithmetic node always share one mode.
        """
        return coerce_decimal(value) if self.decimal_mode else coerce_number(value)

    @staticmethod
    def _eq(left: Any, right: Any) -> bool:
        """Strict typed equality (JS ``===``). Cross-type is never equal."""
        tl, tr = js_type(left), js_type(right)
        if tl != tr:
            return False
        if tl == "number":
            return float(left) == float(right)
        return bool(left == right)

    @staticmethod
    def _compare(op: str, left: Any, right: Any) -> bool:
        tl, tr = js_type(left), js_type(right)
        if tl == tr == "number":
            a, b = float(left), float(right)
        elif tl == tr == "string":
            a, b = left, right
        else:
            return False
        if op == "lt":
            return a < b
        if op == "gt":
            return a > b
        if op == "le":
            return a <= b
        return a >= b  # ge

    def _arith(self, op: str, left: Any, right: Any) -> Any:
        a, b = self._coerce(left), self._coerce(right)
        if a is None or b is None:
            return None
        if op == "add":
            result = a + b
        elif op == "sub":
            result = a - b
        elif op == "mul":
            result = a * b
        else:  # div
            if b == 0:
                return None
            result = a / b
        return self._finite_or_null(result)

    @staticmethod
    def _finite_or_null(result: Any) -> Any:
        """A non-finite arithmetic result (overflow to inf, NaN) becomes null.

        The JS serializer applies the same ``Number.isFinite`` guard, so an
        overflowing product yields ``null`` identically on both sides.
        """
        if isinstance(result, float) and not math.isfinite(result):
            return None
        if isinstance(result, Decimal) and not result.is_finite():
            return None
        return result


# --------------------------------------------------------------------------- #
# JS serializer (client target) — emits a Datastar/JS expression string
# --------------------------------------------------------------------------- #
def _default_signal_ref(path: str) -> str:
    """Render a field reference as a Datastar signal reference (``$path``)."""
    return f"${path}"


def _js_literal(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return json.dumps(value)  # correct JS string escaping
    if isinstance(value, Decimal):
        return str(value)
    return str(value)  # int / float


_JS_COMPARE = {"lt": "<", "gt": ">", "le": "<=", "ge": ">="}
_JS_ARITH = {"add": "+", "sub": "-", "mul": "*", "div": "/"}


def _js_num_operand(node: dict[str, Any], signal_ref: Callable[[str], str]) -> str:
    """Compile an arithmetic operand to a JS expression yielding ``number|null``.

    Arithmetic sub-expressions and numeric literals already yield a number (or
    ``null``); only leaf references need the string-coercion guard, which keeps
    the emitted expression from blowing up for shallow arithmetic.
    """
    if node.get("op") in _ARITH_OPS or node.get("op") == "neg":
        return _serialize(node, signal_ref)
    if (
        node.get("type") == "literal"
        and isinstance(node["value"], (int, float, Decimal))
        and not isinstance(node["value"], bool)
    ):
        return _js_literal(node["value"])
    x = _serialize(node, signal_ref)
    # Number.isFinite (not !isNaN) so "Infinity"/Infinity are rejected to null,
    # matching the server's math.isfinite guard (ADR-0002 §3).
    return (
        f'(typeof {x} === "number" && Number.isFinite({x}) ? {x} : '
        f'((typeof {x} === "string" && {x} !== "" && Number.isFinite(Number({x}))) ? Number({x}) : null))'
    )


def _serialize(node: dict[str, Any], signal_ref: Callable[[str], str]) -> str:
    node_type = node.get("type")
    if node_type == "field":
        return signal_ref(node["name"])
    if node_type == "literal":
        return _js_literal(node["value"])

    op = node["op"]
    if op == "not":
        return f"(!Boolean({_serialize(node['operand'], signal_ref)}))"
    if op == "neg":
        o = _js_num_operand(node["operand"], signal_ref)
        return f"(({o}) === null ? null : -({o}))"
    if op in _LOGICAL_OPS:
        left = _serialize(node["left"], signal_ref)
        right = _serialize(node["right"], signal_ref)
        js_op = "&&" if op == "and" else "||"
        return f"(Boolean({left}) {js_op} Boolean({right}))"
    if op in _EQUALITY_OPS:
        left = _serialize(node["left"], signal_ref)
        right = _serialize(node["right"], signal_ref)
        js_op = "===" if op == "eq" else "!=="
        return f"({left} {js_op} {right})"
    if op in _COMPARE_OPS:
        left = _serialize(node["left"], signal_ref)
        right = _serialize(node["right"], signal_ref)
        js_op = _JS_COMPARE[op]
        # Typed compare: both number or both string, else false (guards JS's
        # coercing < which would make e.g. null < 1 true).
        return (
            f'((((typeof {left} === "number" && typeof {right} === "number") || '
            f'(typeof {left} === "string" && typeof {right} === "string"))) ? '
            f"({left} {js_op} {right}) : false)"
        )
    if op in _ARITH_OPS:
        a = _js_num_operand(node["left"], signal_ref)
        b = _js_num_operand(node["right"], signal_ref)
        js_op = _JS_ARITH[op]
        expr = f"({a}) {js_op} ({b})"
        # Non-finite result (overflow to Infinity, NaN) -> null, matching the
        # server's _finite_or_null guard.
        finite = f"(Number.isFinite({expr}) ? {expr} : null)"
        if op == "div":
            return f"(({a}) === null || ({b}) === null || ({b}) === 0 ? null : {finite})"
        return f"(({a}) === null || ({b}) === null ? null : {finite})"

    raise ExpressionError(f"Cannot serialize operation: {op}")


def serialize_js(ast: dict[str, Any], signal_ref: Callable[[str], str] = _default_signal_ref) -> str:
    """Compile an AST to a JS/Datastar expression string.

    ``signal_ref`` maps a field name to its signal accessor. The default emits
    Datastar ``$path`` syntax; ADR-0003 passes a scope-aware mapper, and the
    conformance harness passes a plain-object accessor.
    """
    return _serialize(ast, signal_ref)


def serialize_expression(expression: str, signal_ref: Callable[[str], str] = _default_signal_ref) -> str:
    """Parse then compile an expression string to a JS/Datastar expression."""
    return serialize_js(parse_expression(expression), signal_ref)


# --------------------------------------------------------------------------- #
# Build-time validation (ADR-0002 §5)
# --------------------------------------------------------------------------- #
# Field kind -> inferred expression type used for arithmetic type-checking.
# ``decimal`` is the deliberate string-backed numeric exception (coerced for the
# preview; the server recomputes it exactly — ADR-0002 §3).
_KIND_TO_TYPE = {
    "number": "number",
    "decimal": "decimal",
    "boolean": "boolean",
    "multiple_choice": "array",
    # string, choice, date, time, datetime, uuid, file -> "string"
}

# Inferred operand types that are definitely non-numeric (rejected in arithmetic).
_NON_NUMERIC_TYPES = frozenset({"boolean", "string", "array"})


def _infer_type(node: dict[str, Any], field_kinds: dict[str, str]) -> str:
    """Infer the result type of an expression node for arithmetic type-checking.

    Returns ``number``/``decimal``/``boolean``/``string``/``array``/``null`` for
    known cases, or ``unknown`` for a reference the checker cannot type (an
    external/unknown signal). The op alone determines a composite node's result
    type — comparisons/logical/``!`` are boolean, arithmetic/``neg`` are numeric —
    so this is O(1) per node.
    """
    if node.get("type") == "literal":
        value = node["value"]
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if value is None:
            return "null"
        return "number"  # int / float / Decimal literal
    if node.get("type") == "field":
        kind = field_kinds.get(node["name"])
        if kind is None:
            return "unknown"  # external/unknown signal — reported elsewhere
        return _KIND_TO_TYPE.get(kind, "string")
    op = node.get("op")
    if op in _COMPARE_OPS or op in _EQUALITY_OPS or op in _LOGICAL_OPS or op == "not":
        return "boolean"
    if op in _ARITH_OPS or op == "neg":
        return "number"
    return "unknown"


def validate_ast(
    ast: dict[str, Any],
    *,
    field_kinds: dict[str, str],
    external_signals: set[str],
    reserved: frozenset[str] = frozenset({"rgForms"}),
) -> list[str]:
    """Validate an already-parsed AST. Returns a list of human-readable errors.

    ``field_kinds`` maps each declared field name to its normalization kind (see
    ``normalization.field_kind``: ``number``/``decimal``/``string``/``boolean``/
    ``multiple_choice``/``date``/…). A reference resolves if it is a declared
    field, a declared external signal, or (its top-level token) is reserved.
    Rejects: unknown references, direct references to the reserved ``rgForms``
    namespace, references to array-typed fields, and **non-numeric operands to
    arithmetic** — string/boolean literals *and* references to non-numeric
    fields (``+ - * /`` are numeric-only; only ``number``/``decimal`` fields
    qualify).
    """
    errors: list[str] = []

    for node in iter_nodes(ast):
        if node.get("type") == "field":
            name = node["name"]
            top = name.split(".")[0]
            if top in reserved:
                errors.append(
                    f"'${name}' references the reserved '{top}' namespace, which authors may not use directly."
                )
            elif name in field_kinds:
                if field_kinds[name] == "multiple_choice":
                    errors.append(
                        f"'${name}' is an array-typed field and cannot be used in an "
                        "expression in v1 (JS array equality/truthiness are not portable)."
                    )
            elif name in external_signals:
                pass  # intentional page-level signal
            else:
                errors.append(
                    f"'${name}' does not resolve to a declared field, a "
                    "Meta.external_signals entry, or a reserved signal."
                )

        op = node.get("op")
        if op in _ARITH_OPS or op == "neg":
            operands = [node["operand"]] if op == "neg" else [node["left"], node["right"]]
            for operand in operands:
                inferred = _infer_type(operand, field_kinds)
                if inferred not in _NON_NUMERIC_TYPES:
                    continue  # number / decimal / null / unknown are allowed
                # Build the most specific message for the offending operand.
                if operand.get("type") == "literal":
                    value = operand["value"]
                    label = f"String operand '{value}'" if inferred == "string" else "Boolean operand"
                elif operand.get("type") == "field":
                    label = f"'${operand['name']}' is a {field_kinds[operand['name']]} field and"
                else:
                    label = f"A {inferred}-valued subexpression"
                errors.append(
                    f"{label} cannot be used in arithmetic; '+ - * /' are numeric-only "
                    "(only number/decimal operands qualify)."
                )

    return errors


# --------------------------------------------------------------------------- #
# Public convenience API
# --------------------------------------------------------------------------- #
def parse_expression(expression: str) -> dict[str, Any]:
    """Parse an expression string into an AST.

    Raises:
        ExpressionError: if the expression is invalid.
    """
    tokenizer = Tokenizer(expression)
    parser = ExpressionParser(tokenizer.tokens)
    return parser.parse()


def evaluate_expression(expression: str, data: dict[str, Any], *, decimal_mode: bool = False) -> Any:
    """Parse and evaluate an expression against canonical form data.

    ``data`` is expected to hold canonical reactive values (ADR-0002 §2); the
    evaluator does not coerce field values itself. Use
    ``forms.ReactiveForm._get_form_data()`` to obtain normalized data.
    ``decimal_mode`` selects exact ``Decimal`` arithmetic (authoritative
    computed values) instead of the float preview.

    Examples:
        >>> evaluate_expression("$order_type == 'urgent'", {"order_type": "urgent"})
        True
        >>> evaluate_expression("$quantity * $price", {"quantity": 10, "price": "5.00"})
        50.0
    """
    ast = parse_expression(expression)
    return ExpressionEvaluator(data, decimal_mode=decimal_mode).evaluate(ast)


__all__ = [
    "ExpressionError",
    "parse_expression",
    "evaluate_expression",
    "serialize_js",
    "serialize_expression",
    "validate_ast",
    "collect_field_names",
    "map_field_names",
    "iter_nodes",
    "js_type",
    "is_truthy",
    "coerce_number",
    "coerce_decimal",
    "ExpressionEvaluator",
    "ExpressionParser",
    "Tokenizer",
]
