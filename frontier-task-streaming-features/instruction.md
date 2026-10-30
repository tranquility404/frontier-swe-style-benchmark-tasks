# Watermarked Streaming Feature Engine

Implement `/app/stream_engine.py` and generate `/app/features.json`.

Read `/app/streaming_spec.md` first. The starter engine is intentionally incomplete. The
verifier will deliver the same events in different orders and may restart the process.

## Required behavior

- Read `config.json` and `events.jsonl` for each episode. Events contain
  `event_id`, `source`, `key`, `event_time`, `ingest_time`, and a numeric `value`.
- Deduplicate event IDs globally. Delivery order must not affect output.
- Maintain a watermark `max_event_time_seen - allowed_lateness_seconds`. Events older than
  the watermark are still accepted as corrections, but increment the late counter and revise
  the affected output rather than being dropped.
- Emit revisioned tumbling-window features for `metric` events: count, sum, min, max, mean,
  and population variance. Window boundaries are epoch-aligned half-open intervals.
- Build session windows for `activity` events by key. Events less than or equal to
  `session_gap_seconds` apart belong to one session; a late event can merge two existing
  sessions and must emit tombstones for superseded session IDs.
- Join `metric` events with `label` events on key when their event times differ by at most
  `join_tolerance_seconds`, emitting each pair exactly once.
- Persist checkpoints after every configured batch. Recovery must not duplicate output or lose
  a revision. The final JSON must include `features`, `sessions`, `joins`, `counters`, and
  `checkpoint_digest`.
- Support `python3 /app/stream_engine.py` and `--episodes-dir DIR --output PATH`.

Do not use wall-clock time, filesystem ordering, process IDs, or hash iteration order in
feature IDs or output ordering.
