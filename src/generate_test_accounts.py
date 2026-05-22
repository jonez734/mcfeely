#!/usr/bin/env python3
# generate_test_accounts.py
# Standalone script to generate test user accounts and shared mailboxes

import argparse
import sys
import string
import random

# Import postoffice modules
try:
    from postoffice import startup
    from bbsengine6.io import echo, inputboolean
    from bbsengine6 import database
except ImportError:
    print("Error: postoffice module not found. Run from mistermcfeely/src directory.")
    sys.exit(1)


def buildargs(args=None, **kw):
    """Build argument parser with database configuration."""
    parser = argparse.ArgumentParser("generate_test_accounts")
    parser.add_argument("--verbose", action="store_true", dest="verbose")
    parser.add_argument("--debug", action="store_true", dest="debug")
    parser.add_argument("--issuperuser", action="store_true", dest="issuperuser", default=True,
                        help="Run as superuser (default: True)")

    parser.add_argument(
        "-n", "--num-accounts",
        type=int,
        default=5,
        help="Number of test accounts to create (default: 5)",
    )

    parser.add_argument(
        "-m", "--num-mailboxes",
        type=int,
        default=3,
        help="Number of shared mailboxes to create (default: 3)",
    )

    parser.add_argument(
        "--skip-mailboxes",
        action="store_true",
        help="Skip mailbox creation if postoffice schema is not available",
    )

    parser.add_argument(
        "--create-schema",
        action="store_true",
        help="Create postoffice.shared_mailbox schema if it doesn't exist",
    )

    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Don't prompt for schema creation, use --create-schema flag instead",
    )

    # Add database configuration group
    defaults = {
        "databasename": "zoid6",
        "databasehost": "localhost",
        "databaseuser": None,
        "databaseport": 5432,
        "databasepassword": None,
    }
    database.buildargdatabasegroup(parser, defaults)

    return parser


