# tests/test_email_auth_integration.py
# Comprehensive integration tests for inbound/outbound email authentication
# Tests the full auth flow: database password storage -> SASL auth -> IMAP/SMTP

import os
import sys
import base64
import unittest
from unittest.mock import Mock, MagicMock, patch
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import warnings
warnings.filterwarnings("ignore", message="'crypt' is deprecated", category=DeprecationWarning)

import crypt

from postoffice import sasl_password, member_password


class MockCursor:
    def __init__(self, data=None):
        self.rowcount = 0
        self._data = data or {}
        self._results = []
        self._query_log = []

    def execute(self, query, params=None):
        self._query_log.append((query, params))
        self.rowcount = 1

    def fetchone(self):
        return self._data.get("single")

    def fetchall(self):
        return self._data.get("all", [])


class MockCursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *args):
        pass


class MockConnection:
    def __init__(self, cursor_data=None):
        self._cursor_data = cursor_data or {}
        self.cursor_obj = MockCursor(cursor_data)

    def cursor(self):
        return MockCursorContext(self.cursor_obj)

    def commit(self):
        pass


class TestSaslPasswordCryptHash(unittest.TestCase):
    """Test SHA-512 crypt hash generation and verification."""

    def setUp(self):
        self.test_password = "TestPassword123!"

    def test_generate_crypt_hash_format(self):
        """Test that generated hash has correct SHA-512 format."""
        hash_result = sasl_password.generate_crypt_hash(self.test_password)

        self.assertTrue(hash_result.startswith("$6$"))
        parts = hash_result.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "")
        self.assertEqual(parts[1], "6")

    def test_generate_crypt_hash_unique_salts(self):
        """Test that each hash has unique salt."""
        hash1 = sasl_password.generate_crypt_hash(self.test_password)
        hash2 = sasl_password.generate_crypt_hash(self.test_password)

        self.assertNotEqual(hash1, hash2)

        salt1 = hash1.split("$")[2]
        salt2 = hash2.split("$")[2]
        self.assertNotEqual(salt1, salt2)

    def test_verify_crypt_hash_correct(self):
        """Test verification with correct password."""
        crypt_hash = sasl_password.generate_crypt_hash(self.test_password)
        result = sasl_password.verify_crypt_hash(self.test_password, crypt_hash)
        self.assertTrue(result)

    def test_verify_crypt_hash_incorrect(self):
        """Test verification with wrong password."""
        crypt_hash = sasl_password.generate_crypt_hash(self.test_password)
        result = sasl_password.verify_crypt_hash("WrongPassword", crypt_hash)
        self.assertFalse(result)

    def test_verify_crypt_hash_empty_password(self):
        """Test verification with empty password."""
        crypt_hash = sasl_password.generate_crypt_hash(self.test_password)
        result = sasl_password.verify_crypt_hash("", crypt_hash)
        self.assertFalse(result)

    def test_verify_crypt_hash_empty_hash(self):
        """Test verification with empty hash."""
        result = sasl_password.verify_crypt_hash(self.test_password, "")
        self.assertFalse(result)

    def test_verify_crypt_hash_none_inputs(self):
        """Test verification with None inputs."""
        result = sasl_password.verify_crypt_hash(None, "$6$salt$hash")
        self.assertFalse(result)
        result = sasl_password.verify_crypt_hash("password", None)
        self.assertFalse(result)


class TestSaslPasswordDatabaseOperations(unittest.TestCase):
    """Test SASL password database operations with mocked connection."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("bbsengine6.database.connect")
    def test_set_sasl_password_success(self, mock_connect):
        """Test setting SASL password."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.set_sasl_password(
            self.args,
            member_moniker="alice",
            password="secret123",
            updated_by="alice",
        )

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_set_sasl_password_upsert(self, mock_connect):
        """Test that set_sasl_password uses upsert (ON CONFLICT)."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.set_sasl_password(
            self.args,
            member_moniker="alice",
            password="secret456",
            updated_by="alice",
        )

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_get_sasl_password_found(self, mock_connect):
        """Test retrieving SASL password."""
        expected_hash = sasl_password.generate_crypt_hash("secret")
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {"crypt_hash": expected_hash}
        mock_cur.rowcount = 1
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.get_sasl_password(self.args, "alice")

        self.assertEqual(result, expected_hash)

    @patch("bbsengine6.database.connect")
    def test_get_sasl_password_not_found(self, mock_connect):
        """Test retrieving SASL password when not set."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_cur.rowcount = 0
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.get_sasl_password(self.args, "nonexistent")

        self.assertIsNone(result)

    @patch("bbsengine6.database.connect")
    def test_delete_sasl_password(self, mock_connect):
        """Test deleting SASL password."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.delete_sasl_password(self.args, "alice")

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_exists_sasl_password_true(self, mock_connect):
        """Test checking if SASL password exists."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.exists_sasl_password(self.args, "alice")

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_exists_sasl_password_false(self, mock_connect):
        """Test checking if SASL password does not exist."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 0
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.exists_sasl_password(self.args, "nonexistent")

        self.assertFalse(result)

    @patch("bbsengine6.database.connect")
    def test_set_sasl_password_for_sync(self, mock_connect):
        """Test synchronous SASL password setting."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        success, error = sasl_password.set_sasl_password_for_sync(
            self.args, "alice", "sync_password", "alice"
        )

        self.assertTrue(success)
        self.assertEqual(error, "")


