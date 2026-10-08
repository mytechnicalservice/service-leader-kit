import pytest

from hookrun import NS, bash, echt, run_hook

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
