"""Spreadsheet formula evaluator and AST for linear programming models (SPEC-50).

Supports:
- Standard arithmetic: +, -, *, /, unary -, parentheses
- Cell references in A1 notation (e.g. B2, F10)
- Cell ranges in A1 notation (e.g. B5:E5, A1:B10)
- Functions: SUM(...), SUMPRODUCT(range1, range2, ...)
- Strict rejection of disallowed functions (IF, MAX, etc.), other sheets, named ranges, and Python injections
- Dependency tracking and cycle detection
"""
from __future__ import annotations

import re
from typing import Any, NamedTuple


class FormulaError(Exception):
    """Raised when a formula has syntax errors or disallowed constructs."""
    pass


class CycleError(FormulaError):
    """Raised when a circular dependency is detected between formula cells."""
    pass


class NonlinearError(FormulaError):
    """Raised when a formula cell is nonlinear in decision variables."""
    pass


# ---------------------------------------------------------------------------
# Cell & Range coordinate helpers
# ---------------------------------------------------------------------------

_CELL_RE = re.compile(r"^([A-Za-z]+)([1-9][0-9]*)$")
_RANGE_RE = re.compile(r"^([A-Za-z]+[1-9][0-9]*):([A-Za-z]+[1-9][0-9]*)$")


def col_to_idx(col_str: str) -> int:
    """Convert column name (e.g. 'A', 'Z', 'AA') to 0-indexed integer."""
    col = 0
    for ch in col_str.upper():
        if not ('A' <= ch <= 'Z'):
            raise FormulaError(f"Invalid column letter: {ch}")
        col = col * 26 + (ord(ch) - ord('A') + 1)
    return col - 1


def idx_to_col(idx: int) -> str:
    """Convert 0-indexed column integer to column name (e.g. 0 -> 'A')."""
    if idx < 0:
        raise FormulaError(f"Invalid column index: {idx}")
    res = []
    idx += 1
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        res.append(chr(ord('A') + rem))
    return "".join(reversed(res))


def parse_cell_coord(cell_str: str) -> tuple[int, int]:
    """Parse 'B5' into (row_0_indexed, col_0_indexed), e.g. (4, 1)."""
    m = _CELL_RE.match(cell_str.strip().upper())
    if not m:
        raise FormulaError(f"Invalid cell reference: {cell_str}")
    col_str, row_str = m.groups()
    return int(row_str) - 1, col_to_idx(col_str)


def format_cell_coord(row_idx: int, col_idx: int) -> str:
    """Format (row_idx, col_idx) to cell name like 'B5'."""
    return f"{idx_to_col(col_idx)}{row_idx + 1}"


def is_valid_cell_name(name: str) -> bool:
    return bool(_CELL_RE.match(name.strip().upper()))


def is_valid_range_name(name: str) -> bool:
    return bool(_RANGE_RE.match(name.strip().upper()))


def expand_range_2d(range_str: str) -> list[list[str]]:
    """Expand 'B2:C4' into 2D grid [['B2', 'C2'], ['B3', 'C3'], ['B4', 'C4']]."""
    m = _RANGE_RE.match(range_str.strip().upper())
    if not m:
        raise FormulaError(f"Invalid range reference: {range_str}")
    start, end = m.groups()
    r1, c1 = parse_cell_coord(start)
    r2, c2 = parse_cell_coord(end)
    min_r, max_r = min(r1, r2), max(r1, r2)
    min_c, max_c = min(c1, c2), max(c1, c2)
    return [
        [format_cell_coord(r, c) for c in range(min_c, max_c + 1)]
        for r in range(min_r, max_r + 1)
    ]


def expand_range_flat(range_str: str) -> list[str]:
    """Expand 'B5:E5' into flat list ['B5', 'C5', 'D5', 'E5']."""
    grid = expand_range_2d(range_str)
    return [cell for row in grid for cell in row]


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class Token(NamedTuple):
    type: str  # 'NUMBER', 'CELL', 'RANGE', 'IDENT', 'OP'
    value: Any


_DISALLOWED_PATTERNS = re.compile(
    r"(__|import|eval|exec|open|lambda|globals|locals|system|subprocess|os\b|sys\b)",
    re.IGNORECASE,
)


