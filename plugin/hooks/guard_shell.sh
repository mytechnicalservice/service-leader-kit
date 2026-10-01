# Sourced by pre-tool-use.sh for Bash/PowerShell inside a workspace (spec §11, §10 alternative routes).
# Matching is on command words and flags, never on the whole payload (probe lessons, spec §11).
# Known limit: deliberate obfuscation (building a path from pieces, encoded commands) is not caught;
# the rules stop accidental and injected destruction or sending, not a determined human.
set -f
cmd=$(slk_field "$payload" command)
full=$(slk_lower "$(slk_slashes "$cmd")")                                  # everything, quotes kept
bare=$(printf '%s\n' "$full" | sed -e 's/"[^"]*"/ /g' -e "s/'[^']*'/ /g")  # quoted text removed
nq=$(printf '%s' "$full" | tr -d "\"'")                                    # quote marks removed, text kept
verbs=$(printf '%s\n' "$bare" | awk -f "$SLK_HOOKS/cmdwords.awk")
words=" $(printf '%s' "$bare" | tr '\n\t' '  ') "

has_verb() { for v in "$@"; do case "$verbs" in *" $v "*) return 0 ;; esac; done; return 1; }
has_word() { for v in "$@"; do case "$words" in *" $v "*) return 0 ;; esac; done; return 1; }
has_flag() { for t in $words; do case "$t" in $1) return 0 ;; esac; done; return 1; }

# A shell that runs a quoted command (bash -c "rm …", powershell -Command "…", eval "…") hides the real
# verbs in quotes: then the quoted text is checked as well. Only then, so quoted arguments of ordinary
# commands (vorgang.py --text "Kopie & rm") never count as commands. Heredocs need nothing extra: their
# lines are separate commands already (lesson from dcg, research 2026-10-01).
WRAP="bash sh zsh dash ksh eval powershell pwsh cmd"
# shellcheck disable=SC2086
if has_verb $WRAP; then
  verbs="$verbs$(printf '%s\n' "$nq" | awk -v inner=1 -f "$SLK_HOOKS/cmdwords.awk")"
  words="$words$(printf '%s' "$nq" | tr '\n\t' '  ') "
fi

DEL="rm rmdir unlink shred truncate remove-item ri del erase rd"
MOVE="mv move-item mi move ren rename-item rni"
COPY="cp copy copy-item cpi rsync ln install dd tee set-content sc out-file clear-content clc add-content ac"
INLINE="python python3 py node perl ruby osascript powershell pwsh cmd"
SEND="curl wget sendmail mail mailx mutt msmtp nc ncat netcat telnet ssh scp sftp ftp send-mailmessage invoke-webrequest iwr invoke-restmethod irm start-bitstransfer"

# 1. Recursive deletion anywhere in the workspace would take the protected folders with it (decision D3).
rec=0
has_verb rmdir rd && rec=1
has_verb rm remove-item ri del erase && { has_flag '-*r*' || has_flag '/s'; } && rec=1
has_verb find && has_word -delete -exec -execdir -ok && rec=1
has_verb git && has_word clean && rec=1
case "$full" in *rmtree*|*removedirs*) rec=1 ;; esac
[ "$rec" = 1 ] && block shell-rekursiv "Rekursives Löschen ist im Kundendienst-Ordner nicht erlaubt. Einzelne Dateien außerhalb von 01_Vorgaenge/ und Unternehmen/ dürfen gelöscht werden; Vorgänge merkt vorgang.py loeschen-markieren zum Löschen vor."

# 2. Deleting or moving with wildcards or variables: the target cannot be checked (decision D3).
# shellcheck disable=SC2086
if has_verb $DEL $MOVE; then
  case "$nq" in *'*'*|*'?'*|*'$'*)
    block shell-platzhalter "Löschen oder Verschieben mit Platzhaltern (*, ?) oder Variablen (\$) ist im Kundendienst-Ordner nicht erlaubt. Nenne jede Datei einzeln." ;;
  esac
fi

# 3. The protected folders: named in the command, or the shell already sits inside one.
named=0; incwd=0
case "$nq" in *01_vorgaenge*|*unternehmen*) named=1 ;; esac
lws=$(slk_lower "$ws"); lcwd=$(slk_lower "$cwd")/
case "$lcwd" in "$lws"/01_vorgaenge/*|"$lws"/unternehmen/*) named=1; incwd=1 ;; esac
schutz="01_Vorgaenge/ und Unternehmen/ sind geschützt: kein Löschen, Verschieben, Überschreiben oder Inline-Code per Shell. Vorgänge ändert vorgang.py (zum Löschen: vorgang.py loeschen-markieren), Unternehmen/ der System-Architekt."
if [ "$named" = 1 ]; then
  # shellcheck disable=SC2086
  has_verb $DEL $MOVE $COPY $INLINE && block shell-geschuetzt "$schutz"
  has_verb sed perl && has_flag '-i*' && block shell-geschuetzt "$schutz"
  has_verb git && has_word rm mv checkout restore reset stash && block shell-geschuetzt "$schutz"
  has_verb uv && has_word python python3 && has_word -c && block shell-geschuetzt "$schutz"
  printf '%s' "$nq" | grep -Eq '>[>|]?[[:space:]]*[^[:space:];|&<>]*(01_vorgaenge|unternehmen)' &&
    block shell-geschuetzt "$schutz"
  if [ "$incwd" = 1 ]; then
    printf '%s' "$nq" | sed -E 's/[0-9]*>>?[[:space:]]*(&[0-9-]?|\/dev\/null)//g' | grep -q '>' &&
      block shell-geschuetzt "$schutz"
  fi
fi

# 4. Only the human decides (spec §6): a sub-agent may not run vorgang.py entscheide.
if [ -n "$agent" ]; then
  case "$full" in *vorgang.py*)
    has_word entscheide && block entscheide-agent "Nur der Nutzer entscheidet. Ein Agent ruft vorgang.py entscheide nicht auf; schreib stattdessen eine Empfehlung mit vorgang.py eintrag --art empfehlung." ;;
  esac
fi

# 5. Nothing leaves the workspace through the shell (spec §8 rule 5, §10). git push stays allowed: the
#    user's own private repo is storage they chose in setup, not sending.
senden="Aus dem Kundendienst-Ordner wird nichts gesendet oder hochgeladen (curl, wget, Mail, Netzwerk aus Skripten). Leg einen Entwurf in 02_Postausgang/ ab; senden tut der Nutzer selbst."
# shellcheck disable=SC2086
has_verb $SEND && block shell-senden "$senden"
case "$full" in *smtplib*|*http.client*|*urllib*|*requests.*|*httpx*|*aiohttp*|*net.mail*|*webclient*|*httpclient*)
  block shell-senden "$senden" ;;
esac
set +f
