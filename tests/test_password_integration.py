# tests/test_password_integration.py
# Integration tests for password management system with mocked database

import os
import sys
import base64
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import (
    member_password,
    shared_mailbox_password,
    password_auth,
    password_crypto,
)


class MockCursor:
    """Mock database cursor that tracks operations."""

    def __init__(self):
        self.rowcount = 0
        self._data = {}
        self._update_count = 0

    def execute(self, query, params=None):
        """Mock execute - stores query and params for inspection."""
        self.last_query = query
        self.last_params = params
        self.rowcount = 1  # Assume success by default

    def fetchone(self):
        """Mock fetchone - return dict-like row."""
        return self._data.get("single")

    def fetchall(self):
        """Mock fetchall - return list of dict-like rows."""
        return self._data.get("all", [])


class MockConnection:
    """Mock database connection."""

    def __init__(self):
        self.cursor_obj = MockCursor()

    def cursor(self):
        """Return context manager for cursor."""
        return MockCursorContext(self.cursor_obj)

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


class TestMemberPasswordIntegration(unittest.TestCase):
    """Integration tests for member personal password management."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        # Create mock args object
        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        """Clean up environment."""
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
        # Setup mock to return encrypted password
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
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("bbsengine6.database.connect")
    def test_set_shared_mailbox_password(self, mock_connect):
        """Test setting per-member shared mailbox password."""
        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.set_shared_mailbox_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            password="mailbox_secret",
            set_by_moniker="alice",
        )

        self.assertTrue(result)
        self.assertIn("INSERT", self.mock_conn.cursor_obj.last_query)
        self.assertIn("member_mailbox_password", self.mock_conn.cursor_obj.last_query)

    @patch("bbsengine6.database.connect")
    def test_get_shared_mailbox_password(self, mock_connect):
        """Test retrieving shared mailbox password."""
        encrypted = password_crypto.encrypt_password("mailbox_secret")
        cursor = MockCursor()
        cursor._data = {"single": {"encrypted_password": encrypted}}

        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor

        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        password = shared_mailbox_password.get_shared_mailbox_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertEqual(password, "mailbox_secret")

    @patch("bbsengine6.database.connect")
    def test_delete_shared_mailbox_password(self, mock_connect):
        """Test deleting shared mailbox password."""
        self.mock_conn.cursor_obj.rowcount = 1

        mock_connect.return_value.__enter__ = Mock(return_value=self.mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.delete_shared_mailbox_password(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
        )

        self.assertTrue(result)
        self.assertIn("DELETE", self.mock_conn.cursor_obj.last_query)

    @patch("bbsengine6.database.connect")
    def test_list_shared_mailbox_passwords(self, mock_connect):
        """Test listing member's shared mailbox passwords."""
        cursor = MockCursor()
        now = datetime.now(timezone.utc)
        cursor._data = {
            "all": [
                {
                    "password_type": "inbound",
                    "encrypted_password": "encrypted_data_here",
                    "set_by_moniker": "alice",
                    "updated_at": now,
                },
                {
                    "password_type": "outbound",
                    "encrypted_password": "encrypted_data_here",
                    "set_by_moniker": "bob",
                    "updated_at": now,
                },
            ]
        }

        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor

        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.list_shared_mailbox_passwords(
            self.args,
            mailbox_id=1,
            member_moniker="alice",
            requester_moniker="alice",
        )

        self.assertIn("inbound", result)
        self.assertIn("outbound", result)
        self.assertTrue(result["inbound"]["exists"])
        self.assertTrue(result["outbound"]["exists"])
        self.assertEqual(result["inbound"]["set_by"], "alice")
        self.assertEqual(result["outbound"]["set_by"], "bob")


class TestPasswordAuthIntegration(unittest.TestCase):
    """Integration tests for password authentication with fallback logic."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False
        self.mock_conn = MockConnection()

    def tearDown(self):
        """Clean up environment."""
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
        mock_get_default.assert_not_called()  # Should not reach fallback

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
    def test_get_auth_password_with_logging(self, mock_get_default, mock_get_per_member):
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


class TestPasswordEncryptionIntegration(unittest.TestCase):
    """Integration tests for encryption with password functions."""

    def setUp(self):
        """Set up test encryption key."""
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

    def tearDown(self):
        """Clean up environment."""
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_encryption_roundtrip_consistency(self):
        """Test that password is consistently encrypted/decrypted."""
        plaintext = "MyComplexPassword123!@#"

        # Encrypt multiple times
        encrypted1 = password_crypto.encrypt_password(plaintext)
        encrypted2 = password_crypto.encrypt_password(plaintext)

        # Should produce different ciphertexts (different nonce)
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to same plaintext
        self.assertEqual(password_crypto.decrypt_password(encrypted1), plaintext)
        self.assertEqual(password_crypto.decrypt_password(encrypted2), plaintext)

    def test_encryption_format_base64(self):
        """Test that encrypted password is valid base64."""
        plaintext = "test_password"
        encrypted = password_crypto.encrypt_password(plaintext)

        # Should be base64 encoded
        try:
            base64.b64decode(encrypted)
        except Exception:
            self.fail("Encrypted password is not valid base64")

    def test_encryption_nonce_uniqueness(self):
        """Test that each encryption uses unique nonce."""
        plaintext = "same_password"

        # Encrypt 10 times
        encrypted_passwords = [
            password_crypto.encrypt_password(plaintext) for _ in range(10)
        ]

        # All should be different (due to random nonce)
        self.assertEqual(len(set(encrypted_passwords)), len(encrypted_passwords))

        # But all should decrypt to same plaintext
        for encrypted in encrypted_passwords:
            self.assertEqual(password_crypto.decrypt_password(encrypted), plaintext)


if __name__ == "__main__":
    unittest.main()
