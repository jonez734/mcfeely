# Postoffice IMAP Server Connectivity Checker

## Overview

The IMAP Checker module provides comprehensive connectivity testing for Cyrus IMAP servers. It verifies that:

1. The IMAP server is listening on the configured address and port
2. The server responds to IMAP protocol commands
3. SSL/TLS is properly configured
4. The server supports required IMAP capabilities

## Features

### Connectivity Checks

The checker performs two levels of verification:

#### 1. TCP Connectivity Check
- Verifies the IMAP server is actually listening on the configured host/port
- Uses raw TCP socket connection (no SSL/TLS overhead)
- Detects connection refused, timeout, host resolution failures
- Fast and lightweight

#### 2. IMAP Protocol Check
- Verifies the server responds to IMAP commands over SSL/TLS
- Checks for valid IMAP greeting
- Retrieves server capabilities
- Verifies SSL/TLS configuration is working

### Configuration

The checker reads IMAP configuration from `~/.postoffice`:

```ini
[imap]
host = localhost
port = 993
```

If no config file exists, defaults to:
- Host: `localhost`
- Port: `993` (standard IMAP SSL port)

### Command-line Usage

```bash
# Check using configured IMAP settings
python -m postoffice imap-check

# Check with verbose output
python -m postoffice imap-check -v

# Override host
python -m postoffice imap-check --imaphost mail.example.com

# Override port
python -m postoffice imap-check --imapport 143

# Override both
python -m postoffice imap-check --imaphost mail.example.com --imapport 993 -v
```

## Module Documentation

### IMAPChecker Class

The `IMAPChecker` class provides the core functionality:

```python
from postoffice.imap_checker import IMAPChecker

# Create checker instance
checker = IMAPChecker(
    host="localhost",
    port=993,
    timeout=5,          # Connection timeout in seconds
    verbose=True        # Show detailed output
)

# Check TCP connectivity
success, message = checker.check_connectivity()

# Check IMAP protocol
success, message = checker.check_imap_protocol()

# Check both
all_pass, results = checker.check_all()
checker.print_results(all_pass, results)

# Quick verification
if IMAPChecker.verify_connection("localhost", 993):
    print("IMAP server is accessible")
```

### Return Values

All check methods return `Tuple[bool, str]`:
- `success` (bool): True if check passed
- `message` (str): Diagnostic message or error description

The `check_all()` method returns `Tuple[bool, list]`:
- `all_pass` (bool): True if all checks passed
- `results` (list): List of dicts with check results

Each result dict contains:
- `name` (str): Check name
- `passed` (bool): Pass/fail status
- `message` (str): Diagnostic message

## Usage Examples

### Basic Check

```bash
$ python -m postoffice imap-check

Checking IMAP server at localhost:993...

=== IMAP Server Connectivity Check ===
Host: localhost
Port: 993
Timeout: 5s

✓ TCP Connectivity: Server listening on localhost:993
✓ IMAP Protocol: IMAP server responding. Capabilities: IMAP4REV1 CAPABILITY AUTH...

✓ All checks passed - IMAP server is accessible
```

### Failed Connection

```bash
$ python -m postoffice imap-check

Checking IMAP server at localhost:9999...

=== IMAP Server Connectivity Check ===
Host: localhost
Port: 9999
Timeout: 5s

✗ TCP Connectivity: Connection refused - no server listening on localhost:9999
✗ IMAP Protocol: Skipped (TCP connectivity failed)

✗ Some checks failed - please verify IMAP configuration
```

### Verbose Output

```bash
$ python -m postoffice imap-check -v

Checking IMAP server at localhost:993...

Checking TCP connectivity to localhost:993...
✓ TCP connection successful
Checking IMAP protocol on localhost:993...
✓ IMAP greeting: * OK [CAPABILITY IMAP4REV1...] Cyrus IMAP4 v2.5.16...
✓ Server capabilities: 14 available

=== IMAP Server Connectivity Check ===
Host: localhost
Port: 993
Timeout: 5s

✓ TCP Connectivity: Server listening on localhost:993
✓ IMAP Protocol: IMAP server responding. Capabilities: IMAP4REV1 CAPABILITY...

✓ All checks passed - IMAP server is accessible
```

## Error Messages

### TCP Connectivity Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Connection timeout | Server not responding | Check server is running, increase timeout |
| Host resolution failed | Invalid hostname | Verify hostname/IP address is correct |
| Connection refused | No server on that port | Check IMAP service is running on correct port |

### IMAP Protocol Errors

