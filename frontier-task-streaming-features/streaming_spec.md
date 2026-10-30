# Streaming feature specification

Canonical event order is `(event_time, ingest_time, source, event_id)`. Timestamps are ISO-8601
UTC strings. A tumbling window uses `start = floor(epoch_seconds / window_seconds) * window_seconds`
and `end = start + window_seconds`. Feature ID is `metric:key:start:end`; revisions begin at 1.

For each metric window, compute count, sum, min, max, mean, and population variance from the
deduplicated values. A correction increments the revision and replaces the previous feature.
Output features are sorted by `(feature_id, revision)`, with only the final revision marked
`current: true`.

Session IDs are `session:key:start`; session end is the greatest event time in the session.
Two sessions merge when a newly inserted event is within the configured gap of either session.
The surviving session has the earliest start; old IDs appear in `tombstones`.

For each metric/label pair on the same key with absolute event-time difference within tolerance,
emit `metric_event_id`, `label_event_id`, and `delta_seconds`. Sort joins by both IDs.
Checkpoint digest is a SHA-256 chain over sorted accepted event IDs and emitted feature IDs.
