from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import Diagnostic, DiagnosticError


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int
    snippet: str


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class BoolLiteral:
    value: bool


@dataclass(frozen=True)
class IntLiteral:
    value: int


@dataclass(frozen=True)
class Variable:
    name: str


@dataclass(frozen=True)
class Call:
    callee: str
    args: list["Expr"]


Expr = StringLiteral | BoolLiteral | IntLiteral | Variable | Call


@dataclass(frozen=True)
class LetStmt:
    name: str
    expr: Expr


@dataclass(frozen=True)
class ReturnStmt:
    expr: Expr


@dataclass(frozen=True)
class IfStmt:
    condition: Expr
    then_body: list["Stmt"]
    else_body: list["Stmt"]


@dataclass(frozen=True)
class ExprStmt:
    expr: Expr


Stmt = LetStmt | ReturnStmt | IfStmt | ExprStmt


@dataclass(frozen=True)
class FunctionDef:
    name: str
    params: list[str]
    body: list[Stmt]


@dataclass(frozen=True)
class SubsetProgram:
    functions: list[FunctionDef]


@dataclass(frozen=True)
class ReturnSignal:
    value: object


def parse_subset_program(source: str) -> SubsetProgram:
    parser = Parser(source)
    program = parser.parse_program()
    parser.expect("EOF")
    return program


def run_subset_program(source: str, *, entry: str, args: list[object]) -> object:
    program = parse_subset_program(source)
    functions = {fn.name: fn for fn in program.functions}
    if entry not in functions:
        raise DiagnosticError(
            Diagnostic(
                phase="subset-runtime",
                code="unknown_entry",
                message=f"unknown entry function: {entry}",
                line=None,
                column=None,
                snippet=None,
            )
        )
    return eval_function(functions, functions[entry], args)


def eval_function(functions: dict[str, FunctionDef], fn: FunctionDef, args: list[object]) -> object:
    if len(fn.params) != len(args):
        raise DiagnosticError(
            Diagnostic(
                phase="subset-runtime",
                code="arity_mismatch",
                message=f"{fn.name} expects {len(fn.params)} arguments, got {len(args)}",
                line=None,
                column=None,
                snippet=None,
            )
        )
    env = dict(zip(fn.params, args))
    result = eval_block(functions, fn.body, env)
    if isinstance(result, ReturnSignal):
        return result.value
    return None


def eval_block(functions: dict[str, FunctionDef], body: list[Stmt], env: dict[str, object]) -> object:
    for stmt in body:
        result = eval_stmt(functions, stmt, env)
        if isinstance(result, ReturnSignal):
            return result
    return None


def eval_stmt(functions: dict[str, FunctionDef], stmt: Stmt, env: dict[str, object]) -> object:
    if isinstance(stmt, LetStmt):
        env[stmt.name] = eval_expr(functions, stmt.expr, env)
        return None
    if isinstance(stmt, ReturnStmt):
        return ReturnSignal(eval_expr(functions, stmt.expr, env))
    if isinstance(stmt, ExprStmt):
        eval_expr(functions, stmt.expr, env)
        return None
    if isinstance(stmt, IfStmt):
        condition = eval_expr(functions, stmt.condition, env)
        branch = stmt.then_body if truthy(condition) else stmt.else_body
        nested_env = dict(env)
        result = eval_block(functions, branch, nested_env)
        env.update({k: v for k, v in nested_env.items() if k in env})
        return result
    raise AssertionError(f"unknown statement: {stmt}")


def eval_expr(functions: dict[str, FunctionDef], expr: Expr, env: dict[str, object]) -> object:
    if isinstance(expr, StringLiteral):
        return expr.value
    if isinstance(expr, BoolLiteral):
        return expr.value
    if isinstance(expr, IntLiteral):
        return expr.value
    if isinstance(expr, Variable):
        if expr.name not in env:
            raise DiagnosticError(
                Diagnostic(
                    phase="subset-runtime",
                    code="unknown_variable",
                    message=f"unknown variable: {expr.name}",
                    line=None,
                    column=None,
                    snippet=None,
                )
            )
        return env[expr.name]
    if isinstance(expr, Call):
        args = [eval_expr(functions, arg, env) for arg in expr.args]
        if expr.callee in BUILTINS:
            return BUILTINS[expr.callee](*args)
        if expr.callee not in functions:
            raise DiagnosticError(
                Diagnostic(
                    phase="subset-runtime",
                    code="unknown_function",
                    message=f"unknown function: {expr.callee}",
                    line=None,
                    column=None,
                    snippet=None,
                )
            )
        return eval_function(functions, functions[expr.callee], args)
    raise AssertionError(f"unknown expression: {expr}")


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return value is not None


