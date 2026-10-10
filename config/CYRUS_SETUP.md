# Cyrus IMAPd Configuration for Mistermcfeely

> **Note [2026-10-09]:** This is the surviving config/ doc after
> the 3-file event-handler consolidation. The following
> sibling docs were deleted on 2026-10-09 as duplicative:
> - `config/EVENT_HANDLER_INTEGRATION.md` (431 lines): a pure
>   event-bridge description (Steps 1-8, ASCII diagram); content
>   is preserved as the "Event Notification for Monitoring"
>   section below.
> - `config/INSTALLATION_SUMMARY.txt` (570 lines): a prose
>   summary of the deploy; the "MISTERMCFEELY NOTIFYD_CLIENT
>   INTEGRATION" section (lines 467-487) was the only
>   event-bridge-specific content and is also covered below.
> - `config/QUICK_DEPLOY.txt` (324 lines): a step-by-step
>   deploy checklist; the notifyd-based deploy step is the
>   only event-bridge-specific content and is also covered
>   below.
>
> The "Event Notification for Monitoring" section below
> describes the `mcfeely-notify` external-event-bridge
> architecture. The production mcfeely deployment does
> **not** use this architecture; the live system polls
> via the in-process `mailbox_poller` in
> `src/postoffice/services/mailbox_poller.py`, and the
> `notify` service is commented out in
> `etc-postoffice/cyrus.conf:35`. The
> `event_notifier: external` line in
> `etc-postoffice/imapd.conf:224` is also not used by the
> live mailbox_poller. The section is preserved as a
> reference for the alternative architecture and for
> operators who want to switch.

This directory contains complete Cyrus IMAPd configuration files for the mistermcfeely IMAP postoffice project.

## Files Included

- **cyrus.conf** - Master service configuration (Daemons, Services, Logging)
- **imapd.conf** - Core IMAP daemon settings and feature configuration
- **imapd.annotations** - Custom annotation definitions for message metadata
- **CYRUS_SETUP.md** - This installation guide

## Quick Start Installation

### 1. Install Cyrus IMAPd

On Fedora/RHEL:
```bash
sudo dnf install cyrus-imapd cyrus-imapd-utils cyrus-imapd-perl
```

On Debian/Ubuntu:
```bash
sudo apt-get install cyrus-imapd cyrus-imapd-2.5
```

Also install SASL and Sieve support:
```bash
# Fedora/RHEL
sudo dnf install cyrus-sasl cyrus-sasl-plain cyrus-imapd-sieve

# Debian/Ubuntu
sudo apt-get install libsasl2-2 sasl2-bin sieve-extensions
```

### 2. Backup Existing Configuration (if any)

```bash
sudo cp /etc/postoffice/cyrus.conf /etc/postoffice/cyrus.conf.backup
sudo cp /etc/postoffice/imapd.conf /etc/postoffice/imapd.conf.backup
if [ -f /etc/postoffice/imapd.annotations ]; then
  sudo cp /etc/postoffice/imapd.annotations /etc/postoffice/imapd.annotations.backup
fi
```

### 3. Install Configuration Files

Copy the configuration files to the system:

```bash
# From mistermcfeely/config directory:
sudo cp cyrus.conf /etc/postoffice/cyrus.conf
sudo cp imapd.conf /etc/postoffice/imapd.conf
sudo cp imapd.annotations /etc/postoffice/imapd.annotations

# Set proper permissions
sudo chown root:root /etc/postoffice/cyrus.conf /etc/postoffice/imapd.conf /etc/postoffice/imapd.annotations
sudo chmod 644 /etc/postoffice/cyrus.conf /etc/postoffice/imapd.conf /etc/postoffice/imapd.annotations
```

### 4. Create Required Directories

```bash
# Create Cyrus directories
sudo mkdir -p /var/lib/imap
sudo mkdir -p /var/spool/imap
sudo mkdir -p /var/lib/imap/notify
sudo mkdir -p /var/lib/imap/sieve
sudo mkdir -p /var/lib/imap/global_scripts

# Set ownership and permissions
sudo chown -R cyrus:cyrus /var/lib/imap /var/spool/imap
sudo chmod -R 750 /var/lib/imap /var/spool/imap
sudo chmod -R 770 /var/lib/imap/notify

# Create directory for TLS certificates
sudo mkdir -p /etc/pki/cyrus
sudo chown cyrus:cyrus /etc/pki/cyrus
sudo chmod 700 /etc/pki/cyrus
```

