# tui/address.py
# Address management for email addresses within domains

import re
from typing import Any, Optional

from bbsengine6.io import echo, inputstring, inputchoice, inputboolean
from bbsengine6.io.echo import echo_traceback
from bbsengine6.util import heading
from bbsengine6 import database
from bbsengine6.listbox import Listbox, ListboxItem


LOCAL_PART_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _help() -> str:
    return "(l)ist, (a)dd, (c)hange, (e)nable/disable, (d)elete, (i)nfo, (q)uit"


def _list_addresses(
    args: Any, pool: Any, domain_id: int, domain_name: str, current_user: str
) -> None:
    echo("")
    heading("Address List")

    sql = """
        SELECT id, local_part, destination, kind, description, enabled, datecreated
        FROM mistermcfeely.address
        WHERE domain_id = %s
        ORDER BY local_part
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain_id,))
                rows = cur.fetchall()

                if not rows:
                    echo(f"No addresses for {domain_name}")
                    echo("Add one: (a)dd")
                    return

                echo(f"Found {len(rows)} address(es):")
                echo("")

                for row in rows:
                    full_addr = f"{row['local_part']}@{domain_name}"
                    dest = row["destination"]
                    kind = row["kind"]
                    enabled = row["enabled"]
                    status = "{green}active{/all}" if enabled else "{red}disabled{/all}"
                    echo(f"  {status} {full_addr}")
                    echo(f"       -> {dest} ({kind})")

                echo("")
                echo(f"Total: {len(rows)} address(es)")

    except Exception:
        echo_traceback("Error listing addresses")


def _validate_destination(args: Any, pool: Any, destination: str, kind: str) -> bool:
    if kind in ("imap", "both"):
        if _mailbox_exists(args, pool, destination):
            return True
        echo(
            f"Destination '{destination}' not found in mailbox database",
            level="warning",
        )
        echo("")
        create = inputboolean(f"Create mailbox '{destination}'? [Y/N]: ", default="N")
        if not create:
            echo("Cancelled - address not created", level="error")
            return False
        return _create_mailbox(args, pool, destination)

    if kind in ("mailman", "both"):
        if _mailman_list_exists(destination):
            return True
        echo(f"Mailman list '{destination}' not found", level="warning")
        echo("")
        create = inputboolean(
            f"Create Mailman list '{destination}'? [Y/N]: ", default="N"
        )
        if not create:
            echo("Cancelled - address not created", level="error")
            return False
        return _create_mailman_list(destination)

    return True


def _create_mailbox(args: Any, pool: Any, address: str) -> bool:
    echo(f"Creating mailbox: {address}")
    maillocation = inputstring("Mail location (default: INBOX): ", args=args) or "INBOX"

    sql = """
        INSERT INTO postoffice.__address (address, maillocation, enabled, datecreated, dateupdated)
        VALUES (%s, %s, true, NOW(), NOW())
        ON CONFLICT (address) DO UPDATE SET
            maillocation = EXCLUDED.maillocation,
            dateupdated = NOW()
        RETURNING address
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (address, maillocation))
                result = cur.fetchone()
        echo(f"Created mailbox: {result['address']} (location: {maillocation})")
        return True
    except Exception:
        echo_traceback("Error creating mailbox")
        return False


def _create_mailman_list(listname: str) -> bool:
    echo("Mailman integration not yet implemented", level="warning")
    echo(f"List '{listname}' was not created")
    return False


def _mailbox_exists(args: Any, pool: Any, destination: str) -> bool:
    if "@" not in destination:
        return False

    sql = (
        "SELECT 1 FROM postoffice.__address WHERE address = %s AND enabled = true LIMIT 1"
    )

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (destination,))
                return cur.rowcount > 0
    except Exception:
        return False


def _mailman_list_exists(listname: str) -> bool:
    return True


def _add_address(
    args: Any, pool: Any, domain_id: int, domain_name: str, current_user: str
) -> None:
    echo("")
    heading("Add New Address")

    local_part = inputstring("Local part (e.g., jam): ", args=args)
    if not local_part:
        echo("Local part cannot be empty", level="error")
        return

    local_part = local_part.strip().lower()

    if not LOCAL_PART_PATTERN.match(local_part):
        echo(
            "Local part can only contain letters, numbers, dash, underscore, dot",
            level="error",
        )
        return

    if "@" in local_part:
        echo("Local part should not contain '@'", level="error")
        return

    destination = inputstring("Destination (user@domain or listname): ", args=args)
    if not destination:
        echo("Destination cannot be empty", level="error")
        return

    echo("Kind: (i)map -> IMAP mailbox, (m)ailman -> mailing list, (b)oth -> both")
    kind_choice = inputchoice("Delivery kind: ", "imb", default="i")

    kind_map = {"i": "imap", "m": "mailman", "b": "both"}
    kind = kind_map.get(kind_choice.lower(), "imap")

    description = inputstring("Description (optional): ", args=args) or None

    if not _validate_destination(args, pool, destination, kind):
        echo("Destination validation failed", level="error")
        return

    sql = """
        INSERT INTO mistermcfeely.address
            (domain_id, local_part, destination, kind, description,
             datecreated, dateupdated, createdby, updatedby)
        VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        domain_id,
                        local_part,
                        destination,
                        kind,
                        description,
                        current_user,
                        current_user,
                    ),
                )
        full_addr = f"{local_part}@{domain_name}"
        echo(f"Added: {full_addr} -> {destination} ({kind})")

    except Exception as e:
        if "unique" in str(e).lower():
            echo(f"Address '{local_part}@{domain_name}' already exists", level="error")
        else:
            echo_traceback("Error adding address")


def _change_address(
    args: Any, pool: Any, domain_id: int, domain_name: str, current_user: str
) -> None:
    address = _select_address(args, pool, domain_id, domain_name)
    if not address:
        return

    echo("")
    heading(f"Change Address: {address['local_part']}@{domain_name}")

    echo(f"Current destination: {address['destination']}")
    new_dest = inputstring(f"New destination [{address['destination']}]: ", args=args)
    if new_dest.strip():
        new_dest = new_dest.strip()
    else:
        new_dest = address["destination"]

    if new_dest != address["destination"]:
        echo("Kind: (i)map, (m)ailman, (b)oth")
        kind_choice = inputchoice(
            "New kind: ", "imb", default=address["kind"][0].lower()
        )
        kind_map = {"i": "imap", "m": "mailman", "b": "both"}
        new_kind = kind_map.get(kind_choice.lower(), address["kind"])
    else:
        new_kind = address["kind"]

    if new_dest != address["destination"] or new_kind != address["kind"]:
        if not _validate_destination(args, pool, new_dest, new_kind):
            echo("Destination validation failed", level="error")
            return

    echo(f"Current description: {address['description'] or '(none)'}")
    new_desc = inputstring("New description: ", args=args)

    sql = """
        UPDATE mistermcfeely.address
        SET destination = %s, kind = %s, description = %s,
            dateupdated = NOW(), updatedby = %s
        WHERE id = %s
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        new_dest,
                        new_kind,
                        new_desc.strip() or None,
                        current_user,
                        address["id"],
                    ),
                )
        echo(f"Updated: {address['local_part']}@{domain_name}")

    except Exception:
        echo_traceback("Error updating address")


