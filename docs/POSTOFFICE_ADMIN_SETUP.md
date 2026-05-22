# Postoffice Admin Setup for Non-Privileged Users

## Problem
A normal user (e.g., `jam`) needs to run postoffice CLI commands like `python -m postoffice accounts` to create mailboxes and manage accounts. This requires:
1. Access to the encryption key for decrypting passwords
2. Read access to `/etc/postoffice/` config files
3. Database access credentials

## Solution

### 1. Copy Encryption Key to User's Home

The encryption key at `/etc/postoffice/password.key` needs to be accessible in the user's home directory:

```bash
sudo cp /etc/postoffice/password.key /home/<username>/.postoffice/password.key
sudo chown <username>:<username> /home/<username>/.postoffice/password.key
chmod 600 /home/<username>/.postoffice/password.key
```

### 2. Grant Read Access to Config Files

Config files in `/etc/postoffice/` need to be readable:

```bash
sudo chgrp <username> /etc/postoffice/*.conf
sudo chmod 640 /etc/postoffice/*.conf
```

### 3. Verify Database Credentials

Ensure the user has database credentials configured (via config file, env vars, or `~/.pgpass`).

## Usage

```bash
POSTOFFICE_PASSWORD_KEY="$(cat ~/.postoffice/password.key)" \
python -m postoffice accounts --issuperuser --loginid <username>
```

## Alternative: System Key with Group Permissions

Instead of copying the key, make the system key readable by the user's group:

```bash
sudo chgrp <username> /etc/postoffice/password.key
sudo chmod 640 /etc/postoffice/password.key
```

This is more secure (single key location) but requires filesystem changes.

## Cyrus Admin TUI

The `python -m postoffice accounts` command launches an interactive TUI:

```bash
POSTOFFICE_PASSWORD_KEY="$(cat ~/.postoffice/password.key)" \
python -m postoffice accounts --issuperuser --loginid <username>
```

**Menu Options:**
- `(a)ccounts` - List all user accounts
- `(c)reate account` - Create new account with inbound/outbound passwords
- `(s)hared mailboxes` - List shared mailboxes with member counts
- `(m)anage mailbox` - View members, create mailboxes, set passwords
- `(x)it` / `(q)uit` - Exit

**Database:** Uses `zoid6test` by default.

**Required Permissions:** `issuperuser` and `loginid` flags.
