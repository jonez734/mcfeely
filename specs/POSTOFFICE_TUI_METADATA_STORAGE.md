# Postoffice TUI - Metadata Storage Strategy

## Overview
Message metadata is stored in **two locations** for redundancy and performance:
1. **IMAP Message Flags** (primary) - Portable, travels with message
2. **Database** (backup) - For queries and analysis

## Dual Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│         Message Metadata (projectid, claimed, hash)         │
├──────────────────────────┬──────────────────────────────────┤
│                          │                                  │
│  IMAP Message Flags      │  Database (postoffice)           │
│  ──────────────────      │  ───────────────────             │
│  Metadata_<base64>       │  __message.metadata (JSONB)      │
│  - Portable              │  - Queryable                     │
│  - Real-time sync        │  - Backup/audit trail           │
│  - No DB dependency      │  - Historical tracking          │
│                          │                                  │
└──────────────────────────┴──────────────────────────────────┘
```

## IMAP Flag Storage

### Format
Custom IMAP flag format: `Metadata_<base64-encoded-json>`

### Example
```
Message has flags: \Seen, \Flagged, Metadata_eyJwcm9qZWN0aWQiOiA0MiwgImNsYWltZWQiOiB0cnVlfQ==
```

When decoded:
```json
{"projectid": 42, "claimed": true, "claimed_by_hash": "abc123..."}
```

### Why Base64?
- IMAP flags are space-separated and must be alphanumeric
- Base64 encoding allows storing complex JSON safely
- Easy to encode/decode without additional dependencies
- IMAP server compatibility

### Advantages
✓ **Portable** - Moves with message if forwarded/synced
✓ **Distributed** - Each IMAP server has copy
✓ **Real-time** - Immediately visible to all clients
✓ **No DB dependency** - Works even if database unavailable
✓ **Standard** - Uses IMAP protocol features

### Limitations
✗ **Flag count** - Some servers limit total flags (~1000)
✗ **Query** - Cannot query IMAP flags directly
✗ **Sync** - Custom flags may not sync across all servers

## Database Storage

### Schema
```sql
CREATE TABLE postoffice.__message (
    id text UNIQUE NOT NULL PRIMARY KEY,
    claimedbymoniker text REFERENCES engine.__member(moniker),
    dateclaimed timestamptz,
    metadata jsonb DEFAULT NULL
);
```

### Format
JSONB column stores complete metadata:

```json
{
    "projectid": 42,
    "claimed": true,
    "claimed_by_hash": "sha256:abc123def456..."
}
```

### Advantages
✓ **Queryable** - Find messages by project ID
✓ **Audit trail** - Can track history with timestamps
✓ **Backup** - Metadata survives IMAP flag loss
✓ **Analysis** - Can generate reports

### Limitations
✗ **Database dependent** - Requires working DB connection
✗ **Synchronization** - Must manually sync if IMAP flags change
✗ **Migration** - Moving message to different server loses DB data

## Metadata Fields

### projectid
- **Type**: Integer
- **Purpose**: Associate message with project/ticket
- **Example**: `42`, `1001`
- **Storage**: Both IMAP flag and DB
- **Sync**: IMAP flag is source of truth

### claimed
- **Type**: Boolean
- **Purpose**: Mark message as claimed/owned
- **Values**: `true` or `false`
- **Storage**: Both IMAP flag and DB
- **Sync**: IMAP flag is source of truth

### claimed_by_hash
- **Type**: String (SHA256 hex)
- **Purpose**: Privacy-preserving claim tracking
- **Format**: `sha256:abcdef0123456789...`
- **Storage**: Both IMAP flag and DB
- **Sync**: IMAP flag is source of truth
- **Privacy**: Only hash stored, not plaintext username

## Synchronization Strategy

### Write Operation (Set Metadata)
```
User action (tag, claim)
    ↓
Update IMAP message flag (primary)
    ↓
Update database (backup)
    ↓
Success message to user
```

### Read Operation (Get Metadata)
```
List messages or view detail
    ↓
Read IMAP flags first
    ↓
Return metadata from flags
    ↓
(If flag unreadable, fallback to DB)
```

### Sync Direction
- **IMAP flags → Database**: Manual sync (can be added later)
- **Database → IMAP flags**: Automatic on write

## Implementation Details

### Encoding Metadata to Flag

```python
metadata = {"projectid": 42, "claimed": True}
metadata_json = json.dumps(metadata)
# '{"projectid": 42, "claimed": true}'

encoded = base64.b64encode(metadata_json.encode()).decode()
# 'eyJwcm9qZWN0aWQiOiA0MiwgImNsYWltZWQiOiB0cnVlfQ=='

flag = f"Metadata_{encoded}"
# 'Metadata_eyJwcm9qZWN0aWQiOiA0MiwgImNsYWltZWQiOiB0cnVlfQ=='

