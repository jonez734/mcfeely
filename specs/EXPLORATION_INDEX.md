# Mistermcfeely Project Exploration - Document Index

This index provides a roadmap to all analysis documents created during the exploration of the Mistermcfeely project structure.

## Overview Documents

### 1. **PROJECT_ANALYSIS.md** (Comprehensive Analysis)
   **Size:** 22 KB | **Type:** Deep-dive technical analysis
   
   Contains:
   - Executive summary of the project
   - Codebase organization and component breakdown
   - User/account management patterns
   - Password and credential storage mechanisms
   - Complete database schema documentation
   - Authentication and authorization flows
   - Security best practices analysis
   - Recommendations for future enhancements
   
   **Best for:** Understanding the complete architecture, security posture, and design decisions
   
   **Key sections:**
   - Section 1: Codebase organization with LOC breakdown
   - Section 2: User/account management with FK relationships
   - Section 3: Password storage, encryption, and usage patterns
   - Section 4: Database schema with all tables and examples
   - Section 5: Authentication and authorization flows
   - Section 6: Summary and recommendations

### 2. **QUICK_REFERENCE.md** (Quick Lookup Guide)
   **Size:** 12 KB | **Type:** Reference manual
   
   Contains:
   - Project at a glance summary
   - Key files and their purposes
   - Password and credential handling quick summary
   - User account model overview
   - Database tables quick lookup
   - Event types and flows
   - Common operations with SQL examples
   - Important design patterns explained
   - Testing and validation guide
   - Troubleshooting tips
   
   **Best for:** Quick lookups, understanding how to perform common operations, diagnosing issues
   
   **Key sections:**
   - Key files with LOC and functions
   - Password/credential handling cheat sheet
   - Database tables summary (not detailed)
   - Event flow diagram
   - Common SQL operations
   - Design patterns overview
   - Troubleshooting checklist

### 3. **EXPLORATION_INDEX.md** (This Document)
   **Size:** < 5 KB | **Type:** Navigation guide
   
   Contains:
   - Overview of all analysis documents
   - Navigation guide to find specific information
   - Quick reference to document sections
   - File locations and recommendations

---

## Document Navigation Guide

### Looking for information about... Use this document:

| Question | Document | Section |
|----------|----------|---------|
| How are passwords stored? | PROJECT_ANALYSIS | Section 3: Password & Credential Storage |
| How are users managed? | PROJECT_ANALYSIS | Section 2: User/Account Management |
| What's the database schema? | PROJECT_ANALYSIS | Section 4: Database Schema & Data Models |
| How do authentication flows work? | PROJECT_ANALYSIS | Section 5: Authentication & Authorization |
| Quick password handling overview | QUICK_REFERENCE | Password & Credential Handling |
| How to add a mailbox? | QUICK_REFERENCE | Common Operations |
| File descriptions and purposes | QUICK_REFERENCE | Key Files & What They Do |
| Troubleshoot an issue | QUICK_REFERENCE | Troubleshooting |
| Design patterns explained | QUICK_REFERENCE | Important Design Patterns |
| Complete system architecture | PROJECT_ANALYSIS | Section 1: Codebase Organization |
| Event routing and notification | PROJECT_ANALYSIS | Section 4: Event Types & Payloads |
| Testing and validation | QUICK_REFERENCE | Testing & Validation |

---

## Key Findings Summary

### Users & Accounts
- **Source:** bbsengine6's `engine.__member` table
- **Identified by:** `moniker` (string) or `id` (bigint)
- **Relations:**
  - Mailbox ownership: `postoffice.mailbox_password`
  - Message claims: `actor_moniker` in events
  - Notifications: `recipient_moniker` in routing rules
  - Audit trail: `createdbymoniker`, `updatedbymoniker`

### Password Storage
- **Table:** `postoffice.mailbox_password`
- **Protection:** ENCRYPTED using `util.getencryptedpassword()` from bbsengine6
- **Database:** PostgreSQL TEXT field (never plaintext)
- **Access Control:** sysop role only
- **Usage:** Decrypted on-demand for IMAP authentication

### Credential Types
1. **Mailbox passwords** - Encrypted in PostgreSQL
2. **IMAP server credentials** - Via bbsengine6 args object
3. **Obfuscation secret** - Environment variable or DB password
4. **Member passwords** - Handled by bbsengine6 auth system

### Database Tables (6 Core)
1. `postoffice.__address` - Define per-user mailboxes
2. `postoffice.mailbox_password` - User credentials (ENCRYPTED)
3. `postoffice.__message` - Message claim tracking
4. `postoffice.virtual` - Virtual mailbox rules
5. `postoffice.message_routing` - Event routing rules
6. `postoffice.mailbox` (view) / `postoffice.__mailbox` (table) - Per-mailbox settings
7. `postoffice.mailbox_member` (view) / `postoffice.__mailbox_member` (table) - Per-member overrides

### Authentication Flows (3 Levels)
1. **System-level:** bbsengine6 member authentication
2. **IMAP server:** Service account credentials
3. **Mailbox access:** Per-user encrypted credentials

