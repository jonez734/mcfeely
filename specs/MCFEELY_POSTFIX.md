# MCFeely Postfix Configuration Specification

This document is referenced by:
- [MCFEELY_DESIGN.md](../MCFEELY_DESIGN.md)
- [MCFEELY_CYRUS_IMAP.md](../MCFEELY_CYRUS_IMAP.md)
- [MCFEELY_DOVECOT.md](../MCFEELY_DOVECOT.md)

## Overview

This document specifies Postfix MTA configuration for integration with either Cyrus IMAPd or Dovecot for MCFeely shared mailbox handling.

## Architecture

```
                    ┌─────────────┐
                    │   Postfix   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Cyrus    │ │  Dovecot │ │  Local   │
        │   LMTP    │ │   LMTP   │ │  Maildir │
        └──────────┘ └──────────┘ └──────────┘
```

## Common Configuration

### /etc/postfix/main.cf - Common Settings

```cf
# Network identity
myhostname = mail.example.com
mydomain = example.com
myorigin = $mydomain
inet_interfaces = all
inet_protocols = ipv4

# Domains
mydestination = $myhostname, localhost, localhost.localdomain
virtual_alias_domains = example.com
 relay_domains = 

# Mail spool
home_mailbox = Maildir/
mail_spool_directory = /var/mail

# Security
smtpd_sasl_auth_enable = no
smtpd_sasl_security_options = noanonymous
smtpd_recipient_restrictions = permit_mynetworks, reject_unauth_destination

# Size limits
message_size_limit = 52428800
mailbox_size_limit = 0

# Logging
maillog_file = /var/log/maillog
```

## Delivery Methods

### Method 1: LMTP to Cyrus IMAPd

```cf
# LMTP socket for Cyrus
mailbox_transport = lmtp:unix:/var/lib/imap/socket/lmtp
fallback_transport = lmtp:unix:/var/lib/imap/socket/lmtp

# Alternative: TCP (if Cyrus listening on network)
# mailbox_transport = lmtp:localhost:24
```

#### /etc/postfix/master.cf - Cyrus LMTP service

```cf
# LMTP to Cyrus
lmtp      unix  -       n       n       -       -       lmtp
```

#### /etc/postfix/transport (optional)

```
example.com lmtp:unix:/var/lib/imap/socket/lmtp
support.example.com lmtp:unix:/var/lib/imap/socket/lmtp
ops.example.com lmtp:unix:/var/lib/imap/socket/lmtp
```

```bash
postmap /etc/postfix/transport
```

### Method 2: LMTP to Dovecot

```cf
# Dovecot LMTP socket
mailbox_transport = lmtp:unix:/var/run/dovecot/lmtp
fallback_transport = lmtp:unix:/var/run/dovecot/lmtp
```

#### /etc/postfix/master.cf - Dovecot LMTP service

```cf
# Dovecot LMTP
dovecot   unix  -       n       n       -       -       lmtp
  -o master_service_disable=*
```

### Method 3: LDA (Local Delivery Agent)

#### Cyrus LDA

```cf
mailbox_command = /usr/lib/cyrus-imapd/deliver
```

#### Dovecot LDA

```cf
mailbox_command = /usr/libexec/dovecot/dovecot-lda -f "$SENDER" -a "$RECIPIENT"
```

### Method 4: Virtual Mailboxes

For virtual domain hosting:

```cf
# Virtual mailbox configuration
virtual_mailbox_domains = example.com
virtual_mailbox_base = /var/mail/vhosts
virtual_mailbox_maps = hash:/etc/postfix/vmailbox
virtual_alias_maps = hash:/etc/postfix/virtual
virtual_uid_maps = static:5000
virtual_gid_maps = static:5000
virtual_mailbox_limit = 0
```

#### /etc/postfix/vmailbox

```
alice@example.com    example.com/alice
bob@example.com      example.com/bob
support@example.com  example.com/support
shared/ops@example.com    example.com/shared/ops
```

#### /etc/postfix/virtual

```
# Forward mappings
postmaster@example.com postmaster
```

```bash
postmap /etc/postfix/vmailbox
postmap /etc/postfix/virtual
```

## Shared Mailbox Configuration

### For Cyrus IMAPd

```cf
# Allow delivery to shared mailboxes
local_recipient_maps = proxy:unix:passwd.byname $alias_maps hash:/etc/postfix/local_recipients
relay_domains = hash:/etc/postfix/relay_domains
```

