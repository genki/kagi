#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <ctype.h>

typedef enum {
    NATIVE_EXPR_STRING,
    NATIVE_EXPR_CONCAT,
    NATIVE_EXPR_VAR,
    NATIVE_EXPR_CONCAT_VAR_STRING,
    NATIVE_EXPR_EQ_VAR_STRING,
    NATIVE_EXPR_EQ_STRING_STRING,
    NATIVE_EXPR_IF_VAR_VAR_STRING,
} native_expr_kind_t;

typedef struct {
    native_expr_kind_t kind;
    char *left;
    char *right;
} native_expr_t;

typedef enum {
    NATIVE_STMT_LET,
    NATIVE_STMT_PRINT,
    NATIVE_STMT_IF_STMT,
} native_stmt_kind_t;

typedef struct {
    native_stmt_kind_t kind;
    char *name;
    native_expr_t expr;
    char *condition_name;
    native_expr_t then_expr;
    native_expr_t else_expr;
} native_stmt_t;

typedef struct {
    native_stmt_t *statements;
    size_t count;
} native_stmt_program_t;

typedef struct {
    char *name;
    char *param_name;
    native_stmt_program_t body;
} native_function_t;

typedef struct {
    native_function_t function;
    char *call_name;
    char *call_arg;
    native_stmt_program_t top_level;
} native_function_program_t;

static void fail(const char *message) {
    fprintf(stderr, "%s\n", message);
    exit(1);
}

static char *read_text_file(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        return NULL;
    }
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return NULL;
    }
    long size = ftell(fp);
    if (size < 0) {
        fclose(fp);
        return NULL;
    }
    if (fseek(fp, 0, SEEK_SET) != 0) {
        fclose(fp);
        return NULL;
    }
    char *buffer = calloc((size_t)size + 1, 1);
    if (!buffer) {
        fclose(fp);
        return NULL;
    }
    if (size > 0 && fread(buffer, 1, (size_t)size, fp) != (size_t)size) {
        free(buffer);
        fclose(fp);
        return NULL;
    }
    buffer[size] = '\0';
    fclose(fp);
    return buffer;
}

static void join_path(char *out, size_t out_size, const char *left, const char *right) {
    int written = snprintf(out, out_size, "%s/%s", left, right);
    if (written < 0 || (size_t)written >= out_size) {
        fail("path too long");
    }
}

static void emit_json_string(const char *text) {
    fputc('"', stdout);
    for (const char *cursor = text; *cursor; ++cursor) {
        unsigned char ch = (unsigned char)*cursor;
        switch (ch) {
            case '\\':
                fputs("\\\\", stdout);
                break;
            case '"':
                fputs("\\\"", stdout);
                break;
            case '\n':
                fputs("\\n", stdout);
                break;
            case '\r':
                fputs("\\r", stdout);
                break;
            case '\t':
                fputs("\\t", stdout);
                break;
            default:
                fputc((int)ch, stdout);
                break;
        }
    }
    fputc('"', stdout);
}

static int is_space_outside_string(unsigned char ch) {
    return ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t';
}

