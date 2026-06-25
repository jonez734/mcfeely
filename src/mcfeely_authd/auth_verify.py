# auth_verify.py
# Password verification for mcfeely-authd (functional style)

import subprocess
from typing import Optional, Tuple

from passlib.hash import sha512_crypt

from . import config


def _get_crypt_hash(username: str, cfg: config.Config) -> Optional[str]:
    """Get SHA-512 crypt hash from database.

    Args:
        username: Username to look up
        cfg: Config instance

    Returns:
        Crypt hash string, or None if not found
    """
    db_args = cfg.get_database_args()

    try:
        import psycopg2
    except ImportError:
        return None

    conn = None
    try:
        conn = psycopg2.connect(**db_args)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT crypt_hash FROM postoffice.sasl_password
            WHERE member_moniker = %s AND enabled = true
            """,
            (username,),
        )

        row = cur.fetchone()
        if row:
            return row[0]
        return None

    finally:
        if conn:
            conn.close()


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
                "/var/run/saslauthd/mux",
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
    """Verify username/password combination.

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

    if cfg.fallback_pam:
        return _verify_pam(username, password)

    return False, reason


def get_user_info(username: str, cfg: config.Config) -> Optional[dict]:
    """Get user information from database.

    Args:
        username: Username to look up
        cfg: Config instance

    Returns:
        Dict with user info, or None if not found
    """
    db_args = cfg.get_database_args()

    try:
        import psycopg2
    except ImportError:
        return None

    conn = None
    try:
        conn = psycopg2.connect(**db_args)
        cur = conn.cursor()

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

    finally:
        if conn:
            conn.close()


__all__ = ["verify_password", "get_user_info", "_verify_database", "_verify_pam"]
