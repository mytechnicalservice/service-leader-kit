import json

from conftest import ROOT


def test_marketplace_lists_plugin_with_matching_name():
    mp = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    pj = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert mp["name"] == "service-leader-kit"
    assert [p["name"] for p in mp["plugins"]] == [pj["name"]] == ["service-leader-kit"]
    assert mp["plugins"][0]["source"] == "./plugin"


def test_license_is_polyform_internal_use():
    assert "PolyForm Internal Use License 1.0.0" in (ROOT / "LICENSE").read_text(encoding="utf-8")