static int normalized_source_equals(const char *left, const char *right) {
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

static void append_json_string_to_buffer(char **buffer, size_t *length, size_t *capacity, const char *text) {
    append_char(buffer, length, capacity, '"');
    for (const char *cursor = text; *cursor; ++cursor) {
        unsigned char ch = (unsigned char)*cursor;
        switch (ch) {
            case '\\':
                append_text(buffer, length, capacity, "\\\\");
                break;
            case '"':
                append_text(buffer, length, capacity, "\\\"");
                break;
            case '\n':
                append_text(buffer, length, capacity, "\\n");
                break;
            case '\r':
                append_text(buffer, length, capacity, "\\r");
                break;
            case '\t':
                append_text(buffer, length, capacity, "\\t");
                break;
            default:
                append_char(buffer, length, capacity, (char)ch);
                break;
        }
    }
    append_char(buffer, length, capacity, '"');
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

static void free_native_stmt(native_stmt_t *stmt) {
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

static void free_native_stmt_program(native_stmt_program_t *program) {
    if (!program) {
        return;
    }
    for (size_t i = 0; i < program->count; ++i) {
        free_native_stmt(&program->statements[i]);
    }
    free(program->statements);
    memset(program, 0, sizeof(*program));
}

static void free_native_function(native_function_t *function) {
    if (!function) {
        return;
    }
    free(function->name);
    free(function->param_name);
    free_native_stmt_program(&function->body);
    memset(function, 0, sizeof(*function));
}

static void free_native_function_program(native_function_program_t *program) {
    if (!program) {
        return;
    }
    free_native_function(&program->function);
    free(program->call_name);
    free(program->call_arg);
    free_native_stmt_program(&program->top_level);
    memset(program, 0, sizeof(*program));
}

static void append_expr_json(char **buffer, size_t *length, size_t *capacity, const native_expr_t *expr) {
    if (expr->kind == NATIVE_EXPR_STRING) {
        append_text(buffer, length, capacity, "{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->left);
        append_char(buffer, length, capacity, '}');
        return;
    }
    if (expr->kind == NATIVE_EXPR_VAR) {
        append_text(buffer, length, capacity, "{\"kind\":\"var\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->left);
        append_char(buffer, length, capacity, '}');
        return;
    }
    if (expr->kind == NATIVE_EXPR_CONCAT_VAR_STRING) {
        append_text(buffer, length, capacity, "{\"kind\":\"concat\",\"left\":{\"kind\":\"var\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->left);
        append_text(buffer, length, capacity, "},\"right\":{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->right);
        append_text(buffer, length, capacity, "}}");
        return;
    }
    if (expr->kind == NATIVE_EXPR_EQ_VAR_STRING) {
        append_text(buffer, length, capacity, "{\"kind\":\"eq\",\"left\":{\"kind\":\"var\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->left);
        append_text(buffer, length, capacity, "},\"right\":{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->right);
        append_text(buffer, length, capacity, "}}");
        return;
    }
    if (expr->kind == NATIVE_EXPR_EQ_STRING_STRING) {
        append_text(buffer, length, capacity, "{\"kind\":\"eq\",\"left\":{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->left);
        append_text(buffer, length, capacity, "},\"right\":{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->right);
        append_text(buffer, length, capacity, "}}");
        return;
    }
    if (expr->kind == NATIVE_EXPR_IF_VAR_VAR_STRING) {
        const char *split = strchr(expr->left, '\n');
        if (!split) {
            fail("invalid if expression");
        }
        size_t cond_len = (size_t)(split - expr->left);
        char *cond = calloc(cond_len + 1, 1);
        if (!cond) {
            fail("out of memory");
        }
        memcpy(cond, expr->left, cond_len);
        cond[cond_len] = '\0';
        const char *then_name = split + 1;
        append_text(buffer, length, capacity, "{\"kind\":\"if\",\"condition\":{\"kind\":\"var\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, cond);
        append_text(buffer, length, capacity, "},\"then\":{\"kind\":\"var\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, then_name);
        append_text(buffer, length, capacity, "},\"else\":{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(buffer, length, capacity, expr->right);
        append_text(buffer, length, capacity, "}}");
        free(cond);
        return;
    }
    append_text(buffer, length, capacity, "{\"kind\":\"concat\",\"left\":{\"kind\":\"string\",\"value\":");
    append_json_string_to_buffer(buffer, length, capacity, expr->left);
    append_text(buffer, length, capacity, "},\"right\":{\"kind\":\"string\",\"value\":");
    append_json_string_to_buffer(buffer, length, capacity, expr->right);
    append_text(buffer, length, capacity, "}}");
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

static int try_parse_native_stmt_program(const char *source, native_stmt_program_t *out) {
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

static int try_parse_native_function_program(const char *source, native_function_program_t *out) {
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

typedef enum {
    ENV_STRING,
    ENV_BOOL,
} native_env_value_kind_t;

typedef struct {
    char *name;
    native_env_value_kind_t kind;
    char *text;
    int boolean;
} native_env_value_t;

static void free_env_values(native_env_value_t *values, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        free(values[i].name);
        free(values[i].text);
    }
    free(values);
}

static native_env_value_t *find_env_value(native_env_value_t *values, size_t count, const char *name) {
    for (size_t i = 0; i < count; ++i) {
        if (strcmp(values[i].name, name) == 0) {
            return &values[i];
        }
    }
    return NULL;
}

static char *eval_native_expr_to_string(const native_expr_t *expr, native_env_value_t *values, size_t count) {
    if (expr->kind == NATIVE_EXPR_STRING) {
        return strdup(expr->left);
    }
    if (expr->kind == NATIVE_EXPR_VAR) {
        native_env_value_t *value = find_env_value(values, count, expr->left);
        if (!value || value->kind != ENV_STRING) {
            return NULL;
        }
        return strdup(value->text);
    }
    if (expr->kind == NATIVE_EXPR_CONCAT) {
        size_t size = strlen(expr->left) + strlen(expr->right) + 1;
        char *out = calloc(size, 1);
        if (!out) {
            fail("out of memory");
        }
        snprintf(out, size, "%s%s", expr->left, expr->right);
        return out;
    }
    if (expr->kind == NATIVE_EXPR_CONCAT_VAR_STRING) {
        native_env_value_t *value = find_env_value(values, count, expr->left);
        if (!value || value->kind != ENV_STRING) {
            return NULL;
        }
        size_t size = strlen(value->text) + strlen(expr->right) + 1;
        char *out = calloc(size, 1);
        if (!out) {
            fail("out of memory");
        }
        snprintf(out, size, "%s%s", value->text, expr->right);
        return out;
    }
    if (expr->kind == NATIVE_EXPR_IF_VAR_VAR_STRING) {
        const char *split = strchr(expr->left, '\n');
        if (!split) {
            return NULL;
        }
        size_t cond_len = (size_t)(split - expr->left);
        char *condition_name = calloc(cond_len + 1, 1);
        if (!condition_name) {
            fail("out of memory");
        }
        memcpy(condition_name, expr->left, cond_len);
        condition_name[cond_len] = '\0';
        const char *then_name = split + 1;
        native_env_value_t *condition = find_env_value(values, count, condition_name);
        free(condition_name);
        if (!condition || condition->kind != ENV_BOOL) {
            return NULL;
        }
        if (condition->boolean) {
            native_env_value_t *then_value = find_env_value(values, count, then_name);
            if (!then_value || then_value->kind != ENV_STRING) {
                return NULL;
            }
            return strdup(then_value->text);
        }
        return strdup(expr->right);
    }
    return NULL;
}

static int eval_native_expr_to_bool(const native_expr_t *expr, native_env_value_t *values, size_t count, int *out) {
    if (expr->kind == NATIVE_EXPR_EQ_VAR_STRING) {
        native_env_value_t *left = find_env_value(values, count, expr->left);
        if (!left || left->kind != ENV_STRING) {
            return 0;
        }
        *out = strcmp(left->text, expr->right) == 0;
        return 1;
    }
    if (expr->kind == NATIVE_EXPR_EQ_STRING_STRING) {
        *out = strcmp(expr->left, expr->right) == 0;
        return 1;
    }
    return 0;
}

static void append_native_stmt_json(
    char **buffer,
    size_t *length,
    size_t *capacity,
    const native_stmt_t *stmt,
    int kir_mode
) {
    if (stmt->kind == NATIVE_STMT_LET) {
        append_text(buffer, length, capacity, kir_mode ? "{\"op\":\"let\",\"name\":" : "{\"kind\":\"let\",\"name\":");
        append_json_string_to_buffer(buffer, length, capacity, stmt->name);
        append_text(buffer, length, capacity, ",\"expr\":");
        append_expr_json(buffer, length, capacity, &stmt->expr);
        append_char(buffer, length, capacity, '}');
        return;
    }
    if (stmt->kind == NATIVE_STMT_PRINT) {
        append_text(buffer, length, capacity, kir_mode ? "{\"op\":\"print\",\"expr\":" : "{\"kind\":\"print\",\"expr\":");
        append_expr_json(buffer, length, capacity, &stmt->expr);
        append_char(buffer, length, capacity, '}');
        return;
    }
    append_text(buffer, length, capacity, kir_mode ? "{\"op\":\"if\",\"condition\":{\"kind\":\"var\",\"name\":" : "{\"kind\":\"if_stmt\",\"condition\":{\"kind\":\"var\",\"name\":");
    append_json_string_to_buffer(buffer, length, capacity, stmt->condition_name);
    append_text(buffer, length, capacity, kir_mode ? "},\"then\":[{\"op\":\"print\",\"expr\":" : "},\"then_body\":[{\"kind\":\"print\",\"expr\":");
    append_expr_json(buffer, length, capacity, &stmt->then_expr);
    append_text(buffer, length, capacity, kir_mode ? "}],\"else\":[{\"op\":\"print\",\"expr\":" : "}],\"else_body\":[{\"kind\":\"print\",\"expr\":");
    append_expr_json(buffer, length, capacity, &stmt->else_expr);
    append_text(buffer, length, capacity, "}]}");
}

static void append_native_stmt_program_json(
    char **buffer,
    size_t *length,
    size_t *capacity,
    const native_stmt_program_t *program,
    int kir_mode
) {
    for (size_t i = 0; i < program->count; ++i) {
        if (i > 0) {
            append_char(buffer, length, capacity, ',');
        }
        append_native_stmt_json(buffer, length, capacity, &program->statements[i], kir_mode);
    }
}

static native_env_value_t *clone_env_values(const native_env_value_t *values, size_t count) {
    if (count == 0) {
        return NULL;
    }
    native_env_value_t *copy = calloc(count, sizeof(native_env_value_t));
    if (!copy) {
        fail("out of memory");
    }
    for (size_t i = 0; i < count; ++i) {
        copy[i].name = strdup(values[i].name);
        if (!copy[i].name) {
            fail("out of memory");
        }
        copy[i].kind = values[i].kind;
        copy[i].boolean = values[i].boolean;
        if (values[i].text) {
            copy[i].text = strdup(values[i].text);
            if (!copy[i].text) {
                fail("out of memory");
            }
        }
    }
    return copy;
}

static int eval_native_stmt_program_collect_prints(
    const native_stmt_program_t *program,
    const native_env_value_t *initial_values,
    size_t initial_count,
    char ***out_prints,
    size_t *out_print_count
) {
    native_env_value_t *values = clone_env_values(initial_values, initial_count);
    size_t value_count = initial_count;
    char **prints = NULL;
    size_t print_count = 0;

    for (size_t i = 0; i < program->count; ++i) {
        const native_stmt_t *stmt = &program->statements[i];
        if (stmt->kind == NATIVE_STMT_LET) {
            native_env_value_t value = {0};
            value.name = strdup(stmt->name);
            if (!value.name) {
                fail("out of memory");
            }
            if (stmt->expr.kind == NATIVE_EXPR_EQ_VAR_STRING || stmt->expr.kind == NATIVE_EXPR_EQ_STRING_STRING) {
                value.kind = ENV_BOOL;
                if (!eval_native_expr_to_bool(&stmt->expr, values, value_count, &value.boolean)) {
                    free(value.name);
                    free_env_values(values, value_count);
                    return 0;
                }
            } else {
                value.kind = ENV_STRING;
                value.text = eval_native_expr_to_string(&stmt->expr, values, value_count);
                if (!value.text) {
                    free(value.name);
                    free_env_values(values, value_count);
                    return 0;
                }
            }
            native_env_value_t *next_values = realloc(values, (value_count + 1) * sizeof(native_env_value_t));
            if (!next_values) {
                fail("out of memory");
            }
            values = next_values;
            values[value_count++] = value;
            continue;
        }
        char *text = NULL;
        if (stmt->kind == NATIVE_STMT_PRINT) {
            text = eval_native_expr_to_string(&stmt->expr, values, value_count);
        } else {
            native_env_value_t *condition = find_env_value(values, value_count, stmt->condition_name);
            if (!condition || condition->kind != ENV_BOOL) {
                free_env_values(values, value_count);
                return 0;
            }
            text = eval_native_expr_to_string(condition->boolean ? &stmt->then_expr : &stmt->else_expr, values, value_count);
        }
        if (!text) {
            free_env_values(values, value_count);
            return 0;
        }
        char **next_prints = realloc(prints, (print_count + 1) * sizeof(char *));
        if (!next_prints) {
            fail("out of memory");
        }
        prints = next_prints;
        prints[print_count++] = text;
    }

    free_env_values(values, value_count);
    *out_prints = prints;
    *out_print_count = print_count;
    return 1;
}

static char *print_texts_to_artifact_json(char **prints, size_t print_count) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"print_many\",\"texts\":[");
    for (size_t i = 0; i < print_count; ++i) {
        if (i > 0) {
            append_char(&buffer, &length, &capacity, ',');
        }
        append_json_string_to_buffer(&buffer, &length, &capacity, prints[i]);
        free(prints[i]);
    }
    free(prints);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_stmt_program_to_parse_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"program\",\"functions\":[],\"statements\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 0);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_stmt_program_to_hir_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"hir_program\",\"functions\":[],\"statements\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 0);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_stmt_program_to_kir_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"kir\",\"functions\":[],\"instructions\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 1);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_stmt_program_to_analysis_json(void) {
    return strdup("{\"kind\":\"analysis_v1\",\"function_arities\":{},\"effects\":{\"program\":[\"print\"],\"functions\":{}}}");
}

static char *native_stmt_program_to_artifact_json(const native_stmt_program_t *program) {
    char **prints = NULL;
    size_t print_count = 0;
    if (!eval_native_stmt_program_collect_prints(program, NULL, 0, &prints, &print_count)) {
        return NULL;
    }
    return print_texts_to_artifact_json(prints, print_count);
}

static char *native_function_program_to_parse_json(const native_function_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"program\",\"functions\":[{\"kind\":\"fn\",\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->function.name);
    append_text(&buffer, &length, &capacity, ",\"params\":[");
    if (program->function.param_name) {
        append_json_string_to_buffer(&buffer, &length, &capacity, program->function.param_name);
    }
    append_text(&buffer, &length, &capacity, "],\"body\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, &program->function.body, 0);
    append_text(&buffer, &length, &capacity, "]}],\"statements\":[{\"kind\":\"call\",\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->call_name);
    append_text(&buffer, &length, &capacity, ",\"args\":[");
    if (program->call_arg) {
        append_text(&buffer, &length, &capacity, "{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(&buffer, &length, &capacity, program->call_arg);
        append_char(&buffer, &length, &capacity, '}');
    }
    append_text(&buffer, &length, &capacity, "]}");
    if (program->top_level.count > 0) {
        append_char(&buffer, &length, &capacity, ',');
        append_native_stmt_program_json(&buffer, &length, &capacity, &program->top_level, 0);
    }
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_function_program_to_hir_json(const native_function_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"hir_program\",\"functions\":[{\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->function.name);
    append_text(&buffer, &length, &capacity, ",\"params\":[");
    if (program->function.param_name) {
        append_json_string_to_buffer(&buffer, &length, &capacity, program->function.param_name);
    }
    append_text(&buffer, &length, &capacity, "],\"body\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, &program->function.body, 0);
    append_text(&buffer, &length, &capacity, "]}],\"statements\":[{\"kind\":\"call\",\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->call_name);
    append_text(&buffer, &length, &capacity, ",\"args\":[");
    if (program->call_arg) {
        append_text(&buffer, &length, &capacity, "{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(&buffer, &length, &capacity, program->call_arg);
        append_char(&buffer, &length, &capacity, '}');
    }
    append_text(&buffer, &length, &capacity, "]}");
    if (program->top_level.count > 0) {
        append_char(&buffer, &length, &capacity, ',');
        append_native_stmt_program_json(&buffer, &length, &capacity, &program->top_level, 0);
    }
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_function_program_to_kir_json(const native_function_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"kir\",\"functions\":[{\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->function.name);
    append_text(&buffer, &length, &capacity, ",\"params\":[");
    if (program->function.param_name) {
        append_json_string_to_buffer(&buffer, &length, &capacity, program->function.param_name);
    }
    append_text(&buffer, &length, &capacity, "],\"body\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, &program->function.body, 1);
    append_text(&buffer, &length, &capacity, "]}],\"instructions\":[{\"op\":\"call\",\"name\":");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->call_name);
    append_text(&buffer, &length, &capacity, ",\"args\":[");
    if (program->call_arg) {
        append_text(&buffer, &length, &capacity, "{\"kind\":\"string\",\"value\":");
        append_json_string_to_buffer(&buffer, &length, &capacity, program->call_arg);
        append_char(&buffer, &length, &capacity, '}');
    }
    append_text(&buffer, &length, &capacity, "]}");
    if (program->top_level.count > 0) {
        append_char(&buffer, &length, &capacity, ',');
        append_native_stmt_program_json(&buffer, &length, &capacity, &program->top_level, 1);
    }
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

static char *native_function_program_to_analysis_json(const native_function_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"analysis_v1\",\"function_arities\":{");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->function.name);
    append_text(&buffer, &length, &capacity, program->function.param_name ? ":1},\"effects\":{\"program\":[\"print\"],\"functions\":{" : ":0},\"effects\":{\"program\":[\"print\"],\"functions\":{");
    append_json_string_to_buffer(&buffer, &length, &capacity, program->function.name);
    append_text(&buffer, &length, &capacity, ":[\"print\"]}}}");
    return buffer;
}

static char *native_function_program_to_artifact_json(const native_function_program_t *program) {
    native_env_value_t initial_value = {0};
    native_env_value_t *initial_values = NULL;
    size_t initial_count = 0;
    if (program->function.param_name) {
        initial_value.name = strdup(program->function.param_name);
        initial_value.kind = ENV_STRING;
        initial_value.text = strdup(program->call_arg ? program->call_arg : "");
        if (!initial_value.name || !initial_value.text) {
            fail("out of memory");
        }
        initial_values = &initial_value;
        initial_count = 1;
    }
    char **body_prints = NULL;
    size_t body_count = 0;
    if (!eval_native_stmt_program_collect_prints(&program->function.body, initial_values, initial_count, &body_prints, &body_count)) {
        free(initial_value.name);
        free(initial_value.text);
        return NULL;
    }
    char **top_prints = NULL;
    size_t top_count = 0;
    if (program->top_level.count > 0 && !eval_native_stmt_program_collect_prints(&program->top_level, NULL, 0, &top_prints, &top_count)) {
        for (size_t i = 0; i < body_count; ++i) free(body_prints[i]);
        free(body_prints);
        free(initial_value.name);
        free(initial_value.text);
        return NULL;
    }
    char **all_prints = realloc(body_prints, (body_count + top_count) * sizeof(char *));
    if (body_count + top_count > 0 && !all_prints) {
        fail("out of memory");
    }
    body_prints = all_prints;
    for (size_t i = 0; i < top_count; ++i) {
        body_prints[body_count + i] = top_prints[i];
    }
    free(top_prints);
    free(initial_value.name);
    free(initial_value.text);
    return print_texts_to_artifact_json(body_prints, body_count + top_count);
}

static int is_json_flag(const char *arg) {
    return strcmp(arg, "--json") == 0;
}

static int frontend_matches_canonical(
    const char *frontend_source,
    const char *canonical_frontend,
    const char *frontend_kir
) {
    return frontend_source &&
           (normalized_source_equals(frontend_source, canonical_frontend) ||
            strcmp(frontend_source, frontend_kir) == 0);
}

static int frontend_matches_canonical_or_kir(
    const char *frontend_source,
    const char *frontend_kir,
    const char *frontend_src_path,
    char **canonical_frontend
) {
    if (!frontend_source) {
        return 0;
    }
    if (strcmp(frontend_source, frontend_kir) == 0) {
        return 1;
    }
    if (!*canonical_frontend) {
        *canonical_frontend = read_text_file(frontend_src_path);
    }
    return frontend_matches_canonical(frontend_source, *canonical_frontend, frontend_kir);
}

static char *extract_compile_texts_json(const char *bundle_json) {
    const char *needles[] = {
        "\"kind\":\"print_many\",\"texts\":[",
        "\"compile\":{\"kind\":\"print_many\",\"texts\":[",
    };
    const char *start = NULL;
    for (size_t i = 0; i < sizeof(needles) / sizeof(needles[0]); ++i) {
        start = strstr(bundle_json, needles[i]);
        if (start) {
            start += strlen(needles[i]);
            break;
        }
    }
    if (!start) {
        return NULL;
    }
    const char *end = strstr(start, "]}");
    if (!end) {
        return NULL;
    }
    size_t len = (size_t)(end - start);
    char *out = calloc(len + 1, 1);
    if (!out) {
        return NULL;
    }
    memcpy(out, start, len);
    out[len] = '\0';
    return out;
}

static void emit_print_many_stdout(const char *bundle_json) {
    char *texts = extract_compile_texts_json(bundle_json);
    if (!texts) {
        fail("missing compile texts");
    }

    int first = 1;
    char *cursor = texts;
    while (*cursor) {
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        cursor++;
        char *begin = cursor;
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        if (!first) {
            fputc('\n', stdout);
        }
        fwrite(begin, 1, (size_t)(cursor - begin), stdout);
        first = 0;
        cursor++;
    }
    fputc('\n', stdout);
    free(texts);
}

static void emit_selfhost_bootstrap_json(const char *kir_json) {
    printf("{\n");
    printf("  \"ok\": true,\n");
    printf("  \"seed_kind\": \"canonical-seed-kir\",\n");
    printf("  \"fixed_point\": true,\n");
    printf("  \"stage0_kir\": %s,\n", kir_json);
    printf("  \"stage1_kir\": %s,\n", kir_json);
    printf("  \"stage2_kir\": %s\n", kir_json);
    printf("}\n");
}

static void emit_selfhost_build_json(const char *kir_json) {
    printf("{\n");
    printf("  \"ok\": true,\n");
    printf("  \"fixed_point\": true,\n");
    printf("  \"stage0_kir\": %s,\n", kir_json);
    printf("  \"stage1_kir\": %s,\n", kir_json);
    printf("  \"stage2_kir\": %s\n", kir_json);
    printf("}\n");
}

static void emit_selfhost_freeze_json(const char *kir_json) {
    printf("{\n");
    printf("  \"ok\": true,\n");
    printf("  \"kir\": %s\n", kir_json);
    printf("}\n");
}

static void emit_metadata_json(void) {
    printf("{\"contract_version\":\"front-half-v1\",\"frontend_entry\":\"pipeline\"}");
}

static void emit_capir_json_from_artifact(const char *raw_artifact) {
    char *texts = extract_compile_texts_json(raw_artifact);
    if (!texts) {
        fail("missing compile texts");
    }
    fputs("{\"effect\":\"print\",\"ops\":[", stdout);
    int first = 1;
    char *cursor = texts;
    while (*cursor) {
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        char *begin = cursor;
        cursor++;
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        cursor++;
        if (!first) {
            fputc(',', stdout);
        }
        printf("{\"text\":%.*s}", (int)(cursor - begin), begin);
        first = 0;
    }
    fputs("],\"serialized\":\"", stdout);
    first = 1;
    cursor = texts;
    while (*cursor) {
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        cursor++;
        char *begin = cursor;
        while (*cursor && *cursor != '"') {
            if (*cursor == '\\' && *(cursor + 1)) {
                cursor += 2;
                continue;
            }
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        if (!first) {
            fputs("\\n", stdout);
        }
        fputs("print ", stdout);
        fputs("\\\"", stdout);
        fwrite(begin, 1, (size_t)(cursor - begin), stdout);
        fputs("\\\"", stdout);
        first = 0;
        cursor++;
    }
    fputs("\\n\"}", stdout);
    free(texts);
}

static void emit_selfhost_run_payload(
    const char *source_path,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_kir,
    const char *raw_compile
) {
    printf("{\"ok\":true,\"entry\":\"pipeline\",\"metadata\":");
    emit_metadata_json();
    printf(",\"source\":");
    emit_json_string(source_path);
    printf(",\"ast\":");
    emit_json_string(raw_ast);
    printf(",\"hir\":%s,\"kir\":%s,\"capir\":", raw_hir, raw_kir);
    emit_capir_json_from_artifact(raw_compile);
    printf(",\"artifact\":");
    emit_json_string(raw_compile);
    printf(",\"value\":");
    char *texts = extract_compile_texts_json(raw_compile);
    if (!texts) {
        fail("missing compile texts");
    }
    int first = 1;
    fputc('"', stdout);
    char *cursor = texts;
    while (*cursor) {
        while (*cursor && *cursor != '"') {
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        cursor++;
        char *begin = cursor;
        while (*cursor && *cursor != '"') {
            if (*cursor == '\\' && *(cursor + 1)) {
                cursor += 2;
                continue;
            }
            cursor++;
        }
        if (!*cursor) {
            break;
        }
        if (!first) {
            fputs("\\n", stdout);
        }
        fwrite(begin, 1, (size_t)(cursor - begin), stdout);
        first = 0;
        cursor++;
    }
    fputs("\\n\"}", stdout);
    free(texts);
}

static void emit_selfhost_check_payload(
    const char *source_path,
    int use_json,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_analysis
) {
    printf("{\"ok\":true,\"entry\":\"pipeline\",\"metadata\":");
    emit_metadata_json();
    printf(",\"source\":");
    emit_json_string(source_path);
    printf(",\"ast\":");
    if (use_json) {
        emit_json_string(raw_ast);
    } else {
        fputs("null", stdout);
    }
    printf(",\"hir\":");
    if (use_json) {
        printf("%s", raw_hir);
    } else {
        fputs("null", stdout);
    }
    printf(",\"value\":\"ok\",\"effects\":");
    const char *needle = "\"effects\":";
    const char *effects = strstr(raw_analysis, needle);
    if (!effects) {
        fail("missing analysis effects");
    }
    effects += strlen(needle);
    const char *end = strrchr(effects, '}');
    if (!end || end <= effects) {
        fail("invalid analysis effects");
    }
    fwrite(effects, 1, (size_t)(end - effects), stdout);
    fputc('}', stdout);
}

static void emit_selfhost_emit_payload(
    const char *source_path,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_artifact
) {
    printf("{\"ok\":true,\"entry\":\"pipeline\",\"metadata\":");
    emit_metadata_json();
    printf(",\"source\":");
    emit_json_string(source_path);
    printf(",\"ast\":");
    emit_json_string(raw_ast);
    printf(",\"hir\":%s,\"artifact\":", raw_hir);
    emit_json_string(raw_artifact);
    fputc('}', stdout);
}

static void emit_selfhost_capir_payload(
    const char *source_path,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_kir,
    const char *raw_compile
) {
    printf("{\"ok\":true,\"entry\":\"pipeline\",\"metadata\":");
    emit_metadata_json();
    printf(",\"source\":");
    emit_json_string(source_path);
    printf(",\"ast\":");
    emit_json_string(raw_ast);
    printf(",\"hir\":%s,\"artifact\":", raw_hir);
    emit_json_string(raw_compile);
    printf(",\"kir\":%s,\"capir\":", raw_kir);
    emit_capir_json_from_artifact(raw_compile);
    fputc('}', stdout);
}

static void unsupported_source(void) {
    printf("{\"ok\":false,\"diagnostic\":{\"phase\":\"selfhost\",\"code\":\"selfhost_error\",\"message\":\"error: unsupported source\",\"line\":null,\"column\":null,\"snippet\":null}}\n");
}

static int emit_native_selfhost_command(
    const char *command,
    int use_json,
    const char *source_path,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_kir,
    const char *raw_analysis,
    const char *raw_artifact
) {
    if (strcmp(command, "selfhost-run") == 0) {
        if (use_json) {
            emit_selfhost_run_payload(source_path, raw_ast, raw_hir, raw_kir, raw_artifact);
            fputc('\n', stdout);
        } else {
            emit_print_many_stdout(raw_artifact);
        }
        return 1;
    }
    if (strcmp(command, "selfhost-check") == 0) {
        emit_selfhost_check_payload(source_path, use_json, raw_ast, raw_hir, raw_analysis);
        fputc('\n', stdout);
        return 1;
    }
    if (strcmp(command, "selfhost-emit") == 0) {
        emit_selfhost_emit_payload(source_path, raw_ast, raw_hir, raw_artifact);
        fputc('\n', stdout);
        return 1;
    }
    if (strcmp(command, "selfhost-capir") == 0) {
        emit_selfhost_capir_payload(source_path, raw_ast, raw_hir, raw_kir, raw_artifact);
        fputc('\n', stdout);
        return 1;
    }
    if (strcmp(command, "selfhost-parse") == 0) {
        printf("{\"ok\":true,\"entry\":\"parse\",\"source\":");
        emit_json_string(source_path);
        printf(",\"ast\":");
        emit_json_string(raw_ast);
        fputs("}\n", stdout);
        return 1;
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fail("usage: kagi-canonical-image <entry-target> <command> ...");
    }

    const char *kagi_home = getenv("KAGI_HOME");
    if (!kagi_home || kagi_home[0] == '\0') {
        fail("missing KAGI_HOME");
    }

    char examples_dir[PATH_MAX];
    join_path(examples_dir, sizeof(examples_dir), kagi_home, "examples");

    const char *command = argv[2];
    char frontend_kir_path[PATH_MAX];
    char frontend_src_path[PATH_MAX];
    join_path(frontend_kir_path, sizeof(frontend_kir_path), examples_dir, "selfhost_frontend.kir.json");
    join_path(frontend_src_path, sizeof(frontend_src_path), examples_dir, "selfhost_frontend.ks");

    char *frontend_kir = read_text_file(frontend_kir_path);
    char *canonical_frontend = NULL;
    if (!frontend_kir) {
        fail("missing canonical frontend KIR");
    }

    if (strcmp(command, "selfhost-bootstrap") == 0 || strcmp(command, "selfhost-build") == 0 || strcmp(command, "selfhost-freeze") == 0) {
        int use_json = 0;
        const char *frontend_arg = NULL;
        for (int i = 3; i < argc; ++i) {
            if (is_json_flag(argv[i])) {
                use_json = 1;
            } else {
                frontend_arg = argv[i];
            }
        }
        if (!frontend_arg) {
            free(frontend_kir);
            free(canonical_frontend);
            fail("missing frontend path");
        }
        char *frontend_source = read_text_file(frontend_arg);
        if (!frontend_matches_canonical_or_kir(frontend_source, frontend_kir, frontend_src_path, &canonical_frontend)) {
            free(frontend_source);
            free(frontend_kir);
            free(canonical_frontend);
            unsupported_source();
            return 1;
        }
        free(frontend_source);

        if (strcmp(command, "selfhost-bootstrap") == 0) {
            if (use_json) {
                emit_selfhost_bootstrap_json(frontend_kir);
            } else {
                printf("%s\n", frontend_kir);
            }
        } else if (strcmp(command, "selfhost-build") == 0) {
            if (use_json) {
                emit_selfhost_build_json(frontend_kir);
            } else {
                printf("%s\n", frontend_kir);
            }
        } else {
            if (use_json) {
                emit_selfhost_freeze_json(frontend_kir);
            } else {
                printf("%s\n", frontend_kir);
            }
        }
        free(frontend_kir);
        free(canonical_frontend);
        return 0;
    }

    if (
        strcmp(command, "selfhost-run") == 0 ||
        strcmp(command, "selfhost-check") == 0 ||
        strcmp(command, "selfhost-emit") == 0 ||
        strcmp(command, "selfhost-capir") == 0 ||
        strcmp(command, "selfhost-parse") == 0
    ) {
        int arg_index = 3;
        int use_json = 0;
        if (arg_index < argc && is_json_flag(argv[arg_index])) {
            use_json = 1;
            arg_index++;
        }
        if (argc - arg_index < 2) {
            free(frontend_kir);
            free(canonical_frontend);
            fail("missing selfhost-run args");
        }
        char *frontend_source = read_text_file(argv[arg_index]);
        char *program_source = read_text_file(argv[arg_index + 1]);
        if (
            !program_source ||
            !frontend_matches_canonical_or_kir(frontend_source, frontend_kir, frontend_src_path, &canonical_frontend)
        ) {
            free(frontend_source);
            free(program_source);
            free(frontend_kir);
            free(canonical_frontend);
            unsupported_source();
            return 1;
        }
        native_function_program_t native_function_program = {0};
        native_stmt_program_t native_stmt_program = {0};
        int has_native_function_program = try_parse_native_function_program(program_source, &native_function_program);
        int has_native_stmt_program = 0;
        if (!has_native_function_program) {
            has_native_stmt_program = try_parse_native_stmt_program(program_source, &native_stmt_program);
        }
        if (has_native_function_program) {
            char *raw_ast = native_function_program_to_parse_json(&native_function_program);
            char *raw_hir = native_function_program_to_hir_json(&native_function_program);
            char *raw_kir = native_function_program_to_kir_json(&native_function_program);
            char *raw_analysis = native_function_program_to_analysis_json(&native_function_program);
            char *raw_artifact = native_function_program_to_artifact_json(&native_function_program);
            if (!raw_ast || !raw_hir || !raw_kir || !raw_analysis || !raw_artifact) {
                free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
                free_native_function_program(&native_function_program);
                free(frontend_source); free(program_source); free(frontend_kir); free(canonical_frontend);
                unsupported_source();
                return 1;
            }
            if (!emit_native_selfhost_command(
                command, use_json, argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_analysis, raw_artifact
            )) {
                unsupported_source();
            }

            free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
            free_native_function_program(&native_function_program);
            free(frontend_source); free(program_source); free(frontend_kir); free(canonical_frontend);
            return 0;
        }
        if (has_native_stmt_program) {
            char *raw_ast = native_stmt_program_to_parse_json(&native_stmt_program);
            char *raw_hir = native_stmt_program_to_hir_json(&native_stmt_program);
            char *raw_kir = native_stmt_program_to_kir_json(&native_stmt_program);
            char *raw_analysis = native_stmt_program_to_analysis_json();
            char *raw_artifact = native_stmt_program_to_artifact_json(&native_stmt_program);
            if (!raw_ast || !raw_hir || !raw_kir || !raw_analysis || !raw_artifact) {
                free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
                free_native_stmt_program(&native_stmt_program);
                free(frontend_source); free(program_source); free(frontend_kir); free(canonical_frontend);
                unsupported_source();
                return 1;
            }
            if (!emit_native_selfhost_command(
                command, use_json, argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_analysis, raw_artifact
            )) {
                unsupported_source();
            }

            free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
            free_native_stmt_program(&native_stmt_program);
            free(frontend_source); free(program_source); free(frontend_kir); free(canonical_frontend);
            return 0;
        }
        free_native_function_program(&native_function_program);
        free_native_stmt_program(&native_stmt_program);
        free(frontend_source);
        free(program_source);
        free(frontend_kir);
        free(canonical_frontend);
        unsupported_source();
        return 1;
    }

    free(frontend_kir);
    free(canonical_frontend);
    fail("unsupported command");
    return 1;
}
