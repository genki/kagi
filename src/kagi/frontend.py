from __future__ import annotations

from dataclasses import dataclass

from .runtime import (
    Action,
    Cell,
    ExecutionResult,
    Heap,
    KagiRuntimeError,
    LoanState,
    apply_action,
    export_owner,
    well_formed,
)


@dataclass(frozen=True)
class ExportAssertion:
    owner_name: str
    expected: str


@dataclass(frozen=True)
class BootstrapProgram:
    heap: Heap
    owner_ids: dict[str, int]
    actions: list[Action]
    assertions: list[tuple[int, ExportAssertion]]


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
                    raise KagiRuntimeError("expected '=' in let binding")
                value = int(parts[4])
                if kind == "key":
                    key_values[name] = value
                elif kind == "epoch":
                    epoch_values[name] = value
                else:
                    raise KagiRuntimeError(f"unknown let kind: {kind}")
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
                    raise KagiRuntimeError(f"unknown owner in assertion: {owner_name}")
                expected = normalize_export(parts[2:], epoch_values)
                assertions.append((len(actions), ExportAssertion(owner_name=owner_name, expected=expected)))
                continue

            if head in {"borrow_mut", "end_mut", "borrow_shared", "end_shared", "drop"}:
                owner_name = parts[1]
                if owner_name not in owner_ids:
                    raise KagiRuntimeError(f"unknown owner: {owner_name}")
                owner_id = owner_ids[owner_name]
                if head == "drop":
                    actions.append(Action(head, owner_id))
                    continue
                value = parse_named_value(head, parts[2], key_values, epoch_values)
                actions.append(Action(head, owner_id, value))
                continue
        except (IndexError, ValueError) as exc:
            raise KagiRuntimeError(f"parse error on line {lineno}: {raw_line}") from exc

        raise KagiRuntimeError(f"unknown statement on line {lineno}: {raw_line}")

    if not well_formed(heap):
        raise KagiRuntimeError("initial heap is not well-formed")

    return BootstrapProgram(heap=heap, owner_ids=owner_ids, actions=actions, assertions=assertions)


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


def execute_bootstrap_program(source: str) -> ExecutionResult:
    program = parse_bootstrap_program(source)
    trace = [program.heap]
    current = program.heap

    for index, action in enumerate(program.actions, start=1):
        current = apply_action(current, action)
        if not well_formed(current):
            raise KagiRuntimeError("heap became ill-formed")
        trace.append(current)

        for assertion_index, assertion in program.assertions:
            if assertion_index != index:
                continue
            owner_id = program.owner_ids[assertion.owner_name]
            actual = export_owner(current, owner_id)
            if actual != assertion.expected:
                raise KagiRuntimeError(
                    f"assert_export failed for {assertion.owner_name}: expected {assertion.expected}, got {actual}"
                )

    return ExecutionResult(heap=current, trace=trace, actions=program.actions)
