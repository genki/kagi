#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "kagi_image_output.h"
#include "kagi_image_parser.h"
#include "kagi_image_serializer.h"
#include "kagi_image_eval.h"
#include "kagi_image_dispatch.h"

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

static int is_json_flag(const char *arg) {
    return strcmp(arg, "--json") == 0;
}

static int frontend_matches_canonical(
    const char *frontend_source,
    const char *canonical_frontend,
    const char *frontend_kir
) {
    return frontend_source &&
           (normalized_source_equals(frontend_source, canonical_frontend) ||
            strcmp(frontend_source, frontend_kir) == 0);
}

static int frontend_matches_canonical_or_kir(
    const char *frontend_source,
    const char *frontend_kir,
    const char *frontend_src_path,
    char **canonical_frontend
) {
    if (!frontend_source) {
        return 0;
    }
    if (strcmp(frontend_source, frontend_kir) == 0) {
        return 1;
    }
    if (!*canonical_frontend) {
        *canonical_frontend = read_text_file(frontend_src_path);
    }
    return frontend_matches_canonical(frontend_source, *canonical_frontend, frontend_kir);
}

static int handle_fixed_point_command(
    const char *command,
    int argc,
    char **argv,
    const char *frontend_kir,
    const char *frontend_src_path,
    char **canonical_frontend
) {
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
        fail("missing frontend path");
    }
    char *frontend_source = read_text_file(frontend_arg);
    if (!frontend_matches_canonical_or_kir(frontend_source, frontend_kir, frontend_src_path, canonical_frontend)) {
        free(frontend_source);
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
    return 0;
}

static int handle_selfhost_program_command(
    const char *command,
    int argc,
    char **argv,
    const char *frontend_kir,
    const char *frontend_src_path,
    char **canonical_frontend
) {
    int arg_index = 3;
    int use_json = 0;
    if (arg_index < argc && is_json_flag(argv[arg_index])) {
        use_json = 1;
        arg_index++;
    }
    if (argc - arg_index < 2) {
        fail("missing selfhost-run args");
    }
    char *frontend_source = read_text_file(argv[arg_index]);
    char *program_source = read_text_file(argv[arg_index + 1]);
    if (
        !program_source ||
        !frontend_matches_canonical_or_kir(frontend_source, frontend_kir, frontend_src_path, canonical_frontend)
    ) {
        free(frontend_source);
        free(program_source);
        unsupported_source();
        return 1;
    }

    native_function_program_t native_function_program = {0};
    native_stmt_program_t native_stmt_program = {0};
    int has_native_function_program = try_parse_native_function_program(program_source, &native_function_program);
    int has_native_stmt_program = 0;
    if (!has_native_function_program) {
        has_native_stmt_program = try_parse_native_stmt_program(program_source, &native_stmt_program);
    }
    if (has_native_function_program) {
        char *raw_ast = native_function_program_to_parse_json(&native_function_program);
        char *raw_hir = native_function_program_to_hir_json(&native_function_program);
        char *raw_kir = native_function_program_to_kir_json(&native_function_program);
        char *raw_analysis = native_function_program_to_analysis_json(&native_function_program);
        char *raw_artifact = native_function_program_to_artifact_json(&native_function_program);
        if (!raw_ast || !raw_hir || !raw_kir || !raw_analysis || !raw_artifact) {
            free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
            free_native_function_program(&native_function_program);
            free(frontend_source); free(program_source);
            unsupported_source();
            return 1;
        }
        if (!emit_native_selfhost_command(
            command, use_json, argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_analysis, raw_artifact
        )) {
            unsupported_source();
        }
        free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
        free_native_function_program(&native_function_program);
        free(frontend_source); free(program_source);
        return 0;
    }
    if (has_native_stmt_program) {
        char *raw_ast = native_stmt_program_to_parse_json(&native_stmt_program);
        char *raw_hir = native_stmt_program_to_hir_json(&native_stmt_program);
        char *raw_kir = native_stmt_program_to_kir_json(&native_stmt_program);
        char *raw_analysis = native_stmt_program_to_analysis_json();
        char *raw_artifact = native_stmt_program_to_artifact_json(&native_stmt_program);
        if (!raw_ast || !raw_hir || !raw_kir || !raw_analysis || !raw_artifact) {
            free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
            free_native_stmt_program(&native_stmt_program);
            free(frontend_source); free(program_source);
            unsupported_source();
            return 1;
        }
        if (!emit_native_selfhost_command(
            command, use_json, argv[arg_index + 1], raw_ast, raw_hir, raw_kir, raw_analysis, raw_artifact
        )) {
            unsupported_source();
        }
        free(raw_ast); free(raw_hir); free(raw_kir); free(raw_analysis); free(raw_artifact);
        free_native_stmt_program(&native_stmt_program);
        free(frontend_source); free(program_source);
        return 0;
    }
    free_native_function_program(&native_function_program);
    free_native_stmt_program(&native_stmt_program);
    free(frontend_source);
    free(program_source);
    unsupported_source();
    return 1;
}

int run_kagi_canonical_image(int argc, char **argv) {
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
    char *canonical_frontend = NULL;
    if (!frontend_kir) {
        fail("missing canonical frontend KIR");
    }

    int exit_code = 1;
    if (is_selfhost_fixed_point_command(command)) {
        exit_code = handle_fixed_point_command(command, argc, argv, frontend_kir, frontend_src_path, &canonical_frontend);
    } else if (
        strcmp(command, "selfhost-run") == 0 ||
        strcmp(command, "selfhost-check") == 0 ||
        strcmp(command, "selfhost-emit") == 0 ||
        strcmp(command, "selfhost-capir") == 0 ||
        strcmp(command, "selfhost-parse") == 0
    ) {
        exit_code = handle_selfhost_program_command(command, argc, argv, frontend_kir, frontend_src_path, &canonical_frontend);
    } else {
        free(frontend_kir);
        free(canonical_frontend);
        fail("unsupported command");
        return 1;
    }

    free(frontend_kir);
    free(canonical_frontend);
    return exit_code;
}
