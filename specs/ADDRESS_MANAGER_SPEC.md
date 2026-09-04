# Address Manager Specification

## Overview

The address manager provides a generic system for managing email addresses across multiple domains (e.g., `projects.zoidtechnologies.com`, `members.zoidtechnologies.com`).

## Features

- Multiple domain support
- Domain management (CRUD)
- Address management (CRUD)
- Destination validation with auto-creation
- Postfix pgsql.cf config generation
- Postfix reload integration

## Database Schema

### address_domain Table

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| name | text | Domain name (e.g., `projects.zoidtechnologies.com`) |
| description | text | Human-readable description |
| enabled | boolean | Whether domain is active |
| datecreated | timestamptz | Creation timestamp |
| createdby | text | Creator moniker |
| dateupdated | timestamptz | Last update timestamp |
| updatedby | text | Last updater moniker |

### address Table

| Column | Type | Description |
|--------|------|-------------|
| id | bigserial | Primary key |
| domain_id | bigint | FK to address_domain |
| local_part | text | Local part (e.g., `jam`) |
| destination | text | Delivery target (e.g., `jam@zoidtechnologies.com`) |
| kind | text | `imap`, `mailman`, or `both` |
| description | text | Human-readable description |
| enabled | boolean | Whether address is active |
| datecreated | timestamptz | Creation timestamp |
| createdby | text | Creator moniker |
| dateupdated | timestamptz | Last update timestamp |
| updatedby | text | Last updater moniker |

**Full address format:** `{local_part}@{domain.name}`

## Address Kinds

| Kind | Description | Example Destination |
|------|-------------|---------------------|
| `imap` | Deliver to IMAP mailbox | `jam@zoidtechnologies.com` |
| `mailman` | Deliver to Mailman list | `listname` |
| `both` | Deliver to both | `jam@zoidtechnologies.com` + `listname` |

## Destination Validation

### Flow

```
1. User enters destination (e.g., jam@zoidtechnologies.com)
2. System checks if destination exists:
   - IMAP: Query postoffice.__address table
   - Mailman: Check Mailman list exists (or skip if not configured)
3. If destination NOT found:
   a. Display warning message
   b. Prompt: "Create mailbox '<destination>'? [Y/N]"
   c. If user declines: Abort Create/Update operation
   d. If user accepts:
      - Prompt for maillocation (default: INBOX)
      - Create mailbox in postoffice.__address
      - If creation fails: Abort operation
4. If destination found: Continue with Create/Update
```

### Validation Rules

| Field | Validation |
|-------|------------|
| local_part | Alphanumeric + `-_.` only, no `@`, max 64 chars |
| destination | Must be valid format for kind |
| kind | One of `imap`, `mailman`, `both` |

## TUI Commands

All TUI modules use functional style: `run(args, moniker, pool=None, **kwargs)` → int.

### Main Menu

```
Address Manager
├── (D)omains   → Domain CRUD (address_domain.run)
├── (A)ddresses → Address CRUD (select domain first, address.run)
├── (S)ettings  → Generate postfix configs
├── (R)eload    → systemctl reload postfix
└── (Q)uit
```

### Domain Menu

```
Choose action:
├── (L)ist     → List all domains
├── (A)dd      → Add new domain
├── (C)hange   → Edit domain description
├── (I)nfo     → Show domain details
├── (X) maint  → Toggle enabled/disabled
└── (Q)uit     → Return to main menu
```

### Address Menu

```
Choose action:
├── (L)ist     → List addresses for domain
├── (A)dd      → Add new address
├── (C)hange   → Edit address
├── (E)nable   → Toggle enabled/disabled
├── (D)elete   → Delete address
├── (I)nfo     → Show address details
└── (Q)uit     → Return to main menu
```

## Postfix Integration

### Config Generation

Each domain generates a pgsql.cf file:

**Filename:** `/etc/postfix/{domain}_pgsql.cf`

**Contents:**
```postfix
# {domain_name} - Postfix PostgreSQL lookup
dbname = {databasename}
user = postfix
password = {password}
host = {host}
port = {port}

query = SELECT destination FROM mistermcfeely.address a
        JOIN mistermcfeely.address_domain d ON a.domain_id = d.id
        WHERE a.local_part = '%u' AND d.name = '{domain_name}'
          AND a.enabled = true AND d.enabled = true
```

### main.cf Integration

```postfix
virtual_alias_maps = 
    pgsql:/etc/postfix/projects_zoidtechnologies_com_pgsql.cf
    hash:/etc/postfix/virtual
```

## File Structure

```
mistermcfeely/
├── sql/
│   ├── 007_projects.sql      # Legacy (unused)
│   └── 008_address_manager.sql # Current schema
├── src/postoffice/tui/
│   ├── address_manager.py    # Main menu
│   ├── address_domain.py     # Domain CRUD
│   └── address.py           # Address CRUD with validation
└── etc-postfix/
    └── postfix/
        ├── projects_pgsql.cf # Legacy (unused)
        └── projects_static   # Legacy (unused)
```

## Usage

```bash
# Run address manager
python -m postoffice addresses --issuperuser

# Commands
# (D)omains   - Manage domains
# (A)ddresses - Manage addresses
# (S)ettings  - Generate postfix configs
# (R)eload    - Reload postfix
```

## Migration Path

1. Run `008_address_manager.sql` to create schema
2. Existing `007_projects.sql` data can be migrated to new schema
3. Old tables (`mistermcfeely.project`) left as reference (unused)

## Future Enhancements

- [ ] Mailman list creation integration
- [ ] Bulk import/export of addresses
- [ ] Address templates per domain
- [ ] Automatic postfix config regeneration on address change
