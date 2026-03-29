from __future__ import annotations

from .diagnostics import Diagnostic, DiagnosticError
from .bootstrap_builders import BOOTSTRAP_BUILTINS
from .lower_subset_to_kir import SUBSET_KIR_BUILTINS, lower_subset_program_to_kir_v0
from .subset_ast import BoolLiteral, Call, Expr, ExprStmt, FunctionDef, IfStmt, IntLiteral, LetStmt, ReturnSignal, ReturnStmt, Stmt, StringLiteral, SubsetProgram, Variable
from .subset_builtins import (
    CORE_BUILTINS,
    intrinsic_after_substring,
    intrinsic_before_substring,
    intrinsic_concat,
    intrinsic_ends_with,
    intrinsic_eq,
    intrinsic_extract_quoted,
    intrinsic_is_identifier,
    intrinsic_line_at,
    intrinsic_line_count,
    intrinsic_starts_with,
    intrinsic_trim,
)
from .subset_typecheck import typecheck_subset_program_v0


BUILTINS = CORE_BUILTINS | BOOTSTRAP_BUILTINS


def execute_kir_entry_v0(program, entry, args, *, builtins=None):
    from .capir_runtime import execute_kir_entry_v0 as execute_shared_kir_entry_v0

    return execute_shared_kir_entry_v0(program, entry=entry, args=args, builtins=builtins)


def run_subset_program(source: str, *, entry: str, args: list[object]) -> object:
    from .subset_parser import parse_subset_program

    program = parse_subset_program(source)
    typecheck_subset_program_v0(program, entry=entry, args=args)
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


def run_subset_program_via_kir(source: str, *, entry: str, args: list[object]) -> object:
    from .subset_parser import parse_subset_program

    program = parse_subset_program(source)
    typecheck_subset_program_v0(program, entry=entry, args=args)
    kir = lower_subset_program_to_kir_v0(program)
    return execute_kir_entry_v0(kir, entry=entry, args=list(args), builtins=SUBSET_KIR_BUILTINS)


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
    env = {param.name: arg for param, arg in zip(fn.params, args)}
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
        if expr.callee == "concat":
            if len(args) != 2:
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-runtime",
                        code="arity_mismatch",
                        message="concat expects 2 arguments",
                        line=None,
                        column=None,
                        snippet=None,
                    )
                )
            return intrinsic_concat(args[0], args[1])
        if expr.callee == "eq":
            if len(args) != 2:
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-runtime",
                        code="arity_mismatch",
                        message="eq expects 2 arguments",
                        line=None,
                        column=None,
                        snippet=None,
                    )
                )
            return intrinsic_eq(args[0], args[1])
        if expr.callee == "trim":
            if len(args) != 1:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="trim expects 1 argument", line=None, column=None, snippet=None))
            return intrinsic_trim(args[0])
        if expr.callee == "starts_with":
            if len(args) != 2:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="starts_with expects 2 arguments", line=None, column=None, snippet=None))
            return intrinsic_starts_with(args[0], args[1])
        if expr.callee == "ends_with":
            if len(args) != 2:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="ends_with expects 2 arguments", line=None, column=None, snippet=None))
            return intrinsic_ends_with(args[0], args[1])
        if expr.callee == "extract_quoted":
            if len(args) != 1:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="extract_quoted expects 1 argument", line=None, column=None, snippet=None))
            return intrinsic_extract_quoted(args[0])
        if expr.callee == "line_count":
            if len(args) != 1:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="line_count expects 1 argument", line=None, column=None, snippet=None))
            return intrinsic_line_count(args[0])
        if expr.callee == "line_at":
            if len(args) != 2:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="line_at expects 2 arguments", line=None, column=None, snippet=None))
            return intrinsic_line_at(args[0], args[1])
        if expr.callee == "before_substring":
            if len(args) != 2:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="before_substring expects 2 arguments", line=None, column=None, snippet=None))
            return intrinsic_before_substring(args[0], args[1])
        if expr.callee == "after_substring":
            if len(args) != 2:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="after_substring expects 2 arguments", line=None, column=None, snippet=None))
            return intrinsic_after_substring(args[0], args[1])
        if expr.callee == "is_identifier":
            if len(args) != 1:
                raise DiagnosticError(Diagnostic(phase="subset-runtime", code="arity_mismatch", message="is_identifier expects 1 argument", line=None, column=None, snippet=None))
            return intrinsic_is_identifier(args[0])
        if expr.callee == "current_program_source":
            if args:
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-runtime",
                        code="arity_mismatch",
                        message="current_program_source expects 0 arguments",
                        line=None,
                        column=None,
                        snippet=None,
                    )
                )
            return str(env.get("source", ""))
        if expr.callee == "current_program_kir":
            if args:
                raise DiagnosticError(
                    Diagnostic(
                        phase="subset-runtime",
                        code="arity_mismatch",
                        message="current_program_kir expects 0 arguments",
                        line=None,
                        column=None,
                        snippet=None,
                    )
                )
            return ""
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
