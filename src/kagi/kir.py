from __future__ import annotations

from dataclasses import dataclass, field
import json

from .artifact import PrintArtifactV1, artifact_v1_stdout
from .diagnostics import DiagnosticError, diagnostic_from_runtime_error


@dataclass(frozen=True)
class KIRStringV0:
    value: str


@dataclass(frozen=True)
class KIRBoolV0:
    value: bool


@dataclass(frozen=True)
class KIRIntV0:
    value: int


@dataclass(frozen=True)
class KIRVarV0:
    name: str


@dataclass(frozen=True)
class KIRConcatV0:
    left: "KIRExprV0"
    right: "KIRExprV0"


@dataclass(frozen=True)
class KIREqV0:
    left: "KIRExprV0"
    right: "KIRExprV0"


@dataclass(frozen=True)
class KIRIfExprV0:
    condition: "KIRExprV0"
    then_expr: "KIRExprV0"
    else_expr: "KIRExprV0"


@dataclass(frozen=True)
class KIRCallExprV0:
    callee: str
    args: list["KIRExprV0"]


KIRExprV0 = KIRStringV0 | KIRBoolV0 | KIRIntV0 | KIRVarV0 | KIRConcatV0 | KIREqV0 | KIRIfExprV0 | KIRCallExprV0


@dataclass(frozen=True)
class KIRPrintV0:
    expr: KIRExprV0

    @property
    def text(self) -> str:
        if isinstance(self.expr, KIRStringV0):
            return self.expr.value
        raise AttributeError("KIRPrintV0.text is only available for string literals")


@dataclass(frozen=True)
class KIRLetV0:
    name: str
    expr: KIRExprV0


@dataclass(frozen=True)
class KIRIfStmtV0:
    condition: KIRExprV0
    then_body: list["KIRStmtV0"]
    else_body: list["KIRStmtV0"]


@dataclass(frozen=True)
class KIRCallV0:
    name: str
    args: list[KIRExprV0]


@dataclass(frozen=True)
class KIRReturnV0:
    expr: KIRExprV0


@dataclass(frozen=True)
class KIRExprStmtV0:
    expr: KIRExprV0


KIRStmtV0 = KIRPrintV0 | KIRLetV0 | KIRIfStmtV0 | KIRCallV0 | KIRReturnV0 | KIRExprStmtV0


@dataclass(frozen=True)
class KIRFunctionV0:
    name: str
    params: list[str]
    body: list[KIRStmtV0]


@dataclass(frozen=True)
class KIRProgramV0:
    instructions: list[KIRStmtV0]
    functions: list[KIRFunctionV0] = field(default_factory=list)


KIRPrintV1 = KIRPrintV0
KIRProgramV1 = KIRProgramV0


def kir_program_from_print_artifact(artifact: PrintArtifactV1) -> KIRProgramV0:
    return KIRProgramV0(instructions=[KIRPrintV0(expr=KIRStringV0(value=text)) for text in artifact.texts])


def parse_kir_program_v0(raw: object) -> KIRProgramV0:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir program must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", f"invalid kir json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "kir":
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "unsupported kir payload")
        )
    if payload.get("effect") == "print":
        ops = payload.get("ops", [])
        if not isinstance(ops, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "print kir program requires ops")
            )
        return KIRProgramV0(
            instructions=[
                KIRPrintV0(expr=KIRStringV0(value=_parse_print_op(item)))
                for item in ops
            ]
        )

    functions = payload.get("functions", [])
    instructions = payload.get("instructions", [])
    if not isinstance(functions, list) or not isinstance(instructions, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir program requires functions and instructions")
        )
    return KIRProgramV0(
        instructions=[parse_kir_stmt_v0(item) for item in instructions],
        functions=[parse_kir_function_v0(item) for item in functions],
    )


def parse_kir_function_v0(raw: object) -> KIRFunctionV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir function must be an object")
        )
    name = raw.get("name")
    params = raw.get("params", [])
    body = raw.get("body")
    if not isinstance(name, str) or not isinstance(params, list) or not isinstance(body, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir function requires name, params, and body")
        )
    if not all(isinstance(param, str) and param for param in params):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir function params must be strings")
        )
    return KIRFunctionV0(
        name=name,
        params=list(params),
        body=[parse_kir_stmt_v0(item) for item in body],
    )


