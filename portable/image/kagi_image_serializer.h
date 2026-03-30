#ifndef KAGI_IMAGE_SERIALIZER_H
#define KAGI_IMAGE_SERIALIZER_H

#include "kagi_image_parser.h"

void append_text(char **buffer, size_t *length, size_t *capacity, const char *text);
void append_char(char **buffer, size_t *length, size_t *capacity, char ch);
void append_json_string_to_buffer(char **buffer, size_t *length, size_t *capacity, const char *text);

char *native_stmt_program_to_parse_json(const native_stmt_program_t *program);
char *native_stmt_program_to_hir_json(const native_stmt_program_t *program);
char *native_stmt_program_to_kir_json(const native_stmt_program_t *program);
char *native_stmt_program_to_analysis_json(void);

char *native_function_program_to_parse_json(const native_function_program_t *program);
char *native_function_program_to_hir_json(const native_function_program_t *program);
char *native_function_program_to_kir_json(const native_function_program_t *program);
char *native_function_program_to_analysis_json(const native_function_program_t *program);

#endif
