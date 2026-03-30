#include <stdlib.h>
#include <string.h>

#include "kagi_image_output.h"
#include "kagi_image_json.h"

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
