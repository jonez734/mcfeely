# Encryption Key Management

## Critical: Single Key for All

The **POSTOFFICE_PASSWORD_KEY must be identical** across all members, all servers, and all deployments.

All member passwords encrypted with same key:
- Alice's inbound password
- Alice's outbound password
- Bob's inbound password
- Carol's shared mailbox password
- etc.

All decrypted using SAME POSTOFFICE_PASSWORD_KEY

## Why One Key?

### 1. All Passwords in Same Database

All member passwords stored in:
- engine.__member table (personal passwords)
- postoffice.member_mailbox_password table (shared mailbox passwords)

Single key needed to encrypt/decrypt all.

### 2. Cross-Server Communication

IMAP server needs to decrypt passwords encrypted by web admin:

Web Admin Server          IMAP Server
1. User sets password
2. Encrypt with KEY  ----> 4. IMAP fetches from DB
3. Store in DB            5. Decrypt with KEY (MUST be same!)

### 3. Member Access

Same member password used by different systems:
- System A (IMAP): Encrypt/Decrypt with KEY
- System B (Web):  Encrypt/Decrypt with KEY
- System C (SMTP): Encrypt/Decrypt with KEY

All three must use SAME key

## Generating the Key

Generate once, use everywhere:

  KEY=$(openssl rand -base64 32)
  echo "$KEY"
  # Output: ABCDefg1234567890abcdefg1234567890abcdefg1=

IMPORTANT:
- Generate this ONCE
- Use this EVERYWHERE
- Never regenerate unless key rotation planned

## Storing the Key

Option 1: Environment Variable (development)
  export POSTOFFICE_PASSWORD_KEY="your_key_here"

Option 2: System File (production - recommended)
  echo "$KEY" | sudo tee /etc/postoffice/password.key
  sudo chmod 600 /etc/postoffice/password.key

Option 3: User File (personal development)
  mkdir -p ~/.postoffice
  echo "$KEY" > ~/.postoffice/password.key
  chmod 600 ~/.postoffice/password.key

## Distributing to Multiple Servers

### Scenario: 3-Server Setup

  KEY SERVER (where key is generated)
    |
    +-> IMAP Server 1 (mail1.example.com)
    +-> IMAP Server 2 (mail2.example.com)
    +-> Web Admin Server (admin.example.com)

### Simple Distribution Script

  #!/bin/bash
  KEY=$(openssl rand -base64 32)
  SERVERS="mail1.example.com mail2.example.com admin.example.com"

  for server in $SERVERS; do
    echo "Deploying to $server..."
    ssh root@$server "mkdir -p /etc/postoffice"
    echo "$KEY" | ssh root@$server "tee /etc/postoffice/password.key > /dev/null"
    ssh root@$server "chmod 600 /etc/postoffice/password.key"
    echo "  ✓ Deployed"
  done

## Verifying Key Consistency

### Quick Check

  KEY=$(cat /etc/postoffice/password.key)
  
  for server in mail1 mail2 admin; do
    REMOTE=$(ssh root@$server "cat /etc/postoffice/password.key")
    if [ "$KEY" = "$REMOTE" ]; then
      echo "✓ $server: Key matches"
    else
      echo "✗ $server: Key MISMATCH!"
    fi
  done

### Application Test

  python -m postoffice startup-check --verbose

All servers should show:
  ✓ Encryption key successfully loaded

## Key Rotation (Advanced)

If you must rotate the key:

1. BACKUP database and key first
2. Decrypt all passwords with old key
3. Re-encrypt with new key
4. Update /etc/postoffice/password.key on all servers
5. Test thoroughly

This is complex - avoid unless necessary!

## Backup and Recovery

### Backup Procedure

  # Backup the key (MOST IMPORTANT!)
  sudo cp /etc/postoffice/password.key /backup/postoffice-key.backup
  sudo chmod 400 /backup/postoffice-key.backup
  
  # Backup database
  pg_dump postoffice > /backup/postoffice_$(date +%Y%m%d).sql
  
  # Compress and store securely
  tar czf /backup/postoffice_backup_$(date +%Y%m%d).tar.gz \
    /backup/postoffice-key.backup \
    /backup/postoffice_*.sql

### Recovery Procedure

If system crashes:

  # 1. Restore database
  psql postoffice < /backup/postoffice_20230515.sql
  
  # 2. Restore key
  sudo cp /backup/postoffice-key.backup /etc/postoffice/password.key
  sudo chmod 600 /etc/postoffice/password.key
  
  # 3. Verify
  python -m postoffice startup-check

## Security Best Practices

DO:
  ✓ Generate key once, use everywhere
  ✓ Store in /etc/postoffice/password.key on servers
  ✓ Use file permissions 0600
  ✓ Back up key securely
  ✓ Use same key across all servers
  ✓ Use environment variable for containers
  ✓ Audit key access regularly
  ✓ Plan key rotation yearly

DON'T:
  ✗ Commit key to version control
  ✗ Log the key
  ✗ Share via email
  ✗ Use different keys across servers
  ✗ Change key without plan
  ✗ Lose backup of key
  ✗ Grant world-readable permissions
  ✗ Regenerate key unnecessarily

## Troubleshooting

### Key Mismatch Between Servers

Error: Cannot decrypt password on server B

Cause: Different keys on different servers

Fix:
  # Verify keys match
  ssh root@mail1 "cat /etc/postoffice/password.key" > /tmp/key1
  ssh root@mail2 "cat /etc/postoffice/password.key" > /tmp/key2
  
  diff /tmp/key1 /tmp/key2  # Should be identical
  
  # If different, redeploy key to all servers

### Lost Key

If key is lost, ALL encrypted passwords are unreadable!

Prevention:
  - Always backup key
  - Keep multiple backups
  - Test recovery procedure

### Key File Corrupted

Check file:
  file /etc/postoffice/password.key
  # Should show: ASCII text
  
  cat /etc/postoffice/password.key | base64 -d | wc -c
  # Should show: 32

## Summary

Number of keys:         1 (single)
Scope:                  All members, all servers
Length:                 32 bytes (base64 encoded)
Generation:             Once, never repeat
Distribution:           Identical to all servers
Storage:                /etc/postoffice/password.key or env var
Permissions:            0600 (owner only)
Backup:                 Critical - store securely
Rotation:               Plan carefully if needed
