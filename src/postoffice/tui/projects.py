# tui/projects.py
# Text User Interface for managing projects.zoidtechnologies.com addresses

from typing import Any, Optional

from bbsengine6.io import echo, inputstring, inputchoice
from bbsengine6.io.echo import echo_traceback
from bbsengine6.util import heading
from bbsengine6 import database


DEFAULT_DOMAIN = "projects.zoidtechnologies.com"


def _help() -> str:
    return "(l)ist, (a)dd, (c)hange, (i)nfo, (e)nable, (d)isable, (h)help, (q)uit"


def _show_help() -> None:
    echo("")
    heading("Projects Address Manager Help")
    echo("")
    echo("This tool manages email addresses for projects.zoidtechnologies.com")
    echo("")
    echo("Address Format:")
    echo("  user@projects.zoidtechnologies.com")
    echo("")
    echo("Destination Types:")
    echo("  imap    - Deliver to IMAP mailbox (user@zoidtechnologies.com)")
    echo("  mailman - Deliver to Mailman mailing list")
    echo("  both    - Deliver to both IMAP and Mailman")
    echo("")
    echo("After adding/changing addresses:")
    echo("  1. Deploy etc-postfix/ config to /etc/postfix/")
    echo("  2. Run: postmap /etc/postfix/projects_static")
    echo("  3. Run: systemctl reload postfix")


def _list_addresses(args: Any, pool: Any, current_user: str) -> None:
    echo("")
    heading("Project Addresses")

    sql = """
        SELECT id, address, destination, kind, enabled, datecreated
        FROM mistermcfeely.project
        ORDER BY address
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

                if not rows:
                    echo("No addresses configured")
                    echo("Add one: (a)dd")
                    return

                echo(f"Found {len(rows)} address(es):")
                echo("")

                for row in rows:
                    addr = row["address"]
                    dest = row["destination"]
                    kind = row["kind"]
                    enabled = row["enabled"]
                    status = (
                        "{green}enabled{/all}" if enabled else "{red}disabled{/all}"
                    )
                    echo(f"  {status} {addr}")
                    echo(f"      -> {dest} ({kind})")

                echo("")
                echo(f"Total: {len(rows)} address(es)")

    except Exception:
        echo_traceback("Error listing addresses")


def _add_address(args: Any, pool: Any, current_user: str) -> None:
    echo("")
    heading("Add New Address")

    address = inputstring(f"Address (user@{DEFAULT_DOMAIN}): ", args=args)
    if not address:
        echo("Address cannot be empty", level="error")
        return

    if "@" not in address:
        full_address = f"{address}@{DEFAULT_DOMAIN}"
    else:
        full_address = address

    destination = inputstring(
        "Destination (user@domain or listname@mailman): ", args=args
    )
    if not destination:
        echo("Destination cannot be empty", level="error")
        return

    echo("Kind: (i)map -> user mailbox, (m)ailman -> mailing list, (b)oth -> both")
    kind_choice = inputchoice("Delivery kind: ", "imb", default="i")

    kind_map = {"i": "imap", "m": "mailman", "b": "both"}
    kind = kind_map.get(kind_choice.lower(), "imap")

    description = inputstring("Description (optional): ", args=args) or None

    sql = """
        INSERT INTO mistermcfeely.project
            (address, destination, kind, description, datecreated, dateupdated, createdby, updatedby)
        VALUES (%s, %s, %s, %s, NOW(), NOW(), %s, %s)
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        full_address,
                        destination,
                        kind,
                        description,
                        current_user,
                        current_user,
                    ),
                )
        echo(f"Added: {full_address} -> {destination} ({kind})")
        echo("Note: Run 'make postmap' in etc-postfix/ after deploying config")

    except Exception as e:
        if "unique" in str(e).lower():
            echo(f"Address '{full_address}' already exists", level="error")
        else:
            echo_traceback("Error adding address")


