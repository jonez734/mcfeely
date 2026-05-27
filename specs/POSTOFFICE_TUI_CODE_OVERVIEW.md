# Postoffice TUI - Code Overview

## Entry Point Flow

```
python -m postoffice
    ↓
postoffice/__main__.py:main()
    ↓
Argument parsing (default command = "tui")
    ↓
handle_tui(args)
    ├─ Check encryption key with startup.get_encryption_key()
    ├─ Abort if key not available
    └─ MessageInterface(args).run()
```

## MessageInterface Class Flow

```
MessageInterface.run()
    ├─ Display main menu with inputchoice()
    ├─ Handle choices:
    │   ├─ "N" → _compose_new_message() [placeholder]
    │   ├─ "L" → _list_messages()
    │   │    ├─ _connect_imap()
    │   │    │    └─ imap_lib.get_imap_credentials()
    │   │    │    └─ imap_lib.connect_cyrus()
    │   │    ├─ _fetch_messages()
    │   │    │    ├─ imap_lib.select_mailbox("INBOX")
    │   │    │    ├─ imap_lib.get_all_uids()
    │   │    │    └─ imap_lib.get_message_headers() for each UID
    │   │    ├─ _show_message_list()
    │   │    │    └─ Listbox with custom_keys handlers:
    │   │    │        ├─ KEY_DELETE → _handle_delete_key()
    │   │    │        ├─ R → _handle_reply_key()
    │   │    │        └─ F → _handle_forward_key()
    │   │    └─ _message_detail(selected_msg)
    │   │         ├─ Fetch full message via IMAP
    │   │         ├─ Display headers and body
    │   │         └─ _message_actions()
    │   │              ├─ KEY_DELETE → _delete_message()
    │   │              ├─ R → _reply_to_message()
    │   │              └─ F → _forward_message()
    │   └─ "X" → Exit (return 0)
    └─ Loop until exit
```

## Data Structures

### Message Dictionary
```python
{
    "uid": int,              # IMAP UID
    "from": str,             # From header (truncated to 25 chars)
    "subject": str,          # Subject (truncated to 50 chars)
    "date": str,             # Date header
}
```

### Listbox Item
```python
ListboxItem(content=f"{from_addr} {subject}")
```

## Key Handlers

### Custom Keys in Listbox
- `KEY_DELETE`: Calls `_handle_delete_key()` → Placeholder
- `R`: Calls `_handle_reply_key()` → Placeholder  
- `F`: Calls `_handle_forward_key()` → Placeholder

### Key Input in Message Detail
Uses `getch()` to capture:
- `KEY_DELETE`: Call `_delete_message(uid)`
- `R`: Call `_reply_to_message(msg)`
- `F`: Call `_forward_message(msg)`
- `KEY_ESCAPE`: Return to list

## IMAP Operations

### Connection
```python
creds = imap_lib.get_imap_credentials(username)
imap = imap_lib.connect_cyrus(creds)
```

### Select Mailbox
```python
imap_lib.select_mailbox(imap, "INBOX")
```

### Fetch Messages
```python
uids = imap_lib.get_all_uids(imap)
for uid in uids:
    headers = imap_lib.get_message_headers(imap, uid)
```

### Fetch Full Message
```python
status, data = imap.uid("FETCH", str(uid), "RFC822")
message = email.message_from_bytes(data[0][1])
```

### Delete Message
```python
imap.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")
imap.expunge()
```

## Error Handling Pattern

All methods follow this pattern:

```python
try:
    # Do work
    operation()
except Exception as e:
    echo(f"Error description: {e}", level="error")
    # Return None or default value
    return
finally:
    # Cleanup if needed
    resource.close()
```

## UI Output Functions

### Menu Input
```python
from bbsengine6.io.inputchoice import inputchoice

choice = inputchoice(
    prompt="Choose action: ",
    options="nlx",
    default="l",
    help="(n)ew message, (l)ist messages, e(x)it"
)
# Returns: "N", "L", "X", or None (if ESC)
```

### Messages
```python
from bbsengine6.io import echo

echo("Text to display")
echo("Error message", level="error")
echo("Debug info", level="debug")
echo("Info message", level="info")
```

### List Display
```python
from bbsengine6.listbox import Listbox, ListboxItem, ListboxResult

items = [
    ListboxItem(content=display_str)
    for display_str in message_strings
]

lb = Listbox(
    args,
    title="Messages",
    items=items,
    itemheight=1,
    itemsperpage=20,
    custom_keys={
        "KEY_DELETE": handler_func,
        "R": reply_func,
        "F": forward_func,
    }
)

result = lb.run()
# Returns: ListboxResult or None
```

### Raw Key Input
```python
from bbsengine6.io.getch import getch_str as getch

key = getch()
# Returns: "KEY_DELETE", "KEY_ESCAPE", "R", "F", or other
```

## Message Body Extraction

```python
def _get_message_body(self, message: email.message.Message) -> str:
    if message.is_multipart():
        # Look for text/plain part
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8")
    else:
        # Single part message
        return message.get_payload()
```

## Files and Line References

### postoffice/tui/message_interface.py
- `MessageInterface` class: Main TUI interface
- `_show_message_list()`: Listbox display logic
- `_message_detail()`: Message view and actions
- `_get_message_body()`: Email body extraction

### postoffice/__main__.py
- `handle_tui()`: TUI command entry point
- Encryption key validation before TUI launch

## Configuration

### Encryption Key Check
- Source: `startup.get_encryption_key()`
- Required: YES (TUI aborts if missing)
- Error: "Error: Encryption key not available"
- Suggestion: Run `python -m postoffice startup-check` to diagnose

### IMAP Credentials
- Source: `imap_lib.get_imap_credentials(username)`
- Includes: host, port, username, password
- Fallback: Shared mailbox password if personal not set

### User Information
- From: `args.loginid` (current username)
- Sysop: `args.issuperuser` (admin flag, currently unused)
