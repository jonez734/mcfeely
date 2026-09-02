# tests/test_mcfeely_authd.py
# Unit tests for mcfeely-authd: protocol, config, auth_verify, and daemon modules

import io
import os
import sys
import json
import socket
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# mcfeely_authd.protocol tests
# ---------------------------------------------------------------------------

class TestProtocolParsing(unittest.TestCase):
    """Test authdaemon protocol parsing (stateless, no sockets needed)."""

    def _make_sock(self, data: str) -> io.BytesIO:
        return io.BytesIO(data.encode("utf-8"))

    def test_parse_request_minimal(self):
        from mcfeely_authd.protocol import parse_request, AuthRequest

        data = "AUTH LOGIN\n10\ntestuser\nsecret123\n\n\n\n"
        req = parse_request(self._make_sock(data))

        self.assertIsInstance(req, AuthRequest)
        self.assertEqual(req.mechanism, "LOGIN")
        self.assertEqual(req.username, "testuser")
        self.assertEqual(req.password, "secret123")
        self.assertIsNone(req.realm)

    def test_parse_request_with_realm(self):
        from mcfeely_authd.protocol import parse_request

        data = "AUTH PLAIN\n18\ntestuser\nsecret123\nexample.com\n\n\n"
        req = parse_request(self._make_sock(data))

        self.assertEqual(req.mechanism, "PLAIN")
        self.assertEqual(req.username, "testuser")
        self.assertEqual(req.password, "secret123")
        self.assertEqual(req.realm, "example.com")
        self.assertEqual(req.user_realm, "testuser@example.com")

    def test_parse_request_with_ip(self):
        from mcfeely_authd.protocol import parse_request

        data = "AUTH LOGIN\n10\ntestuser\nsecret123\n\n127.0.0.1\n10.0.0.1\n"
        req = parse_request(self._make_sock(data))

        self.assertEqual(req.local_ip, "127.0.0.1")
        self.assertEqual(req.remote_ip, "10.0.0.1")

    def test_parse_request_no_auth_prefix(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock("BADLINE\n10\nuser\npass\n\n\n\n"))

    def test_parse_request_empty_mechanism(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock("AUTH \n10\nuser\npass\n\n\n\n"))

    def test_parse_request_invalid_length(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock("AUTH LOGIN\nabc\nuser\npass\n\n\n\n"))

    def test_parse_request_negative_length(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock("AUTH LOGIN\n-1\nuser\npass\n\n\n\n"))

    def test_parse_request_zero_length(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock("AUTH LOGIN\n0\nuser\npass\n\n\n\n"))

    def test_parse_request_too_long(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock(f"AUTH LOGIN\n99999\n{'a'*99999}\npass\n\n\n\n"))

    def test_parse_request_closed_connection(self):
        from mcfeely_authd.protocol import parse_request, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request(self._make_sock(""))

    def test_user_realm_no_realm(self):
        from mcfeely_authd.protocol import AuthRequest

        req = AuthRequest("LOGIN", "alice", "secret")
        self.assertEqual(req.user_realm, "alice")
        self.assertEqual(repr(req), "AuthRequest(mechanism='LOGIN', username='alice')")

    def test_user_realm_with_realm(self):
        from mcfeely_authd.protocol import AuthRequest

        req = AuthRequest("PLAIN", "alice", "secret", realm="example.com")
        self.assertEqual(req.user_realm, "alice@example.com")

    def test_parse_request_from_buffer(self):
        from mcfeely_authd.protocol import parse_request_from_buffer, AuthRequest

        # lines[:5] = ["AUTH LOGIN","14","alice","secret",""] -> sum+1 = 28
        # total_len = 28 + 14 = 42
        data = b"AUTH LOGIN\n14\nalice\nsecret\n\n" + b"\x00" * 14
        req, consumed = parse_request_from_buffer(data)

        self.assertIsInstance(req, AuthRequest)
        self.assertEqual(req.mechanism, "LOGIN")
        self.assertEqual(req.username, "alice")
        self.assertEqual(req.password, "secret")
        self.assertGreater(consumed, 0)

    def test_parse_request_from_buffer_with_padding(self):
        from mcfeely_authd.protocol import parse_request_from_buffer

        data = b"AUTH LOGIN\n14\nalice\nsecret\n\n\n\n\n\n" + b"\x00" * 12
        req, consumed = parse_request_from_buffer(data)
        self.assertEqual(req.username, "alice")
        self.assertGreater(consumed, 0)

    def test_parse_request_from_buffer_incomplete(self):
        from mcfeely_authd.protocol import parse_request_from_buffer, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request_from_buffer(b"AUTH LOGIN\n")

    def test_parse_request_from_buffer_invalid_auth(self):
        from mcfeely_authd.protocol import parse_request_from_buffer, ProtocolError

        with self.assertRaises(ProtocolError):
            parse_request_from_buffer(b"BOGUS\n10\nuser\npass\n\n")

    def test_send_ok(self):
        from mcfeely_authd.protocol import send_ok

        buf = io.BytesIO()
        send_ok(buf, "Authenticated")
        buf.seek(0)
        self.assertEqual(buf.read(), b"OK\nAuthenticated\n")

    def test_send_no(self):
        from mcfeely_authd.protocol import send_no

        buf = io.BytesIO()
        send_no(buf, "Bad password")
        buf.seek(0)
        self.assertEqual(buf.read(), b"NO\nBad password\n")

    def test_send_fail(self):
        from mcfeely_authd.protocol import send_fail

        buf = io.BytesIO()
        send_fail(buf, "Server error")
        buf.seek(0)
        self.assertEqual(buf.read(), b"FAIL\nServer error\n")

    def test_send_ok_no_message(self):
        from mcfeely_authd.protocol import send_ok

        buf = io.BytesIO()
        send_ok(buf)
        buf.seek(0)
        self.assertEqual(buf.read(), b"OK\n")

    def test_auth_response_factory_methods(self):
        from mcfeely_authd.protocol import AuthResponse

        ok_resp = AuthResponse.ok("done")
        self.assertEqual(ok_resp.status, "OK")
        self.assertEqual(ok_resp.message, "done")

        no_resp = AuthResponse.no("denied")
        self.assertEqual(no_resp.status, "NO")
        self.assertEqual(no_resp.message, "denied")

        fail_resp = AuthResponse.fail("error")
        self.assertEqual(fail_resp.status, "FAIL")
        self.assertEqual(fail_resp.message, "error")

    def test_send_response_ok(self):
        from mcfeely_authd.protocol import send_response, AuthResponse

        buf = io.BytesIO()
        send_response(buf, AuthResponse.ok("OK"))
        buf.seek(0)
        self.assertEqual(buf.read(), b"OK\nOK\n")

    def test_send_response_no_message(self):
        from mcfeely_authd.protocol import send_response, AuthResponse

        buf = io.BytesIO()
        send_response(buf, AuthResponse.ok())
        buf.seek(0)
        self.assertEqual(buf.read(), b"OK\n")


