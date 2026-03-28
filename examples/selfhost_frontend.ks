fn extract_text(source) {
  let text = extract_quoted(trim(source));
  if eq(text, "") {
    return "";
  } else {
    return text;
  }
}

fn parse(source) {
  let text = extract_text(source);
  if eq(text, "") {
    return "error: expected quoted string";
  } else {
    return program_ast(text);
  }
}

fn check_ast(ast) {
  let text = program_text(ast);
  if eq(text, "") {
    return "error: invalid program ast";
  } else {
    return "ok";
  }
}

fn lower_ast(ast) {
  let text = program_text(ast);
  if eq(text, "") {
    return "error: invalid program ast";
  } else {
    return print_ast(text);
  }
}

fn check(source) {
  let ast = parse(source);
  if eq(ast, "error: expected quoted string") {
    return ast;
  } else {
    return check_ast(ast);
  }
}

fn lower(source) {
  let ast = parse(source);
  if eq(ast, "error: expected quoted string") {
    return ast;
  } else {
    return lower_ast(ast);
  }
}

fn compile(source) {
  return lower(source);
}
