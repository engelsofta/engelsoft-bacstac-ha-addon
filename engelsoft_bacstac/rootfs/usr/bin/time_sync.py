"""Explicit, device-addressed BACnet time synchronization and fresh read-back."""

import asyncio
from datetime import datetime, timedelta, timezone

from bacpypes3.apdu import TimeSynchronizationRequest, UTCTimeSynchronizationRequest
from bacpypes3.basetypes import DateTime
from bacpypes3.primitivedata import ObjectIdentifier


def supported_mode(services, settings):
    """Prefer UTC, with local time as an explicitly enabled alternative."""
    for mode, name, bit in (("utc", "utc-time-synchronization", 36), ("local", "time-synchronization", 32)):
        if not settings.get(f"time_sync_{mode}"):
            continue
        try:
            value = services[name]
        except (KeyError, TypeError, IndexError):
            try:
                value = services[bit]
            except (KeyError, TypeError, IndexError):
                continue
        if value:
            return mode
    return None


async def synchronize(application, device_id: str, mode: str) -> dict:
    """Send once, never broadcast; matching clocks do not prove command receipt."""
    device = ObjectIdentifier(device_id)
    if str(device[0]) != "device":
        raise ValueError("Select a Device object")
    address = application.dev_to_addr(device)
    if address is None:
        raise ValueError("No live BACnet address for this device")

    async def read(prop):
        return await asyncio.wait_for(application.read_property(address, device, prop), 5)

    services = await read("protocolServicesSupported")
    service, bit = ("utc-time-synchronization", 36) if mode == "utc" else ("time-synchronization", 32)
    try:
        supported = services[service]
    except (KeyError, TypeError, IndexError):
        supported = services[bit]
    if not supported:
        raise ValueError("Device does not support the selected synchronization service")
    # Use the recipient's timezone, never the container's potentially UTC timezone.
    offset = int(await read("utcOffset"))
    daylight = bool(await read("daylightSavingsStatus"))
    local_delta = timedelta(minutes=-offset + (60 if daylight else 0))
    before = DateTime(date=await read("localDate"), time=await read("localTime")).datetime
    sent = datetime.now(timezone.utc).replace(tzinfo=None)
    before_difference = (before - (sent + local_delta)).total_seconds()
    target = sent if mode == "utc" else sent + local_delta
    request_type = UTCTimeSynchronizationRequest if mode == "utc" else TimeSynchronizationRequest
    await application.request(request_type(time=DateTime(target), destination=address))
    await asyncio.sleep(1)
    try:
        after = DateTime(date=await read("localDate"), time=await read("localTime")).datetime
        expected = datetime.now(timezone.utc).replace(tzinfo=None) + local_delta
        difference = abs((after - expected).total_seconds())
        return {"status": "matched" if difference <= 5 else "mismatch",
                "before": before.isoformat(), "after": after.isoformat(),
                "difference_seconds": round(difference, 2),
                "before_difference_seconds": round(before_difference, 2)}
    except Exception:
        return {"status": "unverified", "before": before.isoformat()}
