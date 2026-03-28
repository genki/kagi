from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment
from .kir import (
    KIRProgramV0,
    inspect_kir_program as inspect_kir_program_v0,
    kir_program_from_print_artifact,
    kir_program_to_print_artifact,
    serialize_kir_program_v0,
)
from .kir_runtime import execute_kir_program_v0


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
