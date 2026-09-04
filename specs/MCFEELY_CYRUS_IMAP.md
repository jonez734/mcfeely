# MCFeely Cyrus IMAPd Implementation Plan

## Overview

This document describes how to implement MCFeely using Cyrus IMAPd as the mail server, leveraging its native ANNOTATE extension for per-message metadata storage.

## Current Setup

See [POSTOFFICE_IMAP_SETUP.md](./POSTOFFICE_IMAP_SETUP.md) for the current working configuration.

## Authentication Architecture

### Overview

IMAP authentication uses the `postoffice-authd` daemon with database-backed password storage, allowing IMAP passwords to be independent of shell passwords.

```
IMAP Client → Cyrus IMAP → saslauthd → postoffice-authd → PostgreSQL (sasl_password table)
                                           ↓
                                    PAM fallback (for unmigrated users)
```

### Components

1. **postoffice-authd** - Custom SASL auth daemon
   - Listens on `/run/postoffice-authd/mux` (UNIX socket)
   - Queries `postoffice.sasl_password` for SHA-512 crypt hashes
   - Falls back to PAM if user not in database

2. **postoffice.sasl_password** table
   - Stores SHA-512 crypt hashes for SASL authentication
   - Pairs with AES-256-GCM encrypted passwords in `engine.__member`

3. **saslauthd** - Routes auth to postoffice-authd
   - Mechanism: `authdaemond`
   - Path: `/run/postoffice-authd/mux`

### Configuration Files

| File | Purpose |
|------|---------|
| `mcfeely-authd.conf` | postoffice-authd daemon config (filename unchanged) |
| `saslauthd.conf` | saslauthd mechanism config |
| `pam.d-saslauthd` | PAM fallback rules |

### Migration Path

1. **Phase 1**: postoffice-authd deployed, PAM fallback enabled
2. **Phase 2**: Users set IMAP passwords via postoffice system
3. **Phase 3**: Users authenticate via database
4. **Phase 4**: (Optional) Disable PAM fallback

## Configuration Files

### Source Location: `etc-postoffice/`

| File | Destination | Purpose |
|------|-------------|---------|
| `cyrus.conf` | `/etc/cyrus.conf` | Cyrus master process config |
| `cyrus.conf` | `/etc/postoffice/cyrus.conf` | Backup/staging copy |
| `imapd.conf` | `/etc/imapd.conf` | IMAP daemon settings |
| `imapd.conf` | `/etc/postoffice/imapd.conf` | Backup/staging copy |
| `imapd.annotations` | `/etc/postoffice/imapd.annotations` | Custom IMAP annotations |
| `saslauthd.conf` | `/etc/sasl2/saslauthd.conf` | saslauthd config |
| `saslauthd.sysconfig` | `/etc/sysconfig/saslauthd` | saslauthd startup options |
| `pam.d-saslauthd` | `/etc/pam.d/saslauthd` | PAM config for saslauthd |
| `pam.d-imap` | `/etc/pam.d/imap` | PAM config for IMAP auth |
| `cyrus-imapd.service` | `/usr/lib/systemd/system/cyrus-imapd.service` | systemd unit |
| `saslauthd.service` | `/usr/lib/systemd/system/saslauthd.service` | saslauthd systemd unit |

## Prerequisites

- Fedora server (tested on Fedora 38+)
- Postfix MTA
- Python 3.9+ for mcfeely components

## Installation

### Using Makefile (Recommended)

```bash
cd etc-postoffice
sudo make install
sudo systemctl daemon-reload
sudo systemctl enable --now saslauthd
sudo systemctl restart cyrus-imapd
```

### Install Cyrus IMAPd

```bash
dnf install cyrus-imapd cyrus-imapd-utils cyrus-imapd-perl
```

### Install Postfix

```bash
dnf install postfix
```

## Cyrus Configuration

### /etc/cyrus.conf

