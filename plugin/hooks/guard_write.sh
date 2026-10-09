# Sourced by pre-tool-use.sh for Write/Edit/MultiEdit/NotebookEdit.
# Case files change only through vorgang.py (whole-file, validated, decision fields guarded; decision D1);
# Unternehmen/ is written only by the system architect agent (spec §11, §12.3). Path-based, so it also
# holds when the user opened another folder: some folder containing the path must be a workspace.
# The path is normalised first (relative, "..", backslashes) and every folder occurrence is tried.
if [ "$tool" != apply_patch ]; then
  path=$(slk_field "$payload" file_path)
  [ -n "$path" ] || path=$(slk_field "$payload" notebook_path)
fi
slk_company_denied=0
if [ "$SLK_CODEX" = 1 ]; then
  [ "$agent" != "system-architekt" ] && slk_company_denied=1
else
  [ "$agent" != "service-leader-kit:system-architekt" ] && slk_company_denied=1
fi
np=$(slk_norm_path "$path" "$cwd")
lc=$(slk_lower "$np")
case "$lc" in
  */01_vorgaenge/*)
    if root=$(slk_ws_for "$np" 01_vorgaenge); then
      ws=${ws:-$root}
      block write-vorgang "Dateien in 01_Vorgaenge/ ändert nur das Skript vorgang.py (neu, eintrag, setze, entscheide, schliesse, loeschen-markieren). Ist eine Vorgangsdatei beschädigt, bitte den Nutzer, sie in VS Code selbst zu korrigieren."
    fi ;;
esac
case "$lc" in
  */unternehmen/*)
    if [ "$slk_company_denied" = 1 ] && root=$(slk_ws_for "$np" unternehmen); then
      ws=${ws:-$root}
      block write-unternehmen "Dateien in Unternehmen/ ändert nur der System-Architekt (Agent service-leader-kit:system-architekt). Gib die Änderung an ihn weiter oder bitte den Nutzer, sie selbst vorzunehmen."
    fi ;;
esac
