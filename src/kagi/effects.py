from __future__ import annotations

from dataclasses import dataclass

from .hir import HIRCallStmtV1, HIRIfStmtV1, HIRLetStmtV1, HIRPrintStmtV1, HIRProgramV1, HIRStmtV1
from .resolve import ResolvedProgramV1


@dataclass(frozen=True)
class EffectSummaryV1:
    program_effects: list[str]
    function_effects: dict[str, list[str]]


def infer_effects_v1(resolved: ResolvedProgramV1) -> EffectSummaryV1:
    function_map = {fn.name: fn for fn in resolved.program.functions}
    cache: dict[str, set[str]] = {}

    def effects_of_body(body: list[HIRStmtV1], visiting: set[str]) -> set[str]:
        effects: set[str] = set()
        for stmt in body:
            if isinstance(stmt, HIRPrintStmtV1):
                effects.add("print")
            elif isinstance(stmt, HIRIfStmtV1):
                effects |= effects_of_body(stmt.then_body, visiting)
                effects |= effects_of_body(stmt.else_body, visiting)
            elif isinstance(stmt, HIRCallStmtV1):
                if stmt.name in cache:
                    effects |= cache[stmt.name]
                elif stmt.name in function_map and stmt.name not in visiting:
                    fn_effects = effects_of_body(function_map[stmt.name].body, visiting | {stmt.name})
                    cache[stmt.name] = fn_effects
                    effects |= fn_effects
            elif isinstance(stmt, HIRLetStmtV1):
                continue
        return effects

    function_effects = {
        fn.name: sorted(effects_of_body(fn.body, {fn.name}) or {"pure"})
        for fn in resolved.program.functions
    }
    program_effects = sorted(effects_of_body(resolved.program.statements, set()) or {"pure"})
    return EffectSummaryV1(program_effects=program_effects, function_effects=function_effects)
