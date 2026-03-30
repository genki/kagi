#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "../common/kagi_portable_abi.h"

extern char **environ;

typedef struct {
    char runtime_kind[64];
    char runtime_bin_rel[PATH_MAX];
    char entry_style[64];
    char entry_target[PATH_MAX];
    char image_rel[PATH_MAX];
    char workspace_rel[PATH_MAX];
} runtime_manifest_t;

static void set_env_or_die(const char *key, const char *value) {
    if (setenv(key, value, 1) != 0) {
        perror(key);
        exit(1);
    }
}

static void trim_line(char *line) {
    size_t len = strlen(line);
    while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r' || line[len - 1] == ' ' || line[len - 1] == '\t')) {
        line[--len] = '\0';
    }
    char *start = line;
    while (*start == ' ' || *start == '\t') {
        start++;
    }
    if (start != line) {
        memmove(line, start, strlen(start) + 1);
    }
}

static void require_manifest_value(const char *name, const char *value) {
    if (value[0] == '\0') {
        fprintf(stderr, "missing manifest key: %s\n", name);
        exit(1);
    }
}

static void join_path_or_die(char *out, size_t out_size, const char *left, const char *right) {
    int written = snprintf(out, out_size, "%s/%s", left, right);
    if (written < 0 || (size_t)written >= out_size) {
        fprintf(stderr, "path too long\n");
        exit(1);
    }
}

static runtime_manifest_t load_runtime_manifest(const char *dist_root) {
    runtime_manifest_t manifest;
    memset(&manifest, 0, sizeof(manifest));

    char manifest_path[PATH_MAX];
    snprintf(manifest_path, sizeof(manifest_path), "%s/%s", dist_root, KAGI_PORTABLE_RUNTIME_MANIFEST_REL);

    FILE *fp = fopen(manifest_path, "r");
    if (!fp) {
        fprintf(stderr, "failed to open runtime manifest: %s\n", manifest_path);
        exit(1);
    }

    char line[PATH_MAX * 2];
    while (fgets(line, sizeof(line), fp) != NULL) {
        trim_line(line);
        if (line[0] == '\0' || line[0] == '#') {
            continue;
        }

        char *eq = strchr(line, '=');
        if (!eq) {
            continue;
        }
        *eq = '\0';
        char *key = line;
        char *value = eq + 1;
        trim_line(key);
        trim_line(value);

        if (strcmp(key, KAGI_MANIFEST_RUNTIME_KIND) == 0) {
            snprintf(manifest.runtime_kind, sizeof(manifest.runtime_kind), "%s", value);
        } else if (strcmp(key, KAGI_MANIFEST_RUNTIME_BIN_REL) == 0) {
            snprintf(manifest.runtime_bin_rel, sizeof(manifest.runtime_bin_rel), "%s", value);
        } else if (strcmp(key, KAGI_MANIFEST_ENTRY_STYLE) == 0) {
            snprintf(manifest.entry_style, sizeof(manifest.entry_style), "%s", value);
        } else if (strcmp(key, KAGI_MANIFEST_ENTRY_TARGET) == 0) {
            snprintf(manifest.entry_target, sizeof(manifest.entry_target), "%s", value);
        } else if (strcmp(key, KAGI_MANIFEST_IMAGE_REL) == 0) {
            snprintf(manifest.image_rel, sizeof(manifest.image_rel), "%s", value);
        } else if (strcmp(key, KAGI_MANIFEST_WORKSPACE_REL) == 0) {
            snprintf(manifest.workspace_rel, sizeof(manifest.workspace_rel), "%s", value);
        }
    }

    fclose(fp);

    require_manifest_value(KAGI_MANIFEST_RUNTIME_KIND, manifest.runtime_kind);
    require_manifest_value(KAGI_MANIFEST_RUNTIME_BIN_REL, manifest.runtime_bin_rel);
    require_manifest_value(KAGI_MANIFEST_ENTRY_STYLE, manifest.entry_style);
    require_manifest_value(KAGI_MANIFEST_ENTRY_TARGET, manifest.entry_target);
    require_manifest_value(KAGI_MANIFEST_IMAGE_REL, manifest.image_rel);
    require_manifest_value(KAGI_MANIFEST_WORKSPACE_REL, manifest.workspace_rel);
    return manifest;
}

