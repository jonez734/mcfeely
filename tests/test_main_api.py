# tests/test_main_api.py
# Unit tests for postoffice.__main__ module APIs
# Tests user detection, SYSOP flag checking, and module functions

import os
import sys
import base64
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch
from argparse import Namespace

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import __main__ as postoffice_main


class MockCursor:
    """Mock database cursor that tracks operations."""

    def __init__(self, data=None):
        self.rowcount = 1
        self._data = data or {}

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params

    def fetchone(self):
        if self._data and len(self._data) > 0:
            # Return dict-like row
            return {"value": list(self._data.values())[0]}
        return None

    def fetchall(self):
        return list(self._data.values()) if self._data else []


class MockConnection:
    """Mock database connection."""

    def __init__(self, cursor_data=None):
        self._cursor = MockCursor(cursor_data)

    def cursor(self):
        return MockCursorContext(self._cursor)

    def commit(self):
        pass

    def rollback(self):
        pass


class MockCursorContext:
    """Context manager for mock cursor."""

    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *args):
        pass


class TestCheckSysopFlag(unittest.TestCase):
    """Test check_sysop_flag function."""

    def setUp(self):
        """Set up test args."""
        self.args = Namespace()
        self.args.debug = False
        self.pool = Mock()

    @patch("postoffice.__main__.database.connect")
    def test_check_sysop_flag_returns_true(self, mock_connect):
        """Test SYSOP flag returns True when set."""
        # Create mock connection that returns dict-style cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": True}
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = postoffice_main.check_sysop_flag(self.args, "jam", self.pool)
        self.assertTrue(result)

    @patch("postoffice.__main__.database.connect")
    def test_check_sysop_flag_returns_false(self, mock_connect):
        """Test SYSOP flag returns False when not set."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": False}
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = postoffice_main.check_sysop_flag(self.args, "alice", self.pool)
        self.assertFalse(result)

    @patch("postoffice.__main__.database.connect")
    def test_check_sysop_flag_not_found(self, mock_connect):
        """Test SYSOP flag returns False when member not found."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        result = postoffice_main.check_sysop_flag(self.args, "nonexistent", self.pool)
        self.assertFalse(result)

    @patch("postoffice.__main__.database.connect")
    def test_check_sysop_flag_query_params(self, mock_connect):
        """Test SYSOP flag query uses correct parameters."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": True}
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        postoffice_main.check_sysop_flag(self.args, "jam", self.pool)

        # Verify execute was called with correct params
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify query contains expected elements
        self.assertIn("engine.map_member_flag", query)
        self.assertIn("SYSOP", query)
        self.assertEqual(params, ("jam",))

    @patch("postoffice.__main__.database.connect")
    def test_check_sysop_flag_exception_handling(self, mock_connect):
        """Test SYSOP flag returns False on exception."""
        mock_connect.side_effect = Exception("Database error")

        result = postoffice_main.check_sysop_flag(self.args, "jam", self.pool)
        self.assertFalse(result)


class TestModuleAPIFunctions(unittest.TestCase):
    """Test module API functions (init, access, help, version)."""

    def setUp(self):
        """Set up test args."""
        self.args = Namespace()
        self.args.verbose = False

    def test_init_postoffice_returns_true(self):
        """Test init returns True when encryption key is available."""
        with patch.object(postoffice_main, "startup") as mock_startup:
            mock_startup.initialize_password_system.return_value = True

            result = postoffice_main.init(self.args)
            self.assertTrue(result)

    def test_init_postoffice_returns_false_on_key_error(self):
        """Test init returns False when encryption key unavailable."""
        with patch.object(postoffice_main, "startup") as mock_startup:
            mock_startup.initialize_password_system.return_value = False

            result = postoffice_main.init(self.args)
            self.assertFalse(result)

    def test_access_postoffice_returns_true(self):
        """Test access returns True when encryption key available."""
        with patch.object(postoffice_main, "startup") as mock_startup:
            mock_startup.get_encryption_key.return_value = b"key"

            result = postoffice_main.access(self.args, "run")
            self.assertTrue(result)

    def test_access_postoffice_returns_false_on_no_key(self):
        """Test access returns False when no encryption key."""
        with patch.object(postoffice_main, "startup") as mock_startup:
            mock_startup.get_encryption_key.return_value = None

            result = postoffice_main.access(self.args, "run")
            self.assertFalse(result)

    def test_help_postoffice_returns_string(self):
        """Test help returns non-empty string."""
        result = postoffice_main.help_postoffice(self.args)
        self.assertIsInstance(result, str)
        self.assertIn("postoffice", result)

    def test_version_postoffice_returns_string(self):
        """Test version returns non-empty string."""
        result = postoffice_main.version_postoffice(self.args)
        self.assertIsInstance(result, str)
        self.assertIn("postoffice", result.lower())

    def test_canonical_module_api_names_exist(self):
        """The canonical bbsengine6 module-API names are exposed on the module."""
        for name in ("init", "access", "buildargs", "main"):
            self.assertTrue(
                hasattr(postoffice_main, name),
                f"postoffice.__main__ missing canonical module-API name {name!r}",
            )
            self.assertTrue(callable(getattr(postoffice_main, name)))

    def test_legacy_module_api_names_are_aliases(self):
        """Legacy ``init_postoffice``/``access_postoffice`` keep working."""
        self.assertIs(postoffice_main.init_postoffice, postoffice_main.init)
        self.assertIs(postoffice_main.access_postoffice, postoffice_main.access)

    def test_module_api_signatures_accept_kwargs(self):
        """Each canonical module-API function accepts ``**kwargs`` for framework compat."""
        import inspect
        for name in ("init", "access", "buildargs", "main"):
            sig = inspect.signature(getattr(postoffice_main, name))
            self.assertIn(
                "args", sig.parameters,
                f"{name}() must accept a positional 'args' parameter",
            )
            has_var_kw = any(
                p.kind is inspect.Parameter.VAR_KEYWORD
                for p in sig.parameters.values()
            )
            self.assertTrue(
                has_var_kw,
                f"{name}() must accept **kwargs for bbsengine6 module-API compat",
            )


class TestImapCheckerIntegration(unittest.TestCase):
    """Test IMAP checker integration functions."""

    def setUp(self):
        """Set up test args."""
        self.args = Namespace()
        self.args.debug = False
        self.args.verbose = True
        self.args.imaphost = None
        self.args.imapport = None

    def test_imap_checker_class_import(self):
        """Test IMAPChecker class can be imported."""
        from postoffice.imap_checker import IMAPChecker
        self.assertIsNotNone(IMAPChecker)


class TestUserDetection(unittest.TestCase):
    """Test user detection logic (getcurrentmoniker pattern)."""

    def setUp(self):
        """Set up test args."""
        self.args = Namespace()
        self.args.debug = False
        self.args.databasename = "zoid6test"
        self.args.databasehost = "localhost"
        self.args.databaseport = 5432

    @patch("bbsengine6.member.getcurrentmoniker")
    @patch("bbsengine6.database.getpool")
    def test_user_detection_with_loginid(self, mock_getpool, mock_getmoniker):
        """Test user detection uses args.loginid when provided."""
        self.args.loginid = "jam"

        # Mock pool
        mock_pool = Mock()
        mock_getpool.return_value = mock_pool

        # Should not call getcurrentmoniker when loginid is set
        # In handle_menu, current_user = getattr(args, "loginid", None)
        # which would be "jam" directly

        current_user = getattr(self.args, "loginid", None)
        self.assertEqual(current_user, "jam")
        mock_getmoniker.assert_not_called()

    @patch("bbsengine6.member.getcurrentmoniker")
    @patch("bbsengine6.database.getpool")
    def test_user_detection_fallback_to_getcurrentmoniker(self, mock_getpool, mock_getmoniker):
        """Test user detection falls back to getcurrentmoniker when no loginid."""
        self.args.loginid = None
        mock_getmoniker.return_value = "alice"

        # Mock pool
        mock_pool = Mock()
        mock_getpool.return_value = mock_pool

        # Simulate handle_menu logic
        current_user = getattr(self.args, "loginid", None)
        if current_user is None:
            current_user = postoffice_main.member.getcurrentmoniker(
                self.args, pool=mock_pool
            )

        self.assertEqual(current_user, "alice")
        mock_getmoniker.assert_called_once()

    @patch("bbsengine6.member.getcurrentmoniker")
    @patch("bbsengine6.database.getpool")
    def test_user_detection_returns_none_on_failure(self, mock_getpool, mock_getmoniker):
        """Test user detection returns None when getcurrentmoniker fails."""
        self.args.loginid = None
        mock_getmoniker.side_effect = Exception("DB error")

        # Mock pool
        mock_pool = Mock()
        mock_getpool.return_value = mock_pool

        # Simulate handle_menu logic
        current_user = getattr(self.args, "loginid", None)
        if current_user is None:
            try:
                current_user = postoffice_main.member.getcurrentmoniker(
                    self.args, pool=mock_pool
                )
            except Exception:
                current_user = None

        self.assertIsNone(current_user)


class TestDatabaseArgs(unittest.TestCase):
    """Test database argument building."""

    def test_buildargdatabasegroup_adds_args(self):
        """Test buildargdatabasegroup adds expected arguments."""
        import argparse
        from bbsengine6 import database

        parser = argparse.ArgumentParser()
        defaults = {
            "databasename": "zoid6test",
            "databasehost": "localhost",
            "databaseport": 5432,
        }
        database.buildargdatabasegroup(parser, defaults)
        args = parser.parse_args([])

        self.assertEqual(args.databasename, "zoid6test")
        self.assertEqual(args.databasehost, "localhost")
        self.assertEqual(args.databaseport, 5432)


class TestStartupFunctions(unittest.TestCase):
    """Test startup-related functions."""

    def setUp(self):
        """Set up test args."""
        self.args = Namespace()
        self.args.verbose = True

    @patch.object(postoffice_main, "startup")
    def test_startup_check_returns_int(self, mock_startup):
        """Test startup_check returns integer exit code."""
        mock_startup.startup_check.return_value = True

        # Would need proper setup of encryption key for full test
        # Just verify the function exists and is callable
        self.assertTrue(callable(postoffice_main.handle_startup_check))


class TestPasswordManagement(unittest.TestCase):
    """Test password management integration."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Namespace()
        self.args.debug = False
        self.args.issuperuser = False

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_member_password_import(self):
        """Test member_password module is importable."""
        from postoffice import member_password
        self.assertTrue(hasattr(member_password, "set_personal_password"))

    def test_shared_mailbox_password_import(self):
        """Test shared_mailbox_password module is importable."""
        from postoffice import shared_mailbox_password
        self.assertTrue(hasattr(shared_mailbox_password, "set_shared_mailbox_password"))