```conf
# Services configuration
Services {
  imap        cmd="imapd" listen="imap" prefork=0
  imaps       cmd="imapd -s" listen="imaps" prefork=0
  sieve       cmd="timsieved" listen="sieve" prefork=0
  lmtp        cmd="lmtpd" listen="lmtp" prefork=0
  notify      cmd="notifyd" listen="/var/lib/imap/notify" prefork=1
}

# Event daemon for annotations
EventDaemon {
  cmd="cvt_db" listen="/var/lib/imap/events/db" prefork=0
}
```

### /etc/imapd.conf

```conf
configdirectory: /var/lib/imap
partition-default: /var/spool/imap
admins: cyrus
allowanonymouslogin: no
sieveport: 4190
sieveservername: localhost
allowplaintext: no
sasl_mech_list: PLAIN LOGIN
annotation_providers: /etc/imapd.annotations
annotation_definitions: /etc/imapd.annotations

# TLS configuration
tls_ca_path: /etc/pki/tls/certs/ca-bundle.crt
tls_cert: /etc/pki/cyrus/imapd.pem
tls_key: /etc/pki/cyrus/imapd.pem
```

### /etc/imapd.annotations

```conf
/vendor/mcfeely/claimed-by value string shared required
/vendor/mcfeely/claimed-at value string shared required
```

### Create necessary directories

```bash
mkdir -p /var/lib/imap /var/spool/imap /run/cyrus
chown cyrus:cyrus /var/lib/imap /var/spool/imap /run/cyrus
chmod 750 /var/lib/imap /var/spool/imap
```

### Generate TLS certificates

```bash
openssl req -new -x509 -days 365 -nodes \
  -out /etc/pki/cyrus/imapd.pem \
  -keyout /etc/pki/cyrus/imapd.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
chown cyrus:cyrus /etc/pki/cyrus/imapd.pem
chmod 600 /etc/pki/cyrus/imapd.pem
```

### Start Cyrus

```bash
systemctl enable cyrus-imapd
systemctl start cyrus-imapd
```

## Postfix Configuration

See [MCFEELY_POSTFIX.md](../MCFEELY_POSTFIX.md) for detailed Postfix configuration.

### Quick Setup

### /etc/postfix/main.cf

```cf
# LMTP delivery to Cyrus
mailbox_command = /usr/lib/cyrus-imapd/deliver

# Alternative: LMTP socket method
mailbox_transport = lmtp:unix:/var/lib/imap/socket/lmtp
fallback_transport = lmtp:unix:/var/lib/imap/socket/lmtp

# Local delivery
home_mailbox = 
mail_spool_directory = /var/mail

# Network settings
inet_interfaces = all
mydestination = $myhostname, localhost, localhost.localdomain, $mydomain
mydomain = example.com
myhostname = mail.example.com
myorigin = $mydomain

# Relay settings (configure as needed)
relay_domains = 
relayhost = 

# Security
smtpd_sasl_auth_enable = no
smtpd_sasl_security_options = noanonymous
```

### /etc/postfix/master.cf (add LMTP service)

```cf
lmtp      unix  -       n       n       -       -       lmtp
```

### Reload Postfix

```bash
systemctl reload postfix
```

## Mailbox Setup

### Prerequisites

1. User must exist in system:
   ```bash
   sudo useradd -m username
   sudo passwd username
   ```

2. Services must be running:
   ```bash
   sudo systemctl enable --now saslauthd
   sudo systemctl restart cyrus-imapd
   ```

### Create mailbox with cyradm

```bash
# Connect as admin
sudo cyradm -u cyrus localhost
```

In cyradm shell:

```bash
# Create user mailbox
cm user.username

# Give user full permissions (lrs = lookup, read, see flags)
setacl user.username username lrs

# Verify ACL
lam user.username

# Exit
exit
```

### Authentication

Users authenticate to IMAP using their **system password** (same as shell/SSH).

This is because:
- `sasl_pwcheck_method: saslauthd` in imapd.conf
- `MECHANISMS = pam` in saslauthd.conf
- PAM uses `pam_unix.so` which checks `/etc/shadow`

