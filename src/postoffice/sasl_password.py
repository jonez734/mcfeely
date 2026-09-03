# sasl_password.py
# SASL password management for postoffice-authd daemon
# Stores SHA-512 crypt hashes for PAM/saslauthd-compatible authentication

from passlib.hash import sha512_crypt
from typing import Optional, Any

from bbsengine6 import database
from bbsengine6.io import echo
from bbsengine6.io.echo import echo_traceback


def _is_sysop(args: Any) -> bool:
    """Check if current user is a sysop."""
    return getattr(args, "issuperuser", False)


def _can_manage_password(
    requester_moniker: str, target_moniker: str, is_sysop: bool
) -> bool:
    """Check if requester can manage target's SASL password.

    Members can only manage their own SASL passwords.
    Sysops can manage any member's passwords.
    """
    if is_sysop:
        return True
    return requester_moniker == target_moniker


def _get_db_pool(args: Any):
    """Get or create database pool from args."""
    return database.getpool(args)


def generate_crypt_hash(password: str) -> str:
    """Generate SHA-512 crypt hash from plaintext password.

    Args:
        password: Plaintext password to hash

    Returns:
        SHA-512 crypt hash string (format: $6$<salt>$<hash>)
    """
    return sha512_crypt.using(rounds=5000).hash(password)


def verify_crypt_hash(password: str, crypt_hash: str) -> bool:
    """Verify password against SHA-512 crypt hash.

    Args:
        password: Plaintext password to verify
        crypt_hash: SHA-512 crypt hash to verify against

    Returns:
        True if password matches, False otherwise
    """
    if not password or not crypt_hash:
        return False
    try:
        return sha512_crypt.verify(password, crypt_hash)
    except Exception:
        echo_traceback("sasl_password.verify_sasl_password")
        return False


def set_sasl_password(
    args: Any,
    member_moniker: str,
    password: str,
    updated_by: str,
    enabled: bool = True,
) -> bool:
    """Set SASL password (SHA-512 crypt hash) for a member.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        password: Plaintext password to hash and store.
        updated_by: Moniker of who is setting the password.
        enabled: Whether the password is enabled for auth.

    Returns:
        True if successful, False otherwise.

    Raises:
        PermissionError: If non-sysop tries to set another member's password.
    """
    if not password:
        echo("sasl_password.set_sasl_password: empty password", level="error")
        return False

    is_sysop = _is_sysop(args)
    if not _can_manage_password(updated_by, member_moniker, is_sysop):
        raise PermissionError(
            f"{updated_by} cannot set SASL password for {member_moniker}"
        )

    crypt_hash = generate_crypt_hash(password)

    sql = """
        INSERT INTO postoffice.sasl_password
            (member_moniker, crypt_hash, enabled, datecreated, dateupdated, updated_by)
        VALUES (%s, %s, %s, NOW(), NOW(), %s)
        ON CONFLICT (member_moniker)
        DO UPDATE SET
            crypt_hash = EXCLUDED.crypt_hash,
            enabled = EXCLUDED.enabled,
            dateupdated = NOW(),
            updated_by = EXCLUDED.updated_by
    """
    dat = (member_moniker, crypt_hash, enabled, updated_by)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"sasl_password.set_sasl_password: database error: {e}", level="error")
        return False


def get_sasl_password(args: Any, member_moniker: str) -> Optional[str]:
    """Retrieve crypt hash for a member's SASL password.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.

    Returns:
        SHA-512 crypt hash string, or None if not found or disabled.
    """
    sql = """
        SELECT crypt_hash FROM postoffice.sasl_password
        WHERE member_moniker = %s AND enabled = true
    """
    dat = (member_moniker,)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    return None
                row = cur.fetchone()
                return row["crypt_hash"]
    except Exception as e:
        echo(f"sasl_password.get_sasl_password: database error: {e}", level="error")
        return None


def delete_sasl_password(args: Any, member_moniker: str) -> bool:
    """Delete SASL password for a member.

    This removes the database authentication option.
    The user will fall back to PAM (shell password) if available.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.

    Returns:
        True if successful, False otherwise.
    """
    sql = "DELETE FROM postoffice.sasl_password WHERE member_moniker = %s"
    dat = (member_moniker,)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"sasl_password.delete_sasl_password: database error: {e}", level="error")
        return False


