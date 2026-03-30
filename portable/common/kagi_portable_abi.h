#ifndef KAGI_PORTABLE_ABI_H
#define KAGI_PORTABLE_ABI_H

/*
 * Shared launcher/runtime portable ABI.
 *
 * Native runtime entry dispatch is argv[1]-authoritative.
 * KAGI_ENV_ENTRY_TARGET remains exported as a compatibility/debugging mirror
 * of the manifest entry target, but current native runtime execution does not
 * treat it as the source of truth for dispatch.
 *
 * These relative paths are part of the current portable dist layout contract.
 */

#define KAGI_ENV_HOME "KAGI_HOME"
#define KAGI_ENV_IMAGE "KAGI_IMAGE"
#define KAGI_ENV_ENTRY_TARGET "KAGI_ENTRY_TARGET"

#define KAGI_ENV_PYTHONHOME "PYTHONHOME"
#define KAGI_ENV_PYTHONPATH "PYTHONPATH"
#define KAGI_ENV_PYTHONNOUSERSITE "PYTHONNOUSERSITE"
#define KAGI_ENV_PYTHONDONTWRITEBYTECODE "PYTHONDONTWRITEBYTECODE"

#define KAGI_MANIFEST_RUNTIME_KIND "RUNTIME_KIND"
#define KAGI_MANIFEST_RUNTIME_BIN_REL "RUNTIME_BIN_REL"
#define KAGI_MANIFEST_ENTRY_STYLE "ENTRY_STYLE"
#define KAGI_MANIFEST_ENTRY_TARGET "ENTRY_TARGET"
#define KAGI_MANIFEST_IMAGE_REL "IMAGE_REL"
#define KAGI_MANIFEST_WORKSPACE_REL "WORKSPACE_REL"

#define KAGI_RUNTIME_KIND_PYTHON "python"
#define KAGI_RUNTIME_KIND_NATIVE "native"

#define KAGI_ENTRY_STYLE_PYTHON_MODULE "python-module"
#define KAGI_ENTRY_STYLE_DIRECT "direct"

#define KAGI_PORTABLE_RUNTIME_MANIFEST_REL "app/kagi_runtime.env"
#define KAGI_PORTABLE_PYTHON_BIN_REL "bin/python3"

#endif
