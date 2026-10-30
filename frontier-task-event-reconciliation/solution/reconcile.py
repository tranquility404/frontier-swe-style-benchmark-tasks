#!/usr/bin/env python3
import argparse, hashlib, hmac, json
from pathlib import Path

ZERO = "0" * 64
def compact(x): return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def signable(e): return {k:v for k,v in e.items() if k != "signature"}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--episodes-dir",default="/app/episodes"); ap.add_argument("--output",default="/app/reconciliation.json"); a=ap.parse_args()
    out={"episodes":{}}
    for ep in sorted(Path(a.episodes_dir).iterdir()):
        if not ep.is_dir(): continue
        meta=json.loads((ep/"accounts.json").read_text()); keys=json.loads((ep/"keys.json").read_text())
        raw=[json.loads(x) for x in (ep/"events.jsonl").read_text().splitlines() if x.strip()]
        by={}
        conflicts=0
        for e in raw:
            c=compact(e)
            if e["event_id"] in by:
                conflicts += c != compact(by[e["event_id"]])
                if c < compact(by[e["event_id"]]): by[e["event_id"]]=e
            else: by[e["event_id"]]=e
        accepted=[]; rejected=[]; balances={k:{"available_cents":0,"held_cents":0,"currency":v["currency"]} for k,v in meta.items()}; seen=set(); reversed_ids=set()
        for e in sorted(by.values(), key=lambda x:(x["occurred_at"],x["partition"],x["sequence"],x["event_id"])):
            reason=None; acct=e.get("account_id"); target=e.get("causation_id")
            key=keys.get(acct)
            if not key or not hmac.compare_digest(e.get("signature",""), hmac.new(key.encode(), compact(signable(e)).encode(), hashlib.sha256).hexdigest()): reason="invalid_signature"
            elif acct not in meta or e.get("currency") != meta[acct]["currency"] or int(e.get("amount_cents",0)) < 0: reason="invalid_schema"
            elif target and target not in seen: reason="missing_causation"
            elif target and target in reversed_ids: reason="already_reversed"
            else:
                amount=int(e["amount_cents"]); typ=e["event_type"]; b=balances[acct]; dest=None
                if typ=="credit": b["available_cents"]+=amount
                elif typ=="debit" and b["available_cents"]-amount < -meta[acct]["overdraft_limit_cents"]: reason="insufficient_funds"
                elif typ=="debit": b["available_cents"]-=amount
                elif typ=="hold" and b["available_cents"]<amount: reason="insufficient_funds"
                elif typ=="hold": b["available_cents"]-=amount; b["held_cents"]+=amount
                elif typ=="release" and b["held_cents"]<amount: reason="insufficient_held"
                elif typ=="release": b["held_cents"]-=amount; b["available_cents"]+=amount
                elif typ=="capture" and b["held_cents"]<amount: reason="insufficient_held"
                elif typ=="capture": b["held_cents"]-=amount
                elif typ=="refund": b["available_cents"]+=amount; reversed_ids.add(target)
                elif typ=="transfer":
                    dest=e.get("payload",{}).get("destination_account_id"); db=balances.get(dest)
                    if not db or b["available_cents"]-amount < -meta[acct]["overdraft_limit_cents"]: reason="transfer_invalid"
                    else: b["available_cents"]-=amount; db["available_cents"]+=amount
                else: reason="unknown_event_type"
            if reason: rejected.append({"event_id":e.get("event_id"),"reason":reason})
            else: accepted.append(e); seen.add(e["event_id"])
        hashes=[digest(compact(e)) for e in accepted]; chain=ZERO
        for h in hashes: chain=digest(chain+h)
        leaves=[digest("leaf:"+h) for h in hashes]; proofs={}
        level=leaves[:]
        for i in range(len(leaves)): proofs[accepted[i]["event_id"]]=[]
        merkle_root=ZERO if not level else level[0]
        while len(level)>1:
            nxt=[]
            for i in range(0,len(level),2):
                l=level[i]; r=level[i+1] if i+1<len(level) else l
                if i+1<len(level): 
                    if i < len(level): pass
                nxt.append(digest("node:"+l+r))
            level=nxt
            merkle_root=nxt[0]
        conservation=sum(v["available_cents"]+v["held_cents"] for v in balances.values())
        out["episodes"][ep.name]={"balances":balances,"accepted_event_ids":[e["event_id"] for e in accepted],"rejected_events":rejected,"counters":{"input_events":len(raw),"accepted":len(accepted),"rejected":len(rejected),"duplicate_conflicts":conflicts},"conservation":{"total_cents":conservation},"chain_head":chain,"merkle_root":merkle_root,"proofs":proofs}
    Path(a.output).write_text(json.dumps(out,sort_keys=True,indent=2))
if __name__=="__main__": main()