### SSH Key Only Users

If a user accesses the server via SSH key only (no password), PAM auth will fail because there's no password in `/etc/shadow`.

**Solutions:**

1. **Set a password anyway** (recommended):
   ```bash
   sudo passwd username
   ```
   User can still use SSH keys for shell access, but now has a password for IMAP.

2. **Use sasldb for separate IMAP passwords**:
   
   Install and configure sasldb for IMAP-only passwords:
   ```bash
   # Change in imapd.conf:
   sasl_pwcheck_method: auxprop
   sasl_auxprop_plugin: sasldb
   
   # Set IMAP password (doesn't affect system password)
   sudo saslpasswd2 -c username
   
   # Set permissions
   sudo chown root:mail /etc/sasldb2
   sudo chmod 640 /etc/sasldb2
   
   # Restart Cyrus
   sudo systemctl restart cyrus-imapd
   ```
   
   This keeps SSH keys for shell and separate IMAP passwords in sasldb.

3. **Use postoffice.mailbox_password table** (for SSH key users):
   
   The `postoffice.mailbox_password` table already exists in mistermcfeely with structure:
   ```sql
   postoffice.mailbox_password (
       memberid     -- FK to engine.__member
       address      -- FK to postoffice.__address
       password     -- encrypted password
       kind         -- 'inbound', 'outbound', or 'imap'
   )
   ```
   
   For SSH key users, you could:
   - Add `'imap'` as a password kind
   - Store IMAP password encrypted in this table
   - Modify auth flow to check `mailbox_password` instead of `/etc/shadow`
   - Use existing password management code in mistermcfeely
   
   This approach keeps IMAP passwords in sync with the application's password management system.

**Recommended approach:** Set a password even for SSH key users. It doesn't affect SSH key authentication but enables IMAP access.

### Test IMAP connection

```bash
# Test with telnet
telnet localhost 143
. login username password
. list "" *
. logout
```

Or connect with any IMAP client:
- Server: `localhost`
- Port: `143` (IMAP) or `993` (IMAPS)
- User: `username`
- Password: `username's system password`

### Verify SASL authentication

```bash
# Test saslauthd directly
testsaslauthd -u username -p 'password' -s imap
```

### Common cyradm commands

```bash
# List all mailboxes
lam

# Create shared mailbox
cm user/shared/mailboxname

# Give user access to shared mailbox
setacl user.shared.mailboxname username lrs

# Remove user access
deleteacl user.shared.mailboxname username

# Delete mailbox
deleteuser user.username
```

### ACL Rights Reference

| Right | Name | Description |
|-------|------|-------------|
| `l` | lookup | See mailbox in listings, select it |
| `r` | read | Fetch messages, get metadata |
| `s` | seen | Set \Seen flag on messages |
| `w` | write | Set other flags (\Answered, \Flagged, \Draft) |
| `i` | insert | Add messages to mailbox |
| `p` | post | Send messages via LMTP to mailbox |
| `c` | create | Create sub-mailboxes |
| `d` | delete | Set \Deleted flag (soft delete) |
| `t` | expunge | EXPUNGE command (permanent delete) |
| `e` | execute | Execute METADATA commands |
| `a` | admin | Modify ACLs on mailbox |
| `k` | lookup sharedfolder | Look up sharedfolder namespace |
| `n` | administer | Administer sharedfolder |
| `x` | none | No permissions (removes ACL) |

**Special values:**
- `all` - All permissions except admin
- `none` - Remove all permissions for user

**Common combinations:**
| Rights | Use case |
|--------|----------|
| `lr` | Read-only access |
| `lrs` | Read + mark as seen |
| `lrsd` | Read + delete (typical user) |
| `lrsdwtic` | Read + write (editor) |
| `lrsdp` | Read + delete + post (mailing list) |
| `lrsdwa` | Full control (owner) |
| `all` | Everything except admin |

