from __future__ import annotations

from pathlib import Path

from .kir import parse_kir_program_v0, serialize_kir_program_v0
from .kir_runtime import execute_kir_entry_v0
from .lower_subset_to_kir import SUBSET_KIR_BUILTINS, execute_subset_entry_via_kir_v0, lower_subset_program_to_kir_v0
from .subset_parser import parse_subset_program


def execute_selfhost_frontend_entry_v1(frontend_source: str, *, entry: str, args: list[object]) -> object:
    kir = load_canonical_selfhost_frontend_kir_v1(frontend_source)
    if kir is None:
        kir = try_parse_selfhost_frontend_kir_v1(frontend_source)
    if kir is not None:
        return execute_kir_entry_v0(kir, entry=entry, args=list(args), builtins=SUBSET_KIR_BUILTINS)
    return execute_subset_entry_via_kir_v0(frontend_source, entry=entry, args=list(args))


def compile_selfhost_frontend_to_kir_v1(frontend_source: str) -> str:
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
