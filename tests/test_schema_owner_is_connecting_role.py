"""postoffice creates its schema as the connecting role, not as zoid6.

Creating or reassigning the schema to zoid6 needs the connecting role to be able
to SET ROLE zoid6, which gives the service account zoid6's ownership rights. The
schema should be created and kept by whoever runs the startup.
"""

import re
from pathlib import Path

STARTUP = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "startup.py"


def test_schema_is_not_assigned_to_zoid6():
    text = STARTUP.read_text(encoding="utf-8")
    assert not re.search(r"AUTHORIZATION\s+zoid6", text), "schema must not be created AUTHORIZATION zoid6"
    assert "OWNER TO zoid6" not in text, "schema must not be reassigned to zoid6"


def test_schema_is_created_without_naming_an_owner():
    text = STARTUP.read_text(encoding="utf-8")
    assert "CREATE SCHEMA postoffice\"" in text or 'CREATE SCHEMA postoffice"' in text or \
        re.search(r'CREATE SCHEMA postoffice["\')]', text), "schema creation statement not found"
