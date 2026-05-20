# Analysis: mistermcfeely notifyd_client vs bbsengine6 notify Integration

**Date:** May 20, 2026  
**Question:** Can notifyd_client.py and the notify subpackage be cleanly merged?

---

## Executive Summary

**Answer: PARTIAL YES with architectural caveats**

The systems are fundamentally compatible but serve different purposes:
- **bbsengine6/notify** - Generic event notification system (templating, rate limiting, recipient expansion)
- **mistermcfeely/notifyd_client** - IMAP-specific routing with pattern matching and custom flag obfuscation

A clean merge is possible, but requires understanding the design differences and use cases.

---

## System Comparison

### bbsengine6/notify.send()

```python
def send(
    notification_type: str,          # "email-received", "chat-message", etc.
    recipients: List[str],           # ["alice@example.com", "user:bob"]
    template: str,                   # Template name from engine.__notify_type
    template_vars: Optional[Dict]    # Variables for template rendering
    sender_moniker: Optional[str]    # Who sent it
    data: Optional[Dict]             # Event payload
    urgency: Optional[Urgency]       # ROUTINE, IMPORTANT, CRITICAL
    should_persist: bool = True,     # Save in database
    conn: Optional[Connection]       # Database connection
) -> Notification
```

**Features:**
- ✅ Template-based message rendering (from database or defaults)
- ✅ Recipient expansion (user lists, groups, etc.)
- ✅ Rate limiting (configurable per-type, per-user, per-hour)
- ✅ Auto-registration of event types
- ✅ JSON payload storage
- ✅ Urgency levels (ROUTINE, IMPORTANT, CRITICAL, URGENT)

