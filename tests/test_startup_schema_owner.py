"""postoffice startup creates and owns its schema as the zoid6 role.

The schema's usage grants run through manage_schema_priv, owned by zoid6. A
schema created by the connecting role cannot be granted to web by that
helper, so postoffice startup failed with 'permission denied for schema
postoffice'. Mirror casino's checkcasino: create AUTHORIZATION zoid6, or
reassign an existing schema to zoid6.
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "startup.py"


def test_schema_created_authorized_to_zoid6():
    text = SRC.read_text(encoding="utf-8")
    assert re.search(r"CREATE SCHEMA postoffice\s+AUTHORIZATION zoid6", text), \
        "postoffice schema is not created AUTHORIZATION zoid6"


def test_existing_schema_reassigned_to_zoid6():
    text = SRC.read_text(encoding="utf-8")
    assert "ALTER SCHEMA postoffice OWNER TO zoid6" in text, \
        "existing postoffice schema is not reassigned to zoid6"