def tokenize_formula(formula: str) -> tuple[list[Token], list[float]]:
    """Tokenize a formula string.
    
    Returns (tokens, numbers_found).
    Raises FormulaError if disallowed constructs or syntax errors are found.
    """
    text = formula.strip()
    if text.startswith("="):
        text = text[1:].strip()

    if "!" in text:
        raise FormulaError("References to other sheets are not allowed")

    if _DISALLOWED_PATTERNS.search(text):
        raise FormulaError("Disallowed keyword or injection attempt")

    tokens: list[Token] = []
    numbers_found: list[float] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch.isspace():
            i += 1
            continue

        # Operators and punctuation
        if ch in "+-*/(),":
            tokens.append(Token("OP", ch))
            i += 1
            continue

        # Disallowed operators
        if ch in "^&;%[]{}<>=!|":
            raise FormulaError(f"Disallowed operator or character: {ch}")

        # Numbers
        if ch.isdigit() or (ch == "." and i + 1 < n and text[i + 1].isdigit()):
            start = i
            has_dot = (ch == ".")
            i += 1
            while i < n and (text[i].isdigit() or (text[i] == "." and not has_dot)):
                if text[i] == ".":
                    has_dot = True
                i += 1
            # Scientific notation e.g. 1e-4
            if i < n and text[i].lower() == "e":
                exp_start = i
                i += 1
                if i < n and text[i] in "+-":
                    i += 1
                digits_start = i
                while i < n and text[i].isdigit():
                    i += 1
                if i == digits_start:
                    i = exp_start  # rewind if not a valid exponent
            num_str = text[start:i]
            val = float(num_str)
            tokens.append(Token("NUMBER", val))
            numbers_found.append(val)
            continue

        # Identifiers (Functions, Cells, Ranges)
        if ch.isalpha():
            start = i
            while i < n and (text[i].isalnum() or text[i] == ":"):
                i += 1
            word = text[start:i].upper()

            # Check if it contains colon -> RANGE
            if ":" in word:
                if is_valid_range_name(word):
                    tokens.append(Token("RANGE", word))
                    continue
                else:
                    raise FormulaError(f"Invalid range in formula: {word}")

            # Peek ahead to see if it's a function call e.g. NAME(...)
            peek = i
            while peek < n and text[peek].isspace():
                peek += 1
            is_func = (peek < n and text[peek] == "(")

            if is_func:
                if word in ("SUM", "SUMPRODUCT"):
                    tokens.append(Token("IDENT", word))
                    continue
                else:
                    raise FormulaError(f"Function {word} is not allowed")

            # Check if followed by colon ':' as separate token
            if peek < n and text[peek] == ":":
                colon_idx = peek
                next_start = colon_idx + 1
                while next_start < n and text[next_start].isspace():
                    next_start += 1
                next_end = next_start
                while next_end < n and text[next_end].isalnum():
                    next_end += 1
                second_word = text[next_start:next_end].upper()
                full_range = f"{word}:{second_word}"
                if is_valid_range_name(full_range):
                    tokens.append(Token("RANGE", full_range))
                    i = next_end
                    continue
                else:
                    raise FormulaError(f"Invalid range reference: {full_range}")

            # Check if it's a valid cell reference
            if is_valid_cell_name(word):
                tokens.append(Token("CELL", word))
                continue

            raise FormulaError(f"Disallowed identifier or named range: {word}")

        raise FormulaError(f"Unexpected character in formula: {ch}")

    return tokens, numbers_found


# ---------------------------------------------------------------------------
# AST Nodes
# ---------------------------------------------------------------------------

class ASTNode:
    def eval(self, env: dict[str, float]) -> float:
        raise NotImplementedError

    def get_refs(self) -> set[str]:
        raise NotImplementedError


class NumberNode(ASTNode):
    def __init__(self, value: float):
        self.value = float(value)

    def eval(self, env: dict[str, float]) -> float:
        return self.value

    def get_refs(self) -> set[str]:
        return set()

    def __repr__(self):
        return f"Num({self.value})"


class CellNode(ASTNode):
    def __init__(self, name: str):
        self.name = name.upper()

    def eval(self, env: dict[str, float]) -> float:
        return env.get(self.name, 0.0)

    def get_refs(self) -> set[str]:
        return {self.name}

    def __repr__(self):
        return f"Cell({self.name})"


class RangeNode(ASTNode):
    def __init__(self, range_str: str):
        self.range_str = range_str.upper()
        self.cells = expand_range_flat(self.range_str)

    def eval(self, env: dict[str, float]) -> float:
        raise FormulaError("Range cannot be evaluated as scalar expression")

    def get_refs(self) -> set[str]:
        return set(self.cells)

    def __repr__(self):
        return f"Range({self.range_str})"


class UnaryOpNode(ASTNode):
    def __init__(self, op: str, operand: ASTNode):
        self.op = op
        self.operand = operand

    def eval(self, env: dict[str, float]) -> float:
        val = self.operand.eval(env)
        return -val if self.op == "-" else val

    def get_refs(self) -> set[str]:
        return self.operand.get_refs()

    def __repr__(self):
        return f"Unary({self.op}, {self.operand})"


