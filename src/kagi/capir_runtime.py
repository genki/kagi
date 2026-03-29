from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment
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
    inspect_kir_program as inspect_kir_program_v0,
    kir_program_from_print_artifact,
    kir_program_to_print_artifact,
    serialize_kir_program_v0,
)


@dataclass(frozen=True)
class CapIRExecutionResult:
    output: str


@dataclass(frozen=True)
class CapIRArtifactResult:
    capir: dict[str, object]
    output: str


@dataclass(frozen=True)
class KIRExecutionResult:
    output: str


@dataclass(frozen=True)
class KIRExecutionContextV0:
    current_program_source: str | None = None
    current_program_kir: str | None = None


_UNHANDLED = object()


class _LocalReturnSignal(Exception):
    def __init__(self, value: object):
        super().__init__()
        self.value = value


def execute_kir_program_v0(program: KIRProgramV0, *, builtins=None):
    closed = _try_execute_kir_program_locally_v0(program, builtins=builtins)
    if closed is not None:
        return closed
    from .kir_runtime import execute_kir_program_v0 as execute_host_kir_program_v0

    if builtins is None:
        return execute_host_kir_program_v0(program)
    return execute_host_kir_program_v0(program, builtins=builtins)


def _call_local_function_v0(
    functions: dict[str, KIRFunctionV0],
    name: str,
    args: list[object],
    output: list[str],
    builtins: dict[str, object],
    context: KIRExecutionContextV0 | None = None,
):
    if name == "current_program_source":
        if args:
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "current_program_source takes no arguments")
            )
        if context is None or context.current_program_source is None:
            return _UNHANDLED
        return context.current_program_source
    if name == "current_program_kir":
        if args:
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "current_program_kir takes no arguments")
            )
        if context is None or context.current_program_kir is None:
            return _UNHANDLED
        return context.current_program_kir
    if name in builtins:
        return _UNHANDLED
    fn = functions.get(name)
    if fn is None:
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", f"unknown function: {name}")
        )
    if len(args) != len(fn.params):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", f"arity mismatch for function: {fn.name}")
        )
    env = dict(zip(fn.params, args))
    try:
        handled = _run_local_block_v0(fn.body, env, output, functions, builtins, context=context)
    except _LocalReturnSignal as signal:
        return signal.value
    if not handled:
        return _UNHANDLED
    return None


def _eval_local_expr_v0(
    expr: KIRExprV0,
    env: dict[str, object],
    output: list[str],
    functions: dict[str, KIRFunctionV0],
    builtins: dict[str, object],
    context: KIRExecutionContextV0 | None = None,
):
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
        left = _eval_local_expr_v0(expr.left, env, output, functions, builtins, context=context)
        right = _eval_local_expr_v0(expr.right, env, output, functions, builtins, context=context)
        if left is _UNHANDLED or right is _UNHANDLED:
            return _UNHANDLED
        if not isinstance(left, str) or not isinstance(right, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "concat requires string operands")
            )
        return left + right
    if isinstance(expr, KIREqV0):
        left = _eval_local_expr_v0(expr.left, env, output, functions, builtins, context=context)
        right = _eval_local_expr_v0(expr.right, env, output, functions, builtins, context=context)
        if left is _UNHANDLED or right is _UNHANDLED:
            return _UNHANDLED
        if type(left) is not type(right):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "eq requires matching operand types")
            )
        return left == right
    if isinstance(expr, KIRIfExprV0):
        condition = _eval_local_expr_v0(expr.condition, env, output, functions, builtins, context=context)
        if condition is _UNHANDLED:
            return _UNHANDLED
        if not isinstance(condition, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
            )
        return _eval_local_expr_v0(expr.then_expr if condition else expr.else_expr, env, output, functions, builtins, context=context)
    if isinstance(expr, KIRCallExprV0):
        call_args: list[object] = []
        for arg in expr.args:
            value = _eval_local_expr_v0(arg, env, output, functions, builtins, context=context)
            if value is _UNHANDLED:
                return _UNHANDLED
            call_args.append(value)
        return _call_local_function_v0(functions, expr.callee, call_args, output, builtins, context=context)
    return _UNHANDLED


def _run_local_block_v0(
    body: list[object],
    env: dict[str, object],
    output: list[str],
    functions: dict[str, KIRFunctionV0],
    builtins: dict[str, object],
    context: KIRExecutionContextV0 | None = None,
) -> bool:
    for stmt in body:
        if isinstance(stmt, KIRPrintV0):
            value = _eval_local_expr_v0(stmt.expr, env, output, functions, builtins, context=context)
            if value is _UNHANDLED:
                return False
            if not isinstance(value, str):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "print requires string expression")
                )
            output.append(value)
            continue
        if isinstance(stmt, KIRLetV0):
            value = _eval_local_expr_v0(stmt.expr, env, output, functions, builtins, context=context)
            if value is _UNHANDLED:
                return False
            env[stmt.name] = value
            continue
        if isinstance(stmt, KIRIfStmtV0):
            condition = _eval_local_expr_v0(stmt.condition, env, output, functions, builtins, context=context)
            if condition is _UNHANDLED:
                return False
            if not isinstance(condition, bool):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir-runtime", "if requires boolean condition")
                )
            if not _run_local_block_v0(stmt.then_body if condition else stmt.else_body, dict(env), output, functions, builtins, context=context):
                return False
            continue
        if isinstance(stmt, KIRExprStmtV0):
            value = _eval_local_expr_v0(stmt.expr, env, output, functions, builtins, context=context)
            if value is _UNHANDLED:
                return False
            continue
        if isinstance(stmt, KIRCallV0):
            call_args: list[object] = []
            for arg in stmt.args:
                value = _eval_local_expr_v0(arg, env, output, functions, builtins, context=context)
                if value is _UNHANDLED:
                    return False
                call_args.append(value)
            result = _call_local_function_v0(functions, stmt.name, call_args, output, builtins, context=context)
            if result is _UNHANDLED:
                return False
            continue
        if isinstance(stmt, KIRReturnV0):
            value = _eval_local_expr_v0(stmt.expr, env, output, functions, builtins, context=context)
            if value is _UNHANDLED:
                return False
            raise _LocalReturnSignal(value)
        return False
    return True


