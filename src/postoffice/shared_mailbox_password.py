# shared_mailbox_password.py
# Per-member shared mailbox password management
# Stores encrypted passwords in postoffice.member_mailbox_password table

from typing import Optional, Dict, Any, List
from bbsengine6 import database
from bbsengine6.io import echo
from . import password_crypto


def _is_sysop(args: Any) -> bool:
    """Check if current user is a sysop."""
    return getattr(args, "issuperuser", False)


def _can_manage_mailbox_password(
    requester_moniker: str, target_moniker: str, is_sysop: bool
) -> bool:
    """Check if requester can manage target's password for a mailbox.

    Members can only manage their own passwords.
    Sysops can manage any member's passwords.
    """
    if is_sysop:
        return True
    return requester_moniker == target_moniker


def set_shared_mailbox_password(
    args: Any,
    mailbox_id: int,
    member_moniker: str,
    password_type: str,
    password: str,
    set_by_moniker: str,
) -> bool:
    """Set inbound or outbound password for a member accessing a shared mailbox.

    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: ID of the shared mailbox.
        member_moniker: Member's moniker.
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
    if not _can_manage_mailbox_password(set_by_moniker, member_moniker, is_sysop):
        raise PermissionError(
            f"{set_by_moniker} cannot set password for {member_moniker}"
        )

    try:
        encrypted = password_crypto.encrypt_password(password)
    except Exception as e:
        echo(f"shared_mailbox_password.set: encryption failed: {e}", level="error")
        return False

    sql = """
        INSERT INTO postoffice.member_mailbox_password
        (mailbox_id, member_moniker, password_type, encrypted_password, set_by_moniker, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (mailbox_id, member_moniker, password_type)
        DO UPDATE SET encrypted_password = %s, set_by_moniker = %s, updated_at = NOW()
    """
    dat = (
        mailbox_id,
        member_moniker,
        password_type,
        encrypted,
        set_by_moniker,
        encrypted,
        set_by_moniker,
    )

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"shared_mailbox_password.set: database error: {e}", level="error")
        return False


def get_shared_mailbox_password(
    args: Any,
    mailbox_id: int,
    member_moniker: str,
    password_type: str,
    requester_moniker: str,
) -> Optional[str]:
    """Retrieve and decrypt password for member accessing a shared mailbox.

    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: ID of the shared mailbox.
        member_moniker: Member's moniker.
        password_type: 'inbound' or 'outbound'.
        requester_moniker: Who is requesting (for permission check).

    Returns:
        Decrypted password string, or None if not found or permission denied.
    """
    if password_type not in ("inbound", "outbound"):
        echo(
            f"shared_mailbox_password.get: invalid password_type: {password_type}",
            level="error",
        )
        return None

    is_sysop = _is_sysop(args)
    if not _can_manage_mailbox_password(requester_moniker, member_moniker, is_sysop):
        echo("shared_mailbox_password.get: permission denied", level="error")
        return None

    sql = """
        SELECT encrypted_password FROM postoffice.member_mailbox_password
        WHERE mailbox_id = %s AND member_moniker = %s AND password_type = %s
    """
    dat = (mailbox_id, member_moniker, password_type)

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                if cur.rowcount == 0:
                    return None
                row = cur.fetchone()
                encrypted = row["encrypted_password"]
                if not encrypted:
                    return None
                return password_crypto.decrypt_password(encrypted)
    except Exception as e:
        echo(f"shared_mailbox_password.get: error: {e}", level="error")
        return None


def delete_shared_mailbox_password(
    args: Any,
    mailbox_id: int,
    member_moniker: str,
    password_type: str,
    requester_moniker: str,
) -> bool:
    """Delete password for member accessing a shared mailbox.

    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: ID of the shared mailbox.
        member_moniker: Member's moniker.
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
    if not _can_manage_mailbox_password(requester_moniker, member_moniker, is_sysop):
        raise PermissionError(
            f"{requester_moniker} cannot delete password for {member_moniker}"
        )

    sql = """
        DELETE FROM postoffice.member_mailbox_password
        WHERE mailbox_id = %s AND member_moniker = %s AND password_type = %s
    """
    dat = (mailbox_id, member_moniker, password_type)

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
        return True
    except Exception as e:
        echo(f"shared_mailbox_password.delete: database error: {e}", level="error")
        return False


def list_shared_mailbox_passwords(
    args: Any, mailbox_id: int, member_moniker: str, requester_moniker: str
) -> Dict[str, Dict[str, Any]]:
    """List shared mailbox password metadata for a member (not decrypted).

    Args:
        args: bbsengine6 args object with database connection.
        mailbox_id: ID of the shared mailbox.
        member_moniker: Member's moniker.
        requester_moniker: Who is requesting (for permission check).

    Returns:
        Dictionary with password metadata:
        {
            'inbound': {'exists': True, 'encrypted_len': 123, 'set_by': 'jam', 'updated_at': '...'},
            'outbound': {'exists': False}
        }
    """
    is_sysop = _is_sysop(args)
    if not _can_manage_mailbox_password(requester_moniker, member_moniker, is_sysop):
        echo("shared_mailbox_password.list: permission denied", level="error")
        return {}

    sql = """
        SELECT password_type, encrypted_password, set_by_moniker, updated_at
        FROM postoffice.member_mailbox_password
        WHERE mailbox_id = %s AND member_moniker = %s
    """
    dat = (mailbox_id, member_moniker)

    result = {}
    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                for row in cur.fetchall():
                    pwd_type = row["password_type"]
                    result[pwd_type] = {
                        "exists": True,
                        "encrypted_len": len(row["encrypted_password"]),
                        "set_by": row["set_by_moniker"],
                        "updated_at": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else None,
                    }

                # Add missing password types
                for pwd_type in ["inbound", "outbound"]:
                    if pwd_type not in result:
                        result[pwd_type] = {"exists": False}

        return result
    except Exception as e:
        echo(f"shared_mailbox_password.list: error: {e}", level="error")
        return {}


def get_member_mailboxes(args: Any, member_moniker: str) -> List[Dict[str, Any]]:
    """Get list of shared mailboxes that a member has passwords for.

    Args:
        args: bbsengine6 args object with database connection.
        member_moniker: Member's moniker.

    Returns:
        List of mailbox dictionaries with password info.
    """
    sql = """
        SELECT DISTINCT mb.id, mb.address, COUNT(mmp.id) as password_count
        FROM postoffice.mailbox mb
        INNER JOIN postoffice.member_mailbox_password mmp
            ON mb.id = mmp.mailbox_id
        WHERE mmp.member_moniker = %s
        GROUP BY mb.id, mb.address
        ORDER BY mb.address
    """
    dat = (member_moniker,)

    result = []
    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, dat)
                for row in cur.fetchall():
                    result.append(
                        {
                            "id": row["id"],
                            "address": row["address"],
                            "password_count": row["password_count"],
                        }
                    )
        return result
    except Exception as e:
        echo(f"shared_mailbox_password.get_member_mailboxes: error: {e}", level="error")
        return []


__all__ = [
    "set_shared_mailbox_password",
    "get_shared_mailbox_password",
    "delete_shared_mailbox_password",
    "list_shared_mailbox_passwords",
    "get_member_mailboxes",
]
