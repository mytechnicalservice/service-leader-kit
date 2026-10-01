# Raw hook payloads (captured 2026-10-01, Claude Code 2.1.286 (Claude Code), macOS)

Captured by `spikes/payload-capture` (Plan 2b Task 1); workspace path -> `__WS__`, home -> `/Users/test`,
session id -> `test`.
The transcript filename (session UUID) is zeroed; `prompt_id`, `agent_id` and `tool_use_id` are replaced by
stable placeholders (`test-prompt`, `test-agent`, `toolu_test_<name>`). In `transcript_path` the encoded workspace folder name is replaced by `-__WS__`.

- PreToolUse carries `cwd`: yes (also on SessionStart and Stop). It was the workspace folder in every capture;
  this run never changed directory, so whether `cwd` follows a `cd` from an earlier call is not observed.
- Sub-agent Write `agent_type`: `payload-capture:schreiber` (also adds `agent_id`; the main agent's payloads
  have neither key).
- Skill identity after a `Skill` call: none found. The Write after the Skill call (`PreToolUse-Write-2.json`) has
  the same keys as the first Write. The skill name appears only in the Skill call's own payload:
  `tool_input.skill` = `payload-capture:notiz`.
- Other top-level keys on PreToolUse: `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`,
  `effort`, `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id`.
- SessionStart keys: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `source`.
- Stop keys: PreToolUse common keys plus `stop_hook_active`, `last_assistant_message`, `background_tasks`,
  `session_crons` (no tool_name/tool_input/tool_use_id).
- `tool_input` keys: Write `file_path`, `content`; Edit `file_path`, `old_string`, `new_string`, `replace_all`;
  Bash `command`, `description`; Skill `skill`; Agent `description`, `prompt`, `subagent_type`,
  `run_in_background`.
- Non-ASCII is written literally (`Müller`), quotes JSON-escaped; payloads are one line, no trailing newline.