class BinaryOpNode(ASTNode):
    def __init__(self, op: str, left: ASTNode, right: ASTNode):
        self.op = op
        self.left = left
        self.right = right

    def eval(self, env: dict[str, float]) -> float:
        l = self.left.eval(env)
        r = self.right.eval(env)
        if self.op == "+":
            return l + r
        if self.op == "-":
            return l - r
        if self.op == "*":
            return l * r
        if self.op == "/":
            if abs(r) < 1e-12:
                raise FormulaError("Division by zero in formula")
            return l / r
        raise FormulaError(f"Unknown binary operator: {self.op}")

    def get_refs(self) -> set[str]:
        return self.left.get_refs() | self.right.get_refs()

    def __repr__(self):
        return f"BinOp({self.left} {self.op} {self.right})"


class SumNode(ASTNode):
    def __init__(self, args: list[ASTNode]):
        self.args = args

    def eval(self, env: dict[str, float]) -> float:
        total = 0.0
        for arg in self.args:
            if isinstance(arg, RangeNode):
                for c in arg.cells:
                    total += env.get(c, 0.0)
            else:
                total += arg.eval(env)
        return total

    def get_refs(self) -> set[str]:
        refs = set()
        for arg in self.args:
            refs |= arg.get_refs()
        return refs

    def __repr__(self):
        return f"SUM({self.args})"


class SumProductNode(ASTNode):
    def __init__(self, ranges: list[RangeNode]):
        if len(ranges) < 2:
            raise FormulaError("SUMPRODUCT requires at least two ranges")
        n0 = len(ranges[0].cells)
        for r in ranges[1:]:
            if len(r.cells) != n0:
                raise FormulaError(f"SUMPRODUCT ranges have mismatched dimensions: {n0} vs {len(r.cells)}")
        self.ranges = ranges

    def eval(self, env: dict[str, float]) -> float:
        n = len(self.ranges[0].cells)
        total = 0.0
        for i in range(n):
            prod = 1.0
            for rng in self.ranges:
                prod *= env.get(rng.cells[i], 0.0)
            total += prod
        return total

    def get_refs(self) -> set[str]:
        refs = set()
        for rng in self.ranges:
            refs |= rng.get_refs()
        return refs

    def __repr__(self):
        return f"SUMPRODUCT({self.ranges})"


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class FormulaParser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def match(self, token_type: str, value: Any = None) -> bool:
        tok = self.current()
        if tok and tok.type == token_type:
            if value is None or tok.value == value:
                self.pos += 1
                return True
        return False

    def expect(self, token_type: str, value: Any = None) -> Token:
        tok = self.current()
        if not tok or tok.type != token_type or (value is not None and tok.value != value):
            expected = f"{token_type}({value})" if value is not None else token_type
            got = f"{tok.type}({tok.value})" if tok else "EOF"
            raise FormulaError(f"Expected {expected}, got {got}")
        self.pos += 1
        return tok

    def parse(self) -> ASTNode:
        node = self.expr()
        if self.pos < len(self.tokens):
            extra = self.tokens[self.pos]
            raise FormulaError(f"Unexpected token after expression: {extra.type}({extra.value})")
        return node

    def expr(self) -> ASTNode:
        node = self.term()
        while True:
            if self.match("OP", "+"):
                node = BinaryOpNode("+", node, self.term())
            elif self.match("OP", "-"):
                node = BinaryOpNode("-", node, self.term())
            else:
                break
        return node

    def term(self) -> ASTNode:
        node = self.factor()
        while True:
            if self.match("OP", "*"):
                node = BinaryOpNode("*", node, self.factor())
            elif self.match("OP", "/"):
                node = BinaryOpNode("/", node, self.factor())
            else:
                break
        return node

    def factor(self) -> ASTNode:
        if self.match("OP", "+"):
            return UnaryOpNode("+", self.factor())
        if self.match("OP", "-"):
            return UnaryOpNode("-", self.factor())
        return self.primary()

    def primary(self) -> ASTNode:
        tok = self.current()
        if not tok:
            raise FormulaError("Unexpected end of formula")

        if self.match("NUMBER"):
            return NumberNode(tok.value)

        if self.match("CELL"):
            return CellNode(tok.value)

        if self.match("OP", "("):
            node = self.expr()
            self.expect("OP", ")")
            return node

        if self.match("IDENT", "SUM"):
            self.expect("OP", "(")
            args = []
            if not self.match("OP", ")"):
                while True:
                    # Arg can be a RANGE or an expr
                    next_tok = self.current()
                    if next_tok and next_tok.type == "RANGE":
                        self.pos += 1
                        args.append(RangeNode(next_tok.value))
                    else:
                        args.append(self.expr())
                    if self.match("OP", ","):
                        continue
                    elif self.match("OP", ")"):
                        break
                    else:
                        raise FormulaError("Expected ',' or ')' in SUM")
            return SumNode(args)

        if self.match("IDENT", "SUMPRODUCT"):
            self.expect("OP", "(")
            ranges = []
            while True:
                next_tok = self.current()
                if not next_tok or next_tok.type != "RANGE":
                    raise FormulaError(f"SUMPRODUCT argument must be a range, got {next_tok}")
                self.pos += 1
                ranges.append(RangeNode(next_tok.value))
                if self.match("OP", ","):
                    continue
                elif self.match("OP", ")"):
                    break
                else:
                    raise FormulaError("Expected ',' or ')' in SUMPRODUCT")
            return SumProductNode(ranges)

        raise FormulaError(f"Unexpected token in formula: {tok.type}({tok.value})")


