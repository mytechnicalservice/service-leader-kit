import pytest

from hookrun import bash, echt, run_hook

BLOCK = [
    ("rm 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ('rm "01_Vorgaenge/offen/V-0001.md"', "shell-geschuetzt"),
    ("/bin/RM unternehmen/profil.md", "shell-geschuetzt"),
    ("mv Unternehmen/profil.md /tmp/", "shell-geschuetzt"),
    ("cp /tmp/leer.md 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ("echo x > 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    (": >> Unternehmen/preislogik.md", "shell-geschuetzt"),
    ("sed -i '' 's/a/b/' Unternehmen/profil.md", "shell-geschuetzt"),
    ("cat x | tee 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ("cd 01_Vorgaenge && rm offen/V-0001.md", "shell-geschuetzt"),
    ("git checkout -- 01_Vorgaenge", "shell-geschuetzt"),
    ("uv run python -c \"import os; os.remove('Unternehmen/x')\"", "shell-geschuetzt"),
    ("Remove-Item 01_Vorgaenge\\offen\\V-0001.md", "shell-geschuetzt"),
    ("rm -rf 03_Berichte", "shell-rekursiv"),
    ("rm -R alt", "shell-rekursiv"),
    ("rmdir 05_Projekte/alt", "shell-rekursiv"),
    ('find . -name "*.tmp" -delete', "shell-rekursiv"),
    ("git clean -fd", "shell-rekursiv"),
    ("Remove-Item -Recurse 03_Berichte", "shell-rekursiv"),
    ("python3 -c \"import shutil; shutil.rmtree('03_Berichte')\"", "shell-rekursiv"),
    ("rm 03_Berichte/*.md", "shell-platzhalter"),
    ('rm "$DATEI"', "shell-platzhalter"),
    ("curl -sI https://example.com", "shell-senden"),
    ("curl.exe -T bericht.pdf ftp://x", "shell-senden"),
    ("wget -q http://x", "shell-senden"),
    ("echo hallo | sendmail chef@firma.de", "shell-senden"),
    ("python3 -c \"import smtplib\"", "shell-senden"),
    ("Invoke-WebRequest -Uri https://x -Method Post", "shell-senden"),
    # commands wrapped in another shell, and heredocs
    ('bash -c "rm 01_Vorgaenge/offen/V-0001.md"', "shell-geschuetzt"),
    ("sh -c 'curl -s https://example.com'", "shell-senden"),
    ('eval "wget http://x"', "shell-senden"),
    ('powershell -Command "Remove-Item -Recurse 03_Berichte"', "shell-rekursiv"),
    ('cmd /c "del 01_Vorgaenge\\offen\\V-0001.md"', "shell-geschuetzt"),
    ("python3 - <<'EOF'\nimport os\nos.remove('01_Vorgaenge/offen/V-0001.md')\nEOF", "shell-geschuetzt"),
    ("cat <<EOF > Unternehmen/profil.md\nleer\nEOF", "shell-geschuetzt"),
]

ERLAUBT = [
    "rm 03_Berichte/alt.md",
    "ls -la 01_Vorgaenge/offen",
    "ls 01_Vorgaenge 2>/dev/null > /tmp/liste.txt",
    "cat Unternehmen/profil.md",
    "which curl",
    "ls  # Confirm rm  of nothing",
    "git status",
    "git push",
    'uv run "/p/plugin/scripts/vorgang.py" neu --ws "/x" --titel "Kopie & rm" --text "Quelle 01_Vorgaenge"',
    'uv run "/p/plugin/scripts/vorgang.py" entscheide --nr V-0001 --entscheidung freigegeben --von "Max" --dokument x',
    'echo "Müller \\"GmbH\\"" && ls 01_Vorgaenge',
    'bash -c "ls -la 01_Vorgaenge/offen"',
    "sh tools/auswertung.sh",
    'echo "bash -c rm alles"',
]


def pre(shell, ws, payload, proj=None):
    r = run_hook(shell, "pre-tool-use.sh", payload, proj or ws)
    return r.returncode, r.stderr.decode("utf-8")


def regel(ws):
    return (ws / "Unternehmen" / ".kit-protokoll").read_text(encoding="utf-8").splitlines()[-1].split("\t")[2]


@pytest.mark.parametrize("command,rule", BLOCK)
def test_dangerous_shell_commands_are_blocked(shell, kit_ws, command, rule):
    code, err = pre(shell, kit_ws, bash(kit_ws, command))
    assert code == 2 and err.startswith("Service Leader Kit – gesperrt:"), err
    assert regel(kit_ws).startswith(rule + " tool=Bash")


@pytest.mark.parametrize("command", ERLAUBT)
def test_harmless_commands_pass(shell, kit_ws, command):
    assert pre(shell, kit_ws, bash(kit_ws, command)) == (0, "")


def test_shell_inside_a_protected_folder_blocks_relative_deletes(shell, kit_ws):
    p = bash(kit_ws, "rm V-0001.md", cwd=kit_ws / "01_Vorgaenge" / "offen")
    assert pre(shell, kit_ws, p)[0] == 2
    p = bash(kit_ws, "echo x > V-0001.md", cwd=kit_ws / "01_Vorgaenge" / "offen")
    assert pre(shell, kit_ws, p)[0] == 2
    assert pre(shell, kit_ws, bash(kit_ws, "ls > /dev/null 2>&1", cwd=kit_ws / "Unternehmen"))[0] == 0


def test_only_the_human_decides(shell, kit_ws):
    cmd = 'uv run "/p/plugin/scripts/vorgang.py" entscheide --nr V-0001 --entscheidung freigegeben --von x --dokument y'
    code, err = pre(shell, kit_ws, bash(kit_ws, cmd, agent="service-leader-kit:finanzen"))
    assert code == 2 and "Empfehlung" in err
    assert pre(shell, kit_ws, bash(kit_ws, cmd))[0] == 0


def test_powershell_tool_is_guarded_like_bash(shell, kit_ws):
    assert pre(shell, kit_ws, bash(kit_ws, "Remove-Item -Recurse .", tool="PowerShell"))[0] == 2


def test_real_bash_payload_passes_and_is_guarded(shell, kit_ws):
    p = echt("PreToolUse-Bash.json", kit_ws)
    assert pre(shell, kit_ws, p)[0] == 0
    p["tool_input"]["command"] = "rm 01_Vorgaenge/offen/V-0001.md"
    assert pre(shell, kit_ws, p)[0] == 2


def test_parent_folder_opened_still_protects_the_workspace(shell, kit_ws):
    eltern = kit_ws.parent
    p = bash(eltern, f'rm "{kit_ws.name}/01_Vorgaenge/offen/V-0001.md"')
    assert pre(shell, kit_ws, p, proj=eltern)[0] == 2


def test_outside_a_workspace_nothing_is_blocked(shell, tmp_path):
    anderes = tmp_path / "myTS_app"
    anderes.mkdir()
    assert pre(shell, anderes, bash(anderes, "curl -s https://example.com && rm -rf build")) == (0, "")
