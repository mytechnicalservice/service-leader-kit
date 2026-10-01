# Sourced by pre-tool-use.sh for Write/Edit/MultiEdit/NotebookEdit.
# Case files change only through vorgang.py (whole-file, validated, decision fields guarded; decision D1);
# Unternehmen/ is written only by the system architect agent (spec §11, §12.3). Path-based, so it also
# holds when the user opened another folder: the folder that contains the path must be a workspace.
path=$(slk_field "$payload" file_path)
[ -n "$path" ] || path=$(slk_field "$payload" notebook_path)
lc=$(slk_lower "$(slk_slashes "$path")")
case "$lc" in
  01_vorgaenge/*|./01_vorgaenge/*|*/01_vorgaenge/*)
    if slk_is_ws "$(slk_root_of "$path" 01_vorgaenge "$cwd")"; then
      ws=${ws:-$(slk_root_of "$path" 01_vorgaenge "$cwd")}
      block write-vorgang "Dateien in 01_Vorgaenge/ ändert nur das Skript vorgang.py (neu, eintrag, setze, entscheide, schliesse, loeschen-markieren). Ist eine Vorgangsdatei beschädigt, bitte den Nutzer, sie in VS Code selbst zu korrigieren."
    fi ;;
  unternehmen/*|./unternehmen/*|*/unternehmen/*)
    if [ "$agent" != "service-leader-kit:system-architekt" ] && slk_is_ws "$(slk_root_of "$path" unternehmen "$cwd")"; then
      ws=${ws:-$(slk_root_of "$path" unternehmen "$cwd")}
      block write-unternehmen "Dateien in Unternehmen/ ändert nur der System-Architekt (Agent service-leader-kit:system-architekt). Gib die Änderung an ihn weiter oder bitte den Nutzer, sie selbst vorzunehmen."
    fi ;;
esac
