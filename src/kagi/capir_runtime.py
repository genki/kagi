from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment
from .kir import KIRPrintV0, KIRProgramV0, inspect_kir_artifact, serialize_kir_program_v0
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
    parsed = parse_artifact_v1(artifact)
    if not isinstance(parsed, PrintArtifactV1):
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", "unsupported artifact payload")
        )
    return capir_fragment_from_kir_program(kir_program_from_artifact(artifact))


def kir_program_from_artifact(artifact: object) -> KIRProgramV0:
    parsed = parse_artifact_v1(artifact)
    if not isinstance(parsed, PrintArtifactV1):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir-runtime", "unsupported artifact payload")
        )
    return KIRProgramV0(instructions=[KIRPrintV0(text=text) for text in parsed.texts])


def inspect_kir_artifact(artifact: object) -> dict[str, object]:
    if isinstance(artifact, KIRProgramV0):
        program = artifact
    else:
        program = kir_program_from_artifact(artifact)
    return {
        "kind": "kir",
        "effect": "print",
        "instructions": [{"op": "print", "text": instr.text} for instr in program.instructions],
        "serialized": serialize_kir_program_v0(program),
        "stdout": execute_kir_program_v0(program).output,
    }


def inspect_kir_program(program: KIRProgramV0) -> dict[str, object]:
    return inspect_kir_artifact(program)


def kir_program_to_artifact(program: KIRProgramV0) -> PrintArtifactV1:
    return PrintArtifactV1(texts=[instruction.text for instruction in program.instructions])


def capir_fragment_from_kir_program(program: KIRProgramV0) -> CapIRFragment:
    return CapIRFragment(effect="print", ops=[CapIRPrint(text=instr.text) for instr in program.instructions])


def execute_kir_program(program: KIRProgramV0) -> KIRExecutionResult:
    return KIRExecutionResult(output=execute_kir_program_v0(program).output)


def execute_capir_artifact(artifact: object) -> CapIRExecutionResult:
    return CapIRExecutionResult(output=execute_kir_program_v0(kir_program_from_artifact(artifact)).output)


def execute_capir_fragment(fragment: CapIRFragment) -> CapIRExecutionResult:
    if fragment.effect != "print":
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", f"unsupported effect: {fragment.effect}")
        )
    program = KIRProgramV0(instructions=[KIRPrintV0(text=op.text) for op in fragment.ops])
    return CapIRExecutionResult(output=execute_kir_program_v0(program).output)
