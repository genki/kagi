#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kagi_image_output.h"
#include "kagi_image_parser.h"

static int is_space_outside_string(unsigned char ch) {
    return ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t';
}

int normalized_source_equals(const char *left, const char *right) {
    size_t i = 0;
    size_t j = 0;
    int in_string_left = 0;
    int in_string_right = 0;
    while (left[i] || right[j]) {
        while (left[i] && !in_string_left && is_space_outside_string((unsigned char)left[i])) {
            i++;
        }
        while (right[j] && !in_string_right && is_space_outside_string((unsigned char)right[j])) {
            j++;
        }
        if (left[i] != right[j]) {
            return 0;
        }
        if (!left[i] && !right[j]) {
            return 1;
        }
        if (left[i] == '"' && (i == 0 || left[i - 1] != '\\')) {
            in_string_left = !in_string_left;
        }
        if (right[j] == '"' && (j == 0 || right[j - 1] != '\\')) {
            in_string_right = !in_string_right;
        }
        i++;
        j++;
    }
    return 1;
}

static void append_text(char **buffer, size_t *length, size_t *capacity, const char *text) {
    size_t add = strlen(text);
    size_t need = *length + add + 1;
    if (need > *capacity) {
        size_t next_capacity = *capacity == 0 ? 128 : *capacity;
        while (need > next_capacity) {
            next_capacity *= 2;
        }
        char *next = realloc(*buffer, next_capacity);
        if (!next) {
            fail("out of memory");
        }
        *buffer = next;
        *capacity = next_capacity;
    }
    memcpy(*buffer + *length, text, add);
    *length += add;
    (*buffer)[*length] = '\0';
}

static void append_char(char **buffer, size_t *length, size_t *capacity, char ch) {
    char tmp[2] = {ch, '\0'};
    append_text(buffer, length, capacity, tmp);
}

static int is_ident_start_char(unsigned char ch) {
    return isalpha(ch) || ch == '_';
}

static int is_ident_part_char(unsigned char ch) {
    return isalnum(ch) || ch == '_';
}

static char *trim_copy(const char *text) {
    while (*text && is_space_outside_string((unsigned char)*text)) {
        text++;
    }
    size_t len = strlen(text);
    while (len > 0 && is_space_outside_string((unsigned char)text[len - 1])) {
        len--;
    }
    char *out = calloc(len + 1, 1);
    if (!out) {
        fail("out of memory");
    }
    memcpy(out, text, len);
    out[len] = '\0';
    return out;
}

static int compact_line_equals(const char *left, const char *right) {
    char *left_trimmed = trim_copy(left);
    char *right_trimmed = trim_copy(right);
    int equal = normalized_source_equals(left_trimmed, right_trimmed);
    free(left_trimmed);
    free(right_trimmed);
    return equal;
}

static char *extract_call_inside(const char *text, const char *name) {
    char *trimmed = trim_copy(text);
    size_t name_len = strlen(name);
    size_t len = strlen(trimmed);
    if (len <= name_len + 1 || strncmp(trimmed, name, name_len) != 0) {
        free(trimmed);
        return NULL;
    }
    size_t index = name_len;
    while (trimmed[index] == ' ' || trimmed[index] == '\t') {
        index++;
    }
    if (trimmed[index] != '(' || trimmed[len - 1] != ')') {
        free(trimmed);
        return NULL;
    }
    index += 1;
    size_t inside_len = len - index - 1;
    char *inside = calloc(inside_len + 1, 1);
    if (!inside) {
        fail("out of memory");
    }
    memcpy(inside, trimmed + index, inside_len);
    inside[inside_len] = '\0';
    free(trimmed);
    return inside;
}

static int parse_ident_expr(const char *text, char **out);

static int parse_string_literal_expr(const char *text, char **out) {
    size_t len = strlen(text);
    if (len < 2 || text[0] != '"' || text[len - 1] != '"') {
        return 0;
    }
    char *value = calloc(len - 1, 1);
    if (!value) {
        fail("out of memory");
    }
    size_t j = 0;
    for (size_t i = 1; i + 1 < len; ++i) {
        if (text[i] == '\\' && i + 2 < len) {
            i++;
        }
        value[j++] = text[i];
    }
    value[j] = '\0';
    *out = value;
    return 1;
}