# ---------------------------------------------------------------------------
# mcfeely_authd.config tests
# ---------------------------------------------------------------------------

class TestConfig(unittest.TestCase):
    """Test configuration loading (file, env, defaults)."""

    def setUp(self):
        self.env_patches = {}
        for key in ("BBSENGINE6_DBNAME", "POSTOFFICE_PASSWORD_KEY", "MCFEELY_AUTHD_CONFIG"):
            self.env_patches[key] = os.environ.pop(key, None)

    def tearDown(self):
        for key, val in self.env_patches.items():
            if val is not None:
                os.environ[key] = val
            else:
                os.environ.pop(key, None)

    def test_default_config_values(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent/config.conf")
        self.assertEqual(cfg.socket_path, "/var/run/mcfeely-authd/mux")
        self.assertEqual(cfg.pid_file, "/var/run/mcfeely-authd/mcfeely-authd.pid")
        self.assertEqual(cfg.log_file, "/var/log/mcfeely-authd.log")
        self.assertEqual(cfg.log_level, "INFO")
        self.assertTrue(cfg.log_syslog)
        self.assertTrue(cfg.fallback_pam)
        self.assertEqual(cfg.pam_service, "imap")
        self.assertEqual(cfg.database_dsn, "postgresql://localhost/zoid6test")
        self.assertEqual(cfg.timeout, 30)
        self.assertEqual(cfg.max_children, 50)

    def test_override_via_kwargs(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/test-mux",
            timeout=10,
        )
        self.assertEqual(cfg.socket_path, "/tmp/test-mux")
        self.assertEqual(cfg.timeout, 10)

    def test_config_file_loading(self):
        from mcfeely_authd.config import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write("[socket]\npath = /tmp/test-mux\n")
            f.write("[daemon]\ntimeout = 15\nmax_children = 10\n")
            f.write("[logging]\nlevel = DEBUG\nsyslog = false\n")
            f.write("[auth]\nfallback_pam = false\npam_service = imap\n")
            conf_path = f.name

        try:
            cfg = load_config(config_file=conf_path)
            self.assertEqual(cfg.socket_path, "/tmp/test-mux")
            self.assertEqual(cfg.timeout, 15)
            self.assertEqual(cfg.max_children, 10)
            self.assertEqual(cfg.log_level, "DEBUG")
            self.assertFalse(cfg.log_syslog)
            self.assertFalse(cfg.fallback_pam)
            self.assertEqual(cfg.pam_service, "imap")
        finally:
            os.unlink(conf_path)

    def test_env_var_dbname(self):
        from mcfeely_authd.config import load_config

        os.environ["BBSENGINE6_DBNAME"] = "testdb"
        cfg = load_config(config_file="/nonexistent")
        self.assertIn("testdb", cfg.database_dsn)

    def test_missing_config_file(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/does/not/exist.conf")
        self.assertEqual(cfg.socket_path, "/var/run/mcfeely-authd/mux")

    def test_validate_ok(self):
        from mcfeely_authd.config import load_config

        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(
                config_file="/nonexistent",
                socket_path=f"{tmp}/mux",
                log_file=f"{tmp}/authd.log",
            )
            valid, err = cfg.validate()
            self.assertTrue(valid)
            self.assertIsNone(err)

    def test_validate_no_socket_path(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent", socket_path="")
        valid, err = cfg.validate()
        self.assertFalse(valid)
        self.assertIn("socket_path", err or "")

    def test_get_database_args_default(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent")
        args = cfg.get_database_args()
        self.assertEqual(args.get("databasename"), "zoid6test")

    def test_get_database_args_with_credentials(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(
            config_file="/nonexistent",
            database_dsn="postgresql://user:pass@dbhost:5432/testdb",
        )
        args = cfg.get_database_args()
        self.assertEqual(args.get("databasename"), "testdb")
        self.assertEqual(args.get("databaseuser"), "user")
        self.assertEqual(args.get("databasepassword"), "pass")
        self.assertEqual(args.get("databasehost"), "dbhost")
        self.assertEqual(args.get("databaseport"), 5432)

    def test_get_database_args_with_explicit_credentials(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(
            config_file="/nonexistent",
            database_dsn="postgresql://localhost/zoid6test",
            database_user="custom_user",
            database_password="custom_pass",
        )
        args = cfg.get_database_args()
        self.assertEqual(args.get("databaseuser"), "custom_user")
        self.assertEqual(args.get("databasepassword"), "custom_pass")

    def test_dict_like_access(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent")
        self.assertIn("socket_path", cfg)
        self.assertEqual(cfg["socket_path"], "/var/run/mcfeely-authd/mux")
        cfg["socket_path"] = "/tmp/custom"
        self.assertEqual(cfg["socket_path"], "/tmp/custom")

    def test_items(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent")
        items = dict(cfg.items())
        self.assertIn("socket_path", items)
        self.assertIn("pid_file", items)

    def test_get_method(self):
        from mcfeely_authd.config import load_config

        cfg = load_config(config_file="/nonexistent")
        self.assertEqual(cfg.get("socket_path"), "/var/run/mcfeely-authd/mux")
        self.assertEqual(cfg.get("nonexistent_key", "default"), "default")
        self.assertIsNone(cfg.get("nonexistent_key"))


# ---------------------------------------------------------------------------
# mcfeely_authd.auth_verify tests
# ---------------------------------------------------------------------------

class TestAuthVerify(unittest.TestCase):
    """Test password verification logic (database + PAM fallback)."""

    def setUp(self):
        from mcfeely_authd.config import load_config

        self.cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/mcfeely-authd-test-mux",
            log_file="/tmp/mcfeely-authd-test.log",
        )

    def test_verify_empty_username(self):
        from mcfeely_authd.auth_verify import verify_password

        ok, reason = verify_password("", "secret", self.cfg)
        self.assertFalse(ok)
        self.assertIn("Empty username", reason)

    def test_verify_empty_password(self):
        from mcfeely_authd.auth_verify import verify_password

        ok, reason = verify_password("alice", "", self.cfg)
        self.assertFalse(ok)
        self.assertIn("Empty password", reason)

    def test_verify_no_database_no_pam(self):
        from mcfeely_authd.auth_verify import verify_password

        self.cfg._config["fallback_pam"] = False
        ok, reason = verify_password("alice", "secret", self.cfg)
        self.assertFalse(ok)


class TestAuthVerifyCheckCryptHash(unittest.TestCase):
    """Test the SHA-512 crypt hash verification logic."""

    def setUp(self):
        from mcfeely_authd.auth_verify import _check_crypt_hash

        self._check = _check_crypt_hash

    def test_valid_hash(self):
        from passlib.hash import sha512_crypt

        h = sha512_crypt.hash("correct-password")
        self.assertTrue(self._check("correct-password", h))

    def test_wrong_password(self):
        from passlib.hash import sha512_crypt

        h = sha512_crypt.hash("correct-password")
        self.assertFalse(self._check("wrong-password", h))

    def test_invalid_hash_format(self):
        self.assertFalse(self._check("password", "not-a-valid-hash"))


class TestAuthVerifyDatabase(unittest.TestCase):
    """Test database-based password verification with mocked bbsengine6.database."""

    def setUp(self):
        from mcfeely_authd.config import load_config

        self.cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/mcfeely-authd-test-mux",
            log_file="/tmp/mcfeely-authd-test.log",
        )
        self.cfg._pool = self._make_pool(fetchone_return=None)

    def tearDown(self):
        self.cfg.close_pool()

    def _make_pool(self, fetchone_return=None):
        """Build a MagicMock pool whose connect() is a context manager.

        bbsengine6.database.connect(args, pool=pool) is a
        @contextmanager that yields a connection. The connection's
        cursor() is a context manager that yields a cursor. The cursor
        has execute() and fetchone() we want to drive from the test.
        """
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = fetchone_return

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        mock_pool = MagicMock()
        # pool.getconn() not used directly by callers; connect() is.
        # make connect() a context manager that yields mock_conn.
        from contextlib import contextmanager

        @contextmanager
        def fake_connect(args, pool=None, **kw):
            yield mock_conn

        mock_pool._fake_connect = fake_connect
        return mock_pool

    def _patch_connect(self, fetchone_return=None):
        """Patch bbsengine6.database.connect to yield a mock connection."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = fetchone_return
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        from contextlib import contextmanager

        @contextmanager
        def fake_connect(args, pool=None, **kw):
            yield mock_conn

        return patch("bbsengine6.database.connect", side_effect=fake_connect)

    def test_user_found_password_ok(self):
        from mcfeely_authd.auth_verify import _verify_database
        from passlib.hash import sha512_crypt

        h = sha512_crypt.hash("correct-password")
        patcher = self._patch_connect(fetchone_return=(h,))
        with patcher:
            ok, reason = _verify_database("alice", "correct-password", self.cfg)
        self.assertTrue(ok)
        self.assertIn("database", reason.lower())

    def test_user_found_wrong_password(self):
        from mcfeely_authd.auth_verify import _verify_database
        from passlib.hash import sha512_crypt

        h = sha512_crypt.hash("correct-password")
        patcher = self._patch_connect(fetchone_return=(h,))
        with patcher:
            ok, reason = _verify_database("alice", "wrong-password", self.cfg)
        self.assertFalse(ok)
        self.assertIn("Invalid password", reason)

    def test_user_not_found(self):
        from mcfeely_authd.auth_verify import _verify_database

        patcher = self._patch_connect(fetchone_return=None)
        with patcher:
            ok, reason = _verify_database("unknown", "password", self.cfg)
        self.assertFalse(ok)
        self.assertIn("not found", reason.lower())

    def test_database_error(self):
        from mcfeely_authd.auth_verify import _verify_database

        with patch(
            "bbsengine6.database.connect",
            side_effect=Exception("Connection refused"),
        ):
            ok, reason = _verify_database("alice", "password", self.cfg)
        self.assertFalse(ok)
        self.assertIn("Database error", reason)


@patch("mcfeely_authd.auth_verify.subprocess.run")
class TestAuthVerifyPamFallback(unittest.TestCase):
    """Test PAM fallback password verification."""

    def setUp(self):
        from mcfeely_authd.config import load_config

        self.cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/mcfeely-authd-test-mux",
            log_file="/tmp/mcfeely-authd-test.log",
        )

    def test_pam_success(self, mock_run):
        from mcfeely_authd.auth_verify import _verify_pam

        mock_run.return_value = MagicMock(returncode=0)

        ok, reason = _verify_pam("alice", "password")
        self.assertTrue(ok)
        self.assertIn("PAM", reason)

    def test_pam_failure(self, mock_run):
        from mcfeely_authd.auth_verify import _verify_pam

        mock_run.return_value = MagicMock(returncode=1)

        ok, reason = _verify_pam("alice", "wrong")
        self.assertFalse(ok)

    def test_pam_subprocess_error(self, mock_run):
        from mcfeely_authd.auth_verify import _verify_pam

        mock_run.side_effect = OSError("saslauthd not found")

        ok, reason = _verify_pam("alice", "password")
        self.assertFalse(ok)

    def test_pam_timeout(self, mock_run):
        from mcfeely_authd.auth_verify import _verify_pam

        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="saslauthd", timeout=10)

        ok, reason = _verify_pam("alice", "password")
        self.assertFalse(ok)


class TestAuthVerifyFullFlow(unittest.TestCase):
    """Test the full verify_password flow with fallback."""

    def setUp(self):
        from mcfeely_authd.config import load_config

        self.cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/mcfeely-authd-test-mux",
            log_file="/tmp/mcfeely-authd-test.log",
        )

    @patch("mcfeely_authd.auth_verify._verify_database")
    def test_database_success_no_pam_fallback(self, mock_db):
        from mcfeely_authd.auth_verify import verify_password

        mock_db.return_value = (True, "Authenticated via database")

        ok, reason = verify_password("alice", "secret", self.cfg)
        self.assertTrue(ok)
        self.assertIn("database", reason.lower())

    @patch("mcfeely_authd.auth_verify._verify_database")
    @patch("mcfeely_authd.auth_verify._verify_pam")
    def test_database_fail_fallback_to_pam_ok(self, mock_pam, mock_db):
        from mcfeely_authd.auth_verify import verify_password

        mock_db.return_value = (False, "User not found in database")
        mock_pam.return_value = (True, "Authenticated via PAM")

        ok, reason = verify_password("alice", "secret", self.cfg)
        self.assertTrue(ok)

    @patch("mcfeely_authd.auth_verify._verify_database")
    @patch("mcfeely_authd.auth_verify._verify_pam")
    def test_database_fail_fallback_to_pam_fail(self, mock_pam, mock_db):
        from mcfeely_authd.auth_verify import verify_password

        mock_db.return_value = (False, "User not found in database")
        mock_pam.return_value = (False, "PAM auth unavailable")

        ok, reason = verify_password("alice", "secret", self.cfg)
        self.assertFalse(ok)

    @patch("mcfeely_authd.auth_verify._verify_database")
    @patch("mcfeely_authd.auth_verify._verify_pam")
    def test_no_fallback_when_disabled(self, mock_pam, mock_db):
        from mcfeely_authd.auth_verify import verify_password

        self.cfg._config["fallback_pam"] = False
        mock_db.return_value = (False, "User not found in database")

        ok, reason = verify_password("alice", "secret", self.cfg)
        self.assertFalse(ok)
        mock_pam.assert_not_called()


class TestGetUserInfo(unittest.TestCase):
    """Test the get_user_info function."""

    def setUp(self):
        from mcfeely_authd.config import load_config

        self.cfg = load_config(
            config_file="/nonexistent",
            socket_path="/tmp/mcfeely-authd-test-mux",
            log_file="/tmp/mcfeely-authd-test.log",
        )

    def tearDown(self):
        self.cfg.close_pool()

    def _patch_connect(self, fetchone_return):
        """Patch bbsengine6.database.connect to return a mock conn."""
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = fetchone_return
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        from contextlib import contextmanager

        @contextmanager
        def fake_connect(args, pool=None, **kw):
            yield mock_conn

        return patch("bbsengine6.database.connect", side_effect=fake_connect)

    def test_user_found(self):
        from mcfeely_authd.auth_verify import get_user_info
        from datetime import datetime

        now = datetime.now()
        patcher = self._patch_connect(
            fetchone_return=("alice", True, now, now, "alice@test.com", now)
        )
        with patcher:
            info = get_user_info("alice", self.cfg)
        self.assertIsNotNone(info)
        self.assertEqual(info["member_moniker"], "alice")
        self.assertEqual(info["email"], "alice@test.com")
        self.assertTrue(info["enabled"])

    def test_user_not_found(self):
        from mcfeely_authd.auth_verify import get_user_info

        patcher = self._patch_connect(fetchone_return=None)
        with patcher:
            info = get_user_info("nonexistent", self.cfg)
        self.assertIsNone(info)



class TestDaemonMain(unittest.TestCase):
    """Test the daemon's main() entry point and argument parsing."""

    @patch("mcfeely_authd.mcfeely_authd.config.load_config")
    @patch("mcfeely_authd.mcfeely_authd.auth_verify.verify_password")
    def test_test_mode_auth_success(self, mock_verify, mock_load_config):
        from mcfeely_authd.mcfeely_authd import main

        mock_cfg = MagicMock()
        mock_load_config.return_value = mock_cfg
        mock_verify.return_value = (True, "Authenticated via database")

        with patch.object(sys, "argv", ["mcfeely-authd", "--test", "alice"]), \
             patch("sys.stdin", io.StringIO("secret\n")):
            rc = main()
            self.assertEqual(rc, 0)

    @patch("mcfeely_authd.mcfeely_authd.config.load_config")
    @patch("mcfeely_authd.mcfeely_authd.auth_verify.verify_password")
    def test_test_mode_auth_failure(self, mock_verify, mock_load_config):
        from mcfeely_authd.mcfeely_authd import main

        mock_cfg = MagicMock()
        mock_load_config.return_value = mock_cfg
        mock_verify.return_value = (False, "Invalid password")

        with patch.object(sys, "argv", ["mcfeely-authd", "--test", "alice"]), \
             patch("sys.stdin", io.StringIO("wrong\n")):
            rc = main()
            self.assertEqual(rc, 1)

    @patch("mcfeely_authd.mcfeely_authd.run_daemon")
    @patch("mcfeely_authd.mcfeely_authd.config.load_config")
    def test_foreground_mode(self, mock_load_config, mock_run):
        from mcfeely_authd.mcfeely_authd import main

        mock_cfg = MagicMock()
        mock_load_config.return_value = mock_cfg
        mock_run.return_value = 0

        with patch.object(sys, "argv", ["mcfeely-authd", "--foreground"]):
            rc = main()
            self.assertEqual(rc, 0)
            mock_run.assert_called_once_with(mock_cfg, foreground=True)

    @patch("mcfeely_authd.mcfeely_authd.run_daemon")
    @patch("mcfeely_authd.mcfeely_authd.config.load_config")
    def test_daemon_mode(self, mock_load_config, mock_run):
        from mcfeely_authd.mcfeely_authd import main

        mock_cfg = MagicMock()
        mock_load_config.return_value = mock_cfg
        mock_run.return_value = 0

        with patch.object(sys, "argv", ["mcfeely-authd"]):
            rc = main()
            self.assertEqual(rc, 0)
            mock_run.assert_called_once_with(mock_cfg, foreground=False)

    @patch("mcfeely_authd.mcfeely_authd.run_daemon")
    @patch("mcfeely_authd.mcfeely_authd.config.load_config")
    def test_custom_config_path(self, mock_load_config, mock_run):
        from mcfeely_authd.mcfeely_authd import main

        mock_cfg = MagicMock()
        mock_load_config.return_value = mock_cfg
        mock_run.return_value = 0

        with patch.object(sys, "argv", ["mcfeely-authd", "-c", "/tmp/my.conf", "--foreground"]):
            rc = main()
            self.assertEqual(rc, 0)
            mock_load_config.assert_called_once_with("/tmp/my.conf")


class TestDaemonSetupLogging(unittest.TestCase):
    """Test daemon logging setup."""

    @patch("mcfeely_authd.mcfeely_authd.os.makedirs")
    @patch("mcfeely_authd.mcfeely_authd.logging.FileHandler")
    def test_setup_logging(self, mock_fh, mock_mkdir):
        from mcfeely_authd.mcfeely_authd import setup_logging
        from mcfeely_authd.config import Config

        cfg = Config(config_file="/nonexistent")
        logger = setup_logging(cfg)
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "mcfeely-authd")

    def test_setup_logging_no_syslog(self):
        from mcfeely_authd.mcfeely_authd import setup_logging
        from mcfeely_authd.config import Config

        cfg = Config(config_file="/nonexistent", log_syslog=False, log_file="/tmp/test-authd.log")
        try:
            logger = setup_logging(cfg)
            self.assertIsNotNone(logger)
        finally:
            if os.path.exists("/tmp/test-authd.log"):
                os.unlink("/tmp/test-authd.log")


class TestDaemonValidateConfig(unittest.TestCase):
    """Test daemon configuration validation."""

    def test_run_daemon_invalid_config(self):
        import logging as _logging
        from mcfeely_authd.mcfeely_authd import run_daemon
        from mcfeely_authd.config import Config

        cfg = Config(config_file="/nonexistent", socket_path="")

        def _noop_setup(cfg):
            logger = _logging.getLogger("mcfeely-authd-test")
            logger.addHandler(_logging.NullHandler())
            import mcfeely_authd.mcfeely_authd as _mod
            _mod.LOGGER = logger

        with patch("mcfeely_authd.mcfeely_authd.setup_logging", _noop_setup):
            rc = run_daemon(cfg, foreground=True)
        self.assertEqual(rc, 1)


class TestDaemonHandleSignal(unittest.TestCase):
    """Test signal handling calls sys.exit."""

    @patch("mcfeely_authd.mcfeely_authd.LOGGER")
    def test_handle_signal(self, mock_logger):
        from mcfeely_authd.mcfeely_authd import handle_signal

        with self.assertRaises(SystemExit):
            handle_signal(15, None)
        mock_logger.info.assert_called_once()


class TestDaemonConstants(unittest.TestCase):
    """Test daemon module constants."""

    def test_version_and_name(self):
        from mcfeely_authd.mcfeely_authd import VERSION, DAEMON_NAME

        self.assertEqual(DAEMON_NAME, "mcfeely-authd")
        self.assertIsInstance(VERSION, str)
        self.assertTrue(len(VERSION) > 0)


# ---------------------------------------------------------------------------
# postoffice.services tests (MailboxPoller, MailboxConfig, singleton)
# ---------------------------------------------------------------------------

class TestServicesMailboxConfig(unittest.TestCase):
    """Test MailboxConfig class."""

    def test_defaults(self):
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="imap.example.com", username="user", password="pass")
        self.assertEqual(mb.host, "imap.example.com")
        self.assertEqual(mb.username, "user")
        self.assertEqual(mb.password, "pass")
        self.assertEqual(mb.mailbox, "INBOX")
        self.assertTrue(mb.use_ssl)
        self.assertEqual(mb.port, 993)

    def test_custom_values(self):
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(
            host="mail.test.com",
            username="testuser",
            password="secret",
            mailbox="Work",
            use_ssl=False,
            port=143,
        )
        self.assertEqual(mb.host, "mail.test.com")
        self.assertEqual(mb.mailbox, "Work")
        self.assertFalse(mb.use_ssl)
        self.assertEqual(mb.port, 143)

    def test_port_inferred_from_ssl(self):
        from postoffice.services import MailboxConfig

        mb_ssl = MailboxConfig(host="h", username="u", password="p", use_ssl=True)
        self.assertEqual(mb_ssl.port, 993)

        mb_nossl = MailboxConfig(host="h", username="u", password="p", use_ssl=False)
        self.assertEqual(mb_nossl.port, 143)

    def test_explicit_port_overrides_default(self):
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="h", username="u", password="p", use_ssl=True, port=1143)
        self.assertEqual(mb.port, 1143)


class TestServicesMailboxPoller(unittest.TestCase):
    """Test MailboxPoller initialization."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    def test_disabled(self):
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={"enabled": False, "poll_interval": 30, "mailboxes": []})
        self.assertFalse(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 30)
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    def test_enabled(self):
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 60,
            "mailboxes": [{"host": "imap.test.com", "username": "user", "password": "pass"}],
        })
        self.assertTrue(poller.is_enabled)
        self.assertEqual(poller.poll_interval, 60)
        self.assertEqual(len(poller.mailboxes), 1)

    def test_loads_mailboxes(self):
        from postoffice.services import MailboxPoller, MailboxConfig

        mailboxes = [
            {"host": "imap.gmail.com", "username": "user", "password": "pass", "use_ssl": True},
            {"host": "imap.work.com", "username": "worker", "password": "secret", "use_ssl": True},
        ]
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 30, "mailboxes": mailboxes})
        self.assertEqual(len(poller.mailboxes), 2)
        self.assertIsInstance(poller.mailboxes[0], MailboxConfig)

    def test_invalid_mailbox_config(self):
        from postoffice.services import MailboxPoller

        mailboxes = [
            {"host": "valid.com", "username": "user", "password": "pass"},
            {"host": "", "username": "", "password": ""},
        ]
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 30, "mailboxes": mailboxes})
        self.assertEqual(len(poller.mailboxes), 2)

    def test_property_returns_list(self):
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={
            "enabled": True,
            "poll_interval": 10,
            "mailboxes": [{"host": "h", "username": "u", "password": "p"}],
        })
        mbs = poller.mailboxes
        self.assertIsInstance(mbs, list)
        self.assertEqual(len(mbs), 1)


class TestServicesStartStop(unittest.TestCase):
    """Test MailboxPoller start/stop (with mocked event loop)."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    def test_start_disabled_service(self):
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={"enabled": False, "poll_interval": 30, "mailboxes": []})
        poller.start()
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    @patch("postoffice.services.mailbox_poller.asyncio.create_task")
    def test_start_enabled_service(self, mock_task):
        from postoffice.services import MailboxPoller

        mock_task.return_value = MagicMock()
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 1, "mailboxes": []})
        poller.start()
        self.assertTrue(poller._running)
        self.assertIsNotNone(poller._task)
        poller.stop()

    @patch("postoffice.services.mailbox_poller.asyncio.create_task")
    def test_start_already_running(self, mock_task):
        from postoffice.services import MailboxPoller

        mock_task.return_value = MagicMock()
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 1, "mailboxes": []})
        poller.start()
        self.assertTrue(poller._running)
        poller.start()
        poller.stop()

    @patch("postoffice.services.mailbox_poller.asyncio.create_task")
    def test_stop_service(self, mock_task):
        from postoffice.services import MailboxPoller

        mock_task.return_value = MagicMock()
        poller = MailboxPoller(config={"enabled": True, "poll_interval": 1, "mailboxes": []})
        poller.start()
        self.assertTrue(poller._running)
        poller.stop()
        self.assertFalse(poller._running)
        self.assertIsNone(poller._task)

    def test_stop_not_running(self):
        from postoffice.services import MailboxPoller

        poller = MailboxPoller(config={"enabled": False, "poll_interval": 30, "mailboxes": []})
        poller.stop()
        self.assertFalse(poller._running)


