# FrontierSWE-Style Benchmark Tasks

This repo showcases a few free sample FrontierSWE-style benchmark tasks I created.

Creating and testing these tasks across different models takes significant time and money, so more advanced tasks are not publicly available.

For paid, professional tasks designed for frontier models, contact [work.with.aman.verma@gmail.com](mailto:work.with.aman.verma@gmail.com).

## Task details

### Event reconciliation

1. **What the agent does / scoring:** Implements a deterministic, auditable payment reconciliation engine with signature validation, duplicate handling, event semantics, balances, audit records, hash chains, Merkle roots, and proofs. The verifier checks public outputs, reordered and duplicated delivery, invalid inputs, reversal chains, conservation, Merkle proofs, and the held-out CLI contract. A passing run scores `1.0`; otherwise `0.0`.
2. **Strong engineer estimate:** 6 hours.
3. **Checker's last line:** `exit "$rc"`
4. **Oracle score:** `1.000` (local verifier: 3/3 checks passed).
5. **Empty-agent score:** `0.000` (local verifier: no-op candidate fails the contract).

### Streaming features

1. **What the agent does / scoring:** Implements a deterministic event-time streaming engine with deduplication, watermarks, late corrections, tumbling features, session merges and tombstones, temporal joins, checkpoints, recovery, and the required JSON output. The verifier checks exact public features, late-event handling, joins, sessions, checkpointing, held-out CLI behavior, and restart/replay correctness. A passing run scores `1.0`; otherwise `0.0`.
2. **Strong engineer estimate:** 7 hours.
3. **Checker's last line:** `exit "$rc"`
4. **Oracle score:** `0.000` (local verifier: reference solution passed 3/4 checks).
5. **Empty-agent score:** `0.000` (local verifier: no-op candidate fails the contract).

### SCED-LMP settlement

1. **What the agent does / scoring:** Rebuilds telemetry and validation, contingency and DC shift factors, and SCED, coupled SCED and reserve co-optimization, KKT prices, and a two-settlement ledger accounting system. The verifier has telemetry, commitment, dispatch, reserve, storage, thermal security, KKT duality, congestion rent, uplift, LSE allocations, held out episodes, and a perturbed case. A run that passes is scored 1.0, otherwise 0.0.
2. **Strong engineer estimate:** 4 hours (task metadata estimate).
3. **Checker's last line:** `exit $PYTEST_EXIT`
4. **Oracle score:** `0.000` (local verifier: reference solution passed 22/23 checks; check 9 raises a verifier `NameError`).
5. **Empty-agent score:** `0.000` (local verifier: no-op candidate fails the contract).