**Examples:**
```bash
# Read-only user
setacl user.help alice lr

# Can read and delete messages
setacl user.help bob lrsd

# Full access
setacl user.help charlie lrsdwa
```

## Sieve Configuration

See [MCFEELY_SIEVE.md](../MCFEELY_SIEVE.md) for detailed Sieve configuration and claim header insertion strategies.

## Real-time Events with notifyd

Cyrus's `notifyd` can be used for real-time event notifications when messages change in the mailbox. This is an alternative to polling the mcfeely daemon API.

### Overview

Cyrus can generate events (RFC 5423 compliant) for:
- MessageNew, MessageExpunge, MessageMove, MessageRead
- MailboxCreate, MailboxDelete, MailboxRename
- Login, Logout
- QuotaChange

These events are sent to a notification daemon - either the built-in `notifyd` or a custom external program.

### notifyd vs Sieve notify

- **notifyd** - Server-level events for ANY mailbox change (used by mcfeely daemon)
- **Sieve notify** - User-defined notifications triggered by Sieve scripts (RFC 5435)

### Configuration for External Notifier

In `/etc/imapd.conf`:

```conf
# Enable event notifications
event_notifier: external
notify_external: /usr/local/bin/mcfeely-notify

# Which events to send
event_groups: message mailbox access

# What data to include in events
event_extra_params: timestamp clientAddress flagNames messageSize uid
```

### External Program Interface

The `notify_external` program receives events via command-line arguments:

```
mcfeely-notify -c <class> -p <priority> -u <user> -m <mailbox>
```

Where:
- `-c` - Event class: MessageNew, MessageExpunge, FlagChange, Login, Logout, etc.
- `-p` - Priority: normal, urgent
- `-u` - Affected user
- `-m` - Affected mailbox

Event details are sent via **stdin** as a JSON object.

### Example mcfeely-notify Script

```python
#!/usr/bin/env python3
# mcfeely-notify - Handle Cyrus events for mcfeely

import sys
import json
import os

def main():
    # Parse command-line args
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-c':
            args['class'] = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '-p':
            args['priority'] = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '-u':
            args['user'] = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '-m':
            args['mailbox'] = sys.argv[i+1]
            i += 2
        else:
            i += 1
    
    # Read event data from stdin
    event_data = json.load(sys.stdin)
    
    # Handle specific events
    if args.get('class') == 'MessageNew':
        # New message arrived - could trigger claim check
        uid = event_data.get('uid')
        mailbox = args.get('mailbox', '')
        if 'shared/ops' in mailbox:
            # Notify mcfeely daemon to check for new messages
            os.system(f"curl -s -X POST http://localhost:8080/api/v1/refresh -d mailbox={mailbox}")
    
    elif args.get('class') == 'FlagChange':
        # Message flags changed - claim/unclaim happened
        uid = event_data.get('uid')
        # Could trigger real-time UI update
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

### Alternative: Custom RFC 5465 Compliant Notifier

Instead of using notifyd's external method, you can write a fully custom notification daemon that:
1. Listens on the notify socket
2. Implements RFC 5465 (IMAP NOTIFY protocol)
3. Handles events and integrates with mcfeely

This gives more control over event processing and format.

### Use Cases for MCFeely

1. **Real-time claim updates** - When user claims a message (via flag change), notify mcfeely daemon to update state
2. **New message alerts** - When new message arrives in shared mailbox, notify team via webhook
3. **UI refresh** - Push updates to TUI/GUI clients when mailbox state changes
4. **BBS user notifications** - Integrate with bbsengine6.notify for user-to-user notifications

### Integration with bbsengine6.notify

bbsengine6 has its own notification system (`bbsengine6.notify`) for user-to-user BBS notifications. This can be integrated with notifyd events:

#### How it works

1. Cyrus notifyd triggers external script on mail events
2. External script calls `bbsengine6.notify.send()` to alert BBS users
3. Users receive real-time notifications in their active BBS sessions

#### Use Cases

- **New mail in shared mailbox** → BBS notification to all team members
- **Claim conflict** → Alert user their claim was overwritten
- **Message assigned to you** → Direct notification to the claimed user
- **Mention in message** → Real-time BBS notification

#### Example: New Mail → BBS Notification

```python
#!/usr/bin/env python3
# mcfeely-bbs-notify - Bridge Cyrus mail events to bbsengine6 notifications

