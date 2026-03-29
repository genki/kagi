#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/kagi_launcher.c"
OUT="${1:-$SCRIPT_DIR/kagi}"

cc -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -std=c11 "$SRC" -o "$OUT"
echo "built $OUT"
