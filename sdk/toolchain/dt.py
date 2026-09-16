#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


class DtlError(Exception):
    pass


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


@dataclass
class Token:
    kind: str
    value: str
    line: int
    column: int


@dataclass
class Program:
    functions: dict[str, "FunctionDecl"]
    tests: list[str]
    manifest: dict[str, Any] | None = None
    sources: list[Path] = field(default_factory=list)
    entry_source: Path | None = None


@dataclass
class FunctionDecl:
    name: str
    params: list[str]
    body: list["Stmt"]
    decorators: list[str]
    source: str


class Stmt:
    pass


@dataclass
class LetStmt(Stmt):
    name: str
    initializer: "Expr" | None


@dataclass
class AssignStmt(Stmt):
    target: "Expr"
    value: "Expr"


@dataclass
class ExprStmt(Stmt):
    expr: "Expr"


@dataclass
class IfStmt(Stmt):
    condition: "Expr"
    then_branch: list[Stmt]
    else_branch: list[Stmt] | None


@dataclass
class WhileStmt(Stmt):
    condition: "Expr"
    body: list[Stmt]


@dataclass
class ForStmt(Stmt):
    name: str
    iterable: "Expr"
    body: list[Stmt]


@dataclass
class ReturnStmt(Stmt):
    value: "Expr" | None


class Expr:
    pass


@dataclass
class LiteralExpr(Expr):
    value: Any


@dataclass
class VariableExpr(Expr):
    name: str


@dataclass
class UnaryExpr(Expr):
    operator: str
    operand: Expr


@dataclass
class BinaryExpr(Expr):
    left: Expr
    operator: str
    right: Expr


@dataclass
class CallExpr(Expr):
    callee: Expr
    args: list[Expr]


@dataclass
class ListExpr(Expr):
    items: list[Expr]


@dataclass
class IndexExpr(Expr):
    collection: Expr
    index: Expr


class Lexer:
    def __init__(self, source: str, source_name: str) -> None:
        self.source = source
        self.source_name = source_name
        self.position = 0
        self.line = 1
        self.column = 1

    def lex(self) -> list[Token]:
        tokens: list[Token] = []
        while not self._is_at_end():
            self._skip_ignored()
            if self._is_at_end():
                break
            ch = self._peek()
            line = self.line
            column = self.column

            if ch.isalpha() or ch == "_":
                tokens.append(self._identifier(line, column))
                continue
            if ch.isdigit():
                tokens.append(self._number(line, column))
                continue
            if ch == '"':
                tokens.append(self._string(line, column))
                continue

            two_char = self.source[self.position : self.position + 2]
            if two_char in {"->", "::", "&&", "||", "==", "!=", "<=", ">="}:
                self._advance()
                self._advance()
                tokens.append(Token("SYMBOL", two_char, line, column))
                continue

            if ch in "(){}[];,=:+-*/%!<>@":
                self._advance()
                tokens.append(Token("SYMBOL", ch, line, column))
                continue

            raise DtlError(f"{self.source_name}:{line}:{column}: unexpected character {ch!r}")

        tokens.append(Token("EOF", "", self.line, self.column))
        return tokens

    def _skip_ignored(self) -> None:
        while not self._is_at_end():
            ch = self._peek()
            if ch in " \r\t\n":
                self._advance()
                continue
            if self.source.startswith("//", self.position):
                while not self._is_at_end() and self._peek() != "\n":
                    self._advance()
                continue
            if self.source.startswith("/*", self.position):
                self._advance()
                self._advance()
                depth = 1
                while depth > 0:
                    if self._is_at_end():
                        raise DtlError(f"{self.source_name}:{self.line}:{self.column}: unterminated block comment")
                    if self.source.startswith("/*", self.position):
                        self._advance()
                        self._advance()
                        depth += 1
                        continue
                    if self.source.startswith("*/", self.position):
                        self._advance()
                        self._advance()
                        depth -= 1
                        continue
                    self._advance()
                continue
            break

    def _identifier(self, line: int, column: int) -> Token:
        start = self.position
        while not self._is_at_end() and (self._peek().isalnum() or self._peek() == "_"):
            self._advance()
        value = self.source[start:self.position]
        kind = "KEYWORD" if value in {"fn", "let", "mut", "return", "if", "else", "while", "for", "in", "true", "false", "mod", "use"} else "IDENT"
        return Token(kind, value, line, column)

    def _number(self, line: int, column: int) -> Token:
        start = self.position
        while not self._is_at_end() and self._peek().isdigit():
            self._advance()
        return Token("NUMBER", self.source[start:self.position], line, column)

    def _string(self, line: int, column: int) -> Token:
        self._advance()
        literal_chars: list[str] = []
        while not self._is_at_end():
            ch = self._peek()
            if ch == '"':
                self._advance()
                raw = "".join(literal_chars)
                try:
                    return Token("STRING", json.loads(f'"{raw}"'), line, column)
                except json.JSONDecodeError as exc:
                    raise DtlError(f"{self.source_name}:{line}:{column}: invalid string literal") from exc
            if ch == "\\":
                literal_chars.append(self._advance())
                if self._is_at_end():
                    break
                literal_chars.append(self._advance())
                continue
            if ch == "\n":
                raise DtlError(f"{self.source_name}:{line}:{column}: unterminated string literal")
            literal_chars.append(self._advance())
        raise DtlError(f"{self.source_name}:{line}:{column}: unterminated string literal")

    def _peek(self) -> str:
        return self.source[self.position]

    def _advance(self) -> str:
        ch = self.source[self.position]
        self.position += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _is_at_end(self) -> bool:
        return self.position >= len(self.source)


