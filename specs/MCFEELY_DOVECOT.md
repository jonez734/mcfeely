# MCFeely Dovecot Implementation Plan

## Overview

This document describes how to implement MCFeely using Dovecot as the mail server, using IMAP keywords (flags) for claim storage.

## Prerequisites

- Fedora server (tested on Fedora 38+)
- Postfix MTA
- Python 3.9+ for mcfeely components

## Installation

### Install Dovecot

```bash
dnf install dovecot dovecot-imapd dovecot-pigeonhole
```

### Install Postfix

```bash
dnf install postfix
```

## Dovecot Configuration

### /etc/dovecot/dovecot.conf

```conf
protocols = imap lmtp sieve
listen = *
base_dir = /var/run/dovecot
login_dir = /var/run/dovecot/login
login_executable = /usr/libexec/dovecot/imap-login
mail_location = maildir:~/Maildir
mail_access_groups = mail
mail_privileged_group = mail

# IMAP settings
imap_max_line_length = 65536
imap_idle_notify_interval = 29

# LMTP settings
lmtp_save_to_detail_mailbox = yes

# LDA settings
mailbox_command = /usr/libexec/dovecot/dovecot-lda -f "$SENDER" -a "$RECIPIENT"

# Authentication
auth_mechanisms = PLAIN LOGIN
disable_plaintext_auth = no

# User database
userdb {
  driver = passwd
}

# Socket for Postfix delivery
service lmtp {
  unix_listener /var/lib/imap/socket/lmtp {
    mode = 0660
    user = postfix
    group = postfix
  }
}

# Sieve support
plugin {
  sieve = ~/.dovecot.sieve
  sieve_dir = ~/sieve
}
```

### /etc/dovecot/conf.d/10-mail.conf

```conf
mail_location = maildir:~/Maildir:LAYOUT=fs
namespace inbox {
  inbox = yes
  hidden = no
}
```

### /etc/dovecot/conf.d/10-auth.conf

```conf
auth_mechanisms = PLAIN LOGIN
!include auth-passwdfile.conf.ext
!include auth-system.conf.ext
```

### /etc/dovecot/conf.d/15-lda.conf

```conf
postmaster_address = postmaster@example.com
hostname = mail.example.com
```

### Enable and start Dovecot

```bash
systemctl enable dovecot
systemctl start dovecot
```

## Postfix Configuration

See [MCFEELY_POSTFIX.md](../MCFEELY_POSTFIX.md) for detailed Postfix configuration.

### Quick Setup

```cf
# Virtual mailbox delivery to Dovecot LDA
mailbox_command = /usr/libexec/dovecot/dovecot-lda -f "$SENDER"

# Alternative: LMTP over socket
mailbox_transport = lmtp:unix:/var/lib/imap/socket/lmtp

# Virtual mailbox configuration
virtual_mailbox_domains = example.com
virtual_mailbox_base = /var/mail/vhosts
virtual_mailbox_maps = hash:/etc/postfix/vmailbox
virtual_uid_maps = static:5000
virtual_gid_maps = static:5000

# Alternative: Local delivery with system users
home_mailbox = Maildir/
mail_spool_directory = /var/mail

# Network settings
inet_interfaces = all
mydestination = $myhostname, localhost, localhost.localdomain, $mydomain
mydomain = example.com
myhostname = mail.example.com
myorigin = $mydomain
```

### /etc/postfix/vmailbox (if using virtual)

```
alice@example.com    example.com/alice
bob@example.com      example.com/bob
shared/ops@example.com    example.com/shared/ops
```

```bash
postmap /etc/postfix/vmailbox
```

### Create vmail user/group

```bash
groupadd -g 5000 vmail
useradd -g vmail -u 5000 -s /sbin/nologin vmail
mkdir -p /var/mail/vhosts/example.com
chown vmail:vmail /var/mail/vhosts
```

### Reload Postfix

```bash
systemctl reload postfix
```

## Mailbox Setup

### Create user mailboxes

