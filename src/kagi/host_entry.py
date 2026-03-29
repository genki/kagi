from __future__ import annotations

import sys

from .cli_host import execute_host_command_v1
from .host_abi import parse_host_argv_v1


def main(argv: list[str] | None = None) -> None:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    try:
        command = parse_host_argv_v1(raw_argv)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc

    response = execute_host_command_v1(command)
    if response.stdout:
        print(response.stdout, end="")
    if response.stderr:
        print(response.stderr, file=sys.stderr, end="")
    raise SystemExit(response.exit_code)


if __name__ == "__main__":
    main()