class Parser:
    def __init__(self, tokens: list[Token], source_name: str) -> None:
        self.tokens = tokens
        self.source_name = source_name
        self.position = 0

    def parse(self) -> tuple[dict[str, FunctionDecl], list[str]]:
        functions: dict[str, FunctionDecl] = {}
        tests: list[str] = []
        while not self._check("EOF"):
            decorators = self._parse_decorators()
            if self._match_value("use"):
                self._consume_until(";")
                self._expect_value(";")
                continue
            if self._match_value("mod"):
                self._consume_until(";")
                self._expect_value(";")
                continue
            function = self._parse_function(decorators)
            if function.name in functions:
                raise self._error(self._previous(), f"duplicate function {function.name}")
            functions[function.name] = function
            if "test" in decorators:
                tests.append(function.name)
        return functions, tests

    def _parse_decorators(self) -> list[str]:
        decorators: list[str] = []
        while self._match_value("@"):
            decorators.append(self._expect_kind("IDENT").value)
        return decorators

    def _parse_function(self, decorators: list[str]) -> FunctionDecl:
        self._expect_value("fn")
        name = self._expect_kind("IDENT").value
        self._expect_value("(")
        params: list[str] = []
        if not self._check_value(")"):
            while True:
                params.append(self._expect_kind("IDENT").value)
                if self._match_value(":"):
                    self._skip_type_until({",", ")"})
                if not self._match_value(","):
                    break
        self._expect_value(")")
        if self._match_value("->"):
            self._skip_type_until({"{"})
        body = self._parse_block()
        return FunctionDecl(name=name, params=params, body=body, decorators=decorators, source=self.source_name)

    def _parse_block(self) -> list[Stmt]:
        self._expect_value("{")
        statements: list[Stmt] = []
        while not self._check_value("}"):
            if self._check("EOF"):
                raise self._error(self._peek(), "unterminated block")
            statements.append(self._parse_statement())
        self._expect_value("}")
        return statements

    def _parse_statement(self) -> Stmt:
        if self._match_value("let"):
            self._match_value("mut")
            name = self._expect_kind("IDENT").value
            if self._match_value(":"):
                self._skip_type_until({"=", ";"})
            initializer = None
            if self._match_value("="):
                initializer = self._parse_expression()
            self._expect_value(";")
            return LetStmt(name, initializer)

        if self._match_value("return"):
            value = None
            if not self._check_value(";"):
                value = self._parse_expression()
            self._expect_value(";")
            return ReturnStmt(value)

        if self._match_value("if"):
            condition = self._parse_expression()
            then_branch = self._parse_block()
            else_branch = None
            if self._match_value("else"):
                if self._check_value("if"):
                    else_branch = [self._parse_statement()]
                else:
                    else_branch = self._parse_block()
            return IfStmt(condition, then_branch, else_branch)

        if self._match_value("while"):
            condition = self._parse_expression()
            body = self._parse_block()
            return WhileStmt(condition, body)

        if self._match_value("for"):
            name = self._expect_kind("IDENT").value
            self._expect_value("in")
            iterable = self._parse_expression()
            body = self._parse_block()
            return ForStmt(name, iterable, body)

        expr = self._parse_expression()
        if self._match_value("="):
            value = self._parse_expression()
            self._expect_value(";")
            if not isinstance(expr, (VariableExpr, IndexExpr)):
                raise self._error(self._previous(), "invalid assignment target")
            return AssignStmt(expr, value)
        self._expect_value(";")
        return ExprStmt(expr)

    def _parse_expression(self) -> Expr:
        return self._parse_or()

    def _parse_or(self) -> Expr:
        expr = self._parse_and()
        while self._match_value("||"):
            expr = BinaryExpr(expr, "||", self._parse_and())
        return expr

    def _parse_and(self) -> Expr:
        expr = self._parse_equality()
        while self._match_value("&&"):
            expr = BinaryExpr(expr, "&&", self._parse_equality())
        return expr

    def _parse_equality(self) -> Expr:
        expr = self._parse_comparison()
        while True:
            if self._match_value("=="):
                expr = BinaryExpr(expr, "==", self._parse_comparison())
            elif self._match_value("!="):
                expr = BinaryExpr(expr, "!=", self._parse_comparison())
            else:
                return expr

    def _parse_comparison(self) -> Expr:
        expr = self._parse_term()
        while True:
            if self._match_value("<"):
                expr = BinaryExpr(expr, "<", self._parse_term())
            elif self._match_value("<="):
                expr = BinaryExpr(expr, "<=", self._parse_term())
            elif self._match_value(">"):
                expr = BinaryExpr(expr, ">", self._parse_term())
            elif self._match_value(">="):
                expr = BinaryExpr(expr, ">=", self._parse_term())
            else:
                return expr

    def _parse_term(self) -> Expr:
        expr = self._parse_factor()
        while True:
            if self._match_value("+"):
                expr = BinaryExpr(expr, "+", self._parse_factor())
            elif self._match_value("-"):
                expr = BinaryExpr(expr, "-", self._parse_factor())
            else:
                return expr

    def _parse_factor(self) -> Expr:
        expr = self._parse_unary()
        while True:
            if self._match_value("*"):
                expr = BinaryExpr(expr, "*", self._parse_unary())
            elif self._match_value("/"):
                expr = BinaryExpr(expr, "/", self._parse_unary())
            elif self._match_value("%"):
                expr = BinaryExpr(expr, "%", self._parse_unary())
            else:
                return expr

    def _parse_unary(self) -> Expr:
        if self._match_value("!"):
            return UnaryExpr("!", self._parse_unary())
        if self._match_value("-"):
            return UnaryExpr("-", self._parse_unary())
        return self._parse_postfix()

    def _parse_postfix(self) -> Expr:
        expr = self._parse_primary()
        while True:
            if self._match_value("("):
                args: list[Expr] = []
                if not self._check_value(")"):
                    while True:
                        args.append(self._parse_expression())
                        if not self._match_value(","):
                            break
                self._expect_value(")")
                expr = CallExpr(expr, args)
                continue
            if self._match_value("["):
                index = self._parse_expression()
                self._expect_value("]")
                expr = IndexExpr(expr, index)
                continue
            return expr

    def _parse_primary(self) -> Expr:
        token = self._peek()
        if self._match_kind("NUMBER"):
            return LiteralExpr(int(token.value))
        if self._match_kind("STRING"):
            return LiteralExpr(token.value)
        if self._match_value("true"):
            return LiteralExpr(True)
        if self._match_value("false"):
            return LiteralExpr(False)
        if self._match_kind("IDENT"):
            name = token.value
            while self._match_value("::"):
                name += "::" + self._expect_kind("IDENT").value
            return VariableExpr(name)
        if self._match_value("("):
            expr = self._parse_expression()
            self._expect_value(")")
            return expr
        if self._match_value("["):
            items: list[Expr] = []
            if not self._check_value("]"):
                while True:
                    items.append(self._parse_expression())
                    if not self._match_value(","):
                        break
            self._expect_value("]")
            return ListExpr(items)
        raise self._error(token, f"unexpected token {token.value!r}")

    def _skip_type_until(self, stop_values: set[str]) -> None:
        angle = square = paren = 0
        while not self._check("EOF"):
            token = self._peek()
            if token.value == "<":
                angle += 1
            elif token.value == ">" and angle > 0:
                angle -= 1
            elif token.value == "[":
                square += 1
            elif token.value == "]" and square > 0:
                square -= 1
            elif token.value == "(":
                paren += 1
            elif token.value == ")" and paren > 0:
                paren -= 1
            elif angle == square == paren == 0 and token.value in stop_values:
                return
            self.position += 1
        raise self._error(self._peek(), "unterminated type annotation")

    def _consume_until(self, value: str) -> None:
        while not self._check("EOF") and not self._check_value(value):
            self.position += 1

    def _match_kind(self, kind: str) -> bool:
        if self._check(kind):
            self.position += 1
            return True
        return False

    def _match_value(self, value: str) -> bool:
        if self._check_value(value):
            self.position += 1
            return True
        return False

    def _expect_kind(self, kind: str) -> Token:
        if self._check(kind):
            self.position += 1
            return self.tokens[self.position - 1]
        raise self._error(self._peek(), f"expected {kind}")

    def _expect_value(self, value: str) -> Token:
        if self._check_value(value):
            self.position += 1
            return self.tokens[self.position - 1]
        raise self._error(self._peek(), f"expected {value!r}")

    def _check(self, kind: str) -> bool:
        return self._peek().kind == kind

    def _check_value(self, value: str) -> bool:
        return self._peek().value == value

    def _peek(self) -> Token:
        return self.tokens[self.position]

    def _previous(self) -> Token:
        return self.tokens[self.position - 1]

    def _error(self, token: Token, message: str) -> DtlError:
        return DtlError(f"{self.source_name}:{token.line}:{token.column}: {message}")