#### /etc/postfix/local_recipients

```
# Allow delivery to shared inbox paths
shared/ops@example.com OK
shared/support@example.com OK
```

#### /etc/postfix/relay_domains

```
# Domains we're willing to relay
example.com OK
```

### For Dovecot

```cf
# Dovecot handles recipient verification
virtual_transport = lmtp:unix:/var/run/dovecot/lmtp
relay_domains = 
```

## Security Configuration

### SASL Authentication (for submission)

```cf
# Enable SASL for authenticated relay
submission inet n       -       n       -       -       smtpd
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_sasl_security_options=noanonymous
  -o smtpd_recipient_restrictions=permit_sasl_authenticated,reject
```

### TLS Configuration

```cf
# TLS settings
smtpd_tls_cert_file = /etc/pki/tls/certs/server.crt
smtpd_tls_key_file = /etc/pki/tls/private/server.key
smtpd_tls_security_level = may
smtpd_tls_auth_only = yes
smtpd_tls_loglevel = 1

# Outgoing TLS
smtp_tls_security_level = may
smtp_tls_loglevel = 1
```

### Connection Restrictions

```cf
# Reject unverified recipients
smtpd_recipient_restrictions = 
    permit_mynetworks,
    permit_sasl_authenticated,
    reject_unauth_destination,
    check_recipient_access hash:/etc/postfix/recipient_access

# Rate limiting
anvil_rate_time_unit = 60s
smtpd_client_connection_count_limit = 10
smtpd_client_message_rate_limit = 20
```

#### /etc/postfix/recipient_access

```
# Block specific recipients
bounced@example.com REJECT
```

```bash
postmap /etc/postfix/recipient_access
```

##masquerading and Relaying

### Domain Masquerading

```cf
# Rewrite envelope sender
masquerade_domains = example.com
masquerade_exceptions = root, postmaster

# Rewrite headers
header_checks = regexp:/etc/postfix/header_checks
```

#### /etc/postfix/header_checks

```
/^From:.*@example.com/ REPLACE From: alice@example.com
/^Reply-To:.*@example.com/ REPLACE Reply-To: alice@example.com
```

### Relay Configuration

```bash
# For external relayhost
relayhost = [smtp.example.com]
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
```

#### /etc/postfix/sasl_passwd

```
[smtp.example.com] username:password
```

```bash
postmap /etc/postfix/sasl_passwd
chmod 600 /etc/postfix/sasl_passwd
```

## Testing

### Verify Postfix is running

```bash
postfix check
systemctl status postfix
```

### Test mail delivery

```bash
# Send test email
echo "Test body" | sendmail -v alice@example.com

# Check logs
tail -f /var/log/maillog

# Check mail queue
mailq
postqueue -p
```

### Test LMTP delivery

```bash
# For Cyrus
telnet localhost lmtp
# LHLO localhost
# MAIL FROM:<test@example.com>
# RCPT TO:<user/shared/ops@example.com>
# DATA
# Test message
# .

# For Dovecot
telnet localhost 24
```

### Verify virtual mailbox delivery

```bash
ls -la /var/mail/vhosts/example.com/alice/
```

## Troubleshooting

### Common Issues

1. **Mail not delivered**
   - Check `mailq` for queue
   - Check `/var/log/maillog` for errors
   - Verify transport is correct

2. **Permission errors**
   - Check socket permissions
   - Verify mail spool ownership

3. **Relaying denied**
   - Check `mydestination` and `relay_domains`
   - Verify SASL auth if needed

### Debug Commands

```bash
# Full debug output
postfix -vvv start

# Check configuration
postconf -n

# Test routing
postmap -q example.com hash:/etc/postfix/transport

# Flush queue
postqueue -f

# Remove stuck message
postsuper -d MESSAGE_ID
```

## Maintenance

### Backup configuration

```bash
tar czf postfix-backup-$(date +%Y%m%d).tar.gz \
    /etc/postfix/main.cf \
    /etc/postfix/master.cf \
    /etc/postfix/*.cf \
    /etc/postfix/*.db \
    /etc/postfix/transport \
    /etc/postfix/virtual \
    /etc/postfix/vmailbox
```

### Reload after changes

```bash
postfix reload
```

### Monitoring

- Log rotation: `/var/log/maillog`
- Queue monitoring: `watch -n 5 'mailq'`
- Delivery rate: `postqueue -p | tail -1`