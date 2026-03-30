#ifndef KAGI_IMAGE_EVAL_H
#define KAGI_IMAGE_EVAL_H

#include "kagi_image_parser.h"

char *native_stmt_program_to_artifact_json(const native_stmt_program_t *program);
char *native_function_program_to_artifact_json(const native_function_program_t *program);

#endif
