# tests/test_password_integration.py
# Integration tests for password management system with mocked database

import os
import sys
import base64
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import (
    member_password,
    shared_mailbox_password,
    password_auth,
    password_crypto,
)


class MockCursor:
    def __init__(self, data=None):
        self.rowcount = 0
        self._data = data or {}
        self._update_count = 0

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        self.rowcount = 1

    def fetchone(self):
        if self._data and "single" in self._data:
            return self._data["single"]
        return None

    def fetchall(self):
        return self._data.get("all", [])


class MockConnection:
    def __init__(self):
        self.cursor_obj = MockCursor()

    def cursor(self):
        return MockCursorContext(self.cursor_obj)

    def commit(self):
        pass

    def rollback(self):
        pass


class MockCursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *args):
        pass


class TestMemberPasswordIntegration(unittest.TestCase):
    """Integration tests for member personal password management."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("bbsengine6.database.connect")
    def test_set_personal_password_success(self, mock_connect):
        """Test setting personal inbound password successfully."""
        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password="secret123",
            set_by_moniker="alice",
        )

        self.assertTrue(result)
        self.assertIn("inbound_password", self.mock_conn.cursor_obj.last_query)
        self.assertIn("UPDATE engine.__member", self.mock_conn.cursor_obj.last_query)

    @patch("bbsengine6.database.connect")
    def test_set_personal_password_outbound(self, mock_connect):
        """Test setting personal outbound password."""
        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.set_personal_password(
            self.args,
            member_moniker="bob",
            password_type="outbound",
            password="smtp_secret",
            set_by_moniker="bob",
        )

        self.assertTrue(result)
        self.assertIn("outbound_password", self.mock_conn.cursor_obj.last_query)

    def test_set_personal_password_invalid_type(self):
        """Test error on invalid password_type."""
        with self.assertRaises(ValueError):
            member_password.set_personal_password(
                self.args,
                member_moniker="alice",
                password_type="invalid",
                password="secret",
                set_by_moniker="alice",
            )

    def test_set_personal_password_permission_denied(self):
        """Test non-sysop cannot set another member's password."""
        self.args.issuperuser = False

        with self.assertRaises(PermissionError):
            member_password.set_personal_password(
                self.args,
                member_moniker="bob",
                password_type="inbound",
                password="secret",
                set_by_moniker="alice",
            )

    @patch("bbsengine6.database.connect")
    def test_set_personal_password_sysop_can_set_any(self, mock_connect):
        """Test sysop can set any member's password."""
        self.args.issuperuser = True
        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.set_personal_password(
            self.args,
            member_moniker="bob",
            password_type="inbound",
            password="secret",
            set_by_moniker="admin",
        )

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_get_personal_password_success(self, mock_connect):
        """Test retrieving and decrypting personal password."""
        encrypted = password_crypto.encrypt_password("secret123")
        cursor = MockCursor()
        cursor._data = {"single": {"inbound_password": encrypted}}

        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor

        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        password = member_password.get_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "secret123")

    @patch("bbsengine6.database.connect")
    def test_get_personal_password_sysop_access(self, mock_connect):
        """Test sysop can retrieve any member's password."""
        self.args.issuperuser = True

        encrypted = password_crypto.encrypt_password("secret456")
        cursor = MockCursor()
        cursor._data = {"single": {"inbound_password": encrypted}}

        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor

        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        password = member_password.get_personal_password(
            self.args,
            member_moniker="bob",
            password_type="inbound",
            requester_moniker="admin",
        )

        self.assertEqual(password, "secret456")

    @patch("bbsengine6.database.connect")
    def test_get_personal_password_not_found(self, mock_connect):
        """Test getting password when not set."""
        cursor = MockCursor()
        cursor._data = {"single": {"inbound_password": None}}

        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor

        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        password = member_password.get_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertIsNone(password)

    @patch("bbsengine6.database.connect")
    def test_delete_personal_password(self, mock_connect):
        """Test deleting personal password."""
        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.delete_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertTrue(result)
        self.assertIn("NULL", self.mock_conn.cursor_obj.last_query)