class Environment:
    def __init__(self, parent: "Environment" | None = None) -> None:
        self.parent = parent
        self.values: dict[str, Any] = {}

    def define(self, name: str, value: Any) -> None:
        self.values[name] = value

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise DtlError(f"undefined variable: {name}")

    def assign(self, name: str, value: Any) -> None:
        if name in self.values:
            self.values[name] = value
            return
        if self.parent is not None:
            self.parent.assign(name, value)
            return
        raise DtlError(f"undefined variable: {name}")


class Interpreter:
    def __init__(self, program: Program) -> None:
        self.program = program

    def run_main(self) -> int:
        if "main" not in self.program.functions:
            raise DtlError("missing entry function: main")
        self._call_function("main", [])
        return 0

    def run_tests(self) -> int:
        total = len(self.program.tests)
        passed = 0
        for name in self.program.tests:
            try:
                self._call_function(name, [])
                passed += 1
                print(f"ok {name}")
            except DtlError as exc:
                print(f"FAILED {name}: {exc}", file=sys.stderr)
        print(f"{passed}/{total} tests passed")
        return 0 if passed == total else 1

    def _call_function(self, name: str, args: list[Any]) -> Any:
        function = self.program.functions.get(name)
        if function is None:
            raise DtlError(f"undefined function: {name}")
        if len(args) != len(function.params):
            raise DtlError(f"function {name} expected {len(function.params)} arguments, got {len(args)}")
        env = Environment()
        for param, arg in zip(function.params, args):
            env.define(param, arg)
        try:
            self._execute_block(function.body, env)
        except ReturnSignal as signal:
            return signal.value
        return None

    def _execute_block(self, statements: list[Stmt], env: Environment) -> None:
        for statement in statements:
            self._execute_statement(statement, env)

    def _execute_statement(self, statement: Stmt, env: Environment) -> None:
        if isinstance(statement, LetStmt):
            value = self._evaluate(statement.initializer, env) if statement.initializer is not None else None
            env.define(statement.name, value)
            return
        if isinstance(statement, AssignStmt):
            value = self._evaluate(statement.value, env)
            self._assign(statement.target, value, env)
            return
        if isinstance(statement, ExprStmt):
            self._evaluate(statement.expr, env)
            return
        if isinstance(statement, IfStmt):
            if self._is_truthy(self._evaluate(statement.condition, env)):
                self._execute_block(statement.then_branch, Environment(env))
            elif statement.else_branch is not None:
                self._execute_block(statement.else_branch, Environment(env))
            return
        if isinstance(statement, WhileStmt):
            loop_env = Environment(env)
            while self._is_truthy(self._evaluate(statement.condition, loop_env)):
                self._execute_block(statement.body, Environment(loop_env))
            return
        if isinstance(statement, ForStmt):
            iterable = self._evaluate(statement.iterable, env)
            if not isinstance(iterable, (list, str)):
                raise DtlError("for-loop expects a list or string")
            for item in iterable:
                loop_env = Environment(env)
                loop_env.define(statement.name, item)
                self._execute_block(statement.body, loop_env)
            return
        if isinstance(statement, ReturnStmt):
            raise ReturnSignal(self._evaluate(statement.value, env) if statement.value is not None else None)
        raise DtlError(f"unsupported statement: {statement!r}")

    def _assign(self, target: Expr, value: Any, env: Environment) -> None:
        if isinstance(target, VariableExpr):
            env.assign(target.name, value)
            return
        if isinstance(target, IndexExpr):
            collection = self._evaluate(target.collection, env)
            index = self._evaluate(target.index, env)
            if not isinstance(index, int):
                raise DtlError("index must be an integer")
            if not isinstance(collection, list):
                raise DtlError("indexed assignment requires a list")
            try:
                collection[index] = value
            except IndexError as exc:
                raise DtlError("list index out of range") from exc
            return
        raise DtlError("invalid assignment target")

    def _evaluate(self, expr: Expr | None, env: Environment) -> Any:
        if expr is None:
            return None
        if isinstance(expr, LiteralExpr):
            return expr.value
        if isinstance(expr, VariableExpr):
            return env.get(expr.name)
        if isinstance(expr, UnaryExpr):
            value = self._evaluate(expr.operand, env)
            if expr.operator == "!":
                return not self._is_truthy(value)
            if expr.operator == "-":
                self._require_type(value, int, "unary '-' expects an integer")
                return -value
            raise DtlError(f"unsupported unary operator: {expr.operator}")
        if isinstance(expr, BinaryExpr):
            return self._evaluate_binary(expr, env)
        if isinstance(expr, CallExpr):
            return self._evaluate_call(expr, env)
        if isinstance(expr, ListExpr):
            return [self._evaluate(item, env) for item in expr.items]
        if isinstance(expr, IndexExpr):
            collection = self._evaluate(expr.collection, env)
            index = self._evaluate(expr.index, env)
            self._require_type(index, int, "index must be an integer")
            try:
                return collection[index]
            except (IndexError, TypeError) as exc:
                raise DtlError("invalid index access") from exc
        raise DtlError(f"unsupported expression: {expr!r}")

    def _evaluate_binary(self, expr: BinaryExpr, env: Environment) -> Any:
        if expr.operator == "&&":
            left = self._evaluate(expr.left, env)
            return self._evaluate(expr.right, env) if self._is_truthy(left) else left
        if expr.operator == "||":
            left = self._evaluate(expr.left, env)
            return left if self._is_truthy(left) else self._evaluate(expr.right, env)

        left = self._evaluate(expr.left, env)
        right = self._evaluate(expr.right, env)
        operator = expr.operator

        if operator == "+":
            if isinstance(left, str) or isinstance(right, str):
                return self._to_string(left) + self._to_string(right)
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            self._require_type(left, int, "'+' expects integers or strings")
            self._require_type(right, int, "'+' expects integers or strings")
            return left + right
        if operator == "-":
            self._require_type(left, int, "'-' expects integers")
            self._require_type(right, int, "'-' expects integers")
            return left - right
        if operator == "*":
            self._require_type(left, int, "'*' expects integers")
            self._require_type(right, int, "'*' expects integers")
            return left * right
        if operator == "/":
            self._require_type(left, int, "'/' expects integers")
            self._require_type(right, int, "'/' expects integers")
            if right == 0:
                raise DtlError("division by zero")
            return left // right
        if operator == "%":
            self._require_type(left, int, "'%' expects integers")
            self._require_type(right, int, "'%' expects integers")
            if right == 0:
                raise DtlError("modulo by zero")
            return left % right
        if operator in {"<", "<=", ">", ">="}:
            self._require_comparable(left, right)
            return {
                "<": left < right,
                "<=": left <= right,
                ">": left > right,
                ">=": left >= right,
            }[operator]
        if operator == "==":
            return left == right
        if operator == "!=":
            return left != right
        raise DtlError(f"unsupported operator: {operator}")

    def _evaluate_call(self, expr: CallExpr, env: Environment) -> Any:
        if not isinstance(expr.callee, VariableExpr):
            raise DtlError("call target must be a function name")
        name = expr.callee.name
        args = [self._evaluate(arg, env) for arg in expr.args]
        if name in BUILTINS:
            return BUILTINS[name](self, args)
        return self._call_function(name, args)

    def _is_truthy(self, value: Any) -> bool:
        return bool(value)

    def _to_string(self, value: Any) -> str:
        if value is None:
            return "()"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, list):
            return "[" + ", ".join(self._to_string(item) for item in value) + "]"
        return str(value)

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._normalize(item) for item in value]
        if value is True:
            return True
        if value is False:
            return False
        if value is None:
            return None
        return value

    def _stable_hash(self, value: Any) -> int:
        payload = json.dumps(self._normalize(value), ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)

    def _require_type(self, value: Any, expected: type, message: str) -> None:
        if isinstance(value, bool) and expected is int:
            raise DtlError(message)
        if not isinstance(value, expected):
            raise DtlError(message)

    def _require_comparable(self, left: Any, right: Any) -> None:
        if type(left) is not type(right):
            raise DtlError("comparison expects values of the same type")
        if not isinstance(left, (int, str)):
            raise DtlError("comparison supports integers and strings only")


