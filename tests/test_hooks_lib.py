import datetime as dt
import json
import subprocess

import pytest

from conftest import ROOT
from hookrun import HOOKS, run_lib

SCHEMA = ROOT / "plugin" / "vorlagen" / "kit-config.schema"
GUELTIG = ("schema=1\nablage=github\ngit_auto=ja\nlaufzeit=claude-code\nbeispieldaten=nein\nmail=postausgang\n"
           "sprache=de\nwochenstart=mo\nmonatsstart=erster-werktag\n")


def lib(shell, script, ws=None, **env):
    r = run_lib(shell, script, ws, **env)
    assert r.stderr == b"", r.stderr.decode()
    return r.returncode, r.stdout.decode("utf-8")


def test_field_takes_first_real_key_and_unescapes(shell, tmp_path):
    payload = json.dumps({"session_id": "t", "tool_input": {
        "command": 'echo "tool_name": "Read" && rm "a b\\c"\nls'}, "tool_name": "Bash"}, indent=2)
    f = tmp_path / "p.json"
    f.write_text(payload, encoding="utf-8")
    assert lib(shell, f'slk_field "$(cat "{f}")" tool_name')[1] == "Bash\n"
    assert lib(shell, f'slk_field "$(cat "{f}")" command')[1] == 'echo "tool_name": "Read" && rm "a b\\c"\nls\n'


def test_field_absent_is_empty_and_literals_print_as_written(shell):
    assert lib(shell, "slk_field '{\"a\":1}' agent_type")[1] == ""
    assert lib(shell, "slk_field '{\"stop_hook_active\": true}' stop_hook_active")[1] == "true\n"


def konfig(shell, tmp_path, text: str | bytes):
    ws = tmp_path / "Kundendienst Müller"
    (ws / "Unternehmen").mkdir(parents=True)
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    (ws / "Unternehmen" / ".kit-config").write_bytes(data)
    r = run_lib(shell, f'slk_config "{ws}"')
    return r.returncode, r.stdout.decode(), r.stderr.decode()


def test_config_valid_is_printed_in_schema_order(shell, tmp_path):
    code, out, err = konfig(shell, tmp_path, GUELTIG)
    assert (code, err) == (0, "") and out == GUELTIG


def test_config_from_notepad_is_accepted(shell, tmp_path):
    text = "\ufeff# Einstellungen\r\n" + GUELTIG.replace("\n", "\r\n").replace("ablage=github", "ablage = github ")
    code, out, _ = konfig(shell, tmp_path, text)
    assert code == 0 and "ablage=github\n" in out


@pytest.mark.parametrize("text", [
    "",                                                   # empty
    GUELTIG.replace("sprache=de\n", ""),                  # missing key
    GUELTIG + "farbe=blau\n",                             # unknown key
    GUELTIG + "ablage=lokal\n",                           # duplicate
    GUELTIG.replace("ablage=github", "ablage=dropbox"),   # bad value
    GUELTIG.replace("monatsstart=erster-werktag", "monatsstart=31"),
    "ablage=github\n" + GUELTIG.replace("ablage=github\n", ""),  # schema not first
    GUELTIG.replace("git_auto=ja", "git_auto"),           # no '='
])
def test_config_invalid_prints_nothing(shell, tmp_path, text):
    code, out, err = konfig(shell, tmp_path, text)
    assert (code, out, err) == (1, "", "")


