from __future__ import annotations

from .hir import (
    HIRBoolV1,
    HIRCallStmtV1,
    HIRConcatV1,
    HIREqV1,
    HIRExprV1,
    HIRFunctionV1,
    HIRIfExprV1,
    HIRIfStmtV1,
    HIRLetStmtV1,
    HIRPrintStmtV1,
    HIRProgramV1,
    HIRStmtV1,
    HIRStringV1,
    HIRVarV1,
)
from .kir import (
    KIRBoolV0,
    KIRCallV0,
    KIRConcatV0,
    KIREqV0,
    KIRExprV0,
    KIRFunctionV0,
    KIRIfExprV0,
    KIRIfStmtV0,
    KIRLetV0,
    KIRPrintV0,
    KIRProgramV0,
    KIRStmtV0,
    KIRStringV0,
    KIRVarV0,
)


def lower_hir_program_to_kir_v0(program: HIRProgramV1) -> KIRProgramV0:
    return KIRProgramV0(
        instructions=[lower_hir_stmt_to_kir_v0(stmt) for stmt in program.statements],
        functions=[lower_hir_function_to_kir_v0(fn) for fn in program.functions],
    )


def lower_hir_function_to_kir_v0(fn: HIRFunctionV1) -> KIRFunctionV0:
    return KIRFunctionV0(
        name=fn.name,
        params=list(fn.params),
        body=[lower_hir_stmt_to_kir_v0(stmt) for stmt in fn.body],
    )


def lower_hir_stmt_to_kir_v0(stmt: HIRStmtV1) -> KIRStmtV0:
    if isinstance(stmt, HIRPrintStmtV1):
        return KIRPrintV0(expr=lower_hir_expr_to_kir_v0(stmt.expr))
    if isinstance(stmt, HIRLetStmtV1):
        return KIRLetV0(name=stmt.name, expr=lower_hir_expr_to_kir_v0(stmt.expr))
    if isinstance(stmt, HIRIfStmtV1):
        return KIRIfStmtV0(
            condition=lower_hir_expr_to_kir_v0(stmt.condition),
            then_body=[lower_hir_stmt_to_kir_v0(item) for item in stmt.then_body],
            else_body=[lower_hir_stmt_to_kir_v0(item) for item in stmt.else_body],
        )
    if isinstance(stmt, HIRCallStmtV1):
        return KIRCallV0(name=stmt.name, args=[lower_hir_expr_to_kir_v0(arg) for arg in stmt.args])
    raise TypeError(f"unsupported hir stmt: {stmt!r}")


def lower_hir_expr_to_kir_v0(expr: HIRExprV1) -> KIRExprV0:
    if isinstance(expr, HIRStringV1):
        return KIRStringV0(value=expr.value)
    if isinstance(expr, HIRBoolV1):
        return KIRBoolV0(value=expr.value)
    if isinstance(expr, HIRVarV1):
        return KIRVarV0(name=expr.name)
    if isinstance(expr, HIRConcatV1):
        return KIRConcatV0(
            left=lower_hir_expr_to_kir_v0(expr.left),
            right=lower_hir_expr_to_kir_v0(expr.right),
        )
    if isinstance(expr, HIREqV1):
        return KIREqV0(
            left=lower_hir_expr_to_kir_v0(expr.left),
            right=lower_hir_expr_to_kir_v0(expr.right),
        )
    if isinstance(expr, HIRIfExprV1):
        return KIRIfExprV0(
            condition=lower_hir_expr_to_kir_v0(expr.condition),
            then_expr=lower_hir_expr_to_kir_v0(expr.then_expr),
            else_expr=lower_hir_expr_to_kir_v0(expr.else_expr),
        )
    raise TypeError(f"unsupported hir expr: {expr!r}")
