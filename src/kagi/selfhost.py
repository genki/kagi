from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error


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
    if len(program.statements) != 1:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "only single-statement tiny programs are supported")
        )
    stmt = program.statements[0]
    return json.dumps({"kind": "print", "text": stmt.text}, ensure_ascii=False, separators=(",", ":"))


def render_tiny_program(program: TinyProgram) -> str:
    if len(program.statements) != 1:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "only single-statement tiny programs are supported")
        )
    return program.statements[0].text


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
    if not isinstance(payload, dict) or payload.get("kind") != "print":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "unsupported selfhost artifact")
        )
    text = payload.get("text")
    if not isinstance(text, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-bridge", "print artifact requires string text")
        )
    return text
