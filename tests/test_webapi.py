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
from starlette.testclient import TestClient  # noqa: E402


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

    def test_ingress_requests_can_load_css_and_javascript(self) -> None:
        client = TestClient(webAPI.app, root_path="/api/hassio_ingress/test-token")
        html = client.get("/webapp")
        css = client.get("/static/css/styles.css")
        javascript = client.get("/static/js/theme.js")

        self.assertEqual(html.status_code, 200)
        self.assertEqual(css.status_code, 200)
        self.assertEqual(css.headers["content-type"], "text/css; charset=utf-8")
        self.assertEqual(javascript.status_code, 200)
        self.assertIn("javascript", javascript.headers["content-type"])
        self.assertIn("/api/hassio_ingress/test-token/static/css/styles.css?v=1.3.11", html.text)

    def test_static_route_rejects_path_traversal(self) -> None:
        response = asyncio.run(webAPI.static_asset("../../config.yaml"))
        self.assertEqual(response.status_code, 404)


class ProtectionSaveTests(unittest.IsolatedAsyncioTestCase):
    async def test_iam_switches_preserve_cov_subscriptions(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        old = [{**webAPI.DEFAULT_RULE}]
        app = SimpleNamespace(addon_device_config=[{**webAPI.DEFAULT_RULE, "reread_on_iam": True}],
                              reapply_managed_targets=AsyncMock())
        self.assertIsNone(await webAPI._apply_changed_protection(app, old))
        app.reapply_managed_targets.assert_not_awaited()

    async def test_changed_lifetime_reapplies_transport(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        app = SimpleNamespace(addon_device_config=[{**webAPI.DEFAULT_RULE, "CoV_lifetime": 1200}],
                              reapply_managed_targets=AsyncMock())
        self.assertIsNone(await webAPI._apply_changed_protection(app, [webAPI.DEFAULT_RULE]))
        app.reapply_managed_targets.assert_awaited_once()

    async def test_cleanup_timeout_returns_explicit_saved_settings_error(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        app = SimpleNamespace(addon_device_config=[{**webAPI.DEFAULT_RULE, "CoV_limit": 25}],
                              reapply_managed_targets=AsyncMock(side_effect=TimeoutError))
        response = await webAPI._apply_changed_protection(app, [webAPI.DEFAULT_RULE])
        self.assertEqual(response.status_code, 503)
        self.assertIn("Einstellungen gespeichert", response.body.decode())


if __name__ == "__main__":
    unittest.main()
