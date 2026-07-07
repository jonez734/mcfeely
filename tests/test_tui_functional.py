# test_tui_functional.py
# Tests for functional TUI modules (address_manager, address_domain, address, projects, etc.)

import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice.tui import address_manager, address_domain, address, projects


class TestAddressManager(unittest.TestCase):
    """Tests for address_manager.run() and helper functions."""

    def setUp(self):
        self.mock_args = MagicMock()
        self.mock_args.loginid = "testuser"
        self.mock_args.issuperuser = False
        self.mock_args.databasename = "testdb"
        self.mock_args.databaseuser = "testuser"
        self.mock_args.databasepassword = ""
        self.mock_args.databasehost = "localhost"
        self.mock_args.databaseport = 5432

    def test_help_returns_string(self):
        """Test _help() returns a string with menu options."""
        result = address_manager._help()
        self.assertIsInstance(result, str)
        self.assertIn("domains", result)

    def test_settings_help_returns_string(self):
        """Test _settings_help() returns a string."""
        result = address_manager._settings_help()
        self.assertIsInstance(result, str)
        self.assertIn("generate", result)

    def test_sanitize_domain_replaces_dots_and_dashes(self):
        """Test _sanitize_domain() replaces dots and dashes with underscores."""
        self.assertEqual(address_manager._sanitize_domain("foo.bar.com"), "foo_bar_com")
        self.assertEqual(
            address_manager._sanitize_domain("my-domain.org"), "my_domain_org"
        )

    def test_run_returns_1_on_db_error(self):
        """Test run() returns 1 when database pool cannot be acquired."""
        with patch.object(address_manager, "echo"):
            with patch.object(address_manager, "database") as mock_db:
                mock_db.getpool.side_effect = Exception("db error")
                result = address_manager.run(self.mock_args, "testuser")
                self.assertEqual(result, 1)

    def test_run_closes_pool_when_created(self):
        """Test run() closes the pool it created in the finally block."""
        mock_pool = MagicMock()

        with patch.object(address_manager, "echo"):
            with patch.object(address_manager, "database") as mock_db:
                mock_db.getpool.return_value = mock_pool

                with patch.object(address_manager, "inputchoice") as mock_choice:
                    mock_choice.return_value = "Q"

                    address_manager.run(self.mock_args, "testuser")

                    mock_pool.closeall.assert_called_once()

    def test_run_calls_address_domain_run(self):
        """Test run() dispatches to address_domain.run() on D choice."""
        mock_pool = MagicMock()

        with patch.object(address_manager, "echo"):
            with patch.object(address_manager, "database") as mock_db:
                mock_db.getpool.return_value = mock_pool
                mock_db.connect.return_value.__enter__ = MagicMock(
                    return_value=MagicMock()
                )
                mock_db.connect.return_value.__exit__ = MagicMock(return_value=False)
                mock_db.connect.return_value.cursor.return_value.__enter__ = MagicMock()
                mock_db.connect.return_value.cursor.return_value.__exit__ = MagicMock()
                mock_db.connect.return_value.cursor.return_value.fetchall.return_value = []

                with patch.object(address_manager, "inputchoice") as mock_choice:
                    with patch.object(address_manager, "address_domain") as mock_ad:
                        with patch.object(address_manager, "Listbox") as mock_lb:
                            mock_result = MagicMock()
                            mock_result.status = "selected"
                            mock_result.item = MagicMock()
                            mock_result.item.data = {
                                "id": 1,
                                "name": "test.com",
                                "enabled": True,
                            }
                            mock_lb.return_value.run.return_value = mock_result

                            choice_sequence = ["D", "Q"]
                            mock_choice.side_effect = lambda *args, **kwargs: (
                                choice_sequence.pop(0)
                            )

                            address_manager.run(self.mock_args, "testuser")

                            mock_ad.run.assert_called_once()


class TestAddressDomain(unittest.TestCase):
    """Tests for address_domain helper functions."""

    def setUp(self):
        self.mock_args = MagicMock()
        self.mock_args.loginid = "testuser"

    def test_help_returns_string(self):
        """Test _help() returns a string."""
        result = address_domain._help()
        self.assertIsInstance(result, str)
        self.assertIn("list", result)


class TestAddress(unittest.TestCase):
    """Tests for address helper functions."""

    def test_help_returns_string(self):
        """Test _help() returns a string."""
        result = address._help()
        self.assertIsInstance(result, str)
        self.assertIn("list", result)

    def test_local_part_pattern_valid(self):
        """Test LOCAL_PART_PATTERN matches valid local parts."""
        self.assertTrue(address.LOCAL_PART_PATTERN.match("john"))
        self.assertTrue(address.LOCAL_PART_PATTERN.match("john.doe"))
        self.assertTrue(address.LOCAL_PART_PATTERN.match("john_doe"))
        self.assertTrue(address.LOCAL_PART_PATTERN.match("john-doe"))
        self.assertTrue(address.LOCAL_PART_PATTERN.match("user123"))

    def test_local_part_pattern_invalid(self):
        """Test LOCAL_PART_PATTERN rejects invalid local parts."""
        self.assertFalse(address.LOCAL_PART_PATTERN.match("john@doe"))
        self.assertFalse(address.LOCAL_PART_PATTERN.match("john doe"))
        self.assertFalse(address.LOCAL_PART_PATTERN.match("john!doe"))


class TestProjects(unittest.TestCase):
    """Tests for projects helper functions."""

    def setUp(self):
        self.mock_args = MagicMock()
        self.mock_args.loginid = "testuser"
        self.mock_args.issuperuser = True

    def test_help_returns_string(self):
        """Test _help() returns a string."""
        result = projects._help()
        self.assertIsInstance(result, str)
        self.assertIn("list", result)

    def test_show_help_calls_echo(self):
        """Test _show_help() calls echo."""
        with patch.object(projects, "echo") as mock_echo:
            with patch.object(projects, "heading"):
                projects._show_help()
                self.assertTrue(mock_echo.called)

    def test_run_returns_1_when_not_sysop(self):
        """Test run() returns 1 when user is not admin."""
        self.mock_args.issuperuser = False

        with patch.object(projects, "echo"):
            with patch.object(projects, "database") as mock_db:
                mock_db.getpool.return_value = MagicMock()
                result = projects.run(self.mock_args, "testuser")
                self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
