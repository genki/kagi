#ifndef KAGI_IMAGE_JSON_H
#define KAGI_IMAGE_JSON_H

#include <stddef.h>

void append_text(char **buffer, size_t *length, size_t *capacity, const char *text);
void append_char(char **buffer, size_t *length, size_t *capacity, char ch);
void append_json_string_to_buffer(char **buffer, size_t *length, size_t *capacity, const char *text);

#endif