def _try_execute_kir_program_locally_v0(program: KIRProgramV0, *, builtins=None, context: KIRExecutionContextV0 | None = None):
    output: list[str] = []
    try:
        ok = _run_local_block_v0(
            program.instructions,
            {},
            output,
            {fn.name: fn for fn in program.functions},
            dict(builtins or {}),
            context=context,
        )
    except DiagnosticError:
        raise
    except Exception:
        return None
    if ok:
        return KIRExecutionResult(output="\n".join(output))
    return None


def try_execute_kir_program_fast_v0(program: KIRProgramV0, *, builtins=None, context: KIRExecutionContextV0 | None = None):
    return _try_execute_kir_program_locally_v0(program, builtins=builtins, context=context)


def execute_kir_entry_fast_v0(
    program: KIRProgramV0,
    entry: str,
    args: list[object],
    *,
    builtins=None,
    context: KIRExecutionContextV0 | None = None,
):
    functions = {fn.name: fn for fn in program.functions}
    if entry not in functions:
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", f"unknown entry function: {entry}")
        )
    output: list[str] = []
    try:
        result = _call_local_function_v0(functions, entry, list(args), output, dict(builtins or {}), context=context)
    except DiagnosticError:
        raise
    except Exception:
        return None
    if result is _UNHANDLED:
        return None
    return result


def inspect_capir_artifact(artifact: object) -> dict[str, object]:
    return inspect_capir_fragment(capir_fragment_from_artifact(artifact))


def inspect_capir_fragment(fragment: CapIRFragment) -> dict[str, object]:
    return {
        "effect": fragment.effect,
        "ops": [{"text": op.text} for op in fragment.ops],
        "serialized": serialize_capir_fragment(fragment),
    }


def execute_and_inspect_capir_artifact(artifact: object) -> CapIRArtifactResult:
    fragment = capir_fragment_from_artifact(artifact)
    return CapIRArtifactResult(
        capir=inspect_capir_fragment(fragment),
        output=execute_capir_fragment(fragment).output,
    )


def capir_fragment_from_artifact(artifact: object) -> CapIRFragment:
    return capir_fragment_from_kir_program(kir_program_from_artifact(artifact))


def kir_program_from_artifact(artifact: object) -> KIRProgramV0:
    parsed = parse_artifact_v1(artifact)
    if not isinstance(parsed, PrintArtifactV1):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", "unsupported artifact payload")
        )
    return kir_program_from_print_artifact(parsed)


def inspect_kir_artifact(artifact: object) -> dict[str, object]:
    if isinstance(artifact, KIRProgramV0):
        program = artifact
    else:
        program = kir_program_from_artifact(artifact)
    payload = inspect_kir_program_v0(program)
    payload["serialized"] = serialize_kir_program_v0(program)
    try:
        payload["stdout"] = artifact_v1_stdout(kir_program_to_artifact(program))
    except DiagnosticError:
        payload["stdout"] = execute_kir_program_v0(program).output
    return payload


def inspect_kir_program(program: KIRProgramV0) -> dict[str, object]:
    payload = inspect_kir_artifact(program)
    payload.pop("serialized", None)
    payload.pop("stdout", None)
    return payload


def kir_program_to_artifact(program: KIRProgramV0) -> PrintArtifactV1:
    return kir_program_to_print_artifact(program)


def capir_fragment_from_kir_program(program: KIRProgramV0) -> CapIRFragment:
    artifact = kir_program_to_artifact(program)
    return CapIRFragment(effect="print", ops=[CapIRPrint(text=text) for text in artifact.texts])


def execute_kir_program(program: KIRProgramV0) -> KIRExecutionResult:
    try:
        return KIRExecutionResult(output=artifact_v1_stdout(kir_program_to_artifact(program)))
    except DiagnosticError:
        closed = _try_execute_kir_program_locally_v0(program)
        if closed is not None:
            return KIRExecutionResult(output=closed.output)
        return KIRExecutionResult(output=execute_kir_program_v0(program).output)


def execute_capir_artifact(artifact: object) -> CapIRExecutionResult:
    parsed = parse_artifact_v1(artifact)
    return CapIRExecutionResult(output=artifact_v1_stdout(parsed))


def execute_capir_fragment(fragment: CapIRFragment) -> CapIRExecutionResult:
    if fragment.effect != "print":
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", f"unsupported effect: {fragment.effect}")
        )
    artifact = PrintArtifactV1(texts=[op.text for op in fragment.ops])
    return CapIRExecutionResult(output=artifact_v1_stdout(artifact))