def _change_address(args: Any, pool: Any, current_user: str) -> None:
    echo("")
    heading("Change Address")
    echo("(Note: address field cannot be changed, only destination/kind/description)")

    address = inputstring("Address to change: ", args=args)
    if not address:
        return

    sql = """
        SELECT id, address, destination, kind, description, enabled
        FROM mistermcfeely.project
        WHERE address = %s
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (address,))
                row = cur.fetchone()

                if not row:
                    echo(f"Address '{address}' not found", level="error")
                    return

                echo(
                    f"Current: {row['address']} -> {row['destination']} ({row['kind']})"
                )
                echo(f"Description: {row['description'] or '(none)'}")
                echo("")

                new_dest = inputstring(
                    f"New destination [{row['destination']}]: ", args=args
                )
                new_dest = new_dest.strip() or row["destination"]

                echo("Kind: (i)map, (m)ailman, (b)oth")
                kind_choice = inputchoice(
                    "New kind: ", "imb", default=row["kind"][0].lower()
                )

                kind_map = {"i": "imap", "m": "mailman", "b": "both"}
                new_kind = kind_map.get(kind_choice.lower(), row["kind"])

                new_desc = inputstring(
                    f"New description [{row['description'] or ''}]: ", args=args
                )

                update_sql = """
                    UPDATE mistermcfeely.project
                    SET destination = %s, kind = %s, description = %s,
                        dateupdated = NOW(), updatedby = %s
                    WHERE address = %s
                """

                cur.execute(
                    update_sql,
                    (
                        new_dest,
                        new_kind,
                        new_desc.strip() or None,
                        current_user,
                        address,
                    ),
                )
                echo(f"Updated: {address}")

    except Exception:
        echo_traceback("Error changing address")


def _info_address(args: Any, pool: Any) -> None:
    echo("")
    address = inputstring("Address: ", args=args)
    if not address:
        return

    sql = """
        SELECT id, address, destination, kind, description, enabled,
               datecreated, createdby, dateupdated, updatedby
        FROM mistermcfeely.project
        WHERE address = %s
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (address,))
                row = cur.fetchone()

                if not row:
                    echo(f"Address '{address}' not found", level="error")
                    return

                echo("")
                echo(f"Address:     {row['address']}")
                echo(f"Destination: {row['destination']}")
                echo(f"Kind:        {row['kind']}")
                echo(f"Description: {row['description'] or '(none)'}")
                status = (
                    "{green}enabled{/all}" if row["enabled"] else "{red}disabled{/all}"
                )
                echo(f"Status:      {status}")
                echo(f"Created:    {row['datecreated']} by {row['createdby']}")
                echo(f"Updated:    {row['dateupdated']} by {row['updatedby']}")
                echo(f"ID:         {row['id']}")

    except Exception:
        echo_traceback("Error fetching address info")


def _toggle_enabled(args: Any, pool: Any, current_user: str, enable: bool) -> None:
    action = "enable" if enable else "disable"
    echo("")
    address = inputstring(f"Address to {action}: ", args=args)
    if not address:
        return

    sql = "UPDATE mistermcfeely.project SET enabled = %s, dateupdated = NOW(), updatedby = %s WHERE address = %s"

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (enable, current_user, address))
                if cur.rowcount > 0:
                    echo(f"{action.title()}d: {address}")
                else:
                    echo(f"Address '{address}' not found", level="error")

    except Exception:
        echo_traceback(f"Error {action}ing address")


def run(args: Any, moniker: str, pool: Optional[Any] = None, **kwargs) -> int:
    """Main projects address manager TUI loop."""
    should_close_pool = False

    if pool is None:
        try:
            pool = database.getpool(args)
            should_close_pool = True
        except Exception as e:
            echo(f"Error: Could not connect to database: {e}", level="error")
            return 1

    try:
        current_user = getattr(args, "loginid", None)
        is_sysop = getattr(args, "issuperuser", False)

        if not is_sysop:
            echo(
                "Error: Only administrators can manage projects addresses",
                level="error",
            )
            return 1

        while True:
            echo("")
            heading("Projects Address Manager")
            echo(f"Domain: {DEFAULT_DOMAIN}")
            echo("")

            choice = inputchoice(
                "Choose action: ",
                "laciedhq",
                default="l",
                help=_help,
            )

            if choice in ("Q",):
                echo("Goodbye!")
                return 0
            elif choice == "L":
                _list_addresses(args, pool, current_user)
            elif choice == "A":
                _add_address(args, pool, current_user)
            elif choice == "C":
                _change_address(args, pool, current_user)
            elif choice == "I":
                _info_address(args, pool)
            elif choice == "E":
                _toggle_enabled(args, pool, current_user, True)
            elif choice == "D":
                _toggle_enabled(args, pool, current_user, False)
            elif choice == "H":
                _show_help()

    finally:
        if should_close_pool:
            try:
                pool.closeall()
            except Exception:
                pass

    return 0
