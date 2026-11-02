import pytest

from hookrun import NS, PAYLOADS, bash, echt, run_hook

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
    # heredoc edge cases: arithmetic <<, substitutions in unquoted bodies, CRLF
    ("echo $((1<<2))\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("echo $(( 1 << 2 ))\nrm 01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ("(( x = 1<<2 ))\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("(( x = a << b ))\nrm -rf 03_Berichte", "shell-rekursiv"),
    ("cat <<EOF\n$(rm -rf 03_Berichte)\nEOF", "shell-rekursiv"),
    ("cat <<EOF\n`rm -rf 03_Berichte`\nEOF", "shell-rekursiv"),
    ("cat <<EOF > /tmp/x\nText $(rm 01_Vorgaenge/offen/V-0001.md) Ende\nEOF\nls", "shell-geschuetzt"),
    ("cat <<EOF\r\nx\r\nEOF\r\nrm -rf 03_Berichte", "shell-rekursiv"),
    # final review: the whole workspace (or a parent) moved or deleted; cd/pushd earlier on the line count
    ('mv "../Kundendienst Müller" /tmp/', "shell-geschuetzt"),
    ('cd .. && trash "Kundendienst Müller"', "shell-geschuetzt"),
    ('pushd .. && mv "Kundendienst Müller" /tmp/x', "shell-geschuetzt"),
    ("mv . /tmp/x", "shell-geschuetzt"),
    ("rm -rf ..", "shell-geschuetzt"),
    ("rm -rf /", "shell-geschuetzt"),
    ("cd 03_Berichte; cd ../..; rm -rf 'Kundendienst Müller'", "shell-geschuetzt"),
    # deletes fed by a pipeline: the targets are unknown
    ("Get-ChildItem -Recurse -File | Remove-Item", "shell-platzhalter"),
    ("ls -r | rm", "shell-platzhalter"),
    ("ls 03_Berichte | rm -f", "shell-platzhalter"),
    # git rm -r without --cached
    ("git rm -r 03_Berichte", "shell-rekursiv"),
    ("git rm -rf alt", "shell-rekursiv"),
    ("git -C . rm --recursive -q alt", "shell-rekursiv"),
    # fix wave 2: folder names after , : { ; a cd that may not have happened; mv -T
    ("rm {03_Berichte/a.md,Unternehmen/profil.md}", "shell-geschuetzt"),
    ("cp x.md 03_Berichte/a.md,01_Vorgaenge/offen/V-0001.md", "shell-geschuetzt"),
    ('cd gibtsnicht; trash "../Kundendienst Müller"', "shell-geschuetzt"),
    ('(cd 03_Berichte); trash "../Kundendienst Müller"', "shell-geschuetzt"),
    ('pushd 03_Berichte; popd; trash "../Kundendienst Müller"', "shell-geschuetzt"),
    ('echo x | cd 03_Berichte; trash "../Kundendienst Müller"', "shell-geschuetzt"),
    ('echo $(cd 03_Berichte); mv "../Kundendienst Müller" /tmp/x', "shell-geschuetzt"),
    ("cd gibtsnicht; trash 04_Angebote", "shell-rekursiv"),
    ("(cd 03_Berichte); trash 04_Angebote", "shell-rekursiv"),
    ('mv -T "../Kundendienst Müller" /tmp/x', "shell-geschuetzt"),
    # fix wave 3: -t combined with other short flags
    ("mv -vt /tmp ..", "shell-geschuetzt"),
    ("mv -tv /tmp ..", "shell-geschuetzt"),
    ("mv -vt/tmp ..", "shell-geschuetzt"),
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
    "echo $((1<<2))",
    "cat <<'EOF' > 03_Berichte/n.md\n$(nicht ausführen)\nEOF",
    'cat <<"EOF" > /tmp/x\n`rm -rf 03_Berichte`\nEOF',
    "cat <<E\"O\"F > /tmp/x\n$(rm -rf 03_Berichte)\nEOF",
    "cat <<EOF > /tmp/x\nPreis \\$(netto) und \\`x\\`\nEOF",
    # final review
    "mv 03_Berichte/a.md 04_Angebote/",
    "mv 03_Berichte/a.md .",
    "cd 03_Berichte && rm alt.md",
    "ls | grep x",
    "cat a | tee /tmp/b",
    "ls x.md || rm 03_Berichte/alt.md",
    "git rm --cached -r x",
    "git rm datei.md",
    "cp 03_Berichte/Unternehmensbericht.docx 04_Angebote/",
    "mv 06_Kunden/Partnerunternehmen.md 06_Kunden/alt.md",
    "echo x > 03_Berichte/Unternehmensbericht.md",
    # fix wave 2
    "cp 03_Berichte/a.md 06_Kunden/Büunternehmen.md",
    "cp 03_Berichte/a.md 06_Kunden/unternehmen-alt.md",
    "cp 03_Berichte/a.md 06_Kunden/Unternehmen.md",
    "mv -T 03_Berichte/a.md 03_Berichte/b.md",
    "mv -t 04_Angebote 03_Berichte/a.md",
    "cd 03_Berichte && rm a.md",
    # fix wave 3: a non-ASCII letter after the name keeps it part of a longer word (en dash is not a separator)
    "rm 06_Kunden/UnternehmenÜbersicht.md",
    "cp a.md 06_Kunden/Unternehmen–Liste.md",
    "mv -vt 04_Angebote 03_Berichte/a.md",
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
    code, err = pre(shell, kit_ws, bash(kit_ws, cmd, agent=NS + "finanzen"))
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


@pytest.mark.parametrize("command", [
    "Move-Item . C:/tmp",
    "Set-Location ..; Remove-Item 'Kundendienst Müller'",
    "Move-Item -Path . -Destination C:/tmp",
    "Move-Item C:/tmp/x -Path ..",
    "Remove-Item -Path:Unternehmen/profil.md",
    "Remove-Item -LiteralPath:01_Vorgaenge/offen/V-0001.md",
    "Remove-Item 03_Berichte/a.md,Unternehmen/profil.md",
    "Set-Content -Path:Unternehmen/profil.md -Value x",
    # fix wave 3: PowerShell's typographic quotes and the no-break space separate words
    "Remove-Item „Unternehmen\\profil.md“",
    "Remove-Item “Unternehmen\\profil.md”",
    "Remove-Item ‘Unternehmen\\profil.md’",
    "Remove-Item -Path „01_Vorgaenge\\offen\\V-0001.md“",
    "Set-Content „Unternehmen\\profil.md“ x",
    '"x" > „Unternehmen\\profil.md“',
    "Remove-Item 03_Berichte\\a.md,„Unternehmen\\profil.md“",
    "Remove-Item x, Unternehmen\\profil.md",
])
def test_powershell_cannot_move_the_workspace(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command, tool="PowerShell"))
    assert code == 2 and regel(kit_ws).startswith("shell-geschuetzt tool=PowerShell"), err


def test_deleting_or_moving_the_workspace_or_a_parent_by_absolute_path(shell, kit_ws):
    for command in [f'rm -rf "{kit_ws.parent}"', f'trash "{kit_ws}"', f'mv "{kit_ws}/" /tmp/x',
                    f'rm -rf "{kit_ws.parent.parent}"']:
        code, err = pre(shell, kit_ws, bash(kit_ws, command))
        assert code == 2 and regel(kit_ws).startswith("shell-geschuetzt tool=Bash"), command
    assert pre(shell, kit_ws, bash(kit_ws, f'mv "{kit_ws}/03_Berichte/a.md" "{kit_ws}"')) == (0, "")


def test_workspace_inside_a_folder_named_unternehmen(shell, tmp_path):
    from conftest import baue
    ws = tmp_path / "Unternehmen" / "Kundendienst"
    ws.mkdir(parents=True)
    baue(ws, mit_vorgaengen=False)
    for command in ["cp 03_Berichte/a.md 03_Berichte/b.md", f'cp "{ws}/03_Berichte/a.md" "{ws}/03_Berichte/b.md"',
                    f'echo x > "{ws}/03_Berichte/b.md"']:
        assert pre(shell, ws, bash(ws, command)) == (0, ""), command
    for command in ["rm Unternehmen/profil.md", f'rm "{ws}/Unternehmen/profil.md"',
                    f'echo x > "{ws}/01_Vorgaenge/offen/V-0001.md"']:
        assert pre(shell, ws, bash(ws, command))[0] == 2, command
        assert regel(ws).startswith("shell-geschuetzt"), command


def test_overlong_command_is_blocked_before_parsing(shell, kit_ws):
    command = "echo " + "x" * (140 * 1024)
    code, err = pre(shell, kit_ws, bash(kit_ws, command))
    assert code == 2 and "zu lang zum Prüfen" in err and "Write-Werkzeug" in err
    assert regel(kit_ws).startswith("shell-zu-lang tool=Bash")
    assert pre(shell, kit_ws, bash(kit_ws, "echo " + "x" * (100 * 1024))) == (0, "")


def test_powershell_location_stack_cannot_hide_a_folder_delete(shell, kit_ws):
    p = bash(kit_ws, "Push-Location 03_Berichte; Pop-Location; Remove-Item 04_Angebote", tool="PowerShell")
    assert pre(shell, kit_ws, p)[0] == 2 and regel(kit_ws).startswith("shell-rekursiv tool=PowerShell")


def test_mv_capital_t_does_not_exempt_the_source(shell, kit_ws):
    code, err = pre(shell, kit_ws, bash(kit_ws, f'mv -T "{kit_ws}" /tmp/x'))
    assert code == 2 and regel(kit_ws).startswith("shell-geschuetzt tool=Bash"), err


VORLAGE_RAUS = [
    "cp Unternehmen/vorlagen/briefkopf.docx /tmp/briefkopf.docx",
    'cp "Unternehmen/vorlagen/briefkopf.docx" "$TMPDIR/nm/ref.docx"',
    "cp Unternehmen/vorlagen/briefkopf.docx 04_Angebote/entwurf.docx",
    "cp -r Unternehmen/vorlagen /tmp/vorlagen",
    "mkdir -p /tmp/x && cp Unternehmen/vorlagen/master.pptx /tmp/x/ && ls /tmp/x",
    "Copy-Item -Path Unternehmen\\vorlagen\\briefkopf.docx -Destination C:\\Temp\\b.docx",
]


@pytest.mark.parametrize("command", VORLAGE_RAUS)
def test_templates_may_be_copied_out_of_the_template_folder(shell, kit_ws, command):
    # Letterhead and master are read by Claude's document skills (entscheidungsvorlage: "copy the letterhead").
    assert pre(shell, kit_ws, bash(kit_ws, command)) == (0, ""), command


def test_templates_copied_out_by_absolute_path(shell, kit_ws):
    command = f'cp "{kit_ws}/Unternehmen/vorlagen/briefkopf.docx" /tmp/ref.docx'
    assert pre(shell, kit_ws, bash(kit_ws, command)) == (0, "")


@pytest.mark.parametrize("command", [
    "cp /tmp/x.docx Unternehmen/vorlagen/briefkopf.docx",                   # overwrite a template
    "cp Unternehmen/vorlagen/briefkopf.docx Unternehmen/vorlagen/b.docx",   # write into the folder
    "cp Unternehmen/vorlagen/briefkopf.docx Unternehmen/profil.md",
    "cp -t Unternehmen Unternehmen/vorlagen/briefkopf.docx",
    "cp --target-directory=Unternehmen/vorlagen Unternehmen/vorlagen/briefkopf.docx",
    "cp Unternehmen/profil.md /tmp/p.md",                                   # only the template folder
    "cp Unternehmen/vorlagen/../profil.md /tmp/p.md",
    "cp Unternehmen/vorlagen/briefkopf.docx /tmp/b.docx && rm Unternehmen/profil.md",
    "cp Unternehmen/vorlagen/briefkopf.docx /tmp/b.docx; echo x > Unternehmen/vorlagen/briefkopf.docx",
    "mv Unternehmen/vorlagen/briefkopf.docx /tmp/b.docx",                   # a move deletes the source
    "cp Unternehmen/vorlagen/briefkopf.docx /tmp/a; cp /tmp/x Unternehmen/vorlagen/briefkopf.docx",
    "rsync -a --delete Unternehmen/vorlagen/ /tmp/v/",
    "ln -s /tmp/x Unternehmen/vorlagen/briefkopf.docx",
    "python3 -c \"open('Unternehmen/vorlagen/briefkopf.docx','w')\"",
    "cp Unternehmen/vorlagen/briefkopf.docx 01_Vorgaenge/offen/V-0001.md",
    "Copy-Item -Path C:\\Temp\\b.docx -Destination Unternehmen\\vorlagen\\briefkopf.docx",
])
def test_template_folder_stays_protected_against_writes(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command))
    assert code == 2 and regel(kit_ws).startswith("shell-geschuetzt"), (command, err)


