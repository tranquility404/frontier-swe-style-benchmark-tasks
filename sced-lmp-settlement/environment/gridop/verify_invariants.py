#!/usr/bin/env python3
"""
Local structural and physical invariant checker for /app/settlement_ledger.json.
Usage:
    python3 -m gridop.verify_invariants [/app/settlement_ledger.json] [--episodes-dir /app/episodes]
"""

import argparse
import json
import os
import sys
from gridop.schemas import validate_ledger_schema


def check_physical_invariants(ledger_path: str, episodes_dir: str) -> int:
    if not os.path.exists(ledger_path):
        print(f"[FAIL] Ledger file not found: {ledger_path}", file=sys.stderr)
        return 1

    with open(ledger_path, "r") as f:
        ledger = json.load(f)

    ep_ids = sorted(
        d for d in os.listdir(episodes_dir)
        if os.path.isdir(os.path.join(episodes_dir, d))
        and os.path.exists(os.path.join(episodes_dir, d, "grid_topology.json"))
    )
    schema_errors = validate_ledger_schema(ledger, ep_ids)
    if schema_errors:
        for err in schema_errors:
            print(f"[SCHEMA ERROR] {err}", file=sys.stderr)
        return 1

    episodes = ledger["episodes"]
    for ep_id in ep_ids:
        ep = episodes[ep_id]
        ep_dir = os.path.join(episodes_dir, ep_id)
        with open(os.path.join(ep_dir, "grid_topology.json"), "r") as f:
            topo = json.load(f)

        T = ep["num_intervals"]
        r_req = float(topo.get("min_spinning_reserve_mw", 0.0))
        inj = ep["dispatch"]["net_nodal_injection_mw"]
        spin_gen = ep["dispatch"]["spinning_reserve_mw"]
        spin_stor = ep["dispatch"]["storage_spin_mw"]
        scarcity = ep["dispatch"]["reserve_scarcity_mw"]
        thermal = ep["dispatch"]["thermal_mw"]
        u_status = ep["dispatch"]["commitment_status"]
        st_dis = ep["dispatch"]["storage_discharge_mw"]
        st_soc = ep["dispatch"]["storage_soc_mwh"]

        for t in range(T):
            s_inj = sum(inj[b][t] for b in inj)
            if abs(s_inj) > 1e-3:
                print(f"[INVARIANT ERROR] {ep_id} interval {t}: net nodal injection sum = {s_inj:.6f} != 0", file=sys.stderr)
                return 1

            total_spin = sum(spin_gen[g][t] for g in spin_gen) + sum(spin_stor[s][t] for s in spin_stor) + scarcity[t]
            if total_spin < r_req - 1e-3:
                print(f"[INVARIANT ERROR] {ep_id} interval {t}: spinning reserve {total_spin:.4f} MW < requirement {r_req:.4f} MW", file=sys.stderr)
                return 1

            for g in topo["generators"]:
                gid = g["gen_id"]
                pmax = float(g["p_max_mw"])
                u_t = u_status[gid][t]
                if thermal[gid][t] + spin_gen[gid][t] > pmax * u_t + 1e-3:
                    print(f"[INVARIANT ERROR] {ep_id} {gid} interval {t}: generation + spin > P_max", file=sys.stderr)
                    return 1

            for s in topo.get("storage_units", []):
                sid = s["storage_id"]
                p_dis_max = float(s["p_dis_max_mw"])
                e_min = float(s["soc_min_mwh"])
                e_max = float(s["soc_max_mwh"])
                if st_dis[sid][t] + spin_stor[sid][t] > p_dis_max + 1e-3:
                    print(f"[INVARIANT ERROR] {ep_id} {sid} interval {t}: discharge + spin > P_dis_max", file=sys.stderr)
                    return 1
                if st_soc[sid][t] < e_min - 1e-3 or st_soc[sid][t] > e_max + 1e-3:
                    print(f"[INVARIANT ERROR] {ep_id} {sid} interval {t}: SoC out of bounds", file=sys.stderr)
                    return 1

        max_ratios = ep["dispatch"]["max_post_contingency_loading_ratio"]
        if any(r > 1.0001 for r in max_ratios):
            print(f"[INVARIANT ERROR] {ep_id}: post-contingency overload detected: max ratio = {max(max_ratios):.6f}", file=sys.stderr)
            return 1

    print(f"[OK] Validated schema, power-balance, spinning reserves, storage bounds, and thermal limits for {len(ep_ids)} episodes.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify basic ledger schema and physical invariants.")
    parser.add_argument("ledger_path", nargs="?", default="/app/settlement_ledger.json")
    parser.add_argument("--episodes-dir", default="/app/episodes")
    args = parser.parse_args()
    return check_physical_invariants(args.ledger_path, args.episodes_dir)


if __name__ == "__main__":
    sys.exit(main())
