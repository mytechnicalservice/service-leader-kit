"""Install/update transactions for eigene_kopie's Codex target; preflight before writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

import arbeitsordner as ao
import codex_config as cc
import codex_render as cr
from slk_common import write_atomic

MANIFEST = cr.KIT + "/MANIFEST.json"


def digest(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def sicher(projekt: Path, rel: str) -> Path:
    parts = PurePosixPath(rel).parts
    if not parts or ".." in parts or PurePosixPath(rel).is_absolute():
        raise ValueError(f"Ungültiger Kit-Pfad: {rel}")
    p = projekt
    for part in parts:
        p = p / part
        if p.is_symlink():
            raise ValueError(f"{rel}: Ziel ist ein Link; nichts geändert.")
        if p.exists() and p != projekt / rel and not p.is_dir():
            raise ValueError(f"{rel}: Zielordner ist eine Datei; nichts geändert.")
    if p.exists() and not p.is_file():
        raise ValueError(f"{rel}: Ziel ist keine Datei; nichts geändert.")
    return p


def manifest(projekt: Path) -> dict:
    p = sicher(projekt, MANIFEST)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["schema"] == 1 and isinstance(data["dateien"], dict)
        for rel, sha in data["dateien"].items():
            assert rel.startswith((".agents/skills/", ".codex/agents/", cr.KIT + "/"))
            assert isinstance(sha, str) and len(sha) == 64
            sicher(projekt, rel)
        assert isinstance(data["agents_block"], str) and isinstance(data["hooks"], dict)
    except (ValueError, KeyError, AssertionError, TypeError) as exc:
        raise ValueError("Kit-Dateiliste ist ungültig; keine Dateien geändert.") from exc
    return data


def agents_zusammen(text: str, block: str, bisher: dict, ersetzen: bool) -> tuple[str, list[str]]:
    count = text.count(cr.ANFANG), text.count(cr.ENDE)
    if count == (0, 0):
        # A removed owned block is a local edit, even if the user kept the surrounding file.
        konflikts = ["AGENTS.md (Kit-Block entfernt)"] if bisher and not ersetzen else []
        return text.rstrip() + ("\n\n" if text.strip() else "") + block, konflikts
    if count != (1, 1) or text.index(cr.ENDE) < text.index(cr.ANFANG):
        raise ValueError("AGENTS.md: Kit-Markierungen sind nicht eindeutig; bitte zuerst prüfen.")
    start = text.index(cr.ANFANG)
    end = text.index(cr.ENDE) + len(cr.ENDE)
    old = text[start:end] + "\n"
    conflicts = []
    if not ersetzen and (not bisher or digest(old) != bisher.get("agents_block")):
        conflicts = ["AGENTS.md (Kit-Block geändert)"]
    return text[:start] + block.rstrip("\n") + text[end:], conflicts


def vorbereiten(plugin: Path, projekt: Path, aktualisieren: bool = False, ueberschreiben: bool = False) -> dict:
    files = cr.dateien(plugin)
    for rel in [*files, MANIFEST, "AGENTS.md", ".codex/config.toml", ".codex/hooks.json"]:
        sicher(projekt, rel)
    old = manifest(projekt)
    if aktualisieren and not old:
        raise ValueError("Keine Kit-Dateiliste vorhanden. Erstinstallation oder ZIP-Übernahme zuerst prüfen; "
                         "--aktualisieren ersetzt ohne Dateiliste nichts.")
    conflicts = []
    for rel in files:
        p = projekt / rel
        if p.exists() and not ueberschreiben:
            if not aktualisieren or digest(p.read_bytes()) != old.get("dateien", {}).get(rel):
                conflicts.append(rel)
    skills = sorted(p.parent.name for p in (plugin / "skills").glob("*/SKILL.md"))
    block = cr.agents_block(plugin, skills)
    agents = projekt / "AGENTS.md"
    agents_text, agent_conflicts = agents_zusammen(agents.read_text(encoding="utf-8") if agents.exists() else "",
                                                 block, old, ueberschreiben)
    conflicts += agent_conflicts
    if old and not aktualisieren and not ueberschreiben:
        conflicts.append(MANIFEST)
    cfg = projekt / ".codex/config.toml"
    config = cc.config_zusammen(cfg.read_text(encoding="utf-8-sig") if cfg.exists() else "")
    hp = projekt / ".codex/hooks.json"
    hooks = cr.hooks()
    previous = old.get("hooks", {})
    existing = cc.lies_hooks(hp.read_text(encoding="utf-8-sig") if hp.exists() else "{}")
    # A locally modified owned hook needs the same explicit replacement choice as a file.
    for event, groups in previous.items():
        for group in groups:
            if group not in existing.get("hooks", {}).get(event, []) and not ueberschreiben:
                conflicts.append(f".codex/hooks.json ({event} geändert)")
    merged = cc.hooks_zusammen(existing, hooks, previous)
    new_manifest = {"schema": 1, "version": ao.kit_version(plugin), "variante": "codex",
                    "dateien": {**old.get("dateien", {}), **{r: digest(b) for r, (b, _) in files.items()}},
                    "agents_block": digest(block), "hooks": hooks}
    obsolete = sorted(set(old.get("dateien", {})) - set(files))
    output = {**files, "AGENTS.md": (agents_text.encode(), 0o644), ".codex/config.toml": (config.encode(), 0o644),
              ".codex/hooks.json": ((json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode(), 0o644),
              MANIFEST: ((json.dumps(new_manifest, ensure_ascii=False, indent=2) + "\n").encode(), 0o644)}
    return {"inhalt": output, "konflikte": sorted(set(conflicts)), "veraltet": obsolete,
            "version": ao.kit_version(plugin), "variante": "codex", "dateien": len(output),
            "meldungen": ["Keine Dateien gelöscht. Alte Kit-Dateien bleiben erhalten: " + ", ".join(obsolete)] if obsolete else []}


def pruefen(plugin: Path, projekt: Path, aktualisieren: bool = False) -> dict:
    result = vorbereiten(plugin, projekt, aktualisieren)
    return {k: v for k, v in result.items() if k != "inhalt"}


def baue(plugin: Path, projekt: Path, aktualisieren: bool = False, ueberschreiben: bool = False) -> dict:
    result = vorbereiten(plugin, projekt, aktualisieren, ueberschreiben)
    if result["konflikte"]:
        raise FileExistsError(result["konflikte"])
    for rel, (data, mode) in result.pop("inhalt").items():
        p = sicher(projekt, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(p, data.decode("utf-8")) if p.suffix in (".json", ".toml", ".md") or rel == MANIFEST else p.write_bytes(data)
        p.chmod(mode)
    return result
