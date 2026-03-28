from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .ir import CapIRFragment, CapIRPrint


@dataclass(frozen=True)
class TinyPrint:
    text: str


@dataclass(frozen=True)
class TinyProgram:
    statements: list[TinyPrint]


def parse_tiny_program_ast_json(raw: object) -> TinyProgram:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "program ast must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", f"invalid program ast json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "program":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported program ast")
        )
    statements_raw = payload.get("statements")
    if not isinstance(statements_raw, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "program ast requires statements")
        )
    statements: list[TinyPrint] = []
    for stmt in statements_raw:
        if not isinstance(stmt, dict) or stmt.get("kind") != "print":
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "unsupported statement in program ast")
            )
        text = stmt.get("text")
        if not isinstance(text, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "print statement requires string text")
            )
        statements.append(TinyPrint(text=text))
    return TinyProgram(statements=statements)


def lower_tiny_program(program: TinyProgram) -> str:
    fragment = lower_tiny_program_to_capir(program)
    texts = [stmt.text for stmt in fragment.ops]
    return json.dumps({"kind": "print_many", "texts": texts}, ensure_ascii=False, separators=(",", ":"))


def lower_tiny_program_to_capir(program: TinyProgram) -> CapIRFragment:
    if len(program.statements) == 0:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "tiny program requires at least one statement")
        )
    return CapIRFragment(effect="print", ops=[CapIRPrint(text=stmt.text) for stmt in program.statements])


def render_tiny_program(program: TinyProgram) -> str:
    if len(program.statements) == 0:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "tiny program requires at least one statement")
        )
    return "\n".join(stmt.text for stmt in program.statements)


def render_print_artifact(artifact: object) -> str:
    if not isinstance(artifact, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "selfhost artifact must be a string")
        )
    if artifact.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", artifact)
        )
    try:
        payload = json.loads(artifact)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", f"invalid selfhost artifact json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") not in {"print", "print_many"}:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported selfhost artifact")
        )
    if payload.get("kind") == "print":
        text = payload.get("text")
        if not isinstance(text, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-bridge", "print artifact requires string text")
            )
        return text
    texts = payload.get("texts")
    if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "print_many artifact requires string texts")
        )
    return "\n".join(texts)
