# Postoffice TUI - Enhanced Message Features

## Overview
The message interface now supports three new key commands for message management:
1. **ENTER** - View detailed message (with ability to take actions)
2. **t (or T)** - Tag message with a project ID
3. **c (or C)** - Claim/Unclaim message with hashed user identity

## New Features

### 1. ENTER Key - View Message and Return to List

**Behavior:**
- Press ENTER to select and view a message
- Message displays with full headers and body
- View metadata (if any project ID or claim status)
- Take actions on the message (see below)
- Press any key to return to message list
- List automatically refreshes and redisplays

**Use Case:**
Reading messages in detail without leaving the TUI entirely.

### 2. 't' Key - Tag Message with Project ID

**Behavior:**
- In message list: Press 't' to tag selected message
- In message detail: Press 't' to tag current message
- Prompts for numeric Project ID
- Stores project ID in message metadata (database)
- List shows `[P:12345]` indicator next to tagged messages
- Supports multiple projects across different messages

**Use Case:**
Organizing messages by project for tracking/management.

**Example:**
```
Enter project ID (or press ENTER to cancel): 42
Message tagged with project ID 42
```

**Storage:**
- Stored in `postoffice.__message.metadata` (JSONB)
- Example: `{"projectid": 42}`

### 3. 'c' Key - Claim/Unclaim Message

**Behavior:**
- In message list: Press 'c' to claim/unclaim selected message
- In message detail: Press 'c' to claim/unclaim current message
- First press: Claims message, stores hash of current user's login ID
- Second press: Unclaims message, removes claim hash
- List shows `[C]` indicator next to claimed messages
- Privacy-preserving: Only hash of user ID stored, not plaintext

**Use Case:**
Team coordination - mark messages you're working on or responsible for.

**Example:**
```
Message claimed by username
```

**Storage:**
- Stored in `postoffice.__message.metadata` (JSONB)
- Example: `{"claimed": true, "claimed_by_hash": "abc123..."}`

## Message List Display

### Status Indicators
Messages now display status indicators in the list:

```
[C] [P:42] sender@example.com Important Update
    ^  ^
    |  +-- Project ID indicator
    +------ Claim indicator
```

- `[C]` appears if message is claimed
- `[P:12345]` appears if message has project ID tagged
- Multiple indicators can appear together
- Indicators appear before sender/subject

### Key Reference

| Key | Location | Action |
|-----|----------|--------|
| UP/DOWN | List | Navigate cursor |
| ENTER | List | View message, then return to list |
| DEL | List/Detail | Delete message |
| t/T | List/Detail | Tag with project ID |
| c/C | List/Detail | Claim/unclaim message |
| r/R | Detail | Reply (not yet implemented) |
| f/F | Detail | Forward (not yet implemented) |
| ESC | List | Exit message list |
| Any key | Detail | Return to message list |

## Database Schema

### Updated message Table

```sql
CREATE TABLE postoffice.__message (
    id text UNIQUE NOT NULL PRIMARY KEY,
    claimedbymoniker text REFERENCES engine.__member(moniker),
    dateclaimed timestamptz,
    metadata jsonb DEFAULT NULL
);
```

### Metadata Structure

The `metadata` JSONB column stores:

```json
{
    "projectid": 42,
    "claimed": true,
    "claimed_by_hash": "sha256:abc123def456..."
}
```

**Fields:**
- `projectid` (integer, optional): Project ID to associate with message
- `claimed` (boolean, optional): Whether message is claimed
- `claimed_by_hash` (string, optional): SHA256 hash of claiming user's login ID

## Implementation Details

### Message Metadata Functions

#### `_get_message_metadata(uid: int) -> Optional[Dict]`
Retrieves message metadata from database.

```python
metadata = self._get_message_metadata(msg["uid"])
if metadata and metadata.get("projectid"):
    print(f"Project: {metadata['projectid']}")
```

#### `_set_message_metadata(uid: int, metadata: Dict) -> bool`
Stores message metadata to database. Creates record if needed.

```python
metadata = {"projectid": 42, "claimed": True, "claimed_by_hash": "..."}
self._set_message_metadata(uid, metadata)
```

### Claim Hash Function

Uses SHA256 hash of username for privacy:

```python
claim_hash = hashlib.sha256(self.current_user.encode()).hexdigest()
```

Benefits:
- Cannot reverse engineer username from hash
- Same user always produces same hash
- Different users produce different hashes
- Supports audit logging without exposing user identities

