# Prints the value of the first JSON key named `want` (awk -v want=KEY -f json.awk < payload).
# Strings are unescaped (\n stays a line break); other values (true, 12) print as written.
# Exit 1 if the key is absent. Escaped quotes are hidden first, so a key-like text inside a
# string value ("\"tool_name\": ...") can never match: only real keys have unescaped quotes.
{ s = s $0 " " }
END {
  gsub(/\\\\/, "\001", s)
  gsub(/\\"/, "\002", s)
  if (!match(s, "\"" want "\"[ \t]*:[ \t]*")) exit 1
  rest = substr(s, RSTART + RLENGTH)
  if (substr(rest, 1, 1) == "\"") {
    rest = substr(rest, 2)
    v = substr(rest, 1, index(rest, "\"") - 1)
    gsub(/\\n/, "\n", v); gsub(/\\[rt]/, " ", v); gsub(/\\\//, "/", v)
    gsub(/\002/, "\"", v); gsub(/\001/, "\\", v)
    print v
  } else {
    match(rest, /^[^,} \t\]]*/)
    print substr(rest, 1, RLENGTH)
  }
}