int main(int argc, char **argv) {
    char exe[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n < 0) {
        perror("readlink");
        return 1;
    }
    exe[n] = '\0';

    char root_buf[PATH_MAX];
    snprintf(root_buf, sizeof(root_buf), "%s", exe);
    char *bin_dir = dirname(root_buf);

    char dist_buf[PATH_MAX];
    snprintf(dist_buf, sizeof(dist_buf), "%s", bin_dir);
    char *dist_root = dirname(dist_buf);

    runtime_manifest_t manifest = load_runtime_manifest(dist_root);

    char runtime_bin[PATH_MAX];
    char python_home[PATH_MAX];
    char image_path[PATH_MAX];
    char kagi_home[PATH_MAX];

    join_path_or_die(runtime_bin, sizeof(runtime_bin), dist_root, manifest.runtime_bin_rel);
    snprintf(python_home, sizeof(python_home), "%s", dist_root);
    join_path_or_die(image_path, sizeof(image_path), dist_root, manifest.image_rel);
    join_path_or_die(kagi_home, sizeof(kagi_home), dist_root, manifest.workspace_rel);

    set_env_or_die(KAGI_ENV_HOME, kagi_home);

    if (strcmp(manifest.runtime_kind, KAGI_RUNTIME_KIND_PYTHON) == 0) {
        if (strcmp(manifest.entry_style, KAGI_ENTRY_STYLE_PYTHON_MODULE) != 0) {
            fprintf(stderr, "unsupported entry style for python runtime: %s\n", manifest.entry_style);
            return 1;
        }

        set_env_or_die(KAGI_ENV_PYTHONHOME, python_home);
        set_env_or_die(KAGI_ENV_PYTHONPATH, image_path);
        set_env_or_die(KAGI_ENV_PYTHONNOUSERSITE, "1");
        set_env_or_die(KAGI_ENV_PYTHONDONTWRITEBYTECODE, "1");

        char **child_argv = calloc((size_t)argc + 5, sizeof(char *));
        if (!child_argv) {
            perror("calloc");
            return 1;
        }
        int i = 0;
        child_argv[i++] = runtime_bin;
        child_argv[i++] = "-S";
        child_argv[i++] = "-m";
        child_argv[i++] = manifest.entry_target;
        for (int j = 1; j < argc; ++j) {
            child_argv[i++] = argv[j];
        }
        child_argv[i] = NULL;

        execve(runtime_bin, child_argv, environ);
        fprintf(stderr, "failed to exec bundled python: %s\n", strerror(errno));
        return 1;
    }

    if (strcmp(manifest.runtime_kind, KAGI_RUNTIME_KIND_NATIVE) == 0) {
        if (strcmp(manifest.entry_style, KAGI_ENTRY_STYLE_DIRECT) != 0) {
            fprintf(stderr, "unsupported entry style for native runtime: %s\n", manifest.entry_style);
            return 1;
        }

        set_env_or_die(KAGI_ENV_IMAGE, image_path);
        set_env_or_die(KAGI_ENV_ENTRY_TARGET, manifest.entry_target);

        char **child_argv = calloc((size_t)argc + 3, sizeof(char *));
        if (!child_argv) {
            perror("calloc");
            return 1;
        }
        int i = 0;
        child_argv[i++] = runtime_bin;
        child_argv[i++] = manifest.entry_target;
        for (int j = 1; j < argc; ++j) {
            child_argv[i++] = argv[j];
        }
        child_argv[i] = NULL;

        execve(runtime_bin, child_argv, environ);
        fprintf(stderr, "failed to exec native runtime: %s\n", strerror(errno));
        return 1;
    }

    fprintf(stderr, "unsupported runtime kind: %s\n", manifest.runtime_kind);
    return 1;
}