def parse_kir_stmt_v0(raw: object) -> KIRStmtV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir statement must be an object")
        )
    op = raw.get("op")
    if op == "print":
        return KIRPrintV0(expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "let":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir let requires name")
            )
        return KIRLetV0(name=name, expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "if":
        then_body = raw.get("then")
        else_body = raw.get("else")
        if not isinstance(then_body, list) or not isinstance(else_body, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir if requires bodies")
            )
        return KIRIfStmtV0(
            condition=parse_kir_expr_v0(raw.get("condition")),
            then_body=[parse_kir_stmt_v0(item) for item in then_body],
            else_body=[parse_kir_stmt_v0(item) for item in else_body],
        )
    if op == "call":
        name = raw.get("name")
        args = raw.get("args", [])
        if not isinstance(name, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir call requires name and args")
            )
        return KIRCallV0(name=name, args=[parse_kir_expr_v0(item) for item in args])
    if op == "return":
        return KIRReturnV0(expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "expr":
        return KIRExprStmtV0(expr=parse_kir_expr_v0(raw.get("expr")))
    raise DiagnosticError(
        diagnostic_from_runtime_error("kir", "unsupported kir statement")
    )


def parse_kir_expr_v0(raw: object) -> KIRExprV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir expression must be an object")
        )
    kind = raw.get("kind")
    if kind == "string":
        value = raw.get("value")
        if not isinstance(value, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir string requires value")
            )
        return KIRStringV0(value=value)
    if kind == "bool":
        value = raw.get("value")
        if not isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir bool requires value")
            )
        return KIRBoolV0(value=value)
    if kind == "int":
        value = raw.get("value")
        if not isinstance(value, int) or isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir int requires value")
            )
        return KIRIntV0(value=value)
    if kind == "var":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir var requires name")
            )
        return KIRVarV0(name=name)
    if kind == "concat":
        return KIRConcatV0(
            left=parse_kir_expr_v0(raw.get("left")),
            right=parse_kir_expr_v0(raw.get("right")),
        )
    if kind == "eq":
        return KIREqV0(
            left=parse_kir_expr_v0(raw.get("left")),
            right=parse_kir_expr_v0(raw.get("right")),
        )
    if kind == "if":
        return KIRIfExprV0(
            condition=parse_kir_expr_v0(raw.get("condition")),
            then_expr=parse_kir_expr_v0(raw.get("then")),
            else_expr=parse_kir_expr_v0(raw.get("else")),
        )
    if kind == "call_expr":
        callee = raw.get("callee")
        args = raw.get("args", [])
        if not isinstance(callee, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir call_expr requires callee and args")
            )
        return KIRCallExprV0(callee=callee, args=[parse_kir_expr_v0(item) for item in args])
    raise DiagnosticError(
        diagnostic_from_runtime_error("kir", "unsupported kir expression")
    )


def _parse_print_op(raw: object) -> str:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "print ops must be objects")
        )
    text = raw.get("text")
    if not isinstance(text, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "print ops require text")
        )
    return text


def kir_program_to_print_artifact(program: KIRProgramV0) -> PrintArtifactV1:
    if not _is_print_only_program(program):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "program is not a print-only KIR artifact")
        )
    texts: list[str] = []
    for stmt in program.instructions:
        if isinstance(stmt, KIRPrintV0) and isinstance(stmt.expr, KIRStringV0):
            texts.append(stmt.expr.value)
    return PrintArtifactV1(texts=texts)


def _is_print_only_program(program: KIRProgramV0) -> bool:
    return not program.functions and all(
        isinstance(stmt, KIRPrintV0) and isinstance(stmt.expr, KIRStringV0)
        for stmt in program.instructions
    )


