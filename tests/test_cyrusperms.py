# test_cyrusperms.py
# Tests for postoffice.lib.cyrusperms()

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from postoffice.lib import cyrusperms, CYRUS_PERMISSIONS

BBS_TAG_RE = re.compile(r"\{[^}]+\}")


def strip_bbs_tags(s: str) -> str:
    """Remove BBS color/template tags for plain text comparison."""
    return BBS_TAG_RE.sub("", s)


class TestCyrusperms(unittest.TestCase):
    """Tests for cyrusperms() function."""

    def test_basic_concatenated_string(self):
        """Test basic concatenated permission string."""
        result = strip_bbs_tags(cyrusperms("lr"))
        self.assertEqual(result, "lookup and read")

    def test_three_permissions(self):
        """Test three permissions uses Oxford comma."""
        result = strip_bbs_tags(cyrusperms("lrs"))
        self.assertEqual(result, "lookup, read, and seen")

    def test_all_permissions(self):
        """Test all standard permissions."""
        result = strip_bbs_tags(cyrusperms("lrswipcda"))
        self.assertEqual(result, "lookup, read, seen, write, insert, post, create, delete, and admin")

    def test_empty_string(self):
        """Test empty string returns empty."""
        result = cyrusperms("")
        self.assertEqual(result, "")

    def test_none_input(self):
        """Test None returns empty."""
        result = cyrusperms(None)
        self.assertEqual(result, "")

    def test_space_separated_string(self):
        """Test space-separated permissions."""
        result = strip_bbs_tags(cyrusperms("l r s"))
        self.assertEqual(result, "lookup, read, and seen")

    def test_comma_separated_string(self):
        """Test comma-separated permissions."""
        result = strip_bbs_tags(cyrusperms("l,r,s"))
        self.assertEqual(result, "lookup, read, and seen")

    def test_mixed_separator_with_known_permission(self):
        """Test string with known permission token."""
        result = strip_bbs_tags(cyrusperms("user.jam lrsa"))
        self.assertEqual(result, "lookup, read, seen, and admin")

    def test_list_of_single_chars(self):
        """Test list of single-char permissions."""
        result = strip_bbs_tags(cyrusperms(["l", "r", "s"]))
        self.assertEqual(result, "lookup, read, and seen")

    def test_list_of_strings(self):
        """Test list of multi-char strings."""
        result = strip_bbs_tags(cyrusperms(["lrs", "wip"]))
        self.assertEqual(result, "lookup, read, seen, write, insert, and post")

    def test_unknown_permission_letter(self):
        """Test unknown permission letter passes through."""
        result = strip_bbs_tags(cyrusperms("xyz"))
        self.assertEqual(result, "x, y, and z")

    def test_mixed_known_and_unknown(self):
        """Test mix of known and unknown permissions (unknown passed through)."""
        result = strip_bbs_tags(cyrusperms("lrsXYZ"))
        self.assertEqual(result, "lookup, read, seen, X, Y, and Z")

    def test_case_insensitive(self):
        """Test permissions are case insensitive."""
        result = strip_bbs_tags(cyrusperms("LRS"))
        self.assertEqual(result, "lookup, read, and seen")

    def test_empty_list(self):
        """Test empty list returns empty."""
        result = cyrusperms([])
        self.assertEqual(result, "")

    def test_single_permission(self):
        """Test single permission."""
        result = strip_bbs_tags(cyrusperms("a"))
        self.assertEqual(result, "admin")

    def test_imap_myrights_format(self):
        """Test IMAP MYRIGHTS response format (last token is permissions)."""
        result = strip_bbs_tags(cyrusperms("user.jam lrswcida"))
        self.assertEqual(result, "lookup, read, seen, write, create, insert, delete, and admin")

    def test_whitespace_handling(self):
        """Test extra whitespace is handled."""
        result = strip_bbs_tags(cyrusperms("  l  r  s  "))
        self.assertEqual(result, "lookup, read, and seen")

    def test_two_permissions_no_oxford_comma(self):
        """Test two permissions without Oxford comma."""
        result = strip_bbs_tags(cyrusperms("lr"))
        self.assertEqual(result, "lookup and read")


if __name__ == "__main__":
    unittest.main()