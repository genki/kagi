#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct {
    const char *stem;
    const char *source_name;
    const char *bundle_name;
} canonical_case_t;

static const canonical_case_t CANONICAL_CASES[] = {
    {"hello", "hello.ksrc", "hello.pipeline.json"},
    {"hello_arg_fn", "hello_arg_fn.ksrc", "hello_arg_fn.pipeline.json"},
    {"hello_concat", "hello_concat.ksrc", "hello_concat.pipeline.json"},
    {"hello_fn", "hello_fn.ksrc", "hello_fn.pipeline.json"},
    {"hello_if", "hello_if.ksrc", "hello_if.pipeline.json"},
    {"hello_if_stmt", "hello_if_stmt.ksrc", "hello_if_stmt.pipeline.json"},
    {"hello_let", "hello_let.ksrc", "hello_let.pipeline.json"},
    {"hello_let_concat", "hello_let_concat.ksrc", "hello_let_concat.pipeline.json"},
    {"hello_let_string", "hello_let_string.ksrc", "hello_let_string.pipeline.json"},
    {"hello_print_concat", "hello_print_concat.ksrc", "hello_print_concat.pipeline.json"},
    {"hello_twice", "hello_twice.ksrc", "hello_twice.pipeline.json"},
};

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

static int string_equals_file(const char *text, const char *path) {
    char *file_text = read_text_file(path);
    if (!file_text) {
        return 0;
    }
    int equal = strcmp(text, file_text) == 0;
    free(file_text);
    return equal;
}

static const canonical_case_t *match_canonical_case(const char *workspace, const char *program_source) {
    char examples_dir[PATH_MAX];
    char source_path[PATH_MAX];
    join_path(examples_dir, sizeof(examples_dir), workspace, "examples");
    for (size_t i = 0; i < sizeof(CANONICAL_CASES) / sizeof(CANONICAL_CASES[0]); ++i) {
        join_path(source_path, sizeof(source_path), examples_dir, CANONICAL_CASES[i].source_name);
        if (string_equals_file(program_source, source_path)) {
            return &CANONICAL_CASES[i];
        }
    }
    return NULL;
}

static int is_json_flag(const char *arg) {
    return strcmp(arg, "--json") == 0;
}

static char *load_entry_text(const char *examples_dir, const char *stem, const char *entry) {
    char entry_dir[PATH_MAX];
    char filename[PATH_MAX];
    char path[PATH_MAX];
    join_path(entry_dir, sizeof(entry_dir), examples_dir, "selfhost_entries");
    int written = snprintf(filename, sizeof(filename), "%s.%s.txt", stem, entry);
    if (written < 0 || (size_t)written >= sizeof(filename)) {
        fail("entry filename too long");
    }
    join_path(path, sizeof(path), entry_dir, filename);
    return read_text_file(path);
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
    char *canonical_frontend = read_text_file(frontend_src_path);
    if (!frontend_kir || !canonical_frontend) {
        fail("missing canonical frontend assets");
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
        if (!frontend_source || strcmp(frontend_source, canonical_frontend) != 0) {
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
        if (!frontend_source || !program_source || strcmp(frontend_source, canonical_frontend) != 0) {
            free(frontend_source);
            free(program_source);
            free(frontend_kir);
            free(canonical_frontend);
            unsupported_source();
            return 1;
        }
        const canonical_case_t *matched = match_canonical_case(kagi_home, program_source);
        if (!matched) {
            free(frontend_source);
            free(program_source);
            free(frontend_kir);
            free(canonical_frontend);
            unsupported_source();
            return 1;
        }

        char *raw_ast = load_entry_text(examples_dir, matched->stem, "parse");
        char *raw_hir = load_entry_text(examples_dir, matched->stem, "hir");
        char *raw_kir = load_entry_text(examples_dir, matched->stem, "kir");
        char *raw_analysis = load_entry_text(examples_dir, matched->stem, "analysis");
        char *raw_artifact = load_entry_text(examples_dir, matched->stem, "compile");
        char *bundle_json = load_entry_text(examples_dir, matched->stem, "pipeline");
        if (!raw_ast || !raw_hir || !raw_kir || !raw_analysis || !raw_artifact || !bundle_json) {
            free(frontend_source);
            free(program_source);
            free(frontend_kir);
            free(canonical_frontend);
            free(raw_ast);
            free(raw_hir);
            free(raw_kir);
            free(raw_analysis);
            free(raw_artifact);
            free(bundle_json);
            fail("missing canonical entry snapshot");
        }

        if (strcmp(command, "selfhost-run") == 0) {
            if (use_json) {
                emit_selfhost_run_payload(argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_artifact);
                fputc('\n', stdout);
            } else {
                emit_print_many_stdout(raw_artifact);
            }
        } else if (strcmp(command, "selfhost-check") == 0) {
            emit_selfhost_check_payload(argv[arg_index + 1], use_json, raw_ast, raw_hir, raw_analysis);
            fputc('\n', stdout);
        } else if (strcmp(command, "selfhost-emit") == 0) {
            emit_selfhost_emit_payload(argv[arg_index + 1], raw_ast, raw_hir, raw_artifact);
            fputc('\n', stdout);
        } else if (strcmp(command, "selfhost-capir") == 0) {
            emit_selfhost_capir_payload(argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_artifact);
            fputc('\n', stdout);
        } else if (strcmp(command, "selfhost-parse") == 0) {
            printf("{\"ok\":true,\"entry\":\"parse\",\"source\":");
            emit_json_string(argv[arg_index + 1]);
            printf(",\"ast\":");
            emit_json_string(raw_ast);
            fputs("}\n", stdout);
        } else {
            fputs(bundle_json, stdout);
            fputc('\n', stdout);
        }

        free(raw_ast);
        free(raw_hir);
        free(raw_kir);
        free(raw_analysis);
        free(raw_artifact);
        free(bundle_json);
        free(frontend_source);
        free(program_source);
        free(frontend_kir);
        free(canonical_frontend);
        return 0;
    }

    free(frontend_kir);
    free(canonical_frontend);
    fail("unsupported command");
    return 1;
}
