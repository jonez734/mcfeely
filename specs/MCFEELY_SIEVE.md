# MCFeely Sieve Configuration Specification

This document is referenced by:
- [MCFEELY_DESIGN.md](../MCFEELY_DESIGN.md)
- [MCFEELY_CYRUS_IMAP.md](../MCFEELY_CYRUS_IMAP.md)
- [MCFEELY_DOVECOT.md](../MCFEELY_DOVECOT.md)

## Overview

This document specifies Sieve scripts for handling claim headers on outgoing mail (replies/forwards) for the MCFeely system.

## What is Sieve?

Sieve (RFC 5228) is a mail filtering language that runs on the mail server. It's used for:
- Filtering incoming mail
- Auto-filing into folders
- Setting up vacation responses
- **Adding headers to outgoing mail**

## Architecture

### Claim Headers Flow

```
User replies/forwards claimed message
         │
         ▼
┌─────────────────┐
│   Sieve Script  │ ← Checks original message metadata
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Add X-Claimed-* │
│    Headers       │
└────────┬────────┘
         │
         ▼
   Outgoing Mail
```

## Sieve Implementation Approaches

### Challenge: Sieve and Outgoing Mail

Sieve traditionally handles **incoming** mail. For outgoing mail (replies/forwards), there are a few approaches:

1. **Client-side insertion** - Email client adds headers during compose
2. **MDA (Mail Delivery Agent)** - LDA processes all mail
3. **Sieve on copy** - When message is copied (MUA forward), sieve processes it

### Recommended: Header Check on Copy

When a user forwards a message, the MUA typically creates a new message containing the original. Sieve can intercept this copy and add headers.

## Cyrus Sieve Configuration

### Installing Cyrus Sieve

```bash
dnf install cyrus-imapd cyrus-imapd-utils
```

### Configuring timsieved

In `/etc/cyrus.conf`:

```conf
Services {
  sieve       cmd="timsieved" listen="sieve" prefork=0
}
```

### Sieve Script Location

- User scripts: `/var/lib/imap/sieve/u/user/@domain/default.sieve`
- Global include: `/var/lib/imap/sieve/global/default.include.sieve`

### Example: Claim Header Insertion Script

File: `/var/lib/imap/sieve/include/claim-headers.sieve`

```sieve
require ["fileinto", "variables", "regex", "imap4flags", "copy"];

# This script should be included in user's main script
# It adds claim headers when forwarding/replying to claimed messages

# Note: This works when the message is COPIED (forward)
# Original message keywords/annotations checked via imap4flags

# For replies, the MUA typically creates new message from scratch
# In that case, headers must be added by the client or MTA
```

### User Active Script

File: `/var/lib/imap/sieve/u/a/alice@example.com/default.sieve`

```sieve
require ["fileinto", "variables", "envelope", "mime", "body"];

# Include global functions
include "/var/lib/imap/sieve/include/claim-headers.sieve";

# Default: deliver to INBOX
if true {
  fileinto "INBOX";
}
```

### Managing Scripts via cyradm

```bash
cyradm -u cyrus localhost
> listscripts user/alice@example.com
> setactive user/alice@example.com default
```

## Dovecot Sieve Configuration

### Installing Dovecot Pigeonhole

```bash
dnf install dovecot-pigeonhole
```

### Enabling Sieve in Dovecot

In `/etc/dovecot/conf.d/90-sieve.conf`:

```conf
plugin {
  sieve = file:~/sieve;active=~/.dovecot.sieve
  sieve_dir = ~/sieve
  sieve_default = /etc/dovecot/sieve/default.sieve
  sieve_global_dir = /etc/dovecot/sieve/
  sieve_global_path = /etc/dovecot/sieve/default.sieve
}
```

### Creating sieve directories

```bash
mkdir -p /etc/dovecot/sieve
mkdir -p /var/vmail/example.com/alice/sieve
chown -R vmail:vmail /var/vmail/example.com
```

### Example: Claim Header Script

File: `/etc/dovecot/sieve/mcfeely-headers.sieve`

```sieve
require ["fileinto", "variables", "regex", "imap4flags", "envelope", "date"];

# Check if message being forwarded/replied has claim metadata
# Note: This works when message is a forward (copy)

# The envelope "to" tells us the target folder or recipient
# For forwarded messages, we can check headers

# IMPORTANT: This script runs on INCOMING mail
# For outgoing, we need a different approach

# When message is received (reply to claimed message)
if envelope :matches "In-Reply-To" "*<*@*>" {
  # Extract Message-ID and check against claims database
  # This would require external lookup
}

# Alternative: Check if this is a redirect (Dovecot redirect extension)
if redirect {
  # Add headers to redirected message
}
```

### Per-User Sieve Script

