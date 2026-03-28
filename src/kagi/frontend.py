from __future__ import annotations

from dataclasses import dataclass

from .diagnostics import Diagnostic, DiagnosticError, diagnostic_from_runtime_error
from .ir import Action, ProgramIR
from .runtime import (
    Cell,
    Heap,
    KagiRuntimeError,
    LoanState,
    execute_program_ir,
    well_formed
)


@dataclass(frozen=True)
class ExportAssertion:
    owner_name: str
    expected: str


@dataclass(frozen=True)
class BootstrapProgram:
    program: ProgramIR
    owner_ids: dict[str, int]
    assertions: list[tuple[int, ExportAssertion]]


def fail_parse(
    *,
    source: str,
    lineno: int,
    raw_line: str,
    code: str,
    message: str,
    column: int | None = None,
) -> "DiagnosticError":
    snippet = source.splitlines()[lineno - 1] if source.splitlines() else raw_line
    return DiagnosticError(
        Diagnostic(
            phase="parse",
            code=code,
            message=message,
            line=lineno,
            column=column or 1,
            snippet=snippet,
        )
    )


def parse_core_program(source: str) -> ProgramIR:
    heap: Heap = {}
    actions: list[Action] = []

    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        head = parts[0]

        try:
            if head == "owner":
                owner = int(parts[1])
                alive = parse_alive(parts[2])
                loan = parse_loan(parts[3:])
                heap[owner] = Cell(alive=alive, loan=loan)
                continue

            if head == "borrow_mut":
                actions.append(Action("borrow_mut", int(parts[1]), int(parts[2])))
                continue
            if head == "end_mut":
                actions.append(Action("end_mut", int(parts[1]), int(parts[2])))
                continue
            if head == "borrow_shared":
                actions.append(Action("borrow_shared", int(parts[1]), int(parts[2])))
                continue
            if head == "end_shared":
                actions.append(Action("end_shared", int(parts[1]), int(parts[2])))
                continue
            if head == "drop":
                actions.append(Action("drop", int(parts[1])))
                continue
        except DiagnosticError:
            raise
        except (IndexError, ValueError, KagiRuntimeError) as exc:
            raise fail_parse(
                source=source,
                lineno=lineno,
                raw_line=raw_line,
                code="parse_error",
                message=f"parse error on line {lineno}: {raw_line}",
            ) from exc

        raise fail_parse(
            source=source,
            lineno=lineno,
            raw_line=raw_line,
            code="unknown_statement",
            message=f"unknown statement on line {lineno}: {raw_line}",
        )

    if not well_formed(heap):
        raise DiagnosticError(
            Diagnostic(
                phase="parse",
                code="initial_heap_not_well_formed",
                message="initial heap is not well-formed",
                line=None,
                column=None,
                snippet=None,
            )
        )

    return ProgramIR(heap=heap, actions=actions)


def parse_bootstrap_program(source: str) -> BootstrapProgram:
    owner_ids: dict[str, int] = {}
    key_values: dict[str, int] = {}
    epoch_values: dict[str, int] = {}
    heap: Heap = {}
    actions: list[Action] = []
    assertions: list[tuple[int, ExportAssertion]] = []

    for lineno, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        head = parts[0]

        try:
            if head == "let":
                kind = parts[1]
                name = parts[2]
                if parts[3] != "=":
                    raise fail_parse(
                        source=source,
                        lineno=lineno,
                        raw_line=raw_line,
                        code="expected_equals",
                        message="expected '=' in let binding",
                    )
                value = int(parts[4])
                if kind == "key":
                    key_values[name] = value
                elif kind == "epoch":
                    epoch_values[name] = value
                else:
                    raise fail_parse(
                        source=source,
                        lineno=lineno,
                        raw_line=raw_line,
                        code="unknown_let_kind",
                        message=f"unknown let kind: {kind}",
                    )
                continue

            if head == "owner":
                owner_name = parts[1]
                owner_id = owner_ids.setdefault(owner_name, len(owner_ids))
                alive = parse_alive(parts[2])
                loan = parse_named_loan(parts[3:], key_values, epoch_values)
                heap[owner_id] = Cell(alive=alive, loan=loan)
                continue

            if head == "assert_export":
                owner_name = parts[1]
                if owner_name not in owner_ids:
                    raise fail_parse(
                        source=source,
                        lineno=lineno,
                        raw_line=raw_line,
                        code="unknown_owner_in_assertion",
                        message=f"unknown owner in assertion: {owner_name}",
                    )
                expected = normalize_export(parts[2:], epoch_values)
                assertions.append((len(actions), ExportAssertion(owner_name=owner_name, expected=expected)))
                continue

            if head in {"borrow_mut", "end_mut", "borrow_shared", "end_shared", "drop"}:
                owner_name = parts[1]
                if owner_name not in owner_ids:
                    raise fail_parse(
                        source=source,
                        lineno=lineno,
                        raw_line=raw_line,
                        code="unknown_owner",
                        message=f"unknown owner: {owner_name}",
                    )
                owner_id = owner_ids[owner_name]
                if head == "drop":
                    actions.append(Action(head, owner_id))
                    continue
                value = parse_named_value(head, parts[2], key_values, epoch_values)
                actions.append(Action(head, owner_id, value))
                continue
        except DiagnosticError:
            raise
        except (IndexError, ValueError, KagiRuntimeError) as exc:
            raise fail_parse(
                source=source,
                lineno=lineno,
                raw_line=raw_line,
                code="parse_error",
                message=f"parse error on line {lineno}: {raw_line}",
            ) from exc

        raise fail_parse(
            source=source,
            lineno=lineno,
            raw_line=raw_line,
            code="unknown_statement",
            message=f"unknown statement on line {lineno}: {raw_line}",
        )

    if not well_formed(heap):
        raise DiagnosticError(
            Diagnostic(
                phase="parse",
                code="initial_heap_not_well_formed",
                message="initial heap is not well-formed",
                line=None,
                column=None,
                snippet=None,
            )
        )

    return BootstrapProgram(
        program=ProgramIR(heap=heap, actions=actions),
        owner_ids=owner_ids,
        assertions=assertions,
    )


