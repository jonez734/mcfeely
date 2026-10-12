"""Tests for mcfeely_authd.auth_verify -- the saslauthd path gate.

Run against the local 'zoid6test' fixture DB on a build host. Each
test inserts the rows it needs, calls the gate functions, asserts
the (ok, reason) pair, and cleans up after itself.

These tests pin the legacy Mode B saslauthd path:
  - The DB query in _get_crypt_hash consults engine.__member.approved
    and engine.__member.accountexpires (not just sasl_password.enabled).
  - The saslauthd path accepts only users with a row in
    postoffice.sasl_password. Users with only engine.__member.password
    (BBS web) are NOT authenticated here -- they go through
    bbsengine6-auth-pam via the auxprop-pam default.

Parity with bbsengine6.auth.verify_member is asserted in
test_parity_with_bbsengine6_auth_verify: for users with both an
sasl_password row and an engine.__member.password row, the gate
decision must be identical across both backends.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import pytest


_HERE = Path(__file__).resolve().parent
_SRC_MCFEELY = _HERE.parent
_SRC_BBSENGINE6 = _SRC_MCFEELY.parent.parent / "bbsengine6" / "py" / "src"
for p in (str(_SRC_MCFEELY), str(_SRC_BBSENGINE6)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mcfeely_authd.auth_verify import _get_crypt_hash  # noqa: E402
from mcfeely_authd.config import load_config  # noqa: E402


def _hash_bcrypt(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"),
                         bcrypt.gensalt(rounds=4, prefix=b"2b")).decode("ascii")


def _hash_sha512_crypt(plaintext: str) -> str:
    import crypt as _crypt
    return _crypt.crypt(plaintext, _crypt.mksalt(_crypt.METHOD_SHA512))


@pytest.fixture(scope="module")
def cfg():
    """Load the default saslauthd config; uses the test DSN by default."""
    return load_config(None)


@pytest.fixture
def now():
    return datetime.now(timezone.utc)


@pytest.fixture
def member_factory(cfg, now):
    """Yield a factory that creates a member + sasl_password row pair.

    Cleanup removes both rows. The factory accepts (moniker, approved,
    sasl_hash, accountexpires) and inserts/upserts both rows.
    """
    created: list[str] = []

    def _make(moniker: str, approved: bool, sasl_hash: str | None,
              accountexpires: datetime | None = None) -> None:
        from bbsengine6 import database
        pool = database.getpool(cfg.make_args())
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Upsert member
                cur.execute(
                    """
                    INSERT INTO engine.__member
                        (moniker, email, password, approved, datecreated,
                         accountexpires)
                    VALUES (%s, %s, NULL, %s, NOW(), %s)
                    ON CONFLICT (moniker) DO UPDATE SET
                        email = EXCLUDED.email,
                        approved = EXCLUDED.approved,
                        accountexpires = EXCLUDED.accountexpires
                    """,
                    (moniker, f"{moniker}@test.local", approved,
                     accountexpires),
                )
                # Upsert sasl_password (or delete if hash is None)
                if sasl_hash is None:
                    cur.execute(
                        "DELETE FROM postoffice.sasl_password "
                        "WHERE member_moniker = %s",
                        (moniker,),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO postoffice.sasl_password
                            (member_moniker, crypt_hash, enabled, datecreated,
                             dateupdated, updated_by)
                        VALUES (%s, %s, true, NOW(), NOW(), 'test')
                        ON CONFLICT (member_moniker) DO UPDATE SET
                            crypt_hash = EXCLUDED.crypt_hash,
                            enabled = true,
                            dateupdated = NOW(),
                            updated_by = 'test'
                        """,
                        (moniker, sasl_hash),
                    )
            conn.commit()
        finally:
            pool.putconn(conn)
        created.append(moniker)

    yield _make

    if not created:
        return
    from bbsengine6 import database
    pool = database.getpool(cfg.make_args())
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM postoffice.sasl_password "
                "WHERE member_moniker = ANY(%s)",
                (created,),
            )
            cur.execute(
                "DELETE FROM engine.__member WHERE moniker = ANY(%s)",
                (created,),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


# ---- gate tests (integration, require DB) -----------------------------------


def test_sasl_password_row_only_returns_hash(cfg, member_factory):
    """A user with a sasl_password row, approved, no expiry: hash returned."""
    h = _hash_sha512_crypt("sasl-pw-1")
    member_factory("test_sasl_alice_001", approved=True, sasl_hash=h)
    result = _get_crypt_hash("test_sasl_alice_001", cfg)
    assert result == h


def test_sasl_password_with_approved_false_returns_none(cfg, member_factory):
    h = _hash_sha512_crypt("sasl-pw-2")
    member_factory("test_sasl_alice_002", approved=False, sasl_hash=h)
    result = _get_crypt_hash("test_sasl_alice_002", cfg)
    assert result is None


def test_sasl_password_disabled_returns_none(cfg, member_factory):
    """enabled=false sasl_password: hash is not returned."""
    from bbsengine6 import database
    h = _hash_sha512_crypt("sasl-pw-3")
    member_factory("test_sasl_alice_003", approved=True, sasl_hash=h)
    # Flip enabled to false after the factory inserts it
    pool = database.getpool(cfg.make_args())
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE postoffice.sasl_password SET enabled = false "
                "WHERE member_moniker = %s",
                ("test_sasl_alice_003",),
            )
        conn.commit()
    finally:
        pool.putconn(conn)
    assert _get_crypt_hash("test_sasl_alice_003", cfg) is None