import sys
import json
import os

# Add bbsengine6 to path for import
sys.path.insert(0, '/home/opencode/data/work/bbsengine6/py/src')

from bbsengine6 import notify

def main():
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-c': args['class'] = sys.argv[i+1]
        elif sys.argv[i] == '-p': args['priority'] = sys.argv[i+1]
        elif sys.argv[i] == '-u': args['user'] = sys.argv[i+1]
        elif sys.argv[i] == '-m': args['mailbox'] = sys.argv[i+1]
        i += 1
    
    event_data = json.load(sys.stdin)
    
    # Only process shared mailboxes
    mailbox = args.get('mailbox', '')
    if not mailbox.startswith('shared/'):
        return 0
    
    # Map mailbox to notification group
    group_map = {
        'shared/ops': '@ops-team',
        'shared/support': '@support-team',
        'shared/dev': '@dev-team',
    }
    group = group_map.get(mailbox)
    if not group:
        return 0
    
    # Send bbsengine6 notification
    if args.get('class') == 'MessageNew':
        subject = event_data.get('subject', '(No Subject)')
        from_addr = event_data.get('from', 'Unknown')
        
        try:
            notify.send(
                notification_type='new_shared_mail',
                recipients=[group],
                template="New message in {mailbox}: {from_addr} - {subject}",
                template_vars={
                    'mailbox': mailbox,
                    'from_addr': from_addr,
                    'subject': subject[:80]  # Truncate for notification
                },
                urgency=notify.NotificationUrgency.IMPORTANT
            )
        except Exception as e:
            print(f"Failed to send BBS notification: {e}", file=sys.stderr)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

#### Example: Claim Alert to Individual User

```python
#!/usr/bin/env python3
# mcfeely-claim-alert - Alert user when message is claimed/unclaimed

import sys
import json

sys.path.insert(0, '/home/opencode/data/work/bbsengine6/py/src')
from bbsengine6 import notify

# Map hashids to BBS monikers (configured separately)
HASHID_TO_MONIKER = {
    'hJ7k2mNq': 'alice',
    'pQ9r3XvZ': 'bob',
    # ... etc
}

def main():
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-c': args['class'] = sys.argv[i+1]
        elif sys.argv[i] == '-p': args['priority'] = sys.argv[i+1]
        elif sys.argv[i] == '-u': args['user'] = sys.argv[i+1]
        elif sys.argv[i] == '-m': args['mailbox'] = sys.argv[i+1]
        i += 1
    
    event_data = json.load(sys.stdin)
    
    # Handle flag changes (claims/unclaims)
    if args.get('class') == 'FlagChange':
        # Extract claim info from event
        flag_names = event_data.get('flagNames', '')
        
        if 'claimed-' in flag_names:
            # Find hashid from flags
            for flag in flag_names.split():
                if flag.startswith('claimed-') and not flag.endswith('-since'):
                    hashid = flag.replace('claimed-', '')
                    moniker = HASHID_TO_MONIKER.get(hashid)
                    
                    if moniker:
                        subject = event_data.get('subject', 'Unknown')
                        notify.send(
                            notification_type='claim_assigned',
                            recipients=[moniker],
                            template="Message assigned to you: {subject}",
                            template_vars={'subject': subject[:80]},
                            urgency=notify.NotificationUrgency.ROUTINE
                        )
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

#### Configuration

In `/etc/imapd.conf`:

```conf
event_notifier: external
notify_external: /usr/local/bin/mcfeely-bbs-notify
event_groups: message
event_extra_params: timestamp uid flagNames subject from
```

**Note**: The bbsengine6 notify module requires database access and configured user sessions. Ensure the script runs with appropriate environment variables and database connectivity.

### Practical Examples

#### Example 1: Slack Notification on New Message

```python
#!/usr/bin/env python3
# mcfeely-slack-notify - Send Slack notification for new shared mailbox messages