### 5. Generate TLS Certificates

For testing and development:

```bash
# Create self-signed certificate valid for 1 year
sudo openssl req -new -x509 -days 365 -nodes \
  -out /etc/pki/cyrus/imapd.pem \
  -keyout /etc/pki/cyrus/imapd.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Set permissions
sudo chown cyrus:cyrus /etc/pki/cyrus/imapd.pem
sudo chmod 600 /etc/pki/cyrus/imapd.pem
```

For production with Let's Encrypt:

```bash
# Install certbot and cyrus plugin
sudo dnf install certbot python3-certbot-nginx

# Get certificate for your domain
sudo certbot certonly --standalone -d mail.example.com

# Create combined PEM file for Cyrus
sudo bash -c 'cat /etc/letsencrypt/live/mail.example.com/privkey.pem \
  /etc/letsencrypt/live/mail.example.com/fullchain.pem \
  > /etc/pki/cyrus/imapd.pem'

# Set permissions
sudo chown cyrus:cyrus /etc/pki/cyrus/imapd.pem
sudo chmod 600 /etc/pki/cyrus/imapd.pem

# Add certbot renewal hook to update Cyrus cert
echo '#!/bin/bash
cat /etc/letsencrypt/live/mail.example.com/privkey.pem \
  /etc/letsencrypt/live/mail.example.com/fullchain.pem \
  > /etc/pki/cyrus/imapd.pem
chown cyrus:cyrus /etc/pki/cyrus/imapd.pem
systemctl restart cyrus-imapd' | sudo tee /etc/letsencrypt/renewal-hooks/post/cyrus.sh
sudo chmod 755 /etc/letsencrypt/renewal-hooks/post/cyrus.sh
```

### 6. Configure SASL Authentication

Create saslauthd configuration:

```bash
# Create saslauthd directory
sudo mkdir -p /run/saslauthd
sudo chown cyrus:cyrus /run/saslauthd
sudo chmod 710 /run/saslauthd

# Or use Makefile:
make install-auth
```

The `make install-auth` command installs all saslauthd configuration files:
- `/etc/sasl2/saslauthd.conf` - Main daemon configuration
- `/etc/sysconfig/saslauthd` (or `/etc/default/saslauthd` on Debian) - Runtime flags
- `/etc/pam.d/saslauthd` - PAM authentication rules

Manual installation:
```bash
# Main saslauthd config
sudo cp etc-postoffice/saslauthd.conf /etc/sasl2/saslauthd.conf

# Sysconfig (RHEL) or defaults (Debian)
[ -f /etc/debian_version ] && \
    sudo cp etc-postoffice/saslauthd.sysconfig /etc/default/saslauthd || \
    sudo cp etc-postoffice/saslauthd.sysconfig /etc/sysconfig/saslauthd

# PAM rules
sudo cp etc-postoffice/pam.d-saslauthd /etc/pam.d/saslauthd

# Enable and start saslauthd
sudo systemctl enable saslauthd
sudo systemctl start saslauthd
```

### 7. Initialize Cyrus Databases

First initialization - creates all necessary databases:

```bash
# Initialize as root
sudo /usr/lib/cyrus-imapd/tools/mkimap
```

This creates:
- `/var/lib/imap/tls_sessions.db` - TLS session cache
- `/var/lib/imap/deliver.db` - Delivery state
- `/var/lib/imap/mboxlist.db` - Mailbox list
- `/var/lib/imap/seen.db` - Seen state for users
- `/var/lib/imap/subscription.db` - User subscriptions
- `/var/lib/imap/duplicate.db` - Duplicate delivery detection
- `/var/lib/imap/annotation.db` - Message annotations (for mistermcfeely)

### 9. Start Cyrus IMAPd

```bash
# Enable at boot
sudo systemctl enable cyrus-imapd

# Start the service
sudo systemctl start cyrus-imapd

# Verify it's running
sudo systemctl status cyrus-imapd

# Check logs
sudo journalctl -u cyrus-imapd -f
```

