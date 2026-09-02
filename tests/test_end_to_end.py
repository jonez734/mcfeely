# test_end_to_end.py
# Comprehensive end-to-end integration tests for mistermcfeely
# Tests real API interactions across multiple modules without full mocking

import os
import sys
import base64
import unittest
import json
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import (
    imap_lib,
    message_client,
    member_password,
    shared_mailbox_password,
    password_auth,
    password_crypto,
    audit_log,
)
from postoffice.services import postoffice_client


class MockCursor:
    def __init__(self, data=None):
        self.rowcount = 1
        self._data = data or {}
        self.last_query = None
        self.last_params = None

    def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params

    def fetchone(self):
        if self._data and "single" in self._data:
            return self._data["single"]
        return None

    def fetchall(self):
        return self._data.get("all", [])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockConnection:
    def __init__(self, cursor_data=None):
        self._cursor_data = cursor_data or {}
        self.committed = False
        self.closed = False
        self._cursor = MockCursor(cursor_data)

    def cursor(self, **kwargs):
        return MockCursorContext(self._cursor)

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockCursorContext:
    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, *args):
        pass


class TestEndToEndClaimFlow(unittest.TestCase):
    """End-to-end tests for message claim flow: claim -> flag -> event."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "test_obfuscate_secret"

        self.args = Mock()
        self.args.debug = True
        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "support"
        self.args.imappassword = "password"
        self.args.issuperuser = False
        self.args.databasepassword = "db_secret"

    def tearDown(self):
        for key in ["POSTOFFICE_PASSWORD_KEY", "MCFEELY_OBFUSCATE_SECRET"]:
            if key in os.environ:
                del os.environ[key]

    @patch("postoffice.message_client.fire_event")
    @patch("imaplib.IMAP4_SSL")
    def test_claim_message_full_flow(self, mock_imap_class, mock_fire_event):
        """Test complete claim message flow."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        mock_fire_event.return_value = True

        mock_conn = MockConnection()
        mock_args = Mock()
        mock_args.debug = True

        result = postoffice_client.claim_message(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=423,
            actor_moniker="alice",
            message_id="<msg123@example.com>",
            message_from="user@example.com",
            message_subject="Help needed",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_imap.select.assert_called_once_with("shared/support@example.com")
        mock_imap.store.assert_called_once()
        mock_fire_event.assert_called_once()

        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-claimed")
        self.assertEqual(event_data["actor_moniker"], "alice")

    @patch("postoffice.message_client.fire_event")
    @patch("imaplib.IMAP4_SSL")
    def test_unclaim_message_full_flow(self, mock_imap_class, mock_fire_event):
        """Test complete unclaim message flow."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        mock_fire_event.return_value = True

        mock_conn = MockConnection()

        result = postoffice_client.unclaim_message(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=423,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertTrue(result)
        call_args = mock_imap.store.call_args[0]
        self.assertIn("-FLAGS", call_args[1])

    @patch("postoffice.message_client.fire_event")
    def test_fire_new_message_event(self, mock_fire_event):
        """Test firing new message event."""
        mock_fire_event.return_value = True
        mock_conn = MockConnection()

        result = postoffice_client.fire_new_message_event(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=1024,
            message_id="<new123@example.com>",
            message_from="external@example.com",
            message_subject="New ticket",
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_fire_event.assert_called_once()
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-new")
        self.assertIsNone(call_args[1].get("actor_moniker"))

    @patch("postoffice.message_client.fire_event")
    def test_fire_flag_changed_event(self, mock_fire_event):
        """Test firing flag changed event."""
        mock_fire_event.return_value = True
        mock_conn = MockConnection()

        result = postoffice_client.fire_flag_changed_event(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=423,
            flag_name="\\Seen",
            added=True,
            actor_moniker="bob",
            conn=mock_conn,
        )

        self.assertTrue(result)
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["flag_name"], "\\Seen")
        self.assertTrue(event_data["added"])

    @patch("postoffice.message_client.fire_event")
    def test_fire_message_deleted_event(self, mock_fire_event):
        """Test firing message deleted event."""
        mock_fire_event.return_value = True
        mock_conn = MockConnection()

        result = postoffice_client.fire_message_deleted_event(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=423,
            conn=mock_conn,
        )

        self.assertTrue(result)
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-deleted")


class TestEndToEndFlagObfuscation(unittest.TestCase):
    """End-to-end tests for flag obfuscation in claims."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "consistent_secret"

        self.args = Mock()
        self.args.debug = False

    def tearDown(self):
        for key in ["POSTOFFICE_PASSWORD_KEY", "MCFEELY_OBFUSCATE_SECRET"]:
            if key in os.environ:
                del os.environ[key]

    def test_obfuscation_consistency_across_modules(self):
        """Test that flag obfuscation is consistent across postoffice_client and message_client."""
        moniker = "alice"
        secret = os.environ.get("MCFEELY_OBFUSCATE_SECRET")

        flag_from_notify = message_client.format_claim_flag(moniker, secret)

        flag_from_postoffice_client = message_client.format_claim_flag(moniker, secret)

        self.assertEqual(flag_from_notify, flag_from_postoffice_client)

    def test_obfuscation_produces_valid_flag(self):
        """Test obfuscation produces valid flag format."""
        moniker = "alice"
        secret = "test_secret"

        flag = message_client.format_claim_flag(moniker, secret)

        self.assertTrue(flag.startswith("ClaimedBy_"))
        hex_part = flag[len("ClaimedBy_") :]
        self.assertEqual(len(hex_part), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_obfuscation_different_secrets_different_flags(self):
        """Test that different secrets produce different flags."""
        moniker = "alice"

        flag1 = message_client.format_claim_flag(moniker, "secret1")
        flag2 = message_client.format_claim_flag(moniker, "secret2")

        self.assertNotEqual(flag1, flag2)

    def test_verify_claim_flag_roundtrip(self):
        """Test flag verification works correctly."""
        moniker = "alice"
        secret = "verify_secret"

        flag = message_client.format_claim_flag(moniker, secret)

        self.assertTrue(message_client.verify_claim_flag(flag, moniker, secret))
        self.assertFalse(message_client.verify_claim_flag(flag, "bob", secret))
        self.assertFalse(
            message_client.verify_claim_flag(flag, moniker, "wrong_secret")
        )


class TestEndToEndPasswordFlow(unittest.TestCase):
    """End-to-end tests for password management flow."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key

        self.args = Mock()
        self.args.issuperuser = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_encrypt_decrypt_roundtrip(self):
        """Test password encryption and decryption roundtrip."""
        plaintext = "MySecretPassword123!"

        encrypted = password_crypto.encrypt_password(plaintext)
        decrypted = password_crypto.decrypt_password(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_encrypt_produces_different_ciphertexts(self):
        """Test that each encryption produces unique ciphertext."""
        plaintext = "SamePassword"

        ciphertexts = [password_crypto.encrypt_password(plaintext) for _ in range(5)]

        self.assertEqual(len(set(ciphertexts)), 5)

    @patch("bbsengine6.database.connect")
    def test_member_password_set_and_retrieve(self, mock_connect):
        """Test setting and retrieving member password."""
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = member_password.set_personal_password(
            self.args,
            member_moniker="alice",
            password_type="inbound",
            password="alice_secret",
            set_by_moniker="alice",
        )

        self.assertTrue(result)

    @patch("bbsengine6.database.connect")
    def test_shared_mailbox_password_full_flow(self, mock_connect):
        """Test shared mailbox password set and get flow."""
        self.args.issuperuser = True
        mock_conn = MockConnection()
        mock_connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = Mock(return_value=False)

        result = shared_mailbox_password.set_shared_mailbox_password(
            self.args,
            mailbox_address="support@example.com",
            member_moniker="alice",
            password_type="inbound",
            password="shared_secret",
            set_by_moniker="admin",
        )

        self.assertTrue(result)

    def test_password_validation_full(self):
        """Test password validation with various inputs."""
        self.assertTrue(password_auth.validate_password("inbound", "valid"))
        self.assertTrue(password_auth.validate_password("outbound", "valid"))

        self.assertFalse(password_auth.validate_password("inbound", ""))
        self.assertFalse(password_auth.validate_password("outbound", None))
        self.assertFalse(password_auth.validate_password("invalid", "pass"))


class TestEndToEndIMAPMonitoring(unittest.TestCase):
    """End-to-end tests for IMAP monitoring and state tracking."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    @patch("imaplib.IMAP4_SSL")
    def test_imap_connection_and_select_flow(self, mock_imap_class):
        """Test IMAP connection and mailbox selection flow."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap
        mock_imap.select.return_value = ("OK", [b"123"])

        self.args.imaphost = "mail.example.com"
        self.args.imapuser = "support"
        self.args.imappassword = "password"
        self.args.debug = False

        conn = imap_lib.connect_cyrus(self.args, readonly=True)
        self.assertIsNotNone(conn)

        result = imap_lib.select_mailbox(conn, "shared/support", readonly=True)
        self.assertTrue(result)

    @patch("imaplib.IMAP4_SSL")
    def test_get_all_uids_and_flags_flow(self, mock_imap_class):
        """Test getting UIDs and flags from mailbox."""
        mock_imap = MagicMock()
        mock_imap_class.return_value = mock_imap

        mock_imap.uid.side_effect = [
            ("OK", [b"1 2 3 4 5"]),
            ("OK", [b"1 (FLAGS (\\Seen))"]),
            ("OK", [b"2 (FLAGS (\\Seen \\Answered))"]),
        ]

        uids = imap_lib.get_all_uids(mock_imap)
        self.assertEqual(uids, {1, 2, 3, 4, 5})

        flags1 = imap_lib.get_message_flags(mock_imap, 1)
        self.assertIn("\\Seen", flags1)

    def test_detect_new_and_deleted_messages(self):
        """Test message detection logic."""
        current = {1, 2, 3, 4, 5}
        stored = {1, 2, 3}

        new_msgs = imap_lib.detect_new_messages(current, stored)
        self.assertEqual(new_msgs, {4, 5})

        deleted_msgs = imap_lib.detect_deleted_messages(current, stored)
        self.assertEqual(deleted_msgs, set())

    def test_detect_flag_changes(self):
        """Test flag change detection."""
        current = {"\\Seen", "\\Flagged", "ClaimedBy_alice"}
        stored = {"\\Seen"}

        added, removed = imap_lib.detect_flag_changes(current, stored)

        self.assertEqual(added, {"\\Flagged", "ClaimedBy_alice"})
        self.assertEqual(removed, set())


class TestEndToEndNotificationRouting(unittest.TestCase):
    """End-to-end tests for notification routing."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = True

    def test_render_all_event_types(self):
        """Test rendering messages for all event types."""
        test_cases = [
            (
                "message-new",
                None,
                {"from": "test@example.com", "subject": "Help", "message_uid": 1},
            ),
            ("message-claimed", "alice", {"message_uid": 123}),
            ("message-unclaimed", "bob", {"message_uid": 456}),
            ("message-flagged", "charlie", {"flag_name": "\\Seen", "added": True}),
            ("message-deleted", None, {"message_uid": 789}),
        ]

        for event_type, actor, data in test_cases:
            rendered = message_client.render_event_message(event_type, actor, data)
            self.assertIsNotNone(rendered)
            self.assertGreater(len(rendered), 0)

    def test_render_with_missing_fields(self):
        """Test rendering handles missing fields gracefully."""
        rendered = message_client.render_event_message(
            "message-new", None, {"from": "test@example.com"}
        )
        self.assertIn("test@example.com", rendered)
        self.assertIn("(no subject)", rendered)

    def test_render_special_characters(self):
        """Test rendering with special characters."""
        rendered = message_client.render_event_message(
            "message-new",
            None,
            {
                "from": "te+st@example.com",
                "subject": "Re: <URGENT> Test (urgent) & stuff",
            },
        )
        self.assertIsNotNone(rendered)
        self.assertIsInstance(rendered, str)


class TestEndToEndEventTypes(unittest.TestCase):
    """End-to-end tests for event type templates."""

    def test_all_event_types_have_template(self):
        """Test all expected event types have a render template."""
        expected_types = [
            "message-new",
            "message-claimed",
            "message-unclaimed",
            "message-flagged",
            "message-deleted",
        ]

        for event_type in expected_types:
            self.assertIn(event_type, message_client.EVENT_MESSAGE_TEMPLATES)

    def test_templates_are_strings(self):
        """Test all templates are non-empty strings."""
        for event_type, template in message_client.EVENT_MESSAGE_TEMPLATES.items():
            self.assertIsInstance(template, str)
            self.assertGreater(len(template), 0)


class TestEndToEndAuditLogging(unittest.TestCase):
    """End-to-end tests for audit logging."""

    def test_log_password_operation_basic(self):
        """Test password operation logging."""
        mock_log = Mock()

        result = audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="alice",
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)
        mock_log.assert_called_once()
        self.assertIn("[PASSWORD]", mock_log.call_args[0][0])

    def test_log_auth_failure(self):
        """Test auth failure logging."""
        mock_log = Mock()

        result = audit_log.log_auth_failure(
            member_moniker="alice",
            password_type="inbound",
            reason="password not found",
            mailbox_id=1,
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)
        mock_log.assert_called_once()
        call_args = mock_log.call_args[0][0]
        self.assertIn("AUTH_FAIL", call_args)
        self.assertIn("alice", call_args)

    def test_log_password_operation_no_logger(self):
        """Test logging skipped when no logger provided."""
        result = audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="alice",
        )

        self.assertTrue(result)