def test_copying_out_from_inside_a_protected_folder_stays_blocked(shell, kit_ws):
    p = bash(kit_ws, "cp briefkopf.docx /tmp/b.docx", cwd=kit_ws / "Unternehmen" / "vorlagen")
    assert pre(shell, kit_ws, p)[0] == 2


# T-1952: reading a protected folder in one simple command must not make an unrelated cp or inline code in another
# simple command count as touching it. The three refused calls of the 2026-10-27 demo rehearsal, verbatim.
def demo(name, ws):
    return (PAYLOADS / f"T-1952-{name}.sh").read_text(encoding="utf-8").replace("__WS__", str(ws))


@pytest.fixture
def beispiel(kit_ws):
    for d in ("Unternehmen/vorlagen", "Unternehmen/agenten", "01_Vorgaenge/offen", "06_Kunden/Hansa Pack AG"):
        (kit_ws / "Beispiel" / d).mkdir(parents=True, exist_ok=True)
    return kit_ws


@pytest.mark.parametrize("name", ["lesen-und-python", "briefkopf-ansehen"])
def test_demo_reads_beside_harmless_cp_or_inline_code_pass(shell, beispiel, name):
    assert pre(shell, beispiel, bash(beispiel, demo(name, beispiel), agent=NS + "betrieb")) == (0, "")


