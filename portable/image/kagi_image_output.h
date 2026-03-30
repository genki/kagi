#ifndef KAGI_IMAGE_OUTPUT_H
#define KAGI_IMAGE_OUTPUT_H

void fail(const char *message);
void emit_json_string(const char *text);

void emit_selfhost_bootstrap_json(const char *kir_json);
void emit_selfhost_build_json(const char *kir_json);
void emit_selfhost_freeze_json(const char *kir_json);

void unsupported_source(void);
int is_selfhost_fixed_point_command(const char *command);

int emit_native_selfhost_command(
    const char *command,
    int use_json,
    const char *source_path,
    const char *raw_ast,
    const char *raw_hir,
    const char *raw_kir,
    const char *raw_analysis,
    const char *raw_artifact
);

#endif
