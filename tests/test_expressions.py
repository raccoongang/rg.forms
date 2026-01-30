"""Tests for expression parser and evaluator."""

import pytest
from decimal import Decimal

from rg.forms.expressions import (
    ExpressionError,
    evaluate_expression,
    parse_expression,
)


class TestExpressionParser:
    """Tests for expression parsing."""

    def test_parse_field_reference(self):
        """Parse simple field reference."""
        ast = parse_expression("$name")
        assert ast == {"type": "field", "name": "name"}

    def test_parse_string_literal(self):
        """Parse string literal."""
        ast = parse_expression("'hello'")
        assert ast == {"type": "literal", "value": "hello"}

    def test_parse_number_literal(self):
        """Parse number literal."""
        ast = parse_expression("42")
        assert ast == {"type": "literal", "value": 42}

    def test_parse_decimal_literal(self):
        """Parse decimal literal."""
        ast = parse_expression("3.14")
        assert ast == {"type": "literal", "value": Decimal("3.14")}

    def test_parse_boolean_literal(self):
        """Parse boolean literal."""
        assert parse_expression("true") == {"type": "literal", "value": True}
        assert parse_expression("false") == {"type": "literal", "value": False}

    def test_parse_equality(self):
        """Parse equality comparison."""
        ast = parse_expression("$name == 'test'")
        assert ast["op"] == "eq"
        assert ast["left"] == {"type": "field", "name": "name"}
        assert ast["right"] == {"type": "literal", "value": "test"}

    def test_parse_inequality(self):
        """Parse inequality comparison."""
        ast = parse_expression("$name != 'test'")
        assert ast["op"] == "ne"

    def test_parse_numeric_comparisons(self):
        """Parse numeric comparisons."""
        assert parse_expression("$qty > 10")["op"] == "gt"
        assert parse_expression("$qty < 10")["op"] == "lt"
        assert parse_expression("$qty >= 10")["op"] == "ge"
        assert parse_expression("$qty <= 10")["op"] == "le"

    def test_parse_and(self):
        """Parse AND expression."""
        ast = parse_expression("$a == 1 && $b == 2")
        assert ast["op"] == "and"

    def test_parse_or(self):
        """Parse OR expression."""
        ast = parse_expression("$a == 1 || $b == 2")
        assert ast["op"] == "or"

    def test_parse_not(self):
        """Parse NOT expression."""
        ast = parse_expression("!$active")
        assert ast["op"] == "not"
        assert ast["operand"] == {"type": "field", "name": "active"}

    def test_parse_arithmetic(self):
        """Parse arithmetic expressions."""
        ast = parse_expression("$price * $quantity")
        assert ast["op"] == "mul"

        ast = parse_expression("$a + $b - $c")
        assert ast["op"] == "sub"  # Left associative

    def test_parse_parentheses(self):
        """Parse parenthesized expressions."""
        ast = parse_expression("($a + $b) * $c")
        assert ast["op"] == "mul"
        assert ast["left"]["op"] == "add"

    def test_parse_complex_expression(self):
        """Parse complex expression with multiple operators."""
        ast = parse_expression("$type == 'urgent' && $qty > 10 || $priority == 'high'")
        assert ast["op"] == "or"

    def test_parse_error_invalid_char(self):
        """Parse error on invalid character."""
        with pytest.raises(ExpressionError):
            parse_expression("$name @ 'test'")

    def test_parse_error_empty(self):
        """Parse error on empty expression."""
        with pytest.raises(ExpressionError):
            parse_expression("")


