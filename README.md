# Service Leader Kit (work in progress)

Claude Code plugin (for VS Code) for heads of industrial service. Spec: myTS repo,
`consulting/kvd/service-leader-kit/spec.md`. License: PolyForm Internal Use 1.0.0 (see `LICENSE`).

- `plugin/` — the plugin (`plugin/scripts/` = uv-run Python scripts)
- `plugin/hooks/` — POSIX-shell hooks (SessionStart, PreToolUse, Stop); inactive outside a kit workspace
- `tools/` — developer tools, not shipped to users: sample-data generator; `testworkspace.py` builds a test workspace (`uv run tools/testworkspace.py "<leerer Ordner>"`)
- `tests/` — `uv run --with pytest --with openpyxl==3.1.5 pytest tests -q`
- `spikes/` — throwaway probes (Plan 1, prerequisite check). Removed before the public release.
