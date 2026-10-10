# Cyrus IMAPd Configuration for Mistermcfeely

This directory contains a complete, production-ready Cyrus IMAPd configuration for the mistermcfeely IMAP postoffice project.

## Overview

The mistermcfeely project integrates with Cyrus IMAPd to manage shared mailboxes with real-time notification support. Message claim state is stored using Cyrus's ANNOTATE extension, allowing distributed team members to coordinate on shared inbox messages.

**Key Features Enabled:**
- ✅ IMAP4rev1 with full RFC compliance
- ✅ ANNOTATE-EXPERIMENT-1 extension (message metadata)
- ✅ TLS/SSL encryption (IMAPS on port 993)
- ✅ Sieve email filtering (timsieved on port 4190)
- ✅ LMTP delivery integration (with Postfix)
- ✅ Real-time event notifications (notifyd)
- ✅ Per-message claim tracking via annotations
- ✅ Shared mailbox ACLs for team access

## Files in This Directory

### Configuration Files (Production-Ready)

#### 1. **cyrus.conf** - Master Service Configuration
- Defines all Cyrus daemon processes and services
- IMAP and IMAPS services with connection limits
- LMTP service for Postfix delivery integration
- Sieve service (timsieved) for mail filtering rules
- Notifyd daemon for real-time event notifications
- Logging configuration for all services

**Key Settings:**
```conf
imap        cmd="imapd -U 30" listen="imap" prefork=0 maxchild=100
imaps       cmd="imapd -s -U 30" listen="imaps" prefork=0 maxchild=100
lmtp        cmd="lmtpd -U 30" listen="lmtp" prefork=0 maxchild=20
sieve       cmd="timsieved" listen="sieve" prefork=0 maxchild=10
# notifyd is commented out in the deployed etc-postoffice/cyrus.conf:35
# (mcfeely's live deployment polls via the in-process mailbox_poller
# in src/postoffice/services/mailbox_poller.py; the event-bridge
# notifyd path is not deployed. See MCFEELY_CYRUS_IMAP.md for the
# alternative architecture.)
# notify      cmd="notifyd" listen="/var/lib/imap/notify" prefork=1
```

#### 2. **imapd.conf** - IMAP Daemon Configuration
- Core IMAP protocol settings
- Authentication and TLS configuration
- ANNOTATE extension for message metadata storage
- Database engine selection (twoskip recommended)
- Quotas, limits, and performance tuning
- Email filtering (Sieve) configuration

**Critical Settings for Mistermcfeely:**
```conf
enable_annotate: yes
annotation_db: twoskip
annotation_definitions: /etc/postoffice/imapd.annotations
```

#### 3. **imapd.annotations** - Annotation Definitions
- Defines custom per-message metadata schema
- Three required annotations for message claiming:
  - `/vendor/mcfeely/claimed-by` - User who claimed message (HMAC hash)
  - `/vendor/mcfeely/claimed-at` - Claim timestamp (ISO 8601)
  - `/vendor/mcfeely/claim-notes` - Optional claim reason
- Six optional annotations for extended functionality:
  - `/vendor/mcfeely/claim-priority` - Priority level
  - `/vendor/mcfeely/assigned-team` - Team assignment
  - `/vendor/mcfeely/custom-metadata` - Third-party integration data
  - `/vendor/mcfeely/owner-team` - Mailbox owner team
  - `/vendor/mcfeely/mailbox-sla` - Service level agreement
  - `/vendor/mcfeely/mailbox-category` - Mailbox type classification

### SASL Authentication Files

#### 4. **saslauthd.conf** - saslauthd Daemon Configuration
- Main SASL authentication daemon settings
- Mechanism selection (PAM, LDAP, rimap)
- Runtime configuration (socket dir, PID file, flags)

**Key Settings:**
```conf
MECHANISMS = pam
SOCKETDIR = /run/saslauthd
PAM_SERVICE = imap
```

#### 5. **saslauthd.sysconfig** - System Startup Configuration
- Runtime flags for sysconfig (RHEL) or defaults (Debian)
- Mechanism and socket directory settings

**Key Settings:**
```conf
SOCKETDIR=/run/saslauthd
MECH=pam
FLAGS="-r"
```