def builtin_print(interpreter: Interpreter, args: list[Any]) -> None:
    sys.stdout.write("".join(interpreter._to_string(arg) for arg in args))
    return None


def builtin_println(interpreter: Interpreter, args: list[Any]) -> None:
    sys.stdout.write("".join(interpreter._to_string(arg) for arg in args) + "\n")
    return None


def builtin_len(_: Interpreter, args: list[Any]) -> int:
    _expect_arity("len", args, 1)
    value = args[0]
    if not isinstance(value, (list, str)):
        raise DtlError("len expects a list or string")
    return len(value)


def builtin_assert_eq(_: Interpreter, args: list[Any]) -> None:
    _expect_arity("assert_eq", args, 2)
    if args[0] != args[1]:
        raise DtlError(f"assert_eq failed: expected {args[1]!r}, got {args[0]!r}")
    return None


def builtin_push(_: Interpreter, args: list[Any]) -> None:
    _expect_arity("push", args, 2)
    target = args[0]
    if not isinstance(target, list):
        raise DtlError("push expects a list as the first argument")
    target.append(args[1])
    return None


def builtin_pop(_: Interpreter, args: list[Any]) -> Any:
    _expect_arity("pop", args, 1)
    target = args[0]
    if not isinstance(target, list):
        raise DtlError("pop expects a list")
    if not target:
        raise DtlError("pop from empty list")
    return target.pop()


