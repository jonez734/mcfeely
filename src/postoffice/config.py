# postoffice/config.py
# Configuration for postoffice service

import os
from typing import Any, Dict, Optional


def get_postoffice_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get postoffice configuration, loading from environment if not provided.
    
    Environment variables (with prefix POSTOFFICE_):
        POSTOFFICE_ENABLED - Enable/disable the service
        POSTOFFICE_POLL_INTERVAL - Seconds between mailbox checks
    
    Args:
        config: Optional config dict to use instead of loading from env
        
    Returns:
        Dict with postoffice configuration
    """
    if config is not None:
        return config.get("postoffice", {})
    
    return {}


def _load_mailboxes_from_env() -> list:
    """Load mailbox configurations from environment variables.
    
    Format for each mailbox:
        POSTOFFICE_MAILBOX_<N>_HOST=imap.example.com
        POSTOFFICE_MAILBOX_<N>_USER=user
        POSTOFFICE_MAILBOX_<N>_PASS=password
        POSTOFFICE_MAILBOX_<N>_MAILBOX=INBOX
        POSTOFFICE_MAILBOX_<N>_SSL=true
    """
    mailboxes = []
    n = 0
    while True:
        host = os.environ.get(f"POSTOFFICE_MAILBOX_{n}_HOST")
        if host is None:
            break
        
        mailboxes.append({
            "host": host,
            "username": os.environ.get(f"POSTOFFICE_MAILBOX_{n}_USER", ""),
            "password": os.environ.get(f"POSTOFFICE_MAILBOX_{n}_PASS", ""),
            "mailbox": os.environ.get(f"POSTOFFICE_MAILBOX_{n}_MAILBOX", "INBOX"),
            "use_ssl": os.environ.get(f"POSTOFFICE_MAILBOX_{n}_SSL", "true").lower() == "true",
        })
        n += 1
    
    return mailboxes


def load_config(
    config_file: Optional[str] = None,
    env_prefix: str = "POSTOFFICE_",
    **overrides: Any,
) -> Dict[str, Any]:
    """Load postoffice configuration.
    
    Priority order:
    1. Command line / overrides (highest)
    2. Config file (if provided)
    3. Environment variables
    4. Empty defaults (lowest)
    
    Environment variables use format: POSTOFFICE_<KEY>=value
    Results in nested config: {"postoffice": {"key": value, ...}}
    """
    import json
    
    config: Dict[str, Any] = {}
    
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = json.load(f)
            config = _merge_config(config, file_config)
    
    # Add environment-based config
    env_config = _load_from_env(env_prefix)
    if env_config:
        if "postoffice" not in config:
            config["postoffice"] = {}
        config["postoffice"] = _merge_config(config["postoffice"], env_config)
    
    config = _merge_config(config, overrides)
    
    return config


def _load_from_env(prefix: str) -> Dict[str, Any]:
    """Load configuration from environment variables.
    
    Variable format: <PREFIX><KEY>=value
    Example: POSTOFFICE_ENABLED=true
    Results in: {"postoffice": {"enabled": true, ...}}
    """
    config: Dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        
        config_key = key[len(prefix):].lower()
        
        if value.lower() in ("true", "false"):
            config[config_key] = value.lower() == "true"
        elif value.isdigit():
            config[config_key] = int(value)
        else:
            config[config_key] = value
    
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
