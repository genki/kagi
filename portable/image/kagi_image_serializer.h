#ifndef KAGI_IMAGE_SERIALIZER_H
#define KAGI_IMAGE_SERIALIZER_H

#include "kagi_image_parser.h"

char *native_stmt_program_to_parse_json(const native_stmt_program_t *program);
char *native_stmt_program_to_hir_json(const native_stmt_program_t *program);
char *native_stmt_program_to_kir_json(const native_stmt_program_t *program);
char *native_stmt_program_to_analysis_json(void);

char *native_function_program_to_parse_json(const native_function_program_t *program);
char *native_function_program_to_hir_json(const native_function_program_t *program);
char *native_function_program_to_kir_json(const native_function_program_t *program);
char *native_function_program_to_analysis_json(const native_function_program_t *program);

#endif
