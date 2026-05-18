# test_imap_monitor.py
# Unit tests for imap_monitor module
# Tests state tracking, polling, and event firing

import unittest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from postoffice import imap_monitor


class TestMessageState(unittest.TestCase):
    """Test MessageState dataclass."""
    
    def test_message_state_creation(self):
        """Create message state with defaults."""
        state = imap_monitor.MessageState(uid=123)
        self.assertEqual(state.uid, 123)
        self.assertEqual(len(state.flags), 0)
        self.assertIsNone(state.message_id)
        self.assertIsNone(state.from_addr)
        self.assertIsNone(state.subject)
    
    def test_message_state_with_data(self):
        """Create message state with all fields."""
        state = imap_monitor.MessageState(
            uid=456,
            flags={"\\Seen", "\\Answered"},
            message_id="<abc@example.com>",
            from_addr="user@example.com",
            subject="Test"
        )
        self.assertEqual(state.uid, 456)
        self.assertEqual(len(state.flags), 2)
        self.assertIn("\\Seen", state.flags)


class TestMailboxState(unittest.TestCase):
    """Test MailboxState dataclass."""
    
    def test_mailbox_state_creation(self):
        """Create mailbox state with defaults."""
        state = imap_monitor.MailboxState(mailbox_name="shared/support")
        self.assertEqual(state.mailbox_name, "shared/support")
        self.assertEqual(len(state.messages), 0)
        self.assertIsNone(state.uidvalidity)
        self.assertIsNone(state.last_poll_time)


class TestIMAPMonitorInitialization(unittest.TestCase):
    """Test IMAPMonitor initialization and lifecycle."""
    
    def test_create_monitor(self):
        """Create IMAP monitor instance."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=30)
        
        self.assertEqual(monitor.default_poll_interval, 30)
        self.assertFalse(monitor.running)
        self.assertIsNone(monitor.thread)
        self.assertEqual(len(monitor.mailbox_states), 0)
    
    def test_add_mailbox(self):
        """Add mailbox to monitoring."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args)
        
        monitor.add_mailbox("shared/support")
        self.assertIn("shared/support", monitor.mailbox_states)
        
        state = monitor.mailbox_states["shared/support"]
        self.assertEqual(state.mailbox_name, "shared/support")
    
    def test_remove_mailbox(self):
        """Remove mailbox from monitoring."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args)
        
        monitor.add_mailbox("shared/support")
        self.assertIn("shared/support", monitor.mailbox_states)
        
        monitor.remove_mailbox("shared/support")
        self.assertNotIn("shared/support", monitor.mailbox_states)
    
    def test_add_duplicate_mailbox(self):
        """Adding same mailbox twice is idempotent."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args)
        
        monitor.add_mailbox("shared/support")
        monitor.add_mailbox("shared/support")
        
        self.assertEqual(len(monitor.mailbox_states), 1)


class TestIMAPMonitorThreading(unittest.TestCase):
    """Test IMAPMonitor threading lifecycle."""
    
    def test_start_monitor(self):
        """Start monitor starts background thread."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=60)
        
        monitor.start()
        self.assertTrue(monitor.running)
        self.assertIsNotNone(monitor.thread)
        self.assertTrue(monitor.thread.daemon)
        
        # Cleanup
        monitor.stop(timeout_seconds=1)
        self.assertFalse(monitor.running)
    
    def test_stop_monitor(self):
        """Stop monitor stops background thread."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=60)
        
        monitor.start()
        time.sleep(0.1)  # Let thread start
        
        monitor.stop(timeout_seconds=2)
        self.assertFalse(monitor.running)
    
    def test_start_twice_is_safe(self):
        """Calling start twice doesn't create duplicate threads."""
        args = Mock(debug=False)
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=60)
        
        monitor.start()
        first_thread = monitor.thread
        
        monitor.start()  # Should be no-op
        second_thread = monitor.thread
        
        self.assertIs(first_thread, second_thread)
        
        monitor.stop(timeout_seconds=1)


class TestGlobalMonitorFunctions(unittest.TestCase):
    """Test global monitor instance functions."""
    
    def test_initialize_monitor(self):
        """Initialize global monitor instance."""
        args = Mock(debug=False)
        monitor = imap_monitor.initialize_monitor(args, poll_interval_seconds=30)
        
        self.assertIsNotNone(monitor)
        self.assertEqual(monitor.default_poll_interval, 30)
        
        retrieved = imap_monitor.get_monitor()
        self.assertIs(monitor, retrieved)
    
    def test_start_stop_global_monitor(self):
        """Start and stop global monitor."""
        args = Mock(debug=False)
        monitor = imap_monitor.initialize_monitor(args, poll_interval_seconds=60)
        
        imap_monitor.start_monitor()
        self.assertTrue(monitor.running)
        
        imap_monitor.stop_monitor(timeout_seconds=1)
        self.assertFalse(monitor.running)


class TestMonitorPollInterval(unittest.TestCase):
    """Test poll interval retrieval from config."""
    
    def test_get_poll_interval_from_config(self):
        """Retrieve poll interval from database config."""
        args = Mock(debug=False, databasename="test_db")
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=30)
        
        with patch('postoffice.imap_monitor.database') as mock_db:
            mock_conn = Mock()
            mock_db.connect.return_value = mock_conn
            
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (60,)  # 60 seconds
            mock_cursor.__enter__.return_value = mock_cursor
            mock_db.cursor.return_value = mock_cursor
            
            interval = monitor._get_poll_interval("shared/support")
            
            self.assertEqual(interval, 60)
            mock_db.connect.assert_called_once()
    
    def test_get_poll_interval_default(self):
        """Return default interval if no config found."""
        args = Mock(debug=False, databasename="test_db")
        monitor = imap_monitor.IMAPMonitor(args, poll_interval_seconds=30)
        
        with patch('postoffice.imap_monitor.database') as mock_db:
            mock_conn = Mock()
            mock_db.connect.return_value = mock_conn
            
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None  # No config
            mock_cursor.__enter__.return_value = mock_cursor
            mock_db.cursor.return_value = mock_cursor
            
            interval = monitor._get_poll_interval("shared/unknown")
            
            self.assertEqual(interval, 30)  # Default


if __name__ == "__main__":
    unittest.main()
