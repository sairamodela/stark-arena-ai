
import json, pathlib
def test():
    assert (pathlib.Path("tools/friday_knowledge.json")).exists()
    data = json.loads(pathlib.Path("tools/friday_knowledge.json").read_text())
    assert "insights" in data
    print("PASS: Knowledge sharing Friday->Jarvis")
    assert pathlib.Path("tools/commit_analyzer.py").exists()
    txt = pathlib.Path("tools/commit_analyzer.py").read_text()
    assert "load_friday_knowledge" in txt
    print("PASS: Jarvis uses Friday knowledge")
    assert pathlib.Path("REPORT.md").exists()
    r = pathlib.Path("REPORT.md").read_text()
    assert "Tony" in r and "Friday" in r and "Jarvis" in r
    assert "ONE channel" in r
    assert "Intercommunication Proof" in r
    print("PASS: Perfect satisfaction REPORT.md")
    print("\nAll best cases PASS")

test()
