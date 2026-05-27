# test_imap_client.py
# Comprehensive tests for imap_client module
# Tests message claiming, unclaiming, and event firing

import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import imap_client


class TestClaimMessage(unittest.TestCase):
    """Tests for claim_message function."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = True
        self.args.databasepassword = "test_secret"
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "test_obfuscate"

    def tearDown(self):
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_basic(self, mock_fire_event):
        """Test basic message claiming."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_imap.select.assert_called_once_with("shared/support")
        mock_imap.store.assert_called_once()

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_with_full_headers(self, mock_fire_event):
        """Test claiming message with all header data."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=456,
            actor_moniker="bob",
            message_id="<msg123@example.com>",
            message_from="user@example.com",
            message_subject="Help needed",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertTrue(result)
        
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["message_id"], "<msg123@example.com>")
        self.assertEqual(event_data["from"], "user@example.com")
        self.assertEqual(event_data["subject"], "Help needed")

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_without_imap_conn(self, mock_fire_event):
        """Test claiming message without IMAP connection (event only)."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=789,
            actor_moniker="charlie",
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_fire_event.assert_called_once()

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_fire_event_failure(self, mock_fire_event):
        """Test claiming returns False when fire_event fails."""
        mock_fire_event.return_value = False
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertFalse(result)

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_imap_store_failure(self, mock_fire_event):
        """Test claiming returns False when IMAP store fails."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_imap.select.return_value = ("OK", [b"123"])
        mock_imap.store.side_effect = Exception("IMAP error")
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertFalse(result)

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_event_data_structure(self, mock_fire_event):
        """Test that event data has correct structure."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        imap_client.claim_message(
            self.args,
            mailbox_name="shared/support@example.com",
            message_uid=423,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-claimed")
        self.assertEqual(event_data["actor_moniker"], "alice")

    def test_claim_message_without_optional_params(self):
        """Test claiming message with only required parameters."""
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.return_value = True

            result = imap_client.claim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            self.assertTrue(result)


class TestUnclaimMessage(unittest.TestCase):
    """Tests for unclaim_message function."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = True
        self.args.databasepassword = "test_secret"
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "test_obfuscate"

    def tearDown(self):
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]

    @patch("postoffice.notifyd_client.fire_event")
    def test_unclaim_message_basic(self, mock_fire_event):
        """Test basic message unclaiming."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.unclaim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_imap.select.assert_called_once_with("shared/support")
        
        store_call = mock_imap.store.call_args[0]
        self.assertIn("-FLAGS", store_call[1])

    @patch("postoffice.notifyd_client.fire_event")
    def test_unclaim_message_without_imap_conn(self, mock_fire_event):
        """Test unclaiming message without IMAP connection."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.unclaim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=456,
            actor_moniker="bob",
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_fire_event.assert_called_once()

    @patch("postoffice.notifyd_client.fire_event")
    def test_unclaim_message_event_data(self, mock_fire_event):
        """Test unclaim event has correct data."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        imap_client.unclaim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=789,
            actor_moniker="charlie",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-unclaimed")
        self.assertEqual(event_data["actor_moniker"], "charlie")

    def test_unclaim_message_imap_select_failure(self):
        """Test unclaiming handles IMAP select failure."""
        mock_imap = MagicMock()
        mock_imap.select.side_effect = Exception("Select failed")
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.return_value = True

            result = imap_client.unclaim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            self.assertFalse(result)


class TestFireNewMessageEvent(unittest.TestCase):
    """Tests for fire_new_message_event function."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_new_message_basic(self, mock_fire_event):
        """Test firing new message event."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_new_message_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=1024,
            message_id="<new123@example.com>",
            message_from="sender@example.com",
            message_subject="New message",
            conn=mock_conn,
        )

        self.assertTrue(result)
        mock_fire_event.assert_called_once()

        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-new")
        self.assertIsNone(call_args[1].get("actor_moniker"))

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_new_message_no_connection(self, mock_fire_event):
        """Test firing event without connection."""
        mock_fire_event.return_value = True

        result = imap_client.fire_new_message_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=1024,
            message_id="<msg@example.com>",
            message_from="from@example.com",
            message_subject="Subject",
        )

        self.assertTrue(result)

    def test_fire_new_message_required_params(self):
        """Test that all required params are present."""
        required_params = ["mailbox_name", "message_uid", "message_id", "message_from", "message_subject"]
        
        import inspect
        sig = inspect.signature(imap_client.fire_new_message_event)
        params = list(sig.parameters.keys())
        
        for param in required_params:
            self.assertIn(param, params)


