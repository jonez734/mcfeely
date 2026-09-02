# Postoffice Documentation Index

Complete exploration and documentation of the postoffice module from mistermcfeely.

## Documentation Files

### 1. POSTOFFICE_README.md (603 lines, 16 KB)
**Master overview document - START HERE**

Navigation guide to all documentation and quick answers.

**Contains:**
- What is postoffice
- Core concepts (8 key ideas)
- Architecture layers
- Common operations (copy-paste code)
- CLI commands
- Security considerations
- Deployment checklist
- Troubleshooting guide
- Related documentation references

**Best for:** Getting oriented, finding answers quickly

---

### 2. POSTOFFICE_EXPLORATION_SUMMARY.md (806 lines, 23 KB)
**Complete technical reference - COMPREHENSIVE**

In-depth exploration of every component, function, and relationship.

**Contains:**
- Module structure and directory layout
- Startup submodule and KEY usage (section 2)
  - Key sources and properties
  - Key functions
  - CLI entry point
  - Module integration
- IMAP service and mailbox structure (section 3)
  - Mailbox types
  - IMAP client operations
  - IMAP library
  - IMAP monitor
- Existing TUI components (section 4)
- Module invocation patterns (section 5)
- Password management architecture (section 6)
  - Personal passwords
  - Shared mailbox passwords
  - Authentication with fallback
  - Encryption (moved to bbsengine6)
- Events and notifications (section 7)
- Audit and logging (section 8)
- Connection pool pattern (section 9)
- Key component relationships (section 10)
- Deployment considerations (section 11)
- Summary table of all components

**Best for:** Understanding the full system, detailed research, architecture decisions

---

### 3. POSTOFFICE_ARCHITECTURE_DIAGRAM.md (577 lines, 28 KB)
**Visual architecture and data flows - DIAGRAMS**

System architecture with visual diagrams, examples, and dependency maps.

**Contains:**
- System architecture overview (layered diagram)
- Data flow examples:
  - Setting a member's shared mailbox password
  - Alice accessing shared mailbox via IMAP
  - Monitoring detects new message
  - Member claims a message
- Key design patterns (6 patterns explained)
- Module dependencies (complete dependency graph)

**Best for:** Understanding system architecture, seeing how pieces fit together, understanding data flows

---

### 4. POSTOFFICE_QUICK_REFERENCE.md (727 lines, 16 KB)
**Quick lookup and code examples - DEVELOPERS**

API reference and copy-paste code snippets.

**Contains:**
- File locations tree
- Key concepts at a glance
- Encryption key management (getting key)
- Password types (personal vs shared)
- IMAP operations
  - Getting credentials
  - Connecting
  - Message operations
- Events
  - Event types
  - Firing events
- Background monitoring
- TUI components
- Database tables (schema)
- Logging (audit log, auth failure)
- Claim flag obfuscation
- Module integration
- CLI commands
- Connection pool pattern
- Common workflows
- Encryption details
- Debugging tips

**Best for:** Quick lookup while developing, API reference, code examples

---

## Quick Start

### I want to...

**Understand what postoffice does**
→ Read: POSTOFFICE_README.md (overview section)

**Learn the complete architecture**
→ Read: POSTOFFICE_EXPLORATION_SUMMARY.md

**See how components relate**
→ Read: POSTOFFICE_ARCHITECTURE_DIAGRAM.md

**Write code using postoffice**
→ Read: POSTOFFICE_QUICK_REFERENCE.md

**Deploy postoffice to production**
→ Read: POSTOFFICE_README.md (deployment checklist section)

**Troubleshoot an issue**
→ Read: POSTOFFICE_README.md (troubleshooting section)

**Understand encryption**
→ Read: POSTOFFICE_EXPLORATION_SUMMARY.md (section 2 & 6)

**Monitor shared mailboxes**
→ Read: POSTOFFICE_EXPLORATION_SUMMARY.md (section 3.4)

**Manage passwords**
→ Read: POSTOFFICE_EXPLORATION_SUMMARY.md (section 6)

**Set up events/notifications**
→ Read: POSTOFFICE_EXPLORATION_SUMMARY.md (section 7)

---

## File Organization