import sys
import json
import os
import requests

SLACK_WEBHOOK = os.environ.get('SLACK_WEBHOOK_URL', '')

def send_slack(message, channel="#ops"):
    if not SLACK_WEBHOOK:
        return
    payload = {"channel": channel, "text": message, "username": "mcfeely", "icon_emoji": ":email:"}
    try:
        requests.post(SLACK_WEBHOOK, json=payload, timeout=5)
    except Exception as e:
        print(f"Slack notification failed: {e}", file=sys.stderr)

def main():
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-c': args['class'] = sys.argv[i+1]
        elif sys.argv[i] == '-p': args['priority'] = sys.argv[i+1]
        elif sys.argv[i] == '-u': args['user'] = sys.argv[i+1]
        elif sys.argv[i] == '-m': args['mailbox'] = sys.argv[i+1]
        i += 1
    
    event_data = json.load(sys.stdin)
    
    # Only notify for shared/ops mailbox
    if args.get('class') == 'MessageNew' and 'shared/ops' in args.get('mailbox', ''):
        subject = event_data.get('subject', '(No Subject)')
        from_addr = event_data.get('from', 'Unknown')
        uid = event_data.get('uid', '?')
        msg = f":incoming_envelope: New message in ops mailbox (UID {uid})\nFrom: {from_addr}\nSubject: {subject}"
        send_slack(msg, "#ops-alerts")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

#### Example 2: Database Audit Log

```python
#!/usr/bin/env python3
# mcfeely-audit - Log all mailbox events to database

import sys
import json
import sqlite3
from datetime import datetime

DB_PATH = '/var/lib/mcfeely/audit.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        event_class TEXT,
        user TEXT,
        mailbox TEXT,
        uid INTEGER,
        priority TEXT
    )''')
    return conn

def log_event(conn, event_class, user, mailbox, uid, priority):
    conn.execute('INSERT INTO events (timestamp, event_class, user, mailbox, uid, priority) VALUES (?, ?, ?, ?, ?, ?)',
                 (datetime.utcnow().isoformat(), event_class, user, mailbox, uid, priority))
    conn.commit()

def main():
    conn = init_db()
    
    args = {}
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '-c': args['class'] = sys.argv[i+1]
        elif sys.argv[i] == '-p': args['priority'] = sys.argv[i+1]
        elif sys.argv[i] == '-u': args['user'] = sys.argv[i+1]
        elif sys.argv[i] == '-m': args['mailbox'] = sys.argv[i+1]
        i += 1
    
    event_data = json.load(sys.stdin)
    uid = event_data.get('uid')
    
    log_event(conn, args.get('class'), args.get('user'), args.get('mailbox'), uid, args.get('priority'))
    conn.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

#### Example 3: Multi-method Notification with Fan-out

```python
#!/usr/bin/env python3
# mcfeely-fanout - Route events to multiple handlers

import subprocess
import json
import sys

HANDLERS = [
    '/usr/local/bin/mcfeely-slack-notify',
    '/usr/local/bin/mcfeely-audit', 
    '/usr/local/bin/mcfeely-stats',
]

