# Service Leader Kit (work in progress)

Claude Code plugin (for VS Code) for heads of industrial service. Spec: myTS repo,
`consulting/kvd/service-leader-kit/spec.md`. License: PolyForm Internal Use 1.0.0 (see `LICENSE`).

- `plugin/` — the plugin (`plugin/scripts/` = uv-run Python scripts)
- `plugin/hooks/` — POSIX-shell hooks (SessionStart, PreToolUse, Stop); inactive outside a kit workspace
- `tools/` — developer tools, not shipped to users: sample-data generator; `testworkspace.py` builds a test workspace (`uv run tools/testworkspace.py "<leerer Ordner>"`)
- `tests/` — `uv run --with pytest --with openpyxl==3.1.5 --with python-docx==1.1.2 --with python-pptx==1.0.2 --with pyyaml==6.0.2 pytest tests -q`
- `plugin/evals/` — evals (billed): `DOCKER_CONFIG="$(mktemp -d)" claude plugin eval ./plugin --scaffold --trust-plugin --allow-tools Bash Write Edit Agent Skill --no-publish` — the empty `DOCKER_CONFIG` is needed where the Docker credential store holds symlinks (Docker Desktop on macOS), and without `--allow-tools Bash Write Edit` no grader can pass. On Max's Mac it is not enough: symlinks in `~/.docker/cli-plugins/` still make the eval refuse Bash (open, Plan 6)
- `CHANGELOG.md` — changes per version (German, for users)
- `spikes/` — throwaway probes (Plan 1, prerequisite check). Removed before the public release.
