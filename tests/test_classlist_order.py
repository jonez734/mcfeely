"""postoffice's classlist creates each table before anything that references it.

Each entry's SQL file is run in order. A foreign key or view that names a
table listed later fails with 'relation does not exist'. This checks the
order against the references each file declares.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "postoffice"
PKG_SQL = ROOT / "sql"
STARTUP = ROOT / "startup.py"


def _order():
    text = STARTUP.read_text(encoding="utf-8")
    pairs = re.findall(r'\(\s*"(postoffice\.[\w.]+)",\s*"([\w.]+\.sql)"\s*\)', text)
    return [(cls, sql) for cls, sql in pairs]


def _refs(sql_file):
    text = (PKG_SQL / sql_file).read_text(encoding="utf-8")
    return set(re.findall(r"references\s+(postoffice\.[\w]+)", text, re.I))


def _defined(sql_file):
    text = (PKG_SQL / sql_file).read_text(encoding="utf-8")
    return set(re.findall(r"create\s+(?:table|view|or replace view)\s+(?:if not exists\s+)?(postoffice\.[\w]+)", text, re.I))


def test_each_reference_is_created_earlier():
    order = _order()
    seen = set()
    problems = []
    for cls, sql in order:
        for ref in _refs(sql):
            if ref not in seen and ref != cls:
                problems.append(f"{cls} ({sql}) references {ref} before it is created")
        seen |= _defined(sql)
        seen.add(cls)
    assert not problems, "\n".join(problems)
