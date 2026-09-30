#!/bin/sh
# Builds slk-cowork-probe.zip with the plugin root at the zip root (no nested folder).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/../slk-cowork-probe.zip"
rm -f "$OUT"
cd "$HERE"
zip -qr "$OUT" .claude-plugin hooks agents skills -x '*.DS_Store'
unzip -l "$OUT" | grep -q ' .claude-plugin/plugin.json$' || { echo "zip layout wrong" >&2; exit 1; }
echo "$OUT"