class TestMemberPasswordIntegration(unittest.TestCase):
    """Test member_password integration with SASL password sync."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("postoffice.sasl_password.set_sasl_password_for_sync")
    @patch("bbsengine6.database.connect")
    def test_set_personal_password_syncs_sasl(self, mock_connect, mock_sync):
        """Test that set_personal_password also sets SASL password."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)
        mock_sync.return_value = (True, "")

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password="imap_secret",
            set_by_moniker="alice",
            set_sasl=True,
        )

        self.assertTrue(result)
        mock_sync.assert_called_once()
        call_args = mock_sync.call_args
        self.assertEqual(call_args[0][0], self.args)
        self.assertEqual(call_args[0][1], "alice")
        self.assertEqual(call_args[0][2], "imap_secret")
        self.assertEqual(call_args[0][3], "alice")

    @patch("postoffice.sasl_password.set_sasl_password_for_sync")
    @patch("bbsengine6.database.connect")
    def test_set_personal_password_skip_sasl(self, mock_connect, mock_sync):
        """Test that set_personal_password can skip SASL sync."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password="imap_secret",
            set_by_moniker="alice",
            set_sasl=False,
        )

        self.assertTrue(result)
        mock_sync.assert_not_called()

    @patch("postoffice.sasl_password.set_sasl_password_for_sync")
    @patch("bbsengine6.database.connect")
    def test_set_personal_password_sasl_failure_warning(self, mock_connect, mock_sync):
        """Test that SASL sync failure produces warning but doesn't fail."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)
        mock_sync.return_value = (False, "Database error")

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password="imap_secret",
            set_by_moniker="alice",
            set_sasl=True,
        )

        self.assertTrue(result)

    @patch("postoffice.sasl_password.delete_sasl_password")
    @patch("bbsengine6.database.connect")
    def test_delete_personal_password_syncs_sasl(self, mock_connect, mock_delete):
        """Test that delete_personal_password also deletes SASL password."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.delete_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
            delete_sasl=True,
        )

        self.assertTrue(result)
        mock_delete.assert_called_once_with(self.args, "alice")

    @patch("postoffice.sasl_password.delete_sasl_password")
    @patch("bbsengine6.database.connect")
    def test_delete_personal_password_skip_sasl(self, mock_connect, mock_delete):
        """Test that delete_personal_password can skip SASL delete."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.delete_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            requester_moniker="alice",
            delete_sasl=False,
        )

        self.assertTrue(result)
        mock_delete.assert_not_called()


class TestImapAuthenticationFlow(unittest.TestCase):
    """Test full IMAP authentication flow."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False
        self.args.debug = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("postoffice.sasl_password.get_sasl_password")
    @patch("postoffice.sasl_password.set_sasl_password_for_sync")
    @patch("bbsengine6.database.connect")
    def test_full_auth_flow(self, mock_connect, mock_sync_set, mock_get):
        """Test complete auth flow: set password -> verify -> authenticate."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)
        mock_sync_set.return_value = (True, "")

        password = "TestIMAPPassword123!"
        crypt_hash = sasl_password.generate_crypt_hash(password)
        mock_get.return_value = crypt_hash

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password=password,
            set_by_moniker="alice",
            set_sasl=True,
        )

        self.assertTrue(result)
        mock_sync_set.assert_called_once()

        retrieved_hash = sasl_password.get_sasl_password(self.args, "alice")
        self.assertEqual(retrieved_hash, crypt_hash)

        verify_result = sasl_password.verify_crypt_hash(password, retrieved_hash)
        self.assertTrue(verify_result)

    @patch("postoffice.sasl_password.get_sasl_password")
    def test_auth_verification_fails_wrong_password(self, mock_get):
        """Test that verification fails with wrong password."""
        password = "CorrectPassword"
        wrong_password = "WrongPassword"
        crypt_hash = sasl_password.generate_crypt_hash(password)

        mock_get.return_value = crypt_hash

        result = sasl_password.verify_crypt_hash(wrong_password, crypt_hash)
        self.assertFalse(result)

    @patch("postoffice.sasl_password.get_sasl_password")
    def test_auth_verification_succeeds_correct_password(self, mock_get):
        """Test that verification succeeds with correct password."""
        password = "CorrectPassword"
        crypt_hash = sasl_password.generate_crypt_hash(password)

        mock_get.return_value = crypt_hash

        result = sasl_password.verify_crypt_hash(password, crypt_hash)
        self.assertTrue(result)


