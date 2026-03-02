"""Environment detector: locale, timezone, PATH, proxy vars, shell."""

import os
import time
from typing import Any, Dict, Optional


def detect() -> Dict[str, Any]:
    """Detect environment variables relevant to reproducibility."""
    # Locale
    locale_vars = {}
    for var in ("LC_ALL", "LC_CTYPE", "LANG", "LANGUAGE"):
        val = os.environ.get(var)
        if val:
            locale_vars[var] = val

    # Timezone
    tz = os.environ.get("TZ")
    if not tz:
        try:
            tz = time.tzname[0] if time.tzname else None
        except Exception:
            tz = None

    # PATH
    path = os.environ.get("PATH", "")

    # Proxy variables
    proxy_vars = {}
    for var in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
                "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy"):
        val = os.environ.get(var)
        if val:
            proxy_vars[var] = val

    # Shell
    shell = os.environ.get("SHELL", "unknown")

    # Conda-related env vars
    conda_vars = {}
    for var in ("CONDA_DEFAULT_ENV", "CONDA_PREFIX", "CONDA_EXE"):
        val = os.environ.get(var)
        if val:
            conda_vars[var] = val

    # Python-related env vars
    python_vars = {}
    for var in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE",
                "PYTHONHASHSEED", "PYTHONUNBUFFERED"):
        val = os.environ.get(var)
        if val:
            python_vars[var] = val

    # R-related env vars
    r_vars = {}
    for var in ("R_HOME", "R_LIBS", "R_LIBS_USER"):
        val = os.environ.get(var)
        if val:
            r_vars[var] = val

    return {
        "locale": locale_vars if locale_vars else {"LC_ALL": None},
        "timezone": tz,
        "PATH": path,
        "shell": shell,
        "proxy": proxy_vars if proxy_vars else None,
        "conda_env_vars": conda_vars if conda_vars else None,
        "python_env_vars": python_vars if python_vars else None,
        "r_env_vars": r_vars if r_vars else None,
    }


if __name__ == "__main__":
    import json
    result = detect()
    # Truncate PATH for display
    result_display = dict(result)
    if result_display.get("PATH"):
        entries = result_display["PATH"].split(":")
        result_display["PATH"] = "{} entries".format(len(entries))
        result_display["PATH_first_3"] = entries[:3]
    print(json.dumps(result_display, indent=2))
