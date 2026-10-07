import eval_bericht

CASE = """schema_version: "1.1"
name: {name}
tags: ["skill:x", sauber{extra}]
graders:
  - name: datei
    type: file_exists
    path: "03_Berichte/*.docx"
  - name: keine-datei
    type: file_exists
    path: "03_Berichte/*.pptx"
    exists: false
  - name: pruefer
    type: tool_used
    tool: Agent
    input_match: "finanzen"
  - name: antwort
    type: llm
    criteria: x
"""


def faelle(tmp_path):
    for name, extra in (("a-sauber", ""), ("b-sauber", ", workflow"), ("c-sauber", ", routine")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "case.yaml").write_text(CASE.format(name=name, extra=extra), encoding="utf-8")
    return tmp_path


def lauf(name, rot, fehler=None):
    graders = [{"name": n, "passed": n not in rot} for n in ("datei", "keine-datei", "pruefer", "antwort")]
    return {"name": name, "arms": {"with": [{"score": 1 - len(rot) / 4, "passed": not rot, "costUsd": 0.5,
                                             "error": fehler, "graders": graders}]}}


def test_report_lists_scores_failing_graders_d7_and_agent_signals(tmp_path):
    ergebnis = {"costUsd": 12.5, "partial": True,
                "cases": [lauf("a-sauber", []), lauf("b-sauber", ["datei", "pruefer", "keine-datei"])]}
    b = eval_bericht.auswerten(ergebnis, faelle(tmp_path))
    assert (b["gesamt"], b["bestanden"], b["nicht_gelaufen"]) == (2, 1, ["c-sauber"])
    assert b["office_rot"] == ["b-sauber: datei"] and b["agent_rot"] == ["b-sauber: pruefer"]
    assert [f["art"] for f in b["faelle"]] == ["skill", "workflow"]
    text = eval_bericht.markdown(b)
    assert "Kosten 12,50 USD" in text and "Kostengrenze" in text
    assert "| b-sauber | workflow | 0,25 | datei, keine-datei, pruefer | – |" in text
    assert "Nicht gelaufen: c-sauber" in text