def test_demo_decision_memo_inline_code_reading_a_case_stays_blocked(shell, beispiel):
    # Its "python3 - <<EOF" opens 01_Vorgaenge/offen/V-0003.md: inline code naming a protected folder, read or write.
    code, err = pre(shell, beispiel, bash(beispiel, demo("entscheidungsvorlage", beispiel), agent=NS + "betrieb"))
    assert code == 2 and regel(beispiel).startswith("shell-geschuetzt tool=Bash"), err


DOKUMENT_WEG = [
    # The documented route (Ohne Dokument-Skill): letterhead copied out, script in the temp folder, uv run.
    'mkdir -p "$TMPDIR/ev" && cp Unternehmen/vorlagen/briefkopf.docx "$TMPDIR/ev/briefkopf.docx" && '
    'uv run --with python-docx==1.1.2 python "$TMPDIR/ev/bau.py"',
    # ... with reads of the case and company files in the same call
    "cat 01_Vorgaenge/offen/V-0003.md Unternehmen/freigabegrenzen.md; cp Unternehmen/vorlagen/briefkopf.docx "
    "/tmp/ev/b.docx && uv run --with python-docx==1.1.2 python /tmp/ev/bau.py",
    "sed -n 1,40p 01_Vorgaenge/offen/V-0003.md | head -5; uv run --with python-docx==1.1.2 python -I -c "
    "\"import docx; print(docx.Document('/tmp/ev/b.docx').paragraphs)\"",
    "ls Unternehmen Unternehmen/vorlagen 2>&1; head -n 3 Unternehmen/kpi-ziele.md 2>/dev/null; "
    "python3 -c \"import json; print(json.load(open('/tmp/mr.json')))\"",
    "grep -n Empfehlung 01_Vorgaenge/offen/V-0003.md && cp Unternehmen/vorlagen/master.pptx /tmp/ev/",
    'wc -l "Unternehmen/profil.md" && node -e "console.log(1)"',
]