class TestSharedMailboxPasswordIntegration(unittest.TestCase):
    """Integration tests for shared mailbox password management."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("bbsengine6.database.cursor")
    @patch("bbsengine6.database.connect")
    def test_set_shared_mailbox_password(self, mock_connect, mock_cursor_class):
        """Test setting per-member shared mailbox password."""
        mock_cursor = MagicMock()
        mock_cursor_class.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_class.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.set_shared_mailbox_password(
            self.args,
            mailbox_address="support@example.com",
            member_moniker="alice",
            password_type="inbound",
            password="mailbox_secret",
            set_by_moniker="alice",
        )

        self.assertTrue(result)
        mock_cursor.execute.assert_called_once()

    @patch("bbsengine6.database.cursor")
    @patch("bbsengine6.database.connect")
    def test_get_shared_mailbox_password(self, mock_connect, mock_cursor_class):
        """Test retrieving shared mailbox password."""
        encrypted = password_crypto.encrypt_password("mailbox_secret")
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"encrypted_password": encrypted}
        mock_cursor_class.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_class.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        password = shared_mailbox_password.get_shared_mailbox_password(
            self.args,
            mailbox_address="support@example.com",
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "mailbox_secret")

    @patch("bbsengine6.database.cursor")
    @patch("bbsengine6.database.connect")
    def test_delete_shared_mailbox_password(self, mock_connect, mock_cursor_class):
        """Test deleting shared mailbox password."""
        mock_cursor = MagicMock()
        mock_cursor_class.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_class.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.delete_shared_mailbox_password(
            self.args,
            mailbox_address="support@example.com",
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertTrue(result)

    @patch("bbsengine6.database.cursor")
    @patch("bbsengine6.database.connect")
    def test_list_shared_mailbox_passwords(self, mock_connect, mock_cursor_class):
        """Test listing member's shared mailbox passwords."""
        now = datetime.now(timezone.utc)
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "password_type": "inbound",
                "encrypted_password": "encrypted_data_here",
                "set_by_moniker": "alice",
                "dateupdated": now,
            },
            {
                "password_type": "outbound",
                "encrypted_password": "encrypted_data_here",
                "set_by_moniker": "bob",
                "dateupdated": now,
            },
        ]
        mock_cursor_class.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor_class.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=MagicMock())
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.list_shared_mailbox_passwords(
            self.args,
            mailbox_address="support@example.com",
            member_moniker="alice",
            requester_moniker="alice",
        )

        self.assertIn("inbound", result)
        self.assertIn("outbound", result)
        self.assertTrue(result["inbound"]["exists"])


