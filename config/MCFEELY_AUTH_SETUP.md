# MCFEELY_AUTH_SETUP.md
# Setup guide for mcfeely-authd SASL authentication daemon

## Overview

`mcfeely-authd` is a SASL authentication daemon that enables IMAP passwords to be stored independently of shell passwords. It provides database-based authentication with optional PAM fallback for migration.

## Architecture

```
IMAP Client → Cyrus IMAP → saslauthd → mcfeely-authd → PostgreSQL (sasl_password table)
                                            ↓
                                     PAM (fallback for unmigrated users)
```

## Prerequisites

- Python 3.9+
- PostgreSQL client library (`psycopg2`)
- Cyrus SASL (`cyrus-sasl` and `cyrus-saslauthd`)
- PostgreSQL server with `zoid6test` database

## Installation

### 1. Install Dependencies

```bash
# Python packages
pip install psycopg2-binary

# Cyrus SASL
dnf install cyrus-sasl cyrus-sasl-saslauthd  # Fedora/RHEL
apt install sasl2-bin                          # Debian/Ubuntu
```

### 2. Create Database Schema

```bash
# Run the SQL schema
psql -d zoid6test -f /path/to/mistermcfeely/sql/sasl_password.sql
```

### 3. Install mcfeely-authd

```bash
# Copy daemon to system location
sudo cp src/mcfeely_authd/mcfeely_authd.py /usr/local/bin/mcfeely-authd
sudo chmod +x /usr/local/bin/mcfeely-authd

# Create socket directory
sudo mkdir -p /var/run/mcfeely-authd
sudo chown postoffice:postoffice /var/run/mcfeely-authd

# Create log directory
sudo mkdir -p /var/log/mcfeely-authd
sudo chown postoffice:postoffice /var/log/mcfeely-authd

# Copy configuration
sudo cp etc-postoffice/mcfeely-authd.conf /etc/mcfeely-authd.conf
```

### 4. Configure saslauthd

Update `/etc/saslauthd.conf`:

```bash
# Use authdaemond mechanism
MECHANISMS = authdaemond
AUTHDAEMOND_PATH = /var/run/mcfeely-authd/mux

# Realm merging flag
FLAGS = "-r"
```

### 5. Start mcfeely-authd

```bash
# As root (or via systemd)
sudo /usr/local/bin/mcfeely-authd --foreground

# Or as postoffice user (for testing)
/usr/local/bin/mcfeely-authd -f
```

### 6. Create systemd Service (optional)

Create `/etc/systemd/system/mcfeely-authd.service`:

```ini
[Unit]
Description=mcfeely-authd SASL Authentication Daemon
After=network.target postgresql.service

[Service]
Type=simple
User=postoffice
Group=postoffice
ExecStart=/usr/local/bin/mcfeely-authd
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mcfeely-authd
sudo systemctl start mcfeely-authd
```

## Configuration

### Database Configuration

Edit `/etc/mcfeely-authd.conf`:

```ini
[database]
dsn = postgresql://localhost/zoid6test
```

Or use environment variable:
```bash
export BBSENGINE6_DBNAME=zoid6test
```

### PAM Fallback

To enable/disable PAM fallback for unmigrated users:

```ini
[auth]
fallback_pam = yes   # Enable PAM fallback (default)
fallback_pam = no    # Require database entries only
```

## Usage

### Setting IMAP Password

Use the postoffice password management:

```python
from postoffice import member_password

# Set IMAP password (also sets SASL password)
member_password.set_personal_password(
    args=args,
    member_moniker="alice",
    password_type="inbound",
    password="imap_password_here",
    set_by_moniker="alice"
)
```

### Testing Authentication

```bash
# Test as user (reads password from stdin)
echo "password" | mcfeely-authd --test alice
# Output: OK: Authenticated via database
# or: NO: Invalid password
```

### View SASL Passwords

```python
from postoffice import sasl_password

# List all SASL passwords
passwords = sasl_password.list_sasl_passwords(args)

# Check if user has SASL password
exists = sasl_password.exists_sasl_password(args, "alice")
```

## Troubleshooting

### Socket Connection Failed

Check that mcfeely-authd is running:
```bash
ps aux | grep mcfeely-authd
ls -la /var/run/mcfeely-authd/mux
```

### Authentication Fails

1. Check mcfeely-authd logs:
   ```bash
   tail -f /var/log/mcfeely-authd.log
   ```

2. Verify database connection:
   ```bash
   psql -d zoid6test -c "SELECT * FROM postoffice.sasl_password LIMIT 5;"
   ```

3. Check saslauthd configuration:
   ```bash
   testsaslauthd -s imap -u alice -p password
   ```

### PAM Fallback Not Working

Ensure `/etc/pam.d/imap` has appropriate fallback rules. See `etc-postoffice/pam.d-saslauthd`.

## Migration

### From PAM to Database Auth

1. Ensure mcfeely-authd is running with `fallback_pam = yes`
2. Users can set their IMAP password via the postoffice system
3. Passwords are stored in `postoffice.sasl_password` table
4. PAM fallback is available during transition

### Verification

Test that both auth methods work:

```bash
# Database auth
echo "password" | mcfeely-authd --test alice

# PAM fallback (if configured)
testsaslauthd -s imap -u alice -p shell_password
```

## Security

- mcfeely-authd runs as `postoffice` user
- Socket permissions restrict access to saslauthd
- Passwords are stored as SHA-512 crypt hashes (not reversible)
- PAM fallback allows shell password access during migration

## Environment: zoid6test

All testing uses the `zoid6test` PostgreSQL database as configured in:
- Config file: `dsn = postgresql://localhost/zoid6test`
- Environment: `BBSENGINE6_DBNAME=zoid6test`
- Default in `mistermcfeely/src/postoffice/lib.py`