# password/storages/postgresql.py
# PostgreSQL password storage implementation

from typing import Optional, Dict, Any, List

from bbsengine6 import database
from bbsengine6.io import echo

from ..storage import PasswordStorage


class PostgreSQLStorage(PasswordStorage):
    """PostgreSQL password storage backend.
    
    Stores:
    - Personal passwords in engine.__member (inbound_password, outbound_password)
    - Shared mailbox passwords in postoffice.member_mailbox_password
    
    Encrypted passwords are stored as-is from the cipher implementation.
    """

    def __init__(self, args: Any):
        """Initialize with bbsengine6 args object.
        
        Args:
            args: bbsengine6 args object with database connection info.
        """
        self.args = args

    def get_personal_password(
        self, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get encrypted personal account password."""
        if password_type not in ("inbound", "outbound"):
            echo(
                f"PostgreSQLStorage.get_personal_password: invalid password_type: {password_type}",
                level="error",
            )
            return None

        column_name = f"{password_type}_password"
        sql = (
            f"SELECT {column_name} FROM engine.__member WHERE moniker = %s"
        )
        dat = (member_moniker,)

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
                    if cur.rowcount == 0:
                        return None
                    row = cur.fetchone()
                    encrypted = row[column_name]
                    return encrypted if encrypted else None
        except Exception as e:
            echo(
                f"PostgreSQLStorage.get_personal_password: {e}",
                level="error",
            )
            return None

    def set_personal_password(
        self,
        member_moniker: str,
        password_type: str,
        encrypted_password: str,
        set_by_moniker: str,
    ) -> bool:
        """Store encrypted personal account password."""
        if password_type not in ("inbound", "outbound"):
            echo(
                f"PostgreSQLStorage.set_personal_password: invalid password_type",
                level="error",
            )
            return False

        column_name = f"{password_type}_password"
        sql = f"UPDATE engine.__member SET {column_name} = %s WHERE moniker = %s"
        dat = (encrypted_password, member_moniker)

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
                    if cur.rowcount == 0:
                        echo(
                            f"PostgreSQLStorage.set_personal_password: member not found",
                            level="error",
                        )
                        return False
            return True
        except Exception as e:
            echo(
                f"PostgreSQLStorage.set_personal_password: {e}",
                level="error",
            )
            return False

    def delete_personal_password(
        self, member_moniker: str, password_type: str
    ) -> bool:
        """Delete personal account password."""
        if password_type not in ("inbound", "outbound"):
            return False

        column_name = f"{password_type}_password"
        sql = (
            f"UPDATE engine.__member SET {column_name} = NULL WHERE moniker = %s"
        )
        dat = (member_moniker,)

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
            return True
        except Exception as e:
            echo(
                f"PostgreSQLStorage.delete_personal_password: {e}",
                level="error",
            )
            return False

    def list_personal_passwords(
        self, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List personal password metadata."""
        sql = (
            "SELECT inbound_password, outbound_password FROM engine.__member "
            "WHERE moniker = %s"
        )
        dat = (member_moniker,)

        result = {}
        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
                    if cur.rowcount == 0:
                        return result
                    row = cur.fetchone()
                    for pwd_type in ["inbound", "outbound"]:
                        encrypted = row.get(f"{pwd_type}_password")
                        if encrypted:
                            result[pwd_type] = {"exists": True}
                        else:
                            result[pwd_type] = {"exists": False}
            return result
        except Exception as e:
            echo(
                f"PostgreSQLStorage.list_personal_passwords: {e}",
                level="error",
            )
            return {}

    def get_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str
    ) -> Optional[str]:
        """Get encrypted password for member on shared mailbox."""
        if password_type not in ("inbound", "outbound"):
            return None

        sql = (
            "SELECT encrypted_password FROM postoffice.member_mailbox_password "
            "WHERE mailbox_id = %s AND member_moniker = %s AND password_type = %s"
        )
        dat = (mailbox_id, member_moniker, password_type)

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
                    if cur.rowcount == 0:
                        return None
                    row = cur.fetchone()
                    encrypted = row["encrypted_password"]
                    return encrypted if encrypted else None
        except Exception as e:
            echo(
                f"PostgreSQLStorage.get_shared_mailbox_password: {e}",
                level="error",
            )
            return None

    def set_shared_mailbox_password(
        self,
        mailbox_id: int,
        member_moniker: str,
        password_type: str,
        encrypted_password: str,
        set_by_moniker: str,
    ) -> bool:
        """Store encrypted password for member on shared mailbox."""
        if password_type not in ("inbound", "outbound"):
            return False

        sql = (
            "INSERT INTO postoffice.member_mailbox_password "
            "(mailbox_id, member_moniker, password_type, encrypted_password, "
            "set_by_moniker, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, NOW(), NOW()) "
            "ON CONFLICT (mailbox_id, member_moniker, password_type) "
            "DO UPDATE SET encrypted_password = %s, set_by_moniker = %s, updated_at = NOW()"
        )
        dat = (
            mailbox_id,
            member_moniker,
            password_type,
            encrypted_password,
            set_by_moniker,
            encrypted_password,
            set_by_moniker,
        )

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
            return True
        except Exception as e:
            echo(
                f"PostgreSQLStorage.set_shared_mailbox_password: {e}",
                level="error",
            )
            return False

    def delete_shared_mailbox_password(
        self, mailbox_id: int, member_moniker: str, password_type: str
    ) -> bool:
        """Delete password for member on shared mailbox."""
        if password_type not in ("inbound", "outbound"):
            return False

        sql = (
            "DELETE FROM postoffice.member_mailbox_password "
            "WHERE mailbox_id = %s AND member_moniker = %s AND password_type = %s"
        )
        dat = (mailbox_id, member_moniker, password_type)

        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
            return True
        except Exception as e:
            echo(
                f"PostgreSQLStorage.delete_shared_mailbox_password: {e}",
                level="error",
            )
            return False

    def list_shared_mailbox_passwords(
        self, mailbox_id: int, member_moniker: str
    ) -> Dict[str, Dict[str, Any]]:
        """List passwords for member on shared mailbox."""
        sql = (
            "SELECT password_type, encrypted_password, set_by_moniker, updated_at "
            "FROM postoffice.member_mailbox_password "
            "WHERE mailbox_id = %s AND member_moniker = %s"
        )
        dat = (mailbox_id, member_moniker)

        result = {}
        try:
            with database.connect(self.args) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, dat)
                    for row in cur.fetchall():
                        pwd_type = row["password_type"]
                        result[pwd_type] = {
                            "exists": True,
                            "set_by": row["set_by_moniker"],
                            "updated_at": (
                                row["updated_at"].isoformat()
                                if row["updated_at"]
                                else None
                            ),
                        }

                    for pwd_type in ["inbound", "outbound"]:
                        if pwd_type not in result:
                            result[pwd_type] = {"exists": False}

            return result
        except Exception as e:
            echo(
                f"PostgreSQLStorage.list_shared_mailbox_passwords: {e}",
                level="error",
            )
            return {}

    def get_member_mailboxes(self, member_moniker: str) -> List[Dict[str, Any]]:
        """Get list of mailboxes member has passwords for."""
        sql = (
            "SELECT DISTINCT mb.id, mb.address, "
            "COUNT(mmp.id) as password_count "
            "FROM postoffice.mailbox mb "
            "INNER JOIN postoffice.member_mailbox_password mmp "
            "ON mb.id = mmp.mailbox_id "
            "WHERE mmp.member_moniker = %s "
            "GROUP BY mb.id, mb.address "
            "ORDER BY mb.address"
        )
        dat = (member_moniker,)

        result = []
        try:
            with database.connect(self.args) as conn:
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
            echo(
                f"PostgreSQLStorage.get_member_mailboxes: {e}",
                level="error",
            )
            return []


__all__ = ["PostgreSQLStorage"]
