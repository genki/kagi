#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

extern char **environ;

typedef struct {
    char entry_module[PATH_MAX];
    char python_path_rel[PATH_MAX];
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
    snprintf(manifest_path, sizeof(manifest_path), "%s/app/kagi_runtime.env", dist_root);

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

        if (strcmp(key, "ENTRY_MODULE") == 0) {
            snprintf(manifest.entry_module, sizeof(manifest.entry_module), "%s", value);
        } else if (strcmp(key, "PYTHONPATH_REL") == 0) {
            snprintf(manifest.python_path_rel, sizeof(manifest.python_path_rel), "%s", value);
        } else if (strcmp(key, "WORKSPACE_REL") == 0) {
            snprintf(manifest.workspace_rel, sizeof(manifest.workspace_rel), "%s", value);
        }
    }

    fclose(fp);

    require_manifest_value("ENTRY_MODULE", manifest.entry_module);
    require_manifest_value("PYTHONPATH_REL", manifest.python_path_rel);
    require_manifest_value("WORKSPACE_REL", manifest.workspace_rel);
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

    char python_bin[PATH_MAX];
    char python_home[PATH_MAX];
    char python_path[PATH_MAX];
    char kagi_home[PATH_MAX];

    snprintf(python_bin, sizeof(python_bin), "%s/bin/python3", dist_root);
    snprintf(python_home, sizeof(python_home), "%s", dist_root);
    join_path_or_die(python_path, sizeof(python_path), dist_root, manifest.python_path_rel);
    join_path_or_die(kagi_home, sizeof(kagi_home), dist_root, manifest.workspace_rel);

    set_env_or_die("PYTHONHOME", python_home);
    set_env_or_die("PYTHONPATH", python_path);
    set_env_or_die("PYTHONNOUSERSITE", "1");
    set_env_or_die("PYTHONDONTWRITEBYTECODE", "1");
    set_env_or_die("KAGI_HOME", kagi_home);

    char **child_argv = calloc((size_t)argc + 5, sizeof(char *));
    if (!child_argv) {
        perror("calloc");
        return 1;
    }
    int i = 0;
    child_argv[i++] = python_bin;
    child_argv[i++] = "-S";
    child_argv[i++] = "-m";
    child_argv[i++] = manifest.entry_module;
    for (int j = 1; j < argc; ++j) {
        child_argv[i++] = argv[j];
    }
    child_argv[i] = NULL;

    execve(python_bin, child_argv, environ);
    fprintf(stderr, "failed to exec bundled python: %s\n", strerror(errno));
    return 1;
}
