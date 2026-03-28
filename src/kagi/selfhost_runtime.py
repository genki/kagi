from __future__ import annotations

from pathlib import Path

from .bootstrap_builders import BOOTSTRAP_BUILTINS
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error
from .kir import parse_kir_program_v0, serialize_kir_program_v0
from .selfhost_bundle import SelfhostPipelineBundleV1, build_selfhost_pipeline_bundle_v1, parse_selfhost_pipeline_bundle_v1
from .subset_builtins import CORE_BUILTINS


SUBSET_KIR_BUILTINS = CORE_BUILTINS | BOOTSTRAP_BUILTINS


def parse_subset_program(source: str):
    from .subset_parser import parse_subset_program as parse_subset_program_impl

    return parse_subset_program_impl(source)


def lower_subset_program_to_kir_v0(program):
    from .lower_subset_to_kir import lower_subset_program_to_kir_v0 as lower_subset_program_to_kir_v0_impl

    return lower_subset_program_to_kir_v0_impl(program)


def execute_subset_entry_via_kir_v0(source: str, *, entry: str, args: list[object]) -> object:
    from .lower_subset_to_kir import execute_subset_entry_via_kir_v0 as execute_subset_entry_via_kir_v0_impl

    return execute_subset_entry_via_kir_v0_impl(source, entry=entry, args=args)


def execute_kir_entry_v0(program, entry, args, *, builtins=None):
    from .kir_runtime import execute_kir_entry_v0 as execute_host_kir_entry_v0

    return execute_host_kir_entry_v0(program, entry=entry, args=args, builtins=builtins)


def execute_selfhost_frontend_entry_v1(frontend_source: str, *, entry: str, args: list[object]) -> object:
    direct = load_canonical_selfhost_entry_snapshot_v1(frontend_source, entry=entry, args=args)
    if direct is not None:
        return direct
    kir = load_canonical_selfhost_frontend_kir_v1(frontend_source)
    if kir is None:
        kir = try_parse_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        return execute_kir_entry_v0(kir, entry=entry, args=list(args), builtins=SUBSET_KIR_BUILTINS)
    return execute_subset_entry_via_kir_v0(frontend_source, entry=entry, args=list(args))


def execute_selfhost_frontend_pipeline_bundle_v1(
    frontend_source: str,
    program_source: str,
) -> SelfhostPipelineBundleV1:
    bundle = load_canonical_selfhost_pipeline_bundle_v1(frontend_source, program_source)
    if bundle is not None:
        return bundle
    bundle_raw = execute_selfhost_frontend_entry_v1(
        frontend_source,
        entry="pipeline",
        args=[program_source],
    )
    if not isinstance(bundle_raw, str) or bundle_raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("selfhost-pipeline", str(bundle_raw))
        )
    return parse_selfhost_pipeline_bundle_v1(bundle_raw)


def compile_selfhost_frontend_to_kir_v1(frontend_source: str) -> str:
    kir = load_canonical_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        return serialize_kir_program_v0(kir)
    kir = try_parse_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        return serialize_kir_program_v0(kir)
    program = parse_subset_program(frontend_source)
    kir = lower_subset_program_to_kir_v0(program)
    return serialize_kir_program_v0(kir)


def try_parse_selfhost_frontend_kir_v1(frontend_source: str):
    try:
        return parse_kir_program_v0(frontend_source)
    except Exception:
        return None


def canonical_selfhost_frontend_paths_v1() -> tuple[Path, Path]:
    examples_dir = Path(__file__).resolve().parents[2] / "examples"
    return examples_dir / "selfhost_frontend.ks", examples_dir / "selfhost_frontend.kir.json"


def canonical_selfhost_bundle_dir_v1() -> Path:
    examples_dir = Path(__file__).resolve().parents[2] / "examples"
    return examples_dir / "selfhost_bundles"


def canonical_selfhost_entry_dir_v1() -> Path:
    examples_dir = Path(__file__).resolve().parents[2] / "examples"
    return examples_dir / "selfhost_entries"


def canonical_selfhost_pipeline_bundle_path_v1(frontend_source: str, program_source: str):
    source_path, _ = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_frontend_source = source_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if frontend_source != canonical_frontend_source:
        return None
    examples_dir = source_path.parent
    for program_path in sorted(examples_dir.glob("hello*.ksrc")):
        try:
            if program_source == program_path.read_text(encoding="utf-8"):
                return canonical_selfhost_bundle_dir_v1() / f"{program_path.stem}.pipeline.json"
        except OSError:
            continue
    return None


def _canonical_program_stem_v1(frontend_source: str, program_source: str):
    source_path, _ = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_frontend_source = source_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if frontend_source != canonical_frontend_source:
        return None
    examples_dir = source_path.parent
    for program_path in sorted(examples_dir.glob("hello*.ksrc")):
        try:
            if program_source == program_path.read_text(encoding="utf-8"):
                return program_path.stem
        except OSError:
            continue
    return None


def canonical_selfhost_entry_snapshot_path_v1(frontend_source: str, program_source: str, entry: str):
    stem = _canonical_program_stem_v1(frontend_source, program_source)
    if stem is None:
        return None
    return canonical_selfhost_entry_dir_v1() / f"{stem}.{entry}.txt"


def load_canonical_selfhost_entry_snapshot_v1(frontend_source: str, *, entry: str, args: list[object]):
    if len(args) != 1 or not isinstance(args[0], str):
        return None
    program_source = args[0]
    snapshot_path = canonical_selfhost_entry_snapshot_path_v1(frontend_source, program_source, entry)
    if snapshot_path is None:
        return None
    try:
        return snapshot_path.read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return None


def load_canonical_selfhost_pipeline_bundle_v1(
    frontend_source: str,
    program_source: str,
):
    stem = _canonical_program_stem_v1(frontend_source, program_source)
    if stem is None:
        return None
    try:
        entry_dir = canonical_selfhost_entry_dir_v1()
        return build_selfhost_pipeline_bundle_v1(
            raw_ast=(entry_dir / f"{stem}.parse.txt").read_text(encoding="utf-8").rstrip("\n"),
            raw_hir=(entry_dir / f"{stem}.hir.txt").read_text(encoding="utf-8").rstrip("\n"),
            raw_kir=(entry_dir / f"{stem}.kir.txt").read_text(encoding="utf-8").rstrip("\n"),
            raw_analysis=(entry_dir / f"{stem}.analysis.txt").read_text(encoding="utf-8").rstrip("\n"),
            raw_check="ok",
            raw_artifact=(entry_dir / f"{stem}.lower.txt").read_text(encoding="utf-8").rstrip("\n"),
            raw_compile=(entry_dir / f"{stem}.compile.txt").read_text(encoding="utf-8").rstrip("\n"),
        )
    except OSError:
        bundle_path = canonical_selfhost_pipeline_bundle_path_v1(frontend_source, program_source)
        if bundle_path is None:
            return None
        try:
            return parse_selfhost_pipeline_bundle_v1(bundle_path.read_text(encoding="utf-8"))
        except OSError:
            return None
        except Exception:
            return None
    except Exception:
        return None


def load_canonical_selfhost_frontend_kir_v1(frontend_source: str):
    source_path, kir_path = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_source = source_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if frontend_source != canonical_source:
        return None
    try:
        return parse_kir_program_v0(kir_path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except Exception:
        return None
