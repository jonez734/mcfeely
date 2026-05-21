# member_password.py
# Personal account password management (inbound/outbound)
# Stores encrypted passwords in engine.__member table

from typing import Optional, Dict, Any
from bbsengine6 import database
from bbsengine6.io import echo
from . import password_crypto


def _is_sysop(args: Any) -> bool:
    """Check if current user is a sysop."""
    # Try to get sysop status from args (bbsengine6 convention)
    return getattr(args, "issuperuser", False)


def _can_manage_password(
    requester_moniker: str, target_moniker: str, is_sysop: bool
) -> bool:
    """Check if requester can manage target's password.

    Members can only manage their own passwords.
    Sysops can manage any member's passwords.
    """
    if is_sysop:
        return True
    return requester_moniker == target_moniker


def set_personal_password(
    args: Any,
    member_moniker: str,
    password_type: str,
    password: str,
    set_by_moniker: str,
) -> bool:
    """Set inbound or outbound password for a member's personal account.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        password_type: 'inbound' or 'outbound'.
        password: Plaintext password to store (encrypted).
        set_by_moniker: Moniker of who is setting the password.

    Returns:
        True if successful, False otherwise.

    Raises:
        PermissionError: If non-sysop tries to set another member's password.
        ValueError: If invalid password_type.
    """
    if password_type not in ("inbound", "outbound"):
        raise ValueError(f"Invalid password_type: {password_type}")

    is_sysop = _is_sysop(args)
    if not _can_manage_password(set_by_moniker, member_moniker, is_sysop):
        raise PermissionError(
            f"{set_by_moniker} cannot set password for {member_moniker}"
        )

    try:
        encrypted = password_crypto.encrypt_password(password)
    except Exception as e:
        echo(
            f"member_password.set_personal_password: encryption failed: {e}",
            level="error",
        )
        return False

    column_name = f"{password_type}_password"
    sql = f"UPDATE engine.__member SET {column_name} = %s WHERE moniker = %s"
    dat = (encrypted, member_moniker)

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    echo(
                        f"member_password.set_personal_password: member not found: {member_moniker}",
                        level="error",
                    )
                    return False
        return True
    except Exception as e:
        echo(
            f"member_password.set_personal_password: database error: {e}", level="error"
        )
        return False


def get_personal_password(
    args: Any, member_moniker: str, password_type: str, requester_moniker: str
) -> Optional[str]:
    """Retrieve and decrypt personal account password.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        password_type: 'inbound' or 'outbound'.
        requester_moniker: Who is requesting (for permission check).

    Returns:
        Decrypted password string, or None if not found or permission denied.
    """
    if password_type not in ("inbound", "outbound"):
        echo(
            f"member_password.get_personal_password: invalid password_type: {password_type}",
            level="error",
        )
        return None

    is_sysop = _is_sysop(args)
    if not _can_manage_password(requester_moniker, member_moniker, is_sysop):
        echo(
            f"member_password.get_personal_password: permission denied for {requester_moniker}",
            level="error",
        )
        return None

    column_name = f"{password_type}_password"
    sql = f"SELECT {column_name} FROM engine.__member WHERE moniker = %s"
    dat = (member_moniker,)

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    return None
                row = cur.fetchone()
                encrypted = row[column_name]
                if not encrypted:
                    return None
                return password_crypto.decrypt_password(encrypted)
    except Exception as e:
        echo(f"member_password.get_personal_password: error: {e}", level="error")
        return None


def delete_personal_password(
    args: Any, member_moniker: str, password_type: str, requester_moniker: str
) -> bool:
    """Delete personal account password.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        password_type: 'inbound' or 'outbound'.
        requester_moniker: Who is requesting (for permission check).

    Returns:
        True if successful, False otherwise.

    Raises:
        PermissionError: If non-sysop tries to delete another member's password.
        ValueError: If invalid password_type.
    """
    if password_type not in ("inbound", "outbound"):
        raise ValueError(f"Invalid password_type: {password_type}")

    is_sysop = _is_sysop(args)
    if not _can_manage_password(requester_moniker, member_moniker, is_sysop):
        raise PermissionError(
            f"{requester_moniker} cannot delete password for {member_moniker}"
        )

    column_name = f"{password_type}_password"
    sql = f"UPDATE engine.__member SET {column_name} = NULL WHERE moniker = %s"
    dat = (member_moniker,)

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    echo(
                        f"member_password.delete_personal_password: member not found: {member_moniker}",
                        level="error",
                    )
                    return False
        return True
    except Exception as e:
        echo(
            f"member_password.delete_personal_password: database error: {e}",
            level="error",
        )
        return False


def list_personal_passwords(
    args: Any, member_moniker: str, requester_moniker: str
) -> Dict[str, Dict[str, Any]]:
    """List personal account password metadata (not decrypted).

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Target member's moniker.
        requester_moniker: Who is requesting (for permission check).

    Returns:
        Dictionary with password metadata:
        {
            'inbound': {'exists': True, 'encrypted_len': 123},
            'outbound': {'exists': False}
        }
    """
    is_sysop = _is_sysop(args)
    if not _can_manage_password(requester_moniker, member_moniker, is_sysop):
        echo(
            "member_password.list_personal_passwords: permission denied", level="error"
        )
        return {}

    sql = "SELECT inbound_password, outbound_password FROM engine.__member WHERE moniker = %s"
    dat = (member_moniker,)

    result = {}
    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    return result
                row = cur.fetchone()
                for pwd_type in ["inbound", "outbound"]:
                    encrypted = row.get(f"{pwd_type}_password")
                    if encrypted:
                        result[pwd_type] = {
                            "exists": True,
                            "encrypted_len": len(encrypted),
                        }
                    else:
                        result[pwd_type] = {"exists": False}
        return result
    except Exception as e:
        echo(f"member_password.list_personal_passwords: error: {e}", level="error")
        return {}


__all__ = [
    "set_personal_password",
    "get_personal_password",
    "delete_personal_password",
    "list_personal_passwords",
]
