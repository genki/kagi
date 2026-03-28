fn compile(source) {
  let text = extract_quoted(trim(source));
  if eq(text, "") {
    return "error: expected quoted string";
  } else {
    return text;
  }
}
