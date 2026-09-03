# config.py
# Configuration management for mcfeely-authd.
#
# This module is a thin facade over bbsengine6.config: it owns the
# mcfeely_authd-specific search paths and recoverable-error semantics,
# and delegates generic JSON/env/default-merge machinery to
# bbsengine6.config so the precedence chain matches bed.config,
# zoidoffice.conf, and the other bbsengine6-aware apps.
#
# The resulting object is a Config instance that behaves like a dict
# (``cfg["key"]``, ``cfg.get("key", default)``, ``"key" in cfg``,
# ``cfg.items()``) and additionally exposes the helpers needed by
# the auth-verify path: ``make_args()``, ``get_pool()``, ``close_pool()``,
# and ``validate()``.

import argparse
import errno
import os
from pathlib import Path
from typing import Any, Optional

from bbsengine6 import config as be6_config

DAEMON_NAME = "mcfeely-authd"

KNOWN_SECTIONS: frozenset[str] = frozenset(
    {"global", "auth", "database", "logging", "daemon", "socket"}
)

HARDCODED_DEFAULTS: dict[str, Any] = {
    "socket_path": "/var/run/postoffice-authd/mux",
    "pid_file": "/var/run/postoffice-authd/mcfeely-authd.pid",
    "log_file": "/var/log/postoffice-authd.log",
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

PATH_KEY_SUFFIXES = be6_config.PATH_KEY_SUFFIXES

RECOVERABLE_ERRNOS = frozenset(
    {
        errno.EACCES,
        errno.EIO,
        errno.ESTALE,
        errno.ETXTBSY,
        errno.ENETUNREACH,
        errno.EHOSTUNREACH,
        errno.ECONNREFUSED,
        errno.ETIMEDOUT,
    }
)


def _is_recoverable_load_error(exc: BaseException) -> bool:
    import socket as _socket

    if isinstance(exc, (_socket.gaierror, _socket.timeout, PermissionError)):
        return True
    if isinstance(exc, OSError):
        return getattr(exc, "errno", None) in RECOVERABLE_ERRNOS
    return False


def _bundled_config_path() -> Path:
    return Path(__file__).resolve().parents[3] / "etc-postoffice" / "mcfeely-authd.json"


def _default_search_paths(explicit: Optional[str]) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(Path("/etc/postoffice/mcfeely-authd.json"))
    bundled = _bundled_config_path()
    if bundled.exists():
        candidates.append(bundled)
    return candidates


_SECTION_TO_KEY: dict[tuple[str, str], str] = {
    ("socket", "path"): "socket_path",
    ("logging", "file"): "log_file",
    ("logging", "level"): "log_level",
    ("logging", "syslog"): "log_syslog",
    ("auth", "fallback_pam"): "fallback_pam",
    ("auth", "pam_service"): "pam_service",
    ("database", "dsn"): "database_dsn",
    ("database", "user"): "database_user",
    ("database", "password"): "database_password",
    ("daemon", "pid_file"): "pid_file",
    ("daemon", "timeout"): "timeout",
    ("daemon", "max_children"): "max_children",
}


def _flatten_sections(cfg: dict[str, Any]) -> dict[str, Any]:
    """Map nested JSON sections into the flat keys consumers expect.

    The JSON file uses nested sections
    (``{"socket": {"path": "..."}, "logging": {"level": "..."}}``);
    callers expect flat keys (``socket_path``, ``log_level``).
    """
    out: dict[str, Any] = {}
    for (section, subkey), flat_key in _SECTION_TO_KEY.items():
        section_cfg = cfg.get(section)
        if not isinstance(section_cfg, dict):
            continue
        if subkey in section_cfg:
            out[flat_key] = section_cfg[subkey]
    return out


def load_config(
    config_file: Optional[str] = None,
    *,
    overrides: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Load the merged JSON config dict.

    Search order (first existing file wins):
      1. ``$MCFEELY_AUTHD_CONFIG`` env var (if set and file exists)
      2. explicit ``config_file`` argument
      3. /etc/postoffice/mcfeely-authd.json
      4. <repo>/etc-postoffice/mcfeely-authd.json (bundled fallback)

    The returned dict is layered with ``HARDCODED_DEFAULTS`` so callers
    always see every key (``cfg.get("anything")`` never raises).
    """
    candidates = _default_search_paths(config_file)
    cfg, _used = be6_config.search_config(
        candidates,
        env_var="MCFEELY_AUTHD_CONFIG",
    )
    cfg = be6_config.expand_value(cfg)
    cfg = be6_config.expand_paths(cfg)
    flat = _flatten_sections(cfg)
    merged = be6_config.deep_merge(dict(HARDCODED_DEFAULTS), flat)
    if overrides:
        merged = be6_config.deep_merge(merged, dict(overrides))
    return merged


def get_db_defaults(
    json_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Resolve database arg defaults from config + env + hardcoded.

    Mirrors zoidoffice.conf.get_db_defaults: returns a dict suitable
    as ``defaults=`` for ``database.buildargdatabasegroup`` or any
    argparse group that wants the canonical ``databasename`` /
    ``databasehost`` / ``databaseport`` / ``databaseuser`` /
    ``databasepassword`` keys plus the schema-name fields.

    Precedence (top wins): env > JSON > hardcoded.
    """
    cfg = json_config if json_config is not None else load_config()
    return be6_config.build_argparse_defaults(
        cfg,
        section="database",
        keys=[
            "databasename",
            "databasehost",
            "databaseport",
            "databaseuser",
            "databasepassword",
            "databaseschema",
            "bbsengineschema",
        ],
        env_prefix="BBSENGINE6_DB",
        env_key_map={
            "databasename": "BBSENGINE6_DBNAME",
            "databasehost": "BBSENGINE6_DBHOST",
            "databaseport": "BBSENGINE6_DBPORT",
            "databaseuser": "BBSENGINE6_DBUSER",
            "databasepassword": "BBSENGINE6_DBPASSWORD",
            "databaseschema": "BBSENGINE6_DBSCHEMA",
            "bbsengineschema": "BBSENGINE6_DBENGINESCHEMA",
        },
        global_section="global",
        hardcoded_defaults={
            "databasename": "zoid6test",
            "databasehost": "localhost",
            "databaseport": 5432,
        },
        coerce={"databaseport": int},
    )


class Config:
    """Dict-like configuration object with DAL-bridge helpers.

    Backed by the dict returned from :func:`load_config`. Exposes
    ``__getitem__`` / ``__setitem__`` / ``__contains__`` / ``items``
    / ``get`` for plain dict access, plus ``make_args`` /
    ``get_pool`` / ``close_pool`` / ``validate`` for the auth-verify
    path.

    Deliberately does NOT expose per-key property accessors: callers
    that want a value should use ``cfg["key"]``. This matches the
    other bbsengine6-aware apps (bed.config returns plain dicts;
    zoidoffice.conf returns plain dicts).
    """

    def __init__(
        self,
        config_file: Optional[str] = None,
        *,
        overrides: Optional[dict[str, Any]] = None,
    ):
        self._data: dict[str, Any] = load_config(config_file, overrides=overrides)
        self._pool: Optional[Any] = None

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def items(self):
        return self._data.items()

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def make_args(self) -> argparse.Namespace:
        """Build an argparse.Namespace from the database config.

        bbsengine6.database.getpool() reads args.databasename /
        databasehost / databaseport / databaseuser / databasepassword
        via getattr, so a plain Namespace is sufficient.

        Backwards compatibility: the legacy INI-format config stored
        ``database_dsn`` / ``database_user`` / ``database_password``.
        If those legacy keys are present and the bbsengine6-style keys
        are missing, parse the DSN to derive them.
        """
        args = {
            "databasename": self._data.get("databasename"),
            "databasehost": self._data.get("databasehost"),
            "databaseport": self._data.get("databaseport"),
            "databaseuser": self._data.get("databaseuser"),
            "databasepassword": self._data.get("databasepassword"),
        }

        dsn = self._data.get("database_dsn")
        if dsn and not any(
            args[k] for k in ("databasename", "databaseuser", "databasehost")
        ):
            args = self._merge_dsn_into_args(args, dsn)

        if self._data.get("database_user"):
            args["databaseuser"] = self._data["database_user"]
        if self._data.get("database_password"):
            args["databasepassword"] = self._data["database_password"]

        return argparse.Namespace(**args)

    @staticmethod
    def _merge_dsn_into_args(args: dict, dsn: str) -> dict:
        out = dict(args)
        if "/" in dsn:
            out["databasename"] = dsn.split("/")[-1] or "zoid6test"
        if "@" in dsn:
            user_part = dsn.split("://")[1].split("@")[0]
            if ":" in user_part:
                out["databaseuser"] = user_part.split(":")[0]
                out["databasepassword"] = user_part.split(":")[1]
            else:
                out["databaseuser"] = user_part
            host_part = dsn.split("@")[1].split("/")[0]
            if ":" in host_part:
                out["databasehost"] = host_part.split(":")[0]
                out["databaseport"] = int(host_part.split(":")[1])
        return out

    def get_pool(self) -> Any:
        """Return a cached psycopg_pool.ConnectionPool for this config."""
        if self._pool is None:
            from bbsengine6 import database

            self._pool = database.getpool(self.make_args())
        return self._pool

    def close_pool(self) -> None:
        """Close and discard the cached pool (if any)."""
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
        socket_path = self._data.get("socket_path") or ""
        if not socket_path:
            return False, "socket_path is required"

        socket_dir = os.path.dirname(socket_path)
        if socket_dir and not os.path.exists(socket_dir):
            try:
                os.makedirs(socket_dir, mode=0o755)
            except OSError as e:
                if not _is_recoverable_load_error(e):
                    return False, f"Cannot create socket directory: {e}"

        log_file = self._data.get("log_file") or ""
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, mode=0o755)
            except OSError as e:
                if not _is_recoverable_load_error(e):
                    return False, f"Cannot create log directory: {e}"

        return True, None


__all__ = [
    "Config",
    "load_config",
    "get_db_defaults",
    "HARDCODED_DEFAULTS",
    "KNOWN_SECTIONS",
    "PATH_KEY_SUFFIXES",
]