```bash
# For system users, mailboxes created automatically on first delivery
# For virtual users, use postmap -q to test

# Create shared mailbox directory manually
mkdir -p /var/mail/vhosts/example.com/shared/ops
chown vmail:vmail /var/mail/vhosts/example.com/shared/ops
```

### Set up shared mailbox ACLs

Dovecot uses ACLs stored in `dovecot-acl` files in the mailbox directory:

```bash
# For shared/ops mailbox
touch /var/mail/vhosts/example.com/shared/ops/dovecot-acl

# ACL format:
# user=alice@l r
# user=bob@l r
# user=cyrus a
```

Or via IMAP (using manage command):

```bash
# Connect to Dovecot IMAP and set ACL
openssl s_client -connect localhost:993
tag LOGIN alice@example.com password
tag ACL shared/ops@example.com alice@l rs
```

### Configure ACL plugin

In `/etc/dovecot/conf.d/90-acl.conf`:

```conf
protocol imap {
  mail_plugins = acl
}

plugin {
  acl = vfile:/etc/dovecot/acls:cache_secs=300
}
```

Create `/etc/dovecot/acls/` directory for ACL files.

## Sieve Configuration

See [MCFEELY_SIEVE.md](../MCFEELY_SIEVE.md) for detailed Sieve configuration and claim header insertion strategies.

## MCFeely Daemon Implementation

### IMAP Client for Dovecot Keywords

```python
# mcfeely/imap/dovecot_client.py
import imaplib
from typing import Optional, Tuple, List

class DovecotIMAPClient:
    def __init__(self, host: str = 'localhost', port: int = 993):
        self.host = host
        self.port = port
        self.conn: Optional[imaplib.IMAP4] = None
        self._claimed_keywords = {}  # cache for keyword prefixes

    def login(self, username: str, password: str) -> None:
        self.conn = imaplib.IMAP4_SSL(self.host, self.port)
        self.conn.login(username, password)

    def _keyword_prefix(self, claimed_by: str) -> str:
        """Generate keyword prefix for a claim."""
        return f"claimed-{claimed_by}"

    def get_claim(self, mailbox: str, uid: int) -> Optional[dict]:
        """Get claim info for a message using keywords."""
        typ, data = self.conn.uid('FETCH', uid, '(FLAGS UID)')
        if typ != 'OK' or not data:
            return None
        
        flags = data[0][1].get(b'FLAGS', ())
        flag_strs = [f.decode() if isinstance(f, bytes) else str(f) for f in flags]
        
        # Look for claimed-* keywords
        for flag in flag_strs:
            if flag.startswith('claimed-') and not flag.endswith('-since'):
                claimed_by = flag.replace('claimed-', '')
                # Try to get timestamp
                since_flag = f'claimed-{claimed_by}-since'
                claimed_at = None
                if since_flag in flag_strs:
                    # Extract timestamp from flag value
                    idx = flag_strs.index(since_flag)
                    # Note: timestamps stored differently, might need metadata
                    claimed_at = "current"  # simplified
                return {'claimed_by': claimed_by, 'claimed_at': claimed_at}
        
        return None

    def set_claim(self, mailbox: str, uid: int, claimed_by: str, claimed_at: str) -> bool:
        """Set claim on a message using keywords."""
        prefix = self._keyword_prefix(claimed_by)
        
        # Set both keywords
        keywords = [f'+X-GM-LABELS', f'+{prefix}', f'+{prefix}-since={claimed_at}']
        
        # Use STORE with +FLAGS.SILENT to add keywords
        try:
            # Add claim keyword
            typ, _ = self.conn.uid('STORE', uid, '+FLAGS', f'(\\HasNoKeywords {prefix}'))
            if typ != 'OK':
                return False
            
            # Add timestamp keyword (as custom flag)
            # Note: Dovecot custom flags are limited, use keyword naming convention
            return True
        except Exception as e:
            print(f"Error setting claim: {e}")
            return False

    def clear_claim(self, mailbox: str, uid: int) -> bool:
        """Remove claim from a message."""
        # Get current claim to know which keywords to remove
        claim = self.get_claim(mailbox, uid)
        if not claim:
            return True  # Nothing to clear
        
        prefix = self._keyword_prefix(claim['claimed_by'])
        
        # Remove keywords
        try:
            self.conn.uid('STORE', uid, '-FLAGS', f'({prefix} {prefix}-since=*)')
            return True
        except:
            return False

    def list_messages(self, mailbox: str) -> List[dict]:
        """List all messages in mailbox with claim status."""
        typ, data = self.conn.select(mailbox)
        if typ != 'OK':
            return []
        
        # Get all UIDs
        typ, uid_data = self.conn.uid('SEARCH', None, 'ALL')
        if typ != 'OK':
            return []
        
        uids = uid_data[0].split()
        messages = []
        
        for uid in uids:
            # Fetch message info
            typ, msg_data = self.conn.uid('FETCH', uid, '(UID ENVELOPE FLAGS)')
            if typ == 'OK' and msg_data:
                envelope = msg_data[0][1].get(b'ENVELOPE')
                flags = msg_data[0][1].get(b'FLAGS', ())
                
                subject = envelope[1].decode() if envelope and envelope[1] else '(No Subject)'
                from_addr = envelope[2][0].decode() if envelope and envelope[2] else ''
                
                claim = self.get_claim(mailbox, int(uid))
                
                messages.append({
                    'uid': int(uid),
                    'subject': subject,
                    'from': from_addr,
                    'claimed_by': claim['claimed_by'] if claim else None,
                    'claimed_at': claim.get('claimed_at') if claim else None
                })
        
        return messages
```

