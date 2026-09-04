# startup_test.py
# Test data generator and API verifier for postoffice
# Creates test members, sends messages, verifies notify flow, sets up mailboxes

import argparse
import os
import base64
import random
from typing import Optional

# Set BBSENGINE6_DBNAME so notify functions that create their own connections use the right db
os.environ["BBSENGINE6_DBNAME"] = "zoid6test"

from bbsengine6 import database, io, member, message as message_module
from bbsengine6.startup import main as bbsengine6_startup_main
from postoffice import startup
from postoffice.shared_mailbox_password import set_shared_mailbox_password


_LOREM_WORDS = [
    "lorem",
    "ipsum",
    "dolor",
    "sit",
    "amet",
    "consectetur",
    "adipiscing",
    "elit",
    "sed",
    "do",
    "eiusmod",
    "tempor",
    "incididunt",
    "ut",
    "labore",
    "et",
    "dolore",
    "magna",
    "aliqua",
    "enim",
    "ad",
    "minim",
    "veniam",
    "quis",
    "nostrud",
    "exercitation",
    "ullamco",
    "laboris",
    "nisi",
    "aliquip",
    "ex",
    "ea",
    "commodo",
    "consequat",
    "duis",
    "aute",
    "irure",
    "in",
    "reprehenderit",
    "voluptate",
    "velit",
    "esse",
    "cillum",
    "fugiat",
    "nulla",
    "pariatur",
    "excepteur",
    "sint",
    "occaecat",
    "cupidatat",
    "non",
    "proident",
    "sunt",
    "culpa",
    "qui",
    "officia",
    "deserunt",
    "mollit",
    "anim",
    "id",
    "est",
    "laborum",
    "pellentesque",
    "habitant",
    "morbi",
    "tristique",
    "senectus",
    "netus",
    "malesuada",
    "fames",
    "turpis",
    "egestas",
]


def _generate_paragraph(
    min_sentences: int = 3,
    max_sentences: int = 8,
    min_words: int = 8,
    max_words: int = 20,
) -> str:
    num_sentences = random.randint(min_sentences, max_sentences)
    sentences = []
    for _ in range(num_sentences):
        num_words = random.randint(min_words, max_words)
        words = [random.choice(_LOREM_WORDS) for _ in range(num_words)]
        words[0] = words[0].capitalize()
        sentences.append(" ".join(words) + ".")
    return " ".join(sentences)


def _ensure_encryption_key() -> bytes:
    key_b64 = os.environ.get("POSTOFFICE_PASSWORD_KEY")
    if key_b64:
        try:
            key = base64.b64decode(key_b64)
            if len(key) == 32:
                return key
        except Exception:
            pass

    key = os.urandom(32)
    key_b64 = base64.b64encode(key).decode()

    key_dir = os.path.expanduser("~/.postoffice")
    os.makedirs(key_dir, mode=0o700, exist_ok=True)
    key_path = os.path.join(key_dir, "password.key")
    with open(key_path, "wb") as f:
        f.write(key)
    os.chmod(key_path, 0o600)

    os.environ["POSTOFFICE_PASSWORD_KEY"] = key_b64
    io.echo(f"Generated encryption key, stored at {key_path}", level="ok")
    return key


def _check_database(args) -> bool:
    with database.getpool(args, dbname="postgres") as pool:
        if database.exists(args, args.databasename, pool=pool):
            return True
        if args.create_database:
            if database.create(args, args.databasename, pool=pool):
                io.echo(f"Database {args.databasename} created", level="ok")
                return True
            io.echo(f"Failed to create database {args.databasename}", level="error")
            return False
        io.echo(
            f"Database {args.databasename} does not exist. "
            "Run with --create-database to create it.",
            level="error",
        )
        return False


def _ensure_tables(args, pool) -> bool:
    with database.connect(args, pool=pool) as conn:
        if not bbsengine6_startup_main(args, conn=conn):
            io.echo("bbsengine6 engine/notify tables unavailable", level="error")
            return False
        if not startup.startup_main(args, conn=conn):
            io.echo("postoffice tables unavailable", level="error")
            return False
    return True


def _ensure_member(args, pool, moniker: str) -> bool:
    with database.connect(args, pool=pool) as conn:
        if member.moniker_exists(args, moniker, pool=pool):
            io.echo(f"member {moniker}: exists", level="ok")
            return True
        io.echo(f"member {moniker}: creating...", end="")
        try:
            result = member.insert(
                args,
                {"moniker": moniker, "email": f"{moniker}@localhost.local"},
                conn=conn,
                returnid=False,
            )
            if not result:
                io.echo(" member.insert failed", level="error")
                conn.rollback()
                return False
            member.setflag(args, "APPROVED", True, moniker=moniker, conn=conn)
            member.setpassword(args, "testpass", moniker, conn=conn)
            conn.commit()
            io.echo(" created", level="ok")
            return True
        except Exception as e:
            io.echo(f" failed: {e}", level="error")
            conn.rollback()
            return False


