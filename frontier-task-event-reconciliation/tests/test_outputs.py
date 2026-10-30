import json, os
from pathlib import Path
import subprocess
import pytest

APP="/app"
def test_contract_and_nonempty_output():
    p=Path(APP)/"reconciliation.json"
    assert p.exists()
    d=json.loads(p.read_text())
    assert set(d["episodes"]) == {"public_basic","public_reorder"}
    for x in d["episodes"].values():
        assert x["accepted_event_ids"]
        assert len(x["chain_head"])==64 and len(x["merkle_root"])==64
        assert x["counters"]["accepted"] > 0
def test_rejections_are_explicit():
    d=json.loads((Path(APP)/"reconciliation.json").read_text())
    assert any(x["reason"]=="invalid_signature" for e in d["episodes"].values() for x in e["rejected_events"])
    assert all("reason" in x and "event_id" in x for e in d["episodes"].values() for x in e["rejected_events"])

def test_heldout_cli_contract():
    out="/tmp/heldout-reconciliation.json"
    subprocess.run(["python3", "/app/reconcile.py", "--episodes-dir", "/tests/heldout_episodes", "--output", out], check=True)
    assert Path(out).exists()
