from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .artifact import artifact_v1_stdout
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .kir import (
    KIRBoolV0,
    KIRCallExprV0,
    KIRCallV0,
    KIRConcatV0,
    KIREqV0,
    KIRExprStmtV0,
    KIRExprV0,
    KIRFunctionV0,
    KIRIfExprV0,
    KIRIfStmtV0,
    KIRIntV0,
    KIRLetV0,
    KIRPrintV0,
    KIRProgramV0,
    KIRReturnV0,
    KIRStringV0,
    KIRVarV0,
    kir_program_to_print_artifact,
)


BuiltinFuncV0 = Callable[..., Any]


@dataclass(frozen=True)
class KIRExecutionResultV0:
    output: str


class _ReturnSignal(Exception):
    def __init__(self, value: Any):
        super().__init__()
        self.value = value


def execute_kir_program_v0(
    program: KIRProgramV0,
    *,
    builtins: dict[str, BuiltinFuncV0] | None = None,
) -> KIRExecutionResultV0:
    fast_path = _try_execute_print_only_program_v0(program)
    if fast_path is not None:
        return fast_path
    return _execute_generic_kir_program_v0(program, builtins=builtins)


def _try_execute_print_only_program_v0(program: KIRProgramV0) -> KIRExecutionResultV0 | None:
    try:
        artifact = kir_program_to_print_artifact(program)
    except DiagnosticError:
        return None
    return KIRExecutionResultV0(output=artifact_v1_stdout(artifact))


def _execute_generic_kir_program_v0(
    program: KIRProgramV0,
    *,
    builtins: dict[str, BuiltinFuncV0] | None = None,
) -> KIRExecutionResultV0:
    functions = {fn.name: fn for fn in program.functions}
    output_parts: list[str] = []
    runtime_builtins = dict(builtins or {})

    def eval_expr(expr: KIRExprV0, env: dict[str, Any]) -> Any:
        if isinstance(expr, KIRStringV0):
            return expr.value
        if isinstance(expr, KIRBoolV0):
            return expr.value
        if isinstance(expr, KIRIntV0):
            return expr.value
        if isinstance(expr, KIRVarV0):
            if expr.name not in env:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", f"unknown variable: {expr.name}")
                )
            return env[expr.name]
        if isinstance(expr, KIRConcatV0):
            left = eval_expr(expr.left, env)
            right = eval_expr(expr.right, env)
            if not isinstance(left, str) or not isinstance(right, str):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "concat requires string operands")
                )
            return left + right
        if isinstance(expr, KIREqV0):
            left = eval_expr(expr.left, env)
            right = eval_expr(expr.right, env)
            if type(left) is not type(right):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "eq requires matching operand types")
                )
            return left == right
        if isinstance(expr, KIRIfExprV0):
            condition = eval_expr(expr.condition, env)
            if not isinstance(condition, bool):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
                )
            return eval_expr(expr.then_expr if condition else expr.else_expr, env)
        if isinstance(expr, KIRCallExprV0):
            call_args = [eval_expr(arg, env) for arg in expr.args]
            return call_named(expr.callee, call_args)
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", "unsupported expression")
        )

    def append_output(text: str) -> None:
        if output_parts:
            output_parts.append("\n")
        output_parts.append(text)

    def call_named(name: str, args: list[Any]) -> Any:
        if name in runtime_builtins:
            return runtime_builtins[name](*args)
        if name not in functions:
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", f"unknown function: {name}")
            )
        return run_function(functions[name], args)

    def run_function(fn: KIRFunctionV0, args: list[Any]) -> Any:
        if len(args) != len(fn.params):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", f"arity mismatch for function: {fn.name}")
            )
        env = dict(zip(fn.params, args))
        try:
            run_block(fn.body, env)
        except _ReturnSignal as signal:
            return signal.value
        return None

    def run_block(body: list[Any], env: dict[str, Any]) -> None:
        for stmt in body:
            if isinstance(stmt, KIRPrintV0):
                value = eval_expr(stmt.expr, env)
                if not isinstance(value, str):
                    raise DiagnosticError(
                        diagnostic_from_runtime_error("kir-runtime", "print requires string expression")
                    )
                append_output(value)
                continue
            if isinstance(stmt, KIRLetV0):
                env[stmt.name] = eval_expr(stmt.expr, env)
                continue
            if isinstance(stmt, KIRIfStmtV0):
                condition = eval_expr(stmt.condition, env)
                if not isinstance(condition, bool):
                    raise DiagnosticError(
                        diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
                    )
                run_block(stmt.then_body if condition else stmt.else_body, dict(env))
                continue
            if isinstance(stmt, KIRCallV0):
                call_args = [eval_expr(arg, env) for arg in stmt.args]
                call_named(stmt.name, call_args)
                continue
            if isinstance(stmt, KIRReturnV0):
                raise _ReturnSignal(eval_expr(stmt.expr, env))
            if isinstance(stmt, KIRExprStmtV0):
                eval_expr(stmt.expr, env)
                continue
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "unsupported statement")
            )

    run_block(program.instructions, {})
    return KIRExecutionResultV0(output="".join(output_parts))


