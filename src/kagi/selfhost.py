from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint


@dataclass(frozen=True)
class TinyPrint:
    expr: "TinyExpr"


@dataclass(frozen=True)
class TinyLet:
    name: str
    expr: "TinyExpr"


@dataclass(frozen=True)
class TinyIfStmt:
    condition: "TinyExpr"
    then_body: list["TinyStmt"]
    else_body: list["TinyStmt"]


@dataclass(frozen=True)
class TinyCallStmt:
    name: str


@dataclass(frozen=True)
class TinyFunction:
    name: str
    body: list["TinyStmt"]


@dataclass(frozen=True)
class TinyString:
    value: str


@dataclass(frozen=True)
class TinyBool:
    value: bool


@dataclass(frozen=True)
class TinyConcat:
    left: "TinyExpr"
    right: "TinyExpr"


@dataclass(frozen=True)
class TinyEq:
    left: "TinyExpr"
    right: "TinyExpr"


@dataclass(frozen=True)
class TinyIfExpr:
    condition: "TinyExpr"
    then_expr: "TinyExpr"
    else_expr: "TinyExpr"


@dataclass(frozen=True)
class TinyVar:
    name: str


TinyExpr = TinyString | TinyBool | TinyConcat | TinyEq | TinyIfExpr | TinyVar
TinyStmt = TinyLet | TinyPrint | TinyIfStmt | TinyCallStmt


@dataclass(frozen=True)
class TinyProgram:
    functions: list[TinyFunction]
    statements: list[TinyStmt]


def parse_tiny_program_ast_json(raw: object) -> TinyProgram:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "program ast must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", f"invalid program ast json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported program ast")
        )
    statements_raw = payload.get("statements")
    functions_raw = payload.get("functions", [])
    if not isinstance(functions_raw, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "program ast requires functions")
        )
    if not isinstance(statements_raw, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "program ast requires statements")
        )
    functions: list[TinyFunction] = []
    for fn in functions_raw:
        functions.append(parse_tiny_function(fn))
    statements: list[TinyStmt] = []
    for stmt in statements_raw:
        statements.append(parse_tiny_stmt(stmt))
    return TinyProgram(functions=functions, statements=statements)


def parse_tiny_function(fn: object) -> TinyFunction:
    if not isinstance(fn, dict) or fn.get("kind") != "fn":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "function must be an object")
        )
    name = fn.get("name")
    body_raw = fn.get("body")
    if not isinstance(name, str) or not isinstance(body_raw, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "function requires name and body")
        )
    return TinyFunction(name=name, body=[parse_tiny_stmt(item) for item in body_raw])


def parse_tiny_stmt(stmt: object) -> TinyStmt:
    if not isinstance(stmt, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "statement must be an object")
        )
    kind = stmt.get("kind")
    if kind == "let":
        name = stmt.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "let statement requires name")
            )
        return TinyLet(name=name, expr=parse_tiny_expr(stmt.get("expr")))
    if kind == "print":
        return TinyPrint(expr=parse_tiny_expr(stmt.get("expr")))
    if kind == "if_stmt":
        then_body_raw = stmt.get("then_body")
        else_body_raw = stmt.get("else_body")
        if not isinstance(then_body_raw, list) or not isinstance(else_body_raw, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "if statement requires bodies")
            )
        return TinyIfStmt(
            condition=parse_tiny_expr(stmt.get("condition")),
            then_body=[parse_tiny_stmt(item) for item in then_body_raw],
            else_body=[parse_tiny_stmt(item) for item in else_body_raw],
        )
    if kind == "call":
        name = stmt.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "call statement requires name")
            )
        return TinyCallStmt(name=name)
    raise DiagnosticError(
        diagnostic_from_runtime_error("selfhost-bridge", "unsupported statement in program ast")
    )


def parse_tiny_expr(expr: object) -> TinyExpr:
    if not isinstance(expr, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "expression must be an object")
        )
    kind = expr.get("kind")
    if kind == "string":
        value = expr.get("value")
        if not isinstance(value, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "string expression requires value")
            )
        return TinyString(value=value)
    if kind == "bool":
        value = expr.get("value")
        if not isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "bool expression requires value")
            )
        return TinyBool(value=value)
    if kind == "var":
        name = expr.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "var expression requires name")
            )
        return TinyVar(name=name)
    if kind == "concat":
        return TinyConcat(
            left=parse_tiny_expr(expr.get("left")),
            right=parse_tiny_expr(expr.get("right")),
        )
    if kind == "eq":
        return TinyEq(
            left=parse_tiny_expr(expr.get("left")),
            right=parse_tiny_expr(expr.get("right")),
        )
    if kind == "if":
        return TinyIfExpr(
            condition=parse_tiny_expr(expr.get("condition")),
            then_expr=parse_tiny_expr(expr.get("then")),
            else_expr=parse_tiny_expr(expr.get("else")),
        )
    raise DiagnosticError(
        diagnostic_from_runtime_error("selfhost-bridge", "unsupported expression in program ast")
    )


