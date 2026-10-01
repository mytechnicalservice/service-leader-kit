# Sourced by stop.sh when ablage=github and the workspace is a git repo (spec §7.0, §11). Sets $meldung.
# git_auto=ja: commit everything, then push whatever is not yet on GitHub (so a failed push is retried).
# git_auto=nein: list the changed files for GitHub Desktop, once per change set.
# Untracked files are listed one by one (-uall); the hooks' own marker files never count as a change.
aenderungen=$(git -C "$ws" -c core.quotepath=false status --porcelain -uall 2>/dev/null |
  grep -v -e '\.kit-letzter-stop$' -e '\.kit-stand$' -e '\.kit-protokoll')
if [ "$(slk_get "$cfg" git_auto)" = ja ]; then
  if [ -n "$aenderungen" ]; then
    wer=""
    [ -n "$(git -C "$ws" config user.email 2>/dev/null)" ] ||
      wer="-c user.name=Service-Leader-Kit -c user.email=kit@service-leader-kit.invalid"
    # shellcheck disable=SC2086
    if ! { git -C "$ws" add -A >/dev/null 2>&1 &&
           git -C "$ws" $wer commit -q -m "Kit: Stand $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1; }; then
      meldung="Sicherung fehlgeschlagen: git konnte die Änderungen nicht speichern. Bitte gesundheitscheck ausführen."
      slk_log "$ws" GIT "commit fehlgeschlagen"
    fi
  fi
  vor=$(git -C "$ws" rev-list --count '@{u}..HEAD' 2>/dev/null || echo 1)
  if [ -z "$meldung" ] && [ "$vor" != 0 ] && git -C "$ws" rev-parse -q --verify HEAD >/dev/null 2>&1; then
    if GIT_TERMINAL_PROMPT=0 git -C "$ws" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
         push -q -u origin HEAD >/dev/null 2>&1; then
      slk_log "$ws" GIT "gesichert und übertragen"
    else
      meldung="Sicherung: Die Änderungen sind lokal gespeichert, aber nicht zu GitHub übertragen (keine Verbindung oder keine Berechtigung). Beim nächsten Mal versucht das Kit es erneut."
      slk_log "$ws" GIT "push fehlgeschlagen"
    fi
  fi
elif [ -n "$aenderungen" ]; then
  sig=$(printf '%s' "$aenderungen" | cksum)
  if [ "$sig" != "$(cat "$ws/.git/kit-erinnert" 2>/dev/null)" ]; then
    printf '%s' "$sig" > "$ws/.git/kit-erinnert" 2>/dev/null
    anzahl=$(printf '%s\n' "$aenderungen" | wc -l | tr -d ' ')
    liste=$(printf '%s\n' "$aenderungen" | cut -c4- | tr -d '"' | head -n 5 | tr '\n' ',' | sed 's/,$//; s/,/, /g')
    meldung="Geänderte Dateien ($anzahl): $liste – jetzt in GitHub Desktop sichern."
  fi
fi
