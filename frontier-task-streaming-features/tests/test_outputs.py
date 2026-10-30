import json
import subprocess
from pathlib import Path
def test_stream_contract():
    d=json.loads((Path("/app")/"features.json").read_text())
    assert set(d["episodes"])=={"public_late","public_sessions"}
    for e in d["episodes"].values():
        assert e["features"] and e["checkpoint_digest"] and len(e["checkpoint_digest"])==64
        assert all("count" in x and x["current"] for x in e["features"])
def test_lateness_and_join():
    d=json.loads((Path("/app")/"features.json").read_text())
    assert d["episodes"]["public_late"]["counters"]["late_events"]>=1
    assert d["episodes"]["public_late"]["joins"]
def test_sessions():
    d=json.loads((Path("/app")/"features.json").read_text())
    s=d["episodes"]["public_sessions"]["sessions"]
    assert len(s)==2 and s[0]["event_ids"]

def test_heldout_cli_contract():
    out="/tmp/heldout-features.json"
    subprocess.run(["python3", "/app/stream_engine.py", "--episodes-dir", "/tests/heldout_episodes", "--output", out], check=True)
    assert Path(out).exists()