@pytest.mark.parametrize("command", DOKUMENT_WEG)
def test_document_route_with_reads_passes(shell, kit_ws, command):
    assert pre(shell, kit_ws, bash(kit_ws, command)) == (0, ""), command


@pytest.mark.parametrize("command", [
    # a read does not excuse a second mention by a writing command or by inline code
    "cat Unternehmen/profil.md; python3 -c \"open('Unternehmen/profil.md','w')\"",
    "cat Unternehmen/profil.md.bak; python3 -c \"open('Unternehmen/profil.md','w')\"",
    "ls Unternehmen; python3 -c \"import os; os.remove('Unternehmen/profil.md')\"",
    "cat 01_Vorgaenge/offen/V-0001.md && python3 - <<'EOF'\nopen('01_Vorgaenge/offen/V-0001.md','w')\nEOF",
    "cat Unternehmen/profil.md | python3 -c \"import sys; open(sys.argv[1],'w')\" Unternehmen/profil.md",
    "cat Unternehmen/profil.md && mv Unternehmen/profil.md /tmp/",
    "head Unternehmen/profil.md; rm Unternehmen/profil.md",
    "ls Unternehmen; cp /tmp/x Unternehmen/profil.md",
    "cat Unternehmen/vorlagen/briefkopf.docx; cp /tmp/x Unternehmen/vorlagen/briefkopf.docx",
    "cat 01_Vorgaenge/offen/V-0001.md; sed -i '' 's/a/b/' 01_Vorgaenge/offen/V-0001.md",
    "sed -n 1p 01_Vorgaenge/offen/V-0001.md; uv run python -c \"open('01_Vorgaenge/offen/V-0001.md','w')\"",
    # redirections out of a reading command
    "cat /tmp/x > Unternehmen/profil.md",
    "cat /tmp/x >Unternehmen/profil.md",
    "cat /tmp/x >> 01_Vorgaenge/offen/V-0001.md",
    "head /tmp/x 2> Unternehmen/fehler.log",
    "cat Unternehmen/profil.md > Unternehmen/kopie.md",
    "cat <> Unternehmen/profil.md",
    "grep x /tmp/a | tee Unternehmen/profil.md",
    # a read whose output feeds another command hands the name on (pipe, xargs, substitution, process substitution)
    "ls Unternehmen/profil.md | xargs cp /dev/null",
    "ls Unternehmen/profil.md | xargs tee",
    "ls Unternehmen/profil.md | head -1 | xargs cp /dev/null",
    "ls Unternehmen/profil.md | python3 -c 'import sys; open(sys.stdin.read().strip(), \"w\")'",
    "x=$(ls Unternehmen/profil.md); cp /dev/null \"$x\"",
    "for f in `ls Unternehmen/profil.md`; do cp /dev/null \"$f\"; done",
    "while read f; do cp /dev/null \"$f\"; done < <(ls Unternehmen/profil.md)",
    "python3 -c 'import sys; open(sys.stdin.read().strip(), \"w\")' < <(ls Unternehmen/profil.md)",
    "(ls Unternehmen/profil.md) | xargs cp /dev/null",
    "bash -c 'ls Unternehmen/profil.md' | xargs cp /dev/null",
    "ls Unternehmen/profil.md > /tmp/l; python3 -c \"open(open('/tmp/l').read().strip(), 'w')\"",
    "ls Unternehmen/profil.md >& /tmp/l; python3 -c \"open(open('/tmp/l').read().strip(), 'w')\"",
    "ls Unternehmen/profil.md 2>&1 >/tmp/l; python3 -c \"open(open('/tmp/l').read().strip(), 'w')\"",
    # a group passes the output of its reads on as a whole
    "{ cat Unternehmen/profil.md; } | xargs cp /dev/null",
    "for f in a; do ls Unternehmen/profil.md; done | xargs cp /dev/null",
    "if true; then ls Unternehmen/profil.md; fi | python3 -c 'import sys; open(sys.stdin.read().strip(), \"w\")'",
    "{ ls Unternehmen/profil.md; } > /tmp/l; python3 -c \"open(open('/tmp/l').read().strip(), 'w')\"",
    "exec > /tmp/l; ls Unternehmen/profil.md; python3 -c \"open(open('/tmp/l').read().strip(), 'w')\"",
    # a redirection after the copy is not its destination (refused on 0.3.0 neither: found while fixing T-1952)
    "cp Unternehmen/vorlagen/briefkopf.docx Unternehmen/vorlagen/b.docx 2>/dev/null",
    "cp Unternehmen/vorlagen/briefkopf.docx Unternehmen/vorlagen/b.docx 2>&1",
    "cp Unternehmen/vorlagen/briefkopf.docx Unternehmen/vorlagen/b.docx > /tmp/log",
    # sed reads files, but its script is not a file name
    "sed -e 's/a/b/' -i Unternehmen/profil.md",
    "sed --in-place 's/a/b/' 01_Vorgaenge/offen/V-0001.md",
    # the decision guard and the inline-code guards are unchanged
    "cat Unternehmen/profil.md; python3 -c \"import shutil; shutil.rmtree('03_Berichte')\"",
])
def test_reads_do_not_open_a_way_to_write_protected_folders(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command))
    assert code == 2, (command, err)


