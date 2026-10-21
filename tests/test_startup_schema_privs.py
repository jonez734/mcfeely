"""postoffice startup grants schema usage to every role that connects to it.

bed connects as the ``bed`` role. Without a usage grant on the postoffice
schema, postoffice's startup logs 'permission denied for schema postoffice'.
The grant list must include bed, as casino's and bank's do.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "startup.py"


def test_usage_granted_to_bed_role():
    text = SRC.read_text(encoding="utf-8")
    m = re.search(r'for role in \(([^)]*)\):\s*\n\s*_grant_schema\(conn, "USAGE", role\)', text)
    assert m, "schema usage grant loop not found"
    roles = [r.strip().strip('"\'') for r in m.group(1).split(",") if r.strip()]
    assert "bed" in roles, f"usage not granted to bed; granted to {roles}"
