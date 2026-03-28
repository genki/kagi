from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout
from .effects import EffectSummaryV1
from .hir import HIRProgramV1
from .kir import KIRProgramV1
from .resolve import ResolvedProgramV1
from .selfhost_runtime import execute_selfhost_frontend_pipeline_bundle_v1
from .surface_ast import SurfaceProgramV1
from .typecheck import TypecheckedProgramV1


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
class CompileMetadataV1:
    contract_version: str
    frontend_entry: str


@dataclass(frozen=True)
class CompileResultV1:
    metadata: CompileMetadataV1
    parse: ParseArtifactV1
    check: CheckArtifactV1
    lower: LowerArtifactV1
    compile_artifact: PrintArtifactV1
    compile_kir: KIRProgramV1
    raw_compile_artifact: str
    stdout: str


def compile_source_v1(frontend_source: str, program_source: str) -> CompileResultV1:
    frontend_entry = "pipeline"
    bundle = execute_selfhost_frontend_pipeline_bundle_v1(frontend_source, program_source)
    surface_ast = bundle.surface_ast

    hir = bundle.hir
    resolved = ResolvedProgramV1(program=hir, function_arities=bundle.analysis.function_arities)
    typed = TypecheckedProgramV1(program=hir)
    effects = EffectSummaryV1(
        program_effects=bundle.analysis.program_effects,
        function_effects=bundle.analysis.function_effects,
    )

    lower_artifact = bundle.artifact
    compile_artifact = bundle.compile_artifact
    lower_kir = bundle.kir
    compile_kir = bundle.kir

    return CompileResultV1(
        metadata=CompileMetadataV1(contract_version="front-half-v1", frontend_entry=frontend_entry),
        parse=ParseArtifactV1(raw_ast=bundle.raw_ast, surface_ast=surface_ast),
        check=CheckArtifactV1(raw_result=bundle.raw_check, ok=True, resolved=resolved, typed=typed, effects=effects),
        lower=LowerArtifactV1(raw_artifact=bundle.raw_artifact, hir=hir, artifact=lower_artifact, kir=lower_kir),
        compile_artifact=compile_artifact,
        compile_kir=compile_kir,
        raw_compile_artifact=bundle.raw_compile,
        stdout=artifact_v1_stdout(compile_artifact),
    )
