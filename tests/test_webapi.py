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
from starlette.requests import Request  # noqa: E402


class WebApiTests(unittest.TestCase):
    """Verify startup-independent API behavior."""

    @staticmethod
    def request(path: str) -> Request:
        """Build a minimal HTTP request for direct template rendering."""
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": path,
                "headers": [],
                "query_string": b"",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "scheme": "http",
                "root_path": "",
                "app": webAPI.app,
            }
        )

    def test_build_version_is_exposed(self) -> None:
        self.assertEqual(webAPI.app.version, "test-version")
        self.assertEqual(webAPI.protocol_info()["app_version"], "test-version")

    def test_commands_report_not_ready_before_bacnet_startup(self) -> None:
        whois_response = asyncio.run(webAPI.whois_command())
        iam_response = asyncio.run(webAPI.iam_command())
        self.assertEqual(whois_response.status_code, 503)
        self.assertEqual(iam_response.status_code, 503)

    def test_all_gui_templates_render(self) -> None:
        pages = (
            (webAPI.webapp, "/webapp"),
            (webAPI.subscriptions, "/subscriptions"),
            (webAPI.subscription_targets, "/subscriptions/targets"),
            (webAPI.ede, "/ede"),
        )
        for endpoint, path in pages:
            with self.subTest(path=path):
                response = asyncio.run(endpoint(self.request(path)))
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.media_type)


if __name__ == "__main__":
    unittest.main()