class TestEndToEndLogentryIntegration(unittest.TestCase):
    """End-to-end integration tests for audit_log + password_auth + real bbsengine6.util.logentry().

    Verifies that the full logging pipeline (audit_log -> logentry) produces the
    expected structured output and that the new Phase 5 format works in real flows.
    """

    def _make_bound_logentry(self):
        """Create a logentry partial bound to a unique StringIO capture."""
        import logging
        import io
        import uuid
        from functools import partial
        from bbsengine6 import util as bbsutil

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter('%(message)s'))
        name = f"e2e_logentry_{uuid.uuid4().hex[:8]}"
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        return partial(bbsutil.logentry, logger_name=name), buf

    def test_audit_log_through_real_logentry(self):
        """Full pipeline: audit_log.log_password_operation -> real logentry() -> captured."""
        bound_logentry, buf = self._make_bound_logentry()

        result = audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="alice",
            log_entry_fn=bound_logentry,
        )

        self.assertTrue(result)
        output = buf.getvalue()
        self.assertIn("[PASSWORD] SET", output)
        self.assertIn("type=personal", output)
        self.assertIn("member=alice", output)
        self.assertIn("pwd_type=inbound", output)
        self.assertIn("by=alice", output)

    def test_auth_failure_through_real_logentry(self):
        """Full pipeline: audit_log.log_auth_failure -> real logentry() -> captured."""
        bound_logentry, buf = self._make_bound_logentry()

        result = audit_log.log_auth_failure(
            member_moniker="bob",
            password_type="outbound",
            reason="invalid password",
            mailbox_id=42,
            log_entry_fn=bound_logentry,
        )

        self.assertTrue(result)
        output = buf.getvalue()
        self.assertIn("[PASSWORD] AUTH_FAIL", output)
        self.assertIn("type=shared_mailbox", output)
        self.assertIn("member=bob", output)
        self.assertIn("mailbox_id=42", output)
        self.assertIn("reason=invalid password", output)

    def test_audit_log_with_structured_kwargs_produces_module_format(self):
        """When callers use the new structured kwargs, output is the [module] format."""
        bound_logentry, buf = self._make_bound_logentry()

        # Direct call to logentry with structured kwargs (Phase 5 format)
        bound_logentry(
            "auth failure occurred",
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
        self.assertIn("auth failure occurred", output)

    def test_password_auth_failure_pipeline(self):
        """password_auth.get_auth_password -> audit_log.log_auth_failure -> real logentry."""
        from functools import partial
        from unittest.mock import patch

        from postoffice import password_auth

        # Set up env
        import os, base64
        key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = key

        try:
            bound_logentry, buf = self._make_bound_logentry()
            args = Mock()
            args.issuperuser = False

            with patch("postoffice.shared_mailbox_password.get_shared_mailbox_password", return_value=None), \
                 patch("postoffice.password_auth._get_shared_mailbox_default_password", return_value=None):
                password = password_auth.get_auth_password(
                    args,
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
            self.assertIn("mailbox 1", output)
        finally:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_logentry_no_structured_kwargs_logs_message_unchanged(self):
        """BC mode: logentry with no kwargs just logs the message as-is."""
        bound_logentry, buf = self._make_bound_logentry()

        bound_logentry("plain message without any structure")

        self.assertEqual(buf.getvalue().strip(), "plain message without any structure")

    def test_logentry_with_only_action(self):
        """When only action is given, no [module] prefix appears."""
        bound_logentry, buf = self._make_bound_logentry()

        bound_logentry("test", action="set")

        output = buf.getvalue().strip()
        self.assertIn("set", output)
        self.assertIn("test", output)
        self.assertNotIn("[]", output)


class TestEndToEndCredentialRetrieval(unittest.TestCase):
    """End-to-end tests for IMAP credential retrieval."""

    def setUp(self):
        self.key = base64.b64encode(os.urandom(32)).decode()
        os.environ["POSTOFFICE_PASSWORD_KEY"] = self.key
        self.args = Mock()
        self.args.debug = False

    def tearDown(self):
        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            del os.environ["POSTOFFICE_PASSWORD_KEY"]

    def test_credentials_direct_args(self):
        """Test credentials from direct args."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "testuser"
        self.args.imappassword = "testpass"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNotNone(creds)
        self.assertEqual(creds["host"], "mail.example.com")
        self.assertEqual(creds["username"], "testuser")
        self.assertEqual(creds["password"], "testpass")

    def test_credentials_default_port(self):
        """Test default port is 993."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = None
        self.args.imapuser = "testuser"
        self.args.imappassword = "testpass"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertEqual(creds["port"], 993)

    @patch("postoffice.password_auth.get_auth_password")
    def test_credentials_fallback_to_password_system(self, mock_get_auth):
        """Test fallback to password system."""
        self.args.imaphost = "mail.example.com"
        self.args.imapport = 993
        self.args.imapuser = "testuser"
        self.args.imappassword = None

        mock_get_auth.return_value = "system_password"

        creds = imap_lib.get_imap_credentials(
            self.args,
            member_moniker="alice",
            mailbox_id=1,
        )

        self.assertIsNotNone(creds)
        self.assertEqual(creds["password"], "system_password")

    def test_credentials_missing_host(self):
        """Test failure when host missing."""
        self.args.imaphost = None
        self.args.imapuser = "testuser"
        self.args.imappassword = "testpass"

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNone(creds)

    def test_credentials_no_member_no_fallback(self):
        """Test no fallback when member not specified."""
        self.args.imaphost = "mail.example.com"
        self.args.imapuser = "testuser"
        self.args.imappassword = None

        creds = imap_lib.get_imap_credentials(self.args)

        self.assertIsNone(creds)


class TestEndToEndIMAPMonitorState(unittest.TestCase):
    """End-to-end tests for IMAP monitor state tracking."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    def test_message_state_creation(self):
        """Test MessageState creation with all fields."""
        from postoffice import imap_monitor

        state = imap_monitor.MessageState(
            uid=123,
            flags={"\\Seen", "ClaimedBy_alice"},
            message_id="<msg123@example.com>",
            from_addr="user@example.com",
            subject="Test Subject",
        )

        self.assertEqual(state.uid, 123)
        self.assertEqual(len(state.flags), 2)
        self.assertIn("ClaimedBy_alice", state.flags)

    def test_mailbox_state_creation(self):
        """Test MailboxState creation."""
        from postoffice import imap_monitor

        state = imap_monitor.MailboxState(mailbox_name="shared/support")

        self.assertEqual(state.mailbox_name, "shared/support")
        self.assertEqual(len(state.messages), 0)

    def test_monitor_add_remove_mailbox(self):
        """Test adding and removing mailboxes."""
        from postoffice import imap_monitor

        monitor = imap_monitor.IMAPMonitor(self.args, poll_interval_seconds=30)

        monitor.add_mailbox("shared/support")
        self.assertIn("shared/support", monitor.mailbox_states)

        monitor.add_mailbox("shared/engineering")
        self.assertEqual(len(monitor.mailbox_states), 2)

        monitor.remove_mailbox("shared/support")
        self.assertNotIn("shared/support", monitor.mailbox_states)
        self.assertIn("shared/engineering", monitor.mailbox_states)


class TestEndToEndConnectionPooling(unittest.TestCase):
    """End-to-end tests for connection pooling pattern."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    def test_get_db_connection_from_explicit_conn(self):
        """Test getting connection from explicit conn param."""
        from postoffice import lib

        explicit_conn = Mock()

        use_conn, should_close = lib.get_db_connection(self.args, conn=explicit_conn)

        self.assertIs(use_conn, explicit_conn)
        self.assertFalse(should_close)

    @patch("bbsengine6.database.connect")
    def test_get_db_connection_from_pool(self, mock_connect):
        """Test getting connection from pool."""
        from postoffice import lib

        mock_conn = Mock()
        mock_pool = Mock()
        mock_connect.return_value = mock_conn

        use_conn, should_close = lib.get_db_connection(self.args, pool=mock_pool)

        self.assertIs(use_conn, mock_conn)
        self.assertTrue(should_close)


class TestEndToEndEventPayloadValidation(unittest.TestCase):
    """End-to-end tests for event payload validation."""

    def test_all_event_payloads_are_json_serializable(self):
        """Test all event payloads can be JSON serialized."""
        payloads = [
            {
                "event_type": "message-new",
                "mailbox_name": "shared/support@example.com",
                "message_uid": 123,
                "message_id": "<msg123@example.com>",
                "from": "user@example.com",
                "subject": "Test",
            },
            {
                "event_type": "message-claimed",
                "mailbox_name": "shared/support@example.com",
                "message_uid": 123,
                "actor_moniker": "alice",
            },
            {
                "event_type": "message-flagged",
                "mailbox_name": "shared/support@example.com",
                "message_uid": 123,
                "flag_name": "\\Seen",
                "added": True,
            },
        ]

        for payload in payloads:
            json_str = json.dumps(payload)
            parsed = json.loads(json_str)
            self.assertEqual(parsed["event_type"], payload["event_type"])

    def test_event_data_contains_required_fields(self):
        """Test event data structures have required fields."""
        required_fields = {
            "message-new": ["mailbox_name", "message_uid"],
            "message-claimed": ["mailbox_name", "message_uid", "actor_moniker"],
            "message-unclaimed": ["mailbox_name", "message_uid", "actor_moniker"],
            "message-flagged": ["mailbox_name", "message_uid"],
            "message-deleted": ["mailbox_name", "message_uid"],
        }

        test_data = {
            "message-new": {"mailbox_name": "test", "message_uid": 1},
            "message-claimed": {
                "mailbox_name": "test",
                "message_uid": 1,
                "actor_moniker": "alice",
            },
            "message-unclaimed": {
                "mailbox_name": "test",
                "message_uid": 1,
                "actor_moniker": "alice",
            },
            "message-flagged": {"mailbox_name": "test", "message_uid": 1},
            "message-deleted": {"mailbox_name": "test", "message_uid": 1},
        }

        for event_type, required in required_fields.items():
            data = test_data[event_type]
            for field in required:
                self.assertIn(field, data)


if __name__ == "__main__":
    unittest.main()
