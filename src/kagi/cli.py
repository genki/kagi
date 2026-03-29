from __future__ import annotations

import argparse
import json


def add_json_flag(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--json", action="store_true")


def emit_payload(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def emit_text(text: str) -> None:
    print(text, end="" if text.endswith("\n") else "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kagi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("file")
    add_json_flag(run_parser)

    trace_parser = subparsers.add_parser("trace")
    trace_parser.add_argument("file")
    add_json_flag(trace_parser)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("file")
    add_json_flag(check_parser)

    exports_parser = subparsers.add_parser("exports")
    exports_parser.add_argument("file")
    add_json_flag(exports_parser)

    bootstrap_parser = subparsers.add_parser("bootstrap-check")
    bootstrap_parser.add_argument("file")
    add_json_flag(bootstrap_parser)

    bootstrap_trace_parser = subparsers.add_parser("bootstrap-trace")
    bootstrap_trace_parser.add_argument("file")
    add_json_flag(bootstrap_trace_parser)

    subset_run_parser = subparsers.add_parser("subset-run")
    subset_run_parser.add_argument("file")
    subset_run_parser.add_argument("--entry", default="main")
    subset_run_parser.add_argument("--arg", action="append", default=[])
    add_json_flag(subset_run_parser)

    selfhost_run_parser = subparsers.add_parser("selfhost-run")
    selfhost_run_parser.add_argument("frontend")
    selfhost_run_parser.add_argument("source")
    add_json_flag(selfhost_run_parser)

    selfhost_check_parser = subparsers.add_parser("selfhost-check")
    selfhost_check_parser.add_argument("frontend")
    selfhost_check_parser.add_argument("source")
    add_json_flag(selfhost_check_parser)

    selfhost_parse_parser = subparsers.add_parser("selfhost-parse")
    selfhost_parse_parser.add_argument("frontend")
    selfhost_parse_parser.add_argument("source")
    selfhost_parse_parser.add_argument("--entry", default="parse")
    add_json_flag(selfhost_parse_parser)

    selfhost_emit_parser = subparsers.add_parser("selfhost-emit")
    selfhost_emit_parser.add_argument("frontend")
    selfhost_emit_parser.add_argument("source")
    add_json_flag(selfhost_emit_parser)

    selfhost_capir_parser = subparsers.add_parser("selfhost-capir")
    selfhost_capir_parser.add_argument("frontend")
    selfhost_capir_parser.add_argument("source")
    add_json_flag(selfhost_capir_parser)

    selfhost_freeze_parser = subparsers.add_parser("selfhost-freeze")
    selfhost_freeze_parser.add_argument("frontend")
    add_json_flag(selfhost_freeze_parser)

    selfhost_build_parser = subparsers.add_parser("selfhost-build")
    selfhost_build_parser.add_argument("frontend")
    add_json_flag(selfhost_build_parser)
    return parser


def run_cli_command(args, *, emit_payload, emit_text) -> None:
    from .cli_host import run_cli_command as run_cli_command_impl

    return run_cli_command_impl(args, emit_payload=emit_payload, emit_text=emit_text)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    run_cli_command(args, emit_payload=emit_payload, emit_text=emit_text)


if __name__ == "__main__":
    main()