def builtin_to_string(interpreter: Interpreter, args: list[Any]) -> str:
    _expect_arity("to_string", args, 1)
    return interpreter._to_string(args[0])


def builtin_join(interpreter: Interpreter, args: list[Any]) -> str:
    _expect_arity("join", args, 2)
    items, separator = args
    if not isinstance(items, list) or not isinstance(separator, str):
        raise DtlError("join expects (list, string)")
    return separator.join(interpreter._to_string(item) for item in items)


def builtin_hash(interpreter: Interpreter, args: list[Any]) -> int:
    _expect_arity("hash", args, 1)
    return interpreter._stable_hash(args[0])


def builtin_clone(_: Interpreter, args: list[Any]) -> Any:
    _expect_arity("clone", args, 1)
    return _deep_clone(args[0])


def _deep_clone(value: Any) -> Any:
    if isinstance(value, list):
        return [_deep_clone(item) for item in value]
    return value


def _expect_arity(name: str, args: list[Any], expected: int) -> None:
    if len(args) != expected:
        raise DtlError(f"builtin {name} expected {expected} arguments, got {len(args)}")


BUILTINS = {
    "print": builtin_print,
    "println": builtin_println,
    "len": builtin_len,
    "assert_eq": builtin_assert_eq,
    "push": builtin_push,
    "pop": builtin_pop,
    "to_string": builtin_to_string,
    "join": builtin_join,
    "hash": builtin_hash,
    "clone": builtin_clone,
}


