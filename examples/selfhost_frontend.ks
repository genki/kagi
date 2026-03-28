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

fn try_parse_simple_let_print(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    let delim = concat(" = ", q);
    if starts_with(line1, "let ") {
      let rest = after_substring(line1, "let ");
      let name = before_substring(rest, delim);
      let quoted = extract_quoted(line1);
      let rebuilt1 = concat("let ", concat(name, concat(delim, concat(quoted, q))));
      let rebuilt2 = concat("print ", name);
      if is_identifier(name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            return program_let_print_ast(name, quoted);
          } else {
            return "";
          }
        } else {
          return "";
        }
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

fn try_parse_simple_single_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 4) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let q = quote();
    if eq(line3, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "{") {
          if starts_with(line2, "print concat(") {
            if starts_with(line4, "call ") {
              let fn_header = after_substring(line1, "fn ");
              let fn_name = before_substring(fn_header, "(");
              let fn_rest = after_substring(fn_header, "(");
              let param_name = before_substring(fn_rest, ") {");
              let suffix = extract_quoted(line2);
              let call_header = after_substring(line4, "call ");
              let call_name = before_substring(call_header, "(");
              let arg_text = extract_quoted(line4);
              let rebuilt1 = concat("fn ", concat(fn_name, concat("(", concat(param_name, ") {"))));
              let rebuilt2 = concat(
                "print concat(",
                concat(param_name, concat(", ", concat(q, concat(suffix, concat(q, ")")))))
              );
              let rebuilt4 = concat(
                "call ",
                concat(call_name, concat("(", concat(q, concat(arg_text, concat(q, ")")))))
              );
              if is_identifier(fn_name) {
                if is_identifier(param_name) {
                  if eq(fn_name, call_name) {
                    if eq(rebuilt1, line1) {
                      if eq(rebuilt2, line2) {
                        if eq(rebuilt4, line4) {
                          return program_single_arg_fn_call_ast(fn_name, param_name, arg_text, suffix);
                        } else {
                          return "";
                        }
                      } else {
                        return "";
                      }
                    } else {
                      return "";
                    }
                  } else {
                    return "";
                  }
                } else {
                  return "";
                }
              } else {
                return "";
              }
            } else {
              return "";
            }
          } else {
            return "";
          }
        } else {
          return "";
        }
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
    let simple_let = try_parse_simple_let_print(source);
    if eq(simple_let, "") {
      let simple_fn = try_parse_simple_single_arg_fn_call(source);
      if eq(simple_fn, "") {
        let ast = parse_print_program(source);
        if eq(ast, "") {
          return "error: expected quoted string";
        } else {
          return ast;
        }
      } else {
        return simple_fn;
      }
    } else {
      return simple_let;
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