def _toggle_enabled(
    args: Any, pool: Any, domain_id: int, domain_name: str, current_user: str
) -> None:
    address = _select_address(args, pool, domain_id, domain_name)
    if not address:
        return

    new_state = not address["enabled"]
    action = "enable" if new_state else "disable"

    confirm = inputboolean(
        f"{action.title()} '{address['local_part']}@{domain_name}'? [Y/N]: ",
        default="N",
    )

    if not confirm:
        echo("Cancelled")
        return

    sql = "UPDATE mistermcfeely.address SET enabled = %s, dateupdated = NOW(), updatedby = %s WHERE id = %s"

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (new_state, current_user, address["id"]))
        echo(f"Address {action}d: {address['local_part']}@{domain_name}")

    except Exception:
        echo_traceback(f"Error {action}ing address")


def _delete_address(args: Any, pool: Any, domain_id: int, domain_name: str) -> None:
    address = _select_address(args, pool, domain_id, domain_name)
    if not address:
        return

    full_addr = f"{address['local_part']}@{domain_name}"
    confirm = inputboolean(f"Delete '{full_addr}'? [Y/N]: ", default="N")

    if not confirm:
        echo("Cancelled")
        return

    sql = "DELETE FROM mistermcfeely.address WHERE id = %s"

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (address["id"],))
        echo(f"Deleted: {full_addr}")

    except Exception:
        echo_traceback("Error deleting address")


def _info_address(args: Any, pool: Any, domain_id: int, domain_name: str) -> None:
    address = _select_address(args, pool, domain_id, domain_name)
    if not address:
        return

    full_addr = f"{address['local_part']}@{domain_name}"
    echo("")
    echo(f"Full Address: {full_addr}")
    echo(f"Destination:  {address['destination']}")
    echo(f"Kind:        {address['kind']}")
    echo(f"Description: {address['description'] or '(none)'}")
    status = "{green}enabled{/all}" if address["enabled"] else "{red}disabled{/all}"
    echo(f"Status:     {status}")
    echo(f"Created:    {address['datecreated']}")
    echo(f"ID:         {address['id']}")


def _select_address(
    args: Any, pool: Any, domain_id: int, domain_name: str
) -> dict | None:
    sql = """
        SELECT id, local_part, destination, kind, description, enabled, datecreated
        FROM mistermcfeely.address
        WHERE domain_id = %s
        ORDER BY local_part
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain_id,))
                rows = cur.fetchall()

                if not rows:
                    echo(f"No addresses for {domain_name}", level="error")
                    return None

                items = []
                for row in rows:
                    full_addr = f"{row['local_part']}@{domain_name}"
                    status = "[*] " if row["enabled"] else "[-] "
                    content = f"{status}{full_addr}"
                    items.append(ListboxItem(content=content, pk=row["id"], data=row))

                lb = Listbox(
                    args,
                    title=f"Addresses: {domain_name}",
                    items=items,
                    itemsperpage=20,
                )
                result = lb.run("Select address: ")

                if result.status == "selected" and result.item:
                    return result.item.data

    except Exception:
        echo_traceback("Error listing addresses")

    return None


def run(
    args: Any,
    moniker: str,
    pool: Optional[Any] = None,
    domain_id: int = 0,
    domain_name: str = "",
    **kwargs,
) -> int:
    """Main address management TUI loop for a specific domain."""
    current_user = getattr(args, "loginid", "system")

    while True:
        echo("")
        heading(f"Addresses: {domain_name}")
        echo("")

        choice = inputchoice(
            "Choose action: ",
            "lacedixq",
            default="l",
            help=_help,
        )

        if choice in ("Q",):
            return 0
        elif choice == "L":
            _list_addresses(args, pool, domain_id, domain_name, current_user)
        elif choice == "A":
            _add_address(args, pool, domain_id, domain_name, current_user)
        elif choice == "C":
            _change_address(args, pool, domain_id, domain_name, current_user)
        elif choice == "E":
            _toggle_enabled(args, pool, domain_id, domain_name, current_user)
        elif choice == "D":
            _delete_address(args, pool, domain_id, domain_name)
        elif choice == "I":
            _info_address(args, pool, domain_id, domain_name)
