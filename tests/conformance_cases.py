"""Client/server conformance fixture (ADR-0002 §4, level 1).

Each case is ``(expression, signals, expected)``. The SAME table is evaluated by
the Python ``ExpressionEvaluator`` and by a Node evaluation of the JS the
serializer compiles from the same AST. Both must agree with ``expected``.

Signals hold *canonical* values (string / number / boolean / null / array),
exactly as ``get_signals`` would seed them.
"""

# Sentinel: arithmetic that yields null on both sides.
NULL = None

CASES: list[tuple[str, dict, object]] = [
    # --- strict typed equality (P1: no numeric coercion of strings) ---
    ("$code == '001'", {"code": "001"}, True),
    ("$code == '1'", {"code": "001"}, False),
    ("$code == 1", {"code": "001"}, False),  # string vs number -> not equal
    ("$n == 5", {"n": 5}, True),
    ("$n == 5", {"n": 5.0}, True),  # int/float are both 'number'
    ("$n != 5", {"n": 6}, True),
    ("$b == true", {"b": True}, True),
    ("$b == true", {"b": "true"}, False),  # bool vs string -> not equal
    ("$x == null", {"x": None}, True),
    ("$x == null", {"x": 0}, False),  # number vs null -> not equal
    ("$x == null", {"x": ""}, False),  # string vs null -> not equal
    ("$a == $b", {"a": "", "b": ""}, True),
    ("$a == $b", {"a": "", "b": None}, False),  # string vs null
    # --- ordered comparison: typed; null/invalid/cross-type -> false ---
    ("$q > 10", {"q": 15}, True),
    ("$q > 10", {"q": 5}, False),
    ("$q >= 10", {"q": 10}, True),
    ("$q < 10", {"q": None}, False),  # null operand -> false
    ("$q < 10", {"q": "abc"}, False),  # string vs number -> false
    ("$s < 'm'", {"s": "abc"}, True),  # string vs string ok
    ("$s > 'm'", {"s": "xyz"}, True),
    # --- logical: boolean coercion, boolean-returning ---
    ("$a && $b", {"a": "x", "b": "y"}, True),
    ("$a && $b", {"a": "x", "b": ""}, False),
    ("$a || $b", {"a": "", "b": ""}, False),
    ("$a || $b", {"a": "", "b": "y"}, True),
    ("!$x", {"x": 0}, True),  # 0 is falsy
    ("!$x", {"x": "0"}, False),  # "0" is a truthy string
    ("!$x", {"x": ""}, True),
    ("!$x", {"x": None}, True),
    ("!$x", {"x": "hi"}, False),
    # --- arithmetic: numeric, total, null on invalid / div-by-zero ---
    ("$a + $b", {"a": 10, "b": 5}, 15.0),
    ("$a - $b", {"a": 10, "b": 3}, 7.0),
    ("$a * $b", {"a": 6, "b": 7}, 42.0),
    ("$a / $b", {"a": 100, "b": 4}, 25.0),
    ("$a / $b", {"a": 10, "b": 0}, NULL),  # div by zero -> null
    ("$q * $p", {"q": 5, "p": "19.99"}, 99.95),  # decimal-string preview coercion
    ("$a * 2", {"a": "-"}, NULL),  # in-progress operand -> null
    ("$a + $b", {"a": "", "b": 3}, NULL),  # empty operand -> null
    ("$a + $b", {"a": 3, "b": None}, NULL),  # null operand -> null
    ("($a + $b) * $c", {"a": 1, "b": 2, "c": 3}, 9.0),
    ("-$a", {"a": 5}, -5.0),
    ("-$a", {"a": "-"}, NULL),
    # Non-finite numeric strings must be null on BOTH sides (ADR-0002 §3).
    ("$a + 1", {"a": "NaN"}, NULL),
    ("$a + 1", {"a": "nan"}, NULL),
    ("$a + 1", {"a": "Infinity"}, NULL),
    ("$a + 1", {"a": "-Infinity"}, NULL),
    ("$a * $b", {"a": "1e308", "b": "1e10"}, NULL),  # overflow -> null both sides
    ("$a == 5", {"a": "NaN"}, False),               # equality: string vs number

    # Decimal-string preview coercion still works for finite values.
    ("$p * 2", {"p": "1.5"}, 3.0),
    # A boolean-valued subexpression in arithmetic is null on both sides (this
    # is also rejected at build time, but the runtimes must still agree).
    ("($a == 1) + 1", {"a": 1}, NULL),
    ("(!$a) + 1", {"a": ""}, NULL),
    # --- precedence / composition ---
    ("$a || $b && $c", {"a": False, "b": True, "c": False}, False),
    ("$a || $b && $c", {"a": True, "b": False, "c": False}, True),
    ("$type == 'urgent' && $qty > 5", {"type": "urgent", "qty": 10}, True),
    ("$type == 'urgent' && $qty > 5", {"type": "std", "qty": 10}, False),
    ("$type == 'a' || $type == 'b'", {"type": "b"}, True),
]
