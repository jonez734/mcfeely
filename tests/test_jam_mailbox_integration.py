# test_jam_mailbox_integration.py
# Integration tests for user.jam IMAP mailbox CRUD + notifyd events.
# Uses real Cyrus IMAP server on localhost:143.
# - Cyrus admin credentials (cyrus/<password>) for create/delete operations
# - Jam credentials (jam/<password>) for read/write IMAP operations
#
# Passwords are read from environment variables (recommended for CI/automated runs):
#   CYRUS_ADMIN_PASSWORD  - Cyrus admin password
#   JAM_IMAP_PASSWORD     - Jam IMAP password
#
# If not set, getpass() will prompt (interactive only).

import os
import sys
import getpass
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice import cyrus_admin, imap_lib

_ADMIN_PASSWORD: str | None = None
_JAM_PASSWORD: str | None = None

MAILBOX_NAME = "user.jam"
ALT_USER = "testuser"


def _prompt_admin_password() -> str:
    global _ADMIN_PASSWORD
    if _ADMIN_PASSWORD is None:
        _ADMIN_PASSWORD = os.environ.get("CYRUS_ADMIN_PASSWORD", "")
        if not _ADMIN_PASSWORD:
            try:
                import bbsengine6.io.echo as echo

                echo.echo("Hint: set CYRUS_ADMIN_PASSWORD env var to skip this prompt", level="info")
            except Exception:
                pass
            _ADMIN_PASSWORD = getpass.getpass("Cyrus admin password (localhost:143): ")
    return _ADMIN_PASSWORD


def _prompt_jam_password() -> str:
    global _JAM_PASSWORD
    if _JAM_PASSWORD is None:
        _JAM_PASSWORD = os.environ.get("JAM_IMAP_PASSWORD", "")
        if not _JAM_PASSWORD:
            try:
                import bbsengine6.io.echo as echo

                echo.echo("Hint: set JAM_IMAP_PASSWORD env var to skip this prompt", level="info")
            except Exception:
                pass
            _JAM_PASSWORD = getpass.getpass(
                "Jam mailbox password (localhost:993, user.jam): "
            )
    return _JAM_PASSWORD


def _get_admin() -> cyrus_admin.CyrusAdmin:
    password = _prompt_admin_password()
    admin = cyrus_admin.CyrusAdmin(host="localhost", port=143, admin_user="cyrus")
    admin.login(password)
    return admin


def _get_jam_imap():
    import imaplib

    password = _prompt_jam_password()
    imap = imaplib.IMAP4_SSL("localhost", 993)
    imap.login("jam", password)
    return imap


def _get_jam_args() -> Mock:
    args = Mock()
    args.imaphost = "localhost"
    args.imapport = 993
    args.imapuser = "jam"
    args.imappassword = _prompt_jam_password()
    args.debug = False
    args.databasepassword = "test_secret"
    args.databasename = "zoid6test"
    args.databasehost = "localhost"
    args.databaseport = 5432
    return args


def _get_cyrus_args() -> Mock:
    args = Mock()
    args.imaphost = "localhost"
    args.imapport = 993
    args.imapuser = "cyrus"
    args.imappassword = _prompt_admin_password()
    args.debug = False
    args.databasepassword = "test_secret"
    args.databasename = "zoid6test"
    args.databasehost = "localhost"
    args.databaseport = 5432
    return args


def _cleanup_mailbox(name: str) -> None:
    try:
        admin = _get_admin()
        existing = admin.list_mailboxes("", name)
        if existing:
            admin.delete_mailbox(name)
        admin.logout()
    except Exception:
        pass


def _mailbox_exists(name: str) -> bool:
    try:
        admin = _get_admin()
        existing = admin.list_mailboxes("", name)
        admin.logout()
        return bool(existing)
    except Exception:
        return False


def _create_mailbox(name: str) -> None:
    admin = _get_admin()
    if not _mailbox_exists(name):
        admin.create_mailbox(name)
    admin.logout()