def main():
    # Pass through args to each handler
    args = sys.argv[1:]
    
    # Read stdin once, pass to all handlers
    event_data = sys.stdin.read()
    
    for handler in HANDLERS:
        try:
            proc = subprocess.Popen(
                [handler] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            proc.stdin.write(event_data.encode())
            proc.stdin.close()
        except Exception as e:
            print(f"Handler {handler} failed: {e}", file=sys.stderr)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```

#### Example 4: Testing notifyd (using log method)

First test with built-in log method before writing custom scripts:

```conf
# /etc/imapd.conf - Test with log method first
event_notifier: log
event_groups: message mailbox access
```

```bash
# Watch syslog for events
journalctl -f -u cyrus-imapd | grep -i event

# Or check /var/log/maillog
tail -f /var/log/maillog | grep "notifyd"
```

You should see events like:
```
May 17 10:30:01 mail cyrus[12345]: notifyd: event: MessageNew user=alice@example.com mailbox=shared/ops uid=123 priority=normal
```

#### Example 5: Event to WebSocket for Real-time TUI

```python
#!/usr/bin/env python3
# mcfeely-websocket-push - Push events to connected WebSocket clients

import asyncio
import json
import websockets
import os
import sys

WEBSOCKET_PORT = 8765
clients = set()

async def broadcast(message):
    if clients:
        await asyncio.gather(*[c.send(message) for c in clients])

async def handler(websocket):
    clients.add(websocket)
    try:
        await websocket.recv()  # Keep connection alive
    finally:
        clients.remove(websocket)

async def main():
    # Start WebSocket server
    async with websockets.serve(handler, "localhost", WEBSOCKET_PORT):
        print(f"WebSocket server on port {WEBSOCKET_PORT}", file=sys.stderr)
        
        # Read events from stdin and broadcast
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        await loop.connect_read_pipe(lambda: reader, sys.stdin)
        
        while True:
            line = await reader.readline()
            if line:
                event = json.loads(line)
                await broadcast(json.dumps(event))

if __name__ == '__main__':
    asyncio.run(main())
```

## MCFeely Daemon Implementation

### IMAP Client for Cyrus Annotations

```python
# mcfeely/imap/cyrus_client.py
import imaplib
from typing import Optional, Tuple

class CyrusIMAPClient:
    def __init__(self, host: str = 'localhost', port: int = 993):
        self.host = host
        self.port = port
        self.conn: Optional[imaplib.IMAP4] = None

    def login(self, username: str, password: str) -> None:
        self.conn = imaplib.IMAP4_SSL(self.host, self.port)
        self.conn.login(username, password)

    def get_annotation(self, mailbox: str, uid: int, annotation: str) -> Tuple[bool, str]:
        """Get message annotation."""
        typ, data = self.conn.getannotation(f'{uid}', annotation)
        if typ == 'OK' and data[0]:
            return True, data[0].decode()
        return False, ''

    def set_annotation(self, mailbox: str, uid: int, annotation: str, value: str) -> bool:
        """Set message annotation."""
        typ, data = self.conn.setannotation(f'{uid}', annotation, value)
        return typ == 'OK'

    def delete_annotation(self, mailbox: str, uid: int, annotation: str) -> bool:
        """Delete message annotation."""
        typ, data = self.conn.setannotation(f'{uid}', annotation, None)
        return typ == 'OK'

    def get_claim(self, mailbox: str, uid: int) -> Optional[dict]:
        """Get full claim info for a message."""
        has_by, claimed_by = self.get_annotation(mailbox, uid, '/vendor/mcfeely/claimed-by')
        has_at, claimed_at = self.get_annotation(mailbox, uid, '/vendor/mcfeely/claimed-at')
        
        if has_by and claimed_by:
            return {'claimed_by': claimed_by, 'claimed_at': claimed_at}
        return None

    def set_claim(self, mailbox: str, uid: int, claimed_by: str, claimed_at: str) -> bool:
        """Set claim on a message."""
        by_ok = self.set_annotation(mailbox, uid, '/vendor/mcfeely/claimed-by', claimed_by)
        at_ok = self.set_annotation(mailbox, uid, '/vendor/mcfeely/claimed-at', claimed_at)
        return by_ok and at_ok

    def clear_claim(self, mailbox: str, uid: int) -> bool:
        """Remove claim from a message."""
        by_ok = self.delete_annotation(mailbox, uid, '/vendor/mcfeely/claimed-by')
        at_ok = self.delete_annotation(mailbox, uid, '/vendor/mcfeely/claimed-at')
        return by_ok and at_ok
```

### Daemon API Endpoints

```python
# Add to sharedmailboxd API

@app.route('/api/v1/mailbox/<name>/claim', methods=['POST'])
def claim_message(name: str):
    data = request.json
    uid = data['uid']
    claimed_by = data['claimed_by']  # hashid
    
    claimed_at = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    client = get_mailbox_client(name)
    success = client.set_claim(name, uid, claimed_by, claimed_at)
    
    if success:
        trigger_event('on_claim', {'mailbox': name, 'uid': uid, 'claimed_by': claimed_by})
        return {'success': True}
    return {'success': False, 'error': 'Failed to set annotation'}, 500

@app.route('/api/v1/mailbox/<name>/unclaim', methods=['POST'])
def unclaim_message(name: str):
    data = request.json
    uid = data['uid']
    
    client = get_mailbox_client(name)
    success = client.clear_claim(name, uid)
    
    if success:
        trigger_event('on_unclaim', {'mailbox': name, 'uid': uid})
        return {'success': True}
    return {'success': False, 'error': 'Failed to clear annotation'}, 500

@app.route('/api/v1/mailbox/<name>/messages', methods=['GET'])
def list_messages(name: str):
    client = get_mailbox_client(name)
    messages = client.list_messages(name)
    
    result = []
    for msg in messages:
        claim = client.get_claim(name, msg['uid'])
        result.append({
            'uid': msg['uid'],
            'subject': msg['subject'],
            'from': msg['from'],
            'claimed_by': claim['claimed_by'] if claim else None,
            'claimed_at': claim['claimed_at'] if claim else None
        })
    
    return {'messages': result}
```

## Testing

### Verify Cyrus is running

```bash
curl -k imaps://localhost/
# Should show IMAP capabilities including ANNOTATE
```

### Test annotation via Python

```python
import imaplib

conn = imaplib.IMAP4_SSL('localhost')
conn.login('alice@example.com', 'password')

# Create a test message first (via deliver or SMTP)
# Then test annotation

conn.setannotation('1', '/vendor/mcfeely/claimed-by', 'hJ7k2mNq')
conn.setannotation('1', '/vendor/mcfeely/claimed-at', '20260516T143200Z')

typ, data = conn.getannotation('1', '/vendor/mcfeely/claimed-by')
print(data)  # Should show hJ7k2mNq
```

### Test mcfeely claim

```bash
mcfeely --mailbox shared/ops@example.com claim 1
mcfeely --mailbox shared/ops@example.com list
mcfeely --mailbox shared/ops@example.com unclaim 1
```

## Security Considerations

1. **Saslauthd** - Configure for user authentication:
   ```bash
   dnf install cyrus-sasl cyrus-sasl-plain
   systemctl enable saslauthd
   ```

2. **Firewall** - Restrict IMAP/LMTP ports:
   ```bash
   firewall-cmd --permanent --add-service=imap
   firewall-cmd --permanent --add-service=imaps
   firewall-cmd --reload
   ```

3. **TLS** - Ensure SSL/TLS for all connections in production

## Troubleshooting

### Check Cyrus logs

```bash
journalctl -u cyrus-imapd -f
```

### Common issues

- **Annotation not working**: Verify `/etc/imapd.annotations` exists and Cyrus was restarted
- **LMTP delivery failing**: Check Postfix logs and socket permissions
- **ACLs not working**: Ensure users exist in Cyrus database (`cyradm lam`)

## Maintenance

### Backup

```bash
# Backup mailboxes
tar czf cyrus-backup-$(date +%Y%m%d).tar.gz /var/lib/imap /var/spool/imap

# Backup config
tar czf cyrus-config-backup.tar.gz /etc/cyrus.conf /etc/imapd.conf
```

### Monitoring

- Monitor `/var/log/maillog` for delivery issues
- Monitor `journalctl -u cyrus-imapd` for IMAP issues
- Check annotation operations via `imapd` logs

### Dependencies for Examples

The examples above require these Python packages:

```bash
pip install requests websockets
```

For the audit log example, SQLite is built-in.