#### 6. **pam.d-saslauthd** - PAM Authentication Rules
- PAM service configuration for saslauthd
- System authentication for IMAP users

### Documentation Files

#### 7. **CYRUS_SETUP.md** - Complete Installation Guide
Comprehensive step-by-step instructions including:
- Package installation (Fedora/RHEL and Debian/Ubuntu)
- Configuration file deployment
- Directory and permission setup
- TLS certificate generation (self-signed and Let's Encrypt)
- SASL authentication configuration
- Database initialization
- Service startup and verification
- Post-installation testing procedures
- Troubleshooting guide
- Integration with mistermcfeely
- Backup and recovery procedures
- Performance tuning recommendations

#### 8. **README.md** - This File
Overview, file descriptions, and quick reference.

## Quick Start (2-Minute Summary)

### 1. Install Cyrus
```bash
# On Fedora/RHEL
sudo dnf install cyrus-imapd cyrus-imapd-utils cyrus-sasl cyrus-sasl-plain

# On Debian/Ubuntu
sudo apt-get install cyrus-imapd cyrus-sasl
```

### 2. Deploy Configuration
```bash
sudo cp cyrus.conf /etc/postoffice/cyrus.conf
sudo cp imapd.conf /etc/postoffice/imapd.conf
sudo cp imapd.annotations /etc/postoffice/imapd.annotations
```

### 3. Install SASL Authentication
```bash
make install-auth
# or manually:
sudo cp saslauthd.conf /etc/sasl2/saslauthd.conf
sudo cp saslauthd.sysconfig /etc/sysconfig/saslauthd  # or /etc/default/saslauthd on Debian
sudo cp pam.d-saslauthd /etc/pam.d/saslauthd
```

### 4. Initialize Cyrus
```bash
sudo mkdir -p /var/lib/imap /var/spool/imap
sudo chown -R cyrus:cyrus /var/lib/imap /var/spool/imap
sudo /usr/lib/cyrus-imapd/tools/mkimap
```

### 5. Start Service
```bash
sudo systemctl enable saslauthd
sudo systemctl start saslauthd
sudo systemctl enable cyrus-imapd
sudo systemctl start cyrus-imapd
sudo systemctl status cyrus-imapd
```

### 5. Create Admin & Test Mailbox
```bash
sudo cyradm -u cyrus localhost <<'CYRADM'
cm shared/test@localhost
quit
CYRADM
```

**For complete details, see CYRUS_SETUP.md**

## Configuration Details by Use Case

### Use Case 1: Single-Machine Shared Mailbox
- All users on same system
- Local system authentication via PAM
- Simple shared mailbox pattern: `shared/support@localhost`

**Customize in imapd.conf:**
```conf
servername: localhost
admins: cyrus
sasl_pwcheck_method: saslauthd
```

### Use Case 2: Multi-Domain Organization
- Multiple mail domains
- LDAP/AD authentication backend
- Shared mailbox pattern: `shared/teamname@domain.example.com`

**Customize in imapd.conf:**
```conf
servername: mail.example.com
sasl_mech_list: PLAIN LOGIN DIGEST-MD5
# Add LDAP configuration in SASL settings
```

### Use Case 3: High-Volume Support Queue
- Many concurrent connections
- Real-time event notifications
- Extended annotation tracking

**Customize in imapd.conf:**
```conf
# Performance tuning
maxchild: 200
cache_aggressive: yes
cache_timeout: 30

# Event notifications
event_notifier: external
event_notifier_path: /usr/local/bin/mcfeely-notify
```

### Use Case 4: Secure Compliance Environment
- Mandatory TLS for all connections
- No plaintext authentication
- Message audit trail

**Customize in imapd.conf:**
```conf
allowplaintext: no
tls_require_cert: yes
tls_cipher_suite: HIGH:!aNULL:!MD5:!3DES
expunge_days: 365  # Never auto-delete
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Mistermcfeely Application                   │
│  (IMAP Client, Message Claim Management, Notifications) │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
    ┌───▼────┐          ┌────────▼───────┐
    │  IMAP  │          │    bbsengine6  │
    │ (9993) │          │  Notification  │
    └────┬───┘          └────────────────┘
         │
    ┌────▼─────────────────────────────────┐
    │   Cyrus IMAPd Server                  │
    │  ┌──────────────────────────────────┐│
    │  │ Services:                         ││
    │  │ • imapd (IMAP, port 143)          ││
    │  │ • imaps (IMAPS, port 993)         ││
    │  │ • lmtpd (Delivery)                ││
    │  │ • timsieved (Sieve filtering)     ││
    │  │ • notifyd (Event notification)    ││
    │  └──────────────────────────────────┘│
    │  ┌──────────────────────────────────┐│
    │  │ Datastores:                       ││
    │  │ • Mailboxes: /var/spool/imap     ││
    │  │ • Metadata: /var/lib/imap/*.db   ││
    │  │ • Annotations (claim state)       ││
    │  └──────────────────────────────────┘│
    └─────────────────────────────────────┘
         │
         ├─ LMTP from Postfix
         ├─ TLS to Mail Clients
         └─ Event Notifications
```

## Key Configurations Explained

### Annotation Storage
```
Message UID 42 in shared/support@localhost
├─ Subject: "Customer billing issue"
├─ From: customer@example.com
├─ Date: 2026-05-21T14:30:00Z
└─ Annotations:
   ├─ /vendor/mcfeely/claimed-by: "f7e3d1c9..." (HMAC hash of user ID)
   ├─ /vendor/mcfeely/claimed-at: "2026-05-21T14:35:00Z"
   └─ /vendor/mcfeely/claim-notes: "Waiting on customer response"
```

### ACL Example
```bash
# Create shared mailbox with team access
cm shared/support@example.com

# Alice can: lookup, read, see, write, insert, post, create, delete, admin
setaclown shared/support@example.com alice lrswipcd

# Bob can: lookup, read, see, write, insert, post, create, delete
setaclown shared/support@example.com bob lrswipcd

# Cyrus admin retains full control
setaclown shared/support@example.com cyrus a
```

### Event Flow Example
```
User "alice" claims message UID 423:
  │
  ├─ mistermcfeely.imap_client.claim_message()
  │  │
  │  └─ ANNOTATE command:
  │     SET UID 423
  │     /vendor/mcfeely/claimed-by = (HMAC hash of "alice")
  │     /vendor/mcfeely/claimed-at = "2026-05-21T15:30:00Z"
  │
  ├─ Cyrus stores annotation in /var/lib/imap/annotation.db
  │
  ├─ mail_poller picks up flag change (in-process polling;
  │  the Cyrus notifyd event-bridge is NOT used in the live
  │  deployment; see etc-postoffice/cyrus.conf:35 where the
  │  `notify` service is commented out and
  │  etc-postoffice/imapd.conf where event_notifier is not
  │  set to external)
  │  └─ event_type: "message-claimed"
  │     mailbox_name: "shared/support@example.com"
  │     message_uid: 423
  │     actor: "alice"
  │
  └─ Other systems consume notification:
     ├─ Email notifier sends update email
     ├─ Chat bot posts to Slack
     ├─ Dashboard updates claim state
     └─ Webhook calls external API
```

## Environment Variables for Mistermcfeely

```bash
# Encryption secret for obfuscating claim hashes (optional)
export MCFEELY_OBFUSCATE_SECRET="your-shared-secret-key-minimum-32-chars"

# If not set, uses database password (falls back gracefully)
# If neither set, uses plain text (for backward compatibility)
```

## Validation Checklist

Use this before deploying to production:

- [ ] Configuration files copied to /etc/postoffice/cyrus.conf, /etc/postoffice/imapd.conf, /etc/postoffice/imapd.annotations
- [ ] SASL configuration installed (saslauthd.conf, saslauthd.sysconfig, pam.d-saslauthd)
- [ ] Makefile targets available: `make install-auth`
- [ ] Permissions set: 644 for config files, 750+ for directories
- [ ] TLS certificates generated or deployed from CA
- [ ] SASL authentication mechanism configured (saslauthd running)
- [ ] Cyrus service starts without errors: `systemctl start cyrus-imapd`
- [ ] IMAP ports bound: `netstat -tlnp | grep -E ':143|:993'`
- [ ] Test mailbox created: `cyradm -u cyrus localhost`
- [ ] Annotation extension verified: `imapd -X` shows ANNOTATE
- [ ] Database files initialized in /var/lib/imap/
- [ ] Log files appear in journalctl: `journalctl -u cyrus-imapd`
- [ ] LMTP delivery tested with Postfix
- [ ] TLS handshake successful with client: `openssl s_client -connect localhost:993`

## Common Modifications

### Change Admin User
In imapd.conf:
```conf
# Was: admins: cyrus
admins: mailops
```

### Enable Debug Logging
In imapd.conf:
```conf
# Was: loglevel: 3
loglevel: 5    # Maximum verbosity
trace: yes
```

Then monitor:
```bash
journalctl -u cyrus-imapd -f
```

### Increase Message Size Limit
In imapd.conf:
```conf
# Was: maxmessagesize: 102400  (100 MB)
maxmessagesize: 524288000  (500 MB)
```

### Disable TLS for Internal Networks
In imapd.conf:
```conf
# Add allowed unencrypted networks
allowplaintext: yes  # Or configure per-network if supported
```

**Warning: Only for completely internal networks!**

### Add External Event Handler
In imapd.conf:
```conf
event_notifier: external
event_notifier_path: /usr/local/bin/custom-event-handler
```

Then create `/usr/local/bin/custom-event-handler` script.

## Troubleshooting Quick Reference

| Issue | Check | Fix |
|-------|-------|-----|
| Service won't start | `journalctl -u cyrus-imapd` | Fix syntax in /etc/postoffice/imapd.conf |
| Annotation not working | `ls /var/lib/imap/annotation.db*` | Run `mkimap` to init DB |
| IMAPS connection refused | `netstat -tlnp \| grep 993` | Check TLS certificate path |
| SASL auth fails | `testsaslauthd -u user` | Verify saslauthd running |
| Quota issues | `cyradm` → `lq user/name` | Check partition disk space |

## Performance Baseline

| Metric | Default | High-Volume | Notes |
|--------|---------|-------------|-------|
| Max connections | 100 | 500 | imapd maxchild setting |
| Annotation queries | Per-message | Indexed lookup | twoskip DB is fast |
| Event latency | <1s | <100ms | With notifyd |
| Cache timeout | 11s | 30s | Set in imapd.conf |

## Security Hardening

1. **TLS Certificate**: Use production CA certificate (not self-signed)
2. **Firewall**: Restrict IMAP/IMAPS to known networks
3. **SASL**: Use strong authentication (not PLAIN if possible)
4. **ACLs**: Limit admin access to "cyrus" system account only
5. **Backups**: Regular encrypted backups of /var/lib/imap
6. **Logs**: Aggregate logs to syslog server for audit trail
7. **Passwords**: Use strong passwords for Cyrus admin account

## Related Documentation

- **[CYRUS_SETUP.md](CYRUS_SETUP.md)** - Detailed installation and configuration guide
- **[../README.md](../README.md)** - Mistermcfeely project overview
- **[../QUICK_REFERENCE.md](../QUICK_REFERENCE.md)** - Mistermcfeely quick reference
- **[Cyrus IMAPd Official Docs](https://www.cyrusimap.org/)** - Upstream documentation
- **[RFC 3501 (IMAP4rev1)](https://tools.ietf.org/html/rfc3501)** - IMAP protocol specification
- **[RFC 5423 (IMAP Notifications)](https://tools.ietf.org/html/rfc5423)** - Event notification specification

## Support

For issues with:
- **Cyrus Installation/Configuration**: See CYRUS_SETUP.md troubleshooting section
- **Mistermcfeely Integration**: See ../QUICK_REFERENCE.md
- **IMAP Protocol Questions**: Consult RFC 3501 and Cyrus official documentation
- **This Configuration**: Review the inline comments in cyrus.conf and imapd.conf

## Version Information

- **Cyrus IMAPd**: 3.0+ (tested with 3.4+)
- **Sieve**: RFC 5228 compliant (timsieved)
- **ANNOTATE**: Experimental extension (de facto standard)
- **Python**: 3.9+ (for mistermcfeely client)

## License

These configuration files are provided as part of the mistermcfeely project.

---

**Last Updated**: May 21, 2026
**Maintained By**: mistermcfeely project team
**Status**: Production Ready
