# All patch targets share the write guard; one denial blocks the entire tool call.
patch=$(slk_field "$payload" command | awk -f "$SLK_HOOKS/patch_headers.awk")
# Deletion or a move source stays forbidden in protected folders, even for the architect.
removed=$(printf '%s\n' "$patch" | awk '
  /^\*\*\* Delete File: / { print substr($0, 18) }
  /^\*\*\* Update File: / { src = substr($0, 18) }
  /^\*\*\* Move to: / { print src }
')
printf '%s\n' "$removed" | while IFS= read -r target; do
  [ -n "$target" ] || continue
  norm=$(slk_norm_path "$target" "$cwd")
  case "$(slk_lower "$norm")" in
    */unternehmen/*) slk_ws_for "$norm" unternehmen >/dev/null && exit 2 ;;
    */01_vorgaenge/*) slk_ws_for "$norm" 01_vorgaenge >/dev/null && exit 2 ;;
  esac
done
[ "$?" = 2 ] && block patch-entfernen "Geschützte Dateien werden nicht gelöscht oder verschoben. Nutze für Vorgänge vorgang.py; Unternehmensdateien bleiben erhalten."
paths=$(printf '%s\n' "$patch" | sed -n -e 's/^\*\*\* Add File: //p' -e 's/^\*\*\* Update File: //p' -e 's/^\*\*\* Delete File: //p' -e 's/^\*\*\* Move to: //p')
[ -n "$paths" ] || block patch-ungueltig "Die Datei-Ziele dieses Patches sind nicht prüfbar. Bitte einen vollständigen Patch mit Datei-Zielen verwenden."
_slk_patch_ifs=$IFS
IFS='
'
set -f
for path in $paths; do
  . "$SLK_HOOKS/guard_write.sh"
done
set +f
IFS=$_slk_patch_ifs