### 10. Create Admin Account

The default admin is "cyrus". To create the initial Cyrus admin:

```bash
# Create system user if not present
sudo useradd -r -m -d /var/lib/imap -s /usr/sbin/nologin cyrus 2>/dev/null || true

# Set Cyrus admin password (for SASL)
# Option A: Use system PAM authentication
# Make sure "cyrus" user exists and has a password via system means
# (depends on your auth system - LDAP, PAM, etc.)

# Option B: For testing, create a temporary account
sudo useradd testuser
echo "testpass" | sudo passwd --stdin testuser
```

Then add "testuser" to Cyrus admins by modifying `/etc/postoffice/imapd.conf`:
```conf
admins: cyrus testuser
```

## Configuration Customization

### Email Domain Configuration

Edit `/etc/postoffice/imapd.conf` and set your domain:

```conf
# Add your organization name
# (used in various server messages)
servername: mail.example.com
```

### Shared Mailbox Naming Patterns

The default configuration uses:
```
shared/teamname@hostname.example.com
```

To customize the shared mailbox prefix, modify `/etc/postoffice/imapd.conf`:

```conf
# Default is "shared"
sharedprefix: teams

# Then mailboxes will be: teams/marketing@hostname
```

### Sieve Global Scripts

Enable organization-wide mail filtering:

```bash
# Create global scripts directory
sudo mkdir -p /var/lib/imap/global_scripts
sudo chown cyrus:cyrus /var/lib/imap/global_scripts
sudo chmod 755 /var/lib/imap/global_scripts

# Add a global script to filter out spam
cat > spam_filter.sieve << 'SIEVE'
# Global spam filter
if header :contains "X-Spam-Flag" "YES"
{
  fileinto "Junk";
  stop;
}
SIEVE

sudo cp spam_filter.sieve /var/lib/imap/global_scripts/
sudo chown cyrus:cyrus /var/lib/imap/global_scripts/spam_filter.sieve
```

Then modify `/etc/postoffice/imapd.conf`:
```conf
global_sieve_scripts: /var/lib/imap/global_scripts
```

### Event Notification for Monitoring

> **Note [2026-10-09]:** The architecture below describes the
> `mcfeely-notify` external-event-bridge alternative. The
> production mcfeely deployment does **not** use this
> architecture; the live system polls via the in-process
> `mailbox_poller` in
> `src/postoffice/services/mailbox_poller.py`, and the
> `notify` service is commented out in
> `etc-postoffice/cyrus.conf:35`. The
> `event_notifier: external` line in
> `etc-postoffice/imapd.conf:224` is also not used by the
> live mailbox_poller. This section is preserved as a
> reference for the alternative architecture.

To enable real-time event notifications for mistermcfeely monitoring:

Modify `/etc/postoffice/imapd.conf`:
```conf
# Change from:
event_notifier: log

# To:
event_notifier: external

# And add the path to your notification handler:
event_notifier_path: /usr/local/bin/mcfeely-notify
```

Create the notification handler at `/usr/local/bin/mcfeely-notify`:

```bash
#!/usr/bin/env python3
# mcfeely-notify - Custom event handler for mistermcfeely
# Receives RFC 5423 events from Cyrus and routes to mistermcfeely

import sys
import json
import os
from pathlib import Path

# Read command-line arguments
event_class = None
user = None
mailbox = None
priority = None

i = 1
while i < len(sys.argv):
    if sys.argv[i] == '-c':
        event_class = sys.argv[i+1]
        i += 2
    elif sys.argv[i] == '-u':
        user = sys.argv[i+1]
        i += 2
    elif sys.argv[i] == '-m':
        mailbox = sys.argv[i+1]
        i += 2
    elif sys.argv[i] == '-p':
        priority = sys.argv[i+1]
        i += 2
    else:
        i += 1

# Read event data from stdin
try:
    event_data = json.load(sys.stdin)
except:
    event_data = {}

# Only process events for shared mailboxes
if not mailbox or not mailbox.startswith('shared/'):
    sys.exit(0)

# Log to syslog for mistermcfeely monitoring
import syslog
syslog.openlog('mcfeely-notify', syslog.LOG_PID, syslog.LOG_MAIL)
syslog.syslog(f"Event: {event_class} Mailbox: {mailbox} UID: {event_data.get('uid')}")
syslog.closelog()

sys.exit(0)
```

