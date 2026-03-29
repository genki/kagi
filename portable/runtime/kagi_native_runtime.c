#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

extern char **environ;

static void set_env_or_die(const char *key, const char *value) {
    if (setenv(key, value, 1) != 0) {
        perror(key);
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

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <entry-target> [args...]\n", argv[0]);
        return 2;
    }

    const char *image_path = getenv("KAGI_IMAGE");
    const char *kagi_home = getenv("KAGI_HOME");
    if (!image_path || image_path[0] == '\0') {
        fprintf(stderr, "missing KAGI_IMAGE\n");
        return 1;
    }
    if (!kagi_home || kagi_home[0] == '\0') {
        fprintf(stderr, "missing KAGI_HOME\n");
        return 1;
    }

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

    char python_bin[PATH_MAX];
    join_path_or_die(python_bin, sizeof(python_bin), dist_root, "bin/python3");
    set_env_or_die("PYTHONPATH", image_path);
    set_env_or_die("PYTHONNOUSERSITE", "1");
    set_env_or_die("PYTHONDONTWRITEBYTECODE", "1");
    set_env_or_die("KAGI_HOME", kagi_home);

    char **child_argv = calloc((size_t)argc + 4, sizeof(char *));
    if (!child_argv) {
        perror("calloc");
        return 1;
    }

    int i = 0;
    child_argv[i++] = python_bin;
    child_argv[i++] = "-S";
    child_argv[i++] = "-m";
    child_argv[i++] = argv[1];
    for (int j = 2; j < argc; ++j) {
        child_argv[i++] = argv[j];
    }
    child_argv[i] = NULL;

    execve(python_bin, child_argv, environ);
    fprintf(stderr, "failed to exec native bridge python: %s\n", strerror(errno));
    return 1;
}