class TestServicesSingleton(unittest.TestCase):
    """Test singleton pattern for postoffice service."""

    def setUp(self):
        from postoffice.services import reset_service
        reset_service()

    def test_get_service_singleton(self):
        from postoffice.services import get_service, MailboxPoller

        cfg = {"enabled": False, "poll_interval": 30, "mailboxes": []}
        s1 = get_service(cfg)
        s2 = get_service(cfg)
        self.assertIs(s1, s2)
        self.assertIsInstance(s1, MailboxPoller)

    def test_get_service_different_config_returns_same_instance(self):
        from postoffice.services import get_service, reset_service
        reset_service()

        s1 = get_service({"enabled": False, "poll_interval": 10, "mailboxes": []})
        s2 = get_service({"enabled": True, "poll_interval": 99, "mailboxes": []})
        self.assertIs(s1, s2)

    def test_stop_service_clears_singleton(self):
        from postoffice.services import get_service, stop_service, reset_service
        reset_service()

        s1 = get_service({"enabled": False, "poll_interval": 30, "mailboxes": []})
        stop_service()
        s2 = get_service({"enabled": False, "poll_interval": 30, "mailboxes": []})
        self.assertIsNot(s1, s2)

    def test_start_service_no_config(self):
        from postoffice.services import start_service, stop_service, get_service, reset_service
        reset_service()

        start_service()
        svc = get_service()
        self.assertIsNotNone(svc)
        stop_service()


