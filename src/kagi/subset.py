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


def builtin_starts_with(text: object, prefix: object) -> bool:
    return isinstance(text, str) and isinstance(prefix, str) and text.startswith(prefix)


def builtin_ends_with(text: object, suffix: object) -> bool:
    return isinstance(text, str) and isinstance(suffix, str) and text.endswith(suffix)


def builtin_quote() -> str:
    return '"'


def builtin_line_count(text: object) -> int:
    if not isinstance(text, str):
        return 0
    return len([line.strip() for line in text.splitlines() if line.strip()])


def builtin_line_at(text: object, index: object) -> str:
    if not isinstance(text, str) or not isinstance(index, int):
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if index < 0 or index >= len(lines):
        return ""
    return lines[index]


def builtin_before_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[:pos]


def builtin_after_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[pos + len(needle):]


def builtin_is_identifier(text: object) -> bool:
    return isinstance(text, str) and text != "" and text.replace("_", "").isalnum()


def builtin_print_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {"kind": "print", "expr": {"kind": "string", "value": text}},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_ast(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [{"kind": "print", "expr": {"kind": "string", "value": text}}],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_let_print_ast(name: object, text: object) -> str:
    if not isinstance(name, str):
        name = str(name)
    if not isinstance(text, str):
        text = str(text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [],
            "statements": [
                {"kind": "let", "name": name, "expr": {"kind": "string", "value": text}},
                {"kind": "print", "expr": {"kind": "var", "name": name}},
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_program_single_arg_fn_call_ast(
    fn_name: object,
    param_name: object,
    arg_text: object,
    suffix_text: object,
) -> str:
    if not isinstance(fn_name, str):
        fn_name = str(fn_name)
    if not isinstance(param_name, str):
        param_name = str(param_name)
    if not isinstance(arg_text, str):
        arg_text = str(arg_text)
    if not isinstance(suffix_text, str):
        suffix_text = str(suffix_text)
    return json.dumps(
        {
            "kind": "program",
            "functions": [
                {
                    "kind": "fn",
                    "name": fn_name,
                    "params": [param_name],
                    "body": [
                        {
                            "kind": "print",
                            "expr": {
                                "kind": "concat",
                                "left": {"kind": "var", "name": param_name},
                                "right": {"kind": "string", "value": suffix_text},
                            },
                        }
                    ],
                }
            ],
            "statements": [
                {
                    "kind": "call",
                    "name": fn_name,
                    "args": [{"kind": "string", "value": arg_text}],
                }
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def builtin_print_many_artifact(text: object) -> str:
    if not isinstance(text, str):
        text = str(text)
    return json.dumps({"kind": "print_many", "texts": [text]}, ensure_ascii=False, separators=(",", ":"))


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
    expr = stmt.get("expr")
    if not isinstance(expr, dict) or expr.get("kind") != "string":
        return ""
    text = expr.get("value")
    return text if isinstance(text, str) else ""


def parse_print_program_source(text: str) -> dict | None:
    lines = [raw.strip() for raw in text.splitlines() if raw.strip()]
    functions, statements, index = parse_tiny_program_items(lines, 0)
    if functions is None or statements is None or index != len(lines):
        return None
    if not statements:
        return None
    return {"kind": "program", "functions": functions, "statements": statements}


def parse_tiny_program_items(
    lines: list[str], start: int
) -> tuple[list[dict] | None, list[dict] | None, int]:
    functions: list[dict] = []
    statements: list[dict] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.startswith("fn ") and line.endswith("{"):
            header = line[len("fn "):-1].strip()
            if "(" not in header or not header.endswith(")"):
                return None, None, index
            name, params_raw = header.split("(", 1)
            name = name.strip()
            params_raw = params_raw[:-1].strip()
            if not name or not name.replace("_", "").isalnum():
                return None, None, index
            params = parse_tiny_name_list(params_raw)
            if params is None:
                return None, None, index
            body, next_index = parse_tiny_stmt_block(lines, index + 1, stop_at_closing=True)
            if body is None:
                return None, None, index
            functions.append({"kind": "fn", "name": name, "params": params, "body": body})
            index = next_index
            continue
        block, next_index = parse_tiny_stmt_block(lines, index, stop_at_closing=False)
        if block is None:
            return None, None, index
        statements.extend(block)
        index = next_index
        break
    return functions, statements, index


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
        if line.startswith("call ") and line.endswith(")"):
            call_text = line[len("call "):].strip()
            if "(" not in call_text or not call_text.endswith(")"):
                return None, index
            name, args_raw = call_text.split("(", 1)
            name = name.strip()
            args_raw = args_raw[:-1].strip()
            if not name or not name.replace("_", "").isalnum():
                return None, index
            args = parse_tiny_call_args(args_raw)
            if args is None:
                return None, index
            statements.append({"kind": "call", "name": name, "args": args})
            index += 1
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


def parse_tiny_name_list(text: str) -> list[str] | None:
    if text == "":
        return []
    names = [part.strip() for part in text.split(",")]
    if len(names) > 1:
        return None
    if not names[0] or not names[0].replace("_", "").isalnum():
        return None
    return names


def parse_tiny_call_args(text: str) -> list[dict] | None:
    if text == "":
        return []
    expr = parse_tiny_expr(text)
    if expr is None:
        return None
    return [expr]


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
    functions = payload.get("functions", [])
    if not isinstance(functions, list):
        return "error: invalid program ast"
    function_signatures: dict[str, int] = {}
    for fn in functions:
        if not isinstance(fn, dict) or fn.get("kind") != "fn":
            return "error: invalid program ast"
        name = fn.get("name")
        params = fn.get("params", [])
        body = fn.get("body")
        if not isinstance(name, str) or not name:
            return "error: invalid program ast"
        if name in function_signatures:
            return "error: invalid program ast"
        if not isinstance(params, list) or not all(isinstance(param, str) and param for param in params):
            return "error: invalid program ast"
        if len(params) > 1:
            return "error: invalid program ast"
        function_signatures[name] = len(params)
        if validate_tiny_body(body, set(params), function_signatures) != "ok":
            return "error: invalid program ast"
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) == 0:
        return "error: invalid program ast"
    return validate_tiny_body(statements, set(), function_signatures)


def validate_tiny_body(body: object, defined: set[str], functions: dict[str, int]) -> str:
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
        if kind == "call":
            name = stmt.get("name")
            args = stmt.get("args", [])
            if not isinstance(name, str) or name not in functions:
                return "error"
            if not isinstance(args, list) or len(args) != functions[name]:
                return "error"
            if any(validate_tiny_expr(arg, nested_defined) != "ok" for arg in args):
                return "error"
            continue
        if kind == "if_stmt":
            if validate_tiny_expr(stmt.get("condition"), nested_defined) != "ok":
                return "error"
            if validate_tiny_body(stmt.get("then_body"), nested_defined, functions) != "ok":
                return "error"
            if validate_tiny_body(stmt.get("else_body"), nested_defined, functions) != "ok":
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
    functions_raw = payload.get("functions", [])
    if not isinstance(functions_raw, list):
        return "error: invalid program ast"
    functions: dict[str, tuple[list[str], list[dict]]] = {}
    for fn in functions_raw:
        if not isinstance(fn, dict) or fn.get("kind") != "fn":
            return "error: invalid program ast"
        name = fn.get("name")
        params = fn.get("params", [])
        body = fn.get("body")
        if not isinstance(name, str) or not isinstance(body, list):
            return "error: invalid program ast"
        if not isinstance(params, list) or not all(isinstance(param, str) and param for param in params):
            return "error: invalid program ast"
        if len(params) > 1:
            return "error: invalid program ast"
        functions[name] = (params, body)
    statements = payload.get("statements")
    if not isinstance(statements, list) or len(statements) == 0:
        return "error: invalid program ast"
    env: dict[str, str | bool] = {}
    texts: list[str] = []
    if eval_tiny_body(statements, env, texts, functions, set()) != "ok":
        return "error: invalid program ast"
    return json.dumps({"kind": "print_many", "texts": texts}, ensure_ascii=False, separators=(",", ":"))


def eval_tiny_body(
    body: object,
    env: dict[str, str | bool],
    texts: list[str],
    functions: dict[str, tuple[list[str], list[dict]]],
    call_stack: set[str],
) -> str:
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
        if kind == "call":
            name = stmt.get("name")
            args = stmt.get("args", [])
            if not isinstance(name, str) or name not in functions:
                return "error"
            params, fn_body = functions[name]
            if not isinstance(args, list) or len(args) != len(params):
                return "error"
            if name in call_stack:
                return "error"
            nested_call_env = dict(nested_env)
            for param_name, arg_expr in zip(params, args):
                value = eval_tiny_expr(arg_expr, nested_env)
                if value is None:
                    return "error"
                nested_call_env[param_name] = value
            if eval_tiny_body(fn_body, nested_call_env, texts, functions, call_stack | {name}) != "ok":
                return "error"
            continue
        if kind == "if_stmt":
            condition = eval_tiny_expr(stmt.get("condition"), nested_env)
            if not isinstance(condition, bool):
                return "error"
            branch = stmt.get("then_body") if condition else stmt.get("else_body")
            if eval_tiny_body(branch, nested_env, texts, functions, call_stack) != "ok":
                return "error"
            continue
        return "error"
    return "ok"


BUILTINS = {
    "after_substring": builtin_after_substring,
    "before_substring": builtin_before_substring,
    "eq": builtin_eq,
    "concat": builtin_concat,
    "ends_with": builtin_ends_with,
    "extract_quoted": builtin_extract_quoted,
    "is_identifier": builtin_is_identifier,
    "line_at": builtin_line_at,
    "line_count": builtin_line_count,
    "lower_program_artifact": builtin_lower_program_artifact,
    "parse_print_program": builtin_parse_print_program,
    "print_ast": builtin_print_ast,
    "print_many_artifact": builtin_print_many_artifact,
    "program_ast": builtin_program_ast,
    "program_single_arg_fn_call_ast": builtin_program_single_arg_fn_call_ast,
    "program_let_print_ast": builtin_program_let_print_ast,
    "program_text": builtin_program_text,
    "quote": builtin_quote,
    "starts_with": builtin_starts_with,
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