def lower_tiny_program(program: TinyProgram) -> str:
    fragment = lower_tiny_program_to_capir(program)
    texts = [stmt.text for stmt in fragment.ops]
    return json.dumps({"kind": "print_many", "texts": texts}, ensure_ascii=False, separators=(",", ":"))


def lower_tiny_program_to_capir(program: TinyProgram) -> CapIRFragment:
    if len(program.statements) == 0:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "tiny program requires at least one statement")
        )
    env: dict[str, str | bool] = {}
    ops: list[CapIRPrint] = []
    functions = {fn.name: fn.body for fn in program.functions}
    execute_tiny_statements(program.statements, env, ops, functions, set())
    if len(ops) == 0:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "tiny program requires at least one print")
        )
    return CapIRFragment(effect="print", ops=ops)


def render_tiny_program(program: TinyProgram) -> str:
    if len(program.statements) == 0:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "tiny program requires at least one statement")
        )
    return "\n".join(op.text for op in lower_tiny_program_to_capir(program).ops)


def eval_tiny_expr(expr: TinyExpr, env: dict[str, str | bool]) -> str | bool:
    if isinstance(expr, TinyString):
        return expr.value
    if isinstance(expr, TinyBool):
        return expr.value
    if isinstance(expr, TinyVar):
        if expr.name not in env:
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", f"unknown variable: {expr.name}")
            )
        return env[expr.name]
    if isinstance(expr, TinyConcat):
        left = eval_tiny_expr(expr.left, env)
        right = eval_tiny_expr(expr.right, env)
        if not isinstance(left, str) or not isinstance(right, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "concat requires string operands")
            )
        return left + right
    if isinstance(expr, TinyEq):
        return eval_tiny_expr(expr.left, env) == eval_tiny_expr(expr.right, env)
    if isinstance(expr, TinyIfExpr):
        condition = eval_tiny_expr(expr.condition, env)
        if not isinstance(condition, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "if requires boolean condition")
            )
        return eval_tiny_expr(expr.then_expr if condition else expr.else_expr, env)
    raise DiagnosticError(
        diagnostic_from_runtime_error("selfhost-bridge", "unsupported tiny expression")
    )


def execute_tiny_statements(
    statements: list[TinyStmt],
    env: dict[str, str | bool],
    ops: list[CapIRPrint],
    functions: dict[str, list[TinyStmt]],
    call_stack: set[str],
) -> None:
    for stmt in statements:
        if isinstance(stmt, TinyLet):
            env[stmt.name] = eval_tiny_expr(stmt.expr, env)
            continue
        if isinstance(stmt, TinyPrint):
            value = eval_tiny_expr(stmt.expr, env)
            if not isinstance(value, str):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("selfhost-bridge", "print requires string expression")
                )
            ops.append(CapIRPrint(text=value))
            continue
        if isinstance(stmt, TinyIfStmt):
            condition = eval_tiny_expr(stmt.condition, env)
            if not isinstance(condition, bool):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("selfhost-bridge", "if requires boolean condition")
                )
            branch = stmt.then_body if condition else stmt.else_body
            execute_tiny_statements(branch, dict(env), ops, functions, call_stack)
            continue
        if isinstance(stmt, TinyCallStmt):
            if stmt.name not in functions:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("selfhost-bridge", f"unknown tiny function: {stmt.name}")
                )
            if stmt.name in call_stack:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("selfhost-bridge", f"recursive tiny function: {stmt.name}")
                )
            execute_tiny_statements(functions[stmt.name], dict(env), ops, functions, call_stack | {stmt.name})
            continue
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported tiny statement")
        )


def render_print_artifact(artifact: object) -> str:
    if not isinstance(artifact, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "selfhost artifact must be a string")
        )
    if artifact.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", artifact)
        )
    try:
        payload = json.loads(artifact)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", f"invalid selfhost artifact json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") not in {"print", "print_many"}:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported selfhost artifact")
        )
    if payload.get("kind") == "print":
        text = payload.get("text")
        if not isinstance(text, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "print artifact requires string text")
            )
        return text
    texts = payload.get("texts")
    if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "print_many artifact requires string texts")
        )
    return "\n".join(texts)
