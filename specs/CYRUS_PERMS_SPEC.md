# cyrusperms() Function Specification

**Module:** `postoffice.lib`  
**Purpose:** Expand Cyrus IMAP permission letters into human-readable words

## Function Signature

```python
def cyrusperms(perms: str | list) -> str:
```

## Input

The `perms` argument accepts:
- **String**: Concatenated letters (`"lrs"`), comma-separated (`"l,r,s"`), space-separated (`"l r s"`), or IMAP ACL format (`"user.jam lrswcida"`)
- **List**: List of single-char strings (`["l", "r", "s"]`) or multi-char tokens (`["lrs", "wip"]`)

## Output

Returns a human-readable string with permissions separated by commas and joined with "and" (Oxford comma format).

## Supported Permissions

| Code | Word | Notes |
|------|------|-------|
| `l` | lookup | see mailbox in list |
| `r` | read | select, fetch messages |
| `s` | seen | track unseen count |
| `w` | write | set flags on messages |
| `i` | insert | append/copy into mailbox |
| `p` | post | submit to mailbox |
| `c` | create | create subfolder |
| `k` | create | create subfolder (alias) |
| `d` | delete | expunge messages |
| `e` | delete | delete folder |
| `n` | rename | rename folder |
| `t` | delete | soft expunge (delete messages) |
| `x` | delete mailbox | |
| `a` | admin | setacl |

## IMAP ACL String Handling

The IMAP `MYRIGHTS` response format is:
```
* MYRIGHTS user.jam lrswcida
```

When input contains a username prefix (detected by a space in the string), the function:
1. Splits on whitespace
2. Identifies tokens that consist entirely of known permission letters
3. Joins all matching tokens into a single permission string
4. Unknown multi-char tokens (e.g., `"user.jam"`) are skipped

## Examples

```python
>>> cyrusperms("lrs")
'lookup, read, and seen'

>>> cyrusperms("lr")
'lookup and read'

>>> cyrusperms("l,r,s")
'lookup, read, and seen'

>>> cyrusperms("l r s")
'lookup, read, and seen'

>>> cyrusperms("user.jam lrswipckt")
'lookup, read, seen, write, insert, post, create, create, and delete'

>>> cyrusperms(["l", "r", "s"])
'lookup, read, and seen'

>>> cyrusperms([])
''

>>> cyrusperms(None)
''
```

## Edge Cases

| Input | Output | Notes |
|-------|--------|-------|
| `""` | `""` | Empty string returns empty |
| `[]` | `""` | Empty list returns empty |
| `None` | `""` | None returns empty |
| `"abz"` | `"admin and z"` | `a`=admin, `b` unknown, `z` unknown |
| `"lrsXYZ"` | `"lookup, read, seen, X, Y, and Z"` | Mixed known/unknown |
| `"(user.jam lrswipckt)"` | `"lookup, read, seen, write, insert, post, create, create, and delete"` | Parentheses stripped by caller |

## Implementation Notes

- **Case insensitive**: Input is normalized to lowercase for matching
- **No side effects**: Always extracts permission tokens explicitly; no relying on implicit skip behavior
- **Pass-through**: Unknown single characters are passed through unchanged (uppercase preserved)
- **BBS tags**: Output may include `{var:*}` color tags from `bbsengine6.util.oxfordcomma()` for terminal display; use `strip_bbs_tags()` in tests to compare plain text

## Usage in Scripts

```python
from postoffice.lib import cyrusperms

# Direct usage
echo(f"My rights: {cyrusperms(myrights_str)}")

# With IMAP response
status, myrights = imap.myrights(mailbox)
if status == "OK":
    echo(f"My rights: {cyrusperms(myrights[0].decode().strip('() '))}")
```