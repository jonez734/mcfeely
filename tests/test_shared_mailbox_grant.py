"""shared_mailbox.sql loads without psql variables.

bbsengine6's importsql runs SQL without psql, so a ``:postoffice`` placeholder
reaches the server unresolved and the statement fails. The grant must use the
same guarded form as migration 006: only if the postoffice role exists.
"""

from pathlib import Path

SQL = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "sql" / "shared_mailbox.sql"


def test_no_unresolved_psql_variable():
    text = SQL.read_text(encoding="utf-8")
    assert ":postoffice" not in text, "shared_mailbox.sql uses an unresolved psql variable"


def test_grant_is_guarded_by_role_existence():
    text = SQL.read_text(encoding="utf-8")
    assert "pg_roles WHERE rolname = 'postoffice'" in text