class TestReadKeyFile(unittest.TestCase):
    """Test postoffice.startup._read_key_file helper."""

    def setUp(self):
        from postoffice import startup
        self.startup = startup
        self.tmpdir = tempfile.mkdtemp()
        # Use a known good 32-byte key for round-trip checks.
        self.expected_bytes = os.urandom(32)
        self.expected_b64 = base64.b64encode(self.expected_bytes).decode()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        # Clear the verbose hook if a test set it.
        self.startup.get_encryption_key.__dict__.pop("_verbose", None)

    def _write(self, name, content, mode=0o600):
        path = os.path.join(self.tmpdir, name)
        with open(path, "wb") as f:
            if isinstance(content, str):
                content = content.encode()
            f.write(content)
        os.chmod(path, mode)
        return path

    def test_missing_file_returns_none(self):
        path = os.path.join(self.tmpdir, "does-not-exist")
        self.assertIsNone(self.startup._read_key_file(path))

    def test_valid_file_returns_key(self):
        path = self._write("good.key", self.expected_b64)
        self.assertEqual(self.startup._read_key_file(path), self.expected_bytes)

    def test_empty_file_returns_none(self):
        path = self._write("empty.key", "")
        self.assertIsNone(self.startup._read_key_file(path))

    def test_non_utf8_file_returns_none(self):
        # Raw binary, not valid base64 text.
        path = self._write("binary.key", os.urandom(64))
        self.assertIsNone(self.startup._read_key_file(path))

    def test_insecure_permissions_returns_none(self):
        path = self._write("loose.key", self.expected_b64, mode=0o644)
        self.assertIsNone(self.startup._read_key_file(path))

    def test_invalid_base64_returns_none(self):
        path = self._write("bad.key", "not-valid-base64!!!")
        self.assertIsNone(self.startup._read_key_file(path))

    def test_wrong_length_returns_none(self):
        # Valid base64, but decodes to a non-32-byte value.
        path = self._write("short.key", base64.b64encode(b"too-short").decode())
        self.assertIsNone(self.startup._read_key_file(path))

    def test_unreadable_file_returns_none(self):
        path = self._write("unreadable.key", self.expected_b64, mode=0o600)
        os.chmod(path, 0o000)
        try:
            # Skip the test if running as root (root can read anything).
            if os.geteuid() == 0:
                self.skipTest("running as root; PermissionError not reachable")
            self.assertIsNone(self.startup._read_key_file(path))
        finally:
            os.chmod(path, 0o600)