def _inspect_expr(expr: KIRExprV0) -> dict[str, object]:
    if isinstance(expr, KIRStringV0):
        return {"kind": "string", "value": expr.value}
    if isinstance(expr, KIRBoolV0):
        return {"kind": "bool", "value": expr.value}
    if isinstance(expr, KIRIntV0):
        return {"kind": "int", "value": expr.value}
    if isinstance(expr, KIRVarV0):
        return {"kind": "var", "name": expr.name}
    if isinstance(expr, KIRConcatV0):
        return {"kind": "concat", "left": _inspect_expr(expr.left), "right": _inspect_expr(expr.right)}
    if isinstance(expr, KIREqV0):
        return {"kind": "eq", "left": _inspect_expr(expr.left), "right": _inspect_expr(expr.right)}
    if isinstance(expr, KIRIfExprV0):
        return {
            "kind": "if",
            "condition": _inspect_expr(expr.condition),
            "then": _inspect_expr(expr.then_expr),
            "else": _inspect_expr(expr.else_expr),
        }
    if isinstance(expr, KIRCallExprV0):
        return {"kind": "call_expr", "callee": expr.callee, "args": [_inspect_expr(arg) for arg in expr.args]}
    raise TypeError(f"unsupported kir expr: {expr!r}")


def _inspect_stmt(stmt: KIRStmtV0) -> dict[str, object]:
    if isinstance(stmt, KIRPrintV0):
        return {"op": "print", "expr": _inspect_expr(stmt.expr)}
    if isinstance(stmt, KIRLetV0):
        return {"op": "let", "name": stmt.name, "expr": _inspect_expr(stmt.expr)}
    if isinstance(stmt, KIRIfStmtV0):
        return {
            "op": "if",
            "condition": _inspect_expr(stmt.condition),
            "then": [_inspect_stmt(item) for item in stmt.then_body],
            "else": [_inspect_stmt(item) for item in stmt.else_body],
        }
    if isinstance(stmt, KIRCallV0):
        return {"op": "call", "name": stmt.name, "args": [_inspect_expr(arg) for arg in stmt.args]}
    if isinstance(stmt, KIRReturnV0):
        return {"op": "return", "expr": _inspect_expr(stmt.expr)}
    if isinstance(stmt, KIRExprStmtV0):
        return {"op": "expr", "expr": _inspect_expr(stmt.expr)}
    raise TypeError(f"unsupported kir stmt: {stmt!r}")


def inspect_kir_program(program: KIRProgramV0) -> dict[str, object]:
    if _is_print_only_program(program):
        return {
            "kind": "kir",
            "effect": "print",
            "ops": [{"text": stmt.text} for stmt in program.instructions],
            "stdout": artifact_v1_stdout(kir_program_to_print_artifact(program)),
        }
    return {
        "kind": "kir",
        "functions": [
            {
                "name": fn.name,
                "params": list(fn.params),
                "body": [_inspect_stmt(stmt) for stmt in fn.body],
            }
            for fn in program.functions
        ],
        "instructions": [_inspect_stmt(stmt) for stmt in program.instructions],
    }


def inspect_kir_artifact(program: KIRProgramV0) -> dict[str, object]:
    return inspect_kir_program(program)


def serialize_kir_program_v0(program: KIRProgramV0) -> str:
    if _is_print_only_program(program):
        return json.dumps(
            {
                "kind": "kir",
                "effect": "print",
                "ops": [{"text": stmt.text} for stmt in program.instructions],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    return json.dumps(inspect_kir_program(program), ensure_ascii=False, separators=(",", ":"))


def serialize_kir_program(program: KIRProgramV0) -> str:
    return serialize_kir_program_v0(program)


def execute_kir_program(program: KIRProgramV0) -> str:
    return artifact_v1_stdout(kir_program_to_print_artifact(program))


def parse_kir_program_v0(raw: object) -> KIRProgramV0:
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir program must be a string")
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", f"invalid kir json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict) or payload.get("kind") != "kir":
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "unsupported kir payload")
        )
    if payload.get("effect") == "print":
        ops = payload.get("ops", [])
        if not isinstance(ops, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "print kir requires ops")
            )
        instructions: list[KIRStmtV0] = []
        for item in ops:
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                raise DiagnosticError(
                    diagnostic_from_runtime_error("kir", "print kir ops require text")
                )
            instructions.append(KIRPrintV0(expr=KIRStringV0(value=item["text"])))
        return KIRProgramV0(instructions=instructions, functions=[])
    functions = payload.get("functions", [])
    instructions = payload.get("instructions", [])
    if not isinstance(functions, list) or not isinstance(instructions, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir program requires functions and instructions")
        )
    return KIRProgramV0(
        instructions=[parse_kir_stmt_v0(item) for item in instructions],
        functions=[parse_kir_function_v0(item) for item in functions],
    )