def test_schema_keys_match_spec_table():
    keys = [l.split("=")[0] for l in SCHEMA.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    assert keys == ["schema", "ablage", "git_auto", "laufzeit", "beispieldaten", "mail", "sprache", "wochenstart",
                    "monatsstart"]


def test_workspace_found_above_and_below(shell, tmp_path):
    ws = tmp_path / "Kundendienst Müller"
    (ws / "01_Vorgaenge" / "offen").mkdir(parents=True)
    assert lib(shell, f'slk_ws_from "{ws}/01_Vorgaenge/offen"')[1] == str(ws)
    assert lib(shell, f'slk_ws_below "{tmp_path}"')[1] == str(ws)
    assert lib(shell, f'slk_ws_from "{tmp_path}"')[0] == 1


@pytest.mark.parametrize("datum", ["1970-01-01", "2024-02-29", "2026-08-01", "2026-10-01", "2031-12-31"])
def test_days_and_weekday_match_python(shell, datum):
    d = dt.date.fromisoformat(datum)
    assert lib(shell, f"slk_days {datum}")[1] == f"{(d - dt.date(1970, 1, 1)).days}\n"
    assert lib(shell, f"slk_wochentag {datum}")[1] == f"{d.weekday()}\n"


@pytest.mark.parametrize("a,b,neuer", [("0.2.0", "0.1.9", True), ("0.10.0", "0.9.0", True),
                                       ("0.1.0", "0.1.0", False), ("0.1", "0.1.1", False), ("1.0.0", "", True)])
def test_ver_gt(shell, a, b, neuer):
    assert (lib(shell, f'slk_ver_gt "{a}" "{b}" && echo ja')[1] == "ja\n") is neuer


def test_json_str_round_trips(shell):
    out = lib(shell, "slk_json_str \"$(printf 'a\"b\\\\c\\nzwei\\tTab Müller')\"")[1]
    assert json.loads(out) == 'a"b\\c\nzwei\tTab Müller'
    out = lib(shell, "slk_json_str \"$(printf 'a\\rb\\001c')\"")[1]
    assert json.loads(out) == "a\rbc"


def test_log_appends_and_rotates(shell, tmp_path):
    ws = tmp_path / "ws"
    (ws / "Unternehmen").mkdir(parents=True)
    log = ws / "Unternehmen" / ".kit-protokoll"
    log.write_text("x" * 300_000, encoding="utf-8")
    lib(shell, f'slk_log "{ws}" BLOCK "regel tool=Bash"')
    assert (ws / "Unternehmen" / ".kit-protokoll.1").stat().st_size == 300_000
    assert "\tBLOCK\tregel tool=Bash\n" in log.read_text(encoding="utf-8")
    lib(shell, f'SLK_KEIN_PROTOKOLL=1 slk_log "{ws}" BLOCK zwei')
    assert "zwei" not in log.read_text(encoding="utf-8")


def test_hook_files_stay_lf_on_windows_checkouts():
    for f in ["plugin/hooks/lib.sh", "plugin/hooks/json.awk", "plugin/vorlagen/kit-config.schema"]:
        out = subprocess.run(["git", "check-attr", "eol", "--", f], cwd=ROOT, capture_output=True, text=True).stdout
        assert out.strip().endswith("eol: lf"), out
    for f in HOOKS.iterdir():
        assert b"\r" not in f.read_bytes(), f


def awk(script, text, **v):
    args = ["awk"] + [f"-v{k}={x}" for k, x in v.items()] + ["-f", str(HOOKS / script)]
    return subprocess.run(args, input=text, capture_output=True, text=True).stdout


def test_segments_split_quote_aware_and_flag_args():
    out = awk("segments.awk", 'xargs -n 1 rm x; echo "a & rm" $(ls) \'$HOME\' "$X" "*.md" $false').splitlines()
    assert out == ["rm\t000x\t100$xargs", "ls",
                   "echo\t001a & rm\t100$sub\t001$HOME\t101$X\t011*.md\t000$false"]


def test_segments_dirs_exe_escapes_and_wrappers():
    assert awk("segments.awk", "/bin/RM.exe C:\\a\\b").splitlines() == ["rm\t000C:/a/b"]
    assert awk("segments.awk", "trash 05/Retro\\ Anlage").splitlines() == ["trash\t00005/Retro Anlage"]
    assert awk("segments.awk", "bash -c 'rm -rf x' # rm y").splitlines() == ["bash\t000-c\t001rm -rf x", "rm\t000-rf\t000x"]



def test_segments_heredoc_with_real_crlf_ends_at_the_delimiter():
    out = awk("segments.awk", "cat <<EOF\r\nx\r\nEOF\r\nrm -rf 03_Berichte").splitlines()
    assert out[-1] == "rm\t000-rf\t00003_Berichte"

def test_json_awk_value_ending_in_escaped_backslash():
    out = awk("json.awk", '{"file_path":"C:\\\\dir\\\\","x":1}', want="file_path")
    assert out == "C:\\dir\\\n"


def test_lib_leaves_caller_variables_alone(shell, tmp_path):
    ws = tmp_path / "ws"
    (ws / "Unternehmen").mkdir(parents=True)
    script = (f'd=X f=Y n=Z m=W p=V; slk_ws_from "{ws}" >/dev/null; slk_ws_below "{tmp_path}" >/dev/null; '
              f'slk_norm_path a/../b /c >/dev/null; slk_ws_for /a/01_x/b 01_x; slk_days 2026-10-01 >/dev/null; slk_ver_gt 1.2.3 1.2.4; '
              f'slk_log "{ws}" E t >/dev/null; slk_json_str q >/dev/null; slk_config "{ws}" >/dev/null; '
              f'slk_get "a=b" a >/dev/null; echo "$d$f$n$m$p"')
    assert lib(shell, script, SLK_KEIN_PROTOKOLL="")[1] == "XYZWV\n"


def test_days_rejects_malformed_date(shell):
    assert lib(shell, "slk_days 2026-10-01x") == (1, "")


def test_ws_below_empty_arg_fails(shell):
    assert lib(shell, 'slk_ws_below ""') == (1, "")


def test_ws_from_deep_path(shell, tmp_path):
    ws = tmp_path / "ws"
    deep = ws.joinpath(*["d"] * 15)
    deep.mkdir(parents=True)
    (ws / "01_Vorgaenge").mkdir()
    assert lib(shell, f'slk_ws_from "{deep}"')[1] == str(ws)


def test_field_absent_returns_zero(shell):
    assert lib(shell, "slk_field '{\"a\":1}' zzz") == (0, "")


def test_log_flattens_tabs_and_newlines(shell, tmp_path):
    ws = tmp_path / "ws"
    (ws / "Unternehmen").mkdir(parents=True)
    lib(shell, f'slk_log "{ws}" E "$(printf \'a\\tb\\nc\')"')
    assert (ws / "Unternehmen" / ".kit-protokoll").read_text().endswith("\tE\ta b c\n")


def test_get_first_match_and_absent(shell):
    assert lib(shell, "slk_get \"$(printf 'a=1\\nb=2\\na=3')\" a")[1] == "1\n"
    assert lib(shell, "slk_get 'a=1' zz")[1] == ""


@pytest.mark.parametrize("pfad,erwartet", [
    ("a/b.md", "/cwd/a/b.md"), ("/x/nope/../y", "/x/y"), ("/x/./y//z", "/x/y/z"),
    (r"\x\y\..\z", "/x/z"), (r"C:\a\..\b", "C:/b"), ("../../..//q", "/q"), ("/x/y/", "/x/y"),
])
def test_norm_path(shell, pfad, erwartet):
    assert lib(shell, f"slk_norm_path '{pfad}' /cwd")[1] == erwartet


def test_ws_for_tries_every_occurrence(shell, tmp_path):
    ws = tmp_path / "Unternehmen" / "Kunden Müller"
    ws.mkdir(parents=True)
    pfad = f"{ws}/Unternehmen/profil.md"
    assert lib(shell, f'slk_ws_for "{pfad}" unternehmen')[0] == 1
    (ws / "01_Vorgaenge").mkdir()
    assert lib(shell, f'slk_ws_for "{pfad}" unternehmen') == (0, str(ws))
    assert lib(shell, f'slk_ws_for "{ws}/01_VORGAENGE/x.md" 01_vorgaenge') == (0, str(ws))
    assert lib(shell, f'slk_ws_for "{tmp_path}/Unternehmen/y" unternehmen')[0] == 1
