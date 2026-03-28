from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .hir import HIRBoolV1, HIRConcatV1, HIREqV1, HIRExprV1, HIRFunctionV1, HIRIfExprV1, HIRIfStmtV1, HIRLetStmtV1, HIRPrintStmtV1, HIRProgramV1, HIRStmtV1, HIRStringV1, HIRVarV1
from .resolve import ResolvedProgramV1


@dataclass(frozen=True)
class TypecheckedProgramV1:
    program: HIRProgramV1


def typecheck_program_v1(resolved: ResolvedProgramV1) -> TypecheckedProgramV1:
    for fn in resolved.program.functions:
        typecheck_stmt_block_v1(fn.body, {param: "string" for param in fn.params})
    typecheck_stmt_block_v1(resolved.program.statements, {})
    return TypecheckedProgramV1(program=resolved.program)


def typecheck_stmt_block_v1(body: list[HIRStmtV1], env: dict[str, str]) -> None:
    local_env = dict(env)
    for stmt in body:
        if isinstance(stmt, HIRLetStmtV1):
            local_env[stmt.name] = typecheck_expr_v1(stmt.expr, local_env)
            continue
        if isinstance(stmt, HIRPrintStmtV1):
            expr_type = typecheck_expr_v1(stmt.expr, local_env)
            if expr_type != "string":
                raise DiagnosticError(
                    diagnostic_from_runtime_error("typecheck", "print requires string expression")
                )
            continue
        if isinstance(stmt, HIRIfStmtV1):
            condition_type = typecheck_expr_v1(stmt.condition, local_env)
            if condition_type != "bool":
                raise DiagnosticError(
                    diagnostic_from_runtime_error("typecheck", "if statement requires boolean condition")
                )
            typecheck_stmt_block_v1(stmt.then_body, dict(local_env))
            typecheck_stmt_block_v1(stmt.else_body, dict(local_env))
            continue
        from .hir import HIRCallStmtV1
        if isinstance(stmt, HIRCallStmtV1):
            for arg in stmt.args:
                typecheck_expr_v1(arg, local_env)
            continue
        raise DiagnosticError(
            diagnostic_from_runtime_error("typecheck", "unsupported statement during typecheck")
        )


def typecheck_expr_v1(expr: HIRExprV1, env: dict[str, str]) -> str:
    if isinstance(expr, HIRStringV1):
        return "string"
    if isinstance(expr, HIRBoolV1):
        return "bool"
    if isinstance(expr, HIRVarV1):
        if expr.name not in env:
            raise DiagnosticError(
                diagnostic_from_runtime_error("typecheck", f"unknown variable: {expr.name}")
            )
        return env[expr.name]
    if isinstance(expr, HIRConcatV1):
        left = typecheck_expr_v1(expr.left, env)
        right = typecheck_expr_v1(expr.right, env)
        if left != "string" or right != "string":
            raise DiagnosticError(
                diagnostic_from_runtime_error("typecheck", "concat requires string operands")
            )
        return "string"
    if isinstance(expr, HIREqV1):
        left = typecheck_expr_v1(expr.left, env)
        right = typecheck_expr_v1(expr.right, env)
        if left != right:
            raise DiagnosticError(
                diagnostic_from_runtime_error("typecheck", "eq requires matching operand types")
            )
        return "bool"
    if isinstance(expr, HIRIfExprV1):
        condition = typecheck_expr_v1(expr.condition, env)
        if condition != "bool":
            raise DiagnosticError(
                diagnostic_from_runtime_error("typecheck", "if expression requires boolean condition")
            )
        then_type = typecheck_expr_v1(expr.then_expr, env)
        else_type = typecheck_expr_v1(expr.else_expr, env)
        if then_type != else_type:
            raise DiagnosticError(
                diagnostic_from_runtime_error("typecheck", "if expression branches must match")
            )
        return then_type
    raise DiagnosticError(
        diagnostic_from_runtime_error("typecheck", "unsupported expression during typecheck")
    )
