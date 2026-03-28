from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error


@dataclass(frozen=True)
class SurfaceStringV1:
    value: str


@dataclass(frozen=True)
class SurfaceBoolV1:
    value: bool


@dataclass(frozen=True)
class SurfaceVarV1:
    name: str


@dataclass(frozen=True)
class SurfaceConcatV1:
    left: "SurfaceExprV1"
    right: "SurfaceExprV1"


@dataclass(frozen=True)
class SurfaceEqV1:
    left: "SurfaceExprV1"
    right: "SurfaceExprV1"


@dataclass(frozen=True)
class SurfaceIfExprV1:
    condition: "SurfaceExprV1"
    then_expr: "SurfaceExprV1"
    else_expr: "SurfaceExprV1"


SurfaceExprV1 = (
    SurfaceStringV1
    | SurfaceBoolV1
    | SurfaceVarV1
    | SurfaceConcatV1
    | SurfaceEqV1
    | SurfaceIfExprV1
)


@dataclass(frozen=True)
class SurfacePrintStmtV1:
    expr: SurfaceExprV1


@dataclass(frozen=True)
class SurfaceLetStmtV1:
    name: str
    expr: SurfaceExprV1


@dataclass(frozen=True)
class SurfaceIfStmtV1:
    condition: SurfaceExprV1
    then_body: list["SurfaceStmtV1"]
    else_body: list["SurfaceStmtV1"]


@dataclass(frozen=True)
class SurfaceCallStmtV1:
    name: str
    args: list[SurfaceExprV1]


SurfaceStmtV1 = SurfacePrintStmtV1 | SurfaceLetStmtV1 | SurfaceIfStmtV1 | SurfaceCallStmtV1


@dataclass(frozen=True)
class SurfaceFunctionV1:
    name: str
    params: list[str]
    body: list[SurfaceStmtV1]


@dataclass(frozen=True)
class SurfaceProgramV1:
    functions: list[SurfaceFunctionV1]
    statements: list[SurfaceStmtV1]


def parse_surface_program_v1(raw: object) -> SurfaceProgramV1:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "program ast must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", f"invalid program ast json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "unsupported program ast")
        )
    functions_raw = payload.get("functions", [])
    statements_raw = payload.get("statements")
    if not isinstance(functions_raw, list) or not isinstance(statements_raw, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "program ast requires functions and statements")
        )
    return SurfaceProgramV1(
        functions=[parse_surface_function_v1(item) for item in functions_raw],
        statements=[parse_surface_stmt_v1(item) for item in statements_raw],
    )


def parse_surface_function_v1(raw: object) -> SurfaceFunctionV1:
    if not isinstance(raw, dict) or raw.get("kind") != "fn":
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "function must be an object")
        )
    name = raw.get("name")
    params = raw.get("params", [])
    body = raw.get("body")
    if not isinstance(name, str) or not isinstance(params, list) or not isinstance(body, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "function requires name, params, and body")
        )
    if not all(isinstance(param, str) and param for param in params):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "function params must be strings")
        )
    return SurfaceFunctionV1(
        name=name,
        params=params,
        body=[parse_surface_stmt_v1(item) for item in body],
    )


def parse_surface_stmt_v1(raw: object) -> SurfaceStmtV1:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "statement must be an object")
        )
    kind = raw.get("kind")
    if kind == "print":
        return SurfacePrintStmtV1(expr=parse_surface_expr_v1(raw.get("expr")))
    if kind == "let":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "let statement requires name")
            )
        return SurfaceLetStmtV1(name=name, expr=parse_surface_expr_v1(raw.get("expr")))
    if kind == "if_stmt":
        then_body = raw.get("then_body")
        else_body = raw.get("else_body")
        if not isinstance(then_body, list) or not isinstance(else_body, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "if statement requires bodies")
            )
        return SurfaceIfStmtV1(
            condition=parse_surface_expr_v1(raw.get("condition")),
            then_body=[parse_surface_stmt_v1(item) for item in then_body],
            else_body=[parse_surface_stmt_v1(item) for item in else_body],
        )
    if kind == "call":
        name = raw.get("name")
        args = raw.get("args", [])
        if not isinstance(name, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "call statement requires name and args")
            )
        return SurfaceCallStmtV1(name=name, args=[parse_surface_expr_v1(item) for item in args])
    raise DiagnosticError(
        diagnostic_from_runtime_error("surface-ast", "unsupported statement in program ast")
    )


def parse_surface_expr_v1(raw: object) -> SurfaceExprV1:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("surface-ast", "expression must be an object")
        )
    kind = raw.get("kind")
    if kind == "string":
        value = raw.get("value")
        if not isinstance(value, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "string expression requires value")
            )
        return SurfaceStringV1(value=value)
    if kind == "bool":
        value = raw.get("value")
        if not isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "bool expression requires value")
            )
        return SurfaceBoolV1(value=value)
    if kind == "var":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("surface-ast", "var expression requires name")
            )
        return SurfaceVarV1(name=name)
    if kind == "concat":
        return SurfaceConcatV1(
            left=parse_surface_expr_v1(raw.get("left")),
            right=parse_surface_expr_v1(raw.get("right")),
        )
    if kind == "eq":
        return SurfaceEqV1(
            left=parse_surface_expr_v1(raw.get("left")),
            right=parse_surface_expr_v1(raw.get("right")),
        )
    if kind == "if":
        return SurfaceIfExprV1(
            condition=parse_surface_expr_v1(raw.get("condition")),
            then_expr=parse_surface_expr_v1(raw.get("then")),
            else_expr=parse_surface_expr_v1(raw.get("else")),
        )
    raise DiagnosticError(
        diagnostic_from_runtime_error("surface-ast", "unsupported expression in program ast")
    )
