# Codex trims Unicode whitespace around hunk headers (Rust str::trim).
# Byte sequences are explicit because hooks run with LC_ALL=C on POSIX shells.
BEGIN {
  ws = "([[:space:]]|" sprintf("%c%c", 194, 133) "|" sprintf("%c%c", 194, 160)
  ws = ws "|" sprintf("%c%c%c", 225, 154, 128)
  ws = ws "|" sprintf("%c%c", 226, 128) "[" sprintf("%c-%c", 128, 138) "]"
  ws = ws "|" sprintf("%c%c", 226, 128) "[" sprintf("%c%c%c", 168, 169, 175) "]"
  ws = ws "|" sprintf("%c%c%c", 226, 129, 159) "|" sprintf("%c%c%c", 227, 128, 128) ")"
}
{
  header = $0
  sub("^" ws "+", "", header)
  sub(ws "+$", "", header)
  if (header ~ /^\*\*\* /) print header
  else print $0
}
