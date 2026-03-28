fn parse(source) {
  let ast = parse_print_program(source);
  if eq(ast, "") {
    return "error: expected quoted string";
  } else {
    return ast;
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
