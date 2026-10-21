"""postoffice's schema is owned by zoid6, matching engine, casino, and bank.

The install name is zoid6, so zoid6 owns the install's schemas. Creating the
schema for the connecting role instead left bed owning postoffice objects.
"""

import re
from pathlib import Path

STARTUP = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "startup.py"


def test_schema_is_created_authorized_to_zoid6():
    text = STARTUP.read_text(encoding="utf-8")
    assert re.search(r"CREATE SCHEMA postoffice\s+AUTHORIZATION zoid6", text), \
        "postoffice schema must be created AUTHORIZATION zoid6"