@pytest.mark.parametrize("command", [
    "Get-ChildItem Unternehmen/profil.md | Clear-Content",
    "Get-ChildItem 01_Vorgaenge -Recurse -File | Clear-Content",
    "Get-Content Unternehmen\\profil.md | Set-Content Unternehmen\\profil.md",
])
def test_powershell_reads_piped_into_writers_stay_blocked(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command, tool="PowerShell"))
    assert code == 2, (command, err)


def test_powershell_read_beside_inline_code_passes(shell, kit_ws):
    command = "Get-Content Unternehmen\\kpi-ziele.md; python3 -c \"print(1)\""
    assert pre(shell, kit_ws, bash(kit_ws, command, tool="PowerShell")) == (0, "")


def test_reading_inside_a_protected_folder_beside_inline_code_stays_blocked(shell, kit_ws):
    p = bash(kit_ws, "cat profil.md; python3 -c \"print(1)\"", cwd=kit_ws / "Unternehmen")
    assert pre(shell, kit_ws, p)[0] == 2


# T-1952, second finding: a flag belongs to its own simple command. grep -i beside sed -n is no sed -i.
V = "01_Vorgaenge/offen/V-0004.md"


def test_demo_overview_of_all_cases_passes(shell, kit_ws):
    # The call refused on 2026-11-02: a loop over the cases (sed -n) plus grep -i, verbatim.
    assert pre(shell, kit_ws, bash(kit_ws, demo("alle-vorgaenge", kit_ws))) == (0, "")