| Error | Cause | Solution |
|-------|-------|----------|
| SSL/TLS error | Certificate problem | Check SSL/TLS configuration, verify certificates |
| IMAP protocol error | Invalid response | Server may not be IMAP, check port and service |
| Connection timeout | Server hung | Increase timeout or check server logs |
| CAPABILITY failed | Server doesn't support | Unusual - most IMAP servers support this |

## Integration

The checker is integrated into the postoffice startup sequence:

1. When running `python -m postoffice`, the menu checks for encryption key
2. Optional: Run `imap-check` before accessing message interface to verify server
3. Account management doesn't require IMAP connectivity (database-only operations)

### Programmatic Integration

```python
from postoffice.imap_checker import IMAPChecker

# Check if IMAP is available before connecting
if not IMAPChecker.verify_connection("localhost", 993, verbose=True):
    echo("Warning: IMAP server not accessible", level="error")
    # Handle gracefully
```

## Configuration Files

### ~/.postoffice

Standard postoffice configuration file:

```ini
[imap]
host = localhost
port = 993
```

### Environment Variables

Alternatively, set via environment:

```bash
export IMAP_HOST=mail.example.com
export IMAP_PORT=993
```

(Note: Currently the checker only reads from config file, but can be extended)

## Timeout Behavior

The checker includes configurable timeout for slow networks:

- Default timeout: 5 seconds
- Minimum timeout: 1 second
- Applied to both TCP and SSL/TLS connections

For slow/distant servers, increase timeout:

```python
checker = IMAPChecker("mail.example.com", 993, timeout=10, verbose=True)
```

## Security Considerations

### SSL/TLS Verification

The checker uses `ssl.create_default_context()` which:
- Verifies SSL/TLS certificates against system CA bundle
- Rejects self-signed certificates by default
- Enforces modern TLS protocols

For self-signed certificates, the check will fail. This is intentional for security, but can be bypassed in development:

```python
import ssl
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE
# Then use custom context (not recommended for production)
```

### No Credentials Stored

The checker never requests or stores passwords:
- Doesn't attempt to authenticate
- Only checks if server is responding
- Safe to run in automated monitoring

## Code Quality

- ✅ All files pass ruff linting
- ✅ 100% type hints coverage
- ✅ Comprehensive docstrings
- ✅ Proper error handling
- ✅ Resource cleanup

## API Reference

### IMAPChecker Class

```python
class IMAPChecker:
    def __init__(
        self, 
        host: str,
        port: int,
        timeout: int = 5,
        verbose: bool = False
    ) -> None
    
    def check_connectivity(self) -> Tuple[bool, str]
    def check_imap_protocol(self) -> Tuple[bool, str]
    def check_all(self) -> Tuple[bool, list]
    def print_results(self, all_pass: bool, results: list) -> None
    
    @staticmethod
    def verify_connection(
        host: str,
        port: int,
        timeout: int = 5,
        verbose: bool = False
    ) -> bool
```

## Future Enhancements

Potential additions:

1. **IMAP Account Testing** - Attempt login with test credentials
2. **Mailbox Testing** - Verify mailbox operations (create, delete, select)
3. **Performance Metrics** - Measure response times
4. **Monitoring Integration** - Export metrics for monitoring systems
5. **Health Check Endpoint** - Expose health check via HTTP
6. **Configuration Validation** - Warn about unusual settings
7. **TLS Version Detection** - Identify TLS version in use

## Troubleshooting

### Server shows as not listening but I know it's running

1. Verify correct host/port combination
2. Check firewall rules allow connection
3. Check server logs for binding errors
4. Try connecting manually with `openssl s_client`

### Getting SSL/TLS errors

1. Verify certificate is valid
2. Check certificate chain is complete
3. Verify server hostname matches certificate
4. Check system time is correct (NTP sync)

### Getting IMAP protocol errors

1. Verify the port is actually running IMAP (not something else)
2. Check server logs for protocol errors
3. Verify IMAP is not requiring authentication at connection
4. Check server configuration

## Example Integration

```python
from postoffice import imap_checker, startup

def initialize_postoffice():
    """Initialize postoffice with IMAP verification."""
    # Initialize encryption
    if not startup.get_encryption_key():
        print("Error: Encryption key required")
        return False
    
    # Verify IMAP connectivity
    if not imap_checker.IMAPChecker.verify_connection("localhost", 993):
        print("Warning: IMAP server not accessible")
        # Continue anyway or return False
    
    return True
```

## Files

- `postoffice/imap_checker.py` - IMAPChecker class
- `postoffice/__main__.py` - imap-check command handler

## See Also

- `POSTOFFICE_CYRUS_ADMIN_README.md` - Account management
- `POSTOFFICE_TUI_QUICK_GUIDE.md` - Message interface
