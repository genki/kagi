from __future__ import annotations

import json
from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .effects import EffectSummaryV1, infer_effects_v1
from .hir import HIRProgramV1, lower_surface_program_to_hir_v1
from .resolve import ResolvedProgramV1, resolve_hir_program_v1
from .subset import run_subset_program
from .surface_ast import SurfaceProgramV1, parse_surface_program_v1
from .typecheck import TypecheckedProgramV1, typecheck_program_v1


@dataclass(frozen=True)
class ParseArtifactV1:
    raw_ast: str
    surface_ast: SurfaceProgramV1


@dataclass(frozen=True)
class CheckArtifactV1:
    raw_result: str
    ok: bool
    resolved: ResolvedProgramV1
    typed: TypecheckedProgramV1
    effects: EffectSummaryV1


@dataclass(frozen=True)
class LowerArtifactV1:
    raw_artifact: str
    hir: HIRProgramV1
    artifact: PrintArtifactV1


@dataclass(frozen=True)
class CompileResultV1:
    parse: ParseArtifactV1
    check: CheckArtifactV1
    lower: LowerArtifactV1
    compile_artifact: PrintArtifactV1
    raw_compile_artifact: str
    stdout: str


def parse_selfhost_pipeline_bundle_v1(bundle_raw: str) -> tuple[str, str, str]:
    try:
        bundle = json.loads(bundle_raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", f"invalid bundle: {exc.msg}")
        )
    if not isinstance(bundle, dict) or bundle.get("kind") != "pipeline_bundle":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "unsupported bundle payload")
        )
    ast_value = bundle.get("ast")
    check_raw = bundle.get("check")
    artifact_value = bundle.get("artifact")
    compile_value = bundle.get("compile")

    def bundle_value_to_raw(value: object) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list, int, float, bool)) or value is None:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "unsupported bundle payload")
        )

    try:
        ast_raw = bundle_value_to_raw(ast_value)
        artifact_raw = bundle_value_to_raw(artifact_value)
        compile_raw = bundle_value_to_raw(compile_value)
    except DiagnosticError:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "unsupported bundle payload")
        )
    if check_raw != "ok" or compile_raw != artifact_raw:
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", "inconsistent bundle payload")
        )
    return ast_raw, artifact_raw, compile_raw


def compile_source_v1(frontend_source: str, program_source: str) -> CompileResultV1:
    bundle_raw = run_subset_program(frontend_source, entry="pipeline", args=[program_source])
    if not isinstance(bundle_raw, str) or bundle_raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", str(bundle_raw))
        )
    ast_raw, lower_raw, compile_raw = parse_selfhost_pipeline_bundle_v1(bundle_raw)
    surface_ast = parse_surface_program_v1(ast_raw)

    hir = lower_surface_program_to_hir_v1(surface_ast)
    resolved = resolve_hir_program_v1(hir)
    typed = typecheck_program_v1(resolved)
    effects = infer_effects_v1(resolved)

    lower_artifact = parse_artifact_v1(lower_raw)
    compile_artifact = parse_artifact_v1(compile_raw)

    return CompileResultV1(
        parse=ParseArtifactV1(raw_ast=ast_raw, surface_ast=surface_ast),
        check=CheckArtifactV1(raw_result="ok", ok=True, resolved=resolved, typed=typed, effects=effects),
        lower=LowerArtifactV1(raw_artifact=lower_raw, hir=hir, artifact=lower_artifact),
        compile_artifact=compile_artifact,
        raw_compile_artifact=compile_raw,
        stdout=artifact_v1_stdout(compile_artifact),
    )
