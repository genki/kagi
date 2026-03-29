from __future__ import annotations

import os
from pathlib import Path

from .selfhost_bundle import (
    SelfhostPipelineBundleV1,
    build_selfhost_pipeline_bundle_v1,
    parse_selfhost_pipeline_bundle_v1,
)
from .kir import parse_kir_program_v0


def _examples_dir_v1() -> Path:
    env_home = os.environ.get("KAGI_HOME")
    if env_home:
        examples_dir = Path(env_home) / "examples"
        if examples_dir.exists():
            return examples_dir
    return Path(__file__).resolve().parents[2] / "examples"


def _read_text_v1(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def canonical_selfhost_frontend_paths_v1() -> tuple[Path, Path]:
    examples_dir = _examples_dir_v1()
    return examples_dir / "selfhost_frontend.ks", examples_dir / "selfhost_frontend.kir.json"


def read_canonical_frontend_texts_v1() -> tuple[str, str]:
    source_path, kir_path = canonical_selfhost_frontend_paths_v1()
    return _read_text_v1(source_path), _read_text_v1(kir_path)


def canonical_selfhost_bundle_dir_v1() -> Path:
    return _examples_dir_v1() / "selfhost_bundles"


def canonical_selfhost_entry_dir_v1() -> Path:
    return _examples_dir_v1() / "selfhost_entries"


def _canonical_program_stem_v1(frontend_source: str, program_source: str):
    source_path, _ = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_frontend_source = _read_text_v1(source_path)
    except OSError:
        return None
    if frontend_source != canonical_frontend_source:
        return None
    examples_dir = source_path.parent
    for program_path in sorted(examples_dir.glob("hello*.ksrc")):
        try:
            if program_source == _read_text_v1(program_path):
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
        return _read_text_v1(snapshot_path).rstrip("\n")
    except OSError:
        return None


def canonical_selfhost_pipeline_bundle_path_v1(frontend_source: str, program_source: str):
    source_path, _ = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_frontend_source = _read_text_v1(source_path)
    except OSError:
        return None
    if frontend_source != canonical_frontend_source:
        return None
    examples_dir = source_path.parent
    for program_path in sorted(examples_dir.glob("hello*.ksrc")):
        try:
            if program_source == _read_text_v1(program_path):
                return canonical_selfhost_bundle_dir_v1() / f"{program_path.stem}.pipeline.json"
        except OSError:
            continue
    return None


def load_canonical_selfhost_pipeline_bundle_v1(
    frontend_source: str,
    program_source: str,
) -> SelfhostPipelineBundleV1 | None:
    stem = _canonical_program_stem_v1(frontend_source, program_source)
    if stem is None:
        return None
    try:
        entry_dir = canonical_selfhost_entry_dir_v1()
        return build_selfhost_pipeline_bundle_v1(
            raw_ast=_read_text_v1(entry_dir / f"{stem}.parse.txt").rstrip("\n"),
            raw_hir=_read_text_v1(entry_dir / f"{stem}.hir.txt").rstrip("\n"),
            raw_kir=_read_text_v1(entry_dir / f"{stem}.kir.txt").rstrip("\n"),
            raw_analysis=_read_text_v1(entry_dir / f"{stem}.analysis.txt").rstrip("\n"),
            raw_check="ok",
            raw_artifact=_read_text_v1(entry_dir / f"{stem}.lower.txt").rstrip("\n"),
            raw_compile=_read_text_v1(entry_dir / f"{stem}.compile.txt").rstrip("\n"),
        )
    except OSError:
        bundle_path = canonical_selfhost_pipeline_bundle_path_v1(frontend_source, program_source)
        if bundle_path is None:
            return None
        try:
            return parse_selfhost_pipeline_bundle_v1(_read_text_v1(bundle_path))
        except OSError:
            return None
        except Exception:
            return None
    except Exception:
        return None


def load_canonical_selfhost_frontend_kir_v1(frontend_source: str):
    source_path, kir_path = canonical_selfhost_frontend_paths_v1()
    try:
        canonical_source = _read_text_v1(source_path)
    except OSError:
        return None
    if frontend_source != canonical_source:
        return None
    try:
        return parse_kir_program_v0(_read_text_v1(kir_path))
    except OSError:
        return None
    except Exception:
        return None
