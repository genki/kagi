fn try_parse_single_print(source) {
  let text = trim(source);
  let q = quote();
  let prefix = concat("print ", q);
  if starts_with(text, prefix) {
    if ends_with(text, q) {
      let quoted = extract_quoted(text);
      let rebuilt = concat(prefix, concat(quoted, q));
      if eq(rebuilt, text) {
        return program_ast(quoted);
      } else {
        return "";
      }
    } else {
      return "";
    }
  } else {
    return "";
  }
}

fn parse(source) {
  let simple = try_parse_single_print(source);
  if eq(simple, "") {
    let ast = parse_print_program(source);
    if eq(ast, "") {
      return "error: expected quoted string";
    } else {
      return ast;
    }
  } else {
    return simple;
  }
}

fn check_ast(ast) {
  return validate_program_ast(ast);
}

fn lower_ast(ast) {
  return lower_program_artifact(ast);
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
