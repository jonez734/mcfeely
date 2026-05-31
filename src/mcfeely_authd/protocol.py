# protocol.py
# authdaemon protocol handling for saslauthd communication

from typing import Optional, Tuple


AUTH_PROTOCOL_VERSION = "AUTH"
AUTH_OK = "OK"
AUTH_NO = "NO"
AUTH_FAIL = "FAIL"


class ProtocolError(Exception):
    """Protocol parsing error."""

    pass


def read_line(sock) -> str:
    """Read a newline-terminated line from socket.

    Args:
        sock: Socket file object

    Returns:
        Line content without newline
    """
    line = b""
    while True:
        ch = sock.read(1)
        if not ch:
            raise ProtocolError("Connection closed")
        if ch == b"\n":
            break
        line += ch
    return line.decode("utf-8", errors="replace")


def write_line(sock, line: str) -> None:
    """Write a newline-terminated line to socket.

    Args:
        sock: Socket file object
        line: Line content
    """
    sock.write(f"{line}\n".encode("utf-8"))
    sock.flush()


def read_data(sock, length: int) -> bytes:
    """Read exact number of bytes from socket.

    Args:
        sock: Socket file object
        length: Number of bytes to read

    Returns:
        Bytes read
    """
    data = b""
    while len(data) < length:
        chunk = sock.read(length - len(data))
        if not chunk:
            raise ProtocolError("Connection closed")
        data += chunk
    return data


def write_data(sock, data: bytes) -> None:
    """Write bytes to socket.

    Args:
        sock: Socket file object
        data: Bytes to write
    """
    sock.write(data)
    sock.flush()


class AuthRequest:
    """Parsed authentication request from saslauthd."""

    def __init__(
        self,
        mechanism: str,
        username: str,
        password: str,
        realm: Optional[str] = None,
        local_ip: Optional[str] = None,
        remote_ip: Optional[str] = None,
    ):
        self.mechanism = mechanism
        self.username = username
        self.password = password
        self.realm = realm
        self.local_ip = local_ip
        self.remote_ip = remote_ip

    @property
    def user_realm(self) -> str:
        """Return user[@realm] format."""
        if self.realm:
            return f"{self.username}@{self.realm}"
        return self.username

    def __repr__(self) -> str:
        return f"AuthRequest(mechanism={self.mechanism!r}, username={self.username!r})"


class AuthResponse:
    """Authentication response."""

    def __init__(self, status: str, message: str = ""):
        self.status = status
        self.message = message

    @classmethod
    def ok(cls, message: str = "") -> "AuthResponse":
        return cls(AUTH_OK, message)

    @classmethod
    def no(cls, message: str = "") -> "AuthResponse":
        return cls(AUTH_NO, message)

    @classmethod
    def fail(cls, message: str = "") -> "AuthResponse":
        return cls(AUTH_FAIL, message)

    def __repr__(self) -> str:
        return f"AuthResponse({self.status}, {self.message!r})"


def parse_request(sock) -> AuthRequest:
    """Parse authdaemon request from socket.

    Request format:
        AUTH <mechanism>\n
        <length>\n
        <username>\n
        [<password>]\n
        [<realm>]\n
        [<local_ip>]\n
        [<remote_ip>]\n

    Args:
        sock: Socket file object

    Returns:
        AuthRequest instance

    Raises:
        ProtocolError: If parsing fails
    """
    try:
        line = read_line(sock)
    except Exception as e:
        raise ProtocolError(f"Failed to read auth line: {e}")

    if not line.startswith("AUTH "):
        raise ProtocolError(f"Invalid auth line: {line!r}")

    mechanism = line[5:].strip()
    if not mechanism:
        raise ProtocolError("Empty mechanism")

    try:
        length_line = read_line(sock)
        length = int(length_line)
    except ValueError:
        raise ProtocolError(f"Invalid length: {length_line!r}")

    if length <= 0 or length > 65536:
        raise ProtocolError(f"Invalid length: {length}")

    try:
        username = read_line(sock).strip()
        password = read_line(sock).strip()
        realm = read_line(sock).strip() or None
        local_ip = read_line(sock).strip() or None
        remote_ip = read_line(sock).strip() or None
    except ProtocolError:
        raise
    except Exception as e:
        raise ProtocolError(f"Failed to read fields: {e}")

    return AuthRequest(
        mechanism=mechanism,
        username=username,
        password=password,
        realm=realm,
        local_ip=local_ip,
        remote_ip=remote_ip,
    )


def parse_request_from_buffer(data: bytes) -> Tuple[AuthRequest, int]:
    """Parse authdaemon request from buffer.

    Useful for testing without sockets.

    Args:
        data: Request data bytes

    Returns:
        Tuple of (AuthRequest, bytes_consumed)

    Raises:
        ProtocolError: If parsing fails
    """
    if not data.startswith(b"AUTH "):
        raise ProtocolError(f"Invalid auth line: {data[:20]!r}")

    lines = data.split(b"\n")
    if len(lines) < 4:
        raise ProtocolError("Incomplete request")

    mechanism = lines[0][5:].decode("utf-8", errors="replace").strip()
    if not mechanism:
        raise ProtocolError("Empty mechanism")

    try:
        length = int(lines[1])
    except ValueError:
        raise ProtocolError(f"Invalid length: {lines[1]!r}")

    if length <= 0 or length > 65536:
        raise ProtocolError(f"Invalid length: {length}")

    total_len = sum(len(line) + 1 for line in lines[:5]) + length
    if len(data) < total_len:
        raise ProtocolError("Incomplete request")

    username = lines[2].decode("utf-8", errors="replace").strip()
    password = lines[3].decode("utf-8", errors="replace").strip()
    realm = lines[4].decode("utf-8", errors="replace").strip() or None

    return (
        AuthRequest(
            mechanism=mechanism,
            username=username,
            password=password,
            realm=realm,
        ),
        total_len,
    )


def send_response(sock, response: AuthResponse) -> None:
    """Send authdaemon response to socket.

    Response format:
        <status>\n
        [<message>]\n

    Args:
        sock: Socket file object
        response: AuthResponse instance
    """
    write_line(sock, response.status)
    if response.message:
        write_line(sock, response.message)


def send_ok(sock, message: str = "") -> None:
    """Send OK response."""
    send_response(sock, AuthResponse.ok(message))


def send_no(sock, message: str = "") -> None:
    """Send NO response."""
    send_response(sock, AuthResponse.no(message))


def send_fail(sock, message: str = "") -> None:
    """Send FAIL response."""
    send_response(sock, AuthResponse.fail(message))


__all__ = [
    "AUTH_PROTOCOL_VERSION",
    "AUTH_OK",
    "AUTH_NO",
    "AUTH_FAIL",
    "ProtocolError",
    "AuthRequest",
    "AuthResponse",
    "parse_request",
    "parse_request_from_buffer",
    "send_response",
    "send_ok",
    "send_no",
    "send_fail",
]
