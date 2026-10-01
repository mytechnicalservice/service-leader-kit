# Prints the command words of a shell line (lower-cased, quoted text already removed):
# the first word of every simple command, with wrappers (sudo, xargs, env …), variable
# assignments and directories skipped, and ".exe" dropped. Output: " w1 w2 … ".
# With -v seg=1 each simple command is printed on its own line as "verb arg1 arg2 …" (verb lower-cased,
# arguments as written) so rules can look at one command's own arguments only.
# With -v inner=1 (used on the text inside quotes), shells that run a quoted command
# (bash -c "…", powershell -Command "…", cmd /c "…", eval "…") are skipped too, so the
# command they wrap becomes the command word.
BEGIN {
  wrap = " sudo command exec xargs env nohup time nice builtin then do else elif if while until ! & "
  if (inner) wrap = wrap "bash sh zsh dash ksh eval powershell pwsh cmd "
}
{
  line = $0
  gsub(/&&|\|\||[;|&(){}`]|\$\(/, "\n", line)
  n = split(line, sg, "\n")
  for (i = 1; i <= n; i++) {
    m = split(sg[i], w, /[ \t]+/)
    for (j = 1; j <= m; j++) {
      x = w[j]; lx = tolower(x)
      if (x == "" || lx ~ /^[a-z_][a-z0-9_]*=/ || x ~ /^-/ || x ~ /^[0-9]+$/ || (inner && lx ~ /^\/[a-z]$/)) continue
      sub(/^.*\//, "", x); sub(/\.exe$/, "", x); x = tolower(x)
      if (index(wrap, " " x " ")) continue
      if (seg) {
        line2 = x
        for (k = j + 1; k <= m; k++) if (w[k] != "") line2 = line2 " " w[k]
        print line2
      } else out = out " " x
      break
    }
  }
}
END { if (!seg) print out " " }
