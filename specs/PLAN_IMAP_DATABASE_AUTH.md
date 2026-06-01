# Plan: IMAP Password Database Authentication

## Objective
Convert IMAP authentication from relying on shell account passwords (`/etc/shadow` via PAM) to using a PostgreSQL database lookup, allowing IMAP passwords to be independent of shell passwords.

## Architecture

```
Inbound (port 25/SMTP):
  External MTA → Postfix → LMTP → Cyrus IMAP → User reads via IMAP

Outbound (port 587/submission):
  User → Postfix → saslauthd → mcfeely-authd → PostgreSQL

IMAP (port 143/993):
  User → Cyrus IMAP → saslauthd → mcfeely-authd → PostgreSQL
```

**Key settings in etc-postfix/postfix/main.cf:**
```
mailbox_transport = lmtp:inet:localhost:7024  # Inbound delivery via TCP
```

**Cyrus LMTP listener (etc-postoffice/cyrus.conf):**
```
lmtp cmd="lmtpd" listen="localhost:7024" prefork=1
```

Both inbound and outbound use the same `postoffice.sasl_password` table for authentication.

## Current Architecture

```
IMAP Client → Cyrus IMAP → saslauthd → PAM → /etc/shadow (system passwords)
                 ↑
        Uses user's shell password
```

**Problems:**
- IMAP password must equal shell password
- SSH key-only users cannot access IMAP
- Password changes affect shell access
- Security risk: compromised IMAP = compromised shell

## Proposed Architecture

```
IMAP Client → Cyrus IMAP → saslauthd → mcfeely-authd → PostgreSQL
                                            ↓
                                     Falls back to PAM
                                     (for migration)
```

**Benefits:**
- IMAP password independent of shell password
- SSH key-only users can have IMAP access
- Fine-grained password management per service
- Backward compatibility via PAM fallback

## Implementation Plan

### Phase 1: Database Schema Changes

#### 1.1 Add `postoffice.sasl_password` Table
Store crypt()-hashed passwords for SASL verification.

**File:** `mistermcfeely/sql/sasl_password.sql`
```sql
-- SASL-authenticated password storage
-- Stores SHA-512 crypt hashes for PAM/saslauthd compatibility
-- Paired with AES-256-GCM encrypted passwords in engine.__member

CREATE TABLE IF NOT EXISTS postoffice.sasl_password (
    member_moniker citext PRIMARY KEY REFERENCES engine.__member(moniker) ON DELETE CASCADE,
    crypt_hash text NOT NULL,  -- SHA-512 crypt hash
    enabled boolean DEFAULT true,
    datecreated timestamp with time zone DEFAULT now(),
    dateupdated timestamp with time zone DEFAULT now(),
    updated_by text
);

GRANT SELECT ON postoffice.sasl_password TO postoffice;
GRANT SELECT ON postoffice.sasl_password TO imapd;
```

#### 1.2 Add Columns to `engine.__member`
**File:** `mistermcfeely/sql/member_mailbox_password.sql`
Add `inbound_password` and `outbound_password` columns if not present.

### Phase 2: Password Management Updates

#### 2.1 Update `member_password.py`
- When setting `inbound_password`, also generate SHA-512 crypt hash
- Store both: AES-256-GCM encrypted (for Python) + crypt hash (for Cyrus)
- Add `set_sasl_password()` function

#### 2.2 Create `sasl_password.py` Module
**File:** `mistermcfeely/src/postoffice/sasl_password.py`
```python
def set_sasl_password(args, member_moniker, password, updated_by):
    """Generate crypt hash and store in sasl_password table."""

def get_sasl_password(args, member_moniker):
    """Retrieve crypt hash for auth verification."""

def delete_sasl_password(args, member_moniker):
    """Remove SASL password (user must use PAM fallback)."""
```

### Phase 3: mcfeely-authd Daemon

#### 3.1 Create Daemon Structure
**Directory:** `mistermcfeely/src/mcfeely_authd/`

