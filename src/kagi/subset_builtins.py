from __future__ import annotations


def builtin_eq(left: object, right: object) -> bool:
    return left == right


def builtin_concat(left: object, right: object) -> str:
    return f"{left}{right}"


def builtin_extract_quoted(text: object) -> str:
    if not isinstance(text, str):
        return ""
    start = text.find('"')
    if start == -1:
        return ""
    end = text.find('"', start + 1)
    if end == -1:
        return ""
    return text[start + 1:end]


def builtin_trim(text: object) -> str:
    return text.strip() if isinstance(text, str) else ""


def builtin_starts_with(text: object, prefix: object) -> bool:
    return isinstance(text, str) and isinstance(prefix, str) and text.startswith(prefix)


def builtin_ends_with(text: object, suffix: object) -> bool:
    return isinstance(text, str) and isinstance(suffix, str) and text.endswith(suffix)


def builtin_line_count(text: object) -> int:
    if not isinstance(text, str):
        return 0
    return len([line.strip() for line in text.splitlines() if line.strip()])


def builtin_line_at(text: object, index: object) -> str:
    if not isinstance(text, str) or not isinstance(index, int):
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if index < 0 or index >= len(lines):
        return ""
    return lines[index]


def builtin_before_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[:pos]


def builtin_after_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[pos + len(needle):]


def builtin_is_identifier(text: object) -> bool:
    return isinstance(text, str) and text != "" and text.replace("_", "").isalnum()


CORE_BUILTINS = {
    "after_substring": builtin_after_substring,
    "before_substring": builtin_before_substring,
    "eq": builtin_eq,
    "concat": builtin_concat,
    "ends_with": builtin_ends_with,
    "extract_quoted": builtin_extract_quoted,
    "is_identifier": builtin_is_identifier,
    "line_at": builtin_line_at,
    "line_count": builtin_line_count,
    "starts_with": builtin_starts_with,
    "trim": builtin_trim,
}