def _phase_messages(args, pool) -> list[tuple[int, str]]:
    with database.connect(args, pool=pool) as conn:
        with database.cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO engine.__message_type
                    (type_name, description, rate_limit_per_hour, requires_approval)
                VALUES ('demo_message', 'Demo messages from startup_test', 0, false)
                ON CONFLICT (type_name) DO NOTHING
                """
            )
            io.echo("  registered type", level="ok")
        conn.commit()

    sent = []
    for i in range(3 + random.randint(1, 4)):
        paragraph = _generate_paragraph()
        msg_id = message_module.store_message(
            channel="demo_message",
            sender_moniker="bob",
            content=paragraph[:100],
            recipient_monikers=["alice"],
            template="{message}",
            template_vars={"message": paragraph[:100]},
            data={"index": i + 1},
            database=args.databasename,
        )
        sent.append((msg_id, paragraph))
        io.echo(f"  sent message {i + 1} (id={msg_id})")

    return sent


def _phase_notify_processing(args, pool, sent_ids: list[int]) -> bool:
    io.echo("Phase 4: notify processing test...")

    notifications = message_module.get_pending_messages(
        "alice", limit=50, database=args.databasename
    )
    io.echo(f"  alice has {len(notifications)} notifications")
    if not notifications:
        io.echo("  FAIL: no notifications found for alice", level="error")
        return False

    unread_count = message_module.get_unread_count(
        "alice", args=args, pool=pool
    )
    io.echo(f"  unread count: {unread_count}")

    bob_notifs = [n for n in notifications if n["sender_moniker"] == "bob"]
    if not bob_notifs:
        io.echo("  FAIL: no notifications from bob found for alice", level="error")
        return False

    first = bob_notifs[0]
    first_id = first["id"]
    io.echo(f"  first bob notification: sender={first['sender_moniker']}, id={first_id}")

    message_module.mark_read(first_id, "alice", database=args.databasename)
    unread_after = message_module.get_unread_count("alice", args=args, pool=pool)
    io.echo(f"  after mark_read, unread count: {unread_after}")

    message_module.expunge(first_id, "bob", database=args.databasename)
    notifications_after = message_module.get_pending_messages(
        "alice", limit=10, database=args.databasename
    )
    io.echo(f"  after expunge, notifications: {len(notifications_after)}")
    if any(n["id"] == first_id for n in notifications_after):
        io.echo("  FAIL: expunged notification still present", level="error")
        return False

    io.echo("  notify processing: all checks passed", level="ok")
    return True


def _phase_mailboxes(args, pool) -> bool:
    io.echo("Phase 5: mailbox setup...")

    with database.connect(args, pool=pool) as conn:
        with database.cursor(conn) as cur:
            cur.execute(
                "SELECT 1 FROM postoffice.shared_mailbox WHERE name=%s",
                ("shared/trouble",),
            )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO postoffice.shared_mailbox (name, description, createdbymoniker)
                    VALUES (%s, %s, %s) RETURNING id
                    """,
                    ("shared/trouble", "Shared mailbox for testing", "startup_test"),
                )
                result = cur.fetchone()
                io.echo(f"  shared/trouble created (id={result['id']})", level="ok")
            else:
                io.echo("  shared/trouble: exists", level="ok")

    for moniker in ("alice", "bob"):
        with database.connect(args, pool=pool) as conn:
            with database.cursor(conn) as cur:
                cur.execute(
                    "SELECT address FROM postoffice.__address WHERE address=%s",
                    (moniker,),
                )
                row = cur.fetchone()
                if row:
                    address = row["address"]
                    io.echo(
                        f"  mailbox {moniker}: exists (address={address})", level="ok"
                    )
                else:
                    address = moniker
                    cur.execute(
                        """
                        INSERT INTO postoffice.__address (address, maillocation, enabled)
                        VALUES (%s, %s, %s)
                        """,
                        (address, f"maildir:~{moniker}/Maildir", True),
                    )
                    io.echo(
                        f"  mailbox {moniker}: created (address={address})", level="ok"
                    )

            pw = os.urandom(16).hex()
            set_shared_mailbox_password(args, address, moniker, "inbound", pw, moniker)
            set_shared_mailbox_password(args, address, moniker, "outbound", pw, moniker)
            conn.commit()
            io.echo(
                f'  Mailbox "{moniker}" (address={address}). IMAP password: {pw}',
                level="ok",
            )

    return True


def buildargs(
    parentparser: Optional[argparse.ArgumentParser] = None,
) -> argparse.ArgumentParser:
    if parentparser is None:
        parentparser = argparse.ArgumentParser(description="postoffice startup test")
    database.buildargs(parentparser, defaults={"databasename": "zoid6test"})
    parentparser.add_argument(
        "--create-database",
        action="store_true",
        help="create the database if it does not exist",
    )
    parentparser.add_argument(
        "--verbose",
        action="store_true",
        help="enable verbose output",
    )
    parentparser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be done without doing it",
    )
    return parentparser


def main(args: Optional[argparse.Namespace] = None) -> int:
    if args is None:
        parser = buildargs()
        args = parser.parse_args()

    args.debug = args.verbose if hasattr(args, "verbose") else False

    io.echo("postoffice startup_test starting...")

    _ensure_encryption_key()

    os.environ["BBSENGINE6_DBNAME"] = args.databasename

    if not _check_database(args):
        return 1

    with database.getpool(args) as pool:
        if not _ensure_tables(args, pool):
            return 1

        for moniker in ("alice", "bob"):
            if not _ensure_member(args, pool, moniker):
                return 1

        sent = _phase_messages(args, pool)
        if not _phase_notify_processing(args, pool, [tid for tid, _ in sent]):
            return 1

        if not _phase_mailboxes(args, pool):
            return 1

    io.echo("postoffice startup_test complete", level="ok")
    return 0


if __name__ == "__main__":
    exit(main())