```
mcfeely_authd/
├── mcfeely_authd.py      # Main daemon (fork-per-request)
├── auth_verify.py        # Password verification logic
├── config.py             # Configuration management
├── __init__.py
└── protocol.py           # authdaemon protocol handling
```

#### 3.2 authdaemon Protocol
mcfeely-authd implements the authdaemon protocol expected by saslauthd:
```
# Request from saslauthd
AUTH <mechanism>\n
<length>\n
<username>\n
<password>\n

# Response
OK\n
# or
NO\n
# or
FAIL <reason>\n
```

#### 3.3 mcfeely-authd Configuration
**File:** `mistermcfeely/etc-postoffice/mcfeely-authd.conf`
```ini
[database]
dsn = postgresql://localhost/zoid6test
user = postoffice
password = 

[auth]
fallback_pam = yes
pam_service = imap

[socket]
path = /var/run/mcfeely-authd/mux

[logging]
level = INFO
syslog = yes
```

#### 3.4 Daemon Behavior
1. Listen on UNIX socket (`/var/run/mcfeely-authd/mux`)
2. For each request (fork-per-request):
   - Parse authdaemon protocol
   - Query `postoffice.sasl_password` for user's crypt hash
   - If found: verify password with `crypt.crypt()`
   - If not found OR fallback enabled: try PAM (saslauthd can do this)
   - Return OK/NO/FAIL
3. Handle SIGTERM/SIGHUP gracefully

### Phase 4: SASL Configuration Updates

#### 4.1 Update `etc-postoffice/saslauthd.conf`
**Current (commented out):**
```bash
# PREVIOUS: MECHANISMS = pam
# PREVIOUS: PAM_SERVICE = imap
```

**New:**
```bash
# Authentication mechanisms
# mcfeely-authd handles database lookup with PAM fallback
MECHANISMS = authdaemond

# Path to mcfeely-authd socket
AUTHDAEMOND_PATH = /var/run/mcfeely-authd/mux

# Fallback to PAM if user not in database
FLAGS = "-r"
```

#### 4.2 Update `etc-postoffice/imapd.conf`
**Current (commented out):**
```conf
# PREVIOUS: sasl_pwcheck_method: saslauthd
# PREVIOUS: saslauthd_path: /var/run/saslauthd/mux
```

**New:**
```conf
# SASL authentication
sasl_pwcheck_method: saslauthd
saslauthd_path: /var/run/saslauthd/mux
```

#### 4.3 Update `etc-postoffice/pam.d-imap`
**Current (commented out for reference):**
```
# PREVIOUS: auth        sufficient    pam_unix.so nullok try_first_pass
# PREVIOUS: auth        required      pam_deny.so
```

**New:**
```
# PAM fallback for users not yet migrated to database auth
auth        sufficient    pam_permit.so
auth        required      pam_deny.so
```

### Phase 5: Integration Tests

#### 5.1 Create `test_email_auth_integration.py`
**File:** `mistermcfeely/tests/test_email_auth_integration.py`

Tests to include:
1. `TestInboundEmailAuth` - IMAP login with database password
2. `TestOutboundEmailAuth` - SMTP submission with database password
3. `TestSharedMailboxAuth` - Per-member shared mailbox passwords
4. `TestPasswordFallback` - PAM fallback for unmigrated users
5. `TestPasswordRotation` - Changing passwords updates both formats
6. `TestAuthFailure` - Invalid password handling
7. `TestSSHKeyOnlyUser` - User with no shell password but has IMAP password

#### 5.2 Test Utilities
```python
def create_test_user_with_imap_password(moniker, imap_password):
    """Create test user with both encrypted and hashed passwords."""

def verify_imap_login(host, port, user, password):
    """Verify IMAP authentication succeeds."""

def verify_imap_login_fails(host, port, user, wrong_password):
    """Verify IMAP authentication fails with wrong password."""
```

### Phase 6: Documentation Updates

#### 6.1 Update `specs/MCFEELY_CYRUS_IMAP.md`
- Add section: "Authentication Architecture"
- Document mcfeely-authd daemon
- Document migration path from PAM