**Limitations:**
- ❌ No pattern-based routing (hardcoded recipient expansion)
- ❌ No IMAP-specific integration (no flag obfuscation)
- ❌ Generic design (doesn't understand mailbox contexts)

### mistermcfeely/notifyd_client.fire_event()

```python
def fire_event(
    args,                            # bbsengine6 args object
    mailbox_name: str,              # 'shared/support@example.com'
    event_type: str,                # 'message-claimed', 'message-new', etc.
    event_data: Dict[str, Any],     # Event payload
    actor_moniker: Optional[str]    # Who triggered it
    **kwargs                         # conn, pool for database access
) -> bool
```

**Features:**
- ✅ Pattern-based routing (SQL LIKE patterns: 'shared/%', 'shared/support%')
- ✅ Actor-based filtering (NULL matches any, patterns for roles)
- ✅ Per-mailbox configuration (enable/disable events, polling intervals)
- ✅ IMAP-specific (claim flags, message state)
- ✅ Custom obfuscation (HMAC-SHA256 for flag privacy)
- ✅ Flexible (mailbox context aware)

**Limitations:**
- ❌ No recipient expansion (uses routing table directly)
- ❌ No rate limiting (assumes mailbox-based throttling)
- ❌ No templating (renders messages inline)
- ❌ No auto-registration (types pre-configured in postoffice schema)

---

## Integration Points

### 1. Backend Storage (engine.__notify table)
✅ **COMPATIBLE** - Both use identical schema

```sql
INSERT INTO engine.__notify (
    notification_type,      -- "mcfeely-message-claimed", "email-received"
    sender_moniker,         -- "alice", "system"
    template,               -- Template name (often same as type)
    rendered_message,       -- Human-readable text
    data,                   -- JSON event payload
    urgency,                -- ROUTINE, IMPORTANT, CRITICAL
    should_persist          -- TRUE
)
```

### 2. Notification Types
✅ **COMPATIBLE** - Both register in engine.__notify_type

```sql
INSERT INTO engine.__notify_type (
    type_name,              -- "mcfeely-message-claimed"
    default_urgency,        -- ROUTINE, IMPORTANT
    max_per_user_per_hour,  -- Rate limit
    persist_by_default      -- TRUE/FALSE
)
```

### 3. Recipients
⚠️ **DIFFERENT APPROACHES**

**bbsengine6/notify:**
- Recipients list: `["user:alice", "group:support-team", "email:admin@example.com"]`
- Expansion happens inside send() via _expand_recipients()
- Supports groups, role-based delivery

**mistermcfeely/notifyd_client:**
- Recipients from SQL routing table: `postoffice.notification_routing`
- SQL LIKE pattern matching: `mailbox_name LIKE 'shared/%'` matches all shared
- Actor-based filtering: `actor_moniker IS NULL` matches any actor

---

## Merge Strategy Options

### Option A: Replace notifyd_client with bbsengine6/notify (PARTIAL)

**Pros:**
- Consolidate codebases
- Use standardized rate limiting
- Leverage recipient expansion
- Less code to maintain

**Cons:**
- Loss of pattern-based routing (would need to enumerate all mailboxes)
- Loss of per-mailbox configuration
- Less flexible for IMAP-specific use cases
- Would require migrating postoffice.notification_routing → engine.__notify_recipient

**Verdict:** ❌ Too much loss of functionality

---

### Option B: Keep notifyd_client, use notify as transport layer (HYBRID)

**Architecture:**

```python
# notifyd_client.py (routing layer)
def fire_event(args, mailbox_name, event_type, event_data, **kwargs):
    """
    1. Check if event enabled (postoffice.notification_config)
    2. Get routing rules (postoffice.notification_routing) with LIKE patterns
    3. For each recipient, call notify.send()
    """
    
    # Get routing rules (pattern-based)
    rules = get_routing_rules(args, mailbox_name, event_type, actor_moniker, **kwargs)
    
    for rule in rules:
        # Use bbsengine6/notify to send
        recipients = [rule['recipient_moniker']]
        notify.send(
            notification_type=rule['notification_type'],
            recipients=recipients,
            template=rule['notification_type'],
            sender_moniker=actor_moniker,
            data=event_data,
            urgency=rule['urgency'],
            should_persist=True,
            conn=use_conn,
        )
```

**Pros:**
- Keep pattern-based routing (IMAP-specific advantage)
- Use standardized notify backend (rate limiting, etc.)
- Consolidate recipient insertion logic
- Less code duplication

**Cons:**
- Requires postoffice.notification_type table
- Requires updating recipient insertion (notify.send expects recipients list)
- Adds dependency on bbsengine6/notify module
- Slight performance overhead (additional layer)

**Verdict:** ✅ **RECOMMENDED** - Best of both worlds

---

### Option C: Enhance bbsengine6/notify to support pattern-based routing (FULL MERGE)

**Would require:**

1. Add pattern matching to notify.send():
```python
def send(
    ...,
    mailbox_pattern: Optional[str] = None,  # "shared/%" for LIKE matching
    actor_filter: Optional[str] = None,     # "alice%" for actor-based rules
    ...,
)
```

2. Modify recipient expansion logic:
```python
def _expand_recipients(recipients, mailbox_pattern, actor_filter, cur):
    """
    If pattern provided, query routing table instead of expanding from list.
    Otherwise use existing group/user expansion.
    """
```

3. Move postoffice schema to bbsengine6

**Pros:**
- True single API for all notifications
- Maximizes code reuse
- Pattern matching becomes generic feature

**Cons:**
- Large refactor in bbsengine6
- Adds IMAP-specific concepts to generic system
- Breaking change for existing notify.send() callers
- Ties bbsengine6 to postoffice schema

**Verdict:** ❌ Too invasive, not worth the complexity

---

## Recommended Implementation: Hybrid Approach (Option B)

### Step 1: Enhance notifyd_client.fire_event()

```python
def fire_event(
    args,
    mailbox_name: str,
    event_type: str,
    event_data: Dict[str, Any],
    actor_moniker: Optional[str] = None,
    **kwargs,
) -> bool:
    """
    Fire event via bbsengine6/notify integration.
    
    Uses pattern-based routing from postoffice.notification_routing,
    then delegates to notify.send() for actual delivery.
    """
    
    use_conn, should_close = lib.get_db_connection(args, **kwargs)
    
    if use_conn is None:
        io.echo("notifyd_client.fire_event: no connection or pool provided", level="error")
        return False
    
    try:
        # Check if event enabled
        if not is_event_enabled(args, mailbox_name, event_type, conn=use_conn):
            return True
        
        # Get routing rules (pattern-based)
        rules = get_routing_rules(
            args, mailbox_name, event_type, actor_moniker, conn=use_conn
        )
        
        if not rules:
            return True  # No routes = success
        
        # Fire event for each recipient via notify.send()
        failcount = 0
        for rule in rules:
            try:
                # Use bbsengine6/notify as transport layer
                from bbsengine6 import notify
                
                notify.send(
                    notification_type=rule["notification_type"],
                    recipients=[rule["recipient_moniker"]],
                    template=rule["notification_type"],
                    sender_moniker=actor_moniker,
                    data=event_data,
                    urgency=rule["urgency"],
                    should_persist=True,
                    conn=use_conn,
                )
                
                if getattr(args, "debug", False):
                    io.echo(
                        f"notifyd_client: fired {event_type} to {rule['recipient_moniker']}",
                        level="debug",
                    )
                
            except Exception as e:
                io.echo(
                    f"notifyd_client.fire_event.200: failed to fire event: {e}",
                    level="error",
                )
                failcount += 1
        
        use_conn.commit()
        return failcount == 0
    
    finally:
        if should_close and use_conn:
            try:
                use_conn.close()
            except Exception:
                pass
```

### Step 2: Keep postoffice.notification_routing for pattern matching

No changes needed - SQL LIKE patterns stay as-is

### Step 3: Ensure notification_type exists in engine.__notify_type

```sql
-- Ensure mcfeely notification types are registered
INSERT INTO engine.__notify_type 
(type_name, default_urgency, max_per_user_per_hour, persist_by_default)
VALUES
    ('mcfeely-message-new', 'ROUTINE', 10, true),
    ('mcfeely-message-claimed', 'IMPORTANT', 5, true),
    ('mcfeely-message-unclaimed', 'ROUTINE', 5, true),
    ('mcfeely-message-flagged', 'ROUTINE', 10, true),
    ('mcfeely-message-deleted', 'ROUTINE', 10, true)
ON CONFLICT (type_name) DO NOTHING;
```

### Step 4: Update startup.py

```python
# Ensure notification types are registered on startup
def main(args, **kwargs) -> bool:
    def _work(conn, pool=None):
        # ... existing schema creation ...
        
        # Register notification types
        io.echo("{{var:labelcolor}}notify types{{var:labelcolor}}: ", end="")
        try:
            with database.cursor(conn) as cur:
                cur.execute("""
                    INSERT INTO engine.__notify_type 
                    (type_name, default_urgency, max_per_user_per_hour, persist_by_default)
                    VALUES
                        ('mcfeely-message-new', 'ROUTINE', 10, true),
                        ('mcfeely-message-claimed', 'IMPORTANT', 5, true),
                        ('mcfeely-message-unclaimed', 'ROUTINE', 5, true),
                        ('mcfeely-message-flagged', 'ROUTINE', 10, true),
                        ('mcfeely-message-deleted', 'ROUTINE', 10, true)
                    ON CONFLICT (type_name) DO NOTHING
                """)
            io.echo("ok", level="ok")
        except Exception as e:
            io.echo(f"fail ({e})", level="error")
```

---

## Benefits of Hybrid Approach

### For mistermcfeely:
- ✅ Keeps pattern-based routing (IMAP-specific advantage)
- ✅ Leverages bbsengine6's rate limiting
- ✅ Uses standardized notify backend
- ✅ Less code to maintain (no direct INSERT logic)

### For bbsengine6:
- ✅ One more consumer of notify.send()
- ✅ Validates notify API
- ✅ No changes needed (backward compatible)

### For deployment:
- ✅ Cleaner architecture
- ✅ Single code path for all notifications
- ✅ Standardized rate limiting
- ✅ Shared troubleshooting/monitoring

---

## Migration Path (if desired)

1. **Phase 1:** Keep current notifyd_client, verify send() integration works
2. **Phase 2:** Run both in parallel, compare event insertion counts
3. **Phase 3:** Deprecate direct INSERT, fully migrate to notify.send()
4. **Phase 4:** Remove custom insertion code from notifyd_client

This allows safe migration with rollback capability.

---

## Compatibility Matrix

| Aspect | Current | Hybrid | Full Merge |
|--------|---------|--------|-----------|
| Pattern routing | ✅ Native | ✅ Native | ❌ Lost |
| Rate limiting | ❌ None | ✅ Via notify | ✅ Via notify |
| Recipient expansion | ❌ None | ✅ Via notify | ✅ Via notify |
| Per-mailbox config | ✅ Native | ✅ Native | ⚠️ Requires migration |
| Code duplication | ⚠️ INSERT logic | ✅ None | ✅ None |
| Complexity | Low | Medium | High |
| Breaking changes | None | None | Significant |

---

## Conclusion

**Recommended approach: Option B (Hybrid)**

A clean merge is possible by using bbsengine6/notify.send() as the transport layer while keeping mistermcfeely's pattern-based routing logic. This gives us:

- Best of both worlds (pattern matching + rate limiting)
- Minimal code changes
- No breaking changes
- Improved maintainability
- Standardized notification backend

The key insight: mistermcfeely isn't competing with bbsengine6/notify, it's a *specialization* of it for IMAP events. By treating notify.send() as the transport layer, we get consolidation without losing IMAP-specific advantages.

