# Sourced by pre-tool-use.sh for Bash/PowerShell inside a workspace (spec §11, §10 alternative routes).
# Matching is on command words and flags, never on the whole payload (probe lessons, spec §11).
# Known limit: deliberate obfuscation (building a path from pieces, encoded commands) is not caught;
# the rules stop accidental and injected destruction or sending, not a determined human.
set -f
cmd=$(slk_field "$payload" command)
ofull=$(slk_slashes "$cmd")                                                # as written, quotes kept
full=$(slk_lower "$ofull")
# Double-quoted text holding a $ becomes the token $q (so "$DATEI" still counts as a variable); all
# other quoted text is removed.
obare=$(printf '%s\n' "$ofull" | sed -e 's/"[^"]*\$[^"]*"/ $q /g' -e 's/"[^"]*"/ /g' -e "s/'[^']*'/ /g")
bare=$(slk_lower "$obare")
nq=$(printf '%s' "$full" | tr -d "\"'")                                    # quote marks removed, text kept
onq=$(printf '%s' "$ofull" | tr -d "\"'")
verbs=$(printf '%s\n' "$bare" | awk -f "$SLK_HOOKS/cmdwords.awk")
segs=$(printf '%s\n' "$obare" | awk -v seg=1 -f "$SLK_HOOKS/cmdwords.awk")  # one "verb args" line per command
words=" $(printf '%s' "$bare" | tr '\n\t' '  ') "

has_verb() { for v in "$@"; do case "$verbs" in *" $v "*) return 0 ;; esac; done; return 1; }
has_word() { for v in "$@"; do case "$words" in *" $v "*) return 0 ;; esac; done; return 1; }
has_flag() { for t in $words; do case "$t" in $1) return 0 ;; esac; done; return 1; }
in_list() { _slk_x=$1; for _slk_i in $2; do [ "$_slk_i" = "$_slk_x" ] && return 0; done; return 1; }

# A shell that runs a quoted command (bash -c "rm …", powershell -Command "…", eval "…") hides the real
# verbs in quotes: then the quoted text is checked as well. Only then, so quoted arguments of ordinary
# commands (vorgang.py --text "Kopie & rm") never count as commands. Heredocs need nothing extra: their
# lines are separate commands already (lesson from dcg, research 2026-10-01).
WRAP="bash sh zsh dash ksh eval powershell pwsh cmd"
# shellcheck disable=SC2086
if has_verb $WRAP; then
  verbs="$verbs$(printf '%s\n' "$nq" | awk -v inner=1 -f "$SLK_HOOKS/cmdwords.awk")"
  segs="$segs
$(printf '%s\n' "$onq" | awk -v seg=1 -v inner=1 -f "$SLK_HOOKS/cmdwords.awk")"
  words="$words$(printf '%s' "$nq" | tr '\n\t' '  ') "
fi

DEL="rm rmdir unlink shred truncate remove-item ri del erase rd trash"
RMLIKE="rm trash remove-item ri del erase"
MOVE="mv move-item mi move ren rename-item rni"
COPY="cp copy copy-item cpi rsync ln install dd tee set-content sc out-file clear-content clc add-content ac"
INLINE="python python3 py node perl ruby osascript powershell pwsh cmd"
SEND="curl wget sendmail mail mailx mutt msmtp nc ncat netcat telnet ssh scp sftp ftp send-mailmessage invoke-webrequest iwr invoke-restmethod irm start-bitstransfer"

recmsg="Rekursives Löschen ist im Kundendienst-Ordner nicht erlaubt. Einzelne Dateien außerhalb von 01_Vorgaenge/ und Unternehmen/ dürfen gelöscht werden; Vorgänge merkt vorgang.py loeschen-markieren zum Löschen vor."
platzmsg="Löschen oder Verschieben mit Platzhaltern (*, ?) oder Variablen (\$) ist im Kundendienst-Ordner nicht erlaubt. Nenne jede Datei einzeln."
gitmsg="Git-Befehle, die Änderungen verwerfen (restore, checkout ., reset --hard, stash, clean), sind im Kundendienst-Ordner nicht erlaubt. Ältere Stände holt der Nutzer selbst zurück."

