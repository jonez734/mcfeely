# Password System Startup CLI Guide

## Overview

The `postoffice-startup` command-line interface provides easy setup and management of the mistermcfeely password encryption system.

## Installation

The startup CLI is automatically available after installation:

```bash
# From bash wrapper (recommended)
./bin/postoffice-startup --help

# Or directly via Python
python -m postoffice.startup --help
```

## Commands

### 1. Check Setup (`--check`)

Verify that encryption key is properly configured.

```bash
python -m postoffice.startup --check
```

**Output Examples:**

**When key is set up correctly:**
```
Checking encryption key setup...

✓ POSTOFFICE_PASSWORD_KEY environment variable is set
✗ /etc/postoffice/password.key does not exist
✗ /home/user/.postoffice/password.key does not exist

✓ Encryption key successfully loaded
```

**When key is missing:**
```
Checking encryption key setup...

✗ POSTOFFICE_PASSWORD_KEY environment variable not set
✗ /etc/postoffice/password.key does not exist
✗ /home/user/.postoffice/password.key does not exist

✗ Could not load encryption key from any source

To set up encryption key, choose one method:

1. Environment Variable (Development/Testing):
   export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)

2. System-wide File (Single Server):
   KEY=$(openssl rand -base64 32)
   echo "$KEY" | sudo tee /etc/postoffice/password.key
   sudo chmod 600 /etc/postoffice/password.key
   sudo chown postoffice:postoffice /etc/postoffice/password.key

3. User File (Personal Development):
   mkdir -p ~/.postoffice
   openssl rand -base64 32 > ~/.postoffice/password.key
   chmod 600 ~/.postoffice/password.key

After setup, verify with:
   python -m postoffice.startup --check
```

### 2. Generate Key (`--generate`)

Create a new random encryption key.

```bash
python -m postoffice.startup --generate
```

**Output:**
```
Generating new encryption key...

New encryption key (base64 encoded):
ABCDefg1234567890abcdefg1234567890abcdefg1=

To use this key, run one of:

Option 1 - Environment variable (development):
export POSTOFFICE_PASSWORD_KEY="ABCDefg1234567890abcdefg1234567890abcdefg1="

Option 2 - System file (production):
echo "ABCDefg1234567890abcdefg1234567890abcdefg1=" | sudo tee /etc/postoffice/password.key
sudo chmod 600 /etc/postoffice/password.key
```

**Usage:**
```bash
# Generate and copy to clipboard (macOS)
python -m postoffice.startup --generate | grep "^[A-Za-z0-9+/=" | pbcopy

# Generate and use in environment
export POSTOFFICE_PASSWORD_KEY=$(python -m postoffice.startup --generate | grep "^[A-Za-z0-9+/=")
```

### 3. Install Key (`--install`)

Install encryption key to system location with proper permissions.

```bash
python -m postoffice.startup --install
```

**What it does:**
1. Generates a new random key
2. Creates `/etc/postoffice/` directory (via sudo)
3. Writes key to `/etc/postoffice/password.key` (via sudo)
4. Sets permissions to `0600` (read/write for owner only)
5. Sets ownership to `postoffice:postoffice` (if user exists)

**Requirements:**
- `sudo` access (will prompt for password)
- Internet access to run openssl
- Write permissions to `/etc`

**Example:**
```bash
$ python -m postoffice.startup --install
Installing encryption key to /etc/postoffice/password.key...
[sudo] password for user: ****

✓ Encryption key installed to /etc/postoffice/password.key
  Permissions set to 0600

Verify installation with:
  python -m postoffice.startup --check
```

### 4. Initialize System (`--init`)

Full password system initialization.

```bash
python -m postoffice.startup --init
```

**What it does:**
1. Validates encryption key is available
2. Checks password configuration (cipher/storage)
3. Optionally checks database schema

**Output:**
```
✓ Encryption key valid (32 bytes)
✓ Password system initialized: cipher=aes256gcm, storage=postgresql
✓ mistermcfeely startup complete
```

### 5. Verbose Output (`--verbose` or `-v`)

Add debug output to any command.

```bash
python -m postoffice.startup --check --verbose
python -m postoffice.startup --init -v
```

**Example:**
```bash
$ python -m postoffice.startup --init -v
Initializing password management system...
✓ Encryption key valid (32 bytes)
✓ Password system initialized: cipher=aes256gcm, storage=postgresql
✓ mistermcfeely startup complete
```

## Setup Methods

### Method 1: Environment Variable (Development)

**For temporary use or single session:**
```bash
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
python -m postoffice.startup --check
```

**For persistent use (add to ~/.bashrc or ~/.zshrc):**
```bash
# Generate key once
KEY=$(openssl rand -base64 32)

# Add to shell profile
echo 'export POSTOFFICE_PASSWORD_KEY="'$KEY'"' >> ~/.bashrc
source ~/.bashrc

# Verify
python -m postoffice.startup --check
```

**Pros:**
- Simple
- No sudo required
- Works everywhere

**Cons:**
- Visible in process list
- Lost when shell closes (unless in .bashrc)
- Visible in shell history

### Method 2: User File (Personal Development)

**Setup:**
```bash
mkdir -p ~/.postoffice
openssl rand -base64 32 > ~/.postoffice/password.key
chmod 600 ~/.postoffice/password.key
python -m postoffice.startup --check
```

**Verify permissions:**
```bash
ls -la ~/.postoffice/password.key
# Should show: -rw------- (0600)
```

**Pros:**
- Persistent across sessions
- Secure file permissions
- Per-user (doesn't affect other users)

**Cons:**
- Only works for current user
- Not suitable for services
- Requires explicit setup

### Method 3: System File (Single Server)

**Setup:**
```bash
python -m postoffice.startup --install
```

Or manually:
```bash
# Generate key
KEY=$(openssl rand -base64 32)

# Install to system
echo "$KEY" | sudo tee /etc/postoffice/password.key
sudo chmod 600 /etc/postoffice/password.key
sudo chown postoffice:postoffice /etc/postoffice/password.key

# Verify
python -m postoffice.startup --check
```

**Verify setup:**
```bash
sudo ls -la /etc/postoffice/password.key
# Should show: -rw------- (0600) postoffice:postoffice
```

**Pros:**
- Shared by all services
- Persistent across reboots
- Suitable for systemd services
- Can be backed up

**Cons:**
- Requires sudo
- Affects entire system
- Need to manage backups

### Method 4: With Systemd Service

**Create service file:**
```bash
sudo mkdir -p /etc/systemd/system/mistermcfeely.service.d
```

**Create environment file:**
```bash
sudo tee /etc/systemd/system/mistermcfeely.service.d/env.conf << 'EOF'
[Service]
EnvironmentFile=/etc/postoffice/password.key
