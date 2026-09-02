# tui/message_interface.py
# Text User Interface for reading and managing postoffice messages

import email
import imaplib
import json
import base64
from typing import Any, List, Dict, Optional
from bbsengine6.io import echo
from bbsengine6.io.inputchoice import inputchoice
from bbsengine6.io.getch import getch_str as getch
from bbsengine6.listbox import Listbox, ListboxItem, ListboxResult
from .. import imap_lib, lib, imap_client


class MessageInterface:
    """Interactive TUI for reading and managing IMAP messages."""

    def __init__(self, args: Any):
        self.args = args
        self.current_user = getattr(args, "loginid", None)
        self.is_sysop = getattr(args, "issuperuser", False)
        self.messages: List[Dict[str, Any]] = []
        self.imap: Optional[imaplib.IMAP4_SSL] = None
        self.db: Optional[Any] = None

    def run(self) -> int:
        """Main TUI loop. Returns exit code."""
        if not self.current_user:
            echo("Error: Could not determine current user", level="error")
            return 1

        # Get database connection for metadata operations
        self.db = lib.get_db_connection(self.args)
        if self.db is None:
            echo(
                "Warning: Could not connect to database for metadata",
                level="error",
            )
            # Continue anyway, just without database metadata support

        while True:
            echo("")
            echo("=== postoffice ===", level="info")
            echo(f"User: {self.current_user}")
            echo("")

            choice = inputchoice(
                "Choose action: ",
                "nlx",
                default="l",
                help="(n)ew message, (l)ist messages, e(x)it",
            )

            if choice == "N":
                self._compose_new_message()
            elif choice == "L":
                self._list_messages()
            elif choice == "X":
                echo("Goodbye!")
                return 0

    def _compose_new_message(self) -> None:
        """Handle composing a new message."""
        echo("")
        echo("=== New Message ===", level="info")
        echo("(Not yet implemented)")

    def _list_messages(self) -> None:
        """List messages from IMAP and allow management."""
        # Connect to IMAP and fetch messages
        try:
            self.imap = self._connect_imap()
            if not self.imap:
                echo("Could not connect to IMAP server", level="error")
                return

            self._fetch_messages()

            if not self.messages:
                echo("No messages found", level="info")
                if self.imap:
                    self.imap.logout()
                return

            # Display message list with cursor
            self._show_message_list()

        except Exception as e:
            echo(f"Error listing messages: {e}", level="error")
        finally:
            if self.imap:
                try:
                    self.imap.logout()
                except Exception:
                    pass

    def _connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to IMAP server for current user."""
        try:
            creds = imap_lib.get_imap_credentials(self.args, member_moniker=self.current_user)
            if not creds:
                echo("Could not get IMAP credentials", level="error")
                return None

            imap = imap_lib.connect_cyrus(creds)
            return imap
        except Exception as e:
            echo(f"IMAP connection error: {e}", level="error")
            return None

    def _fetch_messages(self) -> None:
        """Fetch messages from INBOX."""
        try:
            if not self.imap:
                return

            # Select INBOX
            imap_lib.select_mailbox(self.imap, "INBOX")

            # Get all message UIDs
            uids = imap_lib.get_all_uids(self.imap)

            self.messages = []
            for uid in sorted(uids):
                headers = imap_lib.get_message_headers(self.imap, uid)
                if headers:
                    self.messages.append(
                        {
                            "uid": uid,
                            "from": headers.get("from_addr", "Unknown"),
                            "subject": headers.get("subject", "(no subject)"),
                            "date": headers.get("date", ""),
                        }
                    )

        except Exception as e:
            echo(f"Error fetching messages: {e}", level="error")

    def _show_message_list(self) -> None:
        """Display message list with cursor and handle commands."""
        if not self.messages:
            return

        while True:
            # Create listbox items with metadata indicators
            items = []
            for msg in self.messages:
                from_addr = msg["from"][:25].ljust(25)
                subject = msg["subject"][:50]

                # Get metadata from IMAP flags
                metadata = self._get_message_metadata_from_flags(msg["uid"])
                status_indicator = ""
                if metadata:
                    if metadata.get("claimed"):
                        status_indicator = "[C] "
                    if metadata.get("projectid"):
                        status_indicator += f"[P:{metadata['projectid']}] "

                display = f"{status_indicator}{from_addr} {subject}"
                item = ListboxItem(content=display)
                items.append(item)

            echo("")
            echo("=== Messages ===", level="info")
            echo("UP/DOWN=navigate, ENTER=view, DEL=delete, t=tag, c=claim, ESC=exit")
            echo("")

            # Create and run listbox
            try:
                lb = Listbox(
                    self.args,
                    title="Messages",
                    items=items,
                    itemheight=1,
                    itemsperpage=20,
                    custom_keys={
                        "KEY_DELETE": self._handle_delete_key,
                        "T": self._handle_tag_key,
                        "C": self._handle_claim_key,
                    },
                )
                result = lb.run("Messages: ")

                if result is None or result.status == "cancelled":
                    # User pressed ESC
                    return

                if result.status == "selected" and result.item:
                    # Get the index of selected item from the listbox
                    # Note: we iterate through items to find matching index
                    selected_index = None
                    if hasattr(lb, "_selected_index"):
                        selected_index = lb._selected_index
                    else:
                        # Fallback: find by content matching
                        for i, item in enumerate(items):
                            if item.content == result.item.content:
                                selected_index = i
                                break

                    if selected_index is not None and 0 <= selected_index < len(
                        self.messages
                    ):
                        selected_msg = self.messages[selected_index]
                        self._message_detail(selected_msg)
                        # After viewing message, loop continues to redisplay list

            except Exception as e:
                echo(f"Error in message list: {e}", level="error")
                return

    def _handle_delete_key(self) -> Optional[ListboxResult]:
        """Handle DELETE key in message list."""
        selected_index = getattr(self, "_selected_index", None)
        if selected_index is None:
            return None
        if 0 <= selected_index < len(self.messages):
            msg = self.messages[selected_index]
            self._delete_message(msg["uid"])
            self._fetch_messages()
        return None

    def _handle_tag_key(self) -> Optional[ListboxResult]:
        """Handle 'T' key in message list to tag with project ID."""
        selected_index = getattr(self, "_selected_index", None)
        if selected_index is None:
            return None
        if 0 <= selected_index < len(self.messages):
            msg = self.messages[selected_index]
            self._tag_message(msg["uid"])
        return None

    def _handle_claim_key(self) -> Optional[ListboxResult]:
        """Handle 'C' key in message list to claim/unclaim message."""
        selected_index = getattr(self, "_selected_index", None)
        if selected_index is None:
            return None
        if 0 <= selected_index < len(self.messages):
            msg = self.messages[selected_index]
            self._claim_message(msg["uid"])
        return None

    def _message_detail(self, msg: Dict[str, Any]) -> None:
        """Show detailed message view and handle actions."""
        if not self.imap:
            return

        try:
            # Fetch full message
            status, data = self.imap.uid("FETCH", str(msg["uid"]), "RFC822")
            if status != "OK" or not data:
                echo("Could not fetch message", level="error")
                return

            raw_message = data[0][1]
            message = email.message_from_bytes(raw_message)

            # Display message
            echo("")
            echo("=== Message ===", level="info")
            echo(f"From: {message.get('From', 'Unknown')}")
            echo(f"Subject: {message.get('Subject', '(no subject)')}")
            echo(f"Date: {message.get('Date', '')}")
            echo("")
            echo("---")

            # Display body
            body = self._get_message_body(message)
            lines = body.split("\n")
            for line in lines[:30]:  # Show first 30 lines
                echo(line)
            if len(lines) > 30:
                echo(f"... ({len(lines) - 30} more lines)")
            echo("---")
            echo("")

            # Check metadata from IMAP flags
            metadata = self._get_message_metadata_from_flags(msg["uid"])
            if metadata:
                echo("Message Metadata:", level="info")
                if metadata.get("projectid"):
                    echo(f"  Project ID: {metadata['projectid']}")
                if metadata.get("claimed"):
                    echo("  Claimed: Yes")
                echo("")

            # Handle message actions
            self._message_actions(msg)

        except Exception as e:
            echo(f"Error displaying message: {e}", level="error")

    def _get_message_body(self, message: email.message.Message) -> str:  # type: ignore[name-defined]
        """Extract and return message body text."""
        body = ""
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace"
                        )
                        break
                    except Exception:
                        pass
        else:
            try:
                body = message.get_payload(decode=True).decode(
                    "utf-8", errors="replace"
                )
            except Exception:
                body = message.get_payload()

        return body if body else "(no body)"

    def _message_actions(self, msg: Dict[str, Any]) -> None:
        """Handle actions on a message (delete, reply, forward)."""
        echo("Actions:", level="info")
        echo("  DEL = delete")
        echo("  t   = tag with project ID")
        echo("  c   = claim/unclaim")
        echo("  r   = reply")
        echo("  f   = forward")
        echo("  any key = back to list")
        echo("")

        try:
            key = getch()
            if key == "KEY_DELETE":
                self._delete_message(msg["uid"])
            elif key and key.upper() == "T":
                self._tag_message(msg["uid"])
            elif key and key.upper() == "C":
                self._claim_message(msg["uid"])
            elif key and key.upper() == "R":
                self._reply_to_message(msg)
            elif key and key.upper() == "F":
                self._forward_message(msg)
            # Any other key goes back to list
        except (EOFError, KeyboardInterrupt):
            pass

    def _delete_message(self, uid: int) -> None:
        """Delete a message by UID."""
        if not self.imap:
            return

        try:
            self.imap.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")
            self.imap.expunge()
            echo("Message deleted", level="info")
        except Exception as e:
            echo(f"Error deleting message: {e}", level="error")

    def _tag_message(self, uid: int) -> None:
        """Tag message with a project ID."""
        echo("")
        try:
            project_id_str = input(
                "Enter project ID (or press ENTER to cancel): "
            ).strip()
            if not project_id_str:
                return

            try:
                project_id = int(project_id_str)
            except ValueError:
                echo("Invalid project ID - must be a number", level="error")
                return

            # Store metadata in IMAP flags and database
            metadata = self._get_message_metadata_from_flags(uid) or {}
            metadata["projectid"] = project_id
            self._set_message_metadata(uid, metadata)
            echo(f"Message tagged with project ID {project_id}", level="info")
        except Exception as e:
            echo(f"Error tagging message: {e}", level="error")

    def _claim_message(self, uid: int) -> None:
        """Claim or unclaim a message."""
        mailbox_name = "INBOX"
        try:
            metadata = self._get_message_metadata_from_flags(uid) or {}

            if metadata.get("claimed"):
                assert self.current_user is not None
                imap_client.unclaim_message(
                    self.args,
                    mailbox_name,
                    uid,
                    self.current_user,
                    imap_conn=self.imap,
                )
                echo("Message unclaimed", level="info")
            else:
                msg = next((m for m in self.messages if m["uid"] == uid), {})
                assert self.current_user is not None
                imap_client.claim_message(
                    self.args,
                    mailbox_name,
                    uid,
                    self.current_user,
                    message_from=msg.get("from") or "",
                    message_subject=msg.get("subject") or "",
                    imap_conn=self.imap,
                )
                echo(f"Message claimed by {self.current_user}", level="info")
        except Exception as e:
            echo(f"Error claiming message: {e}", level="error")

    def _get_message_metadata_from_flags(self, uid: int) -> Optional[Dict[str, Any]]:
        """Get metadata from IMAP message flags."""
        if not self.imap:
            return None

        try:
            flags = imap_lib.get_message_flags(self.imap, uid)

            # Look for custom metadata flag
            metadata_flag = None
            for flag in flags:
                if flag.startswith("Metadata_"):
                    metadata_flag = flag
                    break

            if not metadata_flag:
                return None

            # Extract base64-encoded JSON from flag
            # Format: Metadata_<base64-encoded-json>
            encoded_data = metadata_flag[9:]  # Skip "Metadata_" prefix
            try:
                json_data = base64.b64decode(encoded_data).decode()
                return json.loads(json_data)
            except (ValueError, json.JSONDecodeError):
                return None

        except Exception as e:
            echo(f"Error retrieving metadata from flags: {e}", level="error")
            return None

    def _set_message_metadata(self, uid: int, metadata: Dict[str, Any]) -> bool:
        """Store metadata in IMAP message flags and database."""
        if not self.imap:
            return False

        try:
            # Prepare metadata as base64-encoded JSON flag
            metadata_json = json.dumps(metadata)
            encoded_metadata = base64.b64encode(metadata_json.encode()).decode()
            metadata_flag = f"Metadata_{encoded_metadata}"

            # Remove old metadata flag if it exists
            flags = imap_lib.get_message_flags(self.imap, uid)
            for flag in flags:
                if flag.startswith("Metadata_"):
                    # Remove old metadata flag
                    self.imap.uid("STORE", str(uid), "-FLAGS", f"({flag})")
                    break

            # Add new metadata flag
            self.imap.uid("STORE", str(uid), "+FLAGS", f"({metadata_flag})")

            # Also store in database if available
            if self.db:
                self._store_metadata_to_db(uid, metadata)

            return True
        except Exception as e:
            echo(f"Error storing metadata: {e}", level="error")
            return False

    def _store_metadata_to_db(self, uid: int, metadata: Dict[str, Any]) -> bool:
        """Store metadata in database as backup."""
        if not self.db:
            return False

        try:
            metadata_json = json.dumps(metadata)
            cur = self.db.cursor()

            # Try to update first
            cur.execute(
                "UPDATE postoffice.__message SET metadata = %s WHERE id = %s",
                [metadata_json, str(uid)],
            )

            # If no rows were updated, insert
            if cur.rowcount == 0:
                cur.execute(
                    "INSERT INTO postoffice.__message (id, metadata) VALUES (%s, %s)",
                    [str(uid), metadata_json],
                )

            self.db.commit()
            cur.close()
            return True
        except Exception as e:
            echo(f"Error storing metadata to database: {e}", level="error")
            if self.db:
                try:
                    self.db.rollback()
                except Exception:
                    pass
            return False

    def _reply_to_message(self, msg: Dict[str, Any]) -> None:
        """Handle reply to message."""
        echo("")
        echo("Reply functionality not yet implemented", level="info")

    def _forward_message(self, msg: Dict[str, Any]) -> None:
        """Handle message forward."""
        echo("")
        echo("Forward functionality not yet implemented", level="info")


def run(args: Any, current_user: Optional[str] = None, pool: Any = None) -> int:
    """Module-level entry point for the message TUI.

    Wraps :class:`MessageInterface` so callers (e.g.
    ``postoffice.__main__``) can invoke ``from .tui.message_interface
    import run`` and call ``run(args, current_user, pool=pool)``
    uniformly. The legacy signature accepted ``(args, current_user,
    pool)``; the current ``MessageInterface`` takes only ``args`` and
    pulls ``loginid`` / ``issuperuser`` from the namespace.
    """
    if current_user is not None:
        args.loginid = current_user
    return MessageInterface(args).run()