## Workflow Examples

### Example 1: Tagging Messages for a Project

```
1. Launch TUI: python -m postoffice
2. List messages (default action)
3. Navigate to message about project requirements
4. Press 't'
5. Enter project ID: 42
6. Message now shows [P:42] in list
7. Continue with other messages for same project
```

### Example 2: Team Coordination with Claims

```
1. Launch TUI: python -m postoffice
2. List messages (default action)
3. See message: "[ ] [ ] john@example.com Bug fix needed"
4. Press 'c' to claim
5. Message shows [C] indicating you claimed it
6. List shows [C] next to message
7. Other users see [C] but don't see who claimed it
8. Press 'c' again to unclaim when done
```

### Example 3: Viewing Message Details

```
1. List messages
2. Press ENTER on a message
3. See full details with metadata section
4. Can take actions (t, c, del, etc.)
5. Press any key to return to list
6. List refreshes and shows updated indicators
```

## Error Handling

### Invalid Project ID
```
Enter project ID (or press ENTER to cancel): abc
Invalid project ID - must be a number
```

### Database Connection Issues
```
Warning: Could not connect to database for metadata: ...
(TUI continues without metadata support)
```

### Claim Without Database
```
Database not available
```

## Integration with Existing Code

### Database Connection
Uses `lib.get_db_connection(args)` for database access.

### IMAP Operations
Uses existing `imap_lib` functions for message operations.

### User Context
Uses `args.loginid` for current user identification.

## Future Enhancements

### High Priority
- [ ] Implement delete confirmation dialog
- [ ] Persist metadata to shared mailbox metadata
- [ ] Show who claimed message (with user permission)
- [ ] Tag messages with multiple projects
- [ ] Add metadata to message detail view header

### Medium Priority
- [ ] Export metadata to CSV/JSON
- [ ] Import metadata from file
- [ ] Sync metadata across shared mailbox
- [ ] Metadata search/filter
- [ ] Message status indicators (open, in progress, done)

### Low Priority
- [ ] Message priority levels
- [ ] Due dates for messages
- [ ] Notes/comments on messages
- [ ] Attachment tracking
- [ ] Message relationships (linked messages)

## Testing

### Syntax Validation
```bash
python -m py_compile postoffice/tui/message_interface.py
```

### Database Migration
```bash
# Apply schema change to database
psql -d postoffice -f sql/message.sql
```

### Manual Testing
```bash
cd mistermcfeely/src
python -m postoffice

# Use 't' to tag messages
# Use 'c' to claim/unclaim
# Check database for metadata
psql -d postoffice -c "SELECT id, metadata FROM postoffice.__message WHERE metadata IS NOT NULL"
```

## Code References

### Key Functions in message_interface.py

- `_show_message_list()`: Display list with metadata indicators
- `_message_detail()`: Show message with metadata section
- `_tag_message()`: Handle project ID tagging
- `_claim_message()`: Handle claim/unclaim with hash
- `_get_message_metadata()`: Retrieve from DB
- `_set_message_metadata()`: Store to DB

### Key Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_tag_message(uid)` | `uid: int -> None` | Tag message with project ID |
| `_claim_message(uid)` | `uid: int -> None` | Claim/unclaim message |
| `_get_message_metadata(uid)` | `uid: int -> Optional[Dict]` | Get metadata from DB |
| `_set_message_metadata(uid, meta)` | `uid: int, meta: Dict -> bool` | Store metadata to DB |

## Security Considerations

### Privacy
- Only hash of username stored, not plaintext
- Other users cannot determine who claimed message from hash
- Can add audit logging without exposing identities

### Data Integrity
- JSONB supports validation via constraints
- Transactions used for data consistency
- Rollback on errors

### Access Control
- User can only claim/tag their own messages (via current_user context)
- Future: could add permission checks
- Sysop could manage all users' claims (is_sysop flag available)

## Performance Notes

- Metadata stored in JSONB for flexibility
- Simple SELECT/UPDATE queries (indexed by id)
- No N+1 queries - metadata loaded on detail view
- List refresh fetches only needed indicators

## See Also

- [POSTOFFICE_TUI_QUICK_GUIDE.md](./POSTOFFICE_TUI_QUICK_GUIDE.md)
- [POSTOFFICE_TUI_IMPLEMENTATION.md](./POSTOFFICE_TUI_IMPLEMENTATION.md)
- `postoffice/tui/message_interface.py` - Implementation
- `sql/message.sql` - Schema
