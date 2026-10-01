# Validates Unternehmen/.kit-config against vorlagen/kit-config.schema (spec §7.1).
# Usage: awk -v schema=<schema file> -f kit_config.awk <.kit-config>
# Prints the settings as key=value lines in schema order and exits 0, or prints nothing and exits 1.
# Tolerates a UTF-8 BOM, CRLF line ends (in the settings and the schema), blank lines, # comments and spaces around keys and values;
# rejects unknown, duplicate, missing or invalid keys. The first setting must be schema=…
BEGIN {
  while ((getline line < schema) > 0) {
    sub(/\r$/, "", line)
    if (line ~ /^[ \t]*(#|$)/) continue
    k = substr(line, 1, index(line, "=") - 1)
    re[k] = substr(line, index(line, "=") + 1)
    order[++nk] = k
  }
  close(schema)
  if (nk == 0) bad = 1
}
{
  sub(/\r$/, "")
  if (NR == 1) sub(/^\357\273\277/, "")
  if ($0 ~ /^[ \t]*(#|$)/) next
  eq = index($0, "=")
  if (eq == 0) { bad = 1; next }
  k = substr($0, 1, eq - 1); v = substr($0, eq + 1)
  gsub(/^[ \t]+|[ \t]+$/, "", k); gsub(/^[ \t]+|[ \t]+$/, "", v)
  if (!(k in re) || (k in val) || v !~ ("^(" re[k] ")$")) { bad = 1; next }
  if (++seen == 1 && k != "schema") bad = 1
  val[k] = v
}
END {
  for (i = 1; i <= nk; i++) if (!(order[i] in val)) bad = 1
  if (bad) exit 1
  for (i = 1; i <= nk; i++) print order[i] "=" val[order[i]]
}
