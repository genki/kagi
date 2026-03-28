from __future__ import annotations

from dataclasses import dataclass

from .kir import KIRPrintV0, KIRProgramV0


@dataclass(frozen=True)
class KIRExecutionResultV0:
    output: str


def execute_kir_program_v0(program: KIRProgramV0) -> KIRExecutionResultV0:
    parts: list[str] = []
    for index, instr in enumerate(program.instructions):
        if isinstance(instr, KIRPrintV0):
            if index > 0:
                parts.append("\n")
            parts.append(instr.text)
    return KIRExecutionResultV0(output="".join(parts))
