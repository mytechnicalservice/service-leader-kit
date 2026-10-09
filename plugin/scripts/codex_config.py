"""Conservative Codex settings merge: preserve text, reject conflicting keys."""
from __future__ import annotations

import json
import tomllib

PROFILE = {"extends": ":workspace", "filesystem": {":workspace_roots": {".agents/skills": "write"}}}
PROFILE_TEXT = ('\n# Service Leader Kit: eigene Skills im Projekt dürfen angelegt werden.\n'
                '[permissions.slk]\nextends = ":workspace"\n'
                '[permissions.slk.filesystem.":workspace_roots"]\n".agents/skills" = "write"\n')


def config_zusammen(text: str) -> str:
    try:
        alt = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(".codex/config.toml ist ungültig; bitte zuerst prüfen.") from exc
    if "sandbox_mode" in alt or "hooks" in alt:
        raise ValueError(".codex/config.toml: sandbox_mode oder eingebettete hooks widersprechen der Kit-Einrichtung; "
                         "bitte selbst prüfen und den Konflikt vor dem erneuten Aufruf lösen.")
    if alt.get("default_permissions", "slk") != "slk":
        raise ValueError(".codex/config.toml: default_permissions ist bereits anders gewählt; nichts geändert. "
                         "Bitte das Profil prüfen und ausdrücklich selbst entscheiden.")
    permissions = alt.get("permissions", {})
    if not isinstance(permissions, dict):
        raise ValueError(".codex/config.toml: permissions muss eine Tabelle sein.")
    if "slk" in permissions and permissions["slk"] != PROFILE:
        raise ValueError(".codex/config.toml: permissions.slk ist bereits anders belegt; nichts geändert.")
    if "default_permissions" not in alt:
        text = 'default_permissions = "slk"\n' + text
    if "slk" not in permissions:
        text = text.rstrip() + "\n" + PROFILE_TEXT
    tomllib.loads(text)  # merge must still parse, including unusual user tables
    return text


def lies_hooks(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(".codex/hooks.json ist ungültig; bitte zuerst prüfen.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        raise ValueError(".codex/hooks.json: hooks muss ein Objekt sein.")
    for groups in data.get("hooks", {}).values():
        if not isinstance(groups, list) or any(not isinstance(g, dict) or not isinstance(g.get("hooks"), list)
                                              or any(not isinstance(h, dict) for h in g["hooks"]) for g in groups):
            raise ValueError(".codex/hooks.json: ungültige Hook-Gruppe; nichts geändert.")
    return data


def hooks_zusammen(alt: dict, neu: dict, bisher: dict) -> dict:
    # Remove only exact kit-owned groups recorded in the previous manifest.
    from eigene_kopie import settings_zusammen
    clean = {**alt, "hooks": {event: [g for g in groups if g not in bisher.get(event, [])]
                              for event, groups in alt.get("hooks", {}).items()}}
    commands = {h["command"] for groups in neu.values() for g in groups for h in g["hooks"]}
    for event, groups in clean["hooks"].items():
        for group in groups:
            overlap = any(h.get("command") in commands for h in group["hooks"])
            if overlap and group not in neu.get(event, []):
                raise ValueError(".codex/hooks.json: Kit-Befehl ist mit abweichender Zuordnung vorhanden; "
                                 "bitte die Hook-Gruppe zuerst selbst prüfen. Nichts geändert.")
    return settings_zusammen(clean, neu)
