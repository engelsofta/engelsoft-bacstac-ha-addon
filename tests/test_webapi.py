"""Small compatibility checks for the FastAPI application."""

import asyncio
import os
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).parents[1] / "engelsoft_bacstac" / "rootfs" / "usr" / "bin"
sys.path.insert(0, str(APP_DIR))
os.environ["BACSTAC_VERSION"] = "test-version"

import webAPI  # noqa: E402


class WebApiTests(unittest.TestCase):
    """Verify startup-independent API behavior."""

    def test_build_version_is_exposed(self) -> None:
        self.assertEqual(webAPI.app.version, "test-version")
        self.assertEqual(webAPI.protocol_info()["app_version"], "test-version")

    def test_commands_report_not_ready_before_bacnet_startup(self) -> None:
        whois_response = asyncio.run(webAPI.whois_command())
        iam_response = asyncio.run(webAPI.iam_command())
        self.assertEqual(whois_response.status_code, 503)
        self.assertEqual(iam_response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