@pytest.mark.parametrize("command", [
    f"sed -n 1p {V}; grep -i hansa {V}",
    # the loop names the folder outside any reading command, so the read exemption cannot hide the flag rule
    'for f in 01_Vorgaenge/offen/V-*.md; do sed -n 1p "$f"; done; grep -i hansa 03_Berichte/x.md',
    'for f in 01_Vorgaenge/offen/V-*.md; do grep -i hansa "$f" | sed -n 1p; done',
    'for f in 01_Vorgaenge/offen/V-*.md; do sed -n "s/^titel: //p" "$f"; done; ls -I x 03_Berichte',
    f'bash -c "sed -n 1p {V}; grep -i hansa {V}"',
])
def test_a_flag_of_another_command_is_not_an_in_place_edit(shell, kit_ws, command):
    assert pre(shell, kit_ws, bash(kit_ws, command)) == (0, ""), command


@pytest.mark.parametrize("command", [
    # sed and perl editing in place: their own flag, in every form the rule knows
    f"sed -i '' s/a/b/ {V}",
    f"sed -i.bak s/a/b/ {V}",
    f"sed --in-place=.bak s/a/b/ {V}",
    f'sed "-i" s/a/b/ {V}',
    f"perl -i -pe s/a/b/ {V}",
    f"perl -pi -e s/a/b/ {V}",
    # ... wrapped, or in a substitution, loop or group
    f'bash -c "sed -i s/a/b/ {V}"',
    f"sh -c 'sed -i s/a/b/ {V}'",
    f'eval "sed -i s/a/b/ {V}"',
    f'bash -c "perl -i -pe s/a/b/ {V}"',
    f'x=$(sed -i s/a/b/ {V})',
    f"x=`sed -i s/a/b/ {V}`",
    f"{{ sed -i s/a/b/ {V}; }}",
    'for f in 01_Vorgaenge/offen/V-*.md; do sed -i s/a/b/ "$f"; done',
    # ... beside the commands that must pass
    f"sed -n 1p {V}; sed -i s/a/b/ {V}",
    f"grep -i hansa {V}; sed -i s/a/b/ {V}",
    f"sed -n 1p {V} && grep -i hansa {V} && sed -i s/a/b/ {V}",
    # a flag that arrives from elsewhere cannot be attributed to a command, so any -i still counts
    f"sed $(echo -i) s/a/b/ {V}",
    f"echo -i | xargs sed s/a/b/ {V}",
    'for f in 01_Vorgaenge/offen/V-*.md; do for o in -i; do sed "$o" s/a/b/ "$f"; done; done',
    "cd 01_Vorgaenge/offen; o=$(echo -i); sed $o s/a/b/ V-0004.md",
    f"for o in -i; do sed $o s/a/b/ {V}; done",
    f"o=$(echo -i); sed $o s/a/b/ {V}",
    # ... and an in-place edit the rule cannot see as sed's own still counts beside a harmless sed -n
    "sed -n 1p 03_Berichte/x.md; find 01_Vorgaenge -name '*.md' -exec sed -i s/a/b/ {} +",
    f"sed -n 1p 03_Berichte/x.md; bash -c \"bash -c 'sed -i s/a/b/ {V}'\"",
    f"sed -n 1p 03_Berichte/x.md; timeout 5 sed -i s/a/b/ {V}",
    f"sed -n 1p 03_Berichte/x.md; sh <<'EOF'\nsed -i s/a/b/ {V}\nEOF",
    # ... also when a reader's own -i sits inside a quoted substitution
    f'echo "$(grep -i x 03_Berichte/x.md)"; sed -n 1p 03_Berichte/x.md; timeout 5 sed -i s/a/b/ {V}',
    # inline code and heredocs on the protected folders, read or write
    f"python3 -c \"print(open('{V}').read())\"",
    f"sed -n 1p {V}; python3 -c \"print(open('{V}').read())\"",
    f"uv run python -c \"print(open('{V}').read())\"",
    f"python3 - <<'EOF'\nprint(open('{V}').read())\nEOF",
    f"grep -i hansa {V}; python3 - <<'EOF'\nprint(open('{V}').read())\nEOF",
    f"cat <<EOF > {V}\nleer\nEOF",
    # deletes, moves and redirects
    f"rm {V}",
    f"sed -n 1p {V}; rm {V}",
    f"grep -i hansa {V}; mv {V} /tmp/x.md",
    f"sed -n 1p {V}; grep -i hansa {V}; echo x > {V}",
    f"grep -i hansa 03_Berichte/x.md >> {V}",
    f"sed -n 1p 03_Berichte/x.md > {V}",
    f"grep -i hansa {V} | tee {V}",
    f"cp /tmp/x.md {V}",
])
def test_per_command_flags_keep_every_write_refused(shell, kit_ws, command):
    code, err = pre(shell, kit_ws, bash(kit_ws, command))
    assert code == 2 and regel(kit_ws).startswith("shell-geschuetzt tool=Bash"), (command, err)
