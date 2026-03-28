from __future__ import annotations

from .bootstrap_builders import BOOTSTRAP_BUILTINS
from .kir import (
    KIRBoolV0,
    KIRCallExprV0,
    KIRConcatV0,
    KIREqV0,
    KIRExprStmtV0,
    KIRExprV0,
    KIRFunctionV0,
    KIRIfStmtV0,
    KIRIntV0,
    KIRLetV0,
    KIRProgramV0,
    KIRReturnV0,
    KIRStmtV0,
    KIRStringV0,
    KIRVarV0,
)
from .subset_builtins import CORE_BUILTINS
from .subset_ast import BoolLiteral, Call, Expr, ExprStmt, FunctionDef, IfStmt, IntLiteral, LetStmt, ReturnStmt, StringLiteral, SubsetProgram, Variable


SUBSET_KIR_BUILTINS = CORE_BUILTINS | BOOTSTRAP_BUILTINS


def execute_kir_entry_v0(program, entry, args, *, builtins=None):
    from .capir_runtime import execute_kir_entry_fast_v0
    from .kir_runtime import execute_kir_entry_v0 as execute_host_kir_entry_v0

    fast = execute_kir_entry_fast_v0(program, entry=entry, args=args, builtins=builtins)
    if fast is not None:
        return fast
    return execute_host_kir_entry_v0(program, entry=entry, args=args, builtins=builtins)


def lower_subset_program_to_kir_v0(program: SubsetProgram) -> KIRProgramV0:
    return KIRProgramV0(
        instructions=[],
        functions=[lower_subset_function_to_kir_v0(fn) for fn in program.functions],
    )


def lower_subset_function_to_kir_v0(fn: FunctionDef) -> KIRFunctionV0:
    return KIRFunctionV0(
        name=fn.name,
        params=[param.name for param in fn.params],
        body=[lower_subset_stmt_to_kir_v0(stmt) for stmt in fn.body],
    )


def lower_subset_stmt_to_kir_v0(stmt: object) -> KIRStmtV0:
    if isinstance(stmt, LetStmt):
        return KIRLetV0(name=stmt.name, expr=lower_subset_expr_to_kir_v0(stmt.expr))
    if isinstance(stmt, ReturnStmt):
        return KIRReturnV0(expr=lower_subset_expr_to_kir_v0(stmt.expr))
    if isinstance(stmt, IfStmt):
        return KIRIfStmtV0(
            condition=lower_subset_expr_to_kir_v0(stmt.condition),
            then_body=[lower_subset_stmt_to_kir_v0(item) for item in stmt.then_body],
            else_body=[lower_subset_stmt_to_kir_v0(item) for item in stmt.else_body],
        )
    if isinstance(stmt, ExprStmt):
        expr = lower_subset_expr_to_kir_v0(stmt.expr)
        if isinstance(expr, KIRCallExprV0):
            return KIRExprStmtV0(expr=expr)
        return KIRExprStmtV0(expr=expr)
    raise TypeError(f"unsupported subset stmt: {stmt!r}")


def lower_subset_expr_to_kir_v0(expr: Expr) -> KIRExprV0:
    if isinstance(expr, StringLiteral):
        return KIRStringV0(value=expr.value)
    if isinstance(expr, BoolLiteral):
        return KIRBoolV0(value=expr.value)
    if isinstance(expr, IntLiteral):
        return KIRIntV0(value=expr.value)
    if isinstance(expr, Variable):
        return KIRVarV0(name=expr.name)
    if isinstance(expr, Call):
        if expr.callee == "concat" and len(expr.args) == 2:
            return KIRConcatV0(
                left=lower_subset_expr_to_kir_v0(expr.args[0]),
                right=lower_subset_expr_to_kir_v0(expr.args[1]),
            )
        if expr.callee == "eq" and len(expr.args) == 2:
            return KIREqV0(
                left=lower_subset_expr_to_kir_v0(expr.args[0]),
                right=lower_subset_expr_to_kir_v0(expr.args[1]),
            )
        return KIRCallExprV0(callee=expr.callee, args=[lower_subset_expr_to_kir_v0(arg) for arg in expr.args])
    raise TypeError(f"unsupported subset expr: {expr!r}")


def execute_subset_entry_via_kir_v0(source: str, *, entry: str, args: list[object]) -> object:
    from .subset_parser import parse_subset_program

    program = lower_subset_program_to_kir_v0(parse_subset_program(source))
    return execute_kir_entry_v0(program, entry, list(args), builtins=SUBSET_KIR_BUILTINS)
