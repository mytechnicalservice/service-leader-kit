#!/bin/sh
. "$(dirname "$0")/../_gemeinsam/arbeitsordner.sh"
baue unordentlich
mkdir -p .claude/agents
printf -- '---\nname: finanzen\ndescription: "Eigene Finanzen-Fassung des Nutzers."\n---\n\nMeine Fassung: Finanzen rechnet immer mit Deckungsbeitrag II.\n' \
  > .claude/agents/finanzen.md
printf '{\n  "permissions": { "allow": ["Bash(git status)"] }\n}\n' > .claude/settings.json
