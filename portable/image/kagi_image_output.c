#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kagi_image_output.h"

void fail(const char *message) {
    fprintf(stderr, "%s\n", message);
    exit(1);
}

void emit_json_string(const char *text) {
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

static void emit_selfhost_fixed_point_json(const char *seed_kind, const char *kir_json) {
    printf("{\n");
    printf("  \"ok\": true,\n");
    if (seed_kind) {
        printf("  \"seed_kind\": \"%s\",\n", seed_kind);
    }
    printf("  \"fixed_point\": true,\n");
    printf("  \"stage0_kir\": %s,\n", kir_json);
    printf("  \"stage1_kir\": %s,\n", kir_json);
    printf("  \"stage2_kir\": %s\n", kir_json);
    printf("}\n");
}

void emit_selfhost_bootstrap_json(const char *kir_json) {
    emit_selfhost_fixed_point_json("canonical-seed-kir", kir_json);
}

void emit_selfhost_build_json(const char *kir_json) {
    emit_selfhost_fixed_point_json(NULL, kir_json);
}

void emit_selfhost_freeze_json(const char *kir_json) {
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

void unsupported_source(void) {
    printf("{\"ok\":false,\"diagnostic\":{\"phase\":\"selfhost\",\"code\":\"selfhost_error\",\"message\":\"error: unsupported source\",\"line\":null,\"column\":null,\"snippet\":null}}\n");
}

int is_selfhost_fixed_point_command(const char *command) {
    return strcmp(command, "selfhost-bootstrap") == 0 ||
           strcmp(command, "selfhost-build") == 0 ||
           strcmp(command, "selfhost-freeze") == 0;
}

int emit_native_selfhost_command(
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
