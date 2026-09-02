#!/usr/bin/env python3
# mcfeely_authd.py
# SASL authentication daemon for mistermcfeely
# Implements authdaemon protocol for saslauthd

import os
import sys
import signal
import errno
import socket
import stat
import argparse
import logging
import logging.handlers

from . import config
from . import protocol
from . import auth_verify


VERSION = "1.0.0"
DAEMON_NAME = "mcfeely-authd"

LOGGER = None


def setup_logging(cfg: config.Config) -> logging.Logger:
    """Set up logging for the daemon.

    Args:
        cfg: Config instance

    Returns:
        Logger instance
    """
    global LOGGER

    logger = logging.getLogger(DAEMON_NAME)
    logger.setLevel(getattr(logging, cfg["log_level"].upper(), logging.INFO))

    log_format = logging.Formatter(
        "%(asctime)s %(name)s[%(process)d]: %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if cfg["log_syslog"]:
        try:
            handler = logging.handlers.SysLogHandler(address="/dev/log")
            handler.setFormatter(log_format)
            logger.addHandler(handler)
        except Exception:
            pass

    try:
        log_dir = os.path.dirname(cfg["log_file"])
        if log_dir:
            os.makedirs(log_dir, mode=0o755, exist_ok=True)
        handler = logging.FileHandler(cfg["log_file"])
        handler.setFormatter(log_format)
        logger.addHandler(handler)
    except Exception as e:
        print(f"Warning: Cannot create log file: {e}", file=sys.stderr)

    LOGGER = logger
    return logger


def log(level: str, msg: str) -> None:
    """Log a message.

    Args:
        level: Log level (debug, info, warning, error)
        msg: Message to log
    """
    if LOGGER:
        getattr(LOGGER, level.lower())(msg)


def daemonize(cfg: config.Config) -> None:
    """Daemonize the process.

    Args:
        cfg: Config instance
    """
    if os.fork() != 0:
        sys.exit(0)

    os.setsid()

    if os.fork() != 0:
        sys.exit(0)

    os.chdir("/")
    os.umask(0)

    stdin = open("/dev/null", "r")
    stdout = open("/dev/null", "a+")
    stderr = open("/dev/null", "a+")
    os.dup2(stdin.fileno(), sys.stdin.fileno())
    os.dup2(stdout.fileno(), sys.stdout.fileno())
    os.dup2(stderr.fileno(), sys.stderr.fileno())

    pid_dir = os.path.dirname(cfg["pid_file"])
    if pid_dir:
        os.makedirs(pid_dir, mode=0o755, exist_ok=True)

    with open(cfg["pid_file"], "w") as f:
        f.write(str(os.getpid()))


def cleanup(pid_file: str, socket_path: str) -> None:
    """Clean up PID file and socket.

    Args:
        pid_file: Path to PID file
        socket_path: Path to UNIX socket
    """
    if pid_file and os.path.exists(pid_file):
        try:
            os.unlink(pid_file)
        except OSError:
            pass

    if socket_path and os.path.exists(socket_path):
        try:
            os.unlink(socket_path)
        except OSError:
            pass


def handle_signal(signum: int, frame) -> None:
    """Handle shutdown signals.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    log("info", f"Received signal {signum}, shutting down")
    sys.exit(0)


def handle_request(sock: socket.socket, cfg: config.Config) -> None:
    """Handle a single authentication request.

    Args:
        sock: Client socket
        cfg: Config instance
    """
    file_obj = None
    try:
        sock.settimeout(cfg["timeout"])
        file_obj = sock.makefile("rwb")
        request = protocol.parse_request(file_obj)
    except protocol.ProtocolError as e:
        log("warning", f"Protocol error: {e}")
        if file_obj:
            try:
                protocol.send_fail(file_obj, str(e))
            except Exception:
                pass
        return

    log("debug", f"Auth request: {request.user_realm} via {request.mechanism}")

    success, reason = auth_verify.verify_password(
        request.username, request.password, cfg
    )

    if success:
        log("info", f"Auth OK: {request.user_realm}")
        protocol.send_ok(file_obj, reason)
    else:
        log("info", f"Auth NO: {request.user_realm} - {reason}")
        protocol.send_no(file_obj, reason)

    if file_obj:
        file_obj.close()


def run_daemon(cfg: config.Config, foreground: bool = False) -> int:
    """Run the mcfeely-authd daemon.

    Args:
        cfg: Config instance
        foreground: If True, don't daemonize

    Returns:
        Exit code
    """
    setup_logging(cfg)

    log("info", f"Starting {DAEMON_NAME} v{VERSION}")

    valid, error = cfg.validate()
    if not valid:
        log("error", f"Configuration error: {error}")
        return 1

    socket_dir = os.path.dirname(cfg["socket_path"])
    if socket_dir:
        os.makedirs(socket_dir, mode=0o755, exist_ok=True)

    if os.path.exists(cfg["socket_path"]):
        os.unlink(cfg["socket_path"])

    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_sock.bind(cfg["socket_path"])
    os.chmod(cfg["socket_path"], stat.S_IRWXO | stat.S_IRWXG | stat.S_IRWXU)

    try:
        import pwd as pwd_mod

        try:
            pw = pwd_mod.getpwnam("postoffice")
            os.chown(cfg["socket_path"], pw.pw_uid, pw.pw_gid)
        except (KeyError, ImportError):
            pass
    except Exception:
        pass

    server_sock.listen(5)

    if not foreground:
        daemonize(cfg)

    log("info", f"Listening on {cfg["socket_path"]}")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGHUP, handle_signal)

    while True:
        try:
            client_sock, _ = server_sock.accept()
        except OSError as e:
            if e.errno == errno.EINTR:
                continue
            raise

        pid = os.fork()
        if pid == 0:
            server_sock.close()
            try:
                handle_request(client_sock, cfg)
            finally:
                client_sock.close()
                sys.exit(0)
        else:
            client_sock.close()
            try:
                os.waitpid(pid, 0)
            except OSError:
                pass


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description=f"{DAEMON_NAME} - SASL authentication daemon for mistermcfeely",
    )
    parser.add_argument(
        "-f",
        "--foreground",
        action="store_true",
        help="Run in foreground (don't daemonize)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to configuration file",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{DAEMON_NAME} {VERSION}",
    )
    parser.add_argument(
        "--test",
        metavar="USER",
        help="Test authentication for USER (reads password from stdin)",
    )

    args = parser.parse_args()

    cfg = config.load_config(args.config)

    if args.test:
        user = args.test
        password = sys.stdin.readline().rstrip("\n")

        success, reason = auth_verify.verify_password(user, password, cfg)

        if success:
            print(f"OK: {reason}")
            return 0
        else:
            print(f"NO: {reason}")
            return 1

    return run_daemon(cfg, foreground=args.foreground)


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "VERSION", "DAEMON_NAME"]
