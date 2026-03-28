from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .effects import EffectSummaryV1, infer_effects_v1
from .hir import HIRProgramV1, lower_surface_program_to_hir_v1
from .kir import KIRProgramV1, kir_program_from_print_artifact
from .resolve import ResolvedProgramV1, resolve_hir_program_v1
from .selfhost_bundle import parse_selfhost_pipeline_bundle_v1
from .subset import run_subset_program
from .surface_ast import SurfaceProgramV1
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
    kir: KIRProgramV1


@dataclass(frozen=True)
class CompileResultV1:
    parse: ParseArtifactV1
    check: CheckArtifactV1
    lower: LowerArtifactV1
    compile_artifact: PrintArtifactV1
    compile_kir: KIRProgramV1
    raw_compile_artifact: str
    stdout: str


def compile_source_v1(frontend_source: str, program_source: str) -> CompileResultV1:
    bundle_raw = run_subset_program(frontend_source, entry="pipeline", args=[program_source])
    if not isinstance(bundle_raw, str) or bundle_raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", str(bundle_raw))
        )
    bundle = parse_selfhost_pipeline_bundle_v1(bundle_raw)
    surface_ast = bundle.surface_ast

    hir = lower_surface_program_to_hir_v1(surface_ast)
    resolved = resolve_hir_program_v1(hir)
    typed = typecheck_program_v1(resolved)
    effects = infer_effects_v1(resolved)

    lower_artifact = bundle.artifact
    compile_artifact = bundle.compile_artifact
    lower_kir = kir_program_from_print_artifact(lower_artifact)
    compile_kir = kir_program_from_print_artifact(compile_artifact)

    return CompileResultV1(
        parse=ParseArtifactV1(raw_ast=bundle.raw_ast, surface_ast=surface_ast),
        check=CheckArtifactV1(raw_result=bundle.raw_check, ok=True, resolved=resolved, typed=typed, effects=effects),
        lower=LowerArtifactV1(raw_artifact=bundle.raw_artifact, hir=hir, artifact=lower_artifact, kir=lower_kir),
        compile_artifact=compile_artifact,
        compile_kir=compile_kir,
        raw_compile_artifact=bundle.raw_compile,
        stdout=artifact_v1_stdout(compile_artifact),
    )
