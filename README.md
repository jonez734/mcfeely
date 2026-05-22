# Mistermcfeely: IMAP Postoffice with BBS Engine Integration

**Mr. McFeely was the postman on Mr. Rogers' Neighborhood**

A basic IMAP client for shared Cyrus mailboxes, integrated with bbsengine6's notifyd event system and member management. Enables real-time notifications when messages are claimed/unclaimed in shared mailboxes.

**⚠️ IMPORTANT:** All database functions in this project use the bbsengine6 **kwargs pattern for connection management. See [CONN_POOL_PATTERN.md](./CONN_POOL_PATTERN.md) for details.

## Overview

**Purpose:** Manage IMAP mailboxes for bbsengine6 members with shared mailbox support and event-driven notifications.

**Key Features:**
- **Cyrus IMAP integration** - Manage user and shared mailboxes via IMAP
- **BBS Engine member system** - Users are looked up from `engine.__member`
- **SYSOP flag detection** - Auto-detect sysop users via `engine.map_member_flag`
- **Message tracking** - Track message claims in PostgreSQL (`public.__message`)
- **Shared mailboxes** - Multiple users can access team mailboxes
- **NotifyD integration** - Events fire to `engine.__notify` for consumption by other systems

## Database Schema

### Tables

| Table | Schema | Purpose |
|-------|--------|---------|
| `postoffice.mailbox` | postoffice | Individual user mailboxes (user.jam) |
| `postoffice.mailbox_password` | postoffice | Mailbox authentication passwords |
| `postoffice.shared_mailbox` | postoffice | Shared team mailboxes (shared/support) |
| `public.__message` | public | Message metadata and claim tracking |

### Member Integration

Users are stored in `engine.__member` and their sysop status is checked via `engine.map_member_flag`:

```sql
-- Check if user has SYSOP flag
SELECT value FROM engine.map_member_flag 
WHERE moniker = 'jam' AND name = 'SYSOP';
-- Returns True if jam is a sysop
```

## Usage

### Command Line

```bash
# Start the interactive menu (auto-detects user from OS login)
python -m postoffice

# Specify user manually
python -m postoffice --loginid jam

# Access account management (requires SYSOP flag or --issuperuser)
python -m postoffice accounts --issuperuser

# Check IMAP connectivity
python -m postoffice imap-check --verbose
```

### User Detection

The system automatically detects the current user by:

1. First checks `--loginid` argument if provided
2. Falls back to `bbsengine6.member.getcurrentmoniker()` which:
   - Uses `util.getcurrentloginid()` to get OS login name
   - Looks up `loginid` in `engine.__member` table
   - Returns the member's `moniker`

**Example:** If your OS user is `jam` and `engine.__member` has `loginid='jam'` pointing to `moniker='jam'`, you're automatically logged in.

### SYSOP Detection

When accessing account management:

1. If `--issuperuser` is passed, skip prompt
2. Otherwise, check `engine.map_member_flag` for SYSOP flag
3. If user has SYSOP flag, prompt: "Administer postoffice? [Y/N]: "
4. If user declines, exit gracefully

## Configuration

### Environment Variables

```bash
# Required: Encryption key for password storage
export POSTOFFICE_PASSWORD_KEY="$(openssl rand -base64 32)"

# Optional: Obfuscation secret for claim flags
export MCFEELY_OBFUSCATE_SECRET="your-shared-secret-key-here"
```

### Database Configuration

Default database is `zoid6test` (testing mode). Override with:

```bash
python -m postoffice --databasename zoid6 --databasehost localhost
```

## Architecture

### Data Flow

```
User runs postoffice
    ↓
Detect user (--loginid or getcurrentmoniker)
    ↓
Check SYSOP flag in engine.map_member_flag
    ↓
If SYSOP, prompt for admin access
    ↓
CyrusAdmin TUI or MessageInterface TUI
    ↓
Manage mailboxes via IMAP
    ↓
Store metadata in PostgreSQL
```

### Modules

| Module | Purpose | Status |
|--------|---------|--------|
| `__main__.py` | CLI entry point, command routing | ✅ Complete |
| `cyrus_admin.py` | Account and shared mailbox TUI | ✅ Complete |
| `message_interface.py` | Message viewing and claiming | ✅ Complete |
| `startup.py` | Encryption key and schema init | ✅ Complete |
| `imap_checker.py` | IMAP connectivity diagnostics | ✅ Complete |

## Testing

Run the message system test:

```bash
# Verify database access
python -c "
from bbsengine6 import database
import argparse
parser = argparse.ArgumentParser()
defaults = {'databasename': 'zoid6test', 'databasehost': 'localhost', 'databaseport': 5432}
database.buildargdatabasegroup(parser, defaults)
args = parser.parse_args([])
pool = database.getpool(args)
with database.connect(args, pool=pool) as conn:
    with database.cursor(conn) as cur:
        cur.execute('SELECT COUNT(*) as cnt FROM public.__message')
        print(f'Messages: {cur.fetchone()[\"cnt\"]}')"
```

## Complete Specification

For comprehensive documentation including SQL schema, implementation notes, and API reference, see [`NOTIFYD_SYNC_SPEC.md`](./NOTIFYD_SYNC_SPEC.md).

## Implementation Status

### ✅ Completed

- CLI with menu and account management modes
- User detection from OS login via `getcurrentmoniker()`
- SYSOP flag detection from `engine.map_member_flag`
- Interactive prompt for admin access
- Account creation (engine.__member + postoffice.mailbox)
- Shared mailbox management
- Message claim tracking in `public.__message`
- Screen initialization with termios error handling
- Terminal cleanup on exit (INTR/EOF)

### 🔮 Future Enhancements (Optional)

- IDLE-based IMAP monitoring
- Full integration testing with real Cyrus server
- Production metrics and observability

## References

- [Cyrus IMAP Documentation](https://www.cyrusimap.org/)
- [Python IMAP Documentation](https://docs.python.org/3/library/imaplib.html)
- [bbsengine6 Documentation](https://github.com/anomalyco/bbsengine6)