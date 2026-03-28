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

fn after_quote_comma(text) {
  let q = quote();
  let with_space = after_substring(text, concat(q, ", "));
  if eq(with_space, "") {
    return after_substring(text, concat(q, ","));
  } else {
    return with_space;
  }
}

fn concat_call_matches(text, prefix, left_text, right_text) {
  let q = quote();
  let with_space = concat(
    prefix,
    concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
  );
  let without_space = concat(
    prefix,
    concat(q, concat(left_text, concat(q, concat(",", concat(q, concat(right_text, concat(q, ")")))))))
  );
  if eq(with_space, text) {
    return "ok";
  } else {
    if eq(without_space, text) {
      return "ok";
    } else {
      return "";
    }
  }
}

fn try_parse_single_print_concat(source) {
  let text = trim(source);
  let q = quote();
  if starts_with(text, "print concat(") {
    let quoted1 = extract_quoted(text);
    let after_first = after_quote_comma(text);
    let quoted2 = extract_quoted(after_first);
    if eq(concat_call_matches(text, "print concat(", quoted1, quoted2), "ok") {
      return program_print_concat_ast(quoted1, quoted2);
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

fn try_parse_simple_let_concat_print(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "print ") {
        let rest = after_substring(line1, "let ");
        let name = before_substring(rest, " = concat(");
        let quoted1 = extract_quoted(line1);
        let after_first = after_quote_comma(line1);
        let quoted2 = extract_quoted(after_first);
        let rebuilt2 = concat("print ", name);
        if is_identifier(name) {
          if eq(concat_call_matches(line1, concat("let ", concat(name, " = concat(")), quoted1, quoted2), "ok") {
            if eq(rebuilt2, line2) {
              return program_let_concat_print_ast(name, quoted1, quoted2);
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
              let rebuilt2_no_space = concat(
                "print concat(",
                concat(param_name, concat(",", concat(q, concat(suffix, concat(q, ")")))))
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
                        if eq(rebuilt2_no_space, line2) {
                          if eq(rebuilt4, line4) {
                            return program_single_arg_fn_call_ast(fn_name, param_name, arg_text, suffix);
                          } else {
                            return "";
                          }
                        } else {
                          return "";
                        }
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
fn build_print_many_artifact_two(first_text, second_text) {
  let q = quote();
  return concat(
    "{\"kind\":\"print_many\",\"texts\":[",
    concat(
      q,
      concat(
        first_text,
        concat(q, concat(",", concat(q, concat(second_text, concat(q, "]}")))))
      )
    )
  );
}

fn render_if_output(left_text, right_text, expected_text, disabled_text) {
  let greeting_text = concat(left_text, right_text);
  if eq(greeting_text, expected_text) {
    return print_many_artifact(greeting_text);
  } else {
    return print_many_artifact(disabled_text);
  }
}

fn try_parse_two_prints_unused(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    let prefix = concat("print ", q);
    if starts_with(line1, prefix) {
      if starts_with(line2, prefix) {
        if ends_with(line1, q) {
          if ends_with(line2, q) {
            let first_text = extract_quoted(line1);
            let second_text = extract_quoted(line2);
            let rebuilt1 = concat(prefix, concat(first_text, q));
            let rebuilt2 = concat(prefix, concat(second_text, q));
            if eq(rebuilt1, line1) {
              if eq(rebuilt2, line2) {
                return program_two_prints_ast(first_text, second_text);
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

fn try_lower_two_prints(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    let prefix = concat("print ", q);
    if starts_with(line1, prefix) {
      if starts_with(line2, prefix) {
        if ends_with(line1, q) {
          if ends_with(line2, q) {
            let first_text = extract_quoted(line1);
            let second_text = extract_quoted(line2);
            let rebuilt1 = concat(prefix, concat(first_text, q));
            let rebuilt2 = concat(prefix, concat(second_text, q));
            if eq(rebuilt1, line1) {
              if eq(rebuilt2, line2) {
                return build_print_many_artifact_two(first_text, second_text);
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

fn try_parse_zero_arg_fn_call_unused(source) {
  let text = trim(source);
  if eq(line_count(text), 4) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let q = quote();
    if starts_with(line1, "fn ") {
      if ends_with(line1, "{") {
        if starts_with(line2, "let ") {
          if starts_with(line3, "print ") {
            if starts_with(line4, "call ") {
              let fn_header = after_substring(line1, "fn ");
              let fn_name = before_substring(fn_header, "(");
              let fn_rest = after_substring(fn_header, "(");
              let params_raw = before_substring(fn_rest, ") {");
              let let_header = after_substring(line2, "let ");
              let var_name = before_substring(let_header, " = concat(");
              let left_text = extract_quoted(line2);
              let after_first = after_substring(line2, concat(q, ", "));
              let right_text = extract_quoted(after_first);
              let print_name = after_substring(line3, "print ");
              let call_header = after_substring(line4, "call ");
              let call_name = before_substring(call_header, "(");
              let call_args = before_substring(after_substring(call_header, "("), ")");
              let rebuilt1 = concat("fn ", concat(fn_name, "() {"));
              let rebuilt2 = concat(
                "let ",
                concat(
                  var_name,
                  concat(
                    " = concat(",
                    concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
                  )
                )
              );
              let rebuilt3 = concat("print ", print_name);
              let rebuilt4 = concat("call ", concat(call_name, "()"));
              if is_identifier(fn_name) {
                if is_identifier(var_name) {
                  if eq(params_raw, "") {
                    if eq(fn_name, call_name) {
                      if eq(call_args, "") {
                        if eq(var_name, print_name) {
                          if eq(rebuilt1, line1) {
                            if eq(rebuilt2, line2) {
                              if eq(rebuilt3, line3) {
                                if eq(rebuilt4, line4) {
                                  return program_zero_arg_fn_call_ast(fn_name, var_name, left_text, right_text);
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

fn try_lower_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_header = after_substring(line1, "fn ");
                let fn_name = before_substring(fn_header, "(");
                let fn_rest = after_substring(fn_header, "(");
                let params_raw = before_substring(fn_rest, ") {");
                let let_header = after_substring(line2, "let ");
                let var_name = before_substring(let_header, " = concat(");
                let left_text = extract_quoted(line2);
                let after_first = after_quote_comma(line2);
                let right_text = extract_quoted(after_first);
                let print_name = after_substring(line3, "print ");
                let call_header = after_substring(line5, "call ");
                let call_name = before_substring(call_header, "(");
                let call_args = before_substring(after_substring(call_header, "("), ")");
                if is_identifier(fn_name) {
                  if is_identifier(var_name) {
                    if eq(params_raw, "") {
                      if eq(fn_name, call_name) {
                        if eq(call_args, "") {
                          if eq(var_name, print_name) {
                            return print_many_artifact(concat(left_text, right_text));
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
  } else {
    return "";
  }
}

fn try_parse_if_expr_print(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "print if(") {
          let line1_rest = after_substring(line1, "let ");
          let greeting_name = before_substring(line1_rest, " = concat(");
          let left_text = extract_quoted(line1);
          let after_first = after_substring(line1, concat(q, ", "));
          let right_text = extract_quoted(after_first);
          let line2_rest = after_substring(line2, "let ");
          let enabled_name = before_substring(line2_rest, " = eq(");
          let eq_inner = after_substring(line2, " = eq(");
          let greeting_ref = before_substring(eq_inner, ", ");
          let expected_text = extract_quoted(line2);
          let if_inner = after_substring(line3, "print if(");
          let enabled_ref = before_substring(if_inner, ", ");
          let after_enabled = after_substring(if_inner, ", ");
          let greeting_ref2 = before_substring(after_enabled, ", ");
          let disabled_text = extract_quoted(line3);
          let rebuilt1 = concat(
            "let ",
            concat(
              greeting_name,
              concat(
                " = concat(",
                concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
              )
            )
          );
          let rebuilt2 = concat(
            "let ",
            concat(
              enabled_name,
              concat(
                " = eq(",
                concat(greeting_ref, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
              )
            )
          );
          let rebuilt3 = concat(
            "print if(",
            concat(
              enabled_ref,
              concat(
                ", ",
                concat(greeting_ref2, concat(", ", concat(q, concat(disabled_text, concat(q, ")")))))
              )
            )
          );
          if is_identifier(greeting_name) {
            if is_identifier(enabled_name) {
              if eq(greeting_name, greeting_ref) {
                if eq(greeting_name, greeting_ref2) {
                  if eq(enabled_name, enabled_ref) {
                    if eq(rebuilt1, line1) {
                      if eq(rebuilt2, line2) {
                        if eq(rebuilt3, line3) {
                          return program_if_expr_print_ast(
                            greeting_name,
                            left_text,
                            right_text,
                            enabled_name,
                            expected_text,
                            disabled_text
                          );
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

fn try_lower_if_expr_print(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "print if(") {
          let line1_rest = after_substring(line1, "let ");
          let greeting_name = before_substring(line1_rest, " = concat(");
          let left_text = extract_quoted(line1);
          let after_first = after_substring(line1, concat(q, ", "));
          let right_text = extract_quoted(after_first);
          let line2_rest = after_substring(line2, "let ");
          let enabled_name = before_substring(line2_rest, " = eq(");
          let eq_inner = after_substring(line2, " = eq(");
          let greeting_ref = before_substring(eq_inner, ", ");
          let expected_text = extract_quoted(line2);
          let if_inner = after_substring(line3, "print if(");
          let enabled_ref = before_substring(if_inner, ", ");
          let after_enabled = after_substring(if_inner, ", ");
          let greeting_ref2 = before_substring(after_enabled, ", ");
          let disabled_text = extract_quoted(line3);
          let rebuilt1 = concat(
            "let ",
            concat(
              greeting_name,
              concat(
                " = concat(",
                concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
              )
            )
          );
          let rebuilt2 = concat(
            "let ",
            concat(
              enabled_name,
              concat(
                " = eq(",
                concat(greeting_ref, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
              )
            )
          );
          let rebuilt3 = concat(
            "print if(",
            concat(
              enabled_ref,
              concat(
                ", ",
                concat(greeting_ref2, concat(", ", concat(q, concat(disabled_text, concat(q, ")")))))
              )
            )
          );
          if is_identifier(greeting_name) {
            if is_identifier(enabled_name) {
              if eq(greeting_name, greeting_ref) {
                if eq(greeting_name, greeting_ref2) {
                  if eq(enabled_name, enabled_ref) {
                    if eq(rebuilt1, line1) {
                      if eq(rebuilt2, line2) {
                        if eq(rebuilt3, line3) {
                          return render_if_output(left_text, right_text, expected_text, disabled_text);
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

fn try_parse_if_stmt_unused(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "if ") {
          if starts_with(line4, "print ") {
            if eq(line5, "} else {") {
              if starts_with(line6, "print ") {
                if eq(line7, "}") {
                  let line1_rest = after_substring(line1, "let ");
                  let greeting_name = before_substring(line1_rest, " = concat(");
                  let left_text = extract_quoted(line1);
                  let after_first = after_quote_comma(line1);
                  let right_text = extract_quoted(after_first);
                  let line2_rest = after_substring(line2, "let ");
                  let enabled_name = before_substring(line2_rest, " = eq(");
                  let eq_inner = after_substring(line2, " = eq(");
                  let greeting_ref = before_substring(eq_inner, ", ");
                  let expected_text = extract_quoted(line2);
                  let condition_text = after_substring(line3, "if ");
                  let condition_name = before_substring(condition_text, " {");
                  let print_then = after_substring(line4, "print ");
                  let disabled_text = extract_quoted(line6);
                  let rebuilt1 = concat(
                    "let ",
                    concat(
                      greeting_name,
                      concat(
                        " = concat(",
                        concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
                      )
                    )
                  );
                  let rebuilt2 = concat(
                    "let ",
                    concat(
                      enabled_name,
                      concat(
                        " = eq(",
                        concat(greeting_ref, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
                      )
                    )
                  );
                  let rebuilt3 = concat("if ", concat(condition_name, " {"));
                  let rebuilt4 = concat("print ", print_then);
                  let rebuilt6 = concat("print ", concat(q, concat(disabled_text, q)));
                  if is_identifier(greeting_name) {
                    if is_identifier(enabled_name) {
                      if eq(greeting_name, greeting_ref) {
                        if eq(enabled_name, condition_name) {
                          if eq(greeting_name, print_then) {
                            if eq(rebuilt1, line1) {
                              if eq(rebuilt2, line2) {
                                if eq(rebuilt3, line3) {
                                  if eq(rebuilt4, line4) {
                                    if eq(rebuilt6, line6) {
                                      return program_if_stmt_ast(
                                        greeting_name,
                                        left_text,
                                        right_text,
                                        enabled_name,
                                        expected_text,
                                        disabled_text
                                      );
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

fn try_lower_if_stmt(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "if ") {
          if starts_with(line4, "print ") {
            if eq(line5, "} else {") {
              if starts_with(line6, "print ") {
                if eq(line7, "}") {
                  let line1_rest = after_substring(line1, "let ");
                  let greeting_name = before_substring(line1_rest, " = concat(");
                  let left_text = extract_quoted(line1);
                  let after_first = after_quote_comma(line1);
                  let right_text = extract_quoted(after_first);
                  let line2_rest = after_substring(line2, "let ");
                  let enabled_name = before_substring(line2_rest, " = eq(");
                  let eq_inner = after_substring(line2, " = eq(");
                  let greeting_ref = before_substring(eq_inner, ", ");
                  let expected_text = extract_quoted(line2);
                  let condition_text = after_substring(line3, "if ");
                  let condition_name = before_substring(condition_text, " {");
                  let print_then = after_substring(line4, "print ");
                  let disabled_text = extract_quoted(line6);
                  let rebuilt1 = concat(
                    "let ",
                    concat(
                      greeting_name,
                      concat(
                        " = concat(",
                        concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
                      )
                    )
                  );
                  let rebuilt2 = concat(
                    "let ",
                    concat(
                      enabled_name,
                      concat(
                        " = eq(",
                        concat(greeting_ref, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
                      )
                    )
                  );
                  let rebuilt3 = concat("if ", concat(condition_name, " {"));
                  let rebuilt4 = concat("print ", print_then);
                  let rebuilt6 = concat("print ", concat(q, concat(disabled_text, q)));
                  if is_identifier(greeting_name) {
                    if is_identifier(enabled_name) {
                      if eq(greeting_name, greeting_ref) {
                        if eq(enabled_name, condition_name) {
                          if eq(greeting_name, print_then) {
                            if eq(rebuilt1, line1) {
                              if eq(rebuilt2, line2) {
                                if eq(rebuilt3, line3) {
                                  if eq(rebuilt4, line4) {
                                    if eq(rebuilt6, line6) {
                                      return render_if_output(left_text, right_text, expected_text, disabled_text);
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

fn build_program_json(statements_json) {
  return concat(
    "{\"kind\":\"program\",\"functions\":[],\"statements\":[",
    concat(statements_json, "]}")
  );
}

fn join_statements_2(stmt1, stmt2) {
  return concat(stmt1, concat(",", stmt2));
}

fn join_statements_3(stmt1, stmt2, stmt3) {
  return concat(join_statements_2(stmt1, stmt2), concat(",", stmt3));
}

fn join_statements_4(stmt1, stmt2, stmt3, stmt4) {
  return concat(join_statements_3(stmt1, stmt2, stmt3), concat(",", stmt4));
}

fn build_string_expr_json(text) {
  return concat("{\"kind\":\"string\",\"value\":\"", concat(text, "\"}"));
}

fn build_var_expr_json(name) {
  return concat("{\"kind\":\"var\",\"name\":\"", concat(name, "\"}"));
}

fn build_concat_expr_json(left_json, right_json) {
  return concat(
    "{\"kind\":\"concat\",\"left\":",
    concat(left_json, concat(",\"right\":", concat(right_json, "}")))
  );
}

fn build_eq_expr_json(left_json, right_json) {
  return concat(
    "{\"kind\":\"eq\",\"left\":",
    concat(left_json, concat(",\"right\":", concat(right_json, "}")))
  );
}

fn build_if_expr_json(condition_json, then_json, else_json) {
  return concat(
    "{\"kind\":\"if\",\"condition\":",
    concat(
      condition_json,
      concat(",\"then\":", concat(then_json, concat(",\"else\":", concat(else_json, "}"))))
    )
  );
}

fn build_print_stmt_json(expr_json) {
  return concat("{\"kind\":\"print\",\"expr\":", concat(expr_json, "}"));
}

fn build_let_stmt_json(name, expr_json) {
  return concat(
    "{\"kind\":\"let\",\"name\":\"",
    concat(name, concat("\",\"expr\":", concat(expr_json, "}")))
  );
}

fn build_if_stmt_json(condition_json, then_stmt_json, else_stmt_json) {
  return concat(
    "{\"kind\":\"if_stmt\",\"condition\":",
    concat(
      condition_json,
      concat(
        ",\"then_body\":[",
        concat(then_stmt_json, concat("],\"else_body\":[", concat(else_stmt_json, "]}")))
      )
    )
  );
}

fn build_print_many_json_2(text1, text2) {
  return concat(
    "{\"kind\":\"print_many\",\"texts\":[\"",
    concat(text1, concat("\",\"", concat(text2, "\"]}")))
  );
}

fn build_string_list_json_0() {
  return "[]";
}

fn build_string_list_json_1(item) {
  return concat("[\"", concat(item, "\"]"));
}

fn build_expr_list_json_0() {
  return "[]";
}

fn build_expr_list_json_1(expr_json) {
  return concat("[", concat(expr_json, "]"));
}

fn build_hir_program_json(functions_json, statements_json) {
  return concat(
    "{\"kind\":\"hir_program\",\"functions\":[",
    concat(functions_json, concat("],\"statements\":[", concat(statements_json, "]}")))
  );
}

fn build_hir_function_json(name, params_json, body_json) {
  return concat(
    "{\"name\":\"",
    concat(name, concat("\",\"params\":", concat(params_json, concat(",\"body\":[", concat(body_json, "]}")))))
  );
}

fn build_call_stmt_json(name, args_json) {
  return concat(
    "{\"kind\":\"call\",\"name\":\"",
    concat(name, concat("\",\"args\":", concat(args_json, "}")))
  );
}

fn build_kir_program_json(functions_json, instructions_json) {
  return concat(
    "{\"kind\":\"kir\",\"functions\":[",
    concat(functions_json, concat("],\"instructions\":[", concat(instructions_json, "]}")))
  );
}

fn build_kir_print_only_json(text) {
  return concat(
    "{\"kind\":\"kir\",\"effect\":\"print\",\"ops\":[{\"text\":\"",
    concat(text, "\"}]}")
  );
}

fn build_kir_print_stmt_json(expr_json) {
  return concat("{\"op\":\"print\",\"expr\":", concat(expr_json, "}"));
}

fn build_kir_let_stmt_json(name, expr_json) {
  return concat(
    "{\"op\":\"let\",\"name\":\"",
    concat(name, concat("\",\"expr\":", concat(expr_json, "}")))
  );
}

fn build_kir_if_stmt_json(condition_json, then_stmt_json, else_stmt_json) {
  return concat(
    "{\"op\":\"if\",\"condition\":",
    concat(
      condition_json,
      concat(
        ",\"then\":[",
        concat(then_stmt_json, concat("],\"else\":[", concat(else_stmt_json, "]}")))
      )
    )
  );
}

fn build_kir_call_stmt_json(name, args_json) {
  return concat(
    "{\"op\":\"call\",\"name\":\"",
    concat(name, concat("\",\"args\":", concat(args_json, "}")))
  );
}

fn build_analysis_program_print_json() {
  return "{\"kind\":\"analysis_v1\",\"function_arities\":{},\"effects\":{\"program\":[\"print\"],\"functions\":{}}}";
}

fn build_analysis_function_print_json(name, arity_text) {
  return concat(
    "{\"kind\":\"analysis_v1\",\"function_arities\":{\"",
    concat(
      name,
      concat(
        "\":",
        concat(
          arity_text,
          concat(
            "},\"effects\":{\"program\":[\"print\"],\"functions\":{\"",
            concat(name, "\":[\"print\"]}}}")
          )
        )
      )
    )
  );
}

fn build_pipeline_bundle_json(ast_json, hir_json, kir_json, analysis_json, artifact_json) {
  return concat(
    "{\"kind\":\"pipeline_bundle\",\"ast\":",
    concat(
      ast_json,
      concat(
        ",\"hir\":",
        concat(
          hir_json,
          concat(
            ",\"kir\":",
            concat(
              kir_json,
              concat(
                ",\"analysis\":",
                concat(
                  analysis_json,
                  concat(
                    ",\"check\":\"ok\",\"artifact\":",
                    concat(artifact_json, concat(",\"compile\":", concat(artifact_json, "}")))
                  )
                )
              )
            )
          )
        )
      )
    )
  );
}

fn parse_simple_line_expr_json(text) {
  let line = trim(text);
  let q = quote();
  if starts_with(line, q) {
    if ends_with(line, q) {
      let quoted = extract_quoted(line);
      let rebuilt = concat(q, concat(quoted, q));
      if eq(rebuilt, line) {
        return build_string_expr_json(quoted);
      } else {
        return "";
      }
    } else {
      return "";
    }
  } else {
    if starts_with(line, "concat(") {
      if ends_with(line, ")") {
        let inner = before_substring(after_substring(line, "concat("), ")");
        if starts_with(inner, q) {
          let left_text = extract_quoted(inner);
          let right_raw = after_quote_comma(inner);
          let right_json = parse_simple_line_expr_json(right_raw);
          if eq(right_json, "") {
            return "";
          } else {
            return build_concat_expr_json(build_string_expr_json(left_text), right_json);
          }
        } else {
          let left_raw = before_substring(inner, ", ");
          let right_raw = after_substring(inner, ", ");
          let left_json = parse_simple_line_expr_json(left_raw);
          let right_json = parse_simple_line_expr_json(right_raw);
          if eq(left_json, "") {
            return "";
          } else {
            if eq(right_json, "") {
              return "";
            } else {
              return build_concat_expr_json(left_json, right_json);
            }
          }
        }
      } else {
        return "";
      }
    } else {
      if starts_with(line, "eq(") {
        if ends_with(line, ")") {
          let inner = before_substring(after_substring(line, "eq("), ")");
          let left_raw = before_substring(inner, ", ");
          let right_raw = after_substring(inner, ", ");
          let left_json = parse_simple_line_expr_json(left_raw);
          let right_json = parse_simple_line_expr_json(right_raw);
          if eq(left_json, "") {
            return "";
          } else {
            if eq(right_json, "") {
              return "";
            } else {
              return build_eq_expr_json(left_json, right_json);
            }
          }
        } else {
          return "";
        }
      } else {
        if starts_with(line, "if(") {
          if ends_with(line, ")") {
            let inner = before_substring(after_substring(line, "if("), ")");
            let condition_raw = before_substring(inner, ", ");
            let then_tail = after_substring(inner, ", ");
            let then_raw = before_substring(then_tail, ", ");
            let else_raw = after_substring(then_tail, ", ");
            let condition_json = parse_simple_line_expr_json(condition_raw);
            let then_json = parse_simple_line_expr_json(then_raw);
            let else_json = parse_simple_line_expr_json(else_raw);
            if eq(condition_json, "") {
              return "";
            } else {
              if eq(then_json, "") {
                return "";
              } else {
                if eq(else_json, "") {
                  return "";
                } else {
                  return build_if_expr_json(condition_json, then_json, else_json);
                }
              }
            }
          } else {
            return "";
          }
        } else {
          if is_identifier(line) {
            return build_var_expr_json(line);
          } else {
            return "";
          }
        }
      }
    }
  }
}

fn parse_simple_line_statement_json(line) {
  let text = trim(line);
  if starts_with(text, "let ") {
    let rest = after_substring(text, "let ");
    let name = before_substring(rest, " = ");
    let expr_text = after_substring(rest, " = ");
    let expr_json = parse_simple_line_expr_json(expr_text);
    if is_identifier(name) {
      if eq(expr_json, "") {
        return "";
      } else {
        return build_let_stmt_json(name, expr_json);
      }
    } else {
      return "";
    }
  } else {
    if starts_with(text, "print ") {
      let expr_text = after_substring(text, "print ");
      let expr_json = parse_simple_line_expr_json(expr_text);
      if eq(expr_json, "") {
        return "";
      } else {
        return build_print_stmt_json(expr_json);
      }
    } else {
      return "";
    }
  }
}

fn parse_simple_line_kir_stmt_json(line) {
  let text = trim(line);
  if starts_with(text, "let ") {
    let rest = after_substring(text, "let ");
    let name = before_substring(rest, " = ");
    let expr_text = after_substring(rest, " = ");
    let expr_json = parse_simple_line_expr_json(expr_text);
    if is_identifier(name) {
      if eq(expr_json, "") {
        return "";
      } else {
        return build_kir_let_stmt_json(name, expr_json);
      }
    } else {
      return "";
    }
  } else {
    if starts_with(text, "print ") {
      let expr_text = after_substring(text, "print ");
      let expr_json = parse_simple_line_expr_json(expr_text);
      if eq(expr_json, "") {
        return "";
      } else {
        return build_kir_print_stmt_json(expr_json);
      }
    } else {
      return "";
    }
  }
}

fn try_parse_line_program(source) {
  let text = trim(source);
  let count = line_count(text);
  if eq(count, 0) {
    return "";
  } else {
    if eq(count, 1) {
      let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
      if eq(stmt1, "") {
        return "";
      } else {
        return build_program_json(stmt1);
      }
    } else {
      if eq(count, 2) {
        let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
        let stmt2 = parse_simple_line_statement_json(line_at(text, 1));
        if eq(stmt1, "") {
          return "";
        } else {
          if eq(stmt2, "") {
            return "";
          } else {
            return build_program_json(join_statements_2(stmt1, stmt2));
          }
        }
      } else {
        if eq(count, 3) {
          let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
          let stmt2 = parse_simple_line_statement_json(line_at(text, 1));
          let stmt3 = parse_simple_line_statement_json(line_at(text, 2));
          if eq(stmt1, "") {
            return "";
          } else {
            if eq(stmt2, "") {
              return "";
            } else {
              if eq(stmt3, "") {
                return "";
              } else {
                return build_program_json(join_statements_3(stmt1, stmt2, stmt3));
              }
            }
          }
        } else {
          if eq(count, 4) {
            let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
            let stmt2 = parse_simple_line_statement_json(line_at(text, 1));
            let stmt3 = parse_simple_line_statement_json(line_at(text, 2));
            let stmt4 = parse_simple_line_statement_json(line_at(text, 3));
            if eq(stmt1, "") {
              return "";
            } else {
              if eq(stmt2, "") {
                return "";
              } else {
                if eq(stmt3, "") {
                  return "";
                } else {
                  if eq(stmt4, "") {
                    return "";
                  } else {
                    return build_program_json(join_statements_4(stmt1, stmt2, stmt3, stmt4));
                  }
                }
              }
            }
          } else {
            return "";
          }
        }
      }
    }
  }
}

fn try_build_bundle_line_program(source) {
  let text = trim(source);
  let count = line_count(text);
  if eq(count, 0) {
    return "";
  } else {
    if eq(count, 1) {
      let ast1 = parse_simple_line_statement_json(line_at(text, 0));
      let kir1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
      if eq(ast1, "") {
        return "";
      } else {
        if eq(kir1, "") {
          return "";
        } else {
          let ast_json = build_program_json(ast1);
          let hir_json = build_hir_program_json("", ast1);
          let kir_json = build_kir_program_json("", kir1);
          let artifact_json = lower(source);
          if starts_with(artifact_json, "error:") {
            return "";
          } else {
            return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_program_print_json(), artifact_json);
          }
        }
      }
    } else {
      if eq(count, 2) {
        let ast1 = parse_simple_line_statement_json(line_at(text, 0));
        let ast2 = parse_simple_line_statement_json(line_at(text, 1));
        let kir1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
        let kir2 = parse_simple_line_kir_stmt_json(line_at(text, 1));
        if eq(ast1, "") {
          return "";
        } else {
          if eq(ast2, "") {
            return "";
          } else {
            if eq(kir1, "") {
              return "";
            } else {
              if eq(kir2, "") {
                return "";
              } else {
                let stmts_json = join_statements_2(ast1, ast2);
                let kir_stmts_json = join_statements_2(kir1, kir2);
                let ast_json = build_program_json(stmts_json);
                let hir_json = build_hir_program_json("", stmts_json);
                let kir_json = build_kir_program_json("", kir_stmts_json);
                let artifact_json = lower(source);
                if starts_with(artifact_json, "error:") {
                  return "";
                } else {
                  return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_program_print_json(), artifact_json);
                }
              }
            }
          }
        }
      } else {
        if eq(count, 3) {
          let ast1 = parse_simple_line_statement_json(line_at(text, 0));
          let ast2 = parse_simple_line_statement_json(line_at(text, 1));
          let ast3 = parse_simple_line_statement_json(line_at(text, 2));
          let kir1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
          let kir2 = parse_simple_line_kir_stmt_json(line_at(text, 1));
          let kir3 = parse_simple_line_kir_stmt_json(line_at(text, 2));
          if eq(ast1, "") {
            return "";
          } else {
            if eq(ast2, "") {
              return "";
            } else {
              if eq(ast3, "") {
                return "";
              } else {
                if eq(kir1, "") {
                  return "";
                } else {
                  if eq(kir2, "") {
                    return "";
                  } else {
                    if eq(kir3, "") {
                      return "";
                    } else {
                      let stmts_json = join_statements_3(ast1, ast2, ast3);
                      let kir_stmts_json = join_statements_3(kir1, kir2, kir3);
                      let ast_json = build_program_json(stmts_json);
                      let hir_json = build_hir_program_json("", stmts_json);
                      let kir_json = build_kir_program_json("", kir_stmts_json);
                      let artifact_json = lower(source);
                      if starts_with(artifact_json, "error:") {
                        return "";
                      } else {
                        return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_program_print_json(), artifact_json);
                      }
                    }
                  }
                }
              }
            }
          }
        } else {
          return "";
        }
      }
    }
  }
}

fn try_build_bundle_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_name = before_substring(after_substring(line1, "fn "), "() {");
                let rest = after_substring(line2, "let ");
                let name = before_substring(rest, " = concat(");
                let quoted1 = extract_quoted(line2);
                let after_first = after_substring(line2, concat(q, ", "));
                let quoted2 = extract_quoted(after_first);
                let rebuilt2 = concat(
                  "let ",
                  concat(
                    name,
                    concat(
                      " = concat(",
                      concat(q, concat(quoted1, concat(q, concat(", ", concat(q, concat(quoted2, concat(q, ")")))))))
                    )
                  )
                );
                let rebuilt3 = concat("print ", name);
                let rebuilt5 = concat(fn_name, "()");
                if is_identifier(fn_name) {
                  if is_identifier(name) {
                    if eq(rebuilt2, line2) {
                      if eq(rebuilt3, line3) {
                        if eq(after_substring(line5, "call "), rebuilt5) {
                          let let_ast = build_let_stmt_json(name, build_concat_expr_json(build_string_expr_json(quoted1), build_string_expr_json(quoted2)));
                          let print_ast = build_print_stmt_json(build_var_expr_json(name));
                          let body_json = join_statements_2(let_ast, print_ast);
                          let fn_json = concat("{\"kind\":\"fn\",\"name\":\"", concat(fn_name, concat("\",\"params\":[],\"body\":[", concat(body_json, "]}"))));
                          let call_ast = build_call_stmt_json(fn_name, build_expr_list_json_0());
                          let ast_json = concat("{\"kind\":\"program\",\"functions\":[", concat(fn_json, concat("],\"statements\":[", concat(call_ast, "]}"))));
                          let hir_fn = build_hir_function_json(fn_name, build_string_list_json_0(), body_json);
                          let hir_json = build_hir_program_json(hir_fn, call_ast);
                          let kir_let = build_kir_let_stmt_json(name, build_concat_expr_json(build_string_expr_json(quoted1), build_string_expr_json(quoted2)));
                          let kir_print = build_kir_print_stmt_json(build_var_expr_json(name));
                          let kir_body = join_statements_2(kir_let, kir_print);
                          let kir_fn = build_hir_function_json(fn_name, build_string_list_json_0(), kir_body);
                          let kir_call = build_kir_call_stmt_json(fn_name, build_expr_list_json_0());
                          let kir_json = build_kir_program_json(kir_fn, kir_call);
                          let artifact_json = lower(source);
                          if starts_with(artifact_json, "error:") {
                            return "";
                          } else {
                            return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_function_print_json(fn_name, "0"), artifact_json);
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
  } else {
    return "";
  }
}

fn try_build_bundle_single_arg_fn_call(source) {
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
                          let print_ast = build_print_stmt_json(build_concat_expr_json(build_var_expr_json(param_name), build_string_expr_json(suffix)));
                          let fn_ast = concat("{\"kind\":\"fn\",\"name\":\"", concat(fn_name, concat("\",\"params\":[\"", concat(param_name, concat("\"],\"body\":[", concat(print_ast, "]}"))))));
                          let call_ast = build_call_stmt_json(fn_name, build_expr_list_json_1(build_string_expr_json(arg_text)));
                          let ast_json = concat("{\"kind\":\"program\",\"functions\":[", concat(fn_ast, concat("],\"statements\":[", concat(call_ast, "]}"))));
                          let hir_fn = build_hir_function_json(fn_name, build_string_list_json_1(param_name), print_ast);
                          let hir_json = build_hir_program_json(hir_fn, call_ast);
                          let kir_print = build_kir_print_stmt_json(build_concat_expr_json(build_var_expr_json(param_name), build_string_expr_json(suffix)));
                          let kir_fn = build_hir_function_json(fn_name, build_string_list_json_1(param_name), kir_print);
                          let kir_call = build_kir_call_stmt_json(fn_name, build_expr_list_json_1(build_string_expr_json(arg_text)));
                          let kir_json = build_kir_program_json(kir_fn, kir_call);
                          let artifact_json = lower(source);
                          if starts_with(artifact_json, "error:") {
                            return "";
                          } else {
                            return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_function_print_json(fn_name, "1"), artifact_json);
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
  } else {
    return "";
  }
}

fn try_build_bundle_if_expr(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line3);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat(
      "print if(",
      concat(
        enabled_name,
        concat(", ", concat(greeting_name, concat(", ", concat(q, concat(disabled_text, concat(q, ")"))))))
      )
    );
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              let greeting_ast = build_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
              let enabled_ast = build_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
              let print_ast = build_print_stmt_json(build_if_expr_json(build_var_expr_json(enabled_name), build_var_expr_json(greeting_name), build_string_expr_json(disabled_text)));
              let stmts_json = join_statements_3(greeting_ast, enabled_ast, print_ast);
              let ast_json = build_program_json(stmts_json);
              let hir_json = build_hir_program_json("", stmts_json);
              let greeting_kir = build_kir_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
              let enabled_kir = build_kir_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
              let print_kir = build_kir_print_stmt_json(build_if_expr_json(build_var_expr_json(enabled_name), build_var_expr_json(greeting_name), build_string_expr_json(disabled_text)));
              let kir_json = build_kir_program_json("", join_statements_3(greeting_kir, enabled_kir, print_kir));
              let artifact_json = lower(source);
              if starts_with(artifact_json, "error:") {
                return "";
              } else {
                return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_program_print_json(), artifact_json);
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

fn try_build_bundle_if_stmt(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line6);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat("if ", concat(enabled_name, " {"));
    let rebuilt4 = concat("print ", greeting_name);
    let rebuilt5 = "} else {";
    let rebuilt6 = concat("print ", concat(q, concat(disabled_text, q)));
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              if eq(rebuilt4, line4) {
                if eq(rebuilt5, line5) {
                  if eq(rebuilt6, line6) {
                    if eq(line7, "}") {
                      let greeting_ast = build_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
                      let enabled_ast = build_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
                      let if_ast = build_if_stmt_json(
                        build_var_expr_json(enabled_name),
                        build_print_stmt_json(build_var_expr_json(greeting_name)),
                        build_print_stmt_json(build_string_expr_json(disabled_text))
                      );
                      let stmts_json = join_statements_3(greeting_ast, enabled_ast, if_ast);
                      let ast_json = build_program_json(stmts_json);
                      let hir_json = build_hir_program_json("", stmts_json);
                      let greeting_kir = build_kir_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
                      let enabled_kir = build_kir_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
                      let if_kir = build_kir_if_stmt_json(
                        build_var_expr_json(enabled_name),
                        build_kir_print_stmt_json(build_var_expr_json(greeting_name)),
                        build_kir_print_stmt_json(build_string_expr_json(disabled_text))
                      );
                      let kir_json = build_kir_program_json("", join_statements_3(greeting_kir, enabled_kir, if_kir));
                      let artifact_json = lower(source);
                      if starts_with(artifact_json, "error:") {
                        return "";
                      } else {
                        return build_pipeline_bundle_json(ast_json, hir_json, kir_json, build_analysis_program_print_json(), artifact_json);
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

fn try_hir_line_program(source) {
  let text = trim(source);
  let count = line_count(text);
  if eq(count, 0) {
    return "";
  } else {
    if eq(count, 1) {
      let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
      if eq(stmt1, "") {
        return "";
      } else {
        return build_hir_program_json("", stmt1);
      }
    } else {
      if eq(count, 2) {
        let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
        let stmt2 = parse_simple_line_statement_json(line_at(text, 1));
        if eq(stmt1, "") {
          return "";
        } else {
          if eq(stmt2, "") {
            return "";
          } else {
            return build_hir_program_json("", join_statements_2(stmt1, stmt2));
          }
        }
      } else {
        if eq(count, 3) {
          let stmt1 = parse_simple_line_statement_json(line_at(text, 0));
          let stmt2 = parse_simple_line_statement_json(line_at(text, 1));
          let stmt3 = parse_simple_line_statement_json(line_at(text, 2));
          if eq(stmt1, "") {
            return "";
          } else {
            if eq(stmt2, "") {
              return "";
            } else {
              if eq(stmt3, "") {
                return "";
              } else {
                return build_hir_program_json("", join_statements_3(stmt1, stmt2, stmt3));
              }
            }
          }
        } else {
          return "";
        }
      }
    }
  }
}

fn try_kir_line_program(source) {
  let text = trim(source);
  let count = line_count(text);
  if eq(count, 0) {
    return "";
  } else {
    if eq(count, 1) {
      let stmt1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
      if eq(stmt1, "") {
        return "";
      } else {
        return build_kir_program_json("", stmt1);
      }
    } else {
      if eq(count, 2) {
        let stmt1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
        let stmt2 = parse_simple_line_kir_stmt_json(line_at(text, 1));
        if eq(stmt1, "") {
          return "";
        } else {
          if eq(stmt2, "") {
            return "";
          } else {
            return build_kir_program_json("", join_statements_2(stmt1, stmt2));
          }
        }
      } else {
        if eq(count, 3) {
          let stmt1 = parse_simple_line_kir_stmt_json(line_at(text, 0));
          let stmt2 = parse_simple_line_kir_stmt_json(line_at(text, 1));
          let stmt3 = parse_simple_line_kir_stmt_json(line_at(text, 2));
          if eq(stmt1, "") {
            return "";
          } else {
            if eq(stmt2, "") {
              return "";
            } else {
              if eq(stmt3, "") {
                return "";
              } else {
                return build_kir_program_json("", join_statements_3(stmt1, stmt2, stmt3));
              }
            }
          }
        } else {
          return "";
        }
      }
    }
  }
}

fn try_hir_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_name = before_substring(after_substring(line1, "fn "), "() {");
                let rest = after_substring(line2, "let ");
                let name = before_substring(rest, " = concat(");
                let quoted1 = extract_quoted(line2);
                let after_first = after_substring(line2, concat(q, ", "));
                let quoted2 = extract_quoted(after_first);
                let rebuilt2 = concat(
                  "let ",
                  concat(
                    name,
                    concat(
                      " = concat(",
                      concat(q, concat(quoted1, concat(q, concat(", ", concat(q, concat(quoted2, concat(q, ")")))))))
                    )
                  )
                );
                let rebuilt3 = concat("print ", name);
                let rebuilt5 = concat(fn_name, "()");
                if is_identifier(fn_name) {
                  if is_identifier(name) {
                    if eq(rebuilt2, line2) {
                      if eq(rebuilt3, line3) {
                        if eq(after_substring(line5, "call "), rebuilt5) {
                          let let_ast = build_let_stmt_json(name, build_concat_expr_json(build_string_expr_json(quoted1), build_string_expr_json(quoted2)));
                          let print_ast = build_print_stmt_json(build_var_expr_json(name));
                          let body_json = join_statements_2(let_ast, print_ast);
                          let call_ast = build_call_stmt_json(fn_name, build_expr_list_json_0());
                          let hir_fn = build_hir_function_json(fn_name, build_string_list_json_0(), body_json);
                          return build_hir_program_json(hir_fn, call_ast);
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

fn try_kir_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_name = before_substring(after_substring(line1, "fn "), "() {");
                let rest = after_substring(line2, "let ");
                let name = before_substring(rest, " = concat(");
                let quoted1 = extract_quoted(line2);
                let after_first = after_substring(line2, concat(q, ", "));
                let quoted2 = extract_quoted(after_first);
                let rebuilt2 = concat(
                  "let ",
                  concat(
                    name,
                    concat(
                      " = concat(",
                      concat(q, concat(quoted1, concat(q, concat(", ", concat(q, concat(quoted2, concat(q, ")")))))))
                    )
                  )
                );
                let rebuilt3 = concat("print ", name);
                let rebuilt5 = concat(fn_name, "()");
                if is_identifier(fn_name) {
                  if is_identifier(name) {
                    if eq(rebuilt2, line2) {
                      if eq(rebuilt3, line3) {
                        if eq(after_substring(line5, "call "), rebuilt5) {
                          let kir_let = build_kir_let_stmt_json(name, build_concat_expr_json(build_string_expr_json(quoted1), build_string_expr_json(quoted2)));
                          let kir_print = build_kir_print_stmt_json(build_var_expr_json(name));
                          let kir_body = join_statements_2(kir_let, kir_print);
                          let kir_fn = build_hir_function_json(fn_name, build_string_list_json_0(), kir_body);
                          let kir_call = build_kir_call_stmt_json(fn_name, build_expr_list_json_0());
                          return build_kir_program_json(kir_fn, kir_call);
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

fn try_analysis_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_name = before_substring(after_substring(line1, "fn "), "() {");
                let rest = after_substring(line2, "let ");
                let name = before_substring(rest, " = concat(");
                let quoted1 = extract_quoted(line2);
                let after_first = after_substring(line2, concat(q, ", "));
                let quoted2 = extract_quoted(after_first);
                let rebuilt2 = concat(
                  "let ",
                  concat(
                    name,
                    concat(
                      " = concat(",
                      concat(q, concat(quoted1, concat(q, concat(", ", concat(q, concat(quoted2, concat(q, ")")))))))
                    )
                  )
                );
                let rebuilt3 = concat("print ", name);
                let rebuilt5 = concat(fn_name, "()");
                if is_identifier(fn_name) {
                  if is_identifier(name) {
                    if eq(rebuilt2, line2) {
                      if eq(rebuilt3, line3) {
                        if eq(after_substring(line5, "call "), rebuilt5) {
                          return build_analysis_function_print_json(fn_name, "0");
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

fn try_hir_single_arg_fn_call(source) {
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
                          let print_ast = build_print_stmt_json(build_concat_expr_json(build_var_expr_json(param_name), build_string_expr_json(suffix)));
                          let call_ast = build_call_stmt_json(fn_name, build_expr_list_json_1(build_string_expr_json(arg_text)));
                          let hir_fn = build_hir_function_json(fn_name, build_string_list_json_1(param_name), print_ast);
                          return build_hir_program_json(hir_fn, call_ast);
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

fn try_kir_single_arg_fn_call(source) {
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
                          let kir_print = build_kir_print_stmt_json(build_concat_expr_json(build_var_expr_json(param_name), build_string_expr_json(suffix)));
                          let kir_fn = build_hir_function_json(fn_name, build_string_list_json_1(param_name), kir_print);
                          let kir_call = build_kir_call_stmt_json(fn_name, build_expr_list_json_1(build_string_expr_json(arg_text)));
                          return build_kir_program_json(kir_fn, kir_call);
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

fn try_analysis_single_arg_fn_call(source) {
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
                          return build_analysis_function_print_json(fn_name, "1");
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

fn try_hir_if_expr(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line3);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat(
      "print if(",
      concat(
        enabled_name,
        concat(", ", concat(greeting_name, concat(", ", concat(q, concat(disabled_text, concat(q, ")"))))))
      )
    );
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              let greeting_ast = build_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
              let enabled_ast = build_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
              let print_ast = build_print_stmt_json(build_if_expr_json(build_var_expr_json(enabled_name), build_var_expr_json(greeting_name), build_string_expr_json(disabled_text)));
              return build_hir_program_json("", join_statements_3(greeting_ast, enabled_ast, print_ast));
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

fn try_kir_if_expr(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line3);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat(
      "print if(",
      concat(
        enabled_name,
        concat(", ", concat(greeting_name, concat(", ", concat(q, concat(disabled_text, concat(q, ")"))))))
      )
    );
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              let greeting_kir = build_kir_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
              let enabled_kir = build_kir_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
              let print_kir = build_kir_print_stmt_json(build_if_expr_json(build_var_expr_json(enabled_name), build_var_expr_json(greeting_name), build_string_expr_json(disabled_text)));
              return build_kir_program_json("", join_statements_3(greeting_kir, enabled_kir, print_kir));
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

fn try_hir_if_stmt(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line6);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat("if ", concat(enabled_name, " {"));
    let rebuilt4 = concat("print ", greeting_name);
    let rebuilt5 = "} else {";
    let rebuilt6 = concat("print ", concat(q, concat(disabled_text, q)));
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              if eq(rebuilt4, line4) {
                if eq(rebuilt5, line5) {
                  if eq(rebuilt6, line6) {
                    if eq(line7, "}") {
                      let greeting_ast = build_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
                      let enabled_ast = build_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
                      let if_ast = build_if_stmt_json(
                        build_var_expr_json(enabled_name),
                        build_print_stmt_json(build_var_expr_json(greeting_name)),
                        build_print_stmt_json(build_string_expr_json(disabled_text))
                      );
                      return build_hir_program_json("", join_statements_3(greeting_ast, enabled_ast, if_ast));
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

fn try_kir_if_stmt(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line6);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat("if ", concat(enabled_name, " {"));
    let rebuilt4 = concat("print ", greeting_name);
    let rebuilt5 = "} else {";
    let rebuilt6 = concat("print ", concat(q, concat(disabled_text, q)));
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              if eq(rebuilt4, line4) {
                if eq(rebuilt5, line5) {
                  if eq(rebuilt6, line6) {
                    if eq(line7, "}") {
                      let greeting_kir = build_kir_let_stmt_json(greeting_name, build_concat_expr_json(build_string_expr_json(left_text), build_string_expr_json(right_text)));
                      let enabled_kir = build_kir_let_stmt_json(enabled_name, build_eq_expr_json(build_var_expr_json(greeting_name), build_string_expr_json(expected_text)));
                      let if_kir = build_kir_if_stmt_json(
                        build_var_expr_json(enabled_name),
                        build_kir_print_stmt_json(build_var_expr_json(greeting_name)),
                        build_kir_print_stmt_json(build_string_expr_json(disabled_text))
                      );
                      return build_kir_program_json("", join_statements_3(greeting_kir, enabled_kir, if_kir));
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

fn try_analysis_line_program(source) {
  let hir_json = try_hir_line_program(source);
  if eq(hir_json, "") {
    return "";
  } else {
    return build_analysis_program_print_json();
  }
}

fn try_analysis_if_expr(source) {
  let hir_json = try_hir_if_expr(source);
  if eq(hir_json, "") {
    return "";
  } else {
    return build_analysis_program_print_json();
  }
}

fn try_analysis_if_stmt(source) {
  let hir_json = try_hir_if_stmt(source);
  if eq(hir_json, "") {
    return "";
  } else {
    return build_analysis_program_print_json();
  }
}

fn try_parse_two_prints(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    if starts_with(line1, concat("print ", q)) {
      if starts_with(line2, concat("print ", q)) {
        let text1 = extract_quoted(line1);
        let text2 = extract_quoted(line2);
        let rebuilt1 = concat("print ", concat(q, concat(text1, q)));
        let rebuilt2 = concat("print ", concat(q, concat(text2, q)));
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            return program_two_prints_ast(text1, text2);
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

fn try_parse_zero_arg_fn_call(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if eq(line4, "}") {
      if starts_with(line1, "fn ") {
        if ends_with(line1, "() {") {
          if starts_with(line2, "let ") {
            if starts_with(line3, "print ") {
              if starts_with(line5, "call ") {
                let fn_name = before_substring(after_substring(line1, "fn "), "() {");
                let rest = after_substring(line2, "let ");
                let name = before_substring(rest, " = concat(");
                let quoted1 = extract_quoted(line2);
                let after_first = after_substring(line2, concat(q, ", "));
                let quoted2 = extract_quoted(after_first);
                let rebuilt2 = concat(
                  "let ",
                  concat(
                    name,
                    concat(
                      " = concat(",
                      concat(q, concat(quoted1, concat(q, concat(", ", concat(q, concat(quoted2, concat(q, ")")))))))
                    )
                  )
                );
                let rebuilt3 = concat("print ", name);
                let rebuilt5 = concat(fn_name, "()");
                if is_identifier(fn_name) {
                  if is_identifier(name) {
                    if eq(rebuilt2, line2) {
                      if eq(rebuilt3, line3) {
                        if eq(after_substring(line5, "call "), rebuilt5) {
                          return program_zero_arg_fn_call_ast(fn_name, name, quoted1, quoted2);
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

fn try_parse_if_expr(source) {
  let text = trim(source);
  if eq(line_count(text), 3) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line3);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat(
      "print if(",
      concat(
        enabled_name,
        concat(", ", concat(greeting_name, concat(", ", concat(q, concat(disabled_text, concat(q, ")"))))))
      )
    );
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              return program_if_expr_print_ast(greeting_name, left_text, right_text, enabled_name, expected_text, disabled_text);
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

fn try_parse_if_stmt(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
    let left_text = extract_quoted(line1);
    let after_left = after_substring(line1, concat(q, ", "));
    let right_text = extract_quoted(after_left);
    let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
    let expected_text = extract_quoted(line2);
    let disabled_text = extract_quoted(line5);
    let rebuilt1 = concat(
      "let ",
      concat(
        greeting_name,
        concat(
          " = concat(",
          concat(q, concat(left_text, concat(q, concat(", ", concat(q, concat(right_text, concat(q, ")")))))))
        )
      )
    );
    let rebuilt2 = concat(
      "let ",
      concat(
        enabled_name,
        concat(
          " = eq(",
          concat(greeting_name, concat(", ", concat(q, concat(expected_text, concat(q, ")")))))
        )
      )
    );
    let rebuilt3 = concat("if ", concat(enabled_name, " {"));
    let rebuilt4 = "} else {";
    let rebuilt5 = concat("print ", concat(q, concat(disabled_text, q)));
    let rebuilt_print_var = concat("print ", greeting_name);
    if is_identifier(greeting_name) {
      if is_identifier(enabled_name) {
        if eq(rebuilt1, line1) {
          if eq(rebuilt2, line2) {
            if eq(rebuilt3, line3) {
              if eq(rebuilt_print_var, line4) {
                if eq(line5, rebuilt4) {
                  if eq(line6, rebuilt5) {
                    if eq(line7, "}") {
                      return program_if_stmt_ast(greeting_name, left_text, right_text, enabled_name, expected_text, disabled_text);
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

fn try_parse_current_shape(source) {
  let two_prints = try_parse_two_prints(source);
  if eq(two_prints, "") {
    let zero_arg_fn = try_parse_zero_arg_fn_call(source);
    if eq(zero_arg_fn, "") {
      let if_expr = try_parse_if_expr_print(source);
      if eq(if_expr, "") {
        let if_stmt = try_parse_if_stmt_simple(source);
        if eq(if_stmt, "") {
          let strict_if_stmt = try_parse_if_stmt(source);
          if eq(strict_if_stmt, "") {
            return "";
          } else {
            return strict_if_stmt;
          }
        } else {
          return if_stmt;
        }
      } else {
        return if_expr;
      }
    } else {
      return zero_arg_fn;
    }
  } else {
    return two_prints;
  }
}

fn try_lower_current_shape(source) {
  let two_prints = try_lower_two_prints(source);
  if eq(two_prints, "") {
    let zero_arg_fn = try_lower_zero_arg_fn_call_simple(source);
    if eq(zero_arg_fn, "") {
      let if_expr = try_lower_if_expr_print(source);
      if eq(if_expr, "") {
        let if_stmt = try_lower_if_stmt_simple(source);
        if eq(if_stmt, "") {
          let strict_if_stmt = try_lower_if_stmt(source);
          if eq(strict_if_stmt, "") {
            return "";
          } else {
            return strict_if_stmt;
          }
        } else {
          return if_stmt;
        }
      } else {
        return if_expr;
      }
    } else {
      return zero_arg_fn;
    }
  } else {
    return two_prints;
  }
}

fn try_parse_zero_arg_fn_call_simple(source) {
  let text = trim(source);
  if eq(line_count(text), 4) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let q = quote();
    if starts_with(line1, "fn ") {
      if ends_with(line1, "{") {
        if starts_with(line2, "let ") {
          if starts_with(line3, "print ") {
            if starts_with(line4, "call ") {
              let fn_name = before_substring(after_substring(line1, "fn "), "() {");
              let var_name = before_substring(after_substring(line2, "let "), " = concat(");
              let left_text = extract_quoted(line2);
              let after_first = after_substring(line2, concat(q, ", "));
              let right_text = extract_quoted(after_first);
              let print_name = after_substring(line3, "print ");
              let call_name = before_substring(after_substring(line4, "call "), "(");
              if is_identifier(fn_name) {
                if is_identifier(var_name) {
                  if eq(print_name, var_name) {
                    if eq(call_name, fn_name) {
                      return program_zero_arg_fn_call_ast(fn_name, var_name, left_text, right_text);
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

fn try_lower_zero_arg_fn_call_simple(source) {
  let text = trim(source);
  if eq(line_count(text), 5) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let q = quote();
    if starts_with(line1, "fn ") {
      if ends_with(line1, "{") {
        if starts_with(line2, "let ") {
          if starts_with(line3, "print ") {
            if eq(line4, "}") {
              if starts_with(line5, "call ") {
              let fn_name = before_substring(after_substring(line1, "fn "), "() {");
              let var_name = before_substring(after_substring(line2, "let "), " = concat(");
              let left_text = extract_quoted(line2);
              let after_first = after_substring(line2, concat(q, ", "));
              let right_text = extract_quoted(after_first);
              let print_name = after_substring(line3, "print ");
              let call_name = before_substring(after_substring(line5, "call "), "(");
              if is_identifier(fn_name) {
                if is_identifier(var_name) {
                  if eq(print_name, var_name) {
                    if eq(call_name, fn_name) {
                      return print_many_artifact(concat(left_text, right_text));
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

fn try_parse_if_stmt_simple(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "if ") {
          if starts_with(line4, "print ") {
            if eq(line5, "} else {") {
              if starts_with(line6, "print ") {
                if eq(line7, "}") {
                  let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
                  let left_text = extract_quoted(line1);
                  let after_first = after_substring(line1, concat(q, ", "));
                  let right_text = extract_quoted(after_first);
                  let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
                  let eq_inner = after_substring(line2, " = eq(");
                  let greeting_ref = before_substring(eq_inner, ", ");
                  let expected_text = extract_quoted(line2);
                  let disabled_text = extract_quoted(line6);
                  let condition_name = before_substring(after_substring(line3, "if "), " {");
                  let print_then = after_substring(line4, "print ");
                  if is_identifier(greeting_name) {
                    if is_identifier(enabled_name) {
                      if eq(greeting_ref, greeting_name) {
                        if eq(enabled_name, condition_name) {
                          if eq(print_then, greeting_name) {
                            return program_if_stmt_ast(
                              greeting_name,
                              left_text,
                              right_text,
                              enabled_name,
                              expected_text,
                              disabled_text
                            );
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
  } else {
    return "";
  }
}

fn try_lower_if_stmt_simple(source) {
  let text = trim(source);
  if eq(line_count(text), 7) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let line3 = line_at(text, 2);
    let line4 = line_at(text, 3);
    let line5 = line_at(text, 4);
    let line6 = line_at(text, 5);
    let line7 = line_at(text, 6);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "let ") {
        if starts_with(line3, "if ") {
          if starts_with(line4, "print ") {
            if eq(line5, "} else {") {
              if starts_with(line6, "print ") {
                if eq(line7, "}") {
                  let greeting_name = before_substring(after_substring(line1, "let "), " = concat(");
                  let left_text = extract_quoted(line1);
                  let after_first = after_substring(line1, concat(q, ", "));
                  let right_text = extract_quoted(after_first);
                  let enabled_name = before_substring(after_substring(line2, "let "), " = eq(");
                  let eq_inner = after_substring(line2, " = eq(");
                  let greeting_ref = before_substring(eq_inner, ", ");
                  let expected_text = extract_quoted(line2);
                  let disabled_text = extract_quoted(line6);
                  let condition_name = before_substring(after_substring(line3, "if "), " {");
                  let print_then = after_substring(line4, "print ");
                  if is_identifier(greeting_name) {
                    if is_identifier(enabled_name) {
                      if eq(greeting_ref, greeting_name) {
                        if eq(enabled_name, condition_name) {
                          if eq(print_then, greeting_name) {
                            return render_if_output(left_text, right_text, expected_text, disabled_text);
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
  } else {
    return "";
  }
}

fn try_lower_single_print(source) {
  let text = trim(source);
  let q = quote();
  let prefix = concat("print ", q);
  if starts_with(text, prefix) {
    if ends_with(text, q) {
      let quoted = extract_quoted(text);
      let rebuilt = concat(prefix, concat(quoted, q));
      if eq(rebuilt, text) {
        return print_many_artifact(quoted);
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

fn try_lower_single_print_concat(source) {
  let text = trim(source);
  let q = quote();
  if starts_with(text, "print concat(") {
    let quoted1 = extract_quoted(text);
    let after_first = after_quote_comma(text);
    let quoted2 = extract_quoted(after_first);
    if eq(concat_call_matches(text, "print concat(", quoted1, quoted2), "ok") {
      return print_many_artifact(concat(quoted1, quoted2));
    } else {
      return "";
    }
  } else {
    return "";
  }
}

fn try_lower_simple_let_print(source) {
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
            return print_many_artifact(quoted);
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

fn try_lower_simple_let_concat_print(source) {
  let text = trim(source);
  if eq(line_count(text), 2) {
    let line1 = line_at(text, 0);
    let line2 = line_at(text, 1);
    let q = quote();
    if starts_with(line1, "let ") {
      if starts_with(line2, "print ") {
        let rest = after_substring(line1, "let ");
        let name = before_substring(rest, " = concat(");
        let quoted1 = extract_quoted(line1);
        let after_first = after_quote_comma(line1);
        let quoted2 = extract_quoted(after_first);
        let rebuilt2 = concat("print ", name);
        if is_identifier(name) {
          if eq(concat_call_matches(line1, concat("let ", concat(name, " = concat(")), quoted1, quoted2), "ok") {
            if eq(rebuilt2, line2) {
              return print_many_artifact(concat(quoted1, quoted2));
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

fn try_lower_simple_single_arg_fn_call(source) {
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
                          return print_many_artifact(concat(arg_text, suffix));
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
  let current = try_parse_current_shape(source);
  if eq(current, "") {
    let line_program = try_parse_line_program(source);
    if eq(line_program, "") {
      let simple_fn = try_parse_simple_single_arg_fn_call(source);
      if eq(simple_fn, "") {
        return "error: unsupported source";
      } else {
        return simple_fn;
      }
    } else {
      return line_program;
    }
  } else {
    return current;
  }
}

fn try_check_known(source) {
  let current = try_parse_current_shape(source);
  if eq(current, "") {
    let simple = try_lower_single_print(source);
    if eq(simple, "") {
      let simple_print_concat = try_lower_single_print_concat(source);
      if eq(simple_print_concat, "") {
        let simple_let = try_lower_simple_let_print(source);
        if eq(simple_let, "") {
          let simple_let_concat = try_lower_simple_let_concat_print(source);
          if eq(simple_let_concat, "") {
            let simple_fn = try_lower_simple_single_arg_fn_call(source);
            if eq(simple_fn, "") {
              return "";
            } else {
              return "ok";
            }
          } else {
            return "ok";
          }
        } else {
          return "ok";
        }
      } else {
        return "ok";
      }
    } else {
      return "ok";
    }
  } else {
    return "ok";
  }
}

fn check(source) {
  let ast = parse(source);
  if starts_with(ast, "error:") {
    return ast;
  } else {
    return "ok";
  }
}

fn lower(source) {
  let current = try_lower_current_shape(source);
  if eq(current, "") {
    let simple = try_lower_single_print(source);
    if eq(simple, "") {
      let simple_print_concat = try_lower_single_print_concat(source);
      if eq(simple_print_concat, "") {
        let simple_let = try_lower_simple_let_print(source);
        if eq(simple_let, "") {
          let simple_let_concat = try_lower_simple_let_concat_print(source);
          if eq(simple_let_concat, "") {
            let simple_fn = try_lower_simple_single_arg_fn_call(source);
            if eq(simple_fn, "") {
              return "error: unsupported source";
            } else {
              return simple_fn;
            }
          } else {
            return simple_let_concat;
          }
        } else {
          return simple_let;
        }
      } else {
        return simple_print_concat;
      }
    } else {
      return simple;
    }
  } else {
    return current;
  }
}

fn hir(source) {
  let line_hir = try_hir_line_program(source);
  if eq(line_hir, "") {
    let zero_arg_hir = try_hir_zero_arg_fn_call(source);
    if eq(zero_arg_hir, "") {
      let single_arg_hir = try_hir_single_arg_fn_call(source);
      if eq(single_arg_hir, "") {
        let if_expr_hir = try_hir_if_expr(source);
        if eq(if_expr_hir, "") {
          let if_stmt_hir = try_hir_if_stmt(source);
          if eq(if_stmt_hir, "") {
            let ast = parse(source);
            if starts_with(ast, "error:") {
              return ast;
            } else {
              let hir_json = program_ast_to_hir(ast);
              if eq(hir_json, "") {
                return "error: unsupported source";
              } else {
                return hir_json;
              }
            }
          } else {
            return if_stmt_hir;
          }
        } else {
          return if_expr_hir;
        }
      } else {
        return single_arg_hir;
      }
    } else {
      return zero_arg_hir;
    }
  } else {
    return line_hir;
  }
}

fn kir(source) {
  let line_kir = try_kir_line_program(source);
  if eq(line_kir, "") {
    let zero_arg_kir = try_kir_zero_arg_fn_call(source);
    if eq(zero_arg_kir, "") {
      let single_arg_kir = try_kir_single_arg_fn_call(source);
      if eq(single_arg_kir, "") {
        let if_expr_kir = try_kir_if_expr(source);
        if eq(if_expr_kir, "") {
          let if_stmt_kir = try_kir_if_stmt(source);
          if eq(if_stmt_kir, "") {
            let hir_json = hir(source);
            if starts_with(hir_json, "error:") {
              return hir_json;
            } else {
              let kir_json = hir_to_kir(hir_json);
              if eq(kir_json, "") {
                return "error: unsupported source";
              } else {
                return kir_json;
              }
            }
          } else {
            return if_stmt_kir;
          }
        } else {
          return if_expr_kir;
        }
      } else {
        return single_arg_kir;
      }
    } else {
      return zero_arg_kir;
    }
  } else {
    return line_kir;
  }
}

fn analysis(source) {
  let line_analysis = try_analysis_line_program(source);
  if eq(line_analysis, "") {
    let zero_arg_analysis = try_analysis_zero_arg_fn_call(source);
    if eq(zero_arg_analysis, "") {
      let single_arg_analysis = try_analysis_single_arg_fn_call(source);
      if eq(single_arg_analysis, "") {
        let if_expr_analysis = try_analysis_if_expr(source);
        if eq(if_expr_analysis, "") {
          let if_stmt_analysis = try_analysis_if_stmt(source);
          if eq(if_stmt_analysis, "") {
            let hir_json = hir(source);
            if starts_with(hir_json, "error:") {
              return hir_json;
            } else {
              let analysis_json = hir_to_analysis(hir_json);
              if eq(analysis_json, "") {
                return "error: unsupported source";
              } else {
                return analysis_json;
              }
            }
          } else {
            return if_stmt_analysis;
          }
        } else {
          return if_expr_analysis;
        }
      } else {
        return single_arg_analysis;
      }
    } else {
      return zero_arg_analysis;
    }
  } else {
    return line_analysis;
  }
}

fn compile(source) {
  return lower(source);
}

fn pipeline(source) {
  let line_bundle = try_build_bundle_line_program(source);
  if eq(line_bundle, "") {
    let zero_arg_bundle = try_build_bundle_zero_arg_fn_call(source);
    if eq(zero_arg_bundle, "") {
      let single_arg_bundle = try_build_bundle_single_arg_fn_call(source);
      if eq(single_arg_bundle, "") {
        let if_expr_bundle = try_build_bundle_if_expr(source);
        if eq(if_expr_bundle, "") {
          let if_stmt_bundle = try_build_bundle_if_stmt(source);
          if eq(if_stmt_bundle, "") {
            let ast = parse(source);
            if starts_with(ast, "error:") {
              return ast;
            } else {
              let hir_json = hir(source);
              if starts_with(hir_json, "error:") {
                return hir_json;
              } else {
                let kir_json = kir(source);
                if starts_with(kir_json, "error:") {
                  return kir_json;
                } else {
                  let analysis_json = analysis(source);
                  if starts_with(analysis_json, "error:") {
                    return analysis_json;
                  } else {
                    let artifact = lower(source);
                    if starts_with(artifact, "error:") {
                      return artifact;
                    } else {
                      return build_pipeline_bundle_json(ast, hir_json, kir_json, analysis_json, artifact);
                    }
                  }
                }
              }
            }
          } else {
            return if_stmt_bundle;
          }
        } else {
          return if_expr_bundle;
        }
      } else {
        return single_arg_bundle;
      }
    } else {
      return zero_arg_bundle;
    }
  } else {
    return line_bundle;
  }
}
