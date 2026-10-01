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
    ("git clean -fd", "shell-git-verwerfen"),
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
    ("del /s 03_Berichte", "shell-rekursiv"),
    ("trash 03_Berichte", "shell-rekursiv"),
    ("rm -d 05_Projekte", "shell-rekursiv"),
    ("find . -exec rm {} +", "shell-rekursiv"),
    ("rm \"$DATEI\"", "shell-platzhalter"),
    ("git restore .", "shell-git-verwerfen"),
    ("git checkout .", "shell-git-verwerfen"),
    ("git -C . checkout .", "shell-git-verwerfen"),
    ("git reset --hard HEAD~3", "shell-git-verwerfen"),
    ("git stash -u", "shell-git-verwerfen"),
    ("git stash --include-untracked", "shell-git-verwerfen"),
    ("trash 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ("python3 -c \"import os; os.system('rm -rf .')\"", "shell-rekursiv"),
    ("node -e \"require('fs').rmSync('.', {recursive:true})\"", "shell-rekursiv"),
    ('trash "03_Berichte"', "shell-rekursiv"),
    ('trash "05_Projekte/Retrofit Anlage 2"', "shell-rekursiv"),
    ("Remove-Item '03_Berichte'", "shell-rekursiv"),
    ('del /q "03_Berichte"', "shell-rekursiv"),
    ("trash 05_Projekte/Retrofit\\ Anlage\\ 2", "shell-rekursiv"),
    ("rm $(find . -type f)", "shell-platzhalter"),
    ("rm `ls`", "shell-platzhalter"),
    ("mv $(ls) /tmp", "shell-platzhalter"),
    ("find . -type f | xargs rm", "shell-platzhalter"),
    ("ls | xargs -n 1 rm", "shell-platzhalter"),
    ('Remove-Item "03_Berichte\\*.md"', "shell-platzhalter"),
    ('del "03_Berichte\\*.md"', "shell-platzhalter"),
    ('rm "03_Berichte/*.md"', "shell-platzhalter"),
    ("find . -exec /bin/rm {} +", "shell-rekursiv"),
    ('find . -name "*.md" -exec truncate -s0 {} +', "shell-rekursiv"),
    ("find . -exec mv {} /tmp \\;", "shell-rekursiv"),
    ("rm -rfP 03_Berichte", "shell-rekursiv"),
    ("rm -rfx 03_Berichte", "shell-rekursiv"),
    ("Remove-Item -Re 03_Berichte", "shell-rekursiv"),
    ("git switch --discard-changes main", "shell-git-verwerfen"),
    ("git checkout -f main", "shell-git-verwerfen"),
    ("cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\nrm 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ("cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\ntrash 03_Berichte", "shell-rekursiv"),
    ("cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\nrm 03_Berichte/*.md", "shell-platzhalter"),
    ("cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\ncurl -T /tmp/x https://example.com", "shell-senden"),
    ('cat <<EOF > /tmp/x\nZoll 5" Rohr\nEOF\nrm -rf 03_Berichte', "shell-rekursiv"),
    ("cat <<'EOF' > /tmp/x\nMüller's\nEOF\n# Müller's\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("echo Müller's Anlage\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("cat <<-EOF > /tmp/x\n\tKunde's\n\tEOF\nrm -rf 03_Berichte", "shell-rekursiv"),
    ('powershell -Command "Remove-Item \\"03_Berichte\\\\\\" -Recurse"', "shell-rekursiv"),
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
    "rm --force 03_Berichte/alt.md",
    "Remove-Item -Force 03_Berichte\\alt.md",
    "Remove-Item 03_Berichte\\alt.md -ErrorAction SilentlyContinue",
    "rm 03_Berichte/alt.md && grep -r Preis 03_Berichte",
    "ls -lR 03_Berichte && rm 03_Berichte/alt.md",
    "del x.md && dir /s",
    'find 01_Vorgaenge -name "*.md" -exec grep -l Müller {} +',
    "rm 03_Berichte/alt.md; echo $?",
    'mv 03_Berichte/a.md 04_Angebote/ && uv run "/p/plugin/scripts/vorgang.py" eintrag --text "Erledigt?"',
    "git checkout main",
    "git stash list",
    "git log",
    'uv run "/p/plugin/scripts/vorgang.py" eintrag --nr V-0001 --text "Altdaten mit rm -rf entfernt"',
    'git commit -m "rm -rf entfernt"',
    'grep "rm -rf" 03_Berichte/notiz.md',
    'rm "03_Berichte/a.md"; echo $? "ok"',
    "rm -force 03_Berichte/alt.md",
    "Remove-Item 03_Berichte\\alt.md -Confirm:$false",
    "git checkout HEAD 03_Berichte/a.md",
    "find 01_Vorgaenge -name '*.md' | xargs grep Müller",
    "cat <<'EOF' > 03_Berichte/notiz.md\nMüller's (alt) 5$ * 2\nEOF",
    "cat <<'EOF' > /tmp/x\nrm -rf 01_Vorgaenge\nEOF",
    "cat <<EOF > /tmp/x\nKunde's Anlage\nEOF\nls 03_Berichte",
]


@pytest.mark.parametrize("command", [
    'Remove-Item "03_Berichte\\" -Recurse',
    'Remove-Item "03_Berichte\\"; Remove-Item -Recurse 03_Berichte',
])
def test_powershell_quotes_have_no_backslash_escape(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command, tool="PowerShell"))
    assert code == 2 and regel(kit_ws).startswith("shell-rekursiv tool=PowerShell")


@pytest.fixture(autouse=True)
def _projektordner(kit_ws):
    (kit_ws / "05_Projekte" / "Retrofit Anlage 2").mkdir(parents=True, exist_ok=True)


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