### Alternative: Use METADATA extension

For more robust timestamp storage, use Dovecot's METADATA extension:

```python
class DovecotMetadataClient(DovecotIMAPClient):
    """Use IMAP METADATA instead of keywords for claim storage."""
    
    def set_claim(self, mailbox: str, uid: int, claimed_by: str, claimed_at: str) -> bool:
        """Set claim via METADATA."""
        try:
            # Set metadata entries
            self.conn.setmetadata(uid, '/private/mcfeely/claimed-by', claimed_by)
            self.conn.setmetadata(uid, '/private/mcfeely/claimed-at', claimed_at)
            return True
        except:
            return False
    
    def get_claim(self, mailbox: str, uid: int) -> Optional[dict]:
        """Get claim via METADATA."""
        try:
            typ, data = self.conn.getmetadata(uid, '/private/mcfeely')
            if typ == 'OK' and data:
                result = {}
                for entry in data:
                    if '/private/mcfeely/claimed-by' in entry:
                        result['claimed_by'] = entry['/private/mcfeely/claimed-by']
                    if '/private/mcfeely/claimed-at' in entry:
                        result['claimed_at'] = entry['/private/mcfeely/claimed-at']
                return result if result else None
        except:
            pass
        return None
```

Enable METADATA in Dovecot:

```conf
# /etc/dovecot/conf.d/90-metadata.conf
plugin {
  metadata = yes
}
```

### Daemon API Endpoints

Same as Cyrus implementation but using Dovecot client:

```python
# sharedmailboxd with Dovecot client
from imap.dovecot_client import DovecotIMAPClient

@app.route('/api/v1/mailbox/<name>/claim', methods=['POST'])
def claim_message(name: str):
    data = request.json
    uid = data['uid']
    claimed_by = data['claimed_by']
    claimed_at = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    
    client = get_mailbox_client(name)
    success = client.set_claim(name, uid, claimed_by, claimed_at)
    
    if success:
        trigger_event('on_claim', {'mailbox': name, 'uid': uid, 'claimed_by': claimed_by})
        return {'success': True}
    return {'success': False}, 500
```

## Testing

### Verify Dovecot is running

```bash
openssl s_client -connect localhost:993
# Should show Dovecot IMAP capabilities
```

### Test keyword operations

```python
import imaplib

conn = imaplib.IMAP4_SSL('localhost')
conn.login('alice@example.com', 'password')
conn.select('INBOX')

# Add custom keyword
conn.uid('STORE', '1', '+FLAGS', ('\\HasNoKeywords claimed-hJ7k2mNq'))

# Check flags
typ, data = conn.uid('FETCH', '1', '(FLAGS)')
print(data)
```

