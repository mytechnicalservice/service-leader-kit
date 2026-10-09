"""Rendering for the Codex target of eigene_kopie; no filesystem writes."""
from __future__ import annotations

import json
import re
from pathlib import Path

from kit_uebersicht import KOPF, kopf

KIT = ".codex/kit"
ANFANG = "<!-- slk:anfang -->"
ENDE = "<!-- slk:ende -->"
ROOT_SETUP = ('SLK_ROOT="$PWD"; while [ ! -f "$SLK_ROOT/.codex/kit/VARIANTE" ]; do '
              '[ "$SLK_ROOT" != / ] || { echo "Kit-Ordner nicht gefunden" >&2; exit 1; }; '
              'SLK_ROOT=$(dirname "$SLK_ROOT"); done; SLK_KIT="$SLK_ROOT/.codex/kit"')


def umschreiben(text: str, skills: list[str]) -> str:
    text = text.replace("$" + "{CLAUDE_PLUGIN_ROOT}", "$SLK_KIT")
    text = text.replace("service-leader-kit:", "").replace(".claude/skills/", ".agents/skills/")
    for name in sorted(skills, key=len, reverse=True):
        text = re.sub(r"(?<![\w./-])/" + re.escape(name) + r"(?![\w/-])", "$" + name, text)
    return text


def arbeitsweise() -> str:
    return ('\n## Kit-Pfad in Codex\n\nVor Skriptaufrufen ermittle den Kit-Ordner mit diesem Block. '
            'Führe ihn und den jeweiligen Aufruf in derselben Shell aus; das funktioniert auch in Unterordnern '
            'ohne Git. Verwende keine fest eingetragenen Rechnerpfade.\n\n```sh\n' + ROOT_SETUP + '\n```\n\n'
            'Die Werkzeuglisten des Claude-Plugins sind hier nicht technisch eingeschränkt. '
            'Halte trotzdem alle Fach- und Sicherheitsregeln ein. '
            'Für Fachagenten nutze `spawn_agent` mit `agent_type` und `fork_turns="none"`; '
            'gib einen vollständigen Auftrag mit. Direkte Änderungen in Unternehmen/ erfolgen mit `apply_patch` '
            'durch `system-architekt`, nie mit Inline-Code oder Shell-Umleitungen.\n')


def skill(text: str, skills: list[str]) -> tuple[str, bool]:
    m = KOPF.match(text)
    if not m:
        raise ValueError("Skill ohne Kopfzeile; Quelle zuerst prüfen.")
    meta = kopf(text)
    if not meta.get("name") or not meta.get("description"):
        raise ValueError("Skill ohne Name/Beschreibung; Quelle zuerst prüfen.")
    meta = {k: host_text(v, skills) for k, v in meta.items()}
    if meta["name"] == "kit-auswerfen":
        meta["description"] = "Explains the user's existing Codex copy and its explicit generator/ZIP update workflow; use only when asked about copying or updating the kit."
    head = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()) + "\n---\n"
    body = host_text(text[m.end():], skills)
    if meta["name"] == "kit-auswerfen":
        body = ('\n# Deine Codex-Kopie\n\nDas Kit ist hier schon deine eigene Codex-Kopie. '
                'Lege keine zweite Kopie an. Für eine neue Version braucht der Nutzer den Generator der neuen '
                'Quelle oder eine neue ZIP. Zeige ihm den Abschnitt „Aktualisieren“ in `.codex/kit/README.de.md`. '
                'Keine Dateien ungefragt ersetzen; eigene Änderungen vor dem Update prüfen und bestätigen.\n')
    implicit = not bool(re.search(r"^disable-model-invocation:\s*true\s*$", m.group(1), re.M))
    return head + arbeitsweise() + body, implicit


def host_text(text: str, skills: list[str]) -> str:
    text = umschreiben(text, skills)
    text = text.replace("Claude Code", "Codex").replace("Claude's built-in", "the available")
    text = text.replace("Claude's", "the available").replace("Claude panel (or `/clear`)", "Codex session")
    text = text.replace("Agent tool", "spawn_agent tool").replace("subagent_type", "agent_type")
    text = text.replace("Agent-Werkzeug, Typ", "spawn_agent, agent_type")
    return text.replace(".claude/agents/", ".codex/agents/").replace(".claude/kit/", KIT + "/")


