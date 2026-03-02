"""Network detection, proxy handling, and offline mode.

Every detector must import this module and call is_online() before
any network operation. This is the single source of truth for
network availability.
"""

import os
import socket
import time
from typing import Dict, Optional

# Module-level cache: None = not checked yet, True/False = result
_online_cache = None
_offline_forced = False

# Default timeout for the connectivity check (seconds)
CONNECTIVITY_TIMEOUT = 2.0

# Hosts to probe, in order — first success wins
_PROBE_HOSTS = [
    ("dns.google", 443),
    ("8.8.8.8", 53),
    ("1.1.1.1", 53),
]


def force_offline(offline: bool = True):
    """Force offline mode globally. Used by --offline flag."""
    global _offline_forced, _online_cache
    _offline_forced = offline
    if offline:
        _online_cache = False


def is_forced_offline() -> bool:
    """Check if offline mode was explicitly forced by the user."""
    return _offline_forced


def get_proxy_config() -> Dict[str, Optional[str]]:
    """Detect proxy configuration from environment variables.

    Returns a dict with http, https, and no_proxy settings.
    Respects both upper and lowercase variants (HTTP_PROXY / http_proxy).
    """
    proxies = {}
    for key in ("HTTP_PROXY", "http_proxy"):
        val = os.environ.get(key)
        if val:
            proxies["http"] = val
            break

    for key in ("HTTPS_PROXY", "https_proxy"):
        val = os.environ.get(key)
        if val:
            proxies["https"] = val
            break

    for key in ("NO_PROXY", "no_proxy"):
        val = os.environ.get(key)
        if val:
            proxies["no_proxy"] = val
            break

    return proxies


def get_requests_proxies() -> Optional[Dict[str, str]]:
    """Return proxy dict suitable for requests.get(proxies=...).

    Returns None if no proxies are configured (let requests use defaults).
    """
    config = get_proxy_config()
    if not config:
        return None
    result = {}
    if "http" in config:
        result["http"] = config["http"]
    if "https" in config:
        result["https"] = config["https"]
    return result if result else None


def is_online(timeout: float = CONNECTIVITY_TIMEOUT, force_recheck: bool = False) -> bool:
    """Check if the machine has internet connectivity.

    Uses a socket connection to well-known DNS servers with a short timeout.
    Results are cached for the lifetime of the process unless force_recheck=True.

    Args:
        timeout: Max seconds to wait for each probe (default 2.0).
        force_recheck: Bypass the cache and re-probe.

    Returns:
        True if any probe succeeds, False otherwise.
    """
    global _online_cache

    if _offline_forced:
        return False

    if _online_cache is not None and not force_recheck:
        return _online_cache

    for host, port in _PROBE_HOSTS:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            _online_cache = True
            return True
        except (socket.timeout, socket.error, OSError):
            continue

    _online_cache = False
    return False


def online_status_message() -> str:
    """Return a human-readable network status string."""
    if _offline_forced:
        return "Offline (forced via --offline flag)"

    online = is_online()
    proxies = get_proxy_config()

    parts = []
    if online:
        parts.append("Online")
    else:
        parts.append("Offline (no internet detected)")

    if proxies:
        proxy_str = ", ".join(
            "{}={}".format(k, v) for k, v in sorted(proxies.items())
        )
        parts.append("Proxies: {}".format(proxy_str))

    return " | ".join(parts)


def reset_cache():
    """Reset the online cache. Useful for testing."""
    global _online_cache, _offline_forced
    _online_cache = None
    _offline_forced = False
