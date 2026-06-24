# postoffice/config.py
# Configuration for postoffice service

import os
from typing import Any, Dict, Optional


def get_postoffice_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Get postoffice configuration, loading from environment if not provided.
    
    Environment variables (with prefix POSTOFFICE_ or CASINO_POSTOFFICE_):
        *_ENABLED - Enable/disable the service
        *_POLL_INTERVAL - Seconds between mailbox checks
    
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
    env_prefix: str = "CASINO_",
    **overrides: Any,
) -> Dict[str, Any]:
    """Load postoffice configuration.
    
    Priority order:
    1. Command line / overrides (highest)
    2. Config file (if provided)
    3. Environment variables
    4. Empty defaults (lowest)
    
    Environment variables use format: CASINO_POSTOFFICE_<KEY>=value
    Results in nested config: {"postoffice": {"key": value, ...}}
    """
    import json
    
    config: Dict[str, Any] = {"postoffice": {}}
    
    if config_file and os.path.exists(config_file):
        with open(config_file) as f:
            file_config = json.load(f)
            config = _merge_config(config, file_config)
    
    # Add environment-based config (support both CASINO_POSTOFFICE_ and POSTOFFICE_ prefixes)
    env_config = _load_from_env(env_prefix)
    config = _merge_config(config, env_config)
    
    # Also check POSTOFFICE_ prefix as fallback
    if "postoffice" not in config or not config.get("postoffice"):
        postoffice_env = _load_from_env("POSTOFFICE_")
        config = _merge_config(config, postoffice_env)
    
    config = _merge_config(config, overrides)
    
    return config


def _load_from_env(prefix: str) -> Dict[str, Any]:
    """Load configuration from environment variables.
    
    Variable format: <PREFIX>_<SECTION>_<KEY>=value or <PREFIX><KEY>=value
    Example: CASINO_POSTOFFICE_ENABLED=true
    Results in: {"postoffice": {"enabled": true, ...}}
    """
    config: Dict[str, Any] = {}
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        
        config_key = key[len(prefix):]
        
        if "_" in config_key:
            parts = config_key.split("_", 1)
            section = parts[0].lower()
            key_name = parts[1].lower()
            
            if section not in config:
                config[section] = {}
            
            if value.lower() in ("true", "false"):
                config[section][key_name] = value.lower() == "true"
            elif value.isdigit():
                config[section][key_name] = int(value)
            else:
                config[section][key_name] = value
        else:
            key_name = config_key.lower()
            if value.lower() in ("true", "false"):
                config[key_name] = value.lower() == "true"
            elif value.isdigit():
                config[key_name] = int(value)
            else:
                config[key_name] = value
    
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
