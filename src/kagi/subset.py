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
    lines = [raw.strip() for raw in text.splitlines() if raw.strip()]
    statements, index = parse_tiny_stmt_block(lines, 0, stop_at_closing=False)
    if statements is None or index != len(lines):
        return None
    if not statements:
        return None
    return {"kind": "program", "statements": statements}


def parse_tiny_stmt_block(
    lines: list[str], start: int, *, stop_at_closing: bool
) -> tuple[list[dict] | None, int]:
    statements: list[dict] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line == "}":
            if stop_at_closing:
                return statements, index + 1
            return None, index
        if line.startswith("} else {"):
            if stop_at_closing:
                return statements, index
            return None, index
        if line.startswith("if ") and line.endswith("{"):
            condition_text = line[len("if "):-1].strip()
            condition = parse_tiny_expr(condition_text)
            if condition is None:
                return None, index
            then_body, next_index = parse_tiny_stmt_block(lines, index + 1, stop_at_closing=True)
            if then_body is None or next_index > len(lines):
                return None, index
            else_body: list[dict] = []
            if next_index < len(lines) and lines[next_index] == "else {":
                else_body, next_index = parse_tiny_stmt_block(lines, next_index + 1, stop_at_closing=True)
                if else_body is None:
                    return None, index
            elif next_index < len(lines) and lines[next_index].startswith("} else {"):
                else_body, next_index = parse_tiny_stmt_block(lines, next_index + 1, stop_at_closing=True)
                if else_body is None:
                    return None, index
            statements.append(
                {
                    "kind": "if_stmt",
                    "condition": condition,
                    "then_body": then_body,
                    "else_body": else_body,
                }
            )
            index = next_index
            continue
        if line == "else {":
            return None, index
        if line.startswith("let "):
            rest = line[len("let "):].strip()
            if "=" not in rest:
                return None, index
            name, expr = rest.split("=", 1)
            name = name.strip()
            if not name or not name.replace("_", "").isalnum():
                return None, index
            parsed_expr = parse_tiny_expr(expr.strip())
            if parsed_expr is None:
                return None, index
            statements.append({"kind": "let", "name": name, "expr": parsed_expr})
            index += 1
            continue
        if line.startswith("print "):
            expr = line[len("print "):].strip()
            parsed_expr = parse_tiny_expr(expr)
            if parsed_expr is None:
                return None, index
            statements.append({"kind": "print", "expr": parsed_expr})
            index += 1
            continue
        return None, index
    if stop_at_closing:
        return None, index
    return statements, index


def parse_tiny_expr(expr: str) -> dict | None:
    expr = expr.strip()
    if expr.startswith('"') and expr.endswith('"') and len(expr) >= 2:
        return {"kind": "string", "value": expr[1:-1]}
    if expr == "true":
        return {"kind": "bool", "value": True}
    if expr == "false":
        return {"kind": "bool", "value": False}
    prefix = 'concat('
    if expr.startswith(prefix) and expr.endswith(')'):
        inner = expr[len(prefix):-1]
        parts = split_concat_args(inner)
        if parts is None or len(parts) != 2:
            return None
        left = parse_tiny_expr(parts[0])
        right = parse_tiny_expr(parts[1])
        if left is None or right is None:
            return None
        return {"kind": "concat", "left": left, "right": right}
    prefix = 'eq('
    if expr.startswith(prefix) and expr.endswith(')'):
        inner = expr[len(prefix):-1]
        parts = split_concat_args(inner)
        if parts is None or len(parts) != 2:
            return None
        left = parse_tiny_expr(parts[0])
        right = parse_tiny_expr(parts[1])
        if left is None or right is None:
            return None
        return {"kind": "eq", "left": left, "right": right}
    prefix = 'if('
    if expr.startswith(prefix) and expr.endswith(')'):
        inner = expr[len(prefix):-1]
        parts = split_concat_args(inner)
        if parts is None or len(parts) != 3:
            return None
        condition = parse_tiny_expr(parts[0])
        then_expr = parse_tiny_expr(parts[1])
        else_expr = parse_tiny_expr(parts[2])
        if condition is None or then_expr is None or else_expr is None:
            return None
        return {"kind": "if", "condition": condition, "then": then_expr, "else": else_expr}
    if expr and expr.replace("_", "").isalnum():
        return {"kind": "var", "name": expr}
    return None


def split_concat_args(text: str) -> list[str] | None:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    in_string = False
    escape = False
    for ch in text:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch == '"':
            current.append(ch)
            in_string = not in_string
            continue
        if not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue
        current.append(ch)
    if in_string or depth != 0:
        return None
    parts.append("".join(current).strip())
    return parts


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
    defined: set[str] = set()
    for stmt in statements:
        if not isinstance(stmt, dict):
            return "error: invalid program ast"
        kind = stmt.get("kind")
        if kind == "let":
            name = stmt.get("name")
            if not isinstance(name, str) or not name:
                return "error: invalid program ast"
            if validate_tiny_expr(stmt.get("expr"), defined) != "ok":
                return "error: invalid program ast"
            defined.add(name)
            continue
        if kind == "print":
            if validate_tiny_expr(stmt.get("expr"), defined) != "ok":
                return "error: invalid program ast"
            continue
        if kind == "if_stmt":
            if validate_tiny_expr(stmt.get("condition"), defined) != "ok":
                return "error: invalid program ast"
            then_body = stmt.get("then_body")
            else_body = stmt.get("else_body")
            if validate_tiny_body(then_body, defined) != "ok":
                return "error: invalid program ast"
            if validate_tiny_body(else_body, defined) != "ok":
                return "error: invalid program ast"
            continue
        return "error: invalid program ast"
    return "ok"


