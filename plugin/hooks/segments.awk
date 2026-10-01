# Quote-aware splitter for the shell guard: prints one line per simple command,
#   verb TAB arg1 TAB arg2 ...        (args keep their spaces)
# verb is lower-cased, without directory and ".exe"; wrappers (sudo, xargs, env ...), VAR=x, numbers and
# options before the verb are skipped. Each arg starts with three flag digits: variable expansion
# (a $ outside '...', except $false/$true/$null), wildcard (* or ?, quoted or not), came-from-quotes.
# A "$(...)" or backtick gives its own line AND a "$sub" arg in the command around it; a command fed by
# xargs gets a "$xargs" arg (its targets are unknown). A shell wrapper (bash -c "...", powershell
# -Command "...", eval "...") gets its quoted args split once more. Backslash: an escape before a space,
# quote or shell operator, otherwise a Windows path separator ("/"). "#" at a word start is a comment.
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
    if (lvl == 0 && (verb in wrapper) && wq) pend[++np] = word
  }
  reset_word()
}
function flush(   line) {
  endword()
  if (verb != "") {
    line = verb args
    if (fed) line = line "\t100$xargs"
    print line
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
function backtick() { if (sp > 0 && kd[sp] == "b") { flush(); pop() } else push("b") }
function parse(text,   c, d) {
  T = text; N = length(T); sp = 0; inq = 0; reset_cmd(); reset_word()
  for (I = 1; I <= N; I++) {
    c = substr(T, I, 1)
    if (inq == 1) {
      if (c == "'") inq = 0
      else { if (c == "*" || c == "?") ww = 1; addch(c == "\\" ? "/" : c) }
    } else if (inq == 2) {
      if (c == "\"") inq = 0
      else if (c == "\\") {
        d = substr(T, I + 1, 1)
        if (d == "\"" || d == "$" || d == "`") { addch(d); I++ } else addch("/")
      } else if (c == "$") dollar()
      else if (c == "`") backtick()
      else { if (c == "*" || c == "?") ww = 1; addch(c) }
    } else if (c == "'") { inq = 1; inw = 1; wq = 1 }
    else if (c == "\"") { inq = 2; inw = 1; wq = 1 }
    else if (c == "\\") {
      d = substr(T, I + 1, 1)
      if (d == "\n") I++
      else if (d != "" && index(SPECIAL, d)) { addch(d); I++ } else addch("/")
    }
    else if (c == "#" && !inw) { while (I < N && substr(T, I + 1, 1) != "\n") I++ }
    else if (c == " " || c == "\t") endword()
    else if (c == "\n" || c == ";" || c == "&" || c == "|") flush()
    else if (c == "(") push("p")
    else if (c == ")") close_sub()
    else if (c == "$") dollar()
    else if (c == "`") backtick()
    else { if (c == "*" || c == "?") ww = 1; addch(c) }
  }
  flush()
  while (sp > 0) { if (kd[sp] == "p") sp--; else pop() }
  flush()
}
{ txt = (NR > 1 ? txt "\n" : "") $0 }
END {
  lvl = 0; np = 0; parse(txt)
  n0 = np; lvl = 1
  for (pk = 1; pk <= n0; pk++) parse(pend[pk])
}