def disable_sasl_password(args: Any, member_moniker: str) -> bool:
    """Disable SASL password without deleting it.

    Useful for temporarily disabling auth without removing the password.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.

    Returns:
        True if successful, False otherwise.
    """
    sql = """
        UPDATE postoffice.sasl_password
        SET enabled = false, dateupdated = NOW()
        WHERE member_moniker = %s
    """
    dat = (member_moniker,)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"sasl_password.disable_sasl_password: database error: {e}", level="error")
        return False


def enable_sasl_password(args: Any, member_moniker: str) -> bool:
    """Re-enable a previously disabled SASL password.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.

    Returns:
        True if successful, False otherwise.
    """
    sql = """
        UPDATE postoffice.sasl_password
        SET enabled = true, dateupdated = NOW()
        WHERE member_moniker = %s
    """
    dat = (member_moniker,)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"sasl_password.enable_sasl_password: database error: {e}", level="error")
        return False


def exists_sasl_password(args: Any, member_moniker: str) -> bool:
    """Check if member has a SASL password entry.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.

    Returns:
        True if entry exists (enabled or not), False otherwise.
    """
    sql = """
        SELECT 1 FROM postoffice.sasl_password
        WHERE member_moniker = %s
    """
    dat = (member_moniker,)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
                return cur.rowcount > 0
    except Exception as e:
        echo(f"sasl_password.exists_sasl_password: database error: {e}", level="error")
        return False


def list_sasl_passwords(args: Any) -> list:
    """List all SASL password entries.

    Args:
        args: bbsengine6 args object with database connection.

    Returns:
        List of dicts with member info: moniker, enabled, datecreated, dateupdated, updated_by
    """
    sql = """
        SELECT member_moniker, enabled, datecreated, dateupdated, updated_by
        FROM postoffice.sasl_password
        ORDER BY datecreated DESC
    """

    result = []
    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql)
                for row in cur.fetchall():
                    result.append(
                        {
                            "member_moniker": row["member_moniker"],
                            "enabled": row["enabled"],
                            "datecreated": row["datecreated"].isoformat()
                            if row["datecreated"]
                            else None,
                            "dateupdated": row["dateupdated"].isoformat()
                            if row["dateupdated"]
                            else None,
                            "updated_by": row["updated_by"],
                        }
                    )
        return result
    except Exception as e:
        echo(f"sasl_password.list_sasl_passwords: database error: {e}", level="error")
        return []


def set_sasl_password_for_sync(
    args: Any,
    member_moniker: str,
    password: str,
    updated_by: str,
) -> tuple[bool, str]:
    """Set SASL password synchronously with the encrypted password.

    This is a convenience function that should be called when setting
    the encrypted IMAP password in engine.__member. It ensures both
    passwords are in sync.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        password: Plaintext password to hash and store.
        updated_by: Moniker of who is setting the password.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    if not password:
        return False, "Empty password"

    try:
        crypt_hash = generate_crypt_hash(password)
    except Exception as e:
        return False, f"Failed to generate crypt hash: {e}"

    sql = """
        INSERT INTO postoffice.sasl_password
            (member_moniker, crypt_hash, enabled, datecreated, dateupdated, updated_by)
        VALUES (%s, %s, true, NOW(), NOW(), %s)
        ON CONFLICT (member_moniker)
        DO UPDATE SET
            crypt_hash = EXCLUDED.crypt_hash,
            enabled = true,
            dateupdated = NOW(),
            updated_by = EXCLUDED.updated_by
    """
    dat = (member_moniker, crypt_hash, updated_by)

    try:
        pool = _get_db_pool(args)
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(sql, dat)
        return True, ""
    except Exception as e:
        return False, str(e)


__all__ = [
    "generate_crypt_hash",
    "verify_crypt_hash",
    "set_sasl_password",
    "get_sasl_password",
    "delete_sasl_password",
    "disable_sasl_password",
    "enable_sasl_password",
    "exists_sasl_password",
    "list_sasl_passwords",
    "set_sasl_password_for_sync",
]
