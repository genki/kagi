from __future__ import annotations

from dataclasses import dataclass
import json

from .diagnostics import DiagnosticError, diagnostic_from_runtime_error


@dataclass(frozen=True)
class PrintArtifactV1:
    texts: list[str]


def parse_artifact_v1(raw: object) -> PrintArtifactV1:
    if isinstance(raw, PrintArtifactV1):
        return raw
    if not isinstance(raw, str):
        raise DiagnosticError(
            diagnostic_from_runtime_error("artifact", "artifact must be a string")
        )
    if raw.startswith("error:"):
        raise DiagnosticError(
            diagnostic_from_runtime_error("artifact", raw)
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DiagnosticError(
            diagnostic_from_runtime_error("artifact", f"invalid artifact json: {exc.msg}")
        ) from exc
    if not isinstance(payload, dict):
        raise DiagnosticError(
            diagnostic_from_runtime_error("artifact", "artifact must decode to an object")
        )
    kind = payload.get("kind")
    if kind == "print_many":
        texts = payload.get("texts")
        if not isinstance(texts, list) or not all(isinstance(text, str) for text in texts):
            raise DiagnosticError(
                diagnostic_from_runtime_error("artifact", "print_many artifact requires string texts")
            )
        return PrintArtifactV1(texts=list(texts))
    if kind == "print":
        text = payload.get("text")
        if not isinstance(text, str):
            raise DiagnosticError(
                diagnostic_from_runtime_error("artifact", "print artifact requires string text")
            )
        return PrintArtifactV1(texts=[text])
    raise DiagnosticError(
        diagnostic_from_runtime_error("artifact", f"unsupported artifact kind: {kind}")
    )


def artifact_v1_to_json(artifact: PrintArtifactV1) -> str:
    return json.dumps({"kind": "print_many", "texts": artifact.texts}, ensure_ascii=False, separators=(",", ":"))


def artifact_v1_stdout(artifact: PrintArtifactV1) -> str:
    return "\n".join(artifact.texts)
