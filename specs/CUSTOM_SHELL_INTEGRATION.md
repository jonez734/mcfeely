# Custom Shell Integration

The postoffice module provides bbsengine6-compatible module patterns for integration into custom shell applications.

## Module API

The postoffice package can be imported and used as a bbsengine6 module:

```python
from postoffice.__main__ import (
    init_postoffice,
    access_postoffice,
    help_postoffice,
    version_postoffice,
)
```

## Command-Line Usage

### Direct Python

```bash
# Show help
python -m postoffice --help

# Show version
python -m postoffice --version

# Check encryption key setup
python -m postoffice startup-check
python -m postoffice startup-check --verbose

# Generate new key
python -m postoffice startup-generate

# Install to /etc/postoffice/
python -m postoffice startup-install

# Initialize password system
python -m postoffice startup-init
```

### Via Bash Wrapper

```bash
# Make executable
chmod +x ./bin/postoffice-startup

# Use wrapper
./bin/postoffice-startup startup-check
./bin/postoffice-startup startup-generate
./bin/postoffice-startup startup-install
./bin/postoffice-startup startup-init
```

## Custom Shell Integration

### Using bbsengine6 Module Framework

```python
from bbsengine6 import module
from postoffice.__main__ import (
    init_postoffice,
    access_postoffice,
    help_postoffice,
    version_postoffice,
)

# Create module API
apis = {
    "init": init_postoffice,
    "access": access_postoffice,
    "help": help_postoffice,
    "version": version_postoffice,
}

# Register postoffice as a module
module.register_module(
    name="postoffice",
    version="1.0.0",
    apis=apis,
    module_path="postoffice.__main__"
)

# Now run via module system
module.runmodule(args, "postoffice")
```

### Direct Function Calls

```python
from postoffice.__main__ import (
    init_postoffice,
    access_postoffice,
    help_postoffice,
    version_postoffice,
)
import argparse

# Create args object
args = argparse.Namespace(verbose=True, database=None)

# Initialize
if init_postoffice(args):
    print("✓ Module initialized")

# Check access
if access_postoffice(args):
    print("✓ Module accessible")

# Get help
help_text = help_postoffice(args)
print(help_text)

# Get version
version = version_postoffice(args)
print(version)
```

### With Custom Args Object

```python
from postoffice.__main__ import init_postoffice
from dataclasses import dataclass

@dataclass
class MyArgs:
    verbose: bool = False
    database: str = None

args = MyArgs(verbose=True)

# Works with any args object
init_postoffice(args)
```

## Module Functions

### `init_postoffice(args) -> bool`

Initialize the postoffice module.

**Parameters:**
- `args`: Object with optional `verbose` and `database` attributes

**Returns:**
- `True` if initialization successful, `False` otherwise

**Example:**
```python
from postoffice.__main__ import init_postoffice
import argparse

args = argparse.Namespace(verbose=True)
if init_postoffice(args):
    print("Module ready")
```

### `access_postoffice(args) -> bool`

Check if postoffice module is accessible.

**Parameters:**
- `args`: Object with optional attributes

**Returns:**
- `True` if encryption key is available, `False` otherwise

**Example:**
```python
from postoffice.__main__ import access_postoffice

if access_postoffice(None):
    print("Module is accessible")
```

### `help_postoffice(args) -> str`

Get help text for postoffice module.

**Parameters:**
- `args`: Unused, but follows bbsengine6 pattern

**Returns:**
- Help text string

**Example:**
```python
from postoffice.__main__ import help_postoffice

help_text = help_postoffice(None)
print(help_text)
```

### `version_postoffice(args) -> str`

Get version information.

**Parameters:**
- `args`: Unused

**Returns:**
- Version string

**Example:**
```python
from postoffice.__main__ import version_postoffice

version = version_postoffice(None)
print(version)  # "postoffice 1.0.0 - mistermcfeely password management"
```

## Command Handlers

The __main__.py module provides command handlers for each startup command:

### Available Handlers

```python
from postoffice.__main__ import (
    handle_startup_check,
    handle_startup_generate,
    handle_startup_install,
    handle_startup_init,
)
import argparse

# Example: Run startup check programmatically
args = argparse.Namespace(verbose=True)
exit_code = handle_startup_check(args)
if exit_code == 0:
    print("✓ Check passed")
```

## bbsengine6 Shell Integration

### Basic Integration

```python
from bbsengine6 import io
from postoffice.__main__ import main

class MyShell:
    def run_postoffice(self, argv):
        """Run postoffice with given arguments."""
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ["postoffice"] + argv
            return main()
        finally:
            sys.argv = original_argv
```

