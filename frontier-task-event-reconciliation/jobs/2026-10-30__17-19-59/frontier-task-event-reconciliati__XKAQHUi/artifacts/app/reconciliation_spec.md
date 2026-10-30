# Reconciliation specification

All JSON uses UTF-8, no ASCII escaping, sorted keys, and compact separators for hashes.
The event signing bytes are:
`json.dumps(signing_object, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()`,
where `signing_object` is the event with `signature` removed. HMAC uses SHA-256 and the
key named by `account_id` in `keys.json`; transfer events use the source account key.

Canonical event order is `(occurred_at, partition, sequence, event_id)`. Duplicate event IDs
are one logical event. A duplicate with different signing bytes is a conflict; retain the
lexicographically smallest complete canonical JSON only after independently validating it.

Amounts are integer cents. `credit` adds available funds. `debit` subtracts available funds
and requires `available - amount >= -overdraft_limit_cents`. `hold` moves available to held,
`release` moves held to available, and `capture` moves held out of the account. `refund`
reverses a prior debit or capture exactly once. `transfer` atomically debits
`payload.source_account_id` and credits `payload.destination_account_id`; its amount is the
event amount. `causation_id` must name an earlier accepted event in canonical order.

An event is rejected if its HMAC, schema, account, currency, amount, causation, or balance
precondition fails. Rejections never mutate state. A refund or reversal targeting an already
reversed event is rejected.

The hash chain starts with 64 zero hex characters. For each accepted event:
`chain_i = sha256((chain_{i-1} + event_hash).encode()).hexdigest()`,
where `event_hash` is SHA-256 of the compact canonical accepted event.

The Merkle tree leaves are `sha256(("leaf:" + event_hash).encode())`. Parent nodes are
`sha256(("node:" + left + right).encode())`; duplicate the final node when a level has odd
cardinality. The empty root is 64 zeroes. Proofs contain sibling hashes and `"L"`/`"R"`
directions from leaf to root.

Output fields are tested exactly: `episodes`, each episode's `balances`, `accepted_event_ids`,
`rejected_events`, `counters`, `conservation`, `chain_head`, `merkle_root`, and `proofs`.
