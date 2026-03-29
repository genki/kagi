from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KagiHostCommandV1:
    command: str
    use_json: bool = False
    file: str | None = None
    frontend: str | None = None
    source: str | None = None
    entry: str | None = None
    args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class KagiHostResponseV1:
    exit_code: int
    stdout: str
    stderr: str
    payload: dict | None = None


def host_command_from_argparse(args) -> KagiHostCommandV1:
    return KagiHostCommandV1(
        command=args.command,
        use_json=getattr(args, "json", False),
        file=getattr(args, "file", None),
        frontend=getattr(args, "frontend", None),
        source=getattr(args, "source", None),
        entry=getattr(args, "entry", None),
        args=list(getattr(args, "arg", [])),
    )
