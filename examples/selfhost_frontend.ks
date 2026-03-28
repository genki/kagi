fn extract_text(source) {
  let text = extract_quoted(trim(source));
  if eq(text, "") {
    return "";
  } else {
    return text;
  }
}

fn check(source) {
  let text = extract_text(source);
  if eq(text, "") {
    return "error: expected quoted string";
  } else {
    return "ok";
  }
}

fn lower(source) {
  let text = extract_text(source);
  if eq(text, "") {
    return "error: expected quoted string";
  } else {
    return concat("emit:", text);
  }
}

fn compile(source) {
  return lower(source);
}
