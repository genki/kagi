from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error

from .surface_ast import (
    SurfaceBoolV1,
    SurfaceCallStmtV1,
    SurfaceConcatV1,
    SurfaceEqV1,
    SurfaceExprV1,
    SurfaceFunctionV1,
    SurfaceIfExprV1,
    SurfaceIfStmtV1,
    SurfaceLetStmtV1,
    SurfacePrintStmtV1,
    SurfaceProgramV1,
    SurfaceStringV1,
    SurfaceStmtV1,
    SurfaceVarV1,
)


@dataclass(frozen=True)
class HIRStringV1:
    value: str


@dataclass(frozen=True)
class HIRBoolV1:
    value: bool


@dataclass(frozen=True)
class HIRVarV1:
    name: str


@dataclass(frozen=True)
class HIRConcatV1:
    left: "HIRExprV1"
    right: "HIRExprV1"


@dataclass(frozen=True)
class HIREqV1:
    left: "HIRExprV1"
    right: "HIRExprV1"


@dataclass(frozen=True)
class HIRIfExprV1:
    condition: "HIRExprV1"
    then_expr: "HIRExprV1"
    else_expr: "HIRExprV1"


HIRExprV1 = HIRStringV1 | HIRBoolV1 | HIRVarV1 | HIRConcatV1 | HIREqV1 | HIRIfExprV1


@dataclass(frozen=True)
class HIRPrintStmtV1:
    expr: HIRExprV1


@dataclass(frozen=True)
class HIRLetStmtV1:
    name: str
    expr: HIRExprV1


@dataclass(frozen=True)
class HIRIfStmtV1:
    condition: HIRExprV1
    then_body: list["HIRStmtV1"]
    else_body: list["HIRStmtV1"]


@dataclass(frozen=True)
class HIRCallStmtV1:
    name: str
    args: list[HIRExprV1]


HIRStmtV1 = HIRPrintStmtV1 | HIRLetStmtV1 | HIRIfStmtV1 | HIRCallStmtV1


@dataclass(frozen=True)
class HIRFunctionV1:
    name: str
    params: list[str]
    body: list[HIRStmtV1]


@dataclass(frozen=True)
class HIRProgramV1:
    functions: list[HIRFunctionV1]
    statements: list[HIRStmtV1]


def inspect_hir_expr_v1(expr: HIRExprV1) -> dict[str, object]:
    if isinstance(expr, HIRStringV1):
        return {"kind": "string", "value": expr.value}
    if isinstance(expr, HIRBoolV1):
        return {"kind": "bool", "value": expr.value}
    if isinstance(expr, HIRVarV1):
        return {"kind": "var", "name": expr.name}
    if isinstance(expr, HIRConcatV1):
        return {
            "kind": "concat",
            "left": inspect_hir_expr_v1(expr.left),
            "right": inspect_hir_expr_v1(expr.right),
        }
    if isinstance(expr, HIREqV1):
        return {
            "kind": "eq",
            "left": inspect_hir_expr_v1(expr.left),
            "right": inspect_hir_expr_v1(expr.right),
        }
    if isinstance(expr, HIRIfExprV1):
        return {
            "kind": "if",
            "condition": inspect_hir_expr_v1(expr.condition),
            "then": inspect_hir_expr_v1(expr.then_expr),
            "else": inspect_hir_expr_v1(expr.else_expr),
        }
    raise TypeError(f"unsupported hir expr: {expr!r}")


def inspect_hir_stmt_v1(stmt: HIRStmtV1) -> dict[str, object]:
    if isinstance(stmt, HIRPrintStmtV1):
        return {"kind": "print", "expr": inspect_hir_expr_v1(stmt.expr)}
    if isinstance(stmt, HIRLetStmtV1):
        return {"kind": "let", "name": stmt.name, "expr": inspect_hir_expr_v1(stmt.expr)}
    if isinstance(stmt, HIRIfStmtV1):
        return {
            "kind": "if_stmt",
            "condition": inspect_hir_expr_v1(stmt.condition),
            "then_body": [inspect_hir_stmt_v1(item) for item in stmt.then_body],
            "else_body": [inspect_hir_stmt_v1(item) for item in stmt.else_body],
        }
    if isinstance(stmt, HIRCallStmtV1):
        return {
            "kind": "call",
            "name": stmt.name,
            "args": [inspect_hir_expr_v1(arg) for arg in stmt.args],
        }
    raise TypeError(f"unsupported hir stmt: {stmt!r}")


def inspect_hir_program_v1(program: HIRProgramV1) -> dict[str, object]:
    return {
        "kind": "hir_program",
        "functions": [
            {
                "name": fn.name,
                "params": list(fn.params),
                "body": [inspect_hir_stmt_v1(stmt) for stmt in fn.body],
            }
            for fn in program.functions
        ],
        "statements": [inspect_hir_stmt_v1(stmt) for stmt in program.statements],
    }


def hir_program_v1_to_json(program: HIRProgramV1) -> str:
    return json.dumps(inspect_hir_program_v1(program), ensure_ascii=False, separators=(",", ":"))


def parse_hir_program_v1(raw: object) -> HIRProgramV1:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir program must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", f"invalid hir json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "hir_program":
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "unsupported hir payload")
        )
    functions = payload.get("functions", [])
    statements = payload.get("statements", [])
    if not isinstance(functions, list) or not isinstance(statements, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir program requires functions and statements")
        )
    return HIRProgramV1(
        functions=[parse_hir_function_v1(item) for item in functions],
        statements=[parse_hir_stmt_v1(item) for item in statements],
    )