```
/home/opencode/data/work/
├── POSTOFFICE_README.md                     ← START HERE
├── POSTOFFICE_DOCUMENTATION_INDEX.md        ← You are here
├── POSTOFFICE_EXPLORATION_SUMMARY.md        ← Technical deep dive
├── POSTOFFICE_ARCHITECTURE_DIAGRAM.md       ← System architecture
└── POSTOFFICE_QUICK_REFERENCE.md            ← API reference

Source code:
/home/opencode/data/work/mistermcfeely/src/postoffice/
├── startup.py (588 lines)
├── __main__.py (292 lines)
├── password_auth.py (149 lines)
├── member_password.py (252 lines)
├── shared_mailbox_password.py (300 lines)
├── imap_lib.py (370 lines)
├── imap_client.py (291 lines)
├── imap_monitor.py
├── mailbox.py (264 lines)
├── virtual.py
├── main.py (49 lines)
├── __init__.py
├── lib.py (115 lines)
├── events.py
├── audit_log.py
├── message_client.py
├── password_crypto.py (20 lines, deprecated)
├── tui/
│   ├── __init__.py
│   └── password_manager.py (303 lines)
└── password/
    └── __init__.py
```

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total source lines | 3,901 |
| Total source files | 21 |
| Documentation lines | 2,713 |
| Documentation files | 4 |
| Main components | 10 |
| Database tables | 7 |
| Event types | 5 |
| CLI commands | 4 |

---

## Reading Recommendations

### For System Architects
1. POSTOFFICE_ARCHITECTURE_DIAGRAM.md (layered architecture, data flows)
2. POSTOFFICE_EXPLORATION_SUMMARY.md (sections 1, 10, 11)
3. POSTOFFICE_README.md (design patterns)

### For Developers
1. POSTOFFICE_README.md (quick start)
2. POSTOFFICE_QUICK_REFERENCE.md (API reference)
3. POSTOFFICE_EXPLORATION_SUMMARY.md (detailed reference)
4. Source code (implementation details)

### For DevOps/System Administrators
1. POSTOFFICE_README.md (deployment checklist, troubleshooting)
2. POSTOFFICE_EXPLORATION_SUMMARY.md (section 11, deployment)
3. POSTOFFICE_QUICK_REFERENCE.md (CLI commands)

### For Security Auditors
1. POSTOFFICE_EXPLORATION_SUMMARY.md (section 2 - KEY usage)
2. POSTOFFICE_README.md (security considerations)
3. POSTOFFICE_EXPLORATION_SUMMARY.md (section 8 - audit logging)

### For Database Administrators
1. POSTOFFICE_EXPLORATION_SUMMARY.md (sections 1, 8, 11)
2. POSTOFFICE_QUICK_REFERENCE.md (database tables)
3. POSTOFFICE_ARCHITECTURE_DIAGRAM.md (section - database layer)

---

## Core Concepts Quick Summary

### 1. Single Encryption Key
- One POSTOFFICE_PASSWORD_KEY encrypts ALL passwords
- 32 bytes, AES-256-GCM
- Sources: env var, /etc/postoffice/password.key, ~/.postoffice/password.key

### 2. Two Password Types
- Personal: in engine.__member (for individual email)
- Shared mailbox: in postoffice.member_mailbox_password (for team mailboxes)

### 3. Fallback Logic
- Shared mailbox access tries: per-member password → shared default → error

### 4. IMAP Integration
- Connect to Cyrus IMAP with automatic credential resolution
- Message claiming with optional HMAC-SHA256 obfuscation

### 5. Background Monitoring
- IMAPMonitor polls mailboxes every 30 seconds
- Detects new, changed, deleted messages
- Fires events automatically

### 6. Event System
- message-new, message-claimed, message-unclaimed, message-flagged, message-deleted
- Events written to engine.__notify
- Routed via postoffice.message_routing rules

### 7. TUI Interfaces
- Main menu: [V]irtual, [M]ailbox, [Q]uit
- Password manager: set/view/delete passwords
- Mailbox CRUD: edit mailbox properties

### 8. Audit Logging
- All password operations logged
- Integrates with bbsengine6.logentry()
- Format: [PASSWORD] ACTION | key=value | ...

---

## Navigation by Topic

### Encryption & Security
- POSTOFFICE_README.md → Security Considerations
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 2 (Startup/KEY)
- POSTOFFICE_QUICK_REFERENCE.md → Encryption Key, Encryption Details

### Password Management
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 6 (Password Architecture)
- POSTOFFICE_QUICK_REFERENCE.md → Password Types, Common Workflows

### IMAP Integration
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 3 (IMAP Service)
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md → Example 2 (Alice accessing mailbox)
- POSTOFFICE_QUICK_REFERENCE.md → IMAP Operations

### Message Claiming
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 3.2 (IMAP Client)
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md → Example 4 (Member claims message)
- POSTOFFICE_QUICK_REFERENCE.md → Claim Flag Obfuscation

### Background Monitoring
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 3.4 (IMAP Monitor)
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md → Example 3 (Monitoring detects new message)
- POSTOFFICE_QUICK_REFERENCE.md → Background Monitoring

