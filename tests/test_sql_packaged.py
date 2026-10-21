"""Every SQL file postoffice's startup loads ships inside the package.

The startup loads SQL through bbsengine6's load_sql, which reads from the
installed package's sql/ directory. A file kept only in the repo's top-level
sql/ directory is missing from the wheel, so startup fails with
FileNotFoundError. Each class in postoffice's classlist must resolve to a file
under src/postoffice/sql/, and pyproject must declare it as package data.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_SQL = ROOT / "src" / "postoffice" / "sql"
STARTUP = ROOT / "src" / "postoffice" / "startup.py"


def _classlist_files():
    text = STARTUP.read_text(encoding="utf-8")
    return sorted(set(re.findall(r'\(\s*"postoffice\.[\w.]+",\s*"([\w.]+\.sql)"\s*\)', text)))


def test_every_classlist_sql_file_is_in_the_package():
    files = _classlist_files()
    assert files, "no postoffice classlist entries found"
    missing = [f for f in files if not (PKG_SQL / f).is_file()]
    assert not missing, f"not packaged under src/postoffice/sql/: {missing}"


def test_pyproject_declares_sql_as_package_data():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'\[tool\.setuptools\.package-data\]\s*\npostoffice\s*=\s*\[[^\]]*"sql/\*\.sql"', text), \
        "pyproject does not declare postoffice sql/*.sql as package data"