#### 6.2 Update `specs/PASSWORD_SYSTEMS_SUMMARY.md`
- Add "System 3: SASL Password Hashes (for Cyrus auth)"
- Document dual-storage approach
- Add migration guide

#### 6.3 Create `config/MCFEELY_AUTH_SETUP.md`
- Installation guide for mcfeely-authd
- Configuration reference
- Troubleshooting guide

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `sql/sasl_password.sql` | Schema for SASL password table |
| `src/postoffice/sasl_password.py` | Password management for SASL auth |
| `src/mcfeely_authd/__init__.py` | Daemon package |
| `src/mcfeely_authd/mcfeely_authd.py` | Main daemon |
| `src/mcfeely_authd/auth_verify.py` | Password verification |
| `src/mcfeely_authd/config.py` | Configuration |
| `src/mcfeely_authd/protocol.py` | authdaemon protocol |
| `etc-postoffice/mcfeely-authd.conf` | Daemon config |
| `tests/test_email_auth_integration.py` | Integration tests |
| `config/MCFEELY_AUTH_SETUP.md` | Setup documentation |

### Modified Files
| File | Change |
|------|--------|
| `src/postoffice/member_password.py` | Add SASL hash generation |
| `src/postoffice/imap_lib.py` | No changes needed |
| `src/postoffice/password_auth.py` | No changes needed |
| `etc-postoffice/saslauthd.conf` | Switch to authdaemond |
| `etc-postoffice/imapd.conf` | Comment previous config |
| `etc-postoffice/pam.d-imap` | PAM fallback config |
| `specs/MCFEELY_CYRUS_IMAP.md` | Document new architecture |
| `specs/PASSWORD_SYSTEMS_SUMMARY.md` | Add SASL password section |
| `Makefile` | Add mcfeely-authd targets |

### Commented Out (for reference)
| File | Line | Original |
|------|------|----------|
| `etc-postoffice/saslauthd.conf` | 15 | `MECHANISMS = pam` |
| `etc-postoffice/saslauthd.conf` | 23 | `PAM_SERVICE = imap` |
| `etc-postoffice/imapd.conf` | 46 | `sasl_pwcheck_method: saslauthd` |
| `etc-postoffice/pam.d-imap` | 6 | `pam_unix.so` line |

## Auth Mechanism Alternatives (Documented)

### Alternative 1: auxprop with Custom Plugin
See commented config in `etc-postoffice/imapd.conf` for direct auxprop approach.

### Alternative 2: SQL auxprop
See commented config in `etc-postoffice/saslauthd.conf` for libsasl2-modules-sql approach.

## Postfix SMTP Configuration

For outbound email (SMTP submission on port 587), configure Postfix to use the same saslauthd/mcfeely-authd chain:

```bash
# /etc/postfix/main.cf
smtpd_sasl_auth_enable = yes
smtpd_sasl_type = cyrus
smtpd_sasl_path = smtpd
smtpd_sasl_security_options = noanonymous
smtpd_tls_security_level = encrypt
```

Both IMAP and SMTP use the same `postoffice.sasl_password` table for authentication. See `etc-postfix/postfix/main.cf` for the staged configuration.

## Testing Strategy

1. **Unit Tests** - Test password hashing, verification functions
2. **Integration Tests** - Test full auth flow with mcfeely-authd
3. **End-to-End Tests** - Test IMAP login via telnet/openssl
4. **Migration Tests** - Test PAM fallback for existing users

## Rollout Plan

1. **Phase 1:** Add schema, update password management
2. **Phase 2:** Deploy mcfeely-authd in parallel with PAM
3. **Phase 3:** Switch saslauthd to authdaemond
4. **Phase 4:** Migrate users to database auth
5. **Phase 5:** Disable PAM fallback (optional)

## Environment: zoid6test

All testing uses the `zoid6test` PostgreSQL database:
- Default connection: `pgsql:host=127.0.0.1;port=5432;dbname=zoid6test`
- Configured via `BBSENGINE6_DBNAME=zoid6test`
- Test users created via `generate_test_accounts.py`