class TestLoadMailboxes(unittest.TestCase):
    """Test load_mailboxes helper."""

    def test_load_mailboxes_empty(self):
        from postoffice.services.config import load_mailboxes

        result = load_mailboxes(None)
        self.assertEqual(result, [])

        result = load_mailboxes({})
        self.assertEqual(result, [])

    def test_load_mailboxes_with_data(self):
        from postoffice.services.config import load_mailboxes, MailboxConfig

        result = load_mailboxes({
            "mailboxes": [
                {"host": "a.com", "username": "u1", "password": "p1"},
                {"host": "b.com", "username": "u2", "password": "p2", "mailbox": "Spam"},
            ]
        })
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], MailboxConfig)
        self.assertEqual(result[0].host, "a.com")
        self.assertEqual(result[1].mailbox, "Spam")


class TestServicesImapClient(unittest.TestCase):
    """Test IMAP client wrapper module functions."""

    @patch("postoffice.services.imap_client.imaplib")
    def test_connect_success(self, mock_imaplib):
        from postoffice.services.imap_client import connect
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="imap.test.com", username="user", password="pass")
        mock_conn = MagicMock()
        mock_imaplib.IMAP4_SSL.return_value = mock_conn

        result = connect(mb)
        self.assertIsNotNone(result)

    @patch("postoffice.services.imap_client.imaplib")
    def test_connect_no_ssl(self, mock_imaplib):
        from postoffice.services.imap_client import connect
        from postoffice.services import MailboxConfig

        mb = MailboxConfig(host="imap.test.com", username="user", password="pass", use_ssl=False)
        mock_conn = MagicMock()
        mock_imaplib.IMAP4.return_value = mock_conn

        result = connect(mb)
        mock_imaplib.IMAP4.assert_called_once_with("imap.test.com", 143)

    @patch("postoffice.services.imap_client.imaplib")
    def test_fetch_envelopes(self, mock_imaplib):
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b"1 2 3"])
        mock_conn.fetch.return_value = ("OK", [(b"1 (FLAGS (\\Seen) BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {50}", b"From: test@test.com Subject: Hello\r\n\r\n")])

        result = fetch_envelopes(mock_conn, limit=3)
        self.assertEqual(len(result), 3)

    @patch("postoffice.services.imap_client.imaplib")
    def test_fetch_envelopes_empty_mailbox(self, mock_imaplib):
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("OK", [b""])

        result = fetch_envelopes(mock_conn)
        self.assertEqual(result, [])

    @patch("postoffice.services.imap_client.imaplib")
    def test_fetch_envelopes_search_fail(self, mock_imaplib):
        from postoffice.services.imap_client import fetch_envelopes

        mock_conn = MagicMock()
        mock_conn.search.return_value = ("NO", [b"Search failed"])

        result = fetch_envelopes(mock_conn)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
