from __future__ import annotations

from dataclasses import dataclass

from .artifact import PrintArtifactV1, artifact_v1_stdout, parse_artifact_v1
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .hir import HIRProgramV1, lower_surface_program_to_hir_v1
from .subset import run_subset_program
from .surface_ast import SurfaceProgramV1, parse_surface_program_v1


@dataclass(frozen=True)
class ParseArtifactV1:
    raw_ast: str
    surface_ast: SurfaceProgramV1


@dataclass(frozen=True)
class CheckArtifactV1:
    raw_result: str
    ok: bool


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


def compile_source_v1(frontend_source: str, program_source: str) -> CompileResultV1:
    ast_raw = run_subset_program(frontend_source, entry="parse", args=[program_source])
    if not isinstance(ast_raw, str) or ast_raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-parse", str(ast_raw))
        )
    surface_ast = parse_surface_program_v1(ast_raw)

    check_raw = run_subset_program(frontend_source, entry="check", args=[program_source])
    if check_raw != "ok":
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-check", str(check_raw))
        )

    hir = lower_surface_program_to_hir_v1(surface_ast)

    lower_raw = run_subset_program(frontend_source, entry="lower", args=[program_source])
    lower_artifact = parse_artifact_v1(lower_raw)

    compile_raw = run_subset_program(frontend_source, entry="compile", args=[program_source])
    compile_artifact = parse_artifact_v1(compile_raw)

    return CompileResultV1(
        parse=ParseArtifactV1(raw_ast=ast_raw, surface_ast=surface_ast),
        check=CheckArtifactV1(raw_result="ok", ok=True),
        lower=LowerArtifactV1(raw_artifact=lower_raw, hir=hir, artifact=lower_artifact),
        compile_artifact=compile_artifact,
        raw_compile_artifact=compile_raw,
        stdout=artifact_v1_stdout(compile_artifact),
    )