static int parse_print_expr(const char *text, native_expr_t *out) {
    char *trimmed = trim_copy(text);
    char *string_value = NULL;
    if (parse_string_literal_expr(trimmed, &string_value)) {
        out->kind = NATIVE_EXPR_STRING;
        out->left = string_value;
        out->right = NULL;
        free(trimmed);
        return 1;
    }
    char *inside = extract_call_inside(trimmed, "concat");
    if (inside) {
        int in_string = 0;
        char *comma = NULL;
        for (char *cursor = inside; *cursor; ++cursor) {
            if (*cursor == '"' && (cursor == inside || *(cursor - 1) != '\\')) {
                in_string = !in_string;
            } else if (*cursor == ',' && !in_string) {
                comma = cursor;
                break;
            }
        }
        if (comma) {
            *comma = '\0';
            char *left = trim_copy(inside);
            char *right = trim_copy(comma + 1);
            char *left_value = NULL;
            char *left_ident = NULL;
            char *right_value = NULL;
            if (parse_string_literal_expr(left, &left_value) && parse_string_literal_expr(right, &right_value)) {
                out->kind = NATIVE_EXPR_CONCAT;
                out->left = left_value;
                out->right = right_value;
                free(left);
                free(right);
                free(inside);
                free(trimmed);
                return 1;
            }
            free(left_value);
            if (parse_ident_expr(left, &left_ident) && parse_string_literal_expr(right, &right_value)) {
                out->kind = NATIVE_EXPR_CONCAT_VAR_STRING;
                out->left = left_ident;
                out->right = right_value;
                free(left);
                free(right);
                free(inside);
                free(trimmed);
                return 1;
            }
            free(left);
            free(right);
            free(left_ident);
            free(right_value);
        }
        free(inside);
    }
    free(trimmed);
    return 0;
}

static int parse_ident_expr(const char *text, char **out) {
    char *trimmed = trim_copy(text);
    if (!is_ident_start_char((unsigned char)trimmed[0])) {
        free(trimmed);
        return 0;
    }
    for (size_t i = 1; trimmed[i]; ++i) {
        if (!is_ident_part_char((unsigned char)trimmed[i])) {
            free(trimmed);
            return 0;
        }
    }
    *out = trimmed;
    return 1;
}

static int parse_simple_expr(const char *text, native_expr_t *out) {
    if (parse_print_expr(text, out)) {
        return 1;
    }
    char *ident = NULL;
    if (parse_ident_expr(text, &ident)) {
        out->kind = NATIVE_EXPR_VAR;
        out->left = ident;
        out->right = NULL;
        return 1;
    }
    return 0;
}

static int parse_eq_var_string_expr(const char *text, native_expr_t *out) {
    char *trimmed = trim_copy(text);
    char *inside = extract_call_inside(trimmed, "eq");
    if (!inside) {
        free(trimmed);
        return 0;
    }
    int in_string = 0;
    char *comma = NULL;
    for (char *cursor = inside; *cursor; ++cursor) {
        if (*cursor == '"' && (cursor == inside || *(cursor - 1) != '\\')) {
            in_string = !in_string;
        } else if (*cursor == ',' && !in_string) {
            comma = cursor;
            break;
        }
    }
    if (!comma) {
        free(inside);
        free(trimmed);
        return 0;
    }
    *comma = '\0';
    char *left = trim_copy(inside);
    char *right = trim_copy(comma + 1);
    char *left_ident = NULL;
    char *left_string = NULL;
    char *right_string = NULL;
    int ok = parse_string_literal_expr(right, &right_string) &&
             (parse_ident_expr(left, &left_ident) || parse_string_literal_expr(left, &left_string));
    free(left);
    free(right);
    free(inside);
    free(trimmed);
    if (!ok) {
        free(left_ident);
        free(left_string);
        free(right_string);
        return 0;
    }
    out->kind = left_ident ? NATIVE_EXPR_EQ_VAR_STRING : NATIVE_EXPR_EQ_STRING_STRING;
    out->left = left_ident ? left_ident : left_string;
    out->right = right_string;
    return 1;
}

