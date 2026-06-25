# test_audit_log.py
# Tests for audit_log module

import sys
import os
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import audit_log


class TestLogPasswordOperation(unittest.TestCase):
    """Tests for log_password_operation function."""

    def test_log_password_operation_success(self):
        """Test successful password operation logging."""
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

        message = mock_log.call_args[0][0]
        self.assertIn("[PASSWORD]", message)
        self.assertIn("SET", message)
        self.assertIn("type=personal", message)
        self.assertIn("member=alice", message)

    def test_log_password_operation_no_logger(self):
        """Test logging is skipped when no logger provided."""
        result = audit_log.log_password_operation(
            action="delete",
            target_type="shared_mailbox",
            target_moniker="bob",
            password_type="outbound",
            performed_by="admin",
        )

        self.assertTrue(result)

    def test_log_password_operation_with_mailbox_id(self):
        """Test logging with mailbox_id included."""
        mock_log = Mock()

        result = audit_log.log_password_operation(
            action="access",
            target_type="shared_mailbox",
            target_moniker="charlie",
            password_type="inbound",
            performed_by="charlie",
            mailbox_id=42,
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)

        message = mock_log.call_args[0][0]
        self.assertIn("mailbox_id=42", message)

    def test_log_password_operation_with_reason(self):
        """Test logging with reason included."""
        mock_log = Mock()

        result = audit_log.log_password_operation(
            action="auth_fail",
            target_type="personal",
            target_moniker="david",
            password_type="inbound",
            performed_by="system",
            reason="password expired",
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)

        message = mock_log.call_args[0][0]
        self.assertIn("reason=password expired", message)

    def test_log_password_operation_all_actions(self):
        """Test logging all possible actions."""
        mock_log = Mock()

        actions = ["set", "delete", "access", "auth_fail", "update"]

        for action in actions:
            mock_log.reset_mock()
            result = audit_log.log_password_operation(
                action=action,
                target_type="personal",
                target_moniker="alice",
                password_type="inbound",
                performed_by="alice",
                log_entry_fn=mock_log,
            )

            self.assertTrue(result)
            message = mock_log.call_args[0][0]
            self.assertIn(action.upper(), message)

    def test_log_password_operation_exception(self):
        """Test logging handles exceptions gracefully."""
        mock_log = Mock()
        mock_log.side_effect = Exception("Log entry failed")

        result = audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="alice",
            log_entry_fn=mock_log,
        )

        self.assertFalse(result)


class TestLogAuthFailure(unittest.TestCase):
    """Tests for log_auth_failure function."""

    def test_log_auth_failure_personal(self):
        """Test auth failure logging for personal account."""
        mock_log = Mock()

        result = audit_log.log_auth_failure(
            member_moniker="alice",
            password_type="inbound",
            reason="password not found",
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)

        message = mock_log.call_args[0][0]
        self.assertIn("AUTH_FAIL", message)
        self.assertIn("type=personal", message)
        self.assertIn("member=alice", message)

    def test_log_auth_failure_shared_mailbox(self):
        """Test auth failure logging for shared mailbox."""
        mock_log = Mock()

        result = audit_log.log_auth_failure(
            member_moniker="bob",
            password_type="outbound",
            reason="invalid password",
            mailbox_id=123,
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)

        message = mock_log.call_args[0][0]
        self.assertIn("AUTH_FAIL", message)
        self.assertIn("type=shared_mailbox", message)
        self.assertIn("mailbox_id=123", message)

    def test_log_auth_failure_no_logger(self):
        """Test auth failure skips when no logger."""
        result = audit_log.log_auth_failure(
            member_moniker="charlie",
            password_type="inbound",
            reason="permission denied",
        )

        self.assertTrue(result)

    def test_log_auth_failure_uses_system_as_performer(self):
        """Test that auth failures are performed by 'system'."""
        mock_log = Mock()

        result = audit_log.log_auth_failure(
            member_moniker="david",
            password_type="inbound",
            reason="unknown member",
            log_entry_fn=mock_log,
        )

        self.assertTrue(result)

        message = mock_log.call_args[0][0]
        self.assertIn("by=system", message)

    def test_log_auth_failure_message_format(self):
        """Test auth failure message has correct format."""
        mock_log = Mock()

        audit_log.log_auth_failure(
            member_moniker="eve",
            password_type="outbound",
            reason="password expired",
            mailbox_id=5,
            log_entry_fn=mock_log,
        )

        message = mock_log.call_args[0][0]

        self.assertIn("[PASSWORD]", message)
        self.assertIn("AUTH_FAIL", message)
        self.assertIn("type=shared_mailbox", message)
        self.assertIn("member=eve", message)
        self.assertIn("pwd_type=outbound", message)
        self.assertIn("mailbox_id=5", message)
        self.assertIn("reason=password expired", message)