Then make it executable:
```bash
sudo chmod 755 /usr/local/bin/mcfeely-notify
```

## Post-Installation Verification

### 1. Check Service Status

```bash
# Check if Cyrus is running
systemctl status cyrus-imapd

# Check if required services are bound
netstat -tlnp | grep -E 'imap|lmtp|sieve'

# Expected output:
# tcp 0 0 0.0.0.0:143 0.0.0.0:* LISTEN (imap)
# tcp 0 0 0.0.0.0:993 0.0.0.0:* LISTEN (imaps)
# tcp 0 0 0.0.0.0:4190 0.0.0.0:* LISTEN (sieve)
```

### 2. Test IMAP Connection

```bash
# Test plain IMAP (will fail if not authenticated)
openssl s_client -connect localhost:993 -showcerts

# Expected: Should show IMAP greeting
# * OK [CAPABILITY IMAP4rev1 ...]
```

### 3. Test Annotation Support

Verify that annotations are working:

```bash
# Connect via Python IMAP
python3 << 'PYTHON'
import imaplib

# Connect to server
conn = imaplib.IMAP4_SSL('localhost')

# Check for annotation support
caps = conn.capabilities()
if 'ANNOTATE-EXPERIMENT-1' in caps:
    print("✓ ANNOTATE extension enabled")
else:
    print("✗ ANNOTATE extension NOT enabled")
    print(f"Available: {caps}")

conn.logout()
PYTHON
```

### 4. Check Cyrus Admin Access

```bash
# Create a test mailbox (requires cyrus admin)
echo "cm user/test@localhost" | cyradm -u cyrus localhost

# List created mailboxes
cyradm -u cyrus localhost << 'CYRADM'
lm
quit
CYRADM
```

### 5. Verify Annotation Definitions

```bash
# Check that annotation definitions are loaded
grep -n "mcfeely" /etc/postoffice/imapd.annotations

# Should show the three main annotations:
# /vendor/mcfeely/claimed-by
# /vendor/mcfeely/claimed-at
# /vendor/mcfeely/claim-notes
```

## Common Configuration Changes

### Enable Message Size Limits

```conf
# In /etc/postoffice/imapd.conf, change:
maxmessagesize: 102400  # 100 MB

# To smaller/larger value as needed
maxmessagesize: 52428800  # 50 MB
```

### Configure Mailbox Quotas

```bash
# Set user quota
cyradm -u cyrus localhost << 'CYRADM'
sq user/alice@example.com 1048576
quit
CYRADM

# Check quota
cyradm -u cyrus localhost << 'CYRADM'
lq user/alice@example.com
quit
CYRADM
```

### Create Shared Mailboxes

```bash
# Create shared team mailbox
cyradm -u cyrus localhost << 'CYRADM'
cm shared/support@example.com
setaclown shared/support@example.com alice@example.com lrswipcd
setaclown shared/support@example.com bob@example.com lrswipcd
setaclown shared/support@example.com cyrus a
quit
CYRADM
```

### Enable Sieve Filtering

```bash
# Sieve is enabled by default
# Users can upload scripts via ManageSieve (port 4190)

# To test with a simple script:
cat > test_filter.sieve << 'SIEVE'
require "fileinto";

if header :contains "Subject" "spam"
{
    fileinto "Junk";
    stop;
}

# Keep remaining messages in inbox
keep;
SIEVE

# Upload via sieveshell
sieveshell -u alice@example.com localhost

# In sieveshell:
# > put test_filter.sieve
# > activate test_filter.sieve
# > list
# > quit
```

## Troubleshooting

### Service Won't Start

Check logs:
```bash
journalctl -u cyrus-imapd -n 50 --no-pager
tail -f /var/log/maillog
```

Common issues:
- **Permission denied**: Check ownership of `/var/lib/imap`, `/var/spool/imap`
- **Port already in use**: Check if other IMAP servers running
- **Configuration syntax error**: Validate with `imapconf -u /etc/postoffice/imapd.conf`

