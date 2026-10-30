"""
Schema definitions and structural validators for /app/settlement_ledger.json.
"""

from typing import Dict, Any, List


REQUIRED_EPISODE_SECTIONS = (
    "episode_id",
    "num_intervals",
    "interval_hours",
    "telemetry_summary",
    "topology_diagnostics",
    "dispatch",
    "prices",
    "settlement",
)

REQUIRED_TELEMETRY_KEYS = (
    "valid_frames_used",
    "corrupt_or_spike_dropped",
    "duplicate_seq_dropped",
    "stale_or_low_quality_imputed",
    "reconstructed_bus_load_mw",
)

REQUIRED_TOPOLOGY_DIAG_KEYS = (
    "bridge_line_ids",
    "active_contingency_pairs",
)

REQUIRED_DISPATCH_KEYS = (
    "thermal_mw",
    "generator_block_dispatch_mw",
    "spinning_reserve_mw",
    "commitment_status",
    "storage_charge_mw",
    "storage_discharge_mw",
    "storage_spin_mw",
    "storage_soc_mwh",
    "reserve_scarcity_mw",
    "net_nodal_injection_mw",
    "base_line_flow_mw",
    "max_post_contingency_loading_ratio",
    "total_variable_dispatch_cost_usd",
)

REQUIRED_PRICES_KEYS = (
    "system_energy_lambda_usd_per_mwh",
    "reserve_mcp_usd_per_mwh",
    "nodal_lmp_usd_per_mwh",
    "nodal_congestion_lmp_usd_per_mwh",
)

REQUIRED_SETTLEMENT_KEYS = (
    "interval_congestion_rent_usd",
    "interval_pst_congestion_rent_usd",
    "total_congestion_rent_usd",
    "generator_settlement",
    "storage_settlement",
    "lse_settlement",
    "total_make_whole_uplift_usd",
)

REQUIRED_GEN_SETTLEMENT_KEYS = (
    "da_energy_revenue_usd",
    "rt_imbalance_revenue_usd",
    "da_reserve_revenue_usd",
    "rt_reserve_revenue_usd",
    "rt_as_dispatched_energy_value_usd",
    "total_three_part_cost_usd",
    "make_whole_uplift_usd",
    "total_net_settlement_usd",
)

REQUIRED_STORAGE_SETTLEMENT_KEYS = (
    "da_energy_revenue_usd",
    "rt_imbalance_revenue_usd",
    "da_reserve_revenue_usd",
    "rt_reserve_revenue_usd",
    "wear_cost_usd",
    "total_net_settlement_usd",
)

REQUIRED_LSE_SETTLEMENT_KEYS = (
    "total_rt_load_mwh",
    "load_share_ratio",
    "da_load_payment_usd",
    "rt_imbalance_load_payment_usd",
    "congestion_rent_rebate_usd",
    "uplift_charge_allocation_usd",
    "net_lse_charge_usd",
)


def validate_ledger_schema(ledger: Dict[str, Any], expected_episode_ids: List[str]) -> List[str]:
    """Return a list of schema error strings (empty list if valid)."""
    errors: List[str] = []
    if not isinstance(ledger, dict):
        return ["Top-level ledger must be a JSON object."]
    if ledger.get("schema_version") != "1.0":
        errors.append(f"Expected schema_version '1.0', got {ledger.get('schema_version')!r}.")
    episodes = ledger.get("episodes")
    if not isinstance(episodes, dict):
        return errors + ["'episodes' must be a JSON object mapping episode_id to episode payload."]

    for ep_id in expected_episode_ids:
        if ep_id not in episodes:
            errors.append(f"Missing episode {ep_id!r} in ledger['episodes'].")
            continue
        ep = episodes[ep_id]
        for k in REQUIRED_EPISODE_SECTIONS:
            if k not in ep:
                errors.append(f"{ep_id}: missing section {k!r}.")
        if "telemetry_summary" in ep:
            for k in REQUIRED_TELEMETRY_KEYS:
                if k not in ep["telemetry_summary"]:
                    errors.append(f"{ep_id}.telemetry_summary: missing key {k!r}.")
        if "topology_diagnostics" in ep:
            for k in REQUIRED_TOPOLOGY_DIAG_KEYS:
                if k not in ep["topology_diagnostics"]:
                    errors.append(f"{ep_id}.topology_diagnostics: missing key {k!r}.")
        if "dispatch" in ep:
            for k in REQUIRED_DISPATCH_KEYS:
                if k not in ep["dispatch"]:
                    errors.append(f"{ep_id}.dispatch: missing key {k!r}.")
        if "prices" in ep:
            for k in REQUIRED_PRICES_KEYS:
                if k not in ep["prices"]:
                    errors.append(f"{ep_id}.prices: missing key {k!r}.")
        if "settlement" in ep:
            for k in REQUIRED_SETTLEMENT_KEYS:
                if k not in ep["settlement"]:
                    errors.append(f"{ep_id}.settlement: missing key {k!r}.")
    return errors