def validate_tiny_body(body: object, defined: set[str]) -> str:
    if not isinstance(body, list):
        return "error"
    nested_defined = set(defined)
    for stmt in body:
        if not isinstance(stmt, dict):
            return "error"
        kind = stmt.get("kind")
        if kind == "let":
            name = stmt.get("name")
            if not isinstance(name, str) or not name:
                return "error"
            if validate_tiny_expr(stmt.get("expr"), nested_defined) != "ok":
                return "error"
            nested_defined.add(name)
            continue
        if kind == "print":
            if validate_tiny_expr(stmt.get("expr"), nested_defined) != "ok":
                return "error"
            continue
        if kind == "if_stmt":
            if validate_tiny_expr(stmt.get("condition"), nested_defined) != "ok":
                return "error"
            if validate_tiny_body(stmt.get("then_body"), nested_defined) != "ok":
                return "error"
            if validate_tiny_body(stmt.get("else_body"), nested_defined) != "ok":
                return "error"
            continue
        return "error"
    return "ok"


def validate_tiny_expr(expr: object, defined: set[str]) -> str:
    if not isinstance(expr, dict):
        return "error"
    kind = expr.get("kind")
    if kind == "string":
        return "ok" if isinstance(expr.get("value"), str) else "error"
    if kind == "bool":
        return "ok" if isinstance(expr.get("value"), bool) else "error"
    if kind == "var":
        name = expr.get("name")
        return "ok" if isinstance(name, str) and name in defined else "error"
    if kind == "concat":
        left_ok = validate_tiny_expr(expr.get("left"), defined)
        right_ok = validate_tiny_expr(expr.get("right"), defined)
        return "ok" if left_ok == "ok" and right_ok == "ok" else "error"
    if kind == "eq":
        left_ok = validate_tiny_expr(expr.get("left"), defined)
        right_ok = validate_tiny_expr(expr.get("right"), defined)
        return "ok" if left_ok == "ok" and right_ok == "ok" else "error"
    if kind == "if":
        cond_ok = validate_tiny_expr(expr.get("condition"), defined)
        then_ok = validate_tiny_expr(expr.get("then"), defined)
        else_ok = validate_tiny_expr(expr.get("else"), defined)
        return "ok" if cond_ok == "ok" and then_ok == "ok" and else_ok == "ok" else "error"
    return "error"


def eval_tiny_expr(expr: object, env: dict[str, str | bool]) -> str | bool | None:
    if not isinstance(expr, dict):
        return None
    kind = expr.get("kind")
    if kind == "string":
        value = expr.get("value")
        return value if isinstance(value, str) else None
    if kind == "bool":
        value = expr.get("value")
        return value if isinstance(value, bool) else None
    if kind == "var":
        name = expr.get("name")
        return env.get(name) if isinstance(name, str) else None
    if kind == "concat":
        left = eval_tiny_expr(expr.get("left"), env)
        right = eval_tiny_expr(expr.get("right"), env)
        if not isinstance(left, str) or not isinstance(right, str):
            return None
        return left + right
    if kind == "eq":
        left = eval_tiny_expr(expr.get("left"), env)
        right = eval_tiny_expr(expr.get("right"), env)
        if left is None or right is None:
            return None
        return left == right
    if kind == "if":
        condition = eval_tiny_expr(expr.get("condition"), env)
        if not isinstance(condition, bool):
            return None
        branch = expr.get("then") if condition else expr.get("else")
        return eval_tiny_expr(branch, env)
    return None


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
    env: dict[str, str | bool] = {}
    texts: list[str] = []
    if eval_tiny_body(statements, env, texts) != "ok":
        return "error: invalid program ast"
    return json.dumps({"kind": "print_many", "texts": texts}, ensure_ascii=False, separators=(",", ":"))


def eval_tiny_body(body: object, env: dict[str, str | bool], texts: list[str]) -> str:
    if not isinstance(body, list):
        return "error"
    nested_env = dict(env)
    for stmt in body:
        if not isinstance(stmt, dict):
            return "error"
        kind = stmt.get("kind")
        if kind == "let":
            name = stmt.get("name")
            value = eval_tiny_expr(stmt.get("expr"), nested_env)
            if not isinstance(name, str) or value is None:
                return "error"
            nested_env[name] = value
            continue
        if kind == "print":
            value = eval_tiny_expr(stmt.get("expr"), nested_env)
            if not isinstance(value, str):
                return "error"
            texts.append(value)
            continue
        if kind == "if_stmt":
            condition = eval_tiny_expr(stmt.get("condition"), nested_env)
            if not isinstance(condition, bool):
                return "error"
            branch = stmt.get("then_body") if condition else stmt.get("else_body")
            if eval_tiny_body(branch, nested_env, texts) != "ok":
                return "error"
            continue
        return "error"
    return "ok"


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
