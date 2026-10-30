#!/usr/bin/env python3
"""
Main CLI entrypoint for Multi-Interval N-1 Contingency SCED and Two-Settlement LMP Clearing.

Supports:
    python3 /app/gridop/settle.py
    python3 /app/gridop/settle.py --episodes-dir <DIR> --output <PATH>
    python3 /app/gridop/settle.py <DIR> <PATH>
"""

import argparse
import json
import os
import sys

# Ensure /app is on sys.path when invoked as python3 /app/gridop/settle.py
APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)

from gridop.telemetry import parse_scada_telemetry
from gridop.shift_factors import compute_shift_factors
from gridop.commitment import compute_commitment_status
from gridop.sced_solver import solve_multi_interval_sced
from gridop.settlement import compute_episode_settlement


def process_all_episodes(episodes_dir: str, output_path: str) -> None:
    if not os.path.isdir(episodes_dir):
        raise FileNotFoundError(f"Episodes directory not found: {episodes_dir}")

    episode_ids = sorted(
        d for d in os.listdir(episodes_dir)
        if os.path.isdir(os.path.join(episodes_dir, d))
        and os.path.exists(os.path.join(episodes_dir, d, "grid_topology.json"))
    )

    episodes_out = {}
    for ep_id in episode_ids:
        ep_dir = os.path.join(episodes_dir, ep_id)
        with open(os.path.join(ep_dir, "grid_topology.json"), "r") as f:
            topology = json.load(f)
        with open(os.path.join(ep_dir, "market_offers.json"), "r") as f:
            offers = json.load(f)
        bin_path = os.path.join(ep_dir, "scada_telemetry.bin")

        telemetry = parse_scada_telemetry(bin_path, topology, offers)
        shift_data = compute_shift_factors(topology)
        commitment_status = compute_commitment_status(topology, int(topology["num_intervals"]))
        sced_result = solve_multi_interval_sced(topology, offers, telemetry, shift_data, commitment_status)
        episodes_out[ep_id] = compute_episode_settlement(ep_id, topology, offers, telemetry, sced_result)

    ledger = {
        "schema_version": "1.0",
        "episodes": episodes_out,
    }
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(ledger, f, indent=2)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run multi-interval N-1 SCED and two-settlement LMP clearing.")
    parser.add_argument("pos_episodes_dir", nargs="?", default=None, help="Optional positional episodes directory")
    parser.add_argument("pos_output", nargs="?", default=None, help="Optional positional output JSON path")
    parser.add_argument("--episodes-dir", "-e", dest="opt_episodes_dir", default=None, help="Episodes directory")
    parser.add_argument("--output", "-o", dest="opt_output", default=None, help="Output settlement ledger JSON path")
    args = parser.parse_args(argv)

    episodes_dir = args.opt_episodes_dir or args.pos_episodes_dir or "/app/episodes"
    output_path = args.opt_output or args.pos_output or "/app/settlement_ledger.json"
    return episodes_dir, output_path


def main() -> int:
    episodes_dir, output_path = parse_args()
    process_all_episodes(episodes_dir, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
