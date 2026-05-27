# Postoffice Cyrus Admin - Account and Mailbox Management

## Overview

The Cyrus Admin module provides a comprehensive Text User Interface (TUI) for managing Cyrus IMAP accounts and shared mailboxes. It allows administrators to:

- **Account Management**: Create accounts, view account details, set/change passwords
- **Shared Mailbox Management**: Create shared mailboxes, manage member access, assign passwords

## Architecture

### Main Components

#### 1. **CyrusAdmin TUI** (`postoffice/tui/cyrus_admin.py`)
- Interactive command-line interface for account and mailbox management
- Main menu with options for account and mailbox operations
- Restricted to administrators (checks `issuperuser` flag)
- Uses `inputchoice()` for menu navigation and `inputpassword()` for password input

#### 2. **Updated Main Entry Point** (`postoffice/__main__.py`)
- New `menu` command (default) for interactive menu
- `tui` command for message interface only
- `accounts` command for direct account management access
- `handle_menu()` function shows main menu with choices for TUI and account management
- Proper error handling and encryption key validation

#### 3. **Test Account Generator** (`src/generate_test_accounts.py`)
- Standalone script to generate test data
- Creates multiple user accounts with passwords
- Creates multiple shared mailboxes
- Assigns members to mailboxes with random passwords
- Useful for development and testing

### Features

#### Account Management
```bash
# Create new account
- Prompts for moniker (username)
- Requires inbound password (IMAP)
- Optionally sets outbound password (SMTP)
- Validates moniker uniqueness
- Stores passwords encrypted

# View accounts
- Lists all user accounts
- Shows creation date
- Displays account metadata

# Account details
- View account creation time
- Check password status
```

#### Shared Mailbox Management
```bash
# Create new shared mailbox
- Prompts for mailbox name
- Records creator
- Generates unique ID
- Validates name uniqueness

# Manage mailbox members
- View members with access to mailbox
- Assign members to mailbox
- Set inbound/outbound passwords per member
- Both password types independently configurable

# Mailbox details
- List all members with access
- Show member count
- Track creation and modification times
```

## Usage

### Running the Postoffice Menu

```bash
# Default menu interface
python -m postoffice

# Direct access to account management
python -m postoffice accounts

# Message interface only
python -m postoffice tui
```

### Menu Navigation

The main menu uses `inputchoice()` for easy keyboard navigation:

```
=== postoffice ===

Choose action: (t)ui messages, (m)anage accounts, (a)dmin menu, (q)uit, e(x)it
```

Press the single letter for desired action:
- `t` - Open message interface
- `m` - Account and mailbox management (admin only)
- `a` - Admin menu (admin only)
- `q` or `x` - Exit

### Account Management Interface

```
=== Cyrus Account Management ===
Administrator: admin

Choose action: (a)ccounts, (c)reate account, (s)hared mailboxes, (m)anage mailbox, e(x)it, (q)uit
```

Actions:
- `a` - List all accounts
- `c` - Create new account
- `s` - List all shared mailboxes
- `m` - Manage specific shared mailbox
- `x`/`q` - Exit

### Creating Test Data

```bash
# Create default test data (5 accounts, 3 mailboxes)
python src/generate_test_accounts.py -v

# Create custom number of accounts and mailboxes
python src/generate_test_accounts.py -n 10 -m 5 -v

# Options:
#   -n, --num-accounts    Number of test accounts (default: 5)
#   -m, --num-mailboxes   Number of shared mailboxes (default: 3)
#   -v, --verbose         Show verbose output
```

## Database Schema

### Tables Created

#### `postoffice.shared_mailbox`
```sql
CREATE TABLE postoffice.shared_mailbox (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    enabled BOOLEAN DEFAULT TRUE
);
```

#### `postoffice.member_mailbox_password` (existing)
```sql
CREATE TABLE postoffice.member_mailbox_password (
    mailbox_id BIGINT NOT NULL,
    member_moniker TEXT NOT NULL,
    password_type TEXT NOT NULL,  -- 'inbound' or 'outbound'
    encrypted_password BYTEA NOT NULL,
    set_by_moniker TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (mailbox_id, member_moniker, password_type)
);
```

## Security Features

### Password Management
- All passwords encrypted using `password_crypto` module
- Uses `inputpassword()` for secure hidden input
- No plaintext password display in logs or output
- Confirmation required for password entry

