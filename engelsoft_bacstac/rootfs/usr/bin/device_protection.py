"""Persistent per-device BACnet protection settings.

Modified by engelsofta in 2026; derived from the Bepacom BACnet/IP add-on.
"""

import json
import os
from typing import Any


CONFIG_PATH = os.environ.get(
    "BACSTAC_DEVICE_PROTECTION_PATH", "/data/device_protection.json"
)
DEFAULT_RULE = {
    "deviceID": "all",
    "CoV_lifetime": 600,
    "CoV_limit": 20,
    "resub_on_iam": True,
    "reread_on_iam": False,
}


def _normalize(rule: dict[str, Any], device_id: str | None = None) -> dict[str, Any]:
    """Return a validated rule using safe bounds."""
    base = DEFAULT_RULE.copy()
    base.update(rule or {})
    base["deviceID"] = str(device_id or base.get("deviceID") or "all")
    base["CoV_lifetime"] = min(28800, max(60, int(base["CoV_lifetime"])))
    base["CoV_limit"] = min(1000, max(0, int(base["CoV_limit"])))
    base["resub_on_iam"] = bool(base["resub_on_iam"])
    base["reread_on_iam"] = bool(base["reread_on_iam"])
    return base


def load_rules(legacy_rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Load rules and migrate the former add-on option on first use."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            payload = json.load(config_file)
        rules = payload.get("rules", payload) if isinstance(payload, dict) else payload
        if isinstance(rules, list) and rules:
            return [_normalize(rule) for rule in rules if isinstance(rule, dict)]
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
        pass

    rules = legacy_rules if isinstance(legacy_rules, list) and legacy_rules else [DEFAULT_RULE]
    normalized = [_normalize(rule) for rule in rules if isinstance(rule, dict)]
    if not any(rule["deviceID"] == "all" for rule in normalized):
        normalized.insert(0, DEFAULT_RULE.copy())
    save_rules(normalized)
    return normalized


def save_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and atomically persist all rules."""
    normalized = [_normalize(rule) for rule in rules if isinstance(rule, dict)]
    if not any(rule["deviceID"] == "all" for rule in normalized):
        normalized.insert(0, DEFAULT_RULE.copy())
    directory = os.path.dirname(CONFIG_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    temporary_path = f"{CONFIG_PATH}.tmp"
    with open(temporary_path, "w", encoding="utf-8") as config_file:
        json.dump({"version": 1, "rules": normalized}, config_file, indent=2)
        config_file.write("\n")
    os.replace(temporary_path, CONFIG_PATH)
    return normalized


def upsert_rule(
    rules: list[dict[str, Any]], device_id: str, values: dict[str, Any]
) -> list[dict[str, Any]]:
    """Create or replace one rule."""
    device_id = str(device_id)
    updated = [rule for rule in rules if rule.get("deviceID") != device_id]
    updated.append(_normalize(values, device_id))
    updated.sort(key=lambda rule: (rule["deviceID"] != "all", rule["deviceID"]))
    return save_rules(updated)


def remove_rule(rules: list[dict[str, Any]], device_id: str) -> list[dict[str, Any]]:
    """Remove an override; the global default itself cannot be removed."""
    if device_id == "all":
        return save_rules(rules)
    return save_rules([rule for rule in rules if rule.get("deviceID") != device_id])
