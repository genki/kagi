#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kagi_image_json.h"
#include "kagi_image_output.h"
#include "kagi_image_parser.h"
#include "kagi_image_serializer.h"
#include "kagi_image_eval.h"

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

char *native_stmt_program_to_artifact_json(const native_stmt_program_t *program) {
    char **prints = NULL;
    size_t print_count = 0;
    if (!eval_native_stmt_program_collect_prints(program, NULL, 0, &prints, &print_count)) {
        return NULL;
    }
    return print_texts_to_artifact_json(prints, print_count);
}

char *native_function_program_to_artifact_json(const native_function_program_t *program) {
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