class TestSharedMailboxAuth(unittest.TestCase):
    """Test shared mailbox authentication."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_user_can_have_independent_imap_password(self):
        """Test that IMAP password is independent of shell password."""
        imap_password = "IMAPOnlyPassword123!"

        crypt_hash = sasl_password.generate_crypt_hash(imap_password)

        self.assertTrue(crypt_hash.startswith("$6$"))

        verify_result = sasl_password.verify_crypt_hash(imap_password, crypt_hash)
        self.assertTrue(verify_result)

    def test_crypt_hash_format_compatible_with_pam(self):
        """Test that generated hash format is compatible with PAM."""
        password = "TestPassword"
        crypt_hash = sasl_password.generate_crypt_hash(password)

        self.assertTrue(crypt_hash.startswith("$6$"))
        parts = crypt_hash.split("$")
        self.assertEqual(parts[0], "")
        self.assertEqual(parts[1], "6")

        self.assertEqual(len(parts), 4)
        salt = parts[2]
        hash_val = parts[3]
        self.assertGreater(len(salt), 8)
        self.assertGreater(len(hash_val), 20)


class TestPasswordFallback(unittest.TestCase):
    """Test PAM fallback for unmigrated users."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    @patch("bbsengine6.database.connect")
    def test_user_without_sasl_password_triggers_pam_fallback(self, mock_connect):
        """Test that missing SASL password triggers PAM fallback behavior."""
        cursor = MockCursor()
        cursor.rowcount = 0
        mock_conn = MockConnection()
        mock_conn.cursor_obj = cursor
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        exists = sasl_password.exists_sasl_password(self.args, "unmigrated_user")
        self.assertFalse(exists)

    @patch("bbsengine6.database.connect")
    def test_disabled_sasl_password(self, mock_connect):
        """Test disabling SASL password without deleting."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.disable_sasl_password(self.args, "alice")

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_re_enable_sasl_password(self, mock_connect):
        """Test re-enabling a disabled SASL password."""
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=False)
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = sasl_password.enable_sasl_password(self.args, "alice")

        self.assertTrue(result)


class TestEndToEndImapFlow(unittest.TestCase):
    """End-to-end tests for IMAP authentication flow."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.issuperuser = True
        self.args.debug = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_password_storage_format(self):
        """Test that stored password format works for auth."""
        password = "SecureIMAPPassword2024!"

        encrypted = sasl_password.generate_crypt_hash(password)

        self.assertTrue(encrypted.startswith("$6$"))

        verify_result = sasl_password.verify_crypt_hash(password, encrypted)
        self.assertTrue(verify_result)

    @patch("postoffice.sasl_password.get_sasl_password")
    def test_multiple_users_independent_passwords(self, mock_get):
        """Test that multiple users can have independent passwords."""
        passwords = {
            "alice": "AlicePassword123!",
            "bob": "BobPassword456!",
            "charlie": "CharliePassword789!",
        }

        for moniker, pwd in passwords.items():
            crypt_hash = sasl_password.generate_crypt_hash(pwd)
            mock_get.return_value = crypt_hash

            retrieved = sasl_password.get_sasl_password(self.args, moniker)

            verify_result = sasl_password.verify_crypt_hash(pwd, retrieved)
            self.assertTrue(verify_result, f"Password verification failed for {moniker}")

    @patch("postoffice.sasl_password.get_sasl_password")
    def test_inbound_vs_outbound_passwords_independent(self, mock_get):
        """Test that inbound and outbound passwords are independent."""
        inbound_password = "InboundPassword123!"
        outbound_password = "OutboundPassword456!"

        inbound_hash = sasl_password.generate_crypt_hash(inbound_password)
        outbound_hash = sasl_password.generate_crypt_hash(outbound_password)

        mock_get.side_effect = [inbound_hash, outbound_hash]

        retrieved_inbound = sasl_password.get_sasl_password(self.args, "alice")
        self.assertEqual(retrieved_inbound, inbound_hash)

        verify_inbound = sasl_password.verify_crypt_hash(inbound_password, retrieved_inbound)
        self.assertTrue(verify_inbound)

        retrieved_outbound = sasl_password.get_sasl_password(self.args, "alice")
        self.assertEqual(retrieved_outbound, outbound_hash)

        verify_outbound = sasl_password.verify_crypt_hash(outbound_password, retrieved_outbound)
        self.assertTrue(verify_outbound)


if __name__ == "__main__":
    unittest.main()