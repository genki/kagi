#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRCS=(
  "$SCRIPT_DIR/kagi_canonical_image.c"
  "$SCRIPT_DIR/kagi_image_output.c"
  "$SCRIPT_DIR/kagi_image_parser.c"
  "$SCRIPT_DIR/kagi_image_serializer.c"
  "$SCRIPT_DIR/kagi_image_eval.c"
)
OUT="${1:-$SCRIPT_DIR/kagi-canonical-image}"

cc -D_GNU_SOURCE -D_POSIX_C_SOURCE=200809L -O2 -Wall -Wextra -std=c11 -I"$SCRIPT_DIR" "${SRCS[@]}" -o "$OUT"
echo "built $OUT"