### Annotation Not Working

Verify:
1. Annotation extension is enabled: `grep "ANNOTATE" /etc/postoffice/imapd.conf`
2. Annotation database exists: `ls -la /var/lib/imap/annotation.db*`
3. Cyrus was restarted after config change: `systemctl restart cyrus-imapd`

### SASL Authentication Failing

Check:
```bash
# Verify saslauthd is running
systemctl status saslauthd

# Test SASL directly
echo "testpass" | testsaslauthd -u testuser -r localhost

# Check socket permissions
ls -la /run/saslauthd/mux
# Should be readable by cyrus user
```

### TLS Certificate Issues

Check certificate validity:
```bash
# View certificate details
openssl x509 -in /etc/pki/cyrus/imapd.pem -text -noout

# Verify certificate matches key
openssl x509 -in /etc/pki/cyrus/imapd.pem -noout -modulus | openssl md5
openssl rsa -in /etc/pki/cyrus/imapd.pem -noout -modulus | openssl md5
# MD5 hashes should match
```

## Integration with Mistermcfeely

Once Cyrus is running and verified:

1. **Set environment variables for mistermcfeely**:
```bash
export MCFEELY_OBFUSCATE_SECRET="your-secret-key-for-claim-hash"
```

2. **Configure notification routing in database**:
```sql
-- Setup notification rules for shared mailboxes
INSERT INTO postoffice.message_routing
(mailbox_name, event_type, actor_moniker, recipient_moniker, urgency)
VALUES 
  ('shared/%', 'message-new', NULL, 'admin', 'ROUTINE'),
  ('shared/%', 'message-claimed', NULL, 'admin', 'IMPORTANT');
```

3. **Start mistermcfeely monitoring**:
```bash
python3 -m mistermcfeely.startup
```

4. **Test claim operation**:
```bash
# Claim a message
python3 -m mistermcfeely.imap_client --mailbox shared/support@localhost claim 1 alice

# Verify annotation was set
cyradm -u cyrus localhost << 'CYRADM'
getannotation shared/support@localhost 1 /vendor/mcfeely/claimed-by
quit
CYRADM
```

## Backup and Recovery

### Regular Backups

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR=/var/backups/cyrus
mkdir -p $BACKUP_DIR

# Backup mailboxes
tar czf $BACKUP_DIR/mailboxes-$(date +%Y%m%d-%H%M%S).tar.gz \
  /var/lib/imap /var/spool/imap

# Backup configuration
tar czf $BACKUP_DIR/config-$(date +%Y%m%d-%H%M%S).tar.gz \
  /etc/postoffice/cyrus.conf /etc/postoffice/imapd.conf /etc/postoffice/imapd.annotations

# Keep only 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete
```

### Recovery from Backup

```bash
# Stop Cyrus
sudo systemctl stop cyrus-imapd

# Restore mailboxes
sudo tar xzf /var/backups/cyrus/mailboxes-YYYYMMDD-HHMMSS.tar.gz -C /

# Restore configuration
sudo tar xzf /var/backups/cyrus/config-YYYYMMDD-HHMMSS.tar.gz -C /

# Rebuild mailbox database
sudo /usr/lib/cyrus-imapd/tools/reconstruct -r

# Restart Cyrus
sudo systemctl start cyrus-imapd
```

## Performance Tuning

### For High-Volume Shared Mailboxes

```conf
# In /etc/postoffice/imapd.conf:

# Increase connection limits
maxchild: 100

# Enable aggressive caching
cache_aggressive: yes

# Increase cache timeout
cache_timeout: 30

# Reduce polling interval in mistermcfeely monitoring config
imap_poll_interval_seconds: 5  # More frequent checks
```

### For Multiple Shared Mailboxes

```conf
# Increase mailbox list cache
maxmboxlist: 500000

# Enable subscriptions caching
cache_mailbox: yes

# Optimize twoskip database settings
annotation_db_path: /var/spool/imap/annotation.db
```

## Support and Documentation

For more information:
- [Cyrus IMAPd Documentation](https://cyrus.example.com/docs)
- [RFC 5423 - IMAP4 Notifications](https://tools.ietf.org/html/rfc5423)
- [mistermcfeely Project](../README.md)