def builtin_eq(left: object, right: object) -> bool:
    return left == right


def builtin_concat(left: object, right: object) -> str:
    return f"{left}{right}"


def builtin_extract_quoted(text: object) -> str:
    if not isinstance(text, str):
        return ""
    start = text.find('"')
    if start == -1:
        return ""
    end = text.find('"', start + 1)
    if end == -1:
        return ""
    return text[start + 1:end]


def builtin_trim(text: object) -> str:
    return text.strip() if isinstance(text, str) else ""


def builtin_print_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps({"kind": "print", "text": text}, ensure_ascii=False, separators=(",", ":"))


def builtin_program_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {"kind": "program", "statements": [{"kind": "print", "text": text}]},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_text(ast: object) -> str:
    if not isinstance(ast, str):
        return ""
    try:
        payload = json.loads(ast)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        return ""
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) != 1:
        return ""
    stmt = statements[0]
    if not isinstance(stmt, dict) or stmt.get("kind") != "print":
        return ""
    text = stmt.get("text")
    return text if isinstance(text, str) else ""


def parse_print_program_source(text: str) -> dict | None:
    statements: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not line.startswith("print "):
            return None
        start = line.find('"')
        if start == -1:
            return None
        end = line.rfind('"')
        if end <= start:
            return None
        statements.append({"kind": "print", "text": line[start + 1:end]})
    if not statements:
        return None
    return {"kind": "program", "statements": statements}


def builtin_parse_print_program(source: object) -> str:
    if not isinstance(source, str):
        return ""
    payload = parse_print_program_source(source)
    if payload is None:
        return ""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def builtin_validate_program_ast(ast: object) -> str:
    if not isinstance(ast, str):
        return "error: invalid program ast"
    try:
        payload = json.loads(ast)
    except json.JSONDecodeError:
        return "error: invalid program ast"
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        return "error: invalid program ast"
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) == 0:
        return "error: invalid program ast"
    for stmt in statements:
        if not isinstance(stmt, dict) or stmt.get("kind") != "print" or not isinstance(stmt.get("text"), str):
            return "error: invalid program ast"
    return "ok"


def builtin_lower_program_artifact(ast: object) -> str:
    if not isinstance(ast, str):
        return "error: invalid program ast"
    try:
        payload = json.loads(ast)
    except json.JSONDecodeError:
        return "error: invalid program ast"
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        return "error: invalid program ast"
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) == 0:
        return "error: invalid program ast"
    texts: list[str] = []
    for stmt in statements:
        if not isinstance(stmt, dict) or stmt.get("kind") != "print" or not isinstance(stmt.get("text"), str):
            return "error: invalid program ast"
        texts.append(stmt["text"])
    return json.dumps({"kind": "print_many", "texts": texts}, ensure_ascii=False, separators=(",", ":"))


BUILTINS = {
    "eq": builtin_eq,
    "concat": builtin_concat,
    "extract_quoted": builtin_extract_quoted,
    "lower_program_artifact": builtin_lower_program_artifact,
    "parse_print_program": builtin_parse_print_program,
    "print_ast": builtin_print_ast,
    "program_ast": builtin_program_ast,
    "program_text": builtin_program_text,
    "validate_program_ast": builtin_validate_program_ast,
    "trim": builtin_trim,
}


