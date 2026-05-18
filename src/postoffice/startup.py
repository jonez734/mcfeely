# startup.py
# Initializes the postoffice schema, tables, privileges, and configuration.

from bbsengine6 import database, io


def init(args, **kwargs) -> bool:
    """Module init - no-op for startup module."""
    return True


def access(args, op, **kwargs) -> bool:
    """All operations allowed."""
    return True


def buildargs(args, **kwargs):
    """No additional arguments."""
    return None


def main(args, **kwargs) -> bool:
    """Initialize postoffice schema and tables on startup."""

    def _work(conn):
        io.echo("running postoffice startup...")

        # --- schema ---
        io.echo(f"{{var:labelcolor}}schema {{var:valuecolor}}postoffice{{var:labelcolor}}: ", end="")
        if not database.schemaexists(args, "postoffice", conn=conn):
            io.echo("create ", end="")
            if not database.createschema(args, "postoffice", conn=conn):
                io.echo(" fail ", level="error")
                return False
        io.echo("  ok  ", level="ok")

        # --- tables (in dependency order) ---
        tables = (
            ("postoffice.mailbox", "mailbox.sql"),
            ("postoffice.virtual", "virtual.sql"),
            ("postoffice.__message", "message.sql"),
            ("postoffice.notification_routing", "notification_routing.sql"),
            ("postoffice.notification_config", "notification_config.sql"),
        )

        failcount = 0
        for table, sqlfile in tables:
            io.echo(
                f"{{var:labelcolor}}table {{var:valuecolor}}{table}{{var:labelcolor}}: ",
                end="",
            )
            if not database.classexists(args, table, conn=conn):
                io.echo("import ", end="")
                if not database.importsql(
                    args, sqlfile, conn=conn, package="postoffice.sql"
                ):
                    io.echo(" fail ", level="error")
                    failcount += 1
                else:
                    io.echo("  ok  ", level="ok")
            else:
                io.echo("  ok  ", level="ok")

        if failcount > 0:
            io.echo("table setup failed", level="error")
            conn.rollback()
            return False

        # --- notification history view ---
        io.echo(
            f"{{var:labelcolor}}view {{var:valuecolor}}postoffice.notification_history{{var:labelcolor}}: ",
            end="",
        )
        try:
            # Create view (idempotent via CREATE OR REPLACE)
            create_view_sql = """
            CREATE OR REPLACE VIEW postoffice.notification_history AS
            SELECT
                n.id,
                n.notification_type,
                n.sender_moniker,
                n.rendered_message,
                n.data,
                n.urgency,
                n.datecreated,
                (n.data->>'mailbox_name')::TEXT as mailbox_name,
                (n.data->>'event_type')::TEXT as event_type,
                (n.data->>'message_uid')::INTEGER as message_uid,
                (n.data->>'actor_moniker')::TEXT as actor_moniker
            FROM engine.__notify n
            WHERE n.notification_type LIKE 'mcfeely-%'
            ORDER BY n.datecreated DESC;
            """
            with database.cursor(conn) as cur:
                cur.execute(create_view_sql)
            io.echo("  ok  ", level="ok")
        except Exception as e:
            io.echo(f" fail ({e})", level="error")
            failcount += 1

        if failcount > 0:
            io.echo("view setup failed", level="error")
            conn.rollback()
            return False

        # --- schema privileges ---
        io.echo(
            f"{{var:labelcolor}}schema {{var:valuecolor}}postoffice {{var:labelcolor}}privs: ",
            end="",
        )
        for role in ("web", "term", "sysop"):
            if not database.manage_schema_priv(
                args, "grant", "usage", "postoffice", role, conn=conn
            ):
                io.echo(f"fail ({role})", level="error")
                failcount += 1

        if not database.manage_schema_priv(
            args, "grant", "create", "postoffice", "sysop", conn=conn
        ):
            io.echo("fail (sysop create)", level="error")
            failcount += 1

        if failcount > 0:
            io.echo("privilege setup failed", level="error")
            conn.rollback()
            return False

        io.echo("  ok  ", level="ok")

        conn.commit()
        return True

    conn = kwargs.get("conn", None)
    if conn is None:
        pool = kwargs.get("pool", None)
        if pool is None:
            io.echo("postoffice.startup.100: no pool", level="error")
            return False
        with database.connect(args, pool=pool) as conn:
            return _work(conn)
    return _work(conn)
