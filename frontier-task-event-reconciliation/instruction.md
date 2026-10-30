# Auditable Event-Sourced Payment Reconciliation

Implement `/app/reconcile.py`. It must read a directory of episode inputs and write `/app/reconciliation.json`.

Read `/app/reconciliation_spec.md` before coding. The implementation is intentionally incomplete in `/app/reconcile.py`; do not modify input episodes or the specification.

## Required behavior

1. Parse `events.jsonl` from each episode. Each event has:
   `event_id`, `partition`, `sequence`, `event_type`, `account_id`, `amount_cents`,
   `currency`, `occurred_at`, `causation_id`, `payload`, and `signature`.
2. Verify HMAC-SHA256 using the episode's `keys.json` and the exact canonical JSON described by the specification. Reject invalid signatures, unknown accounts, unsupported currencies, negative amounts, malformed timestamps, and events whose causation target is absent.
3. Reconcile both partitions deterministically. Delivery order is irrelevant. Deduplicate by `event_id`, keeping the lexicographically smallest canonical representation when conflicting duplicates occur and counting the conflict.
4. Apply `credit`, `debit`, `hold`, `release`, `capture`, `refund`, and `transfer` semantics. A reversal or refund is valid only once its target has been accepted; repeated reversals are rejected without changing balances. Transfers must debit the source and credit the destination atomically.
5. Respect the account's currency minor units and overdraft limit. Invalid operations become rejected audit records, not silent drops.
6. Emit per-episode balances, accepted/rejected event IDs, conflict and rejection counters, conservation totals, a canonical event hash chain, a binary Merkle root, and inclusion proofs for every accepted event.
7. Support `python3 /app/reconcile.py` and `python3 /app/reconcile.py --episodes-dir DIR --output PATH`.

The verifier intentionally changes event ordering, duplicates, and partition interleavings. Do not rely on filename order, input order, or Python hash randomization.
