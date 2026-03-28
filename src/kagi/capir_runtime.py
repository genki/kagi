from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment
from .kir import (
    KIRBoolV0,
    KIRConcatV0,
    KIREqV0,
    KIRExprStmtV0,
    KIRExprV0,
    KIRIfExprV0,
    KIRIfStmtV0,
    KIRIntV0,
    KIRLetV0,
    KIRPrintV0,
    KIRProgramV0,
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


def execute_kir_program_v0(program: KIRProgramV0, *, builtins=None):
    closed = _try_execute_closed_kir_program_v0(program)
    if closed is not None:
        return closed
    from .kir_runtime import execute_kir_program_v0 as execute_host_kir_program_v0

    if builtins is None:
        return execute_host_kir_program_v0(program)
    return execute_host_kir_program_v0(program, builtins=builtins)


def _try_execute_closed_kir_program_v0(program: KIRProgramV0):
    if program.functions:
        return None

    def eval_expr(expr: KIRExprV0, env: dict[str, object]) -> object:
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
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", "closed KIR fast path does not support calls")
        )

    def run_block(body: list[object], env: dict[str, object], output: list[str]) -> bool:
        for stmt in body:
            if isinstance(stmt, KIRPrintV0):
                value = eval_expr(stmt.expr, env)
                if not isinstance(value, str):
                    raise DiagnosticError(
                        diagnostic_from_runtime_error("kir-runtime", "print requires string expression")
                    )
                output.append(value)
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
                run_block(stmt.then_body if condition else stmt.else_body, dict(env), output)
                continue
            if isinstance(stmt, KIRExprStmtV0):
                eval_expr(stmt.expr, env)
                continue
            return False
        return True

    output: list[str] = []
    env: dict[str, object] = {}
    try:
        ok = run_block(program.instructions, env, output)
    except DiagnosticError:
        raise
    except Exception:
        return None
    if ok:
        return KIRExecutionResult(output="\n".join(output))
    return None


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
        closed = _try_execute_closed_kir_program_v0(program)
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