class TestAuditLogMessageFormat(unittest.TestCase):
    """Tests for audit log message format consistency."""

    def test_message_format_components(self):
        """Test that messages contain all expected components."""
        mock_log = Mock()

        audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="admin",
            mailbox_id=5,
            reason="initial setup",
            log_entry_fn=mock_log,
        )

        message = mock_log.call_args[0][0]

        self.assertIn("[PASSWORD]", message)
        self.assertIn("SET", message)
        self.assertIn("type=personal", message)
        self.assertIn("member=alice", message)
        self.assertIn("pwd_type=inbound", message)
        self.assertIn("by=admin", message)
        self.assertIn("mailbox_id=5", message)
        self.assertIn("reason=initial setup", message)

    def test_message_uses_pipe_separator(self):
        """Test that message parts are separated by pipes."""
        mock_log = Mock()

        audit_log.log_password_operation(
            action="delete",
            target_type="shared_mailbox",
            target_moniker="bob",
            password_type="outbound",
            performed_by="charlie",
            log_entry_fn=mock_log,
        )

        message = mock_log.call_args[0][0]
        parts = message.split(" | ")

        self.assertGreater(len(parts), 1)


class TestLogentryIntegration(unittest.TestCase):
    """Integration tests verifying audit_log works with real bbsengine6.util.logentry().

    These tests confirm that:
    - Pre-formatted messages from audit_log pass through logentry() unchanged (BC mode)
    - When logentry() is called with structured kwargs, it produces the new
      '[module] action key=value free_text' format
    """

    def _capture_logentry(self, message, **kwargs):
        """Call real logentry() and capture the formatted output.

        Uses a unique logger name per test so each invocation gets a fresh handler
        (logentry() only adds a handler if no handler of the same type exists).
        """
        import logging
        import io
        import uuid
        from bbsengine6.util import logentry

        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter('%(message)s'))

        unique_name = f"audit_test_{uuid.uuid4().hex[:8]}"
        logentry(message, handler=handler, logger_name=unique_name, **kwargs)
        return buf.getvalue().strip()

    def test_logentry_passes_preformatted_message_through(self):
        """audit_log builds message, logentry() logs it unchanged (no kwargs)."""
        mock_log = Mock()
        audit_log.log_password_operation(
            action="set",
            target_type="personal",
            target_moniker="alice",
            password_type="inbound",
            performed_by="alice",
            log_entry_fn=mock_log,
        )
        preformatted = mock_log.call_args[0][0]

        # Now run that preformatted message through real logentry
        result = self._capture_logentry(preformatted)

        # Real logentry in BC mode (no structured kwargs) just logs the message
        self.assertEqual(result, preformatted)

    def test_logentry_structured_format_with_module(self):
        """Verify the new [module] action format produced by logentry()."""
        result = self._capture_logentry(
            "password set",
            module="postoffice",
            action="set",
            moniker="alice",
            password_type="inbound",
        )

        self.assertIn("[postoffice]", result)
        self.assertIn("set", result)
        self.assertIn("moniker=alice", result)
        self.assertIn("password_type=inbound", result)
        self.assertIn("password set", result)

    def test_logentry_module_brackets_first(self):
        """Verify [module] appears first in structured output."""
        result = self._capture_logentry(
            "msg", module="postoffice", action="delete", moniker="bob"
        )

        self.assertTrue(result.startswith("[postoffice]"))

    def test_logentry_action_after_module(self):
        """Verify action comes immediately after [module]."""
        result = self._capture_logentry(
            "msg", module="postoffice", action="delete", moniker="bob"
        )

        parts = result.split()
        self.assertEqual(parts[0], "[postoffice]")
        self.assertEqual(parts[1], "delete")

    def test_logentry_message_at_end(self):
        """Verify the free-text message appears at the end of structured output."""
        result = self._capture_logentry(
            "auth failure occurred",
            module="postoffice",
            action="auth_fail",
            moniker="alice",
        )

        self.assertTrue(result.endswith("auth failure occurred"))

    def test_logentry_kwargs_pass_through(self):
        """Verify **kwargs fields appear in structured output."""
        result = self._capture_logentry(
            "msg", module="postoffice", action="access", mailbox_id=42, target="shared"
        )

        self.assertIn("mailbox_id=42", result)
        self.assertIn("target=shared", result)

    def test_logentry_skips_falsy_kwargs(self):
        """Verify None/empty kwargs are not in output."""
        result = self._capture_logentry(
            "msg", module="postoffice", action="set", moniker="alice", mailbox_id=None
        )

        self.assertNotIn("mailbox_id=None", result)
        self.assertNotIn("mailbox_id=", result)

    def test_logentry_skips_empty_module(self):
        """Verify empty module does not produce empty brackets."""
        result = self._capture_logentry(
            "plain", action="set", moniker="alice"
        )

        self.assertNotIn("[]", result)
        self.assertIn("plain", result)


if __name__ == "__main__":
    unittest.main()
