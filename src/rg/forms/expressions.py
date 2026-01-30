"""Expression parser and evaluator for reactive form rules.

Parses and evaluates Datastar-style expressions like:
    $order_type == 'urgent'
    $quantity > 10
    $price * $quantity
    $field == 'a' || $field == 'b'

Safety: Uses a simple tokenizer and recursive descent parser.
No eval() or exec() - only safe operations on form data.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class ExpressionError(Exception):
    """Error parsing or evaluating an expression."""

    pass


# Token types
@dataclass
class Token:
    type: str
    value: Any
    pos: int


class Tokenizer:
    """Tokenize a Datastar expression."""

    PATTERNS = [
        ("WHITESPACE", r"\s+"),
        ("NUMBER", r"\d+\.?\d*"),
        ("STRING", r"'[^']*'|\"[^\"]*\""),
        ("BOOL", r"\b(true|false)\b"),
        ("FIELD", r"\$[a-zA-Z_][a-zA-Z0-9_]*"),
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

    def __init__(self, expression: str):
        self.expression = expression
        self.pos = 0
        self.tokens: list[Token] = []
        self._tokenize()

    def _tokenize(self):
        while self.pos < len(self.expression):
            match = None
            for token_type, pattern in self.PATTERNS:
                regex = re.compile(pattern)
                match = regex.match(self.expression, self.pos)
                if match:
                    value = match.group(0)
                    if token_type != "WHITESPACE":
                        self.tokens.append(Token(token_type, value, self.pos))
                    self.pos = match.end()
                    break
            if not match:
                raise ExpressionError(
                    f"Unexpected character at position {self.pos}: "
                    f"'{self.expression[self.pos]}'"
                )


class ExpressionParser:
    """Parse tokenized expression into an AST."""

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> dict:
        """Parse the expression and return an AST."""
        if not self.tokens:
            raise ExpressionError("Empty expression")
        result = self._parse_or()
        if self.pos < len(self.tokens):
            raise ExpressionError(
                f"Unexpected token: {self.tokens[self.pos].value}"
            )
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
            raise ExpressionError(
                f"Expected {types}, got {token.type}: {token.value}"
            )
        self.pos += 1
        return token

    def _match(self, *types: str) -> bool:
        token = self._current()
        return token is not None and token.type in types

    def _parse_or(self) -> dict:
        """Parse OR expressions (lowest precedence)."""
        left = self._parse_and()
        while self._match("OP_OR"):
            self._consume("OP_OR")
            right = self._parse_and()
            left = {"op": "or", "left": left, "right": right}
        return left

    def _parse_and(self) -> dict:
        """Parse AND expressions."""
        left = self._parse_comparison()
        while self._match("OP_AND"):
            self._consume("OP_AND")
            right = self._parse_comparison()
            left = {"op": "and", "left": left, "right": right}
        return left

    def _parse_comparison(self) -> dict:
        """Parse comparison expressions."""
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

    def _parse_additive(self) -> dict:
        """Parse addition and subtraction."""
        left = self._parse_multiplicative()
        while self._match("OP_PLUS", "OP_MINUS"):
            token = self._consume("OP_PLUS", "OP_MINUS")
            op = "add" if token.type == "OP_PLUS" else "sub"
            right = self._parse_multiplicative()
            left = {"op": op, "left": left, "right": right}
        return left

    def _parse_multiplicative(self) -> dict:
        """Parse multiplication and division."""
        left = self._parse_unary()
        while self._match("OP_MUL", "OP_DIV"):
            token = self._consume("OP_MUL", "OP_DIV")
            op = "mul" if token.type == "OP_MUL" else "div"
            right = self._parse_unary()
            left = {"op": op, "left": left, "right": right}
        return left

    def _parse_unary(self) -> dict:
        """Parse unary operators (!, -)."""
        if self._match("OP_NOT"):
            self._consume("OP_NOT")
            operand = self._parse_unary()
            return {"op": "not", "operand": operand}
        if self._match("OP_MINUS"):
            self._consume("OP_MINUS")
            operand = self._parse_unary()
            return {"op": "neg", "operand": operand}
        return self._parse_primary()

    def _parse_primary(self) -> dict:
        """Parse primary expressions (literals, fields, parentheses)."""
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
            # Remove $ prefix
            field_name = token.value[1:]
            return {"type": "field", "name": field_name}

        if token.type == "NUMBER":
            self._consume("NUMBER")
            value = token.value
            if "." in value:
                return {"type": "literal", "value": Decimal(value)}
            return {"type": "literal", "value": int(value)}

        if token.type == "STRING":
            self._consume("STRING")
            # Remove quotes
            value = token.value[1:-1]
            return {"type": "literal", "value": value}

        if token.type == "BOOL":
            self._consume("BOOL")
            value = token.value == "true"
            return {"type": "literal", "value": value}

        raise ExpressionError(f"Unexpected token: {token.type}: {token.value}")


class ExpressionEvaluator:
    """Evaluate a parsed AST against form data."""

    def __init__(self, data: dict[str, Any]):
        self.data = data

    def evaluate(self, ast: dict) -> Any:
        """Evaluate the AST and return the result."""
        if "type" in ast:
            if ast["type"] == "field":
                return self._get_field_value(ast["name"])
            if ast["type"] == "literal":
                return ast["value"]

        op = ast.get("op")
        if op is None:
            raise ExpressionError(f"Invalid AST node: {ast}")

        # Binary operations
        if op in ("and", "or", "eq", "ne", "lt", "gt", "le", "ge", "add", "sub", "mul", "div"):
            left = self.evaluate(ast["left"])
            right = self.evaluate(ast["right"])
            return self._binary_op(op, left, right)

        # Unary operations
        if op == "not":
            return not self.evaluate(ast["operand"])
        if op == "neg":
            return -self.evaluate(ast["operand"])

        raise ExpressionError(f"Unknown operation: {op}")

    def _get_field_value(self, field_name: str) -> Any:
        """Get field value from data, with type coercion."""
        value = self.data.get(field_name, "")
        # Empty string is treated as None for comparisons
        if value == "":
            return None
        # Try to convert to number if it looks like one
        if isinstance(value, str):
            try:
                if "." in value:
                    return Decimal(value)
                return int(value)
            except (ValueError, TypeError):
                pass
        return value

    def _binary_op(self, op: str, left: Any, right: Any) -> Any:
        """Execute a binary operation."""
        # Handle None comparisons
        if left is None or right is None:
            if op == "eq":
                return left == right
            if op == "ne":
                return left != right
            # Other comparisons with None return False
            return False

        # Convert for arithmetic
        if op in ("add", "sub", "mul", "div"):
            left = self._to_number(left)
            right = self._to_number(right)

        if op == "and":
            return bool(left) and bool(right)
        if op == "or":
            return bool(left) or bool(right)
        if op == "eq":
            return self._compare_equal(left, right)
        if op == "ne":
            return not self._compare_equal(left, right)
        if op == "lt":
            return left < right
        if op == "gt":
            return left > right
        if op == "le":
            return left <= right
        if op == "ge":
            return left >= right
        if op == "add":
            return left + right
        if op == "sub":
            return left - right
        if op == "mul":
            return left * right
        if op == "div":
            if right == 0:
                return Decimal(0)  # Avoid division by zero
            return left / right

        raise ExpressionError(f"Unknown binary operation: {op}")

    def _to_number(self, value: Any) -> Decimal:
        """Convert value to Decimal for arithmetic."""
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except Exception:
                return Decimal(0)
        return Decimal(0)

    def _compare_equal(self, left: Any, right: Any) -> bool:
        """Compare two values for equality with type coercion."""
        # String comparison
        if isinstance(left, str) or isinstance(right, str):
            return str(left) == str(right)
        # Numeric comparison
        return left == right


def parse_expression(expression: str) -> dict:
    """Parse an expression string into an AST.

    Args:
        expression: Datastar-style expression like "$field == 'value'"

    Returns:
        AST dictionary

    Raises:
        ExpressionError: If expression is invalid
    """
    tokenizer = Tokenizer(expression)
    parser = ExpressionParser(tokenizer.tokens)
    return parser.parse()


def evaluate_expression(expression: str, data: dict[str, Any]) -> Any:
    """Parse and evaluate an expression against form data.

    Args:
        expression: Datastar-style expression
        data: Dictionary of field name -> value

    Returns:
        Result of evaluation (bool for conditions, number for computed)

    Raises:
        ExpressionError: If expression is invalid

    Examples:
        >>> evaluate_expression("$order_type == 'urgent'", {"order_type": "urgent"})
        True
        >>> evaluate_expression("$quantity * $price", {"quantity": 10, "price": "5.00"})
        Decimal('50.00')
    """
    ast = parse_expression(expression)
    evaluator = ExpressionEvaluator(data)
    return evaluator.evaluate(ast)