def parse_kir_function_v0(raw: object) -> KIRFunctionV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir function must be an object")
        )
    name = raw.get("name")
    params = raw.get("params", [])
    body = raw.get("body", [])
    if not isinstance(name, str) or not isinstance(params, list) or not isinstance(body, list):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir function requires name, params, and body")
        )
    if not all(isinstance(param, str) and param for param in params):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir params must be strings")
        )
    return KIRFunctionV0(
        name=name,
        params=list(params),
        body=[parse_kir_stmt_v0(item) for item in body],
    )


def parse_kir_stmt_v0(raw: object) -> KIRStmtV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir statement must be an object")
        )
    op = raw.get("op")
    if op == "print":
        return KIRPrintV0(expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "let":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir let requires name")
            )
        return KIRLetV0(name=name, expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "if":
        then_body = raw.get("then", [])
        else_body = raw.get("else", [])
        if not isinstance(then_body, list) or not isinstance(else_body, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir if requires then/else lists")
            )
        return KIRIfStmtV0(
            condition=parse_kir_expr_v0(raw.get("condition")),
            then_body=[parse_kir_stmt_v0(item) for item in then_body],
            else_body=[parse_kir_stmt_v0(item) for item in else_body],
        )
    if op == "call":
        name = raw.get("name")
        args = raw.get("args", [])
        if not isinstance(name, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir call requires name and args")
            )
        return KIRCallV0(name=name, args=[parse_kir_expr_v0(item) for item in args])
    if op == "return":
        return KIRReturnV0(expr=parse_kir_expr_v0(raw.get("expr")))
    if op == "expr":
        return KIRExprStmtV0(expr=parse_kir_expr_v0(raw.get("expr")))
    raise DiagnosticError(
        diagnostic_from_runtime_error("kir", "unsupported kir statement")
    )


def parse_kir_expr_v0(raw: object) -> KIRExprV0:
    if not isinstance(raw, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("kir", "kir expression must be an object")
        )
    kind = raw.get("kind")
    if kind == "string":
        value = raw.get("value")
        if not isinstance(value, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir string requires value")
            )
        return KIRStringV0(value=value)
    if kind == "bool":
        value = raw.get("value")
        if not isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir bool requires value")
            )
        return KIRBoolV0(value=value)
    if kind == "int":
        value = raw.get("value")
        if not isinstance(value, int) or isinstance(value, bool):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir int requires integer value")
            )
        return KIRIntV0(value=value)
    if kind == "var":
        name = raw.get("name")
        if not isinstance(name, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir var requires name")
            )
        return KIRVarV0(name=name)
    if kind == "concat":
        return KIRConcatV0(
            left=parse_kir_expr_v0(raw.get("left")),
            right=parse_kir_expr_v0(raw.get("right")),
        )
    if kind == "eq":
        return KIREqV0(
            left=parse_kir_expr_v0(raw.get("left")),
            right=parse_kir_expr_v0(raw.get("right")),
        )
    if kind == "if":
        return KIRIfExprV0(
            condition=parse_kir_expr_v0(raw.get("condition")),
            then_expr=parse_kir_expr_v0(raw.get("then")),
            else_expr=parse_kir_expr_v0(raw.get("else")),
        )
    if kind == "call_expr":
        callee = raw.get("callee")
        args = raw.get("args", [])
        if not isinstance(callee, str) or not isinstance(args, list):
            raise DiagnosticError(
                diagnostic_from_runtime_error("kir", "kir call_expr requires callee and args")
            )
        return KIRCallExprV0(callee=callee, args=[parse_kir_expr_v0(item) for item in args])
    raise DiagnosticError(
        diagnostic_from_runtime_error("kir", "unsupported kir expression")
    )