### Events & Notifications
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 7 (Events & Notifications)
- POSTOFFICE_QUICK_REFERENCE.md → Events
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md → Event flow diagram

### TUI Components
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 4 (Existing TUI)
- POSTOFFICE_QUICK_REFERENCE.md → TUI Components
- POSTOFFICE_README.md → Architecture Layers

### Database Schema
- POSTOFFICE_QUICK_REFERENCE.md → Database Tables
- POSTOFFICE_README.md → Database Schema Overview
- POSTOFFICE_EXPLORATION_SUMMARY.md → Throughout (table references)

### CLI Commands
- POSTOFFICE_QUICK_REFERENCE.md → CLI Commands
- POSTOFFICE_README.md → Startup/Initialization
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 2.2 (CLI Entry Point)

### Deployment
- POSTOFFICE_README.md → Deployment Checklist
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 11 (Deployment)
- POSTOFFICE_QUICK_REFERENCE.md → CLI Commands

### Troubleshooting
- POSTOFFICE_README.md → Troubleshooting section
- POSTOFFICE_QUICK_REFERENCE.md → Debugging section
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md → Data flows

### Architecture & Design
- POSTOFFICE_ARCHITECTURE_DIAGRAM.md (complete)
- POSTOFFICE_README.md → Architecture Layers, Design Patterns
- POSTOFFICE_EXPLORATION_SUMMARY.md → Section 10 (Relationships)

---

## Document Statistics

| File | Lines | Sections | Focus |
|------|-------|----------|-------|
| POSTOFFICE_README.md | 603 | 13 | Overview, quick answers |
| POSTOFFICE_EXPLORATION_SUMMARY.md | 806 | 13 | Technical details |
| POSTOFFICE_ARCHITECTURE_DIAGRAM.md | 577 | 4 | Diagrams, data flows |
| POSTOFFICE_QUICK_REFERENCE.md | 727 | 20 | API reference, examples |
| **TOTAL** | **2,713** | | Complete documentation |

---

## How These Docs Were Created

1. **Explored codebase structure** using:
   - `find` for locating files
   - `wc -l` for file sizes
   - `tree` for directory structure

2. **Analyzed key files** line-by-line:
   - startup.py (588 lines) - encryption key logic
   - password_auth.py (149 lines) - credential fallback
   - member_password.py (252 lines) - personal passwords
   - shared_mailbox_password.py (300 lines) - shared passwords
   - imap_lib.py (370 lines) - IMAP connections
   - imap_client.py (291 lines) - message operations
   - And 15 more files...

3. **Created cross-reference documentation**:
   - Component relationships
   - Data flow diagrams
   - API documentation
   - Code examples

4. **Compiled into 4 documents**:
   - Master README (navigation)
   - Exploration Summary (technical reference)
   - Architecture Diagram (visual understanding)
   - Quick Reference (developer guide)

---

## Related Project Documentation

In the mistermcfeely directory:

- **ENCRYPTION_KEY_MANAGEMENT.md** - Key distribution strategies
- **PASSWORD_SYSTEMS_EXPLAINED.md** - Password architecture
- **PASSWORD_SYSTEMS_SUMMARY.md** - Quick password overview
- **CONN_POOL_PATTERN.md** - Connection pooling
- **IMAP_DAEMON_INTEGRATION.md** - IMAP service integration
- **FINAL_SUMMARY.md** - Project completion summary

---

## Getting Help

1. **Search the documentation**
   - Use Ctrl+F to search across files
   - Look for keywords in the index above

2. **Review code examples**
   - POSTOFFICE_QUICK_REFERENCE.md has copy-paste examples
   - POSTOFFICE_ARCHITECTURE_DIAGRAM.md has data flow examples

3. **Check troubleshooting**
   - POSTOFFICE_README.md has common issues
   - POSTOFFICE_QUICK_REFERENCE.md has debugging tips

4. **Examine source code**
   - `/home/opencode/data/work/mistermcfeely/src/postoffice/`
   - Files are well-commented
   - Follow imports to understand relationships

---

## Version Information

- **Documentation Created:** May 21, 2026
- **Postoffice Module Version:** 1.0.0
- **bbsengine6 Integration:** Full compliance
- **Python Version:** 3.9-3.12
- **Documentation Version:** 1.0

---

## Feedback & Updates

These documents comprehensively cover the postoffice codebase as of May 21, 2026.

To update documentation:
1. Note the changes to postoffice source
2. Update relevant section in appropriate document
3. Update statistics and cross-references
4. Regenerate this index if major changes

---

