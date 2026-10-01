# Prints the command words of a shell line (lower-cased, quoted text already removed):
# the first word of every simple command, with wrappers (sudo, xargs, env …), variable
# assignments and directories skipped, and ".exe" dropped. Output: " w1 w2 … ".
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
  n = split(line, seg, "\n")
  for (i = 1; i <= n; i++) {
    m = split(seg[i], w, /[ \t]+/)
    for (j = 1; j <= m; j++) {
      x = w[j]
      if (x == "" || x ~ /^[a-z_][a-z0-9_]*=/ || x ~ /^-/ || x ~ /^[0-9]+$/ || (inner && x ~ /^\/[a-z]$/)) continue
      sub(/^.*\//, "", x); sub(/\.exe$/, "", x)
      if (index(wrap, " " x " ")) continue
      out = out " " x
      break
    }
  }
}
END { print out " " }
