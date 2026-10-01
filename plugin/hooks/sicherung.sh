# Sourced by stop.sh when ablage=github and the workspace is a git repo (spec §7.0, §11). Sets $meldung.
# git_auto=ja: commit everything, then push whatever is not yet on GitHub (so a failed push is retried).
# git_auto=nein: list the changed files for GitHub Desktop, once per change set.
# Lock, temp and kit marker files never count (pathspec excludes, independent of any .gitignore).
# Untracked files are listed one by one (-uall).
gd=$(git -C "$ws" rev-parse --absolute-git-dir 2>/dev/null) || gd="$ws/.git"
_slk_git() { # git <subcommand and options> restricted to the files a backup should cover
  git -C "$ws" -c core.quotepath=false "$@" -- . ':(exclude)~$*' ':(exclude)**/~$*' ':(exclude)*.tmp' \
    ':(exclude)**/.*.tmp' ':(exclude)Unternehmen/.kit-protokoll*' ':(exclude)Unternehmen/.kit-stand' \
    ':(exclude)Unternehmen/.kit-letzter-stop' ':(exclude).DS_Store' ':(exclude)**/.DS_Store'
}
aenderungen=$(_slk_git status --porcelain -uall 2>/dev/null)
if [ "$(slk_get "$cfg" git_auto)" = ja ]; then
  if [ -n "$aenderungen" ] && { [ -e "$gd/MERGE_HEAD" ] || [ -e "$gd/rebase-merge" ] || [ -e "$gd/rebase-apply" ] ||
       [ -e "$gd/CHERRY_PICK_HEAD" ] || ! git -C "$ws" symbolic-ref -q HEAD >/dev/null 2>&1; }; then
    # Shown at every Stop while changes are waiting; nothing is added, committed or pushed.
    meldung="Sicherung pausiert: In GitHub Desktop ist noch ein Abgleich offen (Konflikt oder unvollständiger Zusammenführung). Bitte dort abschließen."
    slk_log "$ws" GIT "pausiert: merge/rebase/detached"
  else
    # Files GitHub would reject (> 90 MB) stay out of the backup and are named to the user.
    gross=""
    if [ -n "$aenderungen" ]; then
      groesse=$(find "$ws" -path "$ws/.git" -prune -o -type f -size +184320 -print 2>/dev/null)
      ok=""
      # git add exits 1 (yet stages everything else) when an excluded path is also ignored by .gitignore.
      addout=$(_slk_git add -A 2>&1) && addrc=0 || addrc=1
      if [ "$addrc" = 0 ] || printf '%s\n' "$addout" | grep -q 'ignored by one of your .gitignore'; then
        ok=1
        if [ -n "$groesse" ]; then
          while IFS= read -r f; do
            [ -n "$f" ] || continue
            git -C "$ws" reset -q -- ":(literal)${f#"$ws"/}" >/dev/null 2>&1
            gross="${gross:+$gross, }${f#"$ws"/}"
          done <<EOG
$groesse
EOG
        fi
        if ! git -C "$ws" diff --cached --quiet 2>/dev/null; then
          wer=""
          { [ -n "$(git -C "$ws" config user.email 2>/dev/null)" ] && [ -n "$(git -C "$ws" config user.name 2>/dev/null)" ]; } ||
            wer="-c user.name=Service-Leader-Kit -c user.email=kit@service-leader-kit.invalid"
          # shellcheck disable=SC2086
          git -C "$ws" $wer -c commit.gpgsign=false commit -q -m "Kit: Stand $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1 || ok=""
        fi
      fi
      if [ -z "$ok" ]; then
        meldung="Sicherung fehlgeschlagen: git konnte die Änderungen nicht speichern. Bitte gesundheitscheck ausführen."
        slk_log "$ws" GIT "commit fehlgeschlagen"
      fi
    fi
    vor=$(git -C "$ws" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 1)
    if [ -z "$meldung" ] && [ "$vor" != 0 ] && git -C "$ws" rev-parse -q --verify HEAD >/dev/null 2>&1; then
      # Never prompts, never outlasts the hook timeout: a watchdog kills a stuck push after $SLK_PUSH_FRIST seconds.
      plog="$gd/kit-push.log"
      GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never SSH_ASKPASS= \
        GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=15" \
        git -C "$ws" -c credential.interactive=false -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
        push -q -u origin HEAD >"$plog" 2>&1 </dev/null &
      pushpid=$!
      ( sleep "${SLK_PUSH_FRIST:-40}"; kill "$pushpid" ) >/dev/null 2>&1 &
      wachhund=$!
      wait "$pushpid" 2>/dev/null; pushrc=$?
      kill "$wachhund" >/dev/null 2>&1; wait "$wachhund" >/dev/null 2>&1
      if [ "$pushrc" = 0 ]; then
        slk_log "$ws" GIT "gesichert und übertragen"
      elif grep -q -e rejected -e non-fast-forward -e 'fetch first' "$plog" 2>/dev/null; then
        meldung="Sicherung: GitHub hat neuere Stände – bitte in GitHub Desktop zuerst abgleichen."
        slk_log "$ws" GIT "push abgelehnt (neuere Stände)"
      else
        meldung="Sicherung: Die Änderungen sind lokal gespeichert, aber nicht zu GitHub übertragen (keine Verbindung oder keine Berechtigung). Beim nächsten Mal versucht das Kit es erneut."
        slk_log "$ws" GIT "push fehlgeschlagen"
      fi
      rm -f "$plog" 2>/dev/null
    fi
    [ -z "$gross" ] || meldung="${meldung:+$meldung }$gross zu groß für GitHub, nicht gesichert."
  fi
elif [ -n "$aenderungen" ]; then
  sig=$(printf '%s' "$aenderungen" | cksum)
  if [ "$sig" != "$(cat "$gd/kit-erinnert" 2>/dev/null)" ]; then
    { printf '%s' "$sig" > "$gd/kit-erinnert"; } 2>/dev/null
    anzahl=$(printf '%s\n' "$aenderungen" | wc -l | tr -d ' ')
    liste=$(printf '%s\n' "$aenderungen" | cut -c4- | tr -d '"' | head -n 5 | tr '\n' ',' | sed 's/,$//; s/,/, /g')
    meldung="Geänderte Dateien ($anzahl): $liste – jetzt in GitHub Desktop sichern."
  fi
fi