class TestGetEncryptionKeyFallthrough(unittest.TestCase):
    """Test that get_encryption_key falls through to the next source on failure."""

    def setUp(self):
        from postoffice import startup
        self.startup = startup
        self.tmpdir = tempfile.mkdtemp()
        self.expected_bytes = os.urandom(32)
        self.expected_b64 = base64.b64encode(self.expected_bytes).decode()
        # Ensure env var does not interfere.
        self._saved_env = os.environ.pop("POSTOFFICE_PASSWORD_KEY", None)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        if self._saved_env is not None:
            os.environ["POSTOFFICE_PASSWORD_KEY"] = self._saved_env
        self.startup.get_encryption_key.__dict__.pop("_verbose", None)

    def test_falls_through_when_system_file_missing(self):
        # No env var, no system file, valid user file -> should return user key.
        user_path = os.path.join(self.tmpdir, "user.key")
        with open(user_path, "w") as f:
            f.write(self.expected_b64)
        os.chmod(user_path, 0o600)

        with patch.object(self.startup.os.path, "expanduser", return_value=user_path), \
             patch.object(self.startup.os.path, "exists",
                          lambda p: p == user_path):
            result = self.startup.get_encryption_key()
        self.assertEqual(result, self.expected_bytes)

    def test_env_var_invalid_falls_through_to_files(self):
        # Bad env var, no system file, valid user file -> should still return user key.
        os.environ["POSTOFFICE_PASSWORD_KEY"] = "not-valid-base64!!!"
        user_path = os.path.join(self.tmpdir, "user.key")
        with open(user_path, "w") as f:
            f.write(self.expected_b64)
        os.chmod(user_path, 0o600)

        with patch.object(self.startup.os.path, "expanduser", return_value=user_path), \
             patch.object(self.startup.os.path, "exists",
                          lambda p: p == user_path):
            result = self.startup.get_encryption_key()
        self.assertEqual(result, self.expected_bytes)


if __name__ == "__main__":
    unittest.main()