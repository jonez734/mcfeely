# Postoffice TUI Implementation

## Overview
Implemented a Text User Interface (TUI) for the postoffice module that can be invoked with `python -m postoffice` or `python -m postoffice tui`.

## Files Created/Modified

### New Files
1. **postoffice/tui/message_interface.py** - Main TUI interface for reading and managing messages

### Modified Files
1. **postoffice/__main__.py** - Added TUI command handler and made it the default command

## Features Implemented

### Main Menu (io.inputchoice())
- **(n)ew message** - Start composing a new message (placeholder)
- **(l)ist messages** - View messages from IMAP mailbox (default)
- **(x)exit** - Exit the application

### Message List (listboxcursor)
- Display messages with:
  - Sender (truncated to 25 chars)
  - Subject (truncated to 50 chars)
- Navigation with UP/DOWN arrow keys
- ENTER to select a message
- **KEY_DELETE** - Delete message (handler implemented)
- **r** - Reply to message (handler implemented)
- **f** - Forward message (handler implemented)
- **KEY_ESCAPE** - Exit list and return to main menu

### Message Detail View
- Show full message headers:
  - From
  - Subject
  - Date
- Display message body (first 30 lines)
- Quick actions menu

## Architecture

### MessageInterface Class
Located in `postoffice/tui/message_interface.py`

**Methods:**
- `run()` - Main TUI loop
- `_compose_new_message()` - Placeholder for new message composition
- `_list_messages()` - Main message list interface
- `_connect_imap()` - Connect to IMAP server using credentials
- `_fetch_messages()` - Fetch message headers from INBOX
- `_show_message_list()` - Display listbox with message list
- `_message_detail()` - Show detailed view of a single message
- `_get_message_body()` - Extract plain text body from email
- `_message_actions()` - Handle key input for message actions
- `_delete_message()` - Delete a message (sets \Deleted flag and expunges)
- `_reply_to_message()` - Placeholder for reply functionality
- `_forward_message()` - Placeholder for forward functionality

### Key Safety Features
- **Encryption Key Check** - TUI aborts if POSTOFFICE_PASSWORD_KEY is not available
- **Error Handling** - Graceful error messages for IMAP connection issues
- **Resource Cleanup** - IMAP connection is properly closed in finally block

## Usage

### Run TUI (default)
```bash
cd mistermcfeely/src
python -m postoffice
```

### Run TUI explicitly
```bash
python -m postoffice tui
```

### Check encryption key first
```bash
python -m postoffice startup-check
```

## Integration with Existing Code

### IMAP Functions Used
- `imap_lib.get_imap_credentials()` - Get IMAP connection parameters
- `imap_lib.connect_cyrus()` - Connect to Cyrus IMAP server
- `imap_lib.select_mailbox()` - Select mailbox (INBOX)
- `imap_lib.get_all_uids()` - Get all message UIDs
- `imap_lib.get_message_headers()` - Fetch message headers

### bbsengine6 Functions Used
- `echo()` - Output with color/formatting
- `inputchoice()` - Menu choice input
- `getch_str()` - Raw key input
- `Listbox` - Message list display with custom key handlers
- `ListboxItem` - Individual message list item
- `ListboxResult` - Result from listbox selection

## Testing

### Syntax Check
```bash
python -m py_compile postoffice/tui/message_interface.py
python -m py_compile postoffice/__main__.py
```

### Import Test
```bash
cd mistermcfeely/src
python -c "from postoffice.tui.message_interface import MessageInterface; print('✓ Import successful')"
```

### Help
```bash
python -m postoffice --help
```

## TODO / Future Enhancements

### High Priority
- [ ] Implement new message composition
- [ ] Implement reply functionality (quoted text, To:/From: fields)
- [ ] Implement forward functionality
- [ ] Fix listbox selected_index tracking for proper message detail display
- [ ] Implement delete confirmation dialog

### Medium Priority
- [ ] Support shared mailbox messages
- [ ] Add message filtering/search
- [ ] Add pagination info in message list
- [ ] Add attachment display/download
- [ ] Add message marking as read/unread

### Low Priority
- [ ] Implement spam/trash folders
- [ ] Add signature support
- [ ] Add encryption support
- [ ] Add sending via SMTP

## Code Style Notes
- Follows project guidelines (4-space indentation, type hints, docstrings)
- Uses bbsengine6 conventions (echo() for output, not print())
- Resource cleanup with try/finally blocks
- Proper exception handling with meaningful error messages
