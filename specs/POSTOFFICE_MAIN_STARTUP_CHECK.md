# Postoffice Main - IMAP Startup Check

## Overview

The `postoffice/main.py` has been updated to **check IMAP server connectivity before starting the main menu**. This ensures users are immediately notified if the IMAP server is not available.

## Changes

### What Was Added

**IMAP Connectivity Check on Startup**

When the postoffice main menu starts (`postoffice/main.py`), it now:

1. Reads the configured IMAP host and port
2. Attempts to verify the IMAP server is listening
3. If server is not responding:
   - Shows detailed error message
   - Provides troubleshooting hints
   - Asks user if they want to continue anyway
4. If server is responding:
   - Shows confirmation message
   - Proceeds to main menu

### Code Changes

Added `_check_imap_connectivity(args)` function:
```python
def _check_imap_connectivity(args):
    """
    Check if IMAP server is running on configured address/port.
    
    Returns: True if IMAP server is accessible
    """
    imap_host = getattr(args, "imaphost", "localhost")
    imap_port = getattr(args, "imapport", 993)
    
    checker = IMAPChecker(imap_host, imap_port, timeout=5, verbose=False)
    all_pass, _ = checker.check_all()
    return all_pass
```

## Behavior

### When IMAP Server is Running

```
Checking IMAP server connectivity...
✓ IMAP server is responding

postoffice
database: [name] host: [host]:[port]
[V] Virtual
[M] Mailbox
[Q] Quit
```

Proceeds normally to the main menu.

### When IMAP Server is NOT Running

```
Checking IMAP server connectivity...

ERROR: IMAP server is not responding!
  Configured: localhost:993

Please verify:
  1. IMAP server is installed and running
  2. IMAP server is listening on the configured port
  3. Network connectivity to the IMAP server
  4. Firewall rules allow connections to the IMAP port

Run 'python -m postoffice imap-check --verbose' for more diagnostics

Continue without IMAP connection? [Y/N]: _
```

User can choose:
- **Y**: Continue to main menu anyway (not recommended)
- **N**: Exit postoffice (recommended)

## Benefits

1. **Early Detection**: Users discover IMAP issues immediately, not after navigating menus
2. **Clear Guidance**: Error message explains what to check and how to diagnose
3. **Helpful Links**: Suggests running `imap-check` for more detailed diagnostics
4. **User Choice**: Allows continuing anyway for experienced users
5. **Better UX**: Prevents confusing errors deep in the application

## Configuration

The check respects existing IMAP configuration:

**From `~/.postoffice`:**
```ini
[imap]
host = mail.example.com
port = 993
```

**From command-line arguments:**
```python
args.imaphost = "mail.example.com"
args.imapport = 993
```

**Defaults:**
```
host = localhost
port = 993
```

## Startup Flow

```
1. postoffice/main.py starts
   ↓
2. Check IMAP connectivity
   ├─ If success → Show "✓ IMAP server is responding"
   │                Continue to main menu
   │
   └─ If failure → Show error message
                   Ask "Continue anyway? Y/N"
                   ├─ Y → Continue to main menu
                   └─ N → Exit
```

## Integration with __main__.py

The main.py is called by `__main__.py` which handles the entry point. The IMAP check now runs:

```
python -m postoffice
  ↓
postoffice/__main__.py (entry point)
  ↓
postoffice/main.py (check IMAP, then show menu)
```

## Troubleshooting

If users see the IMAP error, they can:

### Option 1: Run diagnostic tool
```bash
python -m postoffice imap-check --verbose
```

Shows detailed IMAP connectivity information.

### Option 2: Check IMAP server status
```bash
ps aux | grep imap
netstat -tlnp | grep 993
```

### Option 3: Start IMAP server
```bash
systemctl start cyrus-imapd  # or dovecot
```

### Option 4: Use different IMAP server
Update `~/.postoffice`:
```ini
[imap]
host = mail.example.com
port = 993
```

## Error Messages Shown

**Error**: IMAP server is not responding!
- **Cause**: No server listening on configured address/port
- **Fix**: Start IMAP server or configure correct address

**Error**: IMAP protocol error
- **Cause**: Server listening but not responding to IMAP
- **Fix**: Check IMAP server configuration

**Error**: SSL/TLS error
- **Cause**: Certificate issue or TLS problem
- **Fix**: Use port 143 (non-SSL) or fix certificate

## Technical Details

### Timeout Handling

- **Connection timeout**: 5 seconds
- If IMAP doesn't respond in 5 seconds, it's considered unavailable
- Can be adjusted in `_check_imap_connectivity()` function

### Non-blocking

- Check is quick and doesn't block for long
- 5-second timeout is reasonable for local networks
- Users can still choose to continue if check fails

### Error Handling

- All exceptions caught and reported clearly
- Connection refused → Clear error message
- Timeout → Clear timeout message
- Protocol errors → Protocol-specific error message

## Files Modified

- `postoffice/main.py`
  - Added `_check_imap_connectivity()` function
  - Added IMAP check to `main()` function
  - Added error messaging and user prompt
  - All linting passes ✓

## Backward Compatibility

- Old code paths still work
- Users can choose to continue without IMAP
- Configuration format unchanged
- No breaking changes

## Testing

```bash
# When IMAP is running:
python -m postoffice
# Should proceed normally

# When IMAP is NOT running:
python -m postoffice
# Should show error and ask to continue
# Press 'N' to exit, 'Y' to continue anyway
```

## Future Enhancements

Possible additions:

1. **Retry on failure**: Option to retry the check
2. **Auto-start**: Attempt to start IMAP server automatically
3. **Healthcheck endpoint**: Expose IMAP health status via HTTP
4. **Monitoring integration**: Send alerts if IMAP goes down
5. **Fallback server**: Try alternate IMAP servers if primary fails

---

## Summary

The `postoffice/main.py` now checks IMAP connectivity on startup, providing users with immediate feedback if the IMAP server is not available and clear guidance on how to fix the issue.

This ensures users don't navigate deep into the application only to discover IMAP is not working.
