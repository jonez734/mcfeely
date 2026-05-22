# imap_checker.py
# IMAP server connectivity and health checking

import imaplib
import socket
import ssl
from typing import Tuple

from bbsengine6.io import echo


class IMAPChecker:
    """Check IMAP server connectivity and SSL/TLS configuration."""

    def __init__(self, host: str, port: int, timeout: int = 5, verbose: bool = False):
        """
        Initialize IMAP checker.

        Args:
            host: IMAP server hostname or IP address
            port: IMAP server port
            timeout: Connection timeout in seconds (default: 5)
            verbose: Show verbose output

        Raises:
            ValueError: If host or port are invalid
        """
        if not host or not isinstance(host, str):
            raise ValueError("Host must be a non-empty string")
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError("Port must be an integer between 1 and 65535")
        if timeout < 1:
            raise ValueError("Timeout must be at least 1 second")

        self.host = host.strip()
        self.port = port
        self.timeout = timeout
        self.verbose = verbose

    def check_connectivity(self) -> Tuple[bool, str]:
        """
        Check if IMAP server is listening on configured address/port.

        Uses TCP socket connection (no SSL/TLS) to verify the server is responding.

        Returns:
            Tuple of (success: bool, message: str)
            - success: True if server is listening and responding
            - message: Diagnostic message
        """
        if self.verbose:
            echo(
                f"Checking TCP connectivity to {self.host}:{self.port}...",
                level="debug",
            )

        try:
            # Create a socket and attempt connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            try:
                sock.connect((self.host, self.port))
                if self.verbose:
                    echo("✓ TCP connection successful", level="debug")
                return True, f"Server listening on {self.host}:{self.port}"
            finally:
                sock.close()

        except socket.timeout:
            msg = f"Connection timeout (waited {self.timeout}s) - server not responding"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except socket.gaierror as e:
            msg = f"Host resolution failed: {e}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except ConnectionRefusedError:
            msg = f"Connection refused - no server listening on {self.host}:{self.port}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except Exception as e:
            msg = f"Connection error: {e}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

    def check_imap_protocol(self) -> Tuple[bool, str]:
        """
        Check if IMAP server responds to IMAP protocol (requires SSL/TLS).

        Attempts an SSL/TLS connection and checks for IMAP greeting.

        Returns:
            Tuple of (success: bool, message: str)
            - success: True if server responds with IMAP greeting
            - message: Diagnostic message including server version info
        """
        if self.verbose:
            echo(f"Checking IMAP protocol on {self.host}:{self.port}...", level="debug")

        try:
            # Create SSL context
            context = ssl.create_default_context()

            # Connect with IMAP4_SSL
            imap = imaplib.IMAP4_SSL(
                self.host, self.port, ssl_context=context, timeout=self.timeout
            )

            try:
                # Get the greeting
                response = imap.welcome.decode("utf-8") if isinstance(imap.welcome, bytes) else imap.welcome
                if self.verbose:
                    echo(f"✓ IMAP greeting: {response}", level="debug")

                # Send CAPABILITY command to verify functionality
                status, capabilities = imap.capability()
                if status == "OK":
                    if self.verbose:
                        echo(
                            f"✓ Server capabilities: {len(capabilities)} available",
                            level="debug",
                        )
                    return (
                        True,
                        f"IMAP server responding. Capabilities: {', '.join(capabilities[0].decode('utf-8').split())}",
                    )
                else:
                    return False, "Server responded but CAPABILITY check failed"

            finally:
                try:
                    imap.logout()
                except Exception:
                    pass  # Already disconnected or error on logout

        except ssl.SSLError as e:
            msg = f"SSL/TLS error: {e}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except imaplib.IMAP4.error as e:
            msg = f"IMAP protocol error: {e}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except socket.timeout:
            msg = f"IMAP connection timeout (waited {self.timeout}s)"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except ConnectionRefusedError:
            msg = f"IMAP connection refused on {self.host}:{self.port}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

        except Exception as e:
            msg = f"IMAP connection error: {e}"
            if self.verbose:
                echo(f"✗ {msg}", level="debug")
            return False, msg

    def check_all(self) -> Tuple[bool, list]:
        """
        Run all connectivity checks.

        Returns:
            Tuple of (all_pass: bool, results: list of dicts)
            Each result dict contains:
            - name: Check name
            - passed: Boolean result
            - message: Diagnostic message
        """
        results = []

        # Check 1: TCP connectivity
        tcp_pass, tcp_msg = self.check_connectivity()
        results.append(
            {"name": "TCP Connectivity", "passed": tcp_pass, "message": tcp_msg}
        )

        if not tcp_pass:
            # Skip IMAP protocol check if TCP fails
            results.append(
                {
                    "name": "IMAP Protocol",
                    "passed": False,
                    "message": "Skipped (TCP connectivity failed)",
                }
            )
            return False, results

        # Check 2: IMAP protocol
        imap_pass, imap_msg = self.check_imap_protocol()
        results.append(
            {"name": "IMAP Protocol", "passed": imap_pass, "message": imap_msg}
        )

        all_pass = tcp_pass and imap_pass
        return all_pass, results

    def print_results(self, all_pass: bool, results: list) -> None:
        """
        Print check results in a formatted way.

        Args:
            all_pass: Overall result
            results: List of result dicts from check_all()
        """
        echo("")
        echo("=== IMAP Server Connectivity Check ===", level="info")
        echo(f"Host: {self.host}")
        echo(f"Port: {self.port}")
        echo(f"Timeout: {self.timeout}s")
        echo("")

        for result in results:
            status = "✓" if result["passed"] else "✗"
            level = "info" if result["passed"] else "error"
            echo(f"{status} {result['name']}: {result['message']}", level=level)

        echo("")
        if all_pass:
            echo("✓ All checks passed - IMAP server is accessible", level="info")
        else:
            echo("✗ Some checks failed - please verify IMAP configuration", level="error")

        echo("")

    @staticmethod
    def verify_connection(
        host: str, port: int, timeout: int = 5, verbose: bool = False
    ) -> bool:
        """
        Quick utility function to verify IMAP connectivity.

        Args:
            host: IMAP server hostname or IP address
            port: IMAP server port
            timeout: Connection timeout in seconds
            verbose: Show verbose output

        Returns:
            True if both TCP and IMAP protocol checks pass
        """
        checker = IMAPChecker(host, port, timeout, verbose)
        all_pass, _ = checker.check_all()
        return all_pass