### Advanced Integration with Menu

```python
from bbsengine6 import io
from postoffice.__main__ import (
    handle_startup_check,
    handle_startup_generate,
    handle_startup_install,
    handle_startup_init,
)
import argparse

def show_postoffice_menu():
    """Show postoffice submenu."""
    menu = """
    Postoffice Password Management
    ==============================
    
    1. Check encryption key setup
    2. Generate new encryption key
    3. Install to /etc/postoffice/
    4. Initialize password system
    5. Back to main menu
    
    Choose (1-5): """
    
    choice = input(menu)
    args = argparse.Namespace(verbose=True)
    
    handlers = {
        "1": handle_startup_check,
        "2": handle_startup_generate,
        "3": handle_startup_install,
        "4": handle_startup_init,
    }
    
    if choice in handlers:
        handlers[choice](args)
    elif choice == "5":
        return
    
    input("\nPress Enter to continue...")
    show_postoffice_menu()
```

## Environment Variables

The postoffice module respects these environment variables:

```bash
# Encryption key (required) - MUST be same for all members/servers
export POSTOFFICE_PASSWORD_KEY=base64_encoded_key

# Optional: Cipher implementation (default: aes256gcm)
export PASSWORD_CIPHER=aes256gcm

# Optional: Storage implementation (default: postgresql)
export PASSWORD_STORAGE=postgresql
```

## Important: Single Encryption Key

⚠️ **The POSTOFFICE_PASSWORD_KEY must be identical across:**

- All members (Alice, Bob, Carol, etc.)
- All servers (IMAP, SMTP, Web, etc.)
- All deployments

If the key differs, password decryption will fail.

See ENCRYPTION_KEY_MANAGEMENT.md for details on key sharing across servers.

## Error Handling

All module functions return appropriate error codes:

```python
from postoffice.__main__ import init_postoffice

try:
    if not init_postoffice(args):
        print("Failed to initialize")
except Exception as e:
    print(f"Error: {e}")
```

## Example: Full Integration

```python
#!/usr/bin/env python
"""Example custom shell with postoffice integration."""

import sys
import argparse
from postoffice.__main__ import (
    init_postoffice,
    access_postoffice,
    help_postoffice,
    version_postoffice,
    handle_startup_check,
)

class PostofficeShell:
    """Simple shell with postoffice integration."""
    
    def __init__(self):
        self.args = argparse.Namespace(verbose=True)
        self.running = True
    
    def run(self):
        """Run the shell."""
        if not init_postoffice(self.args):
            print("Failed to initialize postoffice")
            sys.exit(1)
        
        print(help_postoffice(self.args))
        
        while self.running:
            try:
                cmd = input("\npostoffice> ").strip()
                if not cmd:
                    continue
                
                if cmd == "quit":
                    self.running = False
                elif cmd == "check":
                    handle_startup_check(self.args)
                elif cmd == "version":
                    print(version_postoffice(self.args))
                elif cmd == "help":
                    print(help_postoffice(self.args))
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                print("\nUse 'quit' to exit")
            except Exception as e:
                print(f"Error: {e}")
        
        print("Goodbye!")

if __name__ == "__main__":
    shell = PostofficeShell()
    shell.run()
```

## Testing Integration

```bash
# Test all commands
python -m postoffice startup-check
python -m postoffice startup-generate
python -m postoffice startup-init --verbose

# Run unit tests
export POSTOFFICE_PASSWORD_KEY=$(openssl rand -base64 32)
python -m pytest tests/ -v

# Test with user file
mkdir -p ~/.postoffice
openssl rand -base64 32 > ~/.postoffice/password.key
chmod 600 ~/.postoffice/password.key
python -m postoffice startup-check
```

## Command Reference

| Command | Purpose | Args | Exit Code |
|---------|---------|------|-----------|
| `startup-check` | Verify key setup | `--verbose` | 0=OK, 1=Failed |
| `startup-generate` | Create new key | - | Always 0 |
| `startup-install` | Install to /etc | - | 0=OK, 1=Failed |
| `startup-init` | Initialize system | `--verbose` | 0=OK, 1=Failed |

## Performance Considerations

- Key loading from files is cached after first access
- Module initialization is safe to call multiple times
- Password operations are encrypted/decrypted on-demand

## Security Considerations

- Never log encryption keys
- File permissions are strictly validated (0600 required)
- All password operations are validated before execution
- Access control is enforced at function level
- Use same key for all members and servers