### Access Control
- Admin-only access (checks `issuperuser` flag)
- Permission checks in all password operations
- Non-admins can only modify their own passwords
- Admins can manage any member's passwords

### Database Operations
- Proper connection handling with context managers
- Transaction support via `database.connect()`
- Error handling and logging for all operations
- Cursor cleanup on completion

## Implementation Details

### CyrusAdmin Class Structure

```python
class CyrusAdmin:
    def __init__(self, args: Any)
    def run(self) -> int                              # Main TUI loop
    
    # Account Management
    def _list_accounts(self) -> None                  # List all accounts
    def _create_account(self) -> None                 # Create new account
    
    # Shared Mailbox Management
    def _list_shared_mailboxes(self) -> None          # List all mailboxes
    def _manage_shared_mailbox(self) -> None          # Menu for mailbox ops
    def _view_mailbox_members(self, ...) -> None      # Show members
    def _create_shared_mailbox(self) -> None          # Create new mailbox
    def _set_shared_mailbox_password(self, ...) -> None  # Set member password
```

### Dependencies

**bbsengine6 modules:**
- `bbsengine6.io.echo` - Output messages
- `bbsengine6.io.inputchoice` - Menu navigation
- `bbsengine6.console.inputpassword` - Secure password input
- `bbsengine6.database` - Database connection

**Postoffice modules:**
- `member_password` - Personal account password management
- `shared_mailbox_password` - Shared mailbox password management
- `startup` - Encryption key management

## Error Handling

All operations include comprehensive error handling:

```python
try:
    # Database operation
    with database.connect(self.args) as conn:
        with conn.cursor() as cur:
            # Execute query
except Exception as e:
    echo(f"Error: {e}", level="error")
```

## Future Enhancements

Potential features for future development:

1. **Account Deletion** - Remove user accounts with cascade cleanup
2. **Password Reset** - Force password change for accounts
3. **Audit Logging** - Track all admin actions
4. **Bulk Operations** - Import/export accounts and mailboxes
5. **Access Levels** - Different permission levels for shared mailboxes
6. **Mailbox Quotas** - Set and manage storage limits
7. **Member Roles** - Admin, editor, viewer roles per mailbox
8. **Archiving** - Archive inactive accounts and mailboxes

## Testing

### Unit Tests
```bash
# Verify syntax
python -m py_compile postoffice/tui/cyrus_admin.py
python -m py_compile postoffice/__main__.py
python -m generate_test_accounts.py

# Run linting
ruff check . --no-cache
ruff format .
```

### Integration Testing
```bash
# Generate test data
python src/generate_test_accounts.py -v

# Run the menu
python -m postoffice

# Directly access accounts
python -m postoffice accounts
```

## API Reference

### Key Functions Used

#### Member Password Management
```python
member_password.set_personal_password(args, moniker, password_type, password, set_by_moniker)
member_password.get_personal_password(args, moniker, password_type, requester_moniker)
member_password.list_personal_passwords(args, moniker, requester_moniker)
member_password.delete_personal_password(args, moniker, password_type, requester_moniker)
```

#### Shared Mailbox Password Management
```python
shared_mailbox_password.set_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, password, set_by_moniker)
shared_mailbox_password.get_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, requester_moniker)
shared_mailbox_password.list_shared_mailbox_passwords(args, mailbox_id, requester_moniker)
shared_mailbox_password.delete_shared_mailbox_password(args, mailbox_id, member_moniker, password_type, requester_moniker)
```

## Files Modified/Created

### New Files
- `postoffice/tui/cyrus_admin.py` - CyrusAdmin TUI class (280+ lines)
- `src/generate_test_accounts.py` - Test data generator (320+ lines)
- `sql/005_add_shared_mailbox.sql` - Database schema

### Modified Files
- `postoffice/__main__.py` - Added menu handler and accounts command

### SQL Schema
- `sql/005_add_shared_mailbox.sql` - New shared mailbox table definition
- `sql/004_add_member_mailbox_passwords.sql` - Existing member password table (already present)

## Conclusion

The Cyrus Admin module provides a complete, secure, and user-friendly interface for managing IMAP accounts and shared mailboxes. It follows bbsengine6 conventions, implements proper error handling, and integrates seamlessly with the existing postoffice password management system.
