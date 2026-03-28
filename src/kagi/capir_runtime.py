from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint, serialize_capir_fragment


@dataclass(frozen=True)
class CapIRExecutionResult:
    output: str


def inspect_capir_artifact(artifact: object) -> dict[str, object]:
    fragment = capir_fragment_from_artifact(artifact)
    return {
        "effect": fragment.effect,
        "ops": [{"text": op.text} for op in fragment.ops],
        "serialized": serialize_capir_fragment(fragment),
    }


def capir_fragment_from_artifact(artifact: object) -> CapIRFragment:
    if not isinstance(artifact, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", "artifact must be a string")
        )
    if artifact.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", artifact)
        )
    try:
        payload = json.loads(artifact)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", f"invalid artifact json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", "artifact must decode to an object")
        )
    kind = payload.get("kind")
    if kind == "print_many":
        texts = payload.get("texts")
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise DiagnosticError(
                diagnostic_from_runtime_error("capir-runtime", "print_many artifact requires string texts")
            )
        return CapIRFragment(effect="print", ops=[CapIRPrint(text=text) for text in texts])
    if kind == "print":
        text = payload.get("text")
        if not isinstance(text, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("capir-runtime", "print artifact requires string text")
            )
        return CapIRFragment(effect="print", ops=[CapIRPrint(text=text)])
    raise DiagnosticError(
        diagnostic_from_runtime_error("capir-runtime", f"unsupported artifact kind: {kind}")
    )


def execute_capir_artifact(artifact: object) -> CapIRExecutionResult:
    fragment = capir_fragment_from_artifact(artifact)
    return execute_capir_fragment(fragment)


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