class TestMailboxCreate(unittest.TestCase):
    """Tests for mailbox creation via CyrusAdmin."""

    def setUp(self):
        _cleanup_mailbox(MAILBOX_NAME)

    def tearDown(self):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_create_user_mailbox(self):
        admin = _get_admin()
        result = admin.create_user_mailbox("jam", user_rights="lrsd")
        self.assertTrue(result)
        self.assertTrue(_mailbox_exists(MAILBOX_NAME))
        admin.logout()

    def test_create_mailbox_appears_in_list(self):
        admin = _get_admin()
        admin.create_user_mailbox("jam", user_rights="lrsd")
        mailboxes = admin.list_mailboxes("", "*")
        self.assertIn(MAILBOX_NAME, mailboxes)
        admin.logout()

    def test_create_with_custom_acl(self):
        admin = _get_admin()
        admin.create_mailbox(MAILBOX_NAME)
        result = admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        self.assertTrue(result)
        admin.logout()

    def test_create_returns_false_on_duplicate(self):
        _create_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        result = admin.create_mailbox(MAILBOX_NAME)
        self.assertFalse(result)
        admin.logout()


class TestMailboxCreateEvents(unittest.TestCase):
    """Tests for event firing on mailbox creation."""

    def setUp(self):
        _cleanup_mailbox(MAILBOX_NAME)

    def tearDown(self):
        _cleanup_mailbox(MAILBOX_NAME)

    @patch("postoffice.message_client.fire_event")
    def test_create_fires_mailbox_created_event(self, mock_fire_event):
        mock_fire_event.return_value = True
        admin = _get_admin()
        admin.create_user_mailbox("jam", user_rights="lrsd")
        admin.logout()
        self.assertTrue(mock_fire_event.called)
        mock_fire_event.assert_called()


class TestMailboxRead(unittest.TestCase):
    """Tests for mailbox read operations as jam user."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        admin.logout()

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_list_mailboxes_as_jam(self):
        imap = _get_jam_imap()
        typ, data = imap.list("", "*")
        self.assertEqual(typ, "OK")
        names = [item.split()[-1].decode() for item in data if item]
        self.assertIn(MAILBOX_NAME, names)
        imap.logout()

    def test_select_mailbox_ro_as_jam(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        self.assertIsNotNone(imap)
        result = imap_lib.select_mailbox(imap, MAILBOX_NAME, readonly=True)
        self.assertTrue(result)
        imap.logout()

    def test_select_mailbox_rw_as_jam(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        self.assertIsNotNone(imap)
        result = imap_lib.select_mailbox(imap, MAILBOX_NAME, readonly=False)
        self.assertTrue(result)
        imap.logout()

    def test_get_all_uids_empty_mailbox_as_jam(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        self.assertIsNotNone(imap)
        imap_lib.select_mailbox(imap, MAILBOX_NAME, readonly=True)
        uids = imap_lib.get_all_uids(imap)
        self.assertEqual(uids, set())
        imap.logout()


class TestMailboxACLAsJam(unittest.TestCase):
    """Test jam's ACL on user.jam and managing other users' access."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        admin.logout()

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_get_acl_on_own_mailbox_as_jam(self):
        admin = _get_admin()
        acl = admin.get_acl(MAILBOX_NAME)
        self.assertIn("jam", acl)
        self.assertEqual(acl["jam"], "lrsdwa")
        admin.logout()

    def test_jam_can_grant_read_access_as_jam(self):
        _cleanup_mailbox(f"user.{ALT_USER}")
        admin = _get_admin()
        admin.create_user_mailbox(ALT_USER, user_rights="lrsd")
        admin.set_acl(MAILBOX_NAME, ALT_USER, "lr")
        admin.logout()

        imap = _get_jam_imap()
        imap.select(MAILBOX_NAME, readonly=False)
        status, _ = imap.status(MAILBOX_NAME, "(UIDVALIDITY)")
        self.assertEqual(status, "OK")
        imap.logout()

        admin = _get_admin()
        admin.delete_acl(MAILBOX_NAME, ALT_USER)
        admin.delete_mailbox(f"user.{ALT_USER}")
        admin.logout()

    def test_jam_cannot_delete_own_mailbox(self):
        imap = _get_jam_imap()
        imap.select(MAILBOX_NAME)
        typ, _ = imap.delete(MAILBOX_NAME)
        self.assertNotEqual(typ, "OK")
        imap.logout()


