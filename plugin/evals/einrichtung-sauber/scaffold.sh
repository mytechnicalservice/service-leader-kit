#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
# The setup starts in an empty folder: only the offline uv settings, no workspace (einrichtung.py builds it).
uv_offline
