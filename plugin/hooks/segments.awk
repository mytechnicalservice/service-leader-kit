# Quote-aware splitter for the shell guard: prints one line per simple command,
#   verb TAB arg1 TAB arg2 ...        (args keep their spaces)
# verb is lower-cased, without directory and ".exe"; wrappers (sudo, xargs, env ...), VAR=x, numbers and
# options before the verb are skipped. Each arg starts with three flag digits: variable expansion
# (a $ outside '...', except $false/$true/$null), wildcard (* or ?, quoted or not), came-from-quotes.
# A "$(...)" or backtick gives its own line AND a "$sub" arg in the command around it; a command fed by
# xargs gets a "$xargs" arg (its targets are unknown). A shell wrapper (bash -c "...", powershell
# -Command "...", eval "...") gets its quoted args split once more. Backslash: an escape before a space,
# quote or shell operator, otherwise a Windows path separator ("/"). "#" at a word start is a comment.
# Heredoc bodies are data, not commands. If a text ends inside an open quote (an apostrophe in prose),
# it is split again with the quote state reset at every newline, so one bad line cannot hide later ones.
# With -v ps=1 (PowerShell, cmd) a backslash is always a path separator and a backtick escapes.
BEGIN {
  n = split("sudo command exec xargs env nohup time nice builtin then do else elif if while until ! { }", a, " ")
  for (i = 1; i <= n; i++) skip[a[i]] = 1
  n = split("bash sh zsh dash ksh eval powershell pwsh cmd", a, " ")
  for (i = 1; i <= n; i++) wrapper[a[i]] = 1
  SPECIAL = " \t'\"`;&|()<>"
}
function reset_cmd() { verb = ""; args = ""; fed = 0 }
function reset_word() { word = ""; inw = 0; wv = 0; ww = 0; wq = 0 }
function addch(ch) { if (ch == "\t" || ch == "\n") ch = " "; word = word ch; inw = 1 }
function endword(   lx, b) {
  if (!inw) return
  lx = tolower(word); b = lx
  sub(/^.*\//, "", b); sub(/\.exe$/, "", b)
  if (verb == "") {
    if (b == "" || lx ~ /^[a-z_][a-z0-9_]*=/ || word ~ /^-/ || word ~ /^[0-9]+$/ || (b in skip)) {
      if (b == "xargs") fed = 1
      reset_word(); return
    }
    verb = b
  } else {
    args = args "\t" wv ww wq word
    if (lvl == 0 && (verb in wrapper) && wq) { pend[++np] = word; pendps[np] = (verb == "powershell" || verb == "pwsh" || verb == "cmd") }
  }
  reset_word()
}
function flush(   line) {
  endword()
  if (verb != "") {
    line = verb args
    if (fed) line = line "\t100$xargs"
    out = out line "\n"
  }
  reset_cmd()
}
function push(k) {
  if (k == "p") flush()
  else {
    wv = 1; addch("$sub")
    s_verb[sp + 1] = verb; s_args[sp + 1] = args; s_fed[sp + 1] = fed; s_word[sp + 1] = word
    s_inw[sp + 1] = inw; s_wv[sp + 1] = wv; s_ww[sp + 1] = ww; s_wq[sp + 1] = wq; s_inq[sp + 1] = inq
    reset_cmd(); reset_word(); inq = 0
  }
  sp++; kd[sp] = k
}
function pop() {
  verb = s_verb[sp]; args = s_args[sp]; fed = s_fed[sp]; word = s_word[sp]
  inw = s_inw[sp]; wv = s_wv[sp]; ww = s_ww[sp]; wq = s_wq[sp]; inq = s_inq[sp]
  sp--
}
function close_sub() { flush(); if (sp > 0) { if (kd[sp] == "p") sp--; else pop() } }
function dollar(   rest) {
  if (substr(T, I + 1, 1) == "(") { push("s"); I++; return }
  rest = tolower(substr(T, I + 1, 5))
  if (rest !~ /^(false|true|null)/) wv = 1
  addch("$")
}
function heredoc_start(   j, ch, dl, dash) {
  endword()
  j = I + 2; dash = 0
  if (substr(T, j, 1) == "-") { dash = 1; j++ }
  while (substr(T, j, 1) == " " || substr(T, j, 1) == "\t") j++
  dl = ""
  while (j <= N) {
    ch = substr(T, j, 1)
    if (ch == "'" || ch == "\"" || ch == "\\") { j++; continue }
    if (index(" \t\n;&|()<>", ch)) break
    dl = dl ch; j++
  }
  hd_n++; hd_delim[hd_n] = dl; hd_dash[hd_n] = dash
  I = j - 1
}
# Called at the newline ending a line with heredocs: skips the body lines up to each delimiter line.
function skip_heredocs(   k, st, e, line) {
  for (k = 1; k <= hd_n; k++) {
    while (I < N) {
      st = I + 1
      e = index(substr(T, st), "\n")
      if (e == 0) { line = substr(T, st); I = N } else { line = substr(T, st, e - 1); I = st + e - 1 }
      if (hd_dash[k]) sub(/^[ \t]+/, "", line)
      sub(/\r$/, "", line)
      if (line == hd_delim[k]) break
    }
  }
  hd_n = 0
}
function backtick() { if (sp > 0 && kd[sp] == "b") { flush(); pop() } else push("b") }
function parse(text,   c, d) {
  T = text; N = length(T); sp = 0; inq = 0; hd_n = 0; reset_cmd(); reset_word()
  for (I = 1; I <= N; I++) {
    c = substr(T, I, 1)
    if (nlreset && inq && c == "\n") { inq = 0; flush(); if (hd_n > 0) skip_heredocs(); continue }
    if (inq == 1) {
      if (c == "'") inq = 0
      else { if (c == "*" || c == "?") ww = 1; addch(c == "\\" ? "/" : c) }
    } else if (inq == 2) {
      if (c == "\"") inq = 0
      else if (c == "\\") {
        d = substr(T, I + 1, 1)
        if (PS) addch("/")
        else if (d == "\"" || d == "$" || d == "`") { addch(d); I++ }
        else if (d == "\\") { addch("\\"); I++ }
        else addch("/")
      } else if (c == "$") dollar()
      else if (c == "`") { if (PS) { addch(substr(T, I + 1, 1)); I++ } else backtick() }
      else { if (c == "*" || c == "?") ww = 1; addch(c) }
    } else if (c == "'") { inq = 1; inw = 1; wq = 1 }
    else if (c == "\"") { inq = 2; inw = 1; wq = 1 }
    else if (c == "\\") {
      d = substr(T, I + 1, 1)
      if (PS) addch("/")
      else if (d == "\n") I++
      else if (d != "" && index(SPECIAL, d)) { addch(d); I++ } else addch("/")
    }
    else if (c == "#" && !inw) { while (I < N && substr(T, I + 1, 1) != "\n") I++ }
    else if (c == " " || c == "\t") endword()
    else if (c == "\n") { flush(); if (hd_n > 0) skip_heredocs() }
    else if (c == ";" || c == "&" || c == "|") flush()
    else if (c == "<" && !PS && substr(T, I + 1, 1) == "<" && substr(T, I + 2, 1) != "<") heredoc_start()
    else if (c == "(") push("p")
    else if (c == ")") close_sub()
    else if (c == "$") dollar()
    else if (c == "`") { if (PS) { addch(substr(T, I + 1, 1)); I++ } else backtick() }
    else { if (c == "*" || c == "?") ww = 1; addch(c) }
  }
  opened = (inq != 0)
  flush()
  while (sp > 0) { if (kd[sp] == "p") sp--; else pop() }
  flush()
}
function run(text, psm,   np0) {
  PS = psm; np0 = np
  out = ""; nlreset = 0; parse(text)
  if (opened) { out = ""; np = np0; nlreset = 1; parse(text); nlreset = 0 }
  all = all out
}
{ txt = (NR > 1 ? txt "\n" : "") $0 }
END {
  lvl = 0; np = 0; run(txt, ps + 0)
  n0 = np; lvl = 1
  for (pk = 1; pk <= n0; pk++) run(pend[pk], pendps[pk])
  printf "%s", all
}