class TestPasswordAuthIntegration(unittest.TestCase):
    """Integration tests for password authentication with fallback logic."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_validate_password_valid(self):
        """Test password validation with valid input."""
        self.assertTrue(password_auth.validate_password("inbound", "password123"))
        self.assertTrue(password_auth.validate_password("outbound", "smtp_pass"))

    def test_validate_password_empty(self):
        """Test password validation rejects empty."""
        self.assertFalse(password_auth.validate_password("inbound", ""))
        self.assertFalse(password_auth.validate_password("inbound", None))

    def test_validate_password_invalid_type(self):
        """Test password validation rejects invalid type."""
        self.assertFalse(password_auth.validate_password("invalid", "password"))

    @patch("postoffice.member_password.get_personal_password")
    def test_get_auth_password_personal_account(self, mock_get_personal):
        """Test getting password for personal account (mailbox_id=None)."""
        mock_get_personal.return_value = "personal_secret"

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=None,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "personal_secret")
        mock_get_personal.assert_called_once()

    @patch("postoffice.shared_mailbox_password.get_shared_mailbox_password")
    @patch("postoffice.password_auth._get_shared_mailbox_default_password")
    def test_get_auth_password_shared_mailbox_per_member(
        self, mock_get_default, mock_get_per_member
    ):
        """Test getting per-member password for shared mailbox."""
        mock_get_per_member.return_value = "per_member_secret"
        mock_get_default.return_value = "default_secret"

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "per_member_secret")
        mock_get_per_member.assert_called_once()
        mock_get_default.assert_not_called()

    @patch("postoffice.shared_mailbox_password.get_shared_mailbox_password")
    @patch("postoffice.password_auth._get_shared_mailbox_default_password")
    def test_get_auth_password_shared_mailbox_fallback(
        self, mock_get_default, mock_get_per_member
    ):
        """Test fallback to shared default when per-member not found."""
        mock_get_per_member.return_value = None
        mock_get_default.return_value = "default_secret"

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "default_secret")
        mock_get_per_member.assert_called_once()
        mock_get_default.assert_called_once()

    @patch("postoffice.shared_mailbox_password.get_shared_mailbox_password")
    @patch("postoffice.password_auth._get_shared_mailbox_default_password")
    def test_get_auth_password_shared_mailbox_not_found(
        self, mock_get_default, mock_get_per_member
    ):
        """Test failure when neither per-member nor default password found."""
        mock_get_per_member.return_value = None
        mock_get_default.return_value = None

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertIsNone(password)

    @patch("postoffice.member_password.get_personal_password")
    def test_get_auth_password_invalid_type(self, mock_get_personal):
        """Test error on invalid password_type."""
        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=None,
            member_moniker="alice",
            password_type="invalid",
            requester_moniker="alice",
        )

        self.assertIsNone(password)
        mock_get_personal.assert_not_called()

    @patch("postoffice.shared_mailbox_password.get_shared_mailbox_password")
    @patch("postoffice.password_auth._get_shared_mailbox_default_password")
    def test_get_auth_password_with_logging(
        self, mock_get_default, mock_get_per_member
    ):
        """Test logging function is called on auth failure."""
        mock_get_per_member.return_value = None
        mock_get_default.return_value = None
        mock_log = Mock()

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
            log_entry_fn=mock_log,
        )

        self.assertIsNone(password)
        mock_log.assert_called_once()
        self.assertIn("Auth failed", mock_log.call_args[0][0])


class TestLogentryIntegration(unittest.TestCase):
    """Integration tests for get_auth_password with real bbsengine6.util.logentry().

    Verifies that when password_auth.get_auth_password() receives a real
    logentry() function (the canonical Phase 5 logger), auth failures are
    captured with the new structured format.
    """

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def _make_bound_logentry(self):
        """Create a partial-wrapped logentry that writes to a fresh StringIO.

        Returns (bound_logentry_fn, buf). The logentry function uses a unique
        logger name so each test gets a fresh handler.
        """
        import logging
        import io
        import uuid
        from functools import partial
        from bbsengine6 import util as bbsutil

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter('%(message)s'))
        name = f"pwauth_test_{uuid.uuid4().hex[:8]}"
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        return partial(bbsutil.logentry, logger_name=name), buf

    @patch("postoffice.shared_mailbox_password.get_shared_mailbox_password")
    @patch("postoffice.password_auth._get_shared_mailbox_default_password")
    def test_auth_failure_message_reaches_logentry(self, mock_get_default, mock_get_per_member):
        """Auth failure message body reaches real logentry() and is captured."""
        mock_get_per_member.return_value = None
        mock_get_default.return_value = None
        bound_logentry, buf = self._make_bound_logentry()

        password = password_auth.get_auth_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
            log_entry_fn=bound_logentry,
        )

        self.assertIsNone(password)
        output = buf.getvalue()
        self.assertIn("Auth failed", output)
        self.assertIn("alice", output)
        self.assertIn("inbound", output)

    def test_logentry_with_module_kwarg_produces_structured_format(self):
        """Verify structured [module] format works for password operations."""
        bound_logentry, buf = self._make_bound_logentry()

        # Call with structured kwargs - the new Phase 5 format
        bound_logentry(
            "auth failed",
            module="postoffice",
            action="auth_fail",
            moniker="alice",
            password_type="inbound",
        )

        output = buf.getvalue().strip()
        self.assertIn("[postoffice]", output)
        self.assertIn("auth_fail", output)
        self.assertIn("moniker=alice", output)
        self.assertIn("password_type=inbound", output)
        self.assertIn("auth failed", output)

    def test_logentry_kwargs_ordering(self):
        """Verify [module] comes first, action second, message last (rsplit)."""
        bound_logentry, buf = self._make_bound_logentry()
        bound_logentry(
            "trailing message",
            module="postoffice",
            action="set",
        )

        output = buf.getvalue().strip()
        self.assertTrue(output.startswith("[postoffice] set"))
        self.assertTrue(output.endswith("trailing message"))


class TestPasswordEncryptionIntegration(unittest.TestCase):
    """Integration tests for encryption with password functions."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_encryption_roundtrip_consistency(self):
        """Test that password is consistently encrypted/decrypted."""
        plaintext = "MyComplexPassword123!@#"

        encrypted1 = password_crypto.encrypt_password(plaintext)
        encrypted2 = password_crypto.encrypt_password(plaintext)

        self.assertNotEqual(encrypted1, encrypted2)

        self.assertEqual(password_crypto.decrypt_password(encrypted1), plaintext)
        self.assertEqual(password_crypto.decrypt_password(encrypted2), plaintext)

    def test_encryption_format_base64(self):
        """Test that encrypted password is valid base64."""
        plaintext = "test_password"
        encrypted = password_crypto.encrypt_password(plaintext)

        try:
            base64.b64decode(encrypted)
        except Exception:
            self.fail("Encrypted password is not valid base64")

    def test_encryption_nonce_uniqueness(self):
        """Test that each encryption uses unique nonce."""
        plaintext = "same_password"

        encrypted_passwords = [
            password_crypto.encrypt_password(plaintext) for _ in range(10)
        ]

        self.assertEqual(len(set(encrypted_passwords)), len(encrypted_passwords))

        for encrypted in encrypted_passwords:
            self.assertEqual(password_crypto.decrypt_password(encrypted), plaintext)


if __name__ == "__main__":
    unittest.main()
