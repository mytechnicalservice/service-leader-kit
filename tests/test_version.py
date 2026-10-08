import json

from conftest import ROOT


def test_version_and_changelog_agree():
    version = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    assert version == "0.2.9"
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert text.startswith("# Änderungen\n") and f"\n## {version} – " in text
    assert text.index("\n## 0.2.9") < text.index("\n## 0.2.8") < text.index("\n## 0.2.7") < text.index("\n## 0.2.6") < text.index("\n## 0.2.5") < text.index("\n## 0.2.4") < text.index("\n## 0.2.3") < text.index("\n## 0.2.2") < text.index("\n## 0.2.1") < text.index("\n## 0.2.0") < text.index("\n## 0.1.0")