def parse_alive(token: str) -> bool:
    if token == "alive":
        return True
    if token == "dead":
        return False
    raise KagiRuntimeError(f"invalid alive state: {token}")


def parse_named_loan(tokens: list[str], key_values: dict[str, int], epoch_values: dict[str, int]) -> LoanState:
    if not tokens:
        raise KagiRuntimeError("missing loan state")
    if tokens[0] == "idle":
        return LoanState.idle()
    if tokens[0] == "mut":
        return LoanState.mut(resolve_symbol(tokens[1], key_values))
    if tokens[0] == "shared":
        return LoanState.shared(resolve_symbol(tokens[1], epoch_values), int(tokens[2]))
    raise KagiRuntimeError(f"invalid loan state: {' '.join(tokens)}")


def parse_loan(tokens: list[str]) -> LoanState:
    if not tokens:
        raise KagiRuntimeError("missing loan state")
    if tokens[0] == "idle":
        return LoanState.idle()
    if tokens[0] == "mut":
        return LoanState.mut(int(tokens[1]))
    if tokens[0] == "shared":
        return LoanState.shared(int(tokens[1]), int(tokens[2]))
    raise KagiRuntimeError(f"invalid loan state: {' '.join(tokens)}")


def parse_named_value(kind: str, token: str, key_values: dict[str, int], epoch_values: dict[str, int]) -> int:
    if kind in {"borrow_mut", "end_mut"}:
        return resolve_symbol(token, key_values)
    if kind in {"borrow_shared", "end_shared"}:
        return resolve_symbol(token, epoch_values)
    return int(token)


def resolve_symbol(token: str, table: dict[str, int]) -> int:
    if token in table:
        return table[token]
    return int(token)


def normalize_export(tokens: list[str], epoch_values: dict[str, int]) -> str:
    if tokens[0] in {"idle", "mut"}:
        return tokens[0]
    if tokens[0] == "shared":
        return f"shared {resolve_symbol(tokens[1], epoch_values)}"
    raise KagiRuntimeError(f"invalid export expectation: {' '.join(tokens)}")


def execute_bootstrap_program(source: str):
    program = parse_bootstrap_program(source)
    try:
        result = execute_program_ir(program.program)
    except KagiRuntimeError as exc:
        raise DiagnosticError(diagnostic_from_runtime_error("runtime", str(exc))) from exc

    for index, heap in enumerate(result.trace[1:], start=1):
        for assertion_index, assertion in program.assertions:
            if assertion_index != index:
                continue
            owner_id = program.owner_ids[assertion.owner_name]
            actual = heap[owner_id].loan.export()
            if actual != assertion.expected:
                raise DiagnosticError(
                    Diagnostic(
                        phase="assert",
                        code="assert_export_failed",
                        message=(
                            f"assert_export failed for {assertion.owner_name}: "
                            f"expected {assertion.expected}, got {actual}"
                        ),
                        line=None,
                        column=None,
                        snippet=None,
                    )
                )
    return result
