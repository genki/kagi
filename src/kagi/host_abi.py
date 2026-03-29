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


def parse_host_argv_v1(argv: list[str]) -> KagiHostCommandV1:
    if not argv:
        raise ValueError("missing command")

    command = argv[0]
    rest = list(argv[1:])
    use_json = False
    entry: str | None = None
    args: list[str] = []
    positional: list[str] = []

    index = 0
    while index < len(rest):
        token = rest[index]
        if token == "--json":
            use_json = True
            index += 1
            continue
        if token == "--entry":
            if index + 1 >= len(rest):
                raise ValueError("--entry requires a value")
            entry = rest[index + 1]
            index += 2
            continue
        if token == "--arg":
            if index + 1 >= len(rest):
                raise ValueError("--arg requires a value")
            args.append(rest[index + 1])
            index += 2
            continue
        positional.append(token)
        index += 1

    if command in {"run", "trace", "check", "exports", "bootstrap-check", "bootstrap-trace"}:
        if len(positional) != 1:
            raise ValueError(f"{command} requires file")
        return KagiHostCommandV1(command=command, use_json=use_json, file=positional[0])

    if command == "subset-run":
        if len(positional) != 1:
            raise ValueError("subset-run requires file")
        return KagiHostCommandV1(
            command=command,
            use_json=use_json,
            file=positional[0],
            entry=entry or "main",
            args=args,
        )

    if command in {"selfhost-run", "selfhost-check", "selfhost-emit", "selfhost-capir"}:
        if len(positional) != 2:
            raise ValueError(f"{command} requires frontend and source")
        return KagiHostCommandV1(
            command=command,
            use_json=use_json,
            frontend=positional[0],
            source=positional[1],
        )

    if command == "selfhost-parse":
        if len(positional) != 2:
            raise ValueError("selfhost-parse requires frontend and source")
        return KagiHostCommandV1(
            command=command,
            use_json=use_json,
            frontend=positional[0],
            source=positional[1],
            entry=entry or "parse",
        )

    if command in {"selfhost-freeze", "selfhost-build", "selfhost-bootstrap"}:
        if len(positional) != 1:
            raise ValueError(f"{command} requires frontend")
        return KagiHostCommandV1(
            command=command,
            use_json=use_json,
            frontend=positional[0],
        )

    raise ValueError(f"unsupported command: {command}")
