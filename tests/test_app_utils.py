"""Tests for dependency-free BACstac helpers."""

import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).parents[1] / "engelsoft_bacstac" / "rootfs" / "usr" / "bin"
sys.path.insert(0, str(APP_DIR))

from app_utils import bacnet_identifier_sort_key  # noqa: E402


class BacnetIdentifierSortKeyTests(unittest.TestCase):
    """Verify the natural order shared with the Beacon integration."""

    def test_instances_are_sorted_numerically(self) -> None:
        identifiers = ["analogInput:100", "analogInput:10", "analogInput:2", "analogInput:1"]
        self.assertEqual(
            sorted(identifiers, key=bacnet_identifier_sort_key),
            ["analogInput:1", "analogInput:2", "analogInput:10", "analogInput:100"],
        )

    def test_object_types_are_sorted_before_instances(self) -> None:
        identifiers = ["binaryValue:1", "analogInput:10", "analogInput:2"]
        self.assertEqual(
            sorted(identifiers, key=bacnet_identifier_sort_key),
            ["analogInput:2", "analogInput:10", "binaryValue:1"],
        )

    def test_device_ids_support_colon_and_comma(self) -> None:
        identifiers = ["device:10", "device,2", "device:1"]
        self.assertEqual(
            sorted(identifiers, key=bacnet_identifier_sort_key),
            ["device:1", "device,2", "device:10"],
        )

    def test_malformed_identifiers_are_still_deterministic(self) -> None:
        identifiers = ["unknown:B", "unknown:a", "unknown"]
        self.assertEqual(
            sorted(identifiers, key=bacnet_identifier_sort_key),
            ["unknown", "unknown:a", "unknown:B"],
        )


if __name__ == "__main__":
    unittest.main()