def test_sasl_password_expired_returns_none(cfg, member_factory, now):
    h = _hash_sha512_crypt("sasl-pw-4")
    member_factory("test_sasl_alice_004", approved=True, sasl_hash=h,
                  accountexpires=now - timedelta(hours=1))
    assert _get_crypt_hash("test_sasl_alice_004", cfg) is None


def test_sasl_password_expires_in_future_returns_hash(cfg, member_factory, now):
    h = _hash_sha512_crypt("sasl-pw-5")
    member_factory("test_sasl_alice_005", approved=True, sasl_hash=h,
                  accountexpires=now + timedelta(hours=1))
    result = _get_crypt_hash("test_sasl_alice_005", cfg)
    assert result == h


def test_sasl_password_null_accountexpires_returns_hash(cfg, member_factory):
    h = _hash_sha512_crypt("sasl-pw-6")
    member_factory("test_sasl_alice_006", approved=True, sasl_hash=h,
                  accountexpires=None)
    result = _get_crypt_hash("test_sasl_alice_006", cfg)
    assert result == h


def test_member_no_sasl_password_returns_none(cfg, member_factory):
    """Approved user, no sasl_password row: returns None (the gate
    only accepts users with a sasl_password row in this path).
    """
    member_factory("test_sasl_alice_007", approved=True, sasl_hash=None)
    assert _get_crypt_hash("test_sasl_alice_007", cfg) is None


def test_no_member_returns_none(cfg):
    assert _get_crypt_hash("definitely_does_not_exist_xyz123", cfg) is None


# ---- parity test -------------------------------------------------------------


def test_parity_with_bbsengine6_auth_verify(cfg, member_factory, now):
    """For users with both an sasl_password row and an engine.__member.password
    row, the saslauthd-path gate and the bbsengine6.auth.verify_member
    gate must return the same decision. Cross-imapd invariant: a user
    gets the same OK/NO from any path that consults the same gate.
    """
    from bbsengine6.auth.verify import verify_member
    import argparse

    # User with sasl + member.password, approved, no expiry, valid pw
    h_sasl = _hash_sha512_crypt("shared-pw-1")
    h_member = _hash_bcrypt("shared-pw-1")
    member_factory("test_sasl_parity_001", approved=True, sasl_hash=h_sasl)
    # Set the member.password for parity test
    from bbsengine6 import database
    pool = database.getpool(cfg.make_args())
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE engine.__member SET password = %s "
                "WHERE moniker = %s",
                (h_member, "test_sasl_parity_001"),
            )
        conn.commit()
    finally:
        pool.putconn(conn)
    args = argparse.Namespace(
        databasename="zoid6test", databasehost="localhost",
        databaseport=5432, databaseuser="opencode",
    )
    # Both gates return True
    assert _get_crypt_hash("test_sasl_parity_001", cfg) == h_sasl
    ok, _ = verify_member("test_sasl_parity_001", "shared-pw-1", args=args, now=now)
    assert ok is True

    # Approved=False: both gates return None/False
    h_sasl_2 = _hash_sha512_crypt("shared-pw-2")
    member_factory("test_sasl_parity_002", approved=False, sasl_hash=h_sasl_2)
    assert _get_crypt_hash("test_sasl_parity_002", cfg) is None
    ok, outcome = verify_member("test_sasl_parity_002", "shared-pw-2",
                                args=args, now=now)
    assert ok is False
    assert outcome == "not-approved"

    # Expired: both gates return None/False
    h_sasl_3 = _hash_sha512_crypt("shared-pw-3")
    member_factory("test_sasl_parity_003", approved=True, sasl_hash=h_sasl_3,
                  accountexpires=now - timedelta(hours=1))
    assert _get_crypt_hash("test_sasl_parity_003", cfg) is None
    ok, outcome = verify_member("test_sasl_parity_003", "shared-pw-3",
                                args=args, now=now)
    assert ok is False
    assert outcome == "sasl-expired"