File: `~/sieve/default.sieve` (in user's home)

```sieve
require ["fileinto", "variables"];

# Include claim header insertion
include "sieve:/etc/dovecot/sieve/mcfeely-headers.sieve";

# Deliver to inbox
fileinto "INBOX";
```

## Header Insertion Approaches for MCFeely

### Approach 1: Sieve on Copy (Forward)

Works when MUA creates a copy of the message:

```sieve
# For Cyrus - check annotations on forwarded message
if header :matches "X-Special-Forward" "*" {
  # Extract original message UID
  # Look up claim via CMU's sieveshell or external script
  
  # Add headers to this (outgoing) message
  addheader "X-Claimed-By" "${claimed_by}";
  addheader "X-Claimed-At" "${claimed_at}";
}
```

### Approach 2: Client-Side Headers (Recommended)

Configure email client to add headers based on original message:

1. User opens claimed message
2. Client shows claim info in UI
3. When replying/forwarding, client auto-adds headers:
   - `X-Claimed-By: <hashid>`
   - `X-Claimed-At: <timestamp>`

### Approach 3: MDA Wrapper Script

Create wrapper around LDA that adds headers:

```bash
#!/bin/bash
# /usr/local/bin/mcfeely-lda
# Wraps deliver/dovecot-lda to add claim headers

# Read incoming message from stdin
MSG=$(cat)

# Extract Message-ID
MSGID=$(echo "$MSG" | grep -i "^Message-ID:" | head -1)

# Check claims database
CLAIM=$(sqlite3 /var/lib/mcfeely/claims.db "SELECT * FROM claims WHERE message_id='$MSGID'")

if [ -n "$CLAIM" ]; then
  # Add headers
  CLAIM_BY=$(echo $CLAIM | cut -d'|' -f2)
  CLAIM_AT=$(echo $CLAIM | cut -d'|' -f3)
  MSG=$(echo "$MSG" | sed "1i X-Claimed-By: $CLAIM_BY\nX-Claimed-At: $CLAIM_AT")
fi

# Pass to actual LDA
echo "$MSG" | /usr/libexec/dovecot/dovecot-lda -f "$SENDER" -a "$RECIPIENT"
```

### Approach 4: Postfix Header Check (MTA-Level)

Add header check in Postfix:

In `/etc/postfix/main.cf`:

```cf
header_checks = regexp:/etc/postfix/header_checks
```

In `/etc/postfix/header_checks`:

```
/^X-MCFeely-Claim-By:.*/ PREPEND X-Claimed-By: $1
/^X-MCFeely-Claim-At:.*/ PREPEND X-Claimed-At: $1
```

Client adds `X-MCFeely-*` headers, MTA rewrites to final headers.

## Recommended: Client-Side + Server Verification

### Client Adds Headers (on reply/forward)

When user replies/forwards a claimed message, the client automatically adds:

```
X-Claimed-By: hJ7k2mNq
X-Claimed-At: 20260516T143200Z
```

### Server Verification (optional)

Sieve can verify the claim is valid:

```sieve
require ["fileinto", "external"];

# Verify claim via external script
if external :comparator "i;ascii-numeric" :regex "X-Claimed-By" "." {
  # This is a claimed message being forwarded
  # Add verification header
  addheader "X-Claimed-Verified" "yes";
}
```

## Sieve Extensions Used

| Extension | Purpose |
|-----------|---------|
| `fileinto` | Deliver to folder |
| `variables` | String manipulation |
| `regex` | Pattern matching |
| `imap4flags` | Check message flags (Cyrus) |
| `copy` | Keep original while filtering |
| `date` | Date operations |
| `envelope` | Envelope inspection |
| `mime` | MIME part inspection |
| `body` | Body content search |

## Testing Sieve Scripts

### Cyrus: Compile script

```bash
sieveshell -u alice@example.com localhost
> put /path/to/script.sieve
> activate script.sieve
```

### Dovecot: Check syntax

```bash
sievec /etc/dovecot/sieve/test.sieve
```

### Debug: View script execution

```bash
tail -f /var/log/maillog | grep sieve
```

## Example Scripts

### Global Default Script (Cyrus)

```sieve
require ["fileinto", "variables"];

# Log all incoming mail for debugging
if true {
  # No action, deliver normally
}

# Add list-id for mailing lists
if header :matches "List-Id" "*<*>" {
  fileinto "Lists";
}
```

### User Vacation Script with Claim Support

```sieve
require ["vacation"];

# Auto-reply but preserve claim headers
if header :contains "X-Claimed-By" "" {
  # Preserve claim headers in vacation response
  # (client handles this)
}

vacation
  :subject "I'm out of office"
  :days 7
  "I'm currently out of office. I'll respond when I'm back.";
```

## Troubleshooting

### Script not running

1. Check sieve is enabled in config
2. Verify script location is correct
3. Check syntax with `sievec`
4. Check logs for errors

### Headers not added

- Sieve only runs on **incoming** mail
- For outgoing, use client-side or wrapper
- Check `addheader` syntax (must be first line of actions)

### Permissions

```bash
# Cyrus
chown cyrus:cyrus /var/lib/imap/sieve/...

# Dovecot
chown vmail:vmail /var/vmail/.../sieve/
```

## References

- [Sieve RFC 5228](https://tools.ietf.org/html/rfc5228)
- [RFC 5435 - Sieve Email Filtering: Extension for Notifications](https://tools.ietf.org/html/rfc5435) - enotify extension
- [RFC 5423 - Message Store Events](https://tools.ietf.org/html/rfc5423) - Event format standard
- [RFC 5465 - IMAP NOTIFY Extension](https://tools.ietf.org/html/rfc5465) - Server push notifications
- [Cyrus Sieve](https://www.cyrusimap.org/imap/admin/sieve.html)
- [Dovecot Pigeonhole](https://doc.dovecot.org/admin_manual/pigeonhole_sieve/)