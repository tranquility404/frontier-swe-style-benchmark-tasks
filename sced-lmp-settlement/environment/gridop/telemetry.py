"""
Binary SCADA / Synchrophasor telemetry parser scaffolding.
Refer to /app/grid_settlement_spec.md Section 2 for the normative specification.
"""

import struct
from typing import Dict, Any

HEADER_STRUCT = struct.Struct("<6sHHHHH")
FRAME_STRUCT = struct.Struct("<BBHIIffHH")
SCADA_MAGIC = b"SCADA1"
SCADA_VERSION = 1

FLAG_VALID = 0x01
FLAG_STALE_HOLD = 0x02
FLAG_PMU_LOW_QUALITY = 0x04
FLAG_TELEMETRY_SPIKE = 0x08
FLAG_KW_LOSS_MODE = 0x10


def crc16_ccitt(data: bytes) -> int:
    """Compute CRC-16-CCITT (poly=0x1021, init=0xFFFF, xorout=0x0000) over raw bytes."""
    raise NotImplementedError("Implement CRC-16-CCITT per /app/grid_settlement_spec.md Section 2.2")


def parse_scada_telemetry(bin_path: str, topology: Dict[str, Any], offers: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse scada_telemetry.bin, verify CRC-16-CCITT, drop corrupt/spike frames,
    deduplicate retransmissions by highest seq_num per (frame_type, interval_idx, entity_id),
    convert usable frames to MW, linearly interpolate stale/missing intervals,
    and extract line dynamic rating factors.
    """
    raise NotImplementedError("Implement SCADA binary telemetry pipeline per /app/grid_settlement_spec.md Section 2")
