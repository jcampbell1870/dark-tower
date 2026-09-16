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


@dataclass
class Instruction:
    op: str
    arg: Any | None = None


@dataclass
class BytecodeFunction:
    name: str
    params: list[str]
    instructions: list[Instruction]
    decorators: list[str]
    source: str


@dataclass
class CompiledProgram:
    functions: dict[str, BytecodeFunction]
    tests: list[str]
    manifest: dict[str, Any] | None = None
    sources: list[Path] = field(default_factory=list)
    entry_source: Path | None = None


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


class BytecodeCompiler:
    def __init__(self) -> None:
        self.temp_counter = 0
        self.instructions: list[Instruction] = []

    def compile_program(self, program: Program) -> CompiledProgram:
        functions: dict[str, BytecodeFunction] = {}
        for name, function in program.functions.items():
            functions[name] = self.compile_function(function)
        return CompiledProgram(
            functions=functions,
            tests=list(program.tests),
            manifest=program.manifest,
            sources=list(program.sources),
            entry_source=program.entry_source,
        )

    def compile_function(self, function: FunctionDecl) -> BytecodeFunction:
        self.instructions = []
        for statement in function.body:
            self._compile_statement(statement)
        self._emit("PUSH_CONST", None)
        self._emit("RETURN")
        return BytecodeFunction(
            name=function.name,
            params=list(function.params),
            instructions=list(self.instructions),
            decorators=list(function.decorators),
            source=function.source,
        )

    def _compile_statement(self, statement: Stmt) -> None:
        if isinstance(statement, LetStmt):
            if statement.initializer is None:
                self._emit("PUSH_CONST", None)
            else:
                self._compile_expr(statement.initializer)
            self._emit("DEF_NAME", statement.name)
            return
        if isinstance(statement, AssignStmt):
            if isinstance(statement.target, VariableExpr):
                self._compile_expr(statement.value)
                self._emit("STORE_NAME", statement.target.name)
                return
            if isinstance(statement.target, IndexExpr):
                self._compile_expr(statement.target.collection)
                self._compile_expr(statement.target.index)
                self._compile_expr(statement.value)
                self._emit("INDEX_SET")
                return
            raise DtlError("invalid assignment target")
        if isinstance(statement, ExprStmt):
            self._compile_expr(statement.expr)
            self._emit("POP")
            return
        if isinstance(statement, IfStmt):
            self._compile_expr(statement.condition)
            jump_to_else = self._emit("JUMP_IF_FALSE_POP", None)
            self._emit("PUSH_SCOPE")
            self._compile_block(statement.then_branch)
            self._emit("POP_SCOPE")
            if statement.else_branch is None:
                self._patch(jump_to_else, len(self.instructions))
                return
            jump_to_end = self._emit("JUMP", None)
            self._patch(jump_to_else, len(self.instructions))
            self._emit("PUSH_SCOPE")
            self._compile_block(statement.else_branch)
            self._emit("POP_SCOPE")
            self._patch(jump_to_end, len(self.instructions))
            return
        if isinstance(statement, WhileStmt):
            loop_start = len(self.instructions)
            self._compile_expr(statement.condition)
            jump_to_end = self._emit("JUMP_IF_FALSE_POP", None)
            self._emit("PUSH_SCOPE")
            self._compile_block(statement.body)
            self._emit("POP_SCOPE")
            self._emit("JUMP", loop_start)
            self._patch(jump_to_end, len(self.instructions))
            return
        if isinstance(statement, ForStmt):
            iterable_name = self._temp_name("iter")
            index_name = self._temp_name("index")
            self._compile_expr(statement.iterable)
            self._emit("DEF_NAME", iterable_name)
            self._emit("PUSH_CONST", 0)
            self._emit("DEF_NAME", index_name)
            loop_start = len(self.instructions)
            self._emit("LOAD_NAME", index_name)
            self._emit("LOAD_NAME", iterable_name)
            self._emit("CALL_NAME", {"name": "len", "argc": 1})
            self._emit("BINARY_LT")
            jump_to_end = self._emit("JUMP_IF_FALSE_POP", None)
            self._emit("PUSH_SCOPE")
            self._emit("LOAD_NAME", iterable_name)
            self._emit("LOAD_NAME", index_name)
            self._emit("INDEX_GET")
            self._emit("DEF_NAME", statement.name)
            self._compile_block(statement.body)
            self._emit("POP_SCOPE")
            self._emit("LOAD_NAME", index_name)
            self._emit("PUSH_CONST", 1)
            self._emit("BINARY_ADD")
            self._emit("STORE_NAME", index_name)
            self._emit("JUMP", loop_start)
            self._patch(jump_to_end, len(self.instructions))
            return
        if isinstance(statement, ReturnStmt):
            if statement.value is None:
                self._emit("PUSH_CONST", None)
            else:
                self._compile_expr(statement.value)
            self._emit("RETURN")
            return
        raise DtlError(f"unsupported statement: {statement!r}")

    def _compile_block(self, statements: list[Stmt]) -> None:
        for statement in statements:
            self._compile_statement(statement)

    def _compile_expr(self, expr: Expr) -> None:
        if isinstance(expr, LiteralExpr):
            self._emit("PUSH_CONST", expr.value)
            return
        if isinstance(expr, VariableExpr):
            self._emit("LOAD_NAME", expr.name)
            return
        if isinstance(expr, UnaryExpr):
            self._compile_expr(expr.operand)
            if expr.operator == "!":
                self._emit("UNARY_NOT")
                return
            if expr.operator == "-":
                self._emit("UNARY_NEG")
                return
            raise DtlError(f"unsupported unary operator: {expr.operator}")
        if isinstance(expr, BinaryExpr):
            self._compile_binary(expr)
            return
        if isinstance(expr, CallExpr):
            if not isinstance(expr.callee, VariableExpr):
                raise DtlError("call target must be a function name")
            for arg in expr.args:
                self._compile_expr(arg)
            self._emit("CALL_NAME", {"name": expr.callee.name, "argc": len(expr.args)})
            return
        if isinstance(expr, ListExpr):
            for item in expr.items:
                self._compile_expr(item)
            self._emit("MAKE_LIST", len(expr.items))
            return
        if isinstance(expr, IndexExpr):
            self._compile_expr(expr.collection)
            self._compile_expr(expr.index)
            self._emit("INDEX_GET")
            return
        raise DtlError(f"unsupported expression: {expr!r}")

    def _compile_binary(self, expr: BinaryExpr) -> None:
        if expr.operator == "&&":
            self._compile_expr(expr.left)
            self._emit("DUP")
            jump_to_end = self._emit("JUMP_IF_FALSE_POP", None)
            self._emit("POP")
            self._compile_expr(expr.right)
            self._patch(jump_to_end, len(self.instructions))
            return
        if expr.operator == "||":
            self._compile_expr(expr.left)
            self._emit("DUP")
            jump_to_right = self._emit("JUMP_IF_FALSE_POP", None)
            jump_to_end = self._emit("JUMP", None)
            self._patch(jump_to_right, len(self.instructions))
            self._emit("POP")
            self._compile_expr(expr.right)
            self._patch(jump_to_end, len(self.instructions))
            return
        self._compile_expr(expr.left)
        self._compile_expr(expr.right)
        opcode = {
            "+": "BINARY_ADD",
            "-": "BINARY_SUB",
            "*": "BINARY_MUL",
            "/": "BINARY_DIV",
            "%": "BINARY_MOD",
            "==": "BINARY_EQ",
            "!=": "BINARY_NE",
            "<": "BINARY_LT",
            "<=": "BINARY_LE",
            ">": "BINARY_GT",
            ">=": "BINARY_GE",
        }.get(expr.operator)
        if opcode is None:
            raise DtlError(f"unsupported operator: {expr.operator}")
        self._emit(opcode)

    def _emit(self, op: str, arg: Any | None = None) -> int:
        self.instructions.append(Instruction(op, arg))
        return len(self.instructions) - 1

    def _patch(self, index: int, target: int) -> None:
        self.instructions[index].arg = target

    def _temp_name(self, label: str) -> str:
        self.temp_counter += 1
        return f"__dt_{label}_{self.temp_counter}"


