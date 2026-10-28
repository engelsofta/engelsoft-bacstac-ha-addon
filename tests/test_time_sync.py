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
from time_sync import local_time, supported_mode, synchronize
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
            now = DateTime(local_time(datetime.now(timezone.utc)))
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

    def test_berlin_dst_boundaries_and_date_rollover(self):
        for utc, expected in (
            (datetime(2026, 10, 28, 23, 25), datetime(2026, 10, 29, 0, 25)),
            (datetime(2027, 3, 28, 0, 59), datetime(2027, 3, 28, 1, 59)),
            (datetime(2027, 3, 28, 1), datetime(2027, 3, 28, 3)),
            (datetime(2027, 10, 31, 0, 59), datetime(2027, 10, 31, 2, 59)),
            (datetime(2027, 10, 31, 1), datetime(2027, 10, 31, 2)),
        ):
            self.assertEqual(local_time(utc.replace(tzinfo=timezone.utc)), expected)

    async def test_zero_device_offset_does_not_define_command_or_success(self):
        for month, hour in ((1, 13), (7, 14)):
            instant = datetime(2027, month, 15, 12, tzinfo=timezone.utc)
            for mode in ("local", "utc"):
                with self.subTest(month=month, mode=mode):
                    clock = DateTime(instant.replace(tzinfo=None))

                    async def read(address, device, prop):
                        return {"protocolServicesSupported": [1]*50, "utcOffset": 0,
                                "daylightSavingsStatus": False,
                                "localDate": clock.date, "localTime": clock.time}[prop]

                    async def send(request):
                        nonlocal clock
                        clock = request.time

                    app = SimpleNamespace(dev_to_addr=lambda dev: Address("192.168.1.20"),
                                          read_property=AsyncMock(side_effect=read),
                                          request=AsyncMock(side_effect=send))
                    with patch("time_sync.datetime") as dt, patch("time_sync.asyncio.sleep", new=AsyncMock()):
                        dt.now.return_value = instant
                        result = await synchronize(app, "device:1", mode)
                    self.assertEqual(result["status"], "matched" if mode == "local" else "mismatch")
                    self.assertEqual(clock.datetime.hour, hour if mode == "local" else 12)
                    self.assertEqual(result["difference_seconds"], 0 if mode == "local" else (hour - 12)*3600)

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
