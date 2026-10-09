# Prints the value of the first JSON key named `want` (awk -v want=KEY -f json.awk < payload).
# Strings are unescaped (\n stays a line break); other values (true, 12) print as written.
# Exit 1 if the key is absent. Escaped quotes are hidden first, so a key-like text inside a
# string value ("\"tool_name\": ...") can never match: only real keys have unescaped quotes.
function hex4(h,    i,n) {
  n = 0
  for (i = 1; i <= 4; i++) n = n * 16 + index("0123456789abcdef", tolower(substr(h, i, 1))) - 1
  return n
}
function utf8(n) {
  if (n < 128) return sprintf("%c", n)
  if (n < 2048) return sprintf("%c%c", 192 + int(n / 64), 128 + n % 64)
  if (n < 65536) return sprintf("%c%c%c", 224 + int(n / 4096), 128 + int(n / 64) % 64, 128 + n % 64)
  return sprintf("%c%c%c%c", 240 + int(n / 262144), 128 + int(n / 4096) % 64, 128 + int(n / 64) % 64, 128 + n % 64)
}
function unicode(v,    out,h,n,next6,low) {
  out = ""
  while (match(v, /\\u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]/)) {
    out = out substr(v, 1, RSTART - 1)
    h = substr(v, RSTART + 2, 4); n = hex4(h)
    v = substr(v, RSTART + 6)
    if (n >= 55296 && n <= 56319 && v ~ /^\\u[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]/) {
      low = hex4(substr(v, 3, 4))
      if (low >= 56320 && low <= 57343) { n = 65536 + (n - 55296) * 1024 + low - 56320; v = substr(v, 7) }
    }
    out = out utf8(n)
  }
  return out v
}
{ s = s $0 " " }
END {
  gsub(/\\\\/, "\001", s)
  gsub(/\\"/, "\002", s)
  if (top) {
    # Blank nested content while retaining root keys and their scalar values.
    depth = 0; quoted = 0; root = ""
    for (i = 1; i <= length(s); i++) {
      c = substr(s, i, 1)
      if (c == "\"") quoted = !quoted
      if (!quoted && (c == "{" || c == "[")) depth++
      if (depth <= 1) root = root c
      else root = root " "
      if (!quoted && (c == "}" || c == "]")) depth--
    }
    s = root
  }
  if (!match(s, "\"" want "\"[ \t]*:[ \t]*")) exit 1
  rest = substr(s, RSTART + RLENGTH)
  if (substr(rest, 1, 1) == "\"") {
    rest = substr(rest, 2)
    v = substr(rest, 1, index(rest, "\"") - 1)
    v = unicode(v)
    gsub(/\\n/, "\n", v); gsub(/\\[rt]/, " ", v); gsub(/\\\//, "/", v)
    gsub(/\002/, "\"", v); gsub(/\001/, "\\", v)
    print v
  } else {
    match(rest, /^[^,} \t\]]*/)
    print substr(rest, 1, RLENGTH)
  }
}
