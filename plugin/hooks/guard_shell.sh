# Sourced by pre-tool-use.sh for Bash/PowerShell inside a workspace (spec §11, §10 alternative routes).
# Matching is on command words and flags, never on the whole payload (probe lessons, spec §11).
# Known limit: deliberate obfuscation (building a path from pieces, encoded commands) is not caught;
# the rules stop accidental and injected destruction or sending, not a determined human.
set -f
cmd=$(slk_field "$payload" command)
full=$(slk_lower "$(slk_slashes "$cmd")")                                  # everything, quotes kept
bare=$(printf '%s\n' "$full" | sed -e 's/"[^"]*"/ /g' -e "s/'[^']*'/ /g")  # quoted text removed
nq=$(printf '%s' "$full" | tr -d "\"'")                                    # quote marks removed, text kept
# One line per simple command, split quote-aware (segments.awk): "verb TAB arg TAB arg …", each arg led
# by three flag digits (variable, wildcard, quoted). Wrapped commands (bash -c "…") are split as well.
_slk_ps=0; [ "$tool" = PowerShell ] && _slk_ps=1
segs=$(printf '%s\n' "$cmd" | awk -v ps="$_slk_ps" -f "$SLK_HOOKS/segments.awk")
verbs=$(printf '%s\n' "$segs" | awk -F '\t' '{ printf " %s", $1 } END { print " " }')
words=" $(printf '%s' "$bare" | tr '\n\t' '  ') "

has_verb() { for v in "$@"; do case "$verbs" in *" $v "*) return 0 ;; esac; done; return 1; }
has_word() { for v in "$@"; do case "$words" in *" $v "*) return 0 ;; esac; done; return 1; }
has_flag() { for t in $words; do case "$t" in $1) return 0 ;; esac; done; return 1; }
in_list() { _slk_x=$1; for _slk_i in $2; do [ "$_slk_i" = "$_slk_x" ] && return 0; done; return 1; }

WRAP="bash sh zsh dash ksh eval powershell pwsh cmd"
# A wrapped command may carry flags in its quoted text (sed -i, git rm …): check those words as well.
# shellcheck disable=SC2086
has_verb $WRAP && words="$words$(printf '%s' "$nq" | tr '\n\t' '  ') "

DEL="rm rmdir unlink shred truncate remove-item ri del erase rd trash"
RMLIKE="rm trash remove-item ri del erase"
MOVE="mv move-item mi move ren rename-item rni"
COPY="cp copy copy-item cpi rsync ln install dd tee set-content sc out-file clear-content clc add-content ac"
INLINE="python python3 py node perl ruby osascript powershell pwsh cmd"
SEND="curl wget sendmail mail mailx mutt msmtp nc ncat netcat telnet ssh scp sftp ftp send-mailmessage invoke-webrequest iwr invoke-restmethod irm start-bitstransfer"

recmsg="Rekursives Löschen ist im Kundendienst-Ordner nicht erlaubt. Einzelne Dateien außerhalb von 01_Vorgaenge/ und Unternehmen/ dürfen gelöscht werden; Vorgänge merkt vorgang.py loeschen-markieren zum Löschen vor."
platzmsg="Löschen oder Verschieben mit Platzhaltern (*, ?), Variablen (\$), Befehlsersetzung oder xargs ist im Kundendienst-Ordner nicht erlaubt. Nenne jede Datei einzeln."
gitmsg="Git-Befehle, die Änderungen verwerfen (restore, checkout ., reset --hard, stash, clean), sind im Kundendienst-Ordner nicht erlaubt. Ältere Stände holt der Nutzer selbst zurück."

