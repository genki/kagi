from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error


@dataclass(frozen=True)
class SelfhostAnalysisV1:
    function_arities: dict[str, int]
    program_effects: list[str]
    function_effects: dict[str, list[str]]


def parse_selfhost_analysis_v1(raw: object) -> SelfhostAnalysisV1:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", "analysis must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", f"invalid analysis json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "analysis_v1":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", "unsupported analysis payload")
        )
    function_arities = payload.get("function_arities", {})
    effects = payload.get("effects", {})
    program_effects = effects.get("program", [])
    function_effects = effects.get("functions", {})
    if not isinstance(function_arities, dict) or not all(isinstance(k, str) and isinstance(v, int) for k, v in function_arities.items()):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", "analysis requires function_arities")
        )
    if not isinstance(program_effects, list) or not all(isinstance(item, str) for item in program_effects):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", "analysis requires program effects")
        )
    if not isinstance(function_effects, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-analysis", "analysis requires function effects")
        )
    normalized_function_effects: dict[str, list[str]] = {}
    for name, items in function_effects.items():
        if not isinstance(name, str) or not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise DiagnosticError(
                diagnostic_from_runtime_error("selfhost-analysis", "invalid function effects")
            )
        normalized_function_effects[name] = list(items)
    return SelfhostAnalysisV1(
        function_arities=dict(function_arities),
        program_effects=list(program_effects),
        function_effects=normalized_function_effects,
    )


def selfhost_analysis_v1_to_json(analysis: SelfhostAnalysisV1) -> str:
    return json.dumps(
        {
            "kind": "analysis_v1",
            "function_arities": analysis.function_arities,
            "effects": {
                "program": analysis.program_effects,
                "functions": analysis.function_effects,
            },
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