### Authorization Model
- **RBAC:** sysop, web, term, imapd roles
- **Functional:** Event tracking with actor_moniker
- **Database:** GRANT/REVOKE per role and table

---

## Design Patterns

### 1. CONN_POOL_PATTERN
Functions accept `**kwargs` with 'conn' or 'pool' parameters for flexible connection management.
**Where:** All modules, especially `message_client.py`, `imap_monitor.py`

### 2. Flag Obfuscation
Claim flags use HMAC-SHA256(moniker, secret) to prevent username exposure in logs.
**Where:** `message_client.py:obfuscate_moniker()`

### 3. Thread-Safe Monitoring
Background daemon with `threading.Lock()` for state protection.
**Where:** `imap_monitor.py:IMAPMonitor` class

### 4. Event-Driven Routing
Pattern-based matching with SQL LIKE for flexible subscriptions.
**Where:** `message_client.py:get_routing_rules()`

---

## File Locations

```
Main Analysis:
  /home/opencode/data/work/mistermcfeely/PROJECT_ANALYSIS.md (22 KB)
  /home/opencode/data/work/mistermcfeely/QUICK_REFERENCE.md (12 KB)
  /home/opencode/data/work/mistermcfeely/EXPLORATION_INDEX.md (this file)

Source Code:
  /home/opencode/data/work/mistermcfeely/src/postoffice/
    - imap_lib.py (295 lines)
    - imap_monitor.py (443 lines)
    - message_client.py (443 lines)
    - imap_client.py (291 lines)
    - mailbox.py (264 lines)
    - startup.py (186 lines)
    - virtual.py (193 lines)
    - lib.py (115 lines)

Database Schema:
  /home/opencode/data/work/mistermcfeely/sql/
    - mailbox.sql
    - message.sql
    - virtual.sql
    - message_routing.sql
    - mailbox_view.sql
    - schema.sql

Tests:
  /home/opencode/data/work/mistermcfeely/tests/
    - test_imap_lib.py
    - test_imap_monitor.py
    - test_message_client.py
    - test_message_client_integration.py

Existing Documentation:
  /home/opencode/data/work/mistermcfeely/README.md
  /home/opencode/data/work/mistermcfeely/IMPLEMENTATION_SUMMARY.md
  /home/opencode/data/work/mistermcfeely/CONN_POOL_PATTERN.md
```

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total Source LOC | 2,638 |
| Core Modules | 8 |
| Database Tables | 6 |
| Test Cases | 93 |
| Pass Rate | 100% |
| Database Roles | 4 (web, term, sysop, imapd) |
| Event Types | 5 |
| Python Version | 3.9+ (compatible with bbsengine6) |

---

## How to Use This Documentation

### For System Administrators
1. Read **QUICK_REFERENCE.md** - Common Operations section
2. Reference **PROJECT_ANALYSIS.md** - Section 3 for password handling
3. Use troubleshooting guide when issues arise

### For Developers
1. Start with **PROJECT_ANALYSIS.md** - Section 1 for codebase overview
2. Read **QUICK_REFERENCE.md** - Design Patterns section
3. Refer to specific modules in `/src/postoffice/` for implementation details

### For Security Auditors
1. Read **PROJECT_ANALYSIS.md** - Sections 3 and 5 (Credentials & Auth)
2. Review **PROJECT_ANALYSIS.md** - Section 6 (Summary & Recommendations)
3. Examine SQL schema files in `/sql/` for permission grants

### For DevOps/Operations
1. Read **QUICK_REFERENCE.md** - Key Files section
2. Check troubleshooting guide for common issues
3. Refer to database operations in **PROJECT_ANALYSIS.md** - Section 4

### For Security Enhancement
1. Review **PROJECT_ANALYSIS.md** - Section 6 for recommendations
2. Check credential handling in Section 3
3. Review authentication flows in Section 5

---

## Key Takeaways

1. **Users:** Integrated with bbsengine6's member system (engine.__member)
2. **Passwords:** Encrypted using bbsengine6's util.getencryptedpassword()
3. **Storage:** postoffice.mailbox_password table in PostgreSQL
4. **Access Control:** RBAC via database roles (sysop, web, term, imapd)
5. **Architecture:** Event-driven with pattern-based routing
6. **Quality:** Production-ready with comprehensive test coverage
7. **Security:** Best practices for credential handling, optional flag obfuscation

---

## Document Maintenance

These documents were generated on **May 20, 2026** based on:
- Source code analysis of 8 Python modules
- SQL schema inspection (6 tables)
- Test suite review (93 tests)
- Integration with bbsengine6 patterns
- README and implementation summaries

For updates, refer to:
- `/home/opencode/data/work/mistermcfeely/IMPLEMENTATION_SUMMARY.md`
- `/home/opencode/data/work/mistermcfeely/README.md`

---

**Navigation:** For detailed information, see [PROJECT_ANALYSIS.md](./PROJECT_ANALYSIS.md) for deep dives or [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) for quick lookups.