static int parse_if_var_var_string_expr(const char *text, native_expr_t *out) {
    char *trimmed = trim_copy(text);
    char *inside = extract_call_inside(trimmed, "if");
    if (!inside) {
        free(trimmed);
        return 0;
    }
    int in_string = 0;
    int comma_count = 0;
    char *commas[2] = {0};
    for (char *cursor = inside; *cursor; ++cursor) {
        if (*cursor == '"' && (cursor == inside || *(cursor - 1) != '\\')) {
            in_string = !in_string;
        } else if (*cursor == ',' && !in_string && comma_count < 2) {
            commas[comma_count++] = cursor;
        }
    }
    if (comma_count != 2) {
        free(inside);
        free(trimmed);
        return 0;
    }
    *commas[0] = '\0';
    *commas[1] = '\0';
    char *condition = trim_copy(inside);
    char *then_value = trim_copy(commas[0] + 1);
    char *else_value = trim_copy(commas[1] + 1);
    char *condition_ident = NULL;
    char *then_ident = NULL;
    char *else_string = NULL;
    int ok = parse_ident_expr(condition, &condition_ident) &&
             parse_ident_expr(then_value, &then_ident) &&
             parse_string_literal_expr(else_value, &else_string);
    free(condition);
    free(then_value);
    free(else_value);
    free(inside);
    free(trimmed);
    if (!ok) {
        free(condition_ident);
        free(then_ident);
        free(else_string);
        return 0;
    }
    size_t size = strlen(condition_ident) + strlen(then_ident) + 2;
    char *joined = calloc(size, 1);
    if (!joined) {
        fail("out of memory");
    }
    snprintf(joined, size, "%s\n%s", condition_ident, then_ident);
    free(condition_ident);
    free(then_ident);
    out->kind = NATIVE_EXPR_IF_VAR_VAR_STRING;
    out->left = joined;
    out->right = else_string;
    return 1;
}

void free_native_stmt(native_stmt_t *stmt) {
    if (!stmt) {
        return;
    }
    free(stmt->name);
    free(stmt->expr.left);
    free(stmt->expr.right);
    free(stmt->condition_name);
    free(stmt->then_expr.left);
    free(stmt->then_expr.right);
    free(stmt->else_expr.left);
    free(stmt->else_expr.right);
    memset(stmt, 0, sizeof(*stmt));
}

void free_native_stmt_program(native_stmt_program_t *program) {
    if (!program) {
        return;
    }
    for (size_t i = 0; i < program->count; ++i) {
        free_native_stmt(&program->statements[i]);
    }
    free(program->statements);
    memset(program, 0, sizeof(*program));
}

void free_native_function(native_function_t *function) {
    if (!function) {
        return;
    }
    free(function->name);
    free(function->param_name);
    free_native_stmt_program(&function->body);
    memset(function, 0, sizeof(*function));
}

void free_native_function_program(native_function_program_t *program) {
    if (!program) {
        return;
    }
    free_native_function(&program->function);
    free(program->call_name);
    free(program->call_arg);
    free_native_stmt_program(&program->top_level);
    memset(program, 0, sizeof(*program));
}

static int parse_any_let_line(const char *line, char **out_name, native_expr_t *out_expr) {
    const char *let_prefix = "let ";
    if (strncmp(line, let_prefix, strlen(let_prefix)) != 0) {
        return 0;
    }
    char *copy = strdup(line + strlen(let_prefix));
    if (!copy) {
        fail("out of memory");
    }
    char *equal = strstr(copy, "=");
    if (!equal) {
        free(copy);
        return 0;
    }
    *equal = '\0';
    char *name = trim_copy(copy);
    if (!parse_ident_expr(name, out_name)) {
        free(name);
        free(copy);
        return 0;
    }
    free(name);
    int ok = parse_simple_expr(equal + 1, out_expr) || parse_eq_var_string_expr(equal + 1, out_expr);
    free(copy);
    if (!ok) {
        free(*out_name);
        *out_name = NULL;
    }
    return ok;
}