# Rules 1 and 2 look at one simple command at a time: its own verb and its own arguments. Args arrive as
# "<variable><wildcard><quoted>text"; flags are compared lower-cased. $1 = verb, then the args.
seg_delete_rules() {
  _slk_v=$1; shift
  _slk_rec=0; _slk_ph=0
  case "$_slk_v" in rmdir|rd) _slk_rec=1 ;; esac
  for _slk_a in "$@"; do
    _slk_f=${_slk_a%"${_slk_a#???}"}; _slk_t=${_slk_a#???}
    case "$_slk_f" in 1??|?1?) _slk_ph=1 ;; esac
    in_list "$_slk_v" "$RMLIKE" || continue
    _slk_l=$(slk_lower "$_slk_t")
    case "$_slk_v" in
      rm|trash) printf '%s' "$_slk_l" | grep -Eq '^-[dfiprvx]*r[dfiprvx]*$|^--recursive$|^-rec' && _slk_rec=1 ;;
      *) case "$_slk_l" in -r|-re*|/s) _slk_rec=1 ;; esac ;;
    esac
    # A directory named as the target counts as recursive (trash, rm -d, Remove-Item without -Recurse).
    case "$_slk_f$_slk_l" in ???-*|???/?|1??*|?1?*) ;; *)
      [ -d "$(slk_norm_path "$_slk_t" "$cwd")" ] && _slk_rec=1 ;;
    esac
  done
  [ "$_slk_rec" = 1 ] && block shell-rekursiv "$recmsg"
  [ "$_slk_ph" = 1 ] && block shell-platzhalter "$platzmsg"
}

# find: -delete, or -exec/-execdir/-ok running a delete, move or truncate command.
seg_find_rules() {
  _slk_exec=0
  for _slk_a in "$@"; do
    _slk_l=$(slk_lower "${_slk_a#???}")
    if [ "$_slk_exec" = 1 ]; then
      _slk_l=${_slk_l##*/}; _slk_l=${_slk_l%.exe}
      in_list "$_slk_l" "$DEL $MOVE" && block shell-rekursiv "$recmsg"
      _slk_exec=0
    fi
    case "$_slk_l" in -delete) block shell-rekursiv "$recmsg" ;; -exec|-execdir|-ok|-okdir) _slk_exec=1 ;; esac
  done
}

# git: the subcommand comes after "-C <path>", "-c <k=v>" and other leading options.
seg_git_rules() {
  _slk_sub=""; _slk_rest=" "
  while [ $# -gt 0 ]; do
    _slk_l=$(slk_lower "${1#???}")
    if [ -n "$_slk_sub" ]; then _slk_rest="$_slk_rest$_slk_l "
    else case "$_slk_l" in -c) shift ;; -*) ;; *) _slk_sub=$_slk_l ;; esac
    fi
    shift
  done
  case "$_slk_sub" in
    restore|clean) block shell-git-verwerfen "$gitmsg" ;;
    checkout) case "$_slk_rest" in *" . "*|*" -- "*|*" -f "*|*" --force "*) block shell-git-verwerfen "$gitmsg" ;; esac ;;
    switch) case "$_slk_rest" in *" --discard-changes "*|*" -f "*|*" --force "*) block shell-git-verwerfen "$gitmsg" ;; esac ;;
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
    IFS='	'
    # shellcheck disable=SC2086
    set -- $_slk_line
    IFS=$_slk_oifs
    _slk_vb=$1; shift
    if [ "$_slk_mode" = git ]; then
      [ "$_slk_vb" = git ] && seg_git_rules "$@"
    elif [ "$_slk_vb" = find ]; then
      seg_find_rules "$@"
    elif in_list "$_slk_vb" "$DEL $MOVE"; then
      seg_delete_rules "$_slk_vb" "$@"
    fi
    IFS='
'
  done
  IFS=$_slk_oifs
}

# 1+2. Recursive deletion anywhere in the workspace would take the protected folders with it (decision D3);
# deleting or moving with wildcards, variables or substitutions cannot be checked. Both per command.
check_segs del
# Inline code that destroys without naming a folder: only where code can run (python -c, node -e, bash -c …).
# shellcheck disable=SC2086
if has_verb $INLINE $WRAP || { has_verb uv && has_word python python3 py node; }; then
  for _slk_p in 'rm -rf' 'rm -r ' 'rm -fr'; do
    case " $full" in *[!a-z0-9_.-]"$_slk_p"*) block shell-rekursiv "$recmsg" ;; esac
  done
  case "$full" in *rmtree*|*removedirs*|*rmsync*) block shell-rekursiv "$recmsg" ;; esac
  case "$full" in *"unlink("*) case "$full" in *rglob*|*"glob("*) block shell-rekursiv "$recmsg" ;; esac ;; esac
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
