# Sourced by pre-tool-use.sh for connector (mcp__…) tools inside a workspace (spec §8 rule 5, §11).
# Blocks every tool whose own name sends: Gmail send_message/reply/forward/send_draft, Outlook send tools.
# Creating drafts stays allowed.
name=$(slk_lower "${tool##*__}")
case "$name" in
  *send*|*reply*|*forward*)
    block connector-senden "Senden ist gesperrt ($tool). Erstelle einen Entwurf; senden tut der Nutzer selbst." ;;
esac
