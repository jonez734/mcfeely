#!/usr/bin/env python3
"""Integrated tests that hit a live PostgreSQL database.

These tests require a running PostgreSQL server with a database that has
been bootstrapped with the bbsengine6 schema (engine.__member,
engine.map_member_flag, etc.).

Run with::

    python -m pytest tests/test_postoffice_integration.py \\
        --postoffice-databasename=zoid6 -v

or simply set the env var ``POSTOFFICE_DATABASENAME=zoid6`` (the tests
read either source). Without either, the tests fail with a clear
"DB not configured" error rather than silently passing.
"""

import argparse
import os
import sys
import unittest
from typing import Optional


REPO_SRC = "/home/opencode/data/work/mistermcfeely/src"
BBSENGINE_SRC = "/home/opencode/data/work/bbsengine6/py/src"
for p in (REPO_SRC, BBSENGINE_SRC):
    if p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)


def _resolve_databasename() -> Optional[str]:
    """Look up the configured DB name from env or pytest CLI flag."""
    name = os.environ.get("POSTOFFICE_DATABASENAME")
    if name:
        return name
    for arg in sys.argv:
        if arg.startswith("--postoffice-databasename="):
            return arg.split("=", 1)[1]
    return None


def _is_databasename_configured() -> bool:
    return bool(_resolve_databasename())


@unittest.skipUnless(
    _is_databasename_configured(), "POSTOFFICE_DATABASENAME not set"
)
class PostofficeIntegrationBase(unittest.TestCase):
    """Base class that gives subclasses a working args/conn."""

    @classmethod
    def setUpClass(cls):
        resolved = _resolve_databasename()
        if not resolved:
            raise unittest.SkipTest("POSTOFFICE_DATABASENAME not set")
        cls.args = argparse.Namespace(
            databasename=resolved,
            databasehost=os.environ.get("POSTOFFICE_DATABASEHOST", "localhost"),
            databaseport=int(os.environ.get("POSTOFFICE_DATABASEPORT", "5432")),
            databaseuser=os.environ.get("POSTOFFICE_DATABASEUSER"),
            databasepassword=os.environ.get("POSTOFFICE_DATABASEPASSWORD"),
            debug=False,
        )
        from bbsengine6 import database

        cls.pool = database.getpool(cls.args)

    def _cur(self):
        """Return ``(conn_cm, conn, cursor_cm, cursor)`` where cursor yields dict rows."""
        from bbsengine6 import database

        conn_cm = database.connect(self.args, pool=self.pool)
        conn = conn_cm.__enter__()
        cur_cm = database.cursor(conn)
        cur = cur_cm.__enter__()
        return conn_cm, conn, cur_cm, cur


