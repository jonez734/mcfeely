"""Packaged postoffice SQL runs without psql.

bbsengine6's importsql sends SQL straight to the server. psql meta-commands
(\\echo, \\set, \\i) and :variable placeholders are not SQL and fail. Every file
under src/postoffice/sql/ must be plain SQL.
"""

import re
from pathlib import Path

PKG_SQL = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "sql"


def test_no_psql_meta_commands():
    bad = {}
    for f in sorted(PKG_SQL.glob("*.sql")):
        hits = [ln for ln in f.read_text(encoding="utf-8").splitlines()
                if re.match(r"^\s*\\", ln)]
        if hits:
            bad[f.name] = hits
    assert not bad, f"psql meta-commands in packaged SQL: {bad}"


def test_no_psql_variable_placeholders():
    bad = {}
    for f in sorted(PKG_SQL.glob("*.sql")):
        hits = [ln for ln in f.read_text(encoding="utf-8").splitlines()
                if re.search(r"(?<![:\w]):[a-z_]+\b", ln) and "--" not in ln.split(":", 1)[0]]
        if hits:
            bad[f.name] = hits
    assert not bad, f"psql :variable placeholders in packaged SQL: {bad}"
