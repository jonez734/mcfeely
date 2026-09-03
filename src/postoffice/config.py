# postoffice/config.py
# Configuration for postoffice service

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def get_package_data_path(filename: str) -> Path:
    """Get path to a file in the bed package data directory."""
    try:
        import importlib.resources
        return Path(str(importlib.resources.files("bed")) + "/data/" + filename)
    except (ModuleNotFoundError, TypeError):
        return Path("/etc/bed") / filename


def load_postoffice_defaults() -> Dict[str, Any]:
    """Load default configuration from bed.json package data."""
    bed_json_path = get_package_data_path("bed.json")
    if bed_json_path.exists():
        with open(bed_json_path) as f:
            return json.load(f)
    return {}


def get_postoffice_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get postoffice configuration from explicit sources.

    When ``config`` is provided, returns its ``postoffice`` sub-dict.
    Otherwise loads explicit configuration (env vars, env-derived
    mailboxes, overrides) without merging bed.json defaults.
    """
    if config is not None:
        return config.get("postoffice", {})

    return load_explicit_config().get("postoffice", {})


def _parse_dsn(dsn: str) -> dict[str, str]:
    """Parse a DSN string into a dict."""
    params = {}
    for part in dsn.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key] = value
    return params


def _parse_accept_self_signed(params: dict[str, str]) -> bool:
    """Resolve the accept_self_signed flag from a parsed DSN dict.

    Accepts ``accept_self_signed=true|false`` (preferred) or
    ``insecure=true|false`` as an alias. Defaults to ``True`` so
    self-signed local Cyrus certs work out of the box.
    """
    raw = params.get("accept_self_signed", params.get("insecure", "true"))
    return str(raw).lower() == "true"


def _load_mailboxes_from_env() -> list:
    """Load mailbox configurations from environment variables.

    DSN format (comma-separated for multiple mailboxes):
        POSTOFFICE_MAILBOXES=host=imap.example.com user=admin password=secret,host=imap2.example.com user=u2 pass=p2

    Single mailbox shorthand:
        POSTOFFICE_MAILBOX=host=imap.example.com user=admin password=secret

    ``accept_self_signed`` (alias: ``insecure``) defaults to ``true`` so
    self-signed local Cyrus certs work without extra flags. Set to
    ``false`` per mailbox to require strict CA verification.
    """
    mailboxes = []

    dsn_list = os.environ.get("POSTOFFICE_MAILBOXES", "")
    if dsn_list:
        for dsn in dsn_list.split(","):
            dsn = dsn.strip()
            if dsn:
                params = _parse_dsn(dsn)
                mailboxes.append({
                    "host": params.get("host", ""),
                    "username": params.get("user", params.get("username", "")),
                    "password": params.get("password", params.get("pass", "")),
                    "mailbox": params.get("mailbox", "INBOX"),
                    "use_ssl": params.get("ssl", params.get("use_ssl", "true")).lower() == "true",
                    "port": int(params["port"]) if "port" in params else None,
                    "accept_self_signed": _parse_accept_self_signed(params),
                })

    single_dsn = os.environ.get("POSTOFFICE_MAILBOX", "")
    if single_dsn:
        params = _parse_dsn(single_dsn)
        mailboxes.append({
            "host": params.get("host", ""),
            "username": params.get("user", params.get("username", "")),
            "password": params.get("password", params.get("pass", "")),
            "mailbox": params.get("mailbox", "INBOX"),
            "use_ssl": params.get("ssl", params.get("use_ssl", "true")).lower() == "true",
            "port": int(params["port"]) if "port" in params else None,
            "accept_self_signed": _parse_accept_self_signed(params),
        })

    return mailboxes


def load_config(
    config_file: Optional[str] = None,
    env_prefix: str = "POSTOFFICE_",
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Load postoffice configuration with priority order:
        1. Command line / overrides (highest)
        2. bed.json file (if provided)
        3. bed.json defaults (lowest)
    
    Environment variables:
        POSTOFFICE_<SECTION>_<KEY>=value or POSTOFFICE_<KEY>=value
        Examples: POSTOFFICE_ENABLED=true, POSTOFFICE_POLL_INTERVAL=60
    """
    config = load_postoffice_defaults()
    
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = json.load(f)
            config = _merge_config(config, file_config)
    
    # Try to find bed.json if not provided
    if not config_file:
        env_path = os.environ.get("BED_CONFIG")
        user_path = os.path.expanduser("~/.bbsengine6/bed.json")
        system_path = "/etc/bed/bed.json"
        
        for path in [env_path, user_path, system_path]:
            if path and Path(path).exists():
                with open(path) as f:
                    file_config = json.load(f)
                    config = _merge_config(config, file_config)
                break
    
    # Merge env config into postoffice section
    env_config = _load_from_env(env_prefix)
    if env_config:
        if "postoffice" not in config:
            config["postoffice"] = {}
        config["postoffice"] = _merge_config(config["postoffice"], env_config)
    
    # Load mailboxes from environment
    mailboxes = _load_mailboxes_from_env()
    if mailboxes:
        if "postoffice" not in config:
            config["postoffice"] = {}
        existing = config["postoffice"].get("mailboxes")
        if isinstance(existing, list):
            config["postoffice"]["mailboxes"] = existing + mailboxes
        else:
            config["postoffice"]["mailboxes"] = mailboxes
    
    config = _merge_config(config, overrides)
    
    return config


def _load_from_env(prefix: str) -> Dict[str, Any]:
    """Load configuration from environment variables.
    
    Variable format: <PREFIX><KEY>=value
    Example: POSTOFFICE_ENABLED=true, POSTOFFICE_POLL_INTERVAL=60
    Results in: {"enabled": true, "poll_interval": 60}
    """
    config = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        
        config_key = key[len(prefix):]
        
        if value.lower() in ("true", "false"):
            config[config_key.lower()] = value.lower() == "true"
        elif value.isdigit():
            config[config_key.lower()] = int(value)
        else:
            config[config_key.lower()] = value
    
    return config


def _merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge override into base config."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result


def reload_config() -> Dict[str, Any]:
    """Reload configuration from postoffice.json, ignoring any overrides."""
    return load_postoffice_defaults()


def load_explicit_config(
    env_prefix: str = "POSTOFFICE_",
    **overrides: Any,
) -> Dict[str, Any]:
    """
    Load postoffice configuration from explicit sources only:
    environment variables (POSTOFFICE_*), POSTOFFICE_MAILBOX(ES) DSNs,
    and keyword overrides. Unlike load_config(), this does NOT merge
    bed.json defaults, so an unset environment yields {"postoffice": {}}.
    """
    config: Dict[str, Any] = {}
    env_config = _load_from_env(env_prefix)
    if env_config:
        config["postoffice"] = env_config
    mailboxes = _load_mailboxes_from_env()
    if mailboxes:
        if "postoffice" not in config:
            config["postoffice"] = {}
        config["postoffice"]["mailboxes"] = mailboxes
    if overrides:
        config = _merge_config(config, overrides)
    return config