def parse_formula(formula_str: str) -> tuple[ASTNode, list[float]]:
    """Parse a formula string into an ASTNode. Returns (ast, numbers_in_formula)."""
    tokens, numbers = tokenize_formula(formula_str)
    parser = FormulaParser(tokens)
    ast = parser.parse()
    return ast, numbers


# ---------------------------------------------------------------------------
# Sheet Evaluator & Graph
# ---------------------------------------------------------------------------

class SheetModel:
    """Manages cells, dependencies, cycle detection and evaluation of a sheet."""

    def __init__(self, cells: dict[str, Any], variables: list[str] | None = None):
        # Normalize cell keys to uppercase
        self.raw_cells: dict[str, Any] = {k.strip().upper(): v for k, v in cells.items()}
        self.variables: list[str] = [v.strip().upper() for v in (variables or [])]

        # Parsed formulas: cell -> ASTNode
        self.formula_ast: dict[str, ASTNode] = {}
        # Dependencies: cell -> set of referenced cells
        self.deps: dict[str, set[str]] = {}
        # Numeric literals found in formulas
        self.formula_numbers: list[float] = []

        self._parse_all_formulas()
        self._check_cycles()

    def _parse_all_formulas(self) -> None:
        for cell, val in self.raw_cells.items():
            if isinstance(val, str) and val.strip().startswith("="):
                ast, nums = parse_formula(val)
                self.formula_ast[cell] = ast
                self.deps[cell] = ast.get_refs()
                self.formula_numbers.extend(nums)

    def _check_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str, path: list[str]):
            if node in visiting:
                cycle_path = path[path.index(node):] + [node]
                raise CycleError(f"Formula cycle detected: {' -> '.join(cycle_path)}")
            if node in visited:
                return
            visiting.add(node)
            path.append(node)
            for neighbor in self.deps.get(node, []):
                dfs(neighbor, path)
            path.pop()
            visiting.remove(node)
            visited.add(node)

        for cell in list(self.deps.keys()):
            if cell not in visited:
                dfs(cell, [])

    def evaluate(self, var_values: dict[str, float] | None = None) -> dict[str, float]:
        """Evaluate all cells in the sheet given values for the decision variables.
        
        Returns dict mapping cell name -> float value.
        """
        env: dict[str, float] = {}
        var_map = {k.strip().upper(): float(v) for k, v in (var_values or {}).items()}

        # Populate decision variables first
        for vname, vval in var_map.items():
            env[vname] = vval

        # Populate static constants
        for cell, val in self.raw_cells.items():
            if cell in env:
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                env[cell] = float(val)
            elif isinstance(val, str) and not val.strip().startswith("="):
                try:
                    env[cell] = float(val.strip())
                except ValueError:
                    env[cell] = 0.0

        # Evaluate formulas memoized
        memo: dict[str, float] = {}

        def eval_cell(c: str) -> float:
            c = c.upper()
            if c in memo:
                return memo[c]
            if c in env:
                return env[c]
            if c in self.formula_ast:
                # Recursively evaluate dependencies
                for dep in self.deps[c]:
                    eval_cell(dep)
                res = self.formula_ast[c].eval(env)
                env[c] = res
                memo[c] = res
                return res
            # Not in cells, defaults to 0.0
            env[c] = 0.0
            memo[c] = 0.0
            return 0.0

        for cell in self.raw_cells:
            eval_cell(cell)

        return env
