# postoffice/api/handler.py
# WebSocket message handler - routes messages to postoffice services

from datetime import datetime
from typing import Any, Dict, Optional

from bbsengine6 import io, member
from bbsengine6.message import deliver_pending_on_connect, get_unread_count
from bbsengine6.net import (
    ChannelState,
    channel_subscribe,
    channel_unsubscribe,
    channel_unsubscribe_all,
    channel_get_session_channels,
)

from postoffice.services import MailboxPoller, get_service, check_mail


from bbsengine6.session import SessionManager


class BaseService:
    """Base class for message handlers."""

    def __init__(self, args: Any, session_manager: SessionManager):
        self.args = args
        self.sessions = session_manager

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class AuthService(BaseService):
    """Handle authentication messages."""

    def __init__(
        self,
        args: Any,
        session_manager: SessionManager,
        channel_state: Optional[ChannelState] = None,
    ):
        super().__init__(args, session_manager)
        self.channel_state = channel_state

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        msg_type = message.get("type")

        if msg_type == "auth":
            return await self._handle_auth(websocket, message)
        elif msg_type == "ping":
            return {"type": "pong", "timestamp": datetime.utcnow().isoformat()}

        return None

    async def _handle_auth(
        self, websocket: Any, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = message.get("moniker", "")
        password = message.get("password", "")

        if not moniker:
            return {
                "type": "error",
                "code": "invalid_credentials",
                "message": "Moniker and password required",
            }

        from postoffice import member_password

        if not member_password.checkpassword(self.args, moniker, password):
            return {
                "type": "auth_result",
                "success": False,
                "moniker": moniker,
                "message": "Invalid password",
            }

        session_id = id(websocket)
        is_sysop = member.issysop(self.args, moniker=moniker) is True
        self.sessions.register_session(session_id, moniker, is_sysop=is_sysop)

        from bbsengine6 import bank

        bank_service = bank.BankService(self.args)
        balance = bank_service.get_balance(moniker)

        if self.channel_state:
            channel_subscribe(self.channel_state, session_id, f"member:{moniker}")

        pending_messages = []
        try:
            pending_messages = deliver_pending_on_connect(
                moniker, database=self.args.databasename
            )
        except Exception as e:
            io.echo(f"Failed to deliver pending messages: {e}", level="warning")

        unread_count = 0
        try:
            unread_count = get_unread_count(moniker, database=self.args.databasename)
        except Exception as e:
            io.echo(f"Failed to get unread count: {e}", level="warning")

        return {
            "type": "auth_result",
            "success": True,
            "moniker": moniker,
            "balance": balance,
            "message": "Authenticated",
            "pending_messages": pending_messages,
            "unread_count": unread_count,
        }


class MailboxServiceHandler(BaseService):
    """Handle mailbox and email messages."""

    def __init__(self, args: Any, session_manager: SessionManager):
        super().__init__(args, session_manager)
        self.postoffice_service: Optional[MailboxPoller] = None

    def _get_postoffice_service(self) -> MailboxPoller:
        if self.postoffice_service is None:
            self.postoffice_service = get_service()
        return self.postoffice_service

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        msg_type = message.get("type")

        if msg_type == "check_mail":
            return await self._handle_check_mail(id(websocket), message)
        elif msg_type == "list_mailboxes":
            return await self._handle_list_mailboxes(id(websocket), message)
        elif msg_type == "mailbox_status":
            return await self._handle_mailbox_status(id(websocket), message)

        return None

    async def _handle_check_mail(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        result = await check_mail(moniker=moniker)

        return {
            "type": "mail_check_result",
            "success": result.get("success", False),
            "mailboxes_checked": result.get("mailboxes_checked", 0),
            "total_unread": result.get("total_unread", 0),
            "errors": result.get("errors", []),
        }

    async def _handle_list_mailboxes(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        service = self._get_postoffice_service()
        mailboxes = []
        for mb in service.mailboxes:
            mailboxes.append(
                {
                    "host": mb.host,
                    "mailbox": mb.mailbox,
                    "use_ssl": mb.use_ssl,
                }
            )

        return {
            "type": "mailbox_list",
            "mailboxes": mailboxes,
        }

    async def _handle_mailbox_status(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        service = self._get_postoffice_service()

        return {
            "type": "mailbox_status",
            "enabled": service.is_enabled,
            "poll_interval": service.poll_interval,
            "mailbox_count": len(service.mailboxes),
        }


class AddressServiceHandler(BaseService):
    """Handle virtual address management messages."""

    def __init__(self, args: Any, session_manager: SessionManager):
        super().__init__(args, session_manager)

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        msg_type = message.get("type")

        if msg_type == "list_addresses":
            return await self._handle_list_addresses(id(websocket), message)
        elif msg_type == "create_address":
            return await self._handle_create_address(id(websocket), message)
        elif msg_type == "delete_address":
            return await self._handle_delete_address(id(websocket), message)

        return None

    async def _handle_list_addresses(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        try:
            from postoffice import virtual

            addresses = virtual.list_addresses(self.args, moniker)
            return {
                "type": "address_list",
                "addresses": addresses,
            }
        except Exception as e:
            io.echo(f"Error listing addresses: {e}", level="error")
            return {"type": "error", "code": "list_failed", "message": str(e)}

    async def _handle_create_address(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        address = message.get("address", "")
        if not address:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "address required",
            }

        try:
            from postoffice import virtual

            result = virtual.create_address(self.args, moniker, address)
            if result:
                return {
                    "type": "address_created",
                    "address": address,
                    "message": f"Address {address} created successfully",
                }
            return {
                "type": "error",
                "code": "create_failed",
                "message": "Could not create address",
            }
        except Exception as e:
            io.echo(f"Error creating address: {e}", level="error")
            return {"type": "error", "code": "create_failed", "message": str(e)}

    async def _handle_delete_address(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        address = message.get("address", "")
        if not address:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "address required",
            }

        try:
            from postoffice import virtual

            result = virtual.delete_address(self.args, moniker, address)
            if result:
                return {
                    "type": "address_deleted",
                    "address": address,
                    "message": f"Address {address} deleted successfully",
                }
            return {
                "type": "error",
                "code": "delete_failed",
                "message": "Could not delete address",
            }
        except Exception as e:
            io.echo(f"Error deleting address: {e}", level="error")
            return {"type": "error", "code": "delete_failed", "message": str(e)}


class ChannelServiceHandler(BaseService):
    """Handle channel subscription messages."""

    def __init__(
        self,
        args: Any,
        session_manager: SessionManager,
        channel_state: ChannelState,
        server: Any,
    ):
        super().__init__(args, session_manager)
        self.channel_state = channel_state
        self._server = server

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        msg_type = message.get("type")

        if msg_type == "subscribe_channel":
            return await self._handle_subscribe(id(websocket), message)
        elif msg_type == "unsubscribe_channel":
            return await self._handle_unsubscribe(id(websocket), message)
        elif msg_type == "get_subscriptions":
            return await self._handle_get_subscriptions(id(websocket))

        return None

    async def _handle_subscribe(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        channel = message.get("channel", "").strip()
        if not channel:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "channel required",
            }

        channel_subscribe(self.channel_state, session_id, channel)

        return {
            "type": "subscribed",
            "channel": channel,
            "message": f"Subscribed to {channel}",
        }

    async def _handle_unsubscribe(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        channel = message.get("channel", "").strip()
        if not channel:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "channel required",
            }

        channel_unsubscribe(self.channel_state, session_id, channel)

        return {
            "type": "unsubscribed",
            "channel": channel,
            "message": f"Unsubscribed from {channel}",
        }

    async def _handle_get_subscriptions(self, session_id: int) -> Dict[str, Any]:
        moniker = self.sessions.get_moniker(session_id)
        if not moniker:
            return {"type": "error", "code": "not_authenticated"}

        channels = channel_get_session_channels(self.channel_state, session_id)

        return {
            "type": "subscriptions",
            "channels": list(channels),
        }


class BankServiceHandler(BaseService):
    """Handle bank management messages."""

    def __init__(self, args: Any, session_manager: SessionManager):
        super().__init__(args, session_manager)
        from bbsengine6 import bank

        self.bank_service = bank.BankService(args)

    async def handle_message(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        msg_type = message.get("type")

        if msg_type == "bank_balance":
            return await self._handle_balance(id(websocket), message)
        elif msg_type == "bank_add":
            return await self._handle_add(id(websocket), message)
        elif msg_type == "bank_remove":
            return await self._handle_remove(id(websocket), message)
        elif msg_type == "bank_history":
            return await self._handle_history(id(websocket), message)

        return None

    async def _handle_balance(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        session = self.sessions.get_session(session_id)
        if not session:
            return {"type": "error", "code": "not_authenticated"}

        moniker = message.get("moniker", session.get("moniker"))
        if not moniker:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "moniker required",
            }

        balance = self.bank_service.get_balance(moniker)

        return {
            "type": "bank_balance",
            "moniker": moniker,
            "balance": balance,
        }

    async def _handle_add(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        session = self.sessions.get_session(session_id)
        if not session:
            return {"type": "error", "code": "not_authenticated"}

        moniker = message.get("moniker")
        if not moniker:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "moniker required",
            }

        amount = message.get("amount", 0)
        description = message.get("description", "deposit")

        result = self.bank_service.add_funds(
            moniker,
            amount,
            transaction_type="deposit",
            description=description,
        )

        if result.get("success"):
            return {
                "type": "bank_added",
                "moniker": moniker,
                "amount": amount,
                "new_balance": result.get("new_balance"),
            }
        else:
            return {
                "type": "error",
                "code": "add_failed",
                "message": result.get("message", ""),
            }

    async def _handle_remove(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        session = self.sessions.get_session(session_id)
        if not session:
            return {"type": "error", "code": "not_authenticated"}

        moniker = message.get("moniker")
        if not moniker:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "moniker required",
            }

        amount = message.get("amount", 0)
        description = message.get("description", "withdrawal")

        result = self.bank_service.remove_funds(
            moniker,
            amount,
            transaction_type="withdrawal",
            description=description,
        )

        if result.get("success"):
            return {
                "type": "bank_removed",
                "moniker": moniker,
                "amount": amount,
                "new_balance": result.get("new_balance"),
            }
        else:
            return {
                "type": "error",
                "code": "remove_failed",
                "message": result.get("message", ""),
            }

    async def _handle_history(
        self, session_id: int, message: Dict[str, Any]
    ) -> Dict[str, Any]:
        session = self.sessions.get_session(session_id)
        if not session:
            return {"type": "error", "code": "not_authenticated"}

        moniker = message.get("moniker")
        if not moniker:
            return {
                "type": "error",
                "code": "invalid_request",
                "message": "moniker required",
            }

        limit = message.get("limit", 50)
        history = self.bank_service.get_history(moniker, limit)

        return {
            "type": "bank_history",
            "moniker": moniker,
            "transactions": history,
        }


class MessageRouter:
    """
    Main message handler that coordinates all postoffice services.
    Handles broadcasting and session lifecycle.
    """

    def __init__(
        self,
        args: Any,
        channel_state: Optional[ChannelState] = None,
        server: Any = None,
    ) -> None:
        self.args = args
        self.sessions = SessionManager()
        # Accept shared channel state from caller (typically BED) so
        # that server.publish(...) and ChannelServiceHandler see the
        # same subscriptions.
        self.channel_state = (
            channel_state if channel_state is not None else ChannelState()
        )
        self.server = server

        self.auth_service = AuthService(args, self.sessions, self.channel_state)
        self.mailbox_service = MailboxServiceHandler(args, self.sessions)
        self.address_service = AddressServiceHandler(args, self.sessions)
        self.bank_service = BankServiceHandler(args, self.sessions)
        self.channel_service: Optional[ChannelServiceHandler] = None

    def register_all(self, server: Any) -> None:
        """Register all services with the WebSocketServer."""
        server.register_service(self.auth_service, ["auth", "ping"])
        server.register_service(
            self.mailbox_service, ["check_mail", "list_mailboxes", "mailbox_status"]
        )
        server.register_service(
            self.address_service, ["list_addresses", "create_address", "delete_address"]
        )
        server.register_service(
            self.bank_service,
            ["bank_balance", "bank_add", "bank_remove", "bank_history"],
        )

        self.channel_service = ChannelServiceHandler(
            self.args, self.sessions, self.channel_state, server
        )
        server.register_service(
            self.channel_service,
            ["subscribe_channel", "unsubscribe_channel", "get_subscriptions"],
        )

    async def handle_broadcast(
        self, server: Any, websocket: Any, path: str, message: Dict[str, Any]
    ) -> None:
        """Handle message that should be broadcast."""
        pass

    def unregister_session(self, session_id: int) -> None:
        """Clean up session on disconnect."""
        channel_unsubscribe_all(self.channel_state, session_id)
        self.sessions.unregister_session(session_id)
