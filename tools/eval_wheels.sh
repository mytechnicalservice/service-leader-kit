#!/bin/sh
# Developer tool (not shipped to users): downloads the wheels the kit scripts need into plugin/evals/_gemeinsam/wheels/,
# so that `uv run` works inside the eval sandbox, which has no network and an empty uv cache. The eval scaffold
# (`baue()` in plugin/evals/_gemeinsam/arbeitsordner.sh) points uv at this folder via a uv.toml in the run workspace.
#
# The folder is platform-specific (lxml and pillow ship compiled wheels): build it on the machine that runs the evals,
# before the run. It is gitignored. Network access is needed only here.
#
# Usage: sh tools/eval_wheels.sh [python versions …]   (default: 3.11 3.12 3.13 3.14)
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ZIEL="$ROOT/plugin/evals/_gemeinsam/wheels"
PAKETE="openpyxl==3.1.5 python-docx==1.1.2 python-pptx==1.0.2"
VERSIONEN=${*:-3.11 3.12 3.13 3.14}

if python3 -m pip --version >/dev/null 2>&1; then
  pip_download() { python3 -m pip download "$@"; }
else
  pip_download() { uvx --from pip pip download "$@"; }
fi

mkdir -p "$ZIEL"
for v in $VERSIONEN; do
  echo "Wheels für Python $v …"
  # shellcheck disable=SC2086
  pip_download --quiet --disable-pip-version-check --only-binary=:all: --python-version "$v" -d "$ZIEL" $PAKETE
done
echo "Fertig: $(ls "$ZIEL" | wc -l | tr -d ' ') Wheels in $ZIEL"