class TestExpressionEvaluator:
    """Tests for expression evaluation."""

    def test_eval_field_string(self):
        """Evaluate field reference to string."""
        result = evaluate_expression("$name", {"name": "test"})
        assert result == "test"

    def test_eval_field_number(self):
        """Evaluate field reference to number."""
        result = evaluate_expression("$qty", {"qty": "10"})
        assert result == 10

    def test_eval_equality_true(self):
        """Evaluate equality that is true."""
        result = evaluate_expression("$type == 'urgent'", {"type": "urgent"})
        assert result is True

    def test_eval_equality_false(self):
        """Evaluate equality that is false."""
        result = evaluate_expression("$type == 'urgent'", {"type": "standard"})
        assert result is False

    def test_eval_inequality(self):
        """Evaluate inequality."""
        result = evaluate_expression("$type != 'urgent'", {"type": "standard"})
        assert result is True

    def test_eval_greater_than(self):
        """Evaluate greater than."""
        assert evaluate_expression("$qty > 10", {"qty": "15"}) is True
        assert evaluate_expression("$qty > 10", {"qty": "5"}) is False

    def test_eval_less_than(self):
        """Evaluate less than."""
        assert evaluate_expression("$qty < 10", {"qty": "5"}) is True
        assert evaluate_expression("$qty < 10", {"qty": "15"}) is False

    def test_eval_and_true(self):
        """Evaluate AND that is true."""
        result = evaluate_expression(
            "$type == 'urgent' && $qty > 5",
            {"type": "urgent", "qty": "10"},
        )
        assert result is True

    def test_eval_and_false(self):
        """Evaluate AND that is false."""
        result = evaluate_expression(
            "$type == 'urgent' && $qty > 5",
            {"type": "standard", "qty": "10"},
        )
        assert result is False

    def test_eval_or_true(self):
        """Evaluate OR that is true."""
        result = evaluate_expression(
            "$type == 'urgent' || $priority == 'high'",
            {"type": "standard", "priority": "high"},
        )
        assert result is True

    def test_eval_or_false(self):
        """Evaluate OR that is false."""
        result = evaluate_expression(
            "$type == 'urgent' || $priority == 'high'",
            {"type": "standard", "priority": "low"},
        )
        assert result is False

    def test_eval_not(self):
        """Evaluate NOT."""
        assert evaluate_expression("!$active", {"active": ""}) is True
        assert evaluate_expression("!$active", {"active": "yes"}) is False

    def test_eval_arithmetic_multiply(self):
        """Evaluate multiplication."""
        result = evaluate_expression("$price * $qty", {"price": "10.00", "qty": "3"})
        assert result == Decimal("30.00")

    def test_eval_arithmetic_add(self):
        """Evaluate addition."""
        result = evaluate_expression("$a + $b", {"a": "10", "b": "5"})
        assert result == Decimal("15")

    def test_eval_arithmetic_subtract(self):
        """Evaluate subtraction."""
        result = evaluate_expression("$a - $b", {"a": "10", "b": "3"})
        assert result == Decimal("7")

    def test_eval_arithmetic_divide(self):
        """Evaluate division."""
        result = evaluate_expression("$total / $qty", {"total": "100", "qty": "4"})
        assert result == Decimal("25")

    def test_eval_division_by_zero(self):
        """Division by zero returns 0."""
        result = evaluate_expression("$a / $b", {"a": "10", "b": "0"})
        assert result == Decimal("0")

    def test_eval_empty_field(self):
        """Empty field is treated as None for comparisons."""
        # Empty string becomes None, None == None is True
        assert evaluate_expression("$name == $other", {"name": "", "other": ""}) is True
        # None compared to string literal - not equal
        assert evaluate_expression("$name == 'test'", {"name": ""}) is False

    def test_eval_missing_field(self):
        """Missing field is treated as None."""
        result = evaluate_expression("$missing == 'test'", {})
        assert result is False

    def test_eval_complex_expression(self):
        """Evaluate complex real-world expression."""
        # visible_when="$order_type == 'urgent' || $order_type == 'express'"
        result = evaluate_expression(
            "$order_type == 'urgent' || $order_type == 'express'",
            {"order_type": "express"},
        )
        assert result is True

    def test_eval_computed_total(self):
        """Evaluate computed total expression."""
        # computed="$quantity * $unit_price"
        result = evaluate_expression(
            "$quantity * $unit_price",
            {"quantity": "5", "unit_price": "19.99"},
        )
        assert result == Decimal("5") * Decimal("19.99")
