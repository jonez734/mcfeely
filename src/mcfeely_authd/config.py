# config.py
# Configuration management for mcfeely-authd.
#
# Loads INI-style config files (legacy format), exposes a Config class
# with property-style access for ergonomic callers, and provides
# make_args() / get_pool() helpers that bridge to bbsengine6.database
# (the DAL the rest of mistermcfeely uses). The two layers coexist so
# existing CLI callers and tests that use the property/dict-like API
# keep working while DB code goes through the standard pool.

import os
from typing import Any, Optional


DEFAULT_CONFIG = {
    "socket_path": "/var/run/mcfeely-authd/mux",
    "pid_file": "/var/run/mcfeely-authd/mcfeely-authd.pid",
    "log_file": "/var/log/mcfeely-authd.log",
    "log_level": "INFO",
    "log_syslog": True,
    "fallback_pam": True,
    "pam_service": "imap",
    "database_dsn": "postgresql://localhost/zoid6test",
    "database_user": "",
    "database_password": "",
    "timeout": 30,
    "max_children": 50,
}


class Config:
    """Configuration for mcfeely-authd daemon."""

    def __init__(self, config_file: Optional[str] = None, **overrides):
        self._config = DEFAULT_CONFIG.copy()
        self._pool: Optional[Any] = None
        self._load_config_file(config_file)
        self._apply_overrides(overrides)
        self._apply_env_vars()

    def _load_config_file(self, config_file: Optional[str]) -> None:
        """Load configuration from INI-style config file."""
        if not config_file:
            config_file = os.environ.get(
                "MCFEELY_AUTHD_CONFIG",
                "/etc/postoffice/mcfeely-authd.conf",
            )

        if not os.path.exists(config_file):
            return

        try:
            import configparser
        except ImportError:
            import ConfigParser as configparser  # Python 2 fallback

        parser = configparser.ConfigParser()
        parser.read(config_file)

        if parser.has_section("database"):
            self._config["database_dsn"] = parser.get(
                "database", "dsn", fallback=self._config["database_dsn"]
            )
            self._config["database_user"] = parser.get(
                "database", "user", fallback=self._config["database_user"]
            )
            self._config["database_password"] = parser.get(
                "database", "password", fallback=self._config["database_password"]
            )

        if parser.has_section("auth"):
            self._config["fallback_pam"] = parser.getboolean(
                "auth", "fallback_pam", fallback=self._config["fallback_pam"]
            )
            self._config["pam_service"] = parser.get(
                "auth", "pam_service", fallback=self._config["pam_service"]
            )

        if parser.has_section("socket"):
            self._config["socket_path"] = parser.get(
                "socket", "path", fallback=self._config["socket_path"]
            )

        if parser.has_section("logging"):
            self._config["log_file"] = parser.get(
                "logging", "file", fallback=self._config["log_file"]
            )
            self._config["log_level"] = parser.get(
                "logging", "level", fallback=self._config["log_level"]
            )
            self._config["log_syslog"] = parser.getboolean(
                "logging", "syslog", fallback=self._config["log_syslog"]
            )

        if parser.has_section("daemon"):
            self._config["pid_file"] = parser.get(
                "daemon", "pid_file", fallback=self._config["pid_file"]
            )
            self._config["timeout"] = parser.getint(
                "daemon", "timeout", fallback=self._config["timeout"]
            )
            self._config["max_children"] = parser.getint(
                "daemon", "max_children", fallback=self._config["max_children"]
            )

    def _apply_overrides(self, overrides: dict) -> None:
        """Apply keyword argument overrides."""
        for key, value in overrides.items():
            if key in self._config:
                self._config[key] = value

    def _apply_env_vars(self) -> None:
        """Apply environment variable overrides."""
        if "BBSENGINE6_DBNAME" in os.environ:
            dbname = os.environ["BBSENGINE6_DBNAME"]
            self._config["database_dsn"] = f"postgresql://localhost/{dbname}"

        if "POSTOFFICE_PASSWORD_KEY" in os.environ:
            self._config["encryption_key"] = os.environ["POSTOFFICE_PASSWORD_KEY"]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Get configuration value (dict-like access)."""
        return self._config[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set configuration value (dict-like access)."""
        self._config[key] = value

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._config

    def items(self):
        """Return config items for iteration."""
        return self._config.items()

    @property
    def socket_path(self) -> str:
        return self._config["socket_path"]

    @property
    def pid_file(self) -> str:
        return self._config["pid_file"]

    @property
    def log_file(self) -> str:
        return self._config["log_file"]

    @property
    def log_level(self) -> str:
        return self._config["log_level"]

    @property
    def log_syslog(self) -> bool:
        return self._config["log_syslog"]

    @property
    def fallback_pam(self) -> bool:
        return self._config["fallback_pam"]

    @property
    def pam_service(self) -> str:
        return self._config["pam_service"]

    @property
    def database_dsn(self) -> str:
        return self._config["database_dsn"]

    @property
    def database_user(self) -> str:
        return self._config["database_user"]

    @property
    def database_password(self) -> str:
        return self._config["database_password"]

    @property
    def timeout(self) -> int:
        return self._config["timeout"]

    @property
    def max_children(self) -> int:
        return self._config["max_children"]

    def get_database_args(self) -> dict:
        """Get database connection arguments.

        Returns a dict keyed by bbsengine6.database's expected names
        (``databasename``, ``databasehost``, ``databaseport``,
        ``databaseuser``, ``databasepassword``). Mirrors the rest of
        mistermcfeely (mailbox.py, lib.py, member_password.py, tui/*).
        """
        args = {
            "databasename": self._extract_dbname(),
        }

        dsn = self._config["database_dsn"]
        if "@" in dsn:
            # Parse user:pass@host/db format
            user_part = dsn.split("://")[1].split("@")[0]
            if ":" in user_part:
                args["databaseuser"] = user_part.split(":")[0]
                args["databasepassword"] = user_part.split(":")[1]
            else:
                args["databaseuser"] = user_part

            host_part = dsn.split("@")[1].split("/")[0]
            if ":" in host_part:
                args["databasehost"] = host_part.split(":")[0]
                args["databaseport"] = int(host_part.split(":")[1])

        if self._config["database_user"]:
            args["databaseuser"] = self._config["database_user"]
        if self._config["database_password"]:
            args["databasepassword"] = self._config["database_password"]

        return args

    def _extract_dbname(self) -> str:
        """Extract database name from DSN."""
        dsn = self._config["database_dsn"]
        if "/" in dsn:
            return dsn.split("/")[-1]
        return "zoid6test"

    def make_args(self) -> "argparse.Namespace":
        """Build an argparse.Namespace from get_database_args().

        bbsengine6.database.getpool() reads args.databasename /
        databasehost / databaseport / databaseuser / databasepassword
        via getattr, so a plain Namespace is sufficient.
        """
        import argparse
        a = self.get_database_args()
        return argparse.Namespace(
            databasename=a.get("databasename"),
            databasehost=a.get("databasehost"),
            databaseport=a.get("databaseport"),
            databaseuser=a.get("databaseuser"),
            databasepassword=a.get("databasepassword"),
        )

    def get_pool(self) -> Any:
        """Return a cached psycopg_pool.ConnectionPool for this config.

        Lazy-cached on first call; subsequent calls return the same
        pool so the daemon reuses one pool across many auth requests.
        """
        if self._pool is None:
            from bbsengine6 import database
            self._pool = database.getpool(self.make_args())
        return self._pool

    def close_pool(self) -> None:
        """Close and discard the cached pool (if any).

        Safe to call multiple times. Wired into the SIGTERM handler
        in a follow-up; provided here so tests can reset state.
        """
        if self._pool is not None:
            try:
                self._pool.close()
            except Exception:
                pass
            self._pool = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self._config["socket_path"]:
            return False, "socket_path is required"

        socket_dir = os.path.dirname(self._config["socket_path"])
        if socket_dir and not os.path.exists(socket_dir):
            try:
                os.makedirs(socket_dir, mode=0o755)
            except OSError as e:
                return False, f"Cannot create socket directory: {e}"

        log_dir = os.path.dirname(self._config["log_file"])
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, mode=0o755)
            except OSError as e:
                return False, f"Cannot create log directory: {e}"

        return True, None


def load_config(config_file: Optional[str] = None, **overrides) -> Config:
    """Load configuration from file and environment.

    Args:
        config_file: Path to config file (or None for default)
        **overrides: Key-value overrides

    Returns:
        Config instance
    """
    return Config(config_file=config_file, **overrides)


__all__ = ["Config", "load_config", "DEFAULT_CONFIG"]
