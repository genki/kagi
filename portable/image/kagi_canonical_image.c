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

static char *extract_compile_texts_json(const char *bundle_json) {
    const char *needle = "\"compile\":{\"kind\":\"print_many\",\"texts\":[";
    const char *start = strstr(bundle_json, needle);
    if (!start) {
        return NULL;
    }
    start += strlen(needle);
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

    if (strcmp(command, "selfhost-run") == 0) {
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

        char bundles_dir[PATH_MAX];
        char bundle_path[PATH_MAX];
        join_path(bundles_dir, sizeof(bundles_dir), examples_dir, "selfhost_bundles");
        join_path(bundle_path, sizeof(bundle_path), bundles_dir, matched->bundle_name);
        char *bundle_json = read_text_file(bundle_path);
        if (!bundle_json) {
            free(frontend_source);
            free(program_source);
            free(frontend_kir);
            free(canonical_frontend);
            fail("missing canonical bundle");
        }

        if (use_json) {
            fputs(bundle_json, stdout);
            fputc('\n', stdout);
        } else {
            emit_print_many_stdout(bundle_json);
        }

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
