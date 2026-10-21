"""postoffice grants on its schema are issued by the schema owner, directly.

manage_schema_priv runs as a SECURITY DEFINER function owned by zoid6, so it
grants with zoid6's rights. A schema created by the connecting role (option 2) is
not zoid6's, so that path is denied. The owner issues GRANT itself.
"""

import re
from pathlib import Path

STARTUP = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "startup.py"


def test_schema_grants_do_not_use_the_zoid6_helper():
    text = STARTUP.read_text(encoding="utf-8")
    assert "manage_schema_priv(" not in text, \
        "postoffice must grant on its own schema, not through the zoid6-owned helper"


def test_schema_usage_is_granted_directly():
    text = STARTUP.read_text(encoding="utf-8")
    assert '_grant_schema(conn, "USAGE", role)' in text, \
        "usage must be granted through the owner's direct grant"
    assert re.search(r'GRANT \{\} ON SCHEMA postoffice TO', text), \
        "the direct grant statement must target the postoffice schema"
