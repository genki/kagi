from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    phase: str
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    snippet: str | None = None

    def to_json(self) -> dict[str, object | None]:
        return {
            "phase": self.phase,
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "snippet": self.snippet,
        }


class DiagnosticError(RuntimeError):
    def __init__(self, diagnostic: Diagnostic):
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


def diagnostic_from_runtime_error(phase: str, message: str) -> Diagnostic:
    return Diagnostic(
        phase=phase,
        code=f"{phase}_error",
        message=message,
        line=None,
        column=None,
        snippet=None,
    )