def execute_kir_entry_v0(
    program: KIRProgramV0,
    entry: str,
    args: list[Any],
    *,
    builtins: dict[str, BuiltinFuncV0] | None = None,
) -> Any:
    functions = {fn.name: fn for fn in program.functions}
    if entry not in functions:
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", f"unknown entry function: {entry}")
        )
    runtime_builtins = dict(builtins or {})

    def eval_expr(expr: KIRExprV0, env: dict[str, Any]) -> Any:
        if isinstance(expr, KIRStringV0):
            return expr.value
        if isinstance(expr, KIRBoolV0):
            return expr.value
        if isinstance(expr, KIRIntV0):
            return expr.value
        if isinstance(expr, KIRVarV0):
            if expr.name not in env:
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", f"unknown variable: {expr.name}")
                )
            return env[expr.name]
        if isinstance(expr, KIRConcatV0):
            left = eval_expr(expr.left, env)
            right = eval_expr(expr.right, env)
            if not isinstance(left, str) or not isinstance(right, str):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "concat requires string operands")
                )
            return left + right
        if isinstance(expr, KIREqV0):
            left = eval_expr(expr.left, env)
            right = eval_expr(expr.right, env)
            if type(left) is not type(right):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "eq requires matching operand types")
                )
            return left == right
        if isinstance(expr, KIRIfExprV0):
            condition = eval_expr(expr.condition, env)
            if not isinstance(condition, bool):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
                )
            return eval_expr(expr.then_expr if condition else expr.else_expr, env)
        if isinstance(expr, KIRCallExprV0):
            call_args = [eval_expr(arg, env) for arg in expr.args]
            return call_named(expr.callee, call_args)
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", "unsupported expression")
        )

    def call_named(name: str, call_args: list[Any]) -> Any:
        if name in runtime_builtins:
            return runtime_builtins[name](*call_args)
        if name not in functions:
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", f"unknown function: {name}")
            )
        return run_function(functions[name], call_args)

    def run_block(body: list[Any], env: dict[str, Any]) -> None:
        for stmt in body:
            if isinstance(stmt, KIRPrintV0):
                eval_expr(stmt.expr, env)
                continue
            if isinstance(stmt, KIRLetV0):
                env[stmt.name] = eval_expr(stmt.expr, env)
                continue
            if isinstance(stmt, KIRIfStmtV0):
                condition = eval_expr(stmt.condition, env)
                if not isinstance(condition, bool):
                    raise DiagnosticError(
                        diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
                    )
                run_block(stmt.then_body if condition else stmt.else_body, dict(env))
                continue
            if isinstance(stmt, KIRCallV0):
                call_named(stmt.name, [eval_expr(arg, env) for arg in stmt.args])
                continue
            if isinstance(stmt, KIRReturnV0):
                raise _ReturnSignal(eval_expr(stmt.expr, env))
            if isinstance(stmt, KIRExprStmtV0):
                eval_expr(stmt.expr, env)
                continue
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "unsupported statement")
            )

    def run_function(fn: KIRFunctionV0, call_args: list[Any]) -> Any:
        if len(call_args) != len(fn.params):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", f"arity mismatch for function: {fn.name}")
            )
        env = dict(zip(fn.params, call_args))
        try:
            run_block(fn.body, env)
        except _ReturnSignal as signal:
            return signal.value
        return None

    return run_function(functions[entry], args)
