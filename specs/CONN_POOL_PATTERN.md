# Connection Pool Pattern (CONN_POOL_PATTERN)

**Status:** REQUIRED - All database functions must follow this pattern

## Pattern Definition

All functions that accept database connections or connection pools MUST use the `def foo(args, **kwargs)` pattern with `conn` and `pool` as part of `**kwargs`.

### Signature Template

```python
def my_function(args, arg1: str, arg2: int, **kwargs) -> bool:
    """
    Description of function.
    
    Args:
        args: bbsengine6 args object
        arg1: First positional argument
        arg2: Second positional argument
        **kwargs: Optional - conn (database connection), pool (connection pool)
    
    Returns:
        True on success, False on error
    """
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")
    
    # ... rest of function
```

## Key Rules

1. **Always extract from kwargs**: Use `kwargs.get("conn")` and `kwargs.get("pool")`
2. **No explicit parameters**: Never use `conn=None, pool=None` as function parameters
3. **All optional**: Both `conn` and `pool` should be optional (None by default)
4. **Caller responsibility**: Caller decides whether to pass `conn` or `pool`
5. **Context managers**: When creating connections from pool, always use context managers:
   ```python
   with database.connect(args, pool=pool) as conn:
       # use conn
   ```

## Common Patterns

### Pattern 1: Function that reads from database

```python
def get_config(args, mailbox_name: str, **kwargs) -> dict:
    """Get configuration for mailbox."""
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")
    
    if conn is None and pool is None:
        return {}
    
    use_conn = conn
    should_close = False
    
    if use_conn is None and pool is not None:
        try:
            use_conn = database.connect(args, pool=pool)
            should_close = True
        except Exception as e:
            io.echo(f"Error: {e}", level="error")
            return {}
    
    if use_conn is None:
        return {}
    
    try:
        with database.cursor(use_conn) as cur:
            cur.execute("SELECT * FROM config WHERE mailbox = %s", [mailbox_name])
            return cur.fetchone() or {}
    except Exception as e:
        io.echo(f"Error: {e}", level="error")
        return {}
    finally:
        if should_close and use_conn:
            try:
                use_conn.close()
            except Exception:
                pass
```

### Pattern 2: Function that calls another function

```python
def process_message(args, uid: int, **kwargs) -> bool:
    """Process a message."""
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")
    
    # Call other functions with same kwargs
    result1 = helper_func1(args, uid, conn=conn, pool=pool)
    result2 = helper_func2(args, uid, conn=conn, pool=pool)
    
    return result1 and result2
```

### Pattern 3: Calling from startup (with pool)

```python
def main(args, **kwargs) -> bool:
    """Main initialization."""
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")
    
    # Call functions with explicit kwargs
    result = my_function(args, "arg1", 42, conn=conn, pool=pool)
    
    return result
```

## Migration Notes

**IMPORTANT**: Previous versions used explicit `conn=None, pool=None` parameters. This has been **DEPRECATED** in favor of `**kwargs` pattern.

### Old Pattern (DEPRECATED)
```python
def fire_event(args, event: str, conn=None, pool=None) -> bool:  # ❌ WRONG
    pass
```

### New Pattern (REQUIRED)
```python
def fire_event(args, event: str, **kwargs) -> bool:  # ✅ CORRECT
    conn = kwargs.get("conn")
    pool = kwargs.get("pool")
    pass
```

## Files Updated

All of these files now follow CONN_POOL_PATTERN:

- `src/postoffice/notifyd_client.py`
  - `is_event_enabled()` - uses **kwargs
  - `get_routing_rules()` - uses **kwargs
  - `fire_event()` - uses **kwargs

- `src/postoffice/imap_client.py`
  - `claim_message()` - uses **kwargs
  - `unclaim_message()` - uses **kwargs
  - `fire_new_message_event()` - uses **kwargs
  - `fire_flag_changed_event()` - uses **kwargs
  - `fire_message_deleted_event()` - uses **kwargs

- `src/postoffice/imap_monitor.py`
  - `__init__()` - accepts pool parameter
  - `_get_poll_interval()` - uses pool with context manager
  - `initialize_monitor()` - accepts pool parameter

- `src/postoffice/startup.py`
  - `_work()` - receives and passes pool through kwargs

## Test Expectations

Tests must call functions with kwargs:

```python
# ✅ CORRECT
result = fire_event(args, "message-claimed", event_data, conn=conn)
result = fire_event(args, "message-claimed", event_data, pool=pool)

# ❌ WRONG
result = fire_event(args, "message-claimed", event_data, close_conn=False)  # Parameter doesn't exist
```

## Rationale

1. **Cleaner API**: Reduces function signature clutter
2. **bbsengine6 Compatibility**: Matches bbsengine6's own pattern
3. **Flexibility**: Callers can pass either conn or pool without forcing both
4. **Future-proof**: Easy to add new optional parameters later
5. **Consistency**: All database functions use same signature style

## References

- bbsengine6 `database.py`: Uses this pattern throughout
- empyre `player.py`: Follows this pattern
- murdermotel startup: Follows this pattern