static int parse_runtime_expr(const char *text, native_expr_t *out) {
    return parse_simple_expr(text, out) ||
           parse_eq_var_string_expr(text, out) ||
           parse_if_var_var_string_expr(text, out);
}

static int append_native_stmt(native_stmt_program_t *program, native_stmt_t *stmt) {
    native_stmt_t *next = realloc(program->statements, (program->count + 1) * sizeof(native_stmt_t));
    if (!next) {
        fail("out of memory");
    }
    program->statements = next;
    program->statements[program->count++] = *stmt;
    memset(stmt, 0, sizeof(*stmt));
    return 1;
}

static char *expand_compact_braces(const char *source) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    int in_string = 0;
    for (size_t i = 0; source[i]; ++i) {
        char ch = source[i];
        if (ch == '"' && (i == 0 || source[i - 1] != '\\')) {
            in_string = !in_string;
            append_char(&buffer, &length, &capacity, ch);
            continue;
        }
        if (!in_string && ch == '{') {
            append_char(&buffer, &length, &capacity, ch);
            if (source[i + 1] && source[i + 1] != '\n') {
                append_char(&buffer, &length, &capacity, '\n');
            }
            continue;
        }
        if (!in_string && ch == '}') {
            if (length > 0 && buffer[length - 1] != '\n') {
                append_char(&buffer, &length, &capacity, '\n');
            }
            append_char(&buffer, &length, &capacity, ch);
            if (source[i + 1] && source[i + 1] != '\n') {
                append_char(&buffer, &length, &capacity, '\n');
            }
            continue;
        }
        append_char(&buffer, &length, &capacity, ch);
    }
    if (!buffer) {
        buffer = strdup(source);
        if (!buffer) {
            fail("out of memory");
        }
    }
    return buffer;
}

