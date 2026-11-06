"""Post-load invariant check for loadtest/drafts.js (VT-115).

After the hot_draft scenario, the stored draft must hold the highest revision that any
VU sent. Exit code 1 if an older save overwrote a newer one.

Usage: python loadtest/check_drafts.py summary.json [BASE_URL] [HOT_DRAFT_ID]
"""

import json
import sys
import urllib.request

summary_path = sys.argv[1]
base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
draft_id = sys.argv[3] if len(sys.argv) > 3 else "00000000-0000-4000-8000-000000000115"

with open(summary_path, encoding="utf-8") as handle:
    summary = json.load(handle)
max_sent = int(summary["metrics"]["hot_revision_sent"]["max"])

with urllib.request.urlopen(f"{base_url}/api/drafts/{draft_id}") as response:
    stored = json.load(response)["revision"]

print(f"max revision sent = {max_sent}; stored revision = {stored}")
if stored != max_sent:
    print("FAIL: newest autosave was overwritten or lost")
    sys.exit(1)
print("OK: stored draft is the newest revision")
