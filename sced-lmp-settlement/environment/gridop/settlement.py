"""
Two-Settlement Day-Ahead / Real-Time Energy & Operating Reserve Imbalance Clearing,
Multi-Interval Three-Part Make-Whole Payment (MWP) Uplift, and Load-Serving Entity (LSE) Allocation.
Refer to /app/grid_settlement_spec.md Section 6.
"""

from typing import Dict, Any


def compute_episode_settlement(
    episode_id: str,
    topology: Dict[str, Any],
    offers: Dict[str, Any],
    telemetry: Dict[str, Any],
    sced_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Assemble the complete episode dictionary including telemetry_summary,
    topology_diagnostics, co-optimized dispatch (energy & spinning reserves),
    prices (energy lambda, reserve MCP, nodal LMPs), and two-settlement accounting.
    """
    raise NotImplementedError("Implement two-settlement energy/reserve accounting and netted MWP uplift per /app/grid_settlement_spec.md Section 6")
