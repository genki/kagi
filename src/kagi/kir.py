from __future__ import annotations

from dataclasses import dataclass
import json

from .artifact import PrintArtifactV1, artifact_v1_stdout


@dataclass(frozen=True)
class KIRPrintV0:
    text: str


@dataclass(frozen=True)
class KIRProgramV0:
    instructions: list[KIRPrintV0]


KIRPrintV1 = KIRPrintV0
KIRProgramV1 = KIRProgramV0


def kir_program_from_print_artifact(artifact: PrintArtifactV1) -> KIRProgramV0:
    return KIRProgramV0(instructions=[KIRPrintV0(text=text) for text in artifact.texts])


def kir_program_to_print_artifact(program: KIRProgramV0) -> PrintArtifactV1:
    return PrintArtifactV1(texts=[op.text for op in program.instructions])


def inspect_kir_program(program: KIRProgramV0) -> dict[str, object]:
    return {
        "kind": "kir",
        "effect": "print",
        "ops": [{"text": op.text} for op in program.instructions],
        "stdout": artifact_v1_stdout(kir_program_to_print_artifact(program)),
    }


def inspect_kir_artifact(program: KIRProgramV0) -> dict[str, object]:
    return inspect_kir_program(program)


def serialize_kir_program_v0(program: KIRProgramV0) -> str:
    return json.dumps(
        {
            "kind": "kir",
            "effect": "print",
            "ops": [{"text": op.text} for op in program.instructions],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def serialize_kir_program(program: KIRProgramV0) -> str:
    return serialize_kir_program_v0(program)


def execute_kir_program(program: KIRProgramV0) -> str:
    return artifact_v1_stdout(kir_program_to_print_artifact(program))
