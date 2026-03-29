from __future__ import annotations


def intrinsic_eq(left: object, right: object) -> bool:
    return left == right


def intrinsic_concat(left: object, right: object) -> str:
    return f"{left}{right}"


def intrinsic_extract_quoted(text: object) -> str:
    if not isinstance(text, str):
        return ""
    start = text.find('"')
    if start == -1:
        return ""
    end = text.find('"', start + 1)
    if end == -1:
        return ""
    return text[start + 1:end]


def intrinsic_trim(text: object) -> str:
    return text.strip() if isinstance(text, str) else ""


def intrinsic_starts_with(text: object, prefix: object) -> bool:
    return isinstance(text, str) and isinstance(prefix, str) and text.startswith(prefix)


def intrinsic_ends_with(text: object, suffix: object) -> bool:
    return isinstance(text, str) and isinstance(suffix, str) and text.endswith(suffix)


def intrinsic_line_count(text: object) -> int:
    if not isinstance(text, str):
        return 0
    return len([line.strip() for line in text.splitlines() if line.strip()])


def intrinsic_line_at(text: object, index: object) -> str:
    if not isinstance(text, str) or not isinstance(index, int):
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if index < 0 or index >= len(lines):
        return ""
    return lines[index]


def intrinsic_before_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[:pos]


def intrinsic_after_substring(text: object, needle: object) -> str:
    if not isinstance(text, str) or not isinstance(needle, str):
        return ""
    pos = text.find(needle)
    if pos == -1:
        return ""
    return text[pos + len(needle):]


def intrinsic_is_identifier(text: object) -> bool:
    return isinstance(text, str) and text != "" and text.replace("_", "").isalnum()


builtin_eq = intrinsic_eq
builtin_concat = intrinsic_concat
builtin_extract_quoted = intrinsic_extract_quoted
builtin_trim = intrinsic_trim
builtin_starts_with = intrinsic_starts_with
builtin_ends_with = intrinsic_ends_with
builtin_line_count = intrinsic_line_count
builtin_line_at = intrinsic_line_at
builtin_before_substring = intrinsic_before_substring
builtin_after_substring = intrinsic_after_substring
builtin_is_identifier = intrinsic_is_identifier


CORE_BUILTINS: dict[str, object] = {}