class TestFireFlagChangedEvent(unittest.TestCase):
    """Tests for fire_flag_changed_event function."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_flag_added(self, mock_fire_event):
        """Test firing flag added event."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_flag_changed_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            flag_name="\\Seen",
            added=True,
            actor_moniker="alice",
            conn=mock_conn,
        )

        self.assertTrue(result)
        
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-flagged")
        self.assertTrue(event_data["added"])

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_flag_removed(self, mock_fire_event):
        """Test firing flag removed event."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_flag_changed_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=456,
            flag_name="\\Answered",
            added=False,
            actor_moniker="bob",
            conn=mock_conn,
        )

        self.assertTrue(result)
        
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertFalse(event_data["added"])

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_flag_no_actor(self, mock_fire_event):
        """Test firing flag event without actor."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_flag_changed_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=789,
            flag_name="\\Flagged",
            added=True,
            conn=mock_conn,
        )

        self.assertTrue(result)

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_flag_claimed_by_flag(self, mock_fire_event):
        """Test firing event for claim flag."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_flag_changed_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            flag_name="ClaimedBy_alice",
            added=True,
            actor_moniker="alice",
            conn=mock_conn,
        )

        self.assertTrue(result)


class TestFireMessageDeletedEvent(unittest.TestCase):
    """Tests for fire_message_deleted_event function."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_deleted_basic(self, mock_fire_event):
        """Test firing message deleted event."""
        mock_fire_event.return_value = True
        mock_conn = MagicMock()

        result = imap_client.fire_message_deleted_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=999,
            conn=mock_conn,
        )

        self.assertTrue(result)
        
        call_args = mock_fire_event.call_args
        event_data = call_args[0][3]
        self.assertEqual(event_data["event_type"], "message-deleted")
        self.assertIsNone(call_args[1].get("actor_moniker"))

    @patch("postoffice.notifyd_client.fire_event")
    def test_fire_deleted_no_connection(self, mock_fire_event):
        """Test firing deleted event without connection."""
        mock_fire_event.return_value = True

        result = imap_client.fire_message_deleted_event(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
        )

        self.assertTrue(result)


class TestFlagObfuscationIntegration(unittest.TestCase):
    """Tests for flag obfuscation in claim/unclaim flows."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False
        self.args.databasepassword = "test_secret"

    @patch("postoffice.notifyd_client.get_obfuscate_secret")
    def test_claim_uses_obfuscated_flag(self, mock_get_secret):
        """Test that claim uses obfuscated flag."""
        mock_get_secret.return_value = "obfuscate_secret"
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.return_value = True

            imap_client.claim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            store_call = mock_imap.store.call_args[0]
            flag = store_call[2]
            self.assertIn("ClaimedBy", flag)

    @patch("postoffice.notifyd_client.get_obfuscate_secret")
    def test_unclaim_uses_obfuscated_flag(self, mock_get_secret):
        """Test that unclaim uses obfuscated flag."""
        mock_get_secret.return_value = "obfuscate_secret"
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.return_value = True

            imap_client.unclaim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            store_call = mock_imap.store.call_args[0]
            flag = store_call[2]
            self.assertIn("ClaimedBy", flag)

    @patch("postoffice.notifyd_client.get_obfuscate_secret")
    def test_plain_flag_without_secret(self, mock_get_secret):
        """Test plain flag when no secret available."""
        mock_get_secret.return_value = None
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.return_value = True

            imap_client.claim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="bob",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            store_call = mock_imap.store.call_args[0]
            flag = store_call[2]
            self.assertIn("ClaimedBy", flag)


class TestExceptionHandling(unittest.TestCase):
    """Tests for exception handling in imap_client functions."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = False

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_message_exception_returns_false(self, mock_fire_event):
        """Test that exceptions are caught and False is returned."""
        mock_fire_event.side_effect = Exception("Event fire failed")
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.claim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertFalse(result)

    @patch("postoffice.notifyd_client.fire_event")
    def test_unclaim_message_exception_returns_false(self, mock_fire_event):
        """Test unclaim exception handling."""
        mock_fire_event.side_effect = Exception("Event fire failed")
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        result = imap_client.unclaim_message(
            self.args,
            mailbox_name="shared/support",
            message_uid=123,
            actor_moniker="alice",
            imap_conn=mock_imap,
            conn=mock_conn,
        )

        self.assertFalse(result)

    def test_fire_new_message_exception_returns_false(self):
        """Test new message event exception handling."""
        mock_conn = MagicMock()

        with patch("postoffice.notifyd_client.fire_event") as mock_fire:
            mock_fire.side_effect = Exception("Event fire failed")

            result = imap_client.fire_new_message_event(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                message_id="<msg@example.com>",
                message_from="from@example.com",
                message_subject="Subject",
                conn=mock_conn,
            )

            self.assertFalse(result)


class TestDebugLogging(unittest.TestCase):
    """Tests for debug logging in imap_client functions."""

    def setUp(self):
        self.args = Mock()
        self.args.debug = True
        self.args.databasepassword = "test_secret"
        os.environ["MCFEELY_OBFUSCATE_SECRET"] = "test_obfuscate"

    def tearDown(self):
        if "MCFEELY_OBFUSCATE_SECRET" in os.environ:
            del os.environ["MCFEELY_OBFUSCATE_SECRET"]

    @patch("postoffice.notifyd_client.fire_event")
    def test_claim_debug_output(self, mock_fire_event):
        """Test that debug output is produced when debug is enabled."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("bbsengine6.io.echo") as mock_echo:
            imap_client.claim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            debug_calls = [call for call in mock_echo.call_args_list if call[1].get("level") == "debug"]
            self.assertGreater(len(debug_calls), 0)

    @patch("postoffice.notifyd_client.fire_event")
    def test_unclaim_debug_output(self, mock_fire_event):
        """Test that debug output is produced for unclaim."""
        mock_fire_event.return_value = True
        mock_imap = MagicMock()
        mock_conn = MagicMock()

        with patch("bbsengine6.io.echo") as mock_echo:
            imap_client.unclaim_message(
                self.args,
                mailbox_name="shared/support",
                message_uid=123,
                actor_moniker="alice",
                imap_conn=mock_imap,
                conn=mock_conn,
            )

            debug_calls = [call for call in mock_echo.call_args_list if call[1].get("level") == "debug"]
            self.assertGreater(len(debug_calls), 0)


if __name__ == "__main__":
    unittest.main()