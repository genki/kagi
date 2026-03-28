from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .hir import HIRCallStmtV1, HIRConcatV1, HIREqV1, HIRExprV1, HIRFunctionV1, HIRIfExprV1, HIRIfStmtV1, HIRLetStmtV1, HIRPrintStmtV1, HIRProgramV1, HIRStmtV1, HIRVarV1


@dataclass(frozen=True)
class ResolvedProgramV1:
    program: HIRProgramV1
    function_arities: dict[str, int]


def resolve_hir_program_v1(program: HIRProgramV1) -> ResolvedProgramV1:
    function_arities: dict[str, int] = {}
    for fn in program.functions:
        if fn.name in function_arities:
            raise DiagnosticError(
                diagnostic_from_runtime_error("resolve", f"duplicate function: {fn.name}")
            )
        function_arities[fn.name] = len(fn.params)
    for fn in program.functions:
        resolve_stmt_block_v1(fn.body, set(fn.params), function_arities)
    resolve_stmt_block_v1(program.statements, set(), function_arities)
    return ResolvedProgramV1(program=program, function_arities=function_arities)


def resolve_stmt_block_v1(body: list[HIRStmtV1], scope: set[str], function_arities: dict[str, int]) -> None:
    local_scope = set(scope)
    for stmt in body:
        if isinstance(stmt, HIRLetStmtV1):
            resolve_expr_v1(stmt.expr, local_scope, function_arities)
            local_scope.add(stmt.name)
            continue
        if isinstance(stmt, HIRPrintStmtV1):
            resolve_expr_v1(stmt.expr, local_scope, function_arities)
            continue
        if isinstance(stmt, HIRIfStmtV1):
            resolve_expr_v1(stmt.condition, local_scope, function_arities)
            resolve_stmt_block_v1(stmt.then_body, set(local_scope), function_arities)
            resolve_stmt_block_v1(stmt.else_body, set(local_scope), function_arities)
            continue
        if isinstance(stmt, HIRCallStmtV1):
            if stmt.name not in function_arities:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("resolve", f"unknown function: {stmt.name}")
                )
            if len(stmt.args) != function_arities[stmt.name]:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("resolve", f"arity mismatch for function: {stmt.name}")
                )
            for arg in stmt.args:
                resolve_expr_v1(arg, local_scope, function_arities)
            continue
        raise DiagnosticError(
            diagnostic_from_runtime_error("resolve", "unsupported statement during resolution")
        )


def resolve_expr_v1(expr: HIRExprV1, scope: set[str], function_arities: dict[str, int]) -> None:
    if isinstance(expr, HIRVarV1):
        if expr.name not in scope:
            raise DiagnosticError(
                diagnostic_from_runtime_error("resolve", f"unknown variable: {expr.name}")
            )
        return
    if isinstance(expr, HIRConcatV1):
        resolve_expr_v1(expr.left, scope, function_arities)
        resolve_expr_v1(expr.right, scope, function_arities)
        return
    if isinstance(expr, HIREqV1):
        resolve_expr_v1(expr.left, scope, function_arities)
        resolve_expr_v1(expr.right, scope, function_arities)
        return
    if isinstance(expr, HIRIfExprV1):
        resolve_expr_v1(expr.condition, scope, function_arities)
        resolve_expr_v1(expr.then_expr, scope, function_arities)
        resolve_expr_v1(expr.else_expr, scope, function_arities)
        return
