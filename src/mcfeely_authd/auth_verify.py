# auth_verify.py
# Password verification for mcfeely-authd (functional style).
#
# DB access goes through bbsengine6.database (the DAL the rest of
# mistermcfeely uses) rather than a direct psycopg.connect call. This
# gives us a shared connection pool keyed by DSN, autocommit handling,
# and the standard args namespace (databasename / databasehost /
# databaseport / databaseuser / databasepassword).

import subprocess
from typing import Optional, Tuple

from passlib.hash import sha512_crypt

from . import config


def _get_crypt_hash(username: str, cfg: config.Config) -> Optional[str]:
    """Get SHA-512 crypt hash from database.

    Enforces the BBS auth gate (mirrors bbsengine6.auth.verify_member):
      - engine.__member row exists with approved = true
      - postoffice.sasl_password row exists with enabled = true
      - engine.__member.accountexpires IS NULL OR > now()

    Returns the SHA-512 crypt hash iff all three conditions hold.
    Returns None otherwise.

    Note: this path is the legacy Mode B (saslauthd). It accepts only
    users with a row in postoffice.sasl_password. Users with only
    engine.__member.password (BBS web password) are NOT authenticated
    by this path -- they go through bbsengine6-auth-pam via the
    auxprop-pam default. See specs/MCFEELY_CYRUS_IMAP.md for the
    full design.

    Args:
        username: Username to look up
        cfg: Config instance (provides pool + args namespace)

    Returns:
        Crypt hash string, or None if not found / not approved /
        not enabled / expired
    """
    from bbsengine6 import database

    pool = cfg.get_pool()
    args = cfg.make_args()
    with database.connect(args, pool=pool) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.crypt_hash
                  FROM postoffice.sasl_password sp
                  JOIN engine.__member m ON m.moniker = sp.member_moniker
                 WHERE sp.member_moniker = %s
                   AND sp.enabled = true
                   AND m.approved = true
                   AND (m.accountexpires IS NULL
                        OR m.accountexpires > now())
                """,
                (username,),
            )
            row = cur.fetchone()
            if row:
                return row[0]
            return None


def _check_crypt_hash(password: str, crypt_hash: str) -> bool:
    """Check password against SHA-512 crypt hash.

    Args:
        password: Plaintext password
        crypt_hash: SHA-512 crypt hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        return sha512_crypt.verify(password, crypt_hash)
    except Exception:
        return False


def _verify_database(
    username: str, password: str, cfg: config.Config
) -> Tuple[bool, str]:
    """Verify against database (postoffice.sasl_password table).

    Args:
        username: Username to verify
        password: Plaintext password
        cfg: Config instance

    Returns:
        Tuple of (success: bool, reason: str)
    """
    try:
        crypt_hash = _get_crypt_hash(username, cfg)
    except Exception as e:
        return False, f"Database error: {e}"

    if crypt_hash is None:
        return False, "User not found in database"

    if not _check_crypt_hash(password, crypt_hash):
        return False, "Invalid password"

    return True, "Authenticated via database"


def _verify_pam(username: str, password: str) -> Tuple[bool, str]:
    """Verify against PAM (system passwords via saslauthd).

    This uses the saslauthd PAM mechanism if fallback is enabled.

    Args:
        username: Username to verify
        password: Plaintext password

    Returns:
        Tuple of (success: bool, reason: str)
    """
    try:
        result = subprocess.run(
            [
                "/usr/sbin/saslauthd",
                "-a",
                "pam",
                "-p",
                "/run/saslauthd/mux",
                "-n",
                "1",
            ],
            input=f"{username}\n{password}\n".encode(),
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Authenticated via PAM"
    except (subprocess.SubprocessError, OSError):
        pass

    return False, "PAM authentication not available"


def verify_password(
    username: str, password: str, cfg: config.Config
) -> Tuple[bool, str]:
    """Verify username/password.

    First tries database authentication, then falls back to PAM.

    Args:
        username: Username to verify
        password: Plaintext password
        cfg: Config instance

    Returns:
        Tuple of (success: bool, reason: str)
    """
    if not username:
        return False, "Empty username"

    if not password:
        return False, "Empty password"

    success, reason = _verify_database(username, password, cfg)
    if success:
        return True, reason

    if cfg["fallback_pam"]:
        return _verify_pam(username, password)

    return False, reason


def get_user_info(username: str, cfg: config.Config) -> Optional[dict]:
    """Get user information from database.

    Args:
        username: Username to look up
        cfg: Config instance (provides pool + args namespace)

    Returns:
        Dict with user info, or None if not found
    """
    from bbsengine6 import database

    pool = cfg.get_pool()
    args = cfg.make_args()
    with database.connect(args, pool=pool) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT sp.member_moniker, sp.enabled, sp.datecreated, sp.dateupdated,
                       m.email, m.datecreated as member_created
                FROM postoffice.sasl_password sp
                JOIN engine.__member m ON sp.member_moniker = m.moniker
                WHERE sp.member_moniker = %s
                """,
                (username,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "member_moniker": row[0],
                    "enabled": row[1],
                    "datecreated": row[2],
                    "dateupdated": row[3],
                    "email": row[4],
                    "member_created": row[5],
                }
            return None


__all__ = ["verify_password", "get_user_info", "_verify_database", "_verify_pam"]
