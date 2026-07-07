# tui/address_domain.py
# Domain management for email address domains

from typing import Any, Optional

from bbsengine6.io import echo, inputstring, inputchoice, inputboolean
from bbsengine6.io.echo import echo_traceback
from bbsengine6.util import heading
from bbsengine6 import database
from bbsengine6.listbox import Listbox, ListboxItem


def _help() -> str:
    return "(l)ist, (a)dd, (c)hange, (i)nfo, m(x)aint (toggle enabled), (q)uit"


def _list_domains(args: Any, pool: Any, current_user: str) -> None:
    echo("")
    heading("Address Domains")

    sql = """
        SELECT id, name, description, enabled, datecreated
        FROM mistermcfeely.address_domain
        ORDER BY name
    """

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

                if not rows:
                    echo("No domains configured")
                    echo("Add one: (a)dd")
                    return

                echo(f"Found {len(rows)} domain(s):")
                echo("")

                for row in rows:
                    name = row["name"]
                    desc = row["description"] or ""
                    enabled = row["enabled"]
                    status = (
                        "{green}enabled{/all}" if enabled else "{red}disabled{/all}"
                    )
                    echo(f"  {status} {name}")
                    if desc:
                        echo(f"      {desc}")

                echo("")
                echo(f"Total: {len(rows)} domain(s)")

    except Exception:
        echo_traceback("Error listing domains")


def _add_domain(args: Any, current_user: str) -> None:
    echo("")
    heading("Add New Domain")

    name = inputstring("Domain name (e.g., projects.zoidtechnologies.com): ", args=args)
    if not name:
        echo("Domain name cannot be empty", level="error")
        return

    name = name.strip().lower()
    if "@" in name:
        echo("Domain name should not contain '@'", level="error")
        return

    description = inputstring("Description (optional): ", args=args) or None

    sql = """
        INSERT INTO mistermcfeely.address_domain
            (name, description, datecreated, dateupdated, createdby, updatedby)
        VALUES (%s, %s, NOW(), NOW(), %s, %s)
    """

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (name, description, current_user, current_user))
        echo(f"Added domain: {name}")
        echo("Generate postfix config in Settings to enable email routing")

    except Exception as e:
        if "unique" in str(e).lower():
            echo(f"Domain '{name}' already exists", level="error")
        else:
            echo_traceback("Error adding domain")


def _change_domain(args: Any, pool: Any, current_user: str) -> None:
    echo("")
    heading("Change Domain")
    echo("(Note: name cannot be changed, only description)")

    domain = _select_domain(args, pool)
    if not domain:
        return

    echo(f"Current description: {domain['description'] or '(none)'}")
    echo("")

    new_desc = inputstring("New description: ", args=args)

    sql = """
        UPDATE mistermcfeely.address_domain
        SET description = %s, dateupdated = NOW(), updatedby = %s
        WHERE id = %s
    """

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (new_desc.strip() or None, current_user, domain["id"]))
        echo(f"Updated domain: {domain['name']}")

    except Exception:
        echo_traceback("Error updating domain")


def _info_domain(args: Any, pool: Any) -> None:
    domain = _select_domain(args, pool)
    if not domain:
        return

    echo("")
    echo(f"Domain:     {domain['name']}")
    echo(f"Description: {domain['description'] or '(none)'}")
    status = "{green}enabled{/all}" if domain["enabled"] else "{red}disabled{/all}"
    echo(f"Status:     {status}")
    echo(f"Created:    {domain['datecreated']}")
    echo(f"ID:         {domain['id']}")

    _show_address_count(args, domain["id"])


def _show_address_count(args: Any, domain_id: int) -> None:
    sql = "SELECT COUNT(*) as cnt FROM mistermcfeely.address WHERE domain_id = %s"
    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain_id,))
                row = cur.fetchone()
                echo(f"Addresses:  {row['cnt']}")
    except Exception:
        pass


def _toggle_enabled(args: Any, pool: Any, current_user: str) -> None:
    domain = _select_domain(args, pool)
    if not domain:
        return

    new_state = not domain["enabled"]
    action = "enable" if new_state else "disable"

    confirm = inputboolean(
        f"{action.title()} domain '{domain['name']}'? [Y/N]: ",
        default="N",
    )

    if not confirm:
        echo("Cancelled")
        return

    sql = "UPDATE mistermcfeely.address_domain SET enabled = %s, dateupdated = NOW(), updatedby = %s WHERE id = %s"

    try:
        with database.connect(args) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (new_state, current_user, domain["id"]))
        echo(f"Domain {action}d: {domain['name']}")

    except Exception:
        echo_traceback(f"Error {action}ing domain")


def _select_domain(args: Any, pool: Any) -> dict | None:
    sql = "SELECT id, name FROM mistermcfeely.address_domain ORDER BY name"

    try:
        with database.connect(args, pool=pool) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

                if not rows:
                    echo("No domains configured", level="error")
                    return None

                items = [
                    ListboxItem(content=row["name"], pk=row["id"], data=row)
                    for row in rows
                ]

                lb = Listbox(args, title="Select Domain", items=items, itemsperpage=20)
                result = lb.run("Select domain: ")

                if result.status == "selected" and result.item:
                    return result.item.data

    except Exception:
        echo_traceback("Error listing domains")

    return None


def run(args: Any, moniker: str, pool: Optional[Any] = None, **kwargs) -> int:
    """Main address domain management TUI loop."""
    current_user = getattr(args, "loginid", "system")

    while True:
        echo("")
        heading("Address Domains")
        echo("")

        choice = inputchoice(
            "Choose action: ",
            "lacixq",
            default="l",
            help=_help,
        )

        if choice in ("Q",):
            return 0
        elif choice == "L":
            _list_domains(args, pool, current_user)
        elif choice == "A":
            _add_domain(args, current_user)
        elif choice == "C":
            _change_domain(args, pool, current_user)
        elif choice == "I":
            _info_domain(args, pool)
        elif choice == "X":
            _toggle_enabled(args, pool, current_user)
