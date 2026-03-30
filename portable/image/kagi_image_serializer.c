#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kagi_image_output.h"
#include "kagi_image_parser.h"
#include "kagi_image_serializer.h"

void append_text(char **buffer, size_t *length, size_t *capacity, const char *text) {
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

void append_char(char **buffer, size_t *length, size_t *capacity, char ch) {
    char tmp[2] = {ch, '\0'};
    append_text(buffer, length, capacity, tmp);
}

void append_json_string_to_buffer(char **buffer, size_t *length, size_t *capacity, const char *text) {
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

char *native_stmt_program_to_parse_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"program\",\"functions\":[],\"statements\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 0);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

char *native_stmt_program_to_hir_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"hir_program\",\"functions\":[],\"statements\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 0);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

char *native_stmt_program_to_kir_json(const native_stmt_program_t *program) {
    char *buffer = NULL;
    size_t length = 0;
    size_t capacity = 0;
    append_text(&buffer, &length, &capacity, "{\"kind\":\"kir\",\"functions\":[],\"instructions\":[");
    append_native_stmt_program_json(&buffer, &length, &capacity, program, 1);
    append_text(&buffer, &length, &capacity, "]}");
    return buffer;
}

char *native_stmt_program_to_analysis_json(void) {
    return strdup("{\"kind\":\"analysis_v1\",\"function_arities\":{},\"effects\":{\"program\":[\"print\"],\"functions\":{}}}");
}

char *native_function_program_to_parse_json(const native_function_program_t *program) {
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

char *native_function_program_to_hir_json(const native_function_program_t *program) {
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

char *native_function_program_to_kir_json(const native_function_program_t *program) {
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

char *native_function_program_to_analysis_json(const native_function_program_t *program) {
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