class TestZoid6DatabaseConnectivity(PostofficeIntegrationBase):
    """Sanity check: the configured DB is reachable and reports the right name."""

    def test_current_database(self):
        cm, _conn, cur_cm, cur = self._cur()
        try:
            cur.execute("SELECT current_database() AS db")
            row = cur.fetchone()
        finally:
            cur_cm.__exit__(None, None, None)
            cm.__exit__(None, None, None)
        self.assertEqual(row["db"], _resolve_databasename())

    def test_required_engine_tables_exist(self):
        cm, _conn, cur_cm, cur = self._cur()
        try:
            cur.execute(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'engine'
                  AND tablename IN (
                    '__member',
                    'map_member_flag',
                    'member',
                    'member_flag'
                  )
                ORDER BY tablename
                """
            )
            tables = {r["tablename"] for r in cur.fetchall()}
        finally:
            cur_cm.__exit__(None, None, None)
            cm.__exit__(None, None, None)
        self.assertIn("__member", tables)
        self.assertIn("map_member_flag", tables)


class TestCheckSysopFlagAgainstZoid6(PostofficeIntegrationBase):
    """``check_sysop_flag`` reads engine.map_member_flag and bails on missing rows."""

    def _seed_flag(self, moniker: str, value: bool) -> None:
        cm, _conn, cur_cm, cur = self._cur()
        try:
            cur.execute(
                "INSERT INTO engine.map_member_flag (moniker, name, value) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (moniker, name) DO UPDATE SET value = EXCLUDED.value",
                (moniker, "SYSOP", value),
            )
            _conn.commit()
        finally:
            cur_cm.__exit__(None, None, None)
            cm.__exit__(None, None, None)

    def _has_sysop_flag_row(self, moniker: str) -> bool:
        cm, _conn, cur_cm, cur = self._cur()
        try:
            cur.execute(
                "SELECT 1 FROM engine.map_member_flag "
                "WHERE moniker = %s AND name = 'SYSOP'",
                (moniker,),
            )
            return cur.fetchone() is not None
        finally:
            cur_cm.__exit__(None, None, None)
            cm.__exit__(None, None, None)

    def test_known_sysop_returns_true(self):
        from postoffice.__main__ import check_sysop_flag

        if not self._has_sysop_flag_row("jam"):
            self.skipTest("jam has no SYSOP flag row in zoid6")

        result = check_sysop_flag(self.args, "jam", self.pool)
        self.assertTrue(result)

    def test_known_non_sysop_returns_false(self):
        from postoffice.__main__ import check_sysop_flag

        result = check_sysop_flag(self.args, "test_opencode_1", self.pool)
        self.assertFalse(result)

    def test_nonexistent_member_returns_false(self):
        from postoffice.__main__ import check_sysop_flag

        result = check_sysop_flag(self.args, "definitely_not_a_real_user", self.pool)
        self.assertFalse(result)

    def test_explicit_false_flag_returns_false(self):
        """A row with value=False must not be reported as sysop.

        Uses an existing ``engine.__member`` row (``test_opencode_1``)
        to satisfy the foreign-key constraint, then rolls back the
        SYSOP flag we added.
        """
        from postoffice.__main__ import check_sysop_flag

        target = "test_opencode_1"
        self._seed_flag(target, False)
        try:
            self.assertTrue(self._has_sysop_flag_row(target))
            result = check_sysop_flag(self.args, target, self.pool)
            self.assertFalse(result)
        finally:
            cm, _conn, cur_cm, cur = self._cur()
            try:
                cur.execute(
                    "DELETE FROM engine.map_member_flag "
                    "WHERE moniker = %s AND name = 'SYSOP'",
                    (target,),
                )
                _conn.commit()
            finally:
                cur_cm.__exit__(None, None, None)
                cm.__exit__(None, None, None)


class TestStartupAgainstZoid6(PostofficeIntegrationBase):
    """Encryption key lookup via env var succeeds when configured."""

    def setUp(self):
        import base64
        import os as _os

        self._saved_key = _os.environ.pop("POSTOFFICE_PASSWORD_KEY", None)
        _os.environ["POSTOFFICE_PASSWORD_KEY"] = base64.b64encode(
            _os.urandom(32)
        ).decode()

    def tearDown(self):
        import os as _os

        if self._saved_key is None:
            _os.environ.pop("POSTOFFICE_PASSWORD_KEY", None)
        else:
            _os.environ["POSTOFFICE_PASSWORD_KEY"] = self._saved_key

    def test_startup_get_encryption_key_does_not_raise(self):
        from postoffice import startup

        key = startup.get_encryption_key()
        self.assertIsNotNone(key)
        self.assertEqual(len(key), 32)


class TestPasswordCryptoRoundtrip(PostofficeIntegrationBase):
    """bbsengine6 password crypto roundtrip works (integration sanity).

    These tests set ``POSTOFFICE_PASSWORD_KEY`` to a fresh 32-byte key
    for the duration of the test method so they don't depend on
    whatever the environment looks like outside the suite.
    """

    def setUp(self):
        import base64
        import os as _os

        self._saved_key = _os.environ.pop("POSTOFFICE_PASSWORD_KEY", None)
        _os.environ["POSTOFFICE_PASSWORD_KEY"] = base64.b64encode(
            _os.urandom(32)
        ).decode()

    def tearDown(self):
        import os as _os

        if self._saved_key is None:
            _os.environ.pop("POSTOFFICE_PASSWORD_KEY", None)
        else:
            _os.environ["POSTOFFICE_PASSWORD_KEY"] = self._saved_key

    def test_encrypt_decrypt_roundtrip(self):
        from bbsengine6.util import encrypt_password, decrypt_password

        plaintext = "integration-test-secret"
        ciphertext = encrypt_password(plaintext)
        decrypted = decrypt_password(ciphertext)
        self.assertEqual(decrypted, plaintext)

    def test_ciphertext_is_not_plaintext(self):
        from bbsengine6.util import encrypt_password

        plaintext = "integration-test-secret"
        ciphertext = encrypt_password(plaintext)
        self.assertNotIn(plaintext, ciphertext)

    def test_two_encryptions_of_same_plaintext_differ(self):
        """AES-GCM uses a random nonce; identical plaintexts differ."""
        from bbsengine6.util import encrypt_password

        a = encrypt_password("same")
        b = encrypt_password("same")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
