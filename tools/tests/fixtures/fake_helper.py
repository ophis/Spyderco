"""Fake browser helper for offline run_helper tests.

Reads the job file given as argv[1]. The job controls behaviour:
  "exit": exit code to return (default 0)
  "response": JSON value written to job["result"] when exit is 0
Prints nothing required, per the real browser/*.mjs contract.
"""

import json
import sys

job = json.loads(open(sys.argv[1], encoding="utf-8").read())
code = job.get("exit", 0)
if code == 0:
    with open(job["result"], "w", encoding="utf-8") as f:
        json.dump(job.get("response", {}), f)
sys.exit(code)