def agent(text: str, skills: list[str]) -> str:
    meta = kopf(text)
    m = KOPF.match(text)
    if not m or not meta.get("name") or not meta.get("description"):
        raise ValueError("Agent ohne Name/Beschreibung; Quelle zuerst prüfen.")
    body = arbeitsweise() + host_text(text[m.end():], skills)
    fields = {"name": meta["name"], "description": meta["description"], "developer_instructions": body}
    return "\n".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in fields.items()) + "\n"


def agents_block(plugin: Path, skills: list[str]) -> str:
    text = (plugin / "agents/assistenz.md").read_text(encoding="utf-8")
    persona = text.split("<!-- persona:anfang -->", 1)[1].split("<!-- persona:ende -->", 1)[0].strip()
    extra = ('\n\nDas Kit liegt in `.codex/kit/`, Fachagenten in `.codex/agents/`, Skills in `.agents/skills/`. '
             'Skills rufst du mit `$name` auf. Nur `system-architekt` darf Unternehmensinhalte bearbeiten. '
             'Unteragenten dürfen keine menschliche Entscheidung über `vorgang.py entscheide` setzen. '
             'Keine Dateien löschen, nichts versenden; Mails bleiben Entwürfe. '
             'Die Hooks sind überprüfbare Schutzregeln, keine vollständige Sicherheitsgrenze. '
             'Vor der ersten Nutzung und nach Änderungen prüft der Nutzer sie in `/hooks`.\n')
    return ANFANG + "\n# Service Leader Kit in Codex\n\n" + host_text(persona, skills) + extra + arbeitsweise() + ENDE + "\n"


def hooks() -> dict:
    result = {}
    for event, name in (("SessionStart", "session-start"), ("PreToolUse", "pre-tool-use"), ("Stop", "stop")):
        command = "sh -c '" + ROOT_SETUP + '; exec sh "$SLK_KIT/hooks/' + name + '.sh"' + "'"
        group = {"hooks": [{"type": "command", "command": command, "commandWindows": command, "timeout": 60}]}
        if event == "PreToolUse":
            group["matcher"] = "Bash|PowerShell|exec_command|shell|apply_patch|Write|Edit|MultiEdit|NotebookEdit|mcp__.*"
        result[event] = [group]
    return result


def dateien(plugin: Path) -> dict[str, tuple[bytes, int]]:
    # Use the shared generator's filters and source inventory, never a second inventory.
    import eigene_kopie as ek
    result: dict[str, tuple[bytes, int]] = {}
    skills = sorted(p.parent.name for p in (plugin / "skills").glob("*/SKILL.md"))
    for rel, (src, rewrite) in ek.plan(plugin).items():
        target = rel.replace(".claude/skills/", ".agents/skills/").replace(".claude/kit/", KIT + "/")
        mode = src.stat().st_mode & 0o777
        if rel.startswith(".claude/agents/"):
            target = f".codex/agents/{src.stem}.toml"
            data = agent(src.read_text(encoding="utf-8"), skills).encode()
        elif rel.startswith(".claude/skills/") and src.name == "SKILL.md":
            rendered, implicit = skill(src.read_text(encoding="utf-8"), skills)
            data = rendered.encode()
            if not implicit:
                result[str(Path(target).parent / "agents/openai.yaml")] = (b"policy:\n  allow_implicit_invocation: false\n", 0o644)
        elif rewrite or src.name == "KATALOG.md":
            data = umschreiben(src.read_text(encoding="utf-8"), skills).encode()
        else:
            data = src.read_bytes()
        result[target] = data, mode
    result[KIT + "/VERSION"] = (ek.ao.kit_version(plugin) + "\n").encode(), 0o644
    result[KIT + "/VARIANTE"] = b"codex\n", 0o644
    return result
