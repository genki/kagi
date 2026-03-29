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

int main(int argc, char **argv) {
    char exe[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n < 0) {
        perror("readlink");
        return 1;
    }
    exe[n] = '\0';

    char root_buf[PATH_MAX];
    strncpy(root_buf, exe, sizeof(root_buf));
    root_buf[sizeof(root_buf) - 1] = '\0';
    char *bin_dir = dirname(root_buf);

    char dist_buf[PATH_MAX];
    strncpy(dist_buf, bin_dir, sizeof(dist_buf));
    dist_buf[sizeof(dist_buf) - 1] = '\0';
    char *dist_root = dirname(dist_buf);

    char python_bin[PATH_MAX];
    char python_home[PATH_MAX];
    char python_path[PATH_MAX];
    char kagi_home[PATH_MAX];

    snprintf(python_bin, sizeof(python_bin), "%s/bin/python3", dist_root);
    snprintf(python_home, sizeof(python_home), "%s", dist_root);
    snprintf(python_path, sizeof(python_path), "%s/app/kagi_app.zip", dist_root);
    snprintf(kagi_home, sizeof(kagi_home), "%s/workspace", dist_root);

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
    child_argv[i++] = "kagi.host_entry";
    for (int j = 1; j < argc; ++j) {
        child_argv[i++] = argv[j];
    }
    child_argv[i] = NULL;

    execve(python_bin, child_argv, environ);
    fprintf(stderr, "failed to exec bundled python: %s\n", strerror(errno));
    return 1;
}
