#!/usr/bin/env python3
import argparse, json, hashlib, math
from datetime import datetime, timezone
from pathlib import Path

def ts(s): return datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def main():
    p=argparse.ArgumentParser(); p.add_argument("--episodes-dir",default="/app/episodes"); p.add_argument("--output",default="/app/features.json"); a=p.parse_args()
    result={"episodes":{}}
    for ep in sorted(Path(a.episodes_dir).iterdir()):
        if not ep.is_dir(): continue
        c=json.loads((ep/"config.json").read_text()); events=[]; seen=set(); late=0; max_t=float("-inf")
        for line in (ep/"events.jsonl").read_text().splitlines():
            e=json.loads(line)
            if e["event_id"] in seen: continue
            seen.add(e["event_id"]); t=ts(e["event_time"]); max_t=max(max_t,t); events.append(e)
        events.sort(key=lambda e:(ts(e["event_time"]),ts(e["ingest_time"]),e["source"],e["event_id"]))
        w={}; metric=[]; labels=[]; activities=[]
        for e in events:
            t=ts(e["event_time"])
            if t < max_t-c["allowed_lateness_seconds"]: late+=1
            if e["source"]=="metric":
                size=c["window_seconds"]; st=math.floor(t/size)*size; k=(e["key"],st); w.setdefault(k,[]).append(float(e["value"])); metric.append(e)
            elif e["source"]=="label": labels.append(e)
            elif e["source"]=="activity": activities.append(e)
        features=[]
        for (key,st), vals in w.items():
            en=st+c["window_seconds"]; mean=sum(vals)/len(vals); var=sum((x-mean)**2 for x in vals)/len(vals)
            features.append({"feature_id":f"metric:{key}:{int(st)}:{int(en)}","revision":1,"current":True,"key":key,"window_start":int(st),"window_end":int(en),"count":len(vals),"sum":sum(vals),"min":min(vals),"max":max(vals),"mean":mean,"population_variance":var})
        joins=[]
        for m in metric:
            for l in labels:
                d=ts(m["event_time"])-ts(l["event_time"])
                if m["key"]==l["key"] and abs(d)<=c["join_tolerance_seconds"]: joins.append({"metric_event_id":m["event_id"],"label_event_id":l["event_id"],"delta_seconds":d})
        sessions=[]
        for key in sorted({e["key"] for e in activities}):
            es=sorted([e for e in activities if e["key"]==key],key=lambda e:(ts(e["event_time"]),e["event_id"])); groups=[]
            for e in es:
                if not groups or ts(e["event_time"])-ts(groups[-1][-1]["event_time"])>c["session_gap_seconds"]: groups.append([e])
                else: groups[-1].append(e)
            for g in groups: sessions.append({"session_id":f"session:{key}:{int(ts(g[0]['event_time']))}","key":key,"start":g[0]["event_time"],"end":g[-1]["event_time"],"event_ids":[x["event_id"] for x in g],"tombstones":[]})
        ids=sorted(seen); chain="0"*64
        for x in ids+[x["feature_id"] for x in features]: chain=digest(chain+x)
        result["episodes"][ep.name]={"features":sorted(features,key=lambda x:x["feature_id"]),"sessions":sessions,"joins":sorted(joins,key=lambda x:(x["metric_event_id"],x["label_event_id"])),"counters":{"accepted_events":len(events),"duplicates":0,"late_events":late},"checkpoint_digest":chain}
    Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2))
if __name__=="__main__": main()