def read_text(path: Path) -> str:
    if not path.exists():
        raise DtlError(f"path not found: {path}")
    if not path.is_file():
        raise DtlError(f"path is not a file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DtlError(f"source file is not valid UTF-8: {path}") from exc
    except OSError as exc:
        raise DtlError(f"unable to read source file: {path}") from exc


@dataclass
class LoadResult:
    program: Program
    project_root: Path | None


def load_program(path: Path) -> LoadResult:
    candidate = path.expanduser()
    if candidate.is_file() and candidate.name == "DarkTower.toml":
        return _load_project(candidate.resolve().parent)
    if candidate.is_dir():
        return _load_project(_find_project_root(candidate.resolve()))
    return _load_file(candidate.resolve())


def _find_project_root(start: Path) -> Path:
    current = start
    while True:
        if (current / "DarkTower.toml").is_file():
            return current
        if current.parent == current:
            return start
        current = current.parent


def _load_project(project_root: Path) -> LoadResult:
    manifest_path = project_root / "DarkTower.toml"
    if not manifest_path.exists():
        raise DtlError(f"DarkTower.toml not found in {project_root}")
    if tomllib is None:
        raise DtlError("tomllib is unavailable in this Python runtime")
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DtlError(f"manifest is not valid UTF-8: {manifest_path}") from exc
    except OSError as exc:
        raise DtlError(f"unable to read manifest: {manifest_path}") from exc
    try:
        manifest = tomllib.loads(manifest_text)
    except tomllib.TOMLDecodeError as exc:
        raise DtlError(f"invalid manifest: {manifest_path}: {exc}") from exc

    src_dir = project_root / "src"
    if src_dir.exists():
        if not src_dir.is_dir():
            raise DtlError(f"source directory is not a directory: {src_dir}")
        entry_source = src_dir / "main.dt"
        if not entry_source.exists():
            raise DtlError(f"entry source not found: {entry_source}")
        source_paths = sorted(src_dir.rglob("*.dt"))
        if not source_paths:
            raise DtlError(f"no .dt files found in {src_dir}")
    else:
        entry_source = project_root / "main.dt"
        if not entry_source.exists():
            raise DtlError(f"entry source not found: {entry_source}")
        source_paths = [entry_source]
    program = _parse_sources(source_paths, manifest=manifest, entry_source=entry_source)
    return LoadResult(program=program, project_root=project_root)



def _load_file(source_path: Path) -> LoadResult:
    if not source_path.exists():
        raise DtlError(f"source file not found: {source_path}")
    if not source_path.is_file():
        raise DtlError(f"source path is not a file: {source_path}")
    program = _parse_sources([source_path], manifest=None, entry_source=source_path)
    return LoadResult(program=program, project_root=source_path.parent)



def _parse_sources(source_paths: list[Path], manifest: dict[str, Any] | None, entry_source: Path) -> Program:
    functions: dict[str, FunctionDecl] = {}
    tests: list[str] = []
    for source_path in source_paths:
        source = read_text(source_path)
        tokens = Lexer(source, str(source_path)).lex()
        file_functions, file_tests = Parser(tokens, str(source_path)).parse()
        duplicates = set(functions) & set(file_functions)
        if duplicates:
            duplicate = sorted(duplicates)[0]
            raise DtlError(f"duplicate function across project sources: {duplicate}")
        functions.update(file_functions)
        tests.extend(file_tests)
    return Program(functions=functions, tests=tests, manifest=manifest, sources=source_paths, entry_source=entry_source)



def run_command(source_path: Path) -> int:
    load_result = load_program(source_path)
    interpreter = Interpreter(load_result.program)
    return interpreter.run_main()



def test_command(source_path: Path) -> int:
    load_result = load_program(source_path)
    interpreter = Interpreter(load_result.program)
    return interpreter.run_tests()



def build_command(source_path: Path, output_path: Path, target: str) -> int:
    load_result = load_program(source_path)
    program = load_result.program
    package = None
    if program.manifest is not None:
        package = program.manifest.get("package")
    artifact = {
        "format": "dtl-prototype-v0.3",
        "target": target,
        "package": package,
        "entry": str(program.entry_source) if program.entry_source else None,
        "sources": [str(path) for path in program.sources],
        "functions": sorted(program.functions),
        "tests": program.tests,
    }
    if output_path.exists() and not output_path.is_file():
        raise DtlError(f"output path is not a regular file: {output_path}")
    output_parent = output_path.parent
    try:
        if output_parent != Path("."):
            output_parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise DtlError(f"unable to write output file: {output_path}") from exc
    return 0



def init_command(project_name: str) -> int:
    project_root = Path(project_name).resolve()
    if project_root.exists():
        raise DtlError(f"target path already exists: {project_root}")
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    manifest = f'''[package]\nname = "{project_root.name}"\nversion = "0.1.0"\nedition = "2026"\n'''
    main_source = 'fn main() {\n  println("Hello, Dark Tower!");\n}\n'
    (project_root / "DarkTower.toml").write_text(manifest, encoding="utf-8")
    (src_dir / "main.dt").write_text(main_source, encoding="utf-8")
    print(f"initialized {project_root}")
    return 0



def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dt",
        description="Dark Tower Language (DTL) prototype CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a DTL source file or project")
    run_parser.add_argument("source", nargs="?", default=".", help="Path to a .dt source file or project directory")

    build_parser = subparsers.add_parser("build", help="Build a DTL source file or project")
    build_parser.add_argument("source", nargs="?", default=".", help="Path to a .dt source file or project directory")
    build_parser.add_argument("-o", "--output", required=True, help="Output artifact path")
    build_parser.add_argument("--target", default="linux-x64", help="Target triple for the build artifact")

    test_parser = subparsers.add_parser("test", help="Run @test functions in a DTL source file or project")
    test_parser.add_argument("source", nargs="?", default=".", help="Path to a .dt source file or project directory")

    init_parser = subparsers.add_parser("init", help="Create a new DTL project scaffold")
    init_parser.add_argument("name", help="Directory name for the new project")

    return parser



def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "run":
            return run_command(Path(args.source))
        if args.command == "build":
            return build_command(Path(args.source), Path(args.output), args.target)
        if args.command == "test":
            return test_command(Path(args.source))
        if args.command == "init":
            return init_command(args.name)
    except DtlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
