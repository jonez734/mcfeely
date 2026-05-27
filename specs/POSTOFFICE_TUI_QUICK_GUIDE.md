# Postoffice TUI Quick Reference Guide

## Quick Start

```bash
cd mistermcfeely/src
python -m postoffice
```

This launches the interactive TUI with the main menu.

## Main Menu

```
=== postoffice ===
User: [username]

Choose action: [nlx]
```

Press one of:
- **n** - New message (not yet implemented)
- **l** - List messages (default, shows INBOX)
- **x** - Exit application

## Message List Interface

```
=== Messages ===
UP/DOWN to navigate, ENTER to select, ESC to exit

[from               ] [subject                          ]
sender@example.com  Important Update - Action Required
another@test.com    Meeting Notes
...
```

### Message List Keys

| Key | Action |
|-----|--------|
| UP/DOWN | Navigate cursor |
| ENTER | Select and view message |
| DEL | Delete message |
| r | Reply to message |
| f | Forward message |
| ESC | Exit list |

## Message Detail View

```
=== Message ===
From: sender@example.com
Subject: Important Update - Action Required
Date: Mon, 21 May 2026 10:30:00 +0000

---
Message body text here...
(up to 30 lines shown)
---

Actions:
  DEL = delete
  r   = reply
  f   = forward
  ESC = back to list
```

### Message Detail Keys

| Key | Action |
|-----|--------|
| DEL | Delete message (sets \\Deleted flag) |
| r | Reply to message (stub) |
| f | Forward message (stub) |
| ESC | Return to message list |

## Other Commands

```bash
# Show help
python -m postoffice --help

# Check encryption key setup
python -m postoffice startup-check --verbose

# Generate new encryption key
python -m postoffice startup-generate

# Install key to system
python -m postoffice startup-install

# Initialize password system
python -m postoffice startup-init
```

## Troubleshooting

### "Error: Encryption key not available"

The POSTOFFICE_PASSWORD_KEY environment variable or system key file is missing.

**Solution:**
```bash
# Check current status
python -m postoffice startup-check

# Generate new key
python -m postoffice startup-generate

# Install key
python -m postoffice startup-install

# Verify installation
python -m postoffice startup-check
```

### "Could not connect to IMAP server"

IMAP credentials are missing or invalid.

**Solution:**
- Ensure your user password is set in the system
- Check that postoffice has credentials for your member account
- If using shared mailbox, ensure shared mailbox password is set

### "No messages found"

Your INBOX is empty, or IMAP connection succeeded but mailbox is empty.

**Solution:**
- Check your IMAP server and mailbox status
- Ensure you have messages in your INBOX

## Code Structure

```
mistermcfeely/src/postoffice/
├── __main__.py                 # Entry point, argument parsing
├── startup.py                  # Encryption key management
├── imap_lib.py                 # IMAP operations
├── imap_client.py              # IMAP client wrapper
├── member_password.py          # Member password storage
├── shared_mailbox_password.py  # Shared mailbox passwords
├── mailbox.py                  # Mailbox management
└── tui/
    ├── __init__.py
    ├── message_interface.py     # ← NEW: Main TUI module
    └── password_manager.py      # Password management TUI
```

## Key Files

| File | Purpose |
|------|---------|
| `postoffice/__main__.py` | Entry point, "tui" command handler |
| `postoffice/tui/message_interface.py` | Main TUI interface |
| `postoffice/startup.py` | Encryption key validation |
| `postoffice/imap_lib.py` | IMAP operations |

## Important Notes

1. **Encryption Key Required**: The TUI aborts if POSTOFFICE_PASSWORD_KEY is not available
2. **Default Command**: Running `python -m postoffice` runs the TUI (not startup-check)
3. **Connection Cleanup**: IMAP connections are properly closed in finally blocks
4. **Error Handling**: All operations have graceful error messages
5. **User Context**: Current user is determined from `args.loginid`

## API Reference

### MessageInterface Class

```python
from postoffice.tui.message_interface import MessageInterface

# Initialize with bbsengine6 args
tui = MessageInterface(args)

# Run main TUI loop (returns exit code)
exit_code = tui.run()
```

### Methods

- `run()` - Main TUI loop, returns 0 on exit, 1 on error
- `_list_messages()` - Fetch and display message list
- `_message_detail(msg)` - Show detailed message view
- `_delete_message(uid)` - Delete message by UID
- `_reply_to_message(msg)` - Reply composer (stub)
- `_forward_message(msg)` - Forward composer (stub)

## Development Tips

### Testing the TUI

```bash
cd mistermcfeely/src

# Syntax check
python -m py_compile postoffice/__main__.py
python -m py_compile postoffice/tui/message_interface.py

# Import test
python -c "from postoffice.tui.message_interface import MessageInterface; print('OK')"

# Run with debug
python -m postoffice --verbose
```

### Adding Features

To add new features to the TUI:

1. Edit `postoffice/tui/message_interface.py`
2. Follow the existing pattern for key handlers
3. Use `echo()` for output (not `print()`)
4. Add proper error handling with try/except
5. Test with `python -m py_compile`
6. Commit with `git add` and `git commit`

### Key Handler Pattern

```python
def _handle_new_key(self) -> Optional[ListboxResult]:
    """Handle custom key press."""
    try:
        # Do work
        operation()
    except Exception as e:
        echo(f"Error: {e}", level="error")
        return None
    # Return None to continue, ListboxResult to exit
    return None
```

## See Also

- [POSTOFFICE_TUI_IMPLEMENTATION.md](./POSTOFFICE_TUI_IMPLEMENTATION.md) - Detailed feature list
- [POSTOFFICE_TUI_CODE_OVERVIEW.md](./POSTOFFICE_TUI_CODE_OVERVIEW.md) - Code architecture
- `postoffice/__main__.py` - Entry point and command routing
- `postoffice/tui/message_interface.py` - Main TUI implementation
