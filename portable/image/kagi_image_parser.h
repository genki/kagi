#ifndef KAGI_IMAGE_PARSER_H
#define KAGI_IMAGE_PARSER_H

#include <stddef.h>

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

int normalized_source_equals(const char *left, const char *right);

void free_native_stmt(native_stmt_t *stmt);
void free_native_stmt_program(native_stmt_program_t *program);
void free_native_function(native_function_t *function);
void free_native_function_program(native_function_program_t *program);

int try_parse_native_stmt_program(const char *source, native_stmt_program_t *out);
int try_parse_native_function_program(const char *source, native_function_program_t *out);

#endif