class TestMailboxUpdate(unittest.TestCase):
    """Tests for mailbox ACL modifications via admin."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)
        _cleanup_mailbox(f"user.{ALT_USER}")
        admin = _get_admin()
        admin.create_user_mailbox(ALT_USER, user_rights="lrsd")
        admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        admin.logout()

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _cleanup_mailbox(f"user.{ALT_USER}")

    def test_set_acl_grants_access(self):
        admin = _get_admin()
        result = admin.set_acl(MAILBOX_NAME, ALT_USER, "lr")
        self.assertTrue(result)
        acl = admin.get_acl(MAILBOX_NAME)
        self.assertEqual(acl.get(ALT_USER), "lr")
        admin.logout()

    def test_delete_acl_removes_access(self):
        admin = _get_admin()
        admin.set_acl(MAILBOX_NAME, ALT_USER, "lr")
        admin.delete_acl(MAILBOX_NAME, ALT_USER)
        acl = admin.get_acl(MAILBOX_NAME)
        self.assertNotIn(ALT_USER, acl)
        admin.logout()

    def test_add_user_to_shared_mailbox(self):
        admin = _get_admin()
        result = admin.add_user_to_shared_mailbox(MAILBOX_NAME, ALT_USER, "lrs")
        self.assertTrue(result)
        acl = admin.get_acl(MAILBOX_NAME)
        self.assertEqual(acl.get(ALT_USER), "lrs")
        admin.logout()

    def test_remove_user_from_shared_mailbox(self):
        admin = _get_admin()
        admin.add_user_to_shared_mailbox(MAILBOX_NAME, ALT_USER, "lrs")
        admin.remove_user_from_shared_mailbox(MAILBOX_NAME, ALT_USER)
        acl = admin.get_acl(MAILBOX_NAME)
        self.assertNotIn(ALT_USER, acl)
        admin.logout()


class TestMailboxUpdateEvents(unittest.TestCase):
    """Tests for event firing on ACL modifications."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    @patch("postoffice.message_client.fire_event")
    def test_acl_change_fires_event(self, mock_fire_event):
        mock_fire_event.return_value = True
        admin = _get_admin()
        admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        self.assertTrue(mock_fire_event.called)
        admin.logout()


class TestMailboxDelete(unittest.TestCase):
    """Tests for mailbox deletion (admin-only, jam cannot delete own mailbox)."""

    def setUp(self):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)

    def tearDown(self):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_delete_mailbox_as_admin(self):
        admin = _get_admin()
        result = admin.delete_mailbox(MAILBOX_NAME)
        self.assertTrue(result)
        self.assertFalse(_mailbox_exists(MAILBOX_NAME))
        admin.logout()

    def test_delete_removes_from_list(self):
        _create_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        admin.delete_mailbox(MAILBOX_NAME)
        mailboxes = admin.list_mailboxes("", "*")
        self.assertNotIn(MAILBOX_NAME, mailboxes)
        admin.logout()

    def test_delete_nonexistent_returns_false(self):
        _cleanup_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        result = admin.delete_mailbox(MAILBOX_NAME)
        self.assertFalse(result)
        admin.logout()


class TestMailboxDeleteEvents(unittest.TestCase):
    """Tests for event firing on mailbox deletion."""

    def setUp(self):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)

    def tearDown(self):
        _cleanup_mailbox(MAILBOX_NAME)

    @patch("postoffice.message_client.fire_event")
    def test_delete_fires_mailbox_deleted_event(self, mock_fire_event):
        mock_fire_event.return_value = True
        admin = _get_admin()
        admin.delete_mailbox(MAILBOX_NAME)
        self.assertTrue(mock_fire_event.called)
        admin.logout()