def parse_hir_function_v1(raw: object) -> HIRFunctionV1:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir function must be an object")
        )
    name = raw.get("name")
    params = raw.get("params", [])
    body = raw.get("body")
    if not isinstance(name, str) or not isinstance(params, list) or not isinstance(body, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir function requires name, params, and body")
        )
    if not all(isinstance(param, str) and param for param in params):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir params must be strings")
        )
    return HIRFunctionV1(
        name=name,
        params=list(params),
        body=[parse_hir_stmt_v1(item) for item in body],
    )


def parse_hir_stmt_v1(raw: object) -> HIRStmtV1:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir statement must be an object")
        )
    kind = raw.get("kind")
    if kind == "print":
        return HIRPrintStmtV1(expr=parse_hir_expr_v1(raw.get("expr")))
    if kind == "let":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir let requires name")
            )
        return HIRLetStmtV1(name=name, expr=parse_hir_expr_v1(raw.get("expr")))
    if kind == "if_stmt":
        then_body = raw.get("then_body")
        else_body = raw.get("else_body")
        if not isinstance(then_body, list) or not isinstance(else_body, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir if requires bodies")
            )
        return HIRIfStmtV1(
            condition=parse_hir_expr_v1(raw.get("condition")),
            then_body=[parse_hir_stmt_v1(item) for item in then_body],
            else_body=[parse_hir_stmt_v1(item) for item in else_body],
        )
    if kind == "call":
        name = raw.get("name")
        args = raw.get("args", [])
        if not isinstance(name, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir call requires name and args")
            )
        return HIRCallStmtV1(name=name, args=[parse_hir_expr_v1(item) for item in args])
    raise DiagnosticError(
        diagnostic_from_runtime_error("hir", "unsupported hir statement")
    )


def parse_hir_expr_v1(raw: object) -> HIRExprV1:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("hir", "hir expression must be an object")
        )
    kind = raw.get("kind")
    if kind == "string":
        value = raw.get("value")
        if not isinstance(value, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir string requires value")
            )
        return HIRStringV1(value=value)
    if kind == "bool":
        value = raw.get("value")
        if not isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir bool requires value")
            )
        return HIRBoolV1(value=value)
    if kind == "var":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("hir", "hir var requires name")
            )
        return HIRVarV1(name=name)
    if kind == "concat":
        return HIRConcatV1(
            left=parse_hir_expr_v1(raw.get("left")),
            right=parse_hir_expr_v1(raw.get("right")),
        )
    if kind == "eq":
        return HIREqV1(
            left=parse_hir_expr_v1(raw.get("left")),
            right=parse_hir_expr_v1(raw.get("right")),
        )
    if kind == "if":
        return HIRIfExprV1(
            condition=parse_hir_expr_v1(raw.get("condition")),
            then_expr=parse_hir_expr_v1(raw.get("then")),
            else_expr=parse_hir_expr_v1(raw.get("else")),
        )
    raise DiagnosticError(
        diagnostic_from_runtime_error("hir", "unsupported hir expression")
    )


def lower_surface_program_to_hir_v1(program: SurfaceProgramV1) -> HIRProgramV1:
    return HIRProgramV1(
        functions=[lower_surface_function_to_hir_v1(fn) for fn in program.functions],
        statements=[lower_surface_stmt_to_hir_v1(stmt) for stmt in program.statements],
    )


def lower_surface_function_to_hir_v1(fn: SurfaceFunctionV1) -> HIRFunctionV1:
    return HIRFunctionV1(
        name=fn.name,
        params=list(fn.params),
        body=[lower_surface_stmt_to_hir_v1(stmt) for stmt in fn.body],
    )


def lower_surface_stmt_to_hir_v1(stmt: SurfaceStmtV1) -> HIRStmtV1:
    if isinstance(stmt, SurfacePrintStmtV1):
        return HIRPrintStmtV1(expr=lower_surface_expr_to_hir_v1(stmt.expr))
    if isinstance(stmt, SurfaceLetStmtV1):
        return HIRLetStmtV1(name=stmt.name, expr=lower_surface_expr_to_hir_v1(stmt.expr))
    if isinstance(stmt, SurfaceIfStmtV1):
        return HIRIfStmtV1(
            condition=lower_surface_expr_to_hir_v1(stmt.condition),
            then_body=[lower_surface_stmt_to_hir_v1(item) for item in stmt.then_body],
            else_body=[lower_surface_stmt_to_hir_v1(item) for item in stmt.else_body],
        )
    if isinstance(stmt, SurfaceCallStmtV1):
        return HIRCallStmtV1(name=stmt.name, args=[lower_surface_expr_to_hir_v1(arg) for arg in stmt.args])
    raise TypeError(f"unsupported surface stmt: {stmt!r}")


def lower_surface_expr_to_hir_v1(expr: SurfaceExprV1) -> HIRExprV1:
    if isinstance(expr, SurfaceStringV1):
        return HIRStringV1(value=expr.value)
    if isinstance(expr, SurfaceBoolV1):
        return HIRBoolV1(value=expr.value)
    if isinstance(expr, SurfaceVarV1):
        return HIRVarV1(name=expr.name)
    if isinstance(expr, SurfaceConcatV1):
        return HIRConcatV1(
            left=lower_surface_expr_to_hir_v1(expr.left),
            right=lower_surface_expr_to_hir_v1(expr.right),
        )
    if isinstance(expr, SurfaceEqV1):
        return HIREqV1(
            left=lower_surface_expr_to_hir_v1(expr.left),
            right=lower_surface_expr_to_hir_v1(expr.right),
        )
    if isinstance(expr, SurfaceIfExprV1):
        return HIRIfExprV1(
            condition=lower_surface_expr_to_hir_v1(expr.condition),
            then_expr=lower_surface_expr_to_hir_v1(expr.then_expr),
            else_expr=lower_surface_expr_to_hir_v1(expr.else_expr),
        )
    raise TypeError(f"unsupported surface expr: {expr!r}")