# Set in IMAP
imap.uid("STORE", uid, "+FLAGS", f"({flag})")
```

### Decoding Metadata from Flag

```python
# Get all flags
flags = imap_lib.get_message_flags(imap, uid)
# {'\\Seen', 'Metadata_eyJwcm9qZWN0aWQiOiA0MiwgImNsYWltZWQiOiB0cnVlfQ=='}

# Find metadata flag
for flag in flags:
    if flag.startswith("Metadata_"):
        encoded = flag[9:]  # Remove "Metadata_" prefix
        json_data = base64.b64decode(encoded).decode()
        metadata = json.loads(json_data)
        # {"projectid": 42, "claimed": true, "claimed_by_hash": "..."}
```

## Failure Scenarios

### IMAP Flag Write Fails
```
1. Try to set metadata in IMAP flag
2. If fails → Database write attempted
3. User sees: "Warning: metadata not stored in message"
```

### Database Write Fails
```
1. IMAP flag set successfully ✓
2. Database write fails ✗
3. User sees: "Warning: metadata backup failed"
4. Data not lost - IMAP flag has it
```

### IMAP Flag Corrupted/Lost
```
1. Read IMAP flags → Fails to parse
2. Try database → Success
3. Repair IMAP flag from DB (future feature)
4. User continues without disruption
```

### Both Stores Fail
```
1. Cannot write IMAP flag
2. Cannot write database
3. User sees error
4. Action rolled back, no metadata saved
```

## Performance Considerations

### Read Path
- **Speed**: Fast (single IMAP FETCH command)
- **Latency**: Network latency only
- **Caching**: IMAP server may cache flags

### Write Path
- **Speed**: Slower (2 writes: IMAP + DB)
- **Latency**: ~100-200ms typical
- **Atomicity**: IMAP write before DB ensures at least IMAP has it

### List Display
- **Current**: Fetch metadata for each message in display
- **Optimization**: Batch flag fetch possible with future updates
- **Expected**: <1s for 20 messages

## Migration & Upgrade Path

### Upgrading to Metadata Support
1. Database schema change (add metadata column)
2. TUI code update (add metadata functions)
3. No data migration needed - metadata stored on-demand

### Migrating Messages Between Servers
- IMAP flags migrate with message (automatic)
- Database metadata stays on old server (needs manual export/import)
- Recommend: Regenerate metadata flags on new server

### Backup & Recovery
- Export metadata: `SELECT id, metadata FROM postoffice.__message`
- Restore: Re-import to database, regenerate IMAP flags

## Security Considerations

### Privacy
- Only SHA256 hash of username stored (in both locations)
- Cannot reverse hash to get username
- Other users cannot determine who claimed message

### Data Integrity
- JSONB in database supports schema validation (future)
- IMAP flags are immutable once set
- Audit trail possible via DB timestamps

### Access Control
- User can only claim their own messages (via current_user context)
- Sysop can manage all users (is_sysop flag available)
- Future: Add permission checks

## Troubleshooting

### Metadata Not Persisting
Check both locations:
```bash
# Check IMAP flag
grep -r "Metadata_" messages

# Check database
SELECT id, metadata FROM postoffice.__message WHERE metadata IS NOT NULL

# If in IMAP but not DB: Database connection issue
# If in DB but not IMAP: Message was moved/copied
```

### Metadata Flag Format Error
Error: "Error retrieving metadata from flags"
- Flag may be corrupted
- Try clearing: `imap.uid("STORE", uid, "-FLAGS", "(Metadata_...)")`
- Re-tag message to recreate

### Database Out of Sync
Use IMAP as source of truth:
```python
# Export from IMAP
for msg in messages:
    metadata = get_from_imap_flags(msg)
    if metadata:
        store_to_db(msg, metadata)
```

## Future Enhancements

### High Priority
- [ ] Batch flag fetch for performance
- [ ] Automatic sync: IMAP → Database
- [ ] Metadata validation schema
- [ ] Repair tool: DB → IMAP

### Medium Priority
- [ ] Export/import metadata
- [ ] Metadata history tracking
- [ ] Query builder for metadata
- [ ] Metadata replication to shared mailbox

### Low Priority
- [ ] Compress metadata (gzip)
- [ ] Encrypt metadata in IMAP flags
- [ ] Metadata versioning
- [ ] Distributed metadata index

## Code References

### Key Functions

| Function | Purpose |
|----------|---------|
| `_get_message_metadata_from_flags()` | Read from IMAP |
| `_set_message_metadata()` | Write to IMAP + DB |
| `_store_metadata_to_db()` | Write to DB only |

### Implementation Details
- File: `postoffice/tui/message_interface.py`
- IMAP operations via `imap_lib.get_message_flags()`
- DB operations via `lib.get_db_connection()`

## See Also

- [POSTOFFICE_TUI_ENHANCED_FEATURES.md](./POSTOFFICE_TUI_ENHANCED_FEATURES.md) - Feature overview
- [POSTOFFICE_TUI_QUICK_GUIDE.md](./POSTOFFICE_TUI_QUICK_GUIDE.md) - User guide
- `postoffice/tui/message_interface.py` - Implementation
- `sql/message.sql` - Database schema