# Rules 1 and 2 look at one simple command at a time: its own verb and its own arguments.
# $1 = verb, then its arguments (as written; flags are compared lower-cased).
seg_delete_rules() {
  _slk_v=$1; shift
  _slk_rec=0; _slk_ph=0
  case "$_slk_v" in rmdir|rd) _slk_rec=1 ;; esac
  for _slk_a in "$@"; do
    _slk_l=$(slk_lower "$_slk_a")
    case "$_slk_l" in *'*'*|*'?'*|*'$'*) _slk_ph=1 ;; esac
    in_list "$_slk_v" "$RMLIKE" || continue
    case "$_slk_v" in
      rm|trash) printf '%s' "$_slk_l" | grep -Eq '^-[dfivr]*r[dfivr]*$|^--recursive$|^-rec' && _slk_rec=1 ;;
      *) case "$_slk_l" in -r|-rec*|/s) _slk_rec=1 ;; esac ;;
    esac
    # A directory named as the target counts as recursive (trash, rm -d, Remove-Item without -Recurse).
    case "$_slk_l" in -*|/s|*'$'*|*'*'*|*'?'*) ;; *)
      [ -d "$(slk_norm_path "$_slk_a" "$cwd")" ] && _slk_rec=1 ;;
    esac
  done
  [ "$_slk_rec" = 1 ] && block shell-rekursiv "$recmsg"
  if [ "$_slk_ph" = 1 ] && { in_list "$_slk_v" "$DEL" || in_list "$_slk_v" "$MOVE"; }; then
    block shell-platzhalter "$platzmsg"
  fi
}

seg_find_rules() {
  _slk_exec=0
  for _slk_a in "$@"; do
    _slk_l=$(slk_lower "$_slk_a")
    case "$_slk_l" in -delete) block shell-rekursiv "$recmsg" ;; -exec|-execdir|-ok) _slk_exec=1 ;; esac
    if [ "$_slk_exec" = 1 ]; then
      case "$_slk_l" in rm|unlink|shred|trash) block shell-rekursiv "$recmsg" ;; esac
    fi
  done
}

# git: the subcommand comes after "-C <path>", "-c <k=v>" and other leading options.
seg_git_rules() {
  _slk_sub=""; _slk_rest=" "
  while [ $# -gt 0 ]; do
    if [ -n "$_slk_sub" ]; then _slk_rest="$_slk_rest$(slk_lower "$1") "
    else case "$1" in -c|-C) shift ;; -*) ;; *) _slk_sub=$(slk_lower "$1") ;; esac
    fi
    shift
  done
  case "$_slk_sub" in
    restore|clean) block shell-git-verwerfen "$gitmsg" ;;
    checkout) case "$_slk_rest" in *" . "*|*" -- "*) block shell-git-verwerfen "$gitmsg" ;; esac ;;
    reset) case "$_slk_rest" in *" --hard "*) block shell-git-verwerfen "$gitmsg" ;; esac ;;
    stash) case "$_slk_rest" in " list "*|" show "*) ;; *) block shell-git-verwerfen "$gitmsg" ;; esac ;;
  esac
}

# Runs the rules of mode $1 (del = delete/find rules, git = git rules) on every simple command in $segs.
check_segs() {
  _slk_mode=$1
  _slk_oifs=$IFS
  IFS='
'
  for _slk_line in $segs; do
    IFS=$_slk_oifs
    # shellcheck disable=SC2086
    set -- $_slk_line
    if [ $# -gt 0 ]; then
      _slk_vb=$1; shift
      if [ "$_slk_mode" = git ]; then
        [ "$_slk_vb" = git ] && seg_git_rules "$@"
      elif [ "$_slk_vb" = find ]; then
        seg_find_rules "$@"
      elif in_list "$_slk_vb" "$DEL $MOVE"; then
        seg_delete_rules "$_slk_vb" "$@"
      fi
    fi
    IFS='
'
  done
  IFS=$_slk_oifs
}

# 1+2. Recursive deletion anywhere in the workspace would take the protected folders with it (decision D3);
# deleting or moving with wildcards or variables cannot be checked. Both per command, never on the whole line.
check_segs del
# Inline code that destroys without naming a folder.
for _slk_p in 'rm -rf' 'rm -r ' 'rm -fr'; do
  case " $full" in *[!a-z0-9_.-]"$_slk_p"*) block shell-rekursiv "$recmsg" ;; esac
done
case "$full" in *rmtree*|*removedirs*|*rmsync*) block shell-rekursiv "$recmsg" ;; esac
case "$full" in *"unlink("*) case "$full" in *rglob*|*"glob("*) block shell-rekursiv "$recmsg" ;; esac ;; esac

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

# 3b. Git that throws away work, anywhere in the workspace.
check_segs git

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
