from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment


@dataclass(frozen=True)
class CapIRExecutionResult:
    output: str


@dataclass(frozen=True)
class CapIRArtifactResult:
    capir: dict[str, object]
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
    return CapIRFragment(effect="print", ops=[CapIRPrint(text=text) for text in parsed.texts])


def execute_capir_artifact(artifact: object) -> CapIRExecutionResult:
    parsed = parse_artifact_v1(artifact)
    return CapIRExecutionResult(output=artifact_v1_stdout(parsed))


def execute_capir_fragment(fragment: CapIRFragment) -> CapIRExecutionResult:
    if fragment.effect != "print":
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", f"unsupported effect: {fragment.effect}")
        )
    parts: list[str] = []
    for index, op in enumerate(fragment.ops):
        if index > 0:
            parts.append("\n")
        parts.append(op.text)
    return CapIRExecutionResult(output="".join(parts))
