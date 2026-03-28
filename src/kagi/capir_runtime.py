from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment


@dataclass(frozen=True)
class CapIRExecutionResult:
    output: str


def execute_capir_fragment(fragment: CapIRFragment) -> CapIRExecutionResult:
    if fragment.effect != "print":
        raise DiagnosticError(
            diagnostic_from_runtime_error("capir-runtime", f"unsupported effect: {fragment.effect}")
        )
    parts: list[str] = []
    for op in fragment.ops:
        parts.append(op.text)
    return CapIRExecutionResult(output="".join(parts))