### Test mcfeely

```bash
mcfeely --mailbox INBOX claim 1
mcfeely --mailbox INBOX list
mcfeely --mailbox INBOX unclaim 1
```

### View keywords in email client

- **Thunderbird**: Tags → User Tags (shows custom keywords) - see detailed config below
- **Kontact/KMail**: Labels
- **Alpine**: Custom flags

#### Thunderbird Detailed Setup

1. **Creating a Tag for Your Hashid**

Each user needs to create a tag that maps to their hashid keyword:

```bash
# Get your hashid (from mcfeely config or daemon)
mcfeely status
# Output: Your hashid: hJ7k2mNq
```

In Thunderbird:
- Settings → Tags → Add
- Create tags for each user's hashid you want to track
- Tag name: "hJ7k2mNq" (or a descriptive name like "Alice's Claims")
- The tag automatically maps to the IMAP keyword `claimed-hJ7k2mNq`

2. **Viewing Claim Status in Message List**

- Ensure "Tags" column is visible: View → Columns → Tags
- Each claimed message shows a colored tag dot
- Hover over tag to see which keyword/claim

3. **Refreshing Tag Display**

- Ctrl+Shift+R to refresh folder
- Or: right-click folder → "Mark All Messages as Read" then refresh

4. **Known Limitations**

- Thunderbird shows the keyword flag but not the claim timestamp
- You see YOUR claim as your specific tag color
- Other users' claims show as their keyword flag (e.g., `claimed-pQ9r3XvZ`)
- To see "who" claimed a message with full details, use mcfeely CLI/TUI
- Some older versions of Thunderbird may not support all keyword characters

#### Alternative: View Headers Directly

For advanced users who want to see claims in the message itself:

```bash
# In Thunderbird, View → Message Body → Original
# Or use "Show Headers" add-on
```

The message headers will contain:
```
X-MCFeely-Claimed-By: hJ7k2mNq
X-MCFeely-Claimed-At: 20260517T143200Z
```

(These headers can be added via Sieve or client-side plugins - see [MCFEELY_SIEVE.md](../MCFEELY_SIEVE.md))

## Security Considerations

### Enable SSL/TLS

```conf
# /etc/dovecot/conf.d/10-ssl.conf
ssl = required
ssl_cert = </etc/pki/dovecot/certs/dovecot.pem
ssl_key = </etc/pki/dovecot/private/dovecot.pem
```

### Firewall rules

```bash
firewall-cmd --permanent --add-service=imap
firewall-cmd --permanent --add-service=imaps
firewall-cmd --reload
```

### Disable plaintext auth

```conf
# /etc/dovecot/conf.d/10-auth.conf
disable_plaintext_auth = yes
```

## Troubleshooting

### Check Dovecot logs

```bash
journalctl -u dovecot -f
tail -f /var/log/dovecot/info.log
```

### Common issues

- **Keywords not visible**: Check email client supports custom IMAP keywords
- **Shared mailbox ACLs not working**: Verify ACL plugin enabled and files exist
- **LMTP delivery failing**: Check socket permissions and Postfix config

### Debug IMAP

```bash
doveadm -f auth debug username=alice@example.com
```

## Maintenance

### Backup

```bash
# Backup mailboxes
tar czf dovecot-mail-backup-$(date +%Y%m%d).tar.gz /var/mail

# Backup config
tar czf dovecot-config-backup.tar.gz /etc/dovecot/
```

### Monitoring

- `doveadm stats` - Show connection statistics
- `doveadm who` - Show logged in users
- Monitor `/var/log/maillog` for delivery issues

## Comparison: Keywords vs METADATA

| Feature | Keywords | METADATA |
|---------|----------|-----------|
| Standard support | All clients | Limited |
| Timestamp storage | Via flag naming | Dedicated entries |
| Query support | Limited | Better |
| Complexity | Simple | Moderate |
| Compatibility | Excellent | Partial |

Recommendation: Use keywords for claim status, METADATA for timestamps if client supports it.