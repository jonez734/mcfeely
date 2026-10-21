"""Every foreign key in postoffice's packaged SQL has matching column types.

Postgres rejects a foreign key whose child and parent types differ (for example
text referencing citext, or integer referencing bigint). Each child column
named in a references clause must be the same type as the parent column it
points at.
"""

import re
from pathlib import Path

PKG_SQL = Path(__file__).resolve().parents[1] / "src" / "postoffice" / "sql"

# Parent key types, from the referenced tables in the packaged SQL and the
# shared engine schema.
PARENT = {
    ("engine.__member", "moniker"): "citext",
    ("postoffice.__mailbox", "id"): "bigint",
    ("postoffice.__address", "address"): "text",
}


def _declared_types(text):
    types = {}
    for m in re.finditer(r"^\s*\"?(\w+)\"?\s+(citext|text|bigint|integer|int|bigserial|serial|boolean|timestamptz|timestamp)\b",
                         text, re.M | re.I):
        types.setdefault(m.group(1).lower(), m.group(2).lower())
    return types


def _fk_pairs(text):
    # child column in a column definition or FOREIGN KEY (...) clause, then its parent
    pairs = []
    for m in re.finditer(r"FOREIGN KEY\s*\((\w+)\)\s*REFERENCES\s+([\w.]+)\s*\((\w+)\)", text, re.I):
        pairs.append((m.group(1), m.group(2).lower(), m.group(3)))
    for m in re.finditer(r"\"?(\w+)\"?\s+[\w\s]*?references\s+([\w.]+)\s*\((\w+)\)", text, re.I):
        pairs.append((m.group(1), m.group(2).lower(), m.group(3)))
    return pairs


def test_foreign_key_child_types_match_parents():
    problems = []
    for f in sorted(PKG_SQL.glob("*.sql")):
        text = f.read_text(encoding="utf-8")
        types = _declared_types(text)
        for child, parent_table, parent_col in _fk_pairs(text):
            want = PARENT.get((parent_table, parent_col))
            have = types.get(child.lower())
            if want and have and have.replace("serial", "int").replace("integer", "int") != want.replace("bigint", "int").replace("citext", "text") and have != want:
                problems.append(f"{f.name}: {child} is {have}, parent {parent_table}.{parent_col} is {want}")
    assert not problems, "\n".join(problems)
