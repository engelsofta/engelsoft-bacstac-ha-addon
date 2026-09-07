"""Small dependency-free helpers shared by the BACstac application."""

import re
from typing import Any

_BACNET_IDENTIFIER_PATTERN = re.compile(r"^(.*?)[,:](\d+)$")


def bacnet_identifier_sort_key(identifier: Any) -> tuple[str, int, str]:
    """Sort BACnet identifiers by type and numeric instance like Beacon."""
    value = str(identifier)
    match = _BACNET_IDENTIFIER_PATTERN.fullmatch(value)
    if match is None:
        return value.casefold(), 999_999_999, value.casefold()
    return match.group(1).casefold(), int(match.group(2)), value.casefold()
