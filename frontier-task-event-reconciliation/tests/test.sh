#!/usr/bin/env bash
set -uo pipefail
mkdir -p /logs/verifier; chmod 700 /logs /logs/verifier
pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
rc=$?
printf '%s\n' "$([ "$rc" -eq 0 ] && echo 1.0 || echo 0.0)" > /logs/verifier/reward.txt
chmod 400 /logs/verifier/reward.txt
exit "$rc"
