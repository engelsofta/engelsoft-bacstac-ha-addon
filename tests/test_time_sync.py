"""BACnet time sync capability, destination and read-back checks."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).parents[1] / "engelsoft_bacstac/rootfs/usr/bin"))
from bacpypes3.basetypes import DateTime
from bacpypes3.pdu import Address
from bacpypes3.apdu import TimeSynchronizationRequest, UTCTimeSynchronizationRequest
from time_sync import supported_mode, synchronize
from runtime_settings import normalize

class TimeSyncTests(unittest.IsolatedAsyncioTestCase):
    def test_daily_mode_selection(self):
        both = {"time_sync_local": True, "time_sync_utc": True}
        self.assertEqual(supported_mode([1]*50, both), "utc")
        services = [0]*50
        services[32] = 1
        self.assertEqual(supported_mode(services, both), "local")
        self.assertIsNone(supported_mode(services, {}))

    def test_defaults_off_and_strings_rejected(self):
        self.assertFalse(normalize({})["time_sync_local"])
        self.assertFalse(normalize({})["time_sync_utc"])
        with self.assertRaises(ValueError):
            normalize({"time_sync_utc": "false"})

    async def test_both_services_addressed_and_verified(self):
        for mode, request_type in (("utc", UTCTimeSynchronizationRequest), ("local", TimeSynchronizationRequest)):
            now = DateTime(datetime.now(timezone.utc))
            async def read(address, device, prop):
                return {"protocolServicesSupported": [1]*50, "utcOffset": 0,
                        "daylightSavingsStatus": False, "localDate": now.date, "localTime": now.time}[prop]
            app = SimpleNamespace(dev_to_addr=lambda dev: Address("192.168.1.20"),
                                  read_property=AsyncMock(side_effect=read), request=AsyncMock())
            with patch("time_sync.asyncio.sleep", new=AsyncMock()):
                result = await synchronize(app, "device:123", mode)
            self.assertEqual(result["status"], "matched")
            request = app.request.call_args.args[0]
            self.assertIsInstance(request, request_type)
            self.assertEqual(str(request.pduDestination), "192.168.1.20")

    async def test_unsupported_never_sends(self):
        app = SimpleNamespace(dev_to_addr=lambda dev: Address("192.168.1.20"),
                              read_property=AsyncMock(return_value=[0]*50), request=AsyncMock())
        with self.assertRaises(ValueError):
            await synchronize(app, "device:123", "utc")
        app.request.assert_not_called()

    async def test_wrong_time_and_failed_readback_are_not_success(self):
        old = DateTime(datetime(2020, 1, 1))
        for unreadable in (False, True):
            sent = False
            async def read(address, device, prop):
                if unreadable and sent and prop == "localDate":
                    raise TimeoutError()
                return {"protocolServicesSupported": [1]*50, "utcOffset": 0,
                        "daylightSavingsStatus": False, "localDate": old.date, "localTime": old.time}[prop]
            async def send(request):
                nonlocal sent
                sent = True
            app = SimpleNamespace(dev_to_addr=lambda dev: Address("192.168.1.20"),
                                  read_property=AsyncMock(side_effect=read), request=AsyncMock(side_effect=send))
            with patch("time_sync.asyncio.sleep", new=AsyncMock()):
                result = await synchronize(app, "device:123", "utc")
            self.assertEqual(result["status"], "unverified" if unreadable else "mismatch")
