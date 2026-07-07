# etc-postfix - Postfix Configuration Staging

Staged configuration for Postfix with LMTP delivery to Cyrus IMAP.

## Directory Structure

```
etc-postfix/
├── Makefile
├── README.md
├── postfix/
│   ├── main.cf           # Postfix main config (LMTP to Cyrus)
│   ├── master.cf         # Service definitions
│   ├── virtual          # Virtual alias mappings
│   ├── aliases          # Local alias database
│   └── sieve/
    └── example.script    # Example user sieve script
```

## Components

| Component | Config Location | Purpose |
|-----------|-----------------|---------|
| Postfix | `postfix/` | Mail transport, LMTP delivery to Cyrus |
| Cyrus | `../etc-postoffice/` | IMAP, LMTP, authentication |
| Sieve | `../etc-postoffice/` | Mail filtering (managed via imapd.conf) |

## Address Domains

Email addresses are managed via the generic `address_manager` system:

1. **PostgreSQL** (primary): Dynamic pgsql.cf files per domain
2. **Static file** (fallback): Commented out in main.cf

### Database Schema

**Tables:** `mistermcfeely.address_domain` and `mistermcfeely.address`

```sql
-- address_domain: e.g., 'projects.zoidtechnologies.com'
CREATE TABLE mistermcfeely.address_domain (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    enabled     BOOLEAN DEFAULT true,
    datecreated TIMESTAMPTZ DEFAULT now(),
    createdby   TEXT,
    dateupdated TIMESTAMPTZ DEFAULT now(),
    updatedby   TEXT
);

-- address: e.g., 'webmaster@projects.zoidtechnologies.com'
CREATE TABLE mistermcfeely.address (
    id          BIGSERIAL PRIMARY KEY,
    domain_id   BIGINT REFERENCES mistermcfeely.address_domain(id),
    local_part  TEXT NOT NULL,
    destination TEXT NOT NULL,
    kind        TEXT CHECK (kind IN ('imap', 'mailman', 'both')),
    description TEXT,
    enabled     BOOLEAN DEFAULT true,
    datecreated TIMESTAMPTZ DEFAULT now(),
    createdby   TEXT,
    dateupdated TIMESTAMPTZ DEFAULT now(),
    updatedby   TEXT,
    UNIQUE (domain_id, local_part)
);
```

### Address Kinds

| Kind | Description |
|------|-------------|
| `imap` | Deliver to IMAP mailbox |
| `mailman` | Deliver to Mailman mailing list |
| `both` | Deliver to both |

### Destination Validation

When creating/updating addresses, the system validates destinations:

1. **IMAP destinations** (`user@domain`): Check if mailbox exists in `postoffice.mailbox`
2. **Mailman destinations** (`listname`): Check if list exists

**If destination not found:**
- Prompt to create it automatically
- If user declines, abort the operation
- Default mail location: `INBOX` (can be changed by user or postmaster)

### Postfix Configuration

Each domain generates a pgsql.cf file at `/etc/postfix/{domain}_pgsql.cf`:

```
dbname = zoid6
user = postfix
password = <password>
host = 127.0.0.1
port = 5432

query = SELECT destination FROM mistermcfeely.address a
        JOIN mistermcfeely.address_domain d ON a.domain_id = d.id
        WHERE a.local_part = '%u' AND d.name = 'projects.zoidtechnologies.com'
          AND a.enabled = true AND d.enabled = true
```

### Deployment

```bash
cd etc-postfix
make install-system  # Deploy configs to /etc/postfix
make postmap        # Generate hash database files
systemctl reload postfix
```

### Management

Use the address manager TUI:

```bash
python -m postoffice addresses --issuperuser
```

Menu options:
- **(D)omains** - Manage email domains
- **(A)ddresses** - Manage addresses within domains
- **(S)ettings** - Generate postfix pgsql.cf configs
- **(R)eload** - Reload postfix after config changes

See `008_address_manager.sql` for full schema.

## LMTP Delivery Flow

```
Internet → Postfix SMTP → LMTP socket → Cyrus lmtpd → Mailbox
```

**Key setting in postfix/main.cf:**
```
mailbox_transport = lmtp:unix:/run/cyrus/socket/lmtp
```

## Legacy Schema

The old `mistermcfeely.project` table (007_projects.sql) is unused. See `007_projects.sql` for reference.

## Cyrus Configuration

Cyrus configs are in `../etc-postoffice/`:
- `cyrus.conf` - Master process and services
- `imapd.conf` - IMAP protocol and feature settings
- `cyrus-imapd.conf` - Core daemon settings
- `saslauthd.conf` - Authentication
- PAM configs for IMAP/saslauthd

See `../etc-postoffice/Makefile` for deployment targets.