class AccountGenerator:
    """Generate and store test user accounts and shared mailboxes."""

    def __init__(self, args, pool):
        self.args = args
        self.pool = pool
        self.num_accounts = args.num_accounts
        self.num_mailboxes = args.num_mailboxes
        self.skip_mailboxes = getattr(args, 'skip_mailboxes', False)
        self.create_schema = getattr(args, 'create_schema', False)
        self.no_interactive = getattr(args, 'no_interactive', False)
        self.verbose = args.verbose

    def run(self) -> bool:
        """Generate test data."""
        if self.verbose:
            echo("Initializing password system...", level="debug")

        # Initialize password system
        if not startup.startup(verbose=self.verbose):
            echo("Failed to initialize password system", level="error")
            return False

        echo("✓ Password system initialized", level="debug")
        echo("")

        # Test database connection
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with database.cursor(conn) as cur:
                    cur.execute("SELECT version()")
                    result = cur.fetchone()
                    if self.verbose:
                        echo(f"Connected to database: {result['version'][:50]}...", level="debug")
        except Exception as e:
            echo(f"Failed to connect to database: {e}", level="error")
            return False

        echo("✓ Database connection successful", level="debug")
        echo("")

        # Check if schema exists
        if not self.skip_mailboxes and not self._schema_exists():
            if self.create_schema:
                echo("=== Creating postoffice schema ===", level="info")
                if self._create_postoffice_schema():
                    echo("✓ Postoffice schema created", level="info")
                    echo("")
                else:
                    echo("Failed to create postoffice schema", level="error")
                    return False
            elif not self.no_interactive:
                # Ask user if they want to create the schema
                echo("")
                result = inputboolean(
                    "Postoffice schema not found. Create it now?",
                    default="N"
                )
                echo("")
                if result:
                    echo("=== Creating postoffice schema ===", level="info")
                    if self._create_postoffice_schema():
                        echo("✓ Postoffice schema created", level="info")
                        echo("")
                    else:
                        echo("Failed to create postoffice schema", level="error")
                        return False
                else:
                    echo("Skipping mailbox creation", level="info")
                    self.skip_mailboxes = True
                    echo("")

        # Create test accounts
        echo(f"=== Creating {self.num_accounts} test accounts ===", level="info")
        accounts = self._create_test_accounts()

        if not accounts:
            echo("Failed to create test accounts", level="error")
            return False

        echo(f"✓ Created {len(accounts)} account(s)", level="info")
        echo("")

        # Create shared mailboxes (optional)
        mailboxes = []
        if not self.skip_mailboxes:
            echo(f"=== Creating {self.num_mailboxes} shared mailboxes ===", level="info")
            mailboxes = self._create_test_mailboxes()

            if mailboxes:
                echo(f"✓ Created {len(mailboxes)} mailbox(es)", level="info")
                echo("")

        echo("=== Test Data Generation Complete ===", level="info")
        echo("")
        echo("Created accounts:", level="info")
        for account in accounts:
            echo(f"  • {account['moniker']}", level="info")

        if mailboxes:
            echo("")
            echo("Created shared mailboxes:", level="info")
            for mailbox in mailboxes:
                echo(f"  • {mailbox['name']} (ID: {mailbox['id']})", level="info")

        echo("")
        echo("Tip: Use 'python -m postoffice accounts' to manage these", level="info")
        return True

    def _schema_exists(self) -> bool:
        """Check if postoffice.shared_mailbox table exists."""
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with database.cursor(conn) as cur:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'postoffice'
                            AND table_name = 'shared_mailbox'
                        )
                    """)
                    result = cur.fetchone()
                    return result[0] if result else False
        except Exception as e:
            if self.verbose:
                echo(f"Error checking schema: {e}", level="debug")
            return False

    def _create_postoffice_schema(self) -> bool:
        """Create postoffice schema with shared_mailbox table."""
        try:
            with database.connect(self.args, pool=self.pool) as conn:
                with database.cursor(conn) as cur:
                    # Create schema if it doesn't exist
                    cur.execute("CREATE SCHEMA IF NOT EXISTS postoffice")
                    if self.verbose:
                        echo("✓ Postoffice schema exists or created", level="debug")

                    # Create shared_mailbox table if it doesn't exist
                    sql = """
                    CREATE TABLE IF NOT EXISTS postoffice.shared_mailbox (
                        id BIGSERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        created_by TEXT NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        enabled BOOLEAN DEFAULT TRUE
                    )
                    """
                    cur.execute(sql)
                    if self.verbose:
                        echo("✓ shared_mailbox table exists or created", level="debug")

                    # Create indexes
                    cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shared_mailbox_name
                        ON postoffice.shared_mailbox(name)
                    """)

                    cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shared_mailbox_created
                        ON postoffice.shared_mailbox(created_at DESC)
                    """)

                    if self.verbose:
                        echo("✓ Indexes created", level="debug")

            return True
        except Exception as e:
            echo(f"Error creating postoffice schema: {e}", level="error")
            return False

    def _create_test_accounts(self) -> list:
        """Create test user accounts."""
        accounts = []
        sql_check = "SELECT moniker FROM engine.__member WHERE moniker = %s"
        sql_insert = "INSERT INTO engine.__member (moniker, email, datecreated, dateupdated) VALUES (%s, %s, NOW(), NOW())"

        for i in range(self.num_accounts):
            moniker = f"testuser{i+1}"
            email = f"{moniker}@example.com"

            try:
                with database.connect(self.args, pool=self.pool) as conn:
                    with database.cursor(conn) as cur:
                        # Check if account already exists
                        cur.execute(sql_check, (moniker,))
                        if cur.rowcount > 0:
                            if self.verbose:
                                echo(f"Account '{moniker}' already exists, skipping", level="debug")
                            continue

                        # Create account
                        cur.execute(sql_insert, (moniker, email))

                        if self.verbose:
                            echo(f"✓ Created account: {moniker}", level="debug")
                        accounts.append({
                            "moniker": moniker,
                        })

            except Exception as e:
                echo(f"Error creating account {moniker}: {e}", level="error")

        return accounts

    def _create_test_mailboxes(self) -> list:
        """Create test shared mailboxes."""
        mailboxes = []
        sql_check = "SELECT id FROM postoffice.shared_mailbox WHERE name = %s"
        sql_insert = "INSERT INTO postoffice.shared_mailbox (name, created_by, created_at, updated_at) VALUES (%s, %s, NOW(), NOW()) RETURNING id"

        mailbox_names = [
            "support",
            "billing",
            "engineering",
        ]

        for i, base_name in enumerate(mailbox_names[:self.num_mailboxes]):
            name = f"shared/{base_name}"

            try:
                with database.connect(self.args, pool=self.pool) as conn:
                    with database.cursor(conn) as cur:
                        # Check if mailbox already exists
                        cur.execute(sql_check, (name,))
                        if cur.rowcount > 0:
                            if self.verbose:
                                echo(f"Mailbox '{name}' already exists, skipping", level="debug")
                            continue

                        # Create mailbox
                        cur.execute(sql_insert, (name, "admin"))
                        result = cur.fetchone()
                        mailbox_id = result["id"]

                        if self.verbose:
                            echo(f"✓ Created mailbox: {name} (ID: {mailbox_id})", level="debug")

                        mailboxes.append({
                            "id": mailbox_id,
                            "name": name,
                        })

            except Exception as e:
                # If the postoffice schema doesn't exist, just skip mailbox creation
                if "postoffice" in str(e) or "shared_mailbox" in str(e):
                    echo(f"Postoffice schema not available, skipping mailbox creation", level="info")
                    self.skip_mailboxes = True
                    return []
                else:
                    echo(f"Error creating mailbox {name}: {e}", level="error")

        return mailboxes

    def _generate_password(self, length: int = 16) -> str:
        """Generate a random password."""
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return "".join(random.choice(chars) for _ in range(length))


def main():
    """Main entry point."""
    parser = buildargs()
    args = parser.parse_args()

    # Initialize database pool
    try:
        pool = database.getpool(args, dbname=args.databasename)
        generator = AccountGenerator(args, pool)
        if generator.run():
            return 0
        else:
            return 1
    except Exception as e:
        echo(f"Failed to initialize database pool: {e}", level="error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