int try_parse_native_stmt_program(const char *source, native_stmt_program_t *out) {
    memset(out, 0, sizeof(*out));
    char *copy = expand_compact_braces(source);
    char *lines[64] = {0};
    size_t count = 0;
    for (char *line = strtok(copy, "\n"); line && count < 64; line = strtok(NULL, "\n")) {
        char *trimmed = trim_copy(line);
        if (trimmed[0] != '\0') {
            lines[count++] = trimmed;
        } else {
            free(trimmed);
        }
    }
    if (count == 0) {
        free(copy);
        return 0;
    }
    size_t i = 0;
    while (i < count) {
        native_stmt_t stmt = {0};
        if (strncmp(lines[i], "let ", 4) == 0) {
            stmt.kind = NATIVE_STMT_LET;
            if (!parse_any_let_line(lines[i], &stmt.name, &stmt.expr)) {
                free_native_stmt(&stmt);
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            append_native_stmt(out, &stmt);
            i += 1;
            continue;
        }
        if (strncmp(lines[i], "print ", 6) == 0) {
            stmt.kind = NATIVE_STMT_PRINT;
            if (!parse_runtime_expr(lines[i] + 6, &stmt.expr)) {
                free_native_stmt(&stmt);
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            append_native_stmt(out, &stmt);
            i += 1;
            continue;
        }
        if (strncmp(lines[i], "if ", 3) == 0) {
            if (i + 4 >= count) {
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            stmt.kind = NATIVE_STMT_IF_STMT;
            size_t header_len = strlen(lines[i]);
            if (header_len < 4 || lines[i][header_len - 1] != '{') {
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            size_t condition_end = header_len - 1;
            while (condition_end > 0 && (lines[i][condition_end - 1] == ' ' || lines[i][condition_end - 1] == '\t')) {
                condition_end--;
            }
            char *condition = calloc(condition_end - 2, 1);
            if (!condition) {
                fail("out of memory");
            }
            memcpy(condition, lines[i] + 3, condition_end - 3);
            condition[condition_end - 3] = '\0';
            char *condition_ident = NULL;
            if (!parse_ident_expr(condition, &condition_ident)) {
                free(condition);
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            free(condition);
            stmt.condition_name = condition_ident;
            size_t else_print_index = 0;
            size_t close_index = 0;
            int compact_else = compact_line_equals(lines[i + 2], "} else {");
            int split_else = compact_line_equals(lines[i + 2], "}") && compact_line_equals(lines[i + 3], "else {");
            if (compact_else) {
                else_print_index = i + 3;
                close_index = i + 4;
            } else if (split_else) {
                if (i + 5 >= count) {
                    free_native_stmt(&stmt);
                    free_native_stmt_program(out);
                    for (size_t j = 0; j < count; ++j) free(lines[j]);
                    free(copy);
                    return 0;
                }
                else_print_index = i + 4;
                close_index = i + 5;
            }
            if (strncmp(lines[i + 1], "print ", 6) != 0 ||
                (!compact_else && !split_else) ||
                strncmp(lines[else_print_index], "print ", 6) != 0 ||
                !compact_line_equals(lines[close_index], "}") ||
                !parse_runtime_expr(lines[i + 1] + 6, &stmt.then_expr) ||
                !parse_runtime_expr(lines[else_print_index] + 6, &stmt.else_expr)) {
                free_native_stmt(&stmt);
                free_native_stmt_program(out);
                for (size_t j = 0; j < count; ++j) free(lines[j]);
                free(copy);
                return 0;
            }
            append_native_stmt(out, &stmt);
            i = close_index + 1;
            continue;
        }
        free_native_stmt_program(out);
        for (size_t j = 0; j < count; ++j) free(lines[j]);
        free(copy);
        return 0;
    }
    for (size_t j = 0; j < count; ++j) free(lines[j]);
    free(copy);
    return out->count > 0;
}

static char *join_lines_slice(char **lines, size_t start, size_t end) {
    size_t total = 1;
    for (size_t i = start; i < end; ++i) {
        total += strlen(lines[i]) + 1;
    }
    char *buffer = calloc(total, 1);
    if (!buffer) {
        fail("out of memory");
    }
    size_t offset = 0;
    for (size_t i = start; i < end; ++i) {
        size_t len = strlen(lines[i]);
        memcpy(buffer + offset, lines[i], len);
        offset += len;
        if (i + 1 < end) {
            buffer[offset++] = '\n';
        }
    }
    buffer[offset] = '\0';
    return buffer;
}

static int parse_call_line(
    const char *line,
    char **out_name,
    char **out_arg,
    size_t *out_arg_count
) {
    const char *call_prefix = "call ";
    if (strncmp(line, call_prefix, strlen(call_prefix)) != 0) {
        return 0;
    }
    const char *call_text = line + strlen(call_prefix);
    const char *open = strchr(call_text, '(');
    size_t len = strlen(call_text);
    if (!open || len == 0 || call_text[len - 1] != ')') {
        return 0;
    }
    size_t name_len = (size_t)(open - call_text);
    char *name = calloc(name_len + 1, 1);
    if (!name) {
        fail("out of memory");
    }
    memcpy(name, call_text, name_len);
    name[name_len] = '\0';
    char *ident = NULL;
    if (!parse_ident_expr(name, &ident)) {
        free(name);
        return 0;
    }
    free(name);
    size_t arg_len = len - (size_t)(open - call_text) - 2;
    char *arg_text = calloc(arg_len + 1, 1);
    if (!arg_text) {
        fail("out of memory");
    }
    memcpy(arg_text, open + 1, arg_len);
    arg_text[arg_len] = '\0';
    char *trimmed_arg = trim_copy(arg_text);
    free(arg_text);
    *out_name = ident;
    *out_arg = NULL;
    *out_arg_count = 0;
    if (trimmed_arg[0] == '\0') {
        free(trimmed_arg);
        return 1;
    }
    char *string_arg = NULL;
    if (!parse_string_literal_expr(trimmed_arg, &string_arg)) {
        free(trimmed_arg);
        free(*out_name);
        *out_name = NULL;
        return 0;
    }
    free(trimmed_arg);
    *out_arg = string_arg;
    *out_arg_count = 1;
    return 1;
}

int try_parse_native_function_program(const char *source, native_function_program_t *out) {
    memset(out, 0, sizeof(*out));
    char *copy = expand_compact_braces(source);
    char *lines[96] = {0};
    size_t count = 0;
    for (char *line = strtok(copy, "\n"); line && count < 96; line = strtok(NULL, "\n")) {
        char *trimmed = trim_copy(line);
        if (trimmed[0] != '\0') {
            lines[count++] = trimmed;
        } else {
            free(trimmed);
        }
    }
    if (count < 3 || strncmp(lines[0], "fn ", 3) != 0) {
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    size_t header_len = strlen(lines[0]);
    if (header_len < 5 || lines[0][header_len - 1] != '{') {
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    char *open_paren = strchr(lines[0] + 3, '(');
    if (!open_paren) {
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    size_t fn_name_len = (size_t)(open_paren - (lines[0] + 3));
    char *fn_name_raw = calloc(fn_name_len + 1, 1);
    if (!fn_name_raw) {
        fail("out of memory");
    }
    memcpy(fn_name_raw, lines[0] + 3, fn_name_len);
    fn_name_raw[fn_name_len] = '\0';
    char *fn_name = NULL;
    if (!parse_ident_expr(fn_name_raw, &fn_name)) {
        free(fn_name_raw);
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    free(fn_name_raw);
    char *param_close = strchr(open_paren, ')');
    if (!param_close) {
        free(fn_name);
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    size_t param_len = (size_t)(param_close - open_paren - 1);
    char *param_name = NULL;
    if (param_len > 0) {
        char *param_raw = calloc(param_len + 1, 1);
        if (!param_raw) {
            fail("out of memory");
        }
        memcpy(param_raw, open_paren + 1, param_len);
        param_raw[param_len] = '\0';
        if (!parse_ident_expr(param_raw, &param_name)) {
            free(param_raw);
            free(fn_name);
            for (size_t i = 0; i < count; ++i) free(lines[i]);
            free(copy);
            return 0;
        }
        free(param_raw);
    }

    size_t close_index = 0;
    int found_close = 0;
    int depth = 1;
    for (size_t i = 1; i < count; ++i) {
        if (compact_line_equals(lines[i], "} else {")) {
            continue;
        }
        if (compact_line_equals(lines[i], "else {")) {
            continue;
        }
        if (compact_line_equals(lines[i], "}")) {
            if (i + 1 < count && compact_line_equals(lines[i + 1], "else {")) {
                continue;
            }
            depth--;
            if (depth == 0) {
                close_index = i;
                found_close = 1;
                break;
            }
            continue;
        }
        size_t line_len = strlen(lines[i]);
        if (line_len >= 4 && strncmp(lines[i], "if ", 3) == 0 && lines[i][line_len - 1] == '{') {
            depth++;
        }
    }
    if (!found_close || close_index <= 1 || close_index + 1 >= count) {
        free(fn_name);
        free(param_name);
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }

    char *body_source = join_lines_slice(lines, 1, close_index);
    if (!try_parse_native_stmt_program(body_source, &out->function.body)) {
        free(body_source);
        free(fn_name);
        free(param_name);
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }
    free(body_source);

    char *call_name = NULL;
    char *call_arg = NULL;
    size_t call_arg_count = 0;
    if (!parse_call_line(lines[close_index + 1], &call_name, &call_arg, &call_arg_count) ||
        strcmp(call_name, fn_name) != 0 ||
        ((param_name == NULL) != (call_arg_count == 0))) {
        free(call_name);
        free(call_arg);
        free_native_stmt_program(&out->function.body);
        free(fn_name);
        free(param_name);
        for (size_t i = 0; i < count; ++i) free(lines[i]);
        free(copy);
        return 0;
    }

    if (close_index + 2 < count) {
        char *top_level_source = join_lines_slice(lines, close_index + 2, count);
        if (!try_parse_native_stmt_program(top_level_source, &out->top_level)) {
            free(top_level_source);
            free(call_name);
            free(call_arg);
            free_native_stmt_program(&out->function.body);
            free(fn_name);
            free(param_name);
            for (size_t i = 0; i < count; ++i) free(lines[i]);
            free(copy);
            return 0;
        }
        free(top_level_source);
    }

    out->function.name = fn_name;
    out->function.param_name = param_name;
    out->call_name = call_name;
    out->call_arg = call_arg;
    for (size_t i = 0; i < count; ++i) free(lines[i]);
    free(copy);
    return 1;
}