class Parser:
    def __init__(self, source: str):
        self.source = source
        self.lines = source.splitlines()
        self.tokens = tokenize(source)
        self.index = 0

    def parse_program(self) -> SubsetProgram:
        functions: list[FunctionDef] = []
        while self.peek().kind != "EOF":
            functions.append(self.parse_function())
        return SubsetProgram(functions=functions)

    def parse_function(self) -> FunctionDef:
        self.expect("FN")
        name = self.expect("IDENT").value
        self.expect("LPAREN")
        params: list[str] = []
        if self.peek().kind != "RPAREN":
            params.append(self.expect("IDENT").value)
            while self.match("COMMA"):
                params.append(self.expect("IDENT").value)
        self.expect("RPAREN")
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body)


    def parse_block(self) -> list[Stmt]:
        self.expect("LBRACE")
        body: list[Stmt] = []
        while self.peek().kind != "RBRACE":
            body.append(self.parse_stmt())
        self.expect("RBRACE")
        return body

    def parse_stmt(self) -> Stmt:
        token = self.peek()
        if token.kind == "LET":
            self.advance()
            name = self.expect("IDENT").value
            self.expect("EQUAL")
            expr = self.parse_expr()
            self.expect("SEMICOLON")
            return LetStmt(name=name, expr=expr)
        if token.kind == "RETURN":
            self.advance()
            expr = self.parse_expr()
            self.expect("SEMICOLON")
            return ReturnStmt(expr=expr)
        if token.kind == "IF":
            self.advance()
            condition = self.parse_expr()
            then_body = self.parse_block()
            else_body: list[Stmt] = []
            if self.match("ELSE"):
                else_body = self.parse_block()
            return IfStmt(condition=condition, then_body=then_body, else_body=else_body)
        expr = self.parse_expr()
        self.expect("SEMICOLON")
        return ExprStmt(expr=expr)

    def parse_expr(self) -> Expr:
        token = self.peek()
        if token.kind == "STRING":
            self.advance()
            return StringLiteral(token.value)
        if token.kind == "INT":
            self.advance()
            return IntLiteral(int(token.value))
        if token.kind == "TRUE":
            self.advance()
            return BoolLiteral(True)
        if token.kind == "FALSE":
            self.advance()
            return BoolLiteral(False)
        if token.kind == "IDENT":
            self.advance()
            if self.match("LPAREN"):
                args: list[Expr] = []
                if self.peek().kind != "RPAREN":
                    args.append(self.parse_expr())
                    while self.match("COMMA"):
                        args.append(self.parse_expr())
                self.expect("RPAREN")
                return Call(token.value, args)
            return Variable(token.value)
        raise self.error(token, "expected expression", code="expected_expression")

    def peek(self) -> Token:
        return self.tokens[self.index]

    def advance(self) -> Token:
        token = self.tokens[self.index]
        self.index += 1
        return token

    def match(self, kind: str) -> bool:
        if self.peek().kind == kind:
            self.advance()
            return True
        return False

    def expect(self, kind: str) -> Token:
        token = self.peek()
        if token.kind != kind:
            raise self.error(token, f"expected {kind}, got {token.kind}", code="unexpected_token")
        return self.advance()

    def error(self, token: Token, message: str, *, code: str) -> DiagnosticError:
        return DiagnosticError(
            Diagnostic(
                phase="subset-parse",
                code=code,
                message=message,
                line=token.line,
                column=token.column,
                snippet=token.snippet,
            )
        )


KEYWORDS = {
    "fn": "FN",
    "let": "LET",
    "return": "RETURN",
    "if": "IF",
    "else": "ELSE",
    "true": "TRUE",
    "false": "FALSE",
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    lines = source.splitlines()
    line = 1
    column = 1
    index = 0

    def snippet_for(line_no: int) -> str:
        if 1 <= line_no <= len(lines):
            return lines[line_no - 1]
        return ""

    while index < len(source):
        ch = source[index]
        if ch in " \t\r":
            index += 1
            column += 1
            continue
        if ch == "\n":
            index += 1
            line += 1
            column = 1
            continue
        if ch == "#":
            while index < len(source) and source[index] != "\n":
                index += 1
                column += 1
            continue
        if ch.isalpha() or ch == "_":
            start = index
            start_col = column
            while index < len(source) and (source[index].isalnum() or source[index] == "_"):
                index += 1
                column += 1
            value = source[start:index]
            tokens.append(Token(KEYWORDS.get(value, "IDENT"), value, line, start_col, snippet_for(line)))
            continue
        if ch.isdigit():
            start = index
            start_col = column
            while index < len(source) and source[index].isdigit():
                index += 1
                column += 1
            tokens.append(Token("INT", source[start:index], line, start_col, snippet_for(line)))
            continue
        if ch == '"':
            start_col = column
            index += 1
            column += 1
            chars: list[str] = []
            while index < len(source) and source[index] != '"':
                if source[index] == "\\" and index + 1 < len(source):
                    escape = source[index + 1]
                    mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
                    chars.append(mapping.get(escape, escape))
                    index += 2
                    column += 2
                    continue
                chars.append(source[index])
                index += 1
                column += 1
            if index >= len(source):
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-parse",
                        code="unterminated_string",
                        message="unterminated string literal",
                        line=line,
                        column=start_col,
                        snippet=snippet_for(line),
                    )
                )
            index += 1
            column += 1
            tokens.append(Token("STRING", "".join(chars), line, start_col, snippet_for(line)))
            continue
        single_tokens = {
            "(": "LPAREN",
            ")": "RPAREN",
            "{": "LBRACE",
            "}": "RBRACE",
            ",": "COMMA",
            ";": "SEMICOLON",
            "=": "EQUAL",
        }
        if ch in single_tokens:
            tokens.append(Token(single_tokens[ch], ch, line, column, snippet_for(line)))
            index += 1
            column += 1
            continue
        raise DiagnosticError(
            Diagnostic(
                phase="subset-parse",
                code="invalid_character",
                message=f"invalid character: {ch}",
                line=line,
                column=column,
                snippet=snippet_for(line),
            )
        )

    tokens.append(Token("EOF", "", line, column, snippet_for(line)))
    return tokens
