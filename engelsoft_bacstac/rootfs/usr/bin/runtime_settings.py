"""Persistent live BACstac settings.

Modified by engelsofta in 2026; derived from the Bepacom BACnet/IP add-on.
"""

import json
import os
from typing import Any

CONFIG_PATH = os.environ.get("BACSTAC_RUNTIME_SETTINGS_PATH", "/data/runtime_settings.json")
DEFAULTS = {
    "managed_poll_rate": 10,
    "managed_cov_subscription_delay_ms": 1000,
    "managed_cov_fallback_timeout": 30,
    "defaultPriority": 15,
}


def normalize(values: dict[str, Any] | None) -> dict[str, int]:
    data = DEFAULTS.copy()
    data.update(values or {})
    return {
        "managed_poll_rate": min(300, max(3, int(data["managed_poll_rate"]))),
        "managed_cov_subscription_delay_ms": min(30000, max(0, int(data["managed_cov_subscription_delay_ms"]))),
        "managed_cov_fallback_timeout": min(600, max(10, int(data["managed_cov_fallback_timeout"]))),
        "defaultPriority": min(16, max(1, int(data["defaultPriority"]))),
    }


def save(values: dict[str, Any]) -> dict[str, int]:
    settings = normalize(values)
    directory = os.path.dirname(CONFIG_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary = f"{CONFIG_PATH}.tmp"
    with open(temporary, "w", encoding="utf-8") as settings_file:
        json.dump({"version": 1, "settings": settings}, settings_file, indent=2)
        settings_file.write("\n")
    os.replace(temporary, CONFIG_PATH)
    return settings


def load(legacy: dict[str, Any] | None = None) -> dict[str, int]:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as settings_file:
            payload = json.load(settings_file)
        return normalize(payload.get("settings", payload))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
        migrated = {key: (legacy or {}).get(key, value) for key, value in DEFAULTS.items()}
        return save(migrated)