class VirtualMachine:
    def __init__(self, program: CompiledProgram) -> None:
        self.program = program

    def run_main(self) -> int:
        if "main" not in self.program.functions:
            raise DtlError("missing entry function: main")
        self.call_function("main", [])
        return 0

    def run_tests(self) -> int:
        total = len(self.program.tests)
        passed = 0
        for name in self.program.tests:
            try:
                self.call_function(name, [])
                passed += 1
                print(f"ok {name}")
            except DtlError as exc:
                print(f"FAILED {name}: {exc}", file=sys.stderr)
        print(f"{passed}/{total} tests passed")
        return 0 if passed == total else 1

    def call_function(self, name: str, args: list[Any]) -> Any:
        function = self.program.functions.get(name)
        if function is None:
            raise DtlError(f"undefined function: {name}")
        if len(args) != len(function.params):
            raise DtlError(f"function {name} expected {len(function.params)} arguments, got {len(args)}")
        env = Environment()
        for param, arg in zip(function.params, args):
            env.define(param, arg)
        return self._execute_function(function, env)

    def _execute_function(self, function: BytecodeFunction, env: Environment) -> Any:
        stack: list[Any] = []
        ip = 0
        while ip < len(function.instructions):
            instruction = function.instructions[ip]
            ip += 1
            op = instruction.op
            arg = instruction.arg

            if op == "PUSH_CONST":
                stack.append(_deep_clone(arg))
            elif op == "LOAD_NAME":
                stack.append(env.get(str(arg)))
            elif op == "DEF_NAME":
                env.define(str(arg), stack.pop())
            elif op == "STORE_NAME":
                env.assign(str(arg), stack.pop())
            elif op == "POP":
                if not stack:
                    raise DtlError("stack underflow")
                stack.pop()
            elif op == "DUP":
                if not stack:
                    raise DtlError("stack underflow")
                stack.append(stack[-1])
            elif op == "PUSH_SCOPE":
                env = Environment(env)
            elif op == "POP_SCOPE":
                if env.parent is None:
                    raise DtlError("cannot exit root scope")
                env = env.parent
            elif op == "JUMP":
                ip = int(arg)
            elif op == "JUMP_IF_FALSE_POP":
                condition = stack.pop()
                if not self._is_truthy(condition):
                    ip = int(arg)
            elif op == "CALL_NAME":
                call_spec = dict(arg)
                argc = int(call_spec["argc"])
                name = str(call_spec["name"])
                values = [stack.pop() for _ in range(argc)]
                values.reverse()
                stack.append(self._call_value(name, values))
            elif op == "MAKE_LIST":
                count = int(arg)
                if count == 0:
                    stack.append([])
                else:
                    items = stack[-count:]
                    del stack[-count:]
                    stack.append(items)
            elif op == "INDEX_GET":
                index = stack.pop()
                collection = stack.pop()
                stack.append(self._index_get(collection, index))
            elif op == "INDEX_SET":
                value = stack.pop()
                index = stack.pop()
                collection = stack.pop()
                self._index_set(collection, index, value)
            elif op == "UNARY_NOT":
                stack.append(not self._is_truthy(stack.pop()))
            elif op == "UNARY_NEG":
                value = stack.pop()
                self._require_type(value, int, "unary '-' expects an integer")
                stack.append(-value)
            elif op == "BINARY_ADD":
                self._binary_numeric_or_string(stack, "+")
            elif op == "BINARY_SUB":
                self._binary_integer(stack, "-")
            elif op == "BINARY_MUL":
                self._binary_integer(stack, "*")
            elif op == "BINARY_DIV":
                self._binary_integer(stack, "/")
            elif op == "BINARY_MOD":
                self._binary_integer(stack, "%")
            elif op == "BINARY_EQ":
                right = stack.pop()
                left = stack.pop()
                stack.append(left == right)
            elif op == "BINARY_NE":
                right = stack.pop()
                left = stack.pop()
                stack.append(left != right)
            elif op == "BINARY_LT":
                self._binary_compare(stack, "<")
            elif op == "BINARY_LE":
                self._binary_compare(stack, "<=")
            elif op == "BINARY_GT":
                self._binary_compare(stack, ">")
            elif op == "BINARY_GE":
                self._binary_compare(stack, ">=")
            elif op == "RETURN":
                return stack.pop() if stack else None
            else:
                raise DtlError(f"unsupported instruction: {op}")
        return None

    def _call_value(self, name: str, args: list[Any]) -> Any:
        if name in BUILTINS:
            return BUILTINS[name](self, args)
        return self.call_function(name, args)

    def _index_get(self, collection: Any, index: Any) -> Any:
        self._require_type(index, int, "index must be an integer")
        try:
            return collection[index]
        except (IndexError, TypeError) as exc:
            raise DtlError("invalid index access") from exc

    def _index_set(self, collection: Any, index: Any, value: Any) -> None:
        self._require_type(index, int, "index must be an integer")
        if not isinstance(collection, list):
            raise DtlError("indexed assignment requires a list")
        try:
            collection[index] = value
        except IndexError as exc:
            raise DtlError("list index out of range") from exc

    def _binary_numeric_or_string(self, stack: list[Any], operator: str) -> None:
        right = stack.pop()
        left = stack.pop()
        if isinstance(left, str) or isinstance(right, str):
            stack.append(self._to_string(left) + self._to_string(right))
            return
        if isinstance(left, list) and isinstance(right, list):
            stack.append(left + right)
            return
        self._require_type(left, int, f"'{operator}' expects integers or strings")
        self._require_type(right, int, f"'{operator}' expects integers or strings")
        stack.append(left + right)

    def _binary_integer(self, stack: list[Any], operator: str) -> None:
        right = stack.pop()
        left = stack.pop()
        self._require_type(left, int, f"'{operator}' expects integers")
        self._require_type(right, int, f"'{operator}' expects integers")
        if operator == "-":
            stack.append(left - right)
            return
        if operator == "*":
            stack.append(left * right)
            return
        if operator == "/":
            if right == 0:
                raise DtlError("division by zero")
            stack.append(left // right)
            return
        if operator == "%":
            if right == 0:
                raise DtlError("modulo by zero")
            stack.append(left % right)
            return
        raise DtlError(f"unsupported integer operator: {operator}")

    def _binary_compare(self, stack: list[Any], operator: str) -> None:
        right = stack.pop()
        left = stack.pop()
        self._require_comparable(left, right)
        stack.append({
            "<": left < right,
            "<=": left <= right,
            ">": left > right,
            ">=": left >= right,
        }[operator])

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


def builtin_print(vm: VirtualMachine, args: list[Any]) -> None:
    sys.stdout.write("".join(vm._to_string(arg) for arg in args))
    return None


def builtin_println(vm: VirtualMachine, args: list[Any]) -> None:
    sys.stdout.write("".join(vm._to_string(arg) for arg in args) + "\n")
    return None


def builtin_len(_: VirtualMachine, args: list[Any]) -> int:
    _expect_arity("len", args, 1)
    value = args[0]
    if not isinstance(value, (list, str)):
        raise DtlError("len expects a list or string")
    return len(value)


def builtin_assert_eq(_: VirtualMachine, args: list[Any]) -> None:
    _expect_arity("assert_eq", args, 2)
    if args[0] != args[1]:
        raise DtlError(f"assert_eq failed: expected {args[1]!r}, got {args[0]!r}")
    return None


def builtin_push(_: VirtualMachine, args: list[Any]) -> None:
    _expect_arity("push", args, 2)
    target = args[0]
    if not isinstance(target, list):
        raise DtlError("push expects a list as the first argument")
    target.append(args[1])
    return None


def builtin_pop(_: VirtualMachine, args: list[Any]) -> Any:
    _expect_arity("pop", args, 1)
    target = args[0]
    if not isinstance(target, list):
        raise DtlError("pop expects a list")
    if not target:
        raise DtlError("pop from empty list")
    return target.pop()


def builtin_to_string(vm: VirtualMachine, args: list[Any]) -> str:
    _expect_arity("to_string", args, 1)
    return vm._to_string(args[0])


def builtin_join(vm: VirtualMachine, args: list[Any]) -> str:
    _expect_arity("join", args, 2)
    items, separator = args
    if not isinstance(items, list) or not isinstance(separator, str):
        raise DtlError("join expects (list, string)")
    return separator.join(vm._to_string(item) for item in items)


def builtin_hash(vm: VirtualMachine, args: list[Any]) -> int:
    _expect_arity("hash", args, 1)
    return vm._stable_hash(args[0])


def builtin_clone(_: VirtualMachine, args: list[Any]) -> Any:
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


@dataclass
class LoadedArtifacts:
    source: Path
    project_root: Path | None
    program: Program
    bytecode: CompiledProgram


def load_program(path: Path, *, require_entry: bool = True, prefer_project: bool = False) -> LoadResult:
    candidate = path.expanduser()
    if not candidate.exists():
        if candidate.name == "DarkTower.toml":
            return _load_project(candidate.parent, require_entry=require_entry)
        if candidate.suffix == ".dt":
            return _load_file(candidate)
        raise DtlError(f"project path not found: {candidate}")
    if candidate.is_file() and candidate.name == "DarkTower.toml":
        return _load_project(candidate.resolve().parent, require_entry=require_entry)
    if candidate.is_file():
        resolved = candidate.resolve()
        if prefer_project:
            project_root = _find_project_root(resolved.parent, search_parents=True)
            if project_root is not None:
                return _load_project(project_root, require_entry=require_entry)
        return _load_file(resolved)
    if candidate.is_dir():
        search_parents = path == Path(".")
        project_root = _find_project_root(candidate.resolve(), search_parents=search_parents)
        if project_root is None:
            raise DtlError(f"project root not found: {candidate.resolve()}")
        return _load_project(project_root, require_entry=require_entry)
    return _load_file(candidate.resolve())


def load_artifacts(path: Path) -> LoadedArtifacts:
    load_result = load_program(path)
    source = path.expanduser()
    if source.exists():
        source = source.resolve()
    bytecode = BytecodeCompiler().compile_program(load_result.program)
    return LoadedArtifacts(source=source, project_root=load_result.project_root, program=load_result.program, bytecode=bytecode)


def _find_project_root(start: Path, *, search_parents: bool) -> Path | None:
    current = start
    while True:
        if (current / "DarkTower.toml").is_file():
            return current
        if not search_parents or current.parent == current:
            return None
        current = current.parent


def _load_project(project_root: Path, *, require_entry: bool = True) -> LoadResult:
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
        if require_entry and not entry_source.exists():
            raise DtlError(f"entry source not found: {entry_source}")
        if entry_source.exists() and not entry_source.is_file():
            raise DtlError(f"entry source is not a file: {entry_source}")
        source_paths = sorted(src_dir.rglob("*.dt"))
        if not source_paths:
            raise DtlError(f"no .dt files found in {src_dir}")
        entry = entry_source if entry_source.exists() else None
    else:
        entry_source = project_root / "main.dt"
        if not entry_source.exists():
            raise DtlError(f"entry source not found: {entry_source}")
        if not entry_source.is_file():
            raise DtlError(f"entry source is not a file: {entry_source}")
        source_paths = [entry_source]
        entry = entry_source
    program = _parse_sources(source_paths, manifest=manifest, entry_source=entry)
    return LoadResult(program=program, project_root=project_root)


def _load_file(source_path: Path) -> LoadResult:
    if not source_path.exists():
        raise DtlError(f"source file not found: {source_path}")
    if not source_path.is_file():
        raise DtlError(f"source path is not a file: {source_path}")
    program = _parse_sources([source_path], manifest=None, entry_source=source_path)
    return LoadResult(program=program, project_root=source_path.parent)


def _parse_sources(source_paths: list[Path], manifest: dict[str, Any] | None, entry_source: Path | None) -> Program:
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
    loaded = load_artifacts(source_path)
    vm = VirtualMachine(loaded.bytecode)
    return vm.run_main()


def test_command(source_path: Path) -> int:
    loaded = load_artifacts_for_tests(source_path)
    vm = VirtualMachine(loaded.bytecode)
    return vm.run_tests()


def load_artifacts_for_tests(path: Path) -> LoadedArtifacts:
    load_result = load_program(path, require_entry=False, prefer_project=True)
    source = path.expanduser()
    if source.exists():
        source = source.resolve()
    bytecode = BytecodeCompiler().compile_program(load_result.program)
    return LoadedArtifacts(source=source, project_root=load_result.project_root, program=load_result.program, bytecode=bytecode)


def serialize_bytecode(program: CompiledProgram) -> dict[str, Any]:
    return {
        name: {
            "params": function.params,
            "decorators": function.decorators,
            "source": function.source,
            "instructions": [
                {"op": instruction.op, "arg": instruction.arg}
                for instruction in function.instructions
            ],
        }
        for name, function in sorted(program.functions.items())
    }


def build_command(source_path: Path, output_path: Path, target: str) -> int:
    loaded = load_artifacts(source_path)
    program = loaded.program
    bytecode = loaded.bytecode
    if "main" not in bytecode.functions:
        raise DtlError("missing entry function: main")
    package = None
    if program.manifest is not None:
        package = program.manifest.get("package")
    artifact = {
        "format": "dtl-bytecode-v0.4",
        "source": str(loaded.source),
        "target": target,
        "package": package,
        "entry": str(program.entry_source) if program.entry_source else None,
        "sources": [str(path) for path in program.sources],
        "functions": sorted(program.functions),
        "tests": program.tests,
        "bytecode": serialize_bytecode(bytecode),
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