class TestCyrusAdminConvenience(unittest.TestCase):
    """Tests for cyrus_admin convenience functions."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_create_shared_mailbox_convenience(self):
        _cleanup_mailbox("user.sharedtest")
        result = cyrus_admin.create_shared_mailbox(
            "sharedtest",
            admin_password=_prompt_admin_password(),
            host="localhost",
            port=143,
            owner="jam",
        )
        self.assertTrue(result)
        self.assertTrue(_mailbox_exists("user.sharedtest"))
        admin = _get_admin()
        admin.delete_mailbox("user.sharedtest")
        admin.logout()


class TestDetectHelpers(unittest.TestCase):
    """Pure unit tests for imap_lib detect helper functions - no IMAP connection needed."""

    def test_detect_new_messages(self):
        current = {1, 2, 3}
        stored = {1}
        new = imap_lib.detect_new_messages(current, stored)
        self.assertEqual(new, {2, 3})

    def test_detect_deleted_messages(self):
        current = {1}
        stored = {1, 2, 3}
        deleted = imap_lib.detect_deleted_messages(current, stored)
        self.assertEqual(deleted, {2, 3})

    def test_detect_flag_changes(self):
        current = {"\\Seen", "\\Flagged"}
        stored = {"\\Seen"}
        added, removed = imap_lib.detect_flag_changes(current, stored)
        self.assertEqual(added, {"\\Flagged"})
        self.assertEqual(removed, set())


class TestImapLibWithJamMailbox(unittest.TestCase):
    """Test imap_lib functions as jam user against user.jam."""

    @classmethod
    def setUpClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)
        _create_mailbox(MAILBOX_NAME)
        admin = _get_admin()
        admin.set_acl(MAILBOX_NAME, "jam", "lrsdwa")
        admin.logout()

    @classmethod
    def tearDownClass(cls):
        _cleanup_mailbox(MAILBOX_NAME)

    def test_connect_cyrus_as_jam(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        self.assertIsNotNone(imap)
        imap.logout()

    def test_connect_cyrus_with_jam_moniker(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args, member_moniker="jam")
        self.assertIsNotNone(imap)
        imap.logout()

    def test_get_imap_credentials_for_jam(self):
        args = _get_jam_args()
        creds = imap_lib.get_imap_credentials(args)
        self.assertIsNotNone(creds)
        self.assertEqual(creds["host"], "localhost")
        self.assertEqual(creds["port"], 993)
        self.assertEqual(creds["username"], "jam")

    def test_get_all_uids_returns_set(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        imap_lib.select_mailbox(imap, MAILBOX_NAME, readonly=True)
        uids = imap_lib.get_all_uids(imap)
        self.assertIsInstance(uids, set)
        imap.logout()

    def test_get_message_flags_on_empty_mailbox(self):
        args = _get_jam_args()
        imap = imap_lib.connect_cyrus(args)
        imap_lib.select_mailbox(imap, MAILBOX_NAME, readonly=True)
        uids = imap_lib.get_all_uids(imap)
        if uids:
            flags = imap_lib.get_message_flags(imap, list(uids)[0])
            self.assertIsInstance(flags, set)
        imap.logout()

    def test_detect_new_messages(self):
        current = {1, 2, 3}
        stored = {1}
        new = imap_lib.detect_new_messages(current, stored)
        self.assertEqual(new, {2, 3})

    def test_detect_deleted_messages(self):
        current = {1}
        stored = {1, 2, 3}
        deleted = imap_lib.detect_deleted_messages(current, stored)
        self.assertEqual(deleted, {2, 3})

    def test_detect_flag_changes(self):
        current = {"\\Seen", "\\Flagged"}
        stored = {"\\Seen"}
        added, removed = imap_lib.detect_flag_changes(current, stored)
        self.assertEqual(added, {"\\Flagged"})
        self.assertEqual(removed, set())


if __name__ == "__main__":
    unittest.main()