"""BACnet handler classes for BACnet add-on.

Modified by engelsofta in 2026; derived from the Bepacom BACnet/IP add-on.
"""

import asyncio
import time
from ast import List
from logging import config
from math import e, isinf, isnan
from re import A
from typing import Any, Dict, TypeVar

from fastapi.encoders import jsonable_encoder
from bacpypes3.apdu import (AbortPDU, ConfirmedCOVNotificationRequest,
                            ErrorPDU, ErrorRejectAbortNack,
                            ReadPropertyMultipleRequest, ReadPropertyRequest,
                            RejectPDU, SimpleAckPDU, SubscribeCOVRequest,
                            UnconfirmedCOVNotificationRequest)
from bacpypes3.basetypes import (BinaryPV, DeviceStatus, EngineeringUnits,
                                 ErrorClass, ErrorCode, ErrorType, EventState,
                                 PropertyIdentifier, ReadAccessResult,
                                 Reliability, ServicesSupported)
from bacpypes3.constructeddata import AnyAtomic
from bacpypes3.debugging import bacpypes_debugging
from bacpypes3.errors import *
from bacpypes3.ipv4.app import ForeignApplication, NormalApplication
from bacpypes3.json.util import octetstring_encode
from bacpypes3.object import get_vendor_info
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import ObjectIdentifier, ObjectType, OctetString
from bacpypes3.service.cov import SubscriptionContextManager
from const import (LOGGER, device_properties_to_read,
                   object_properties_to_read_once,
                   object_properties_to_read_periodically,
                   subscribable_objects)
from inventory_cache import InventoryCache

KeyType = TypeVar("KeyType")
_debug = 0
_DISCOVERY_READ_CONCURRENCY = 3


def custom_init(
    self,
    app: "Application",  # noqa: F821
    address: Address,
    monitored_object_identifier: ObjectIdentifier,
    subscriber_process_identifier: int,
    issue_confirmed_notifications: bool,
    lifetime: int,
):
    original_init(
        self,
        app,
        address,
        monitored_object_identifier,
        subscriber_process_identifier,
        issue_confirmed_notifications,
        lifetime,
    )

    # result of refresh task to check if exception occurred
    self.refresh_subscription_task = None


original_init = SubscriptionContextManager.__init__

SubscriptionContextManager.__init__ = custom_init


class BACnetIOHandler(NormalApplication, ForeignApplication):
    bacnet_device_dict: dict = {}
    subscription_tasks: list = []
    update_event: asyncio.Event = asyncio.Event()
    startup_complete: asyncio.Event = asyncio.Event()
    default_subscription_lifetime = 60
    subscription_list = []
    i_am_queue: asyncio.Queue = asyncio.Queue()
    poll_tasks: list[asyncio.Task] = []
    addon_device_config: list = []

    def __init__(
        self,
        device,
        local_ip,
        foreign_ip="",
        ttl=255,
        update_event=asyncio.Event(),
        addon_device_config=[],
        subscription_mode="managed_polling",
        managed_poll_rate=10,
        managed_cov_subscription_delay=1,
        managed_cov_fallback_timeout=30,
    ) -> None:
        if foreign_ip:
            ForeignApplication.__init__(self, device, local_ip)
            self.register(addr=Address(foreign_ip), ttl=int(ttl))
        else:
            NormalApplication.__init__(self, device, local_ip)
        super().i_am()
        super().who_is()
        self.update_event = update_event
        self.subscription_diagnostics = {
            "started_at_epoch": time.time(),
            "tasks_created": 0,
            "subscriptions_established": 0,
            "cov_values_received": 0,
            "subscription_failures": 0,
            "subscription_cancellations": 0,
            "duplicate_task_creation_attempts": 0,
            "managed_target_updates": 0,
            "cov_limit_fallbacks": 0,
            "cov_silence_fallbacks": 0,
        }
        self.vendor_info = get_vendor_info(0)
        asyncio.get_event_loop().create_task(self.IAm_handler())
        self.addon_device_config = (
            addon_device_config if addon_device_config else list()
        )
        self.subscription_mode = subscription_mode
        self.managed_poll_rate = max(3, int(managed_poll_rate))
        self.managed_cov_subscription_delay = max(
            0, int(managed_cov_subscription_delay)
        )
        self.managed_cov_fallback_timeout = max(
            10, int(managed_cov_fallback_timeout)
        )
        self.managed_poll_tasks: dict[str, asyncio.Task] = {}
        self.managed_poll_targets: set[tuple[str, str]] = set()
        self.managed_cov_task_names: set[str] = set()
        self.managed_cov_reconcile_task: asyncio.Task | None = None
        self.managed_targets: set[tuple[str, str]] = set()
        self.managed_disabled_targets: set[tuple[str, str]] = set()
        self.managed_requested_modes: dict[tuple[str, str], str] = {}
        self.pending_managed_updates: set[tuple[str, str]] = set()
        self.target_status: dict[tuple[str, str], dict[str, Any]] = {}
        self.cov_fallback_tasks: dict[tuple[str, str], asyncio.Task] = {}
        self.cov_watchdog_tasks: dict[tuple[str, str], asyncio.Task] = {}
        # The BACnet station benefits from bounded parallel discovery reads,
        # but can become unreliable when it receives a large burst. Keep this
        # deliberately conservative; runtime COV and managed polling do not use
        # this semaphore.
        self.discovery_read_semaphore = asyncio.Semaphore(
            _DISCOVERY_READ_CONCURRENCY
        )
        self.inventory_cache = InventoryCache()
        self.inventory_cache_diagnostics = {
            "restored_devices": 0,
            "restored_objects": 0,
            "ignored_entries": 0,
            "last_saved_device": None,
            "last_saved_objects": 0,
            "save_deferred": False,
            "save_attempted": False,
            "candidate_objects": 0,
            "candidate_missing": 0,
            "candidate_missing_examples": [],
            "last_error": None,
        }
        self._active_discovery_devices: set[str] = set()
        self._fresh_discovery_properties: dict[
            str, dict[str, set[str]]
        ] = {}
        self._restore_inventory_cache()
        LOGGER.info(
            "BACnet discovery read concurrency: %s",
            _DISCOVERY_READ_CONCURRENCY,
        )
        self.startup_complete.set()
        LOGGER.debug("Application initialised")

    def _restore_inventory_cache(self) -> None:
        """Restore only validated snapshots while preserving the shared dict."""
        restored, diagnostics = self.inventory_cache.load_all()
        if restored:
            self.bacnet_device_dict.clear()
            self.bacnet_device_dict.update(restored)
            LOGGER.info(
                "Restored BACnet inventory cache: devices=%s objects=%s",
                diagnostics["devices"],
                diagnostics["objects"],
            )
        else:
            LOGGER.info("No valid BACnet inventory cache available")

        self.inventory_cache_diagnostics.update(
            {
                "restored_devices": diagnostics["devices"],
                "restored_objects": diagnostics["objects"],
                "ignored_entries": diagnostics["ignored"],
            }
        )

    def _begin_fresh_discovery(self, device_identifier: ObjectIdentifier) -> str:
        device_key = self.identifier_to_string(device_identifier)
        self._active_discovery_devices.add(device_key)
        self._fresh_discovery_properties[device_key] = {}
        return device_key

    def _end_fresh_discovery(self, device_key: str) -> None:
        self._active_discovery_devices.discard(device_key)

    def _complete_device_inventory_snapshot(
        self, device_identifier: ObjectIdentifier
    ) -> tuple[dict[str, Any] | None, int, list[str]]:
        """Build a cache candidate only when every listed object was freshly read."""
        device_key = self.identifier_to_string(device_identifier)
        device_payload = self.bacnet_device_dict.get(device_key)
        if not isinstance(device_payload, dict):
            return None, 0, [device_key]

        device_object = device_payload.get(device_key)
        if not isinstance(device_object, dict):
            return None, 0, [device_key]

        raw_object_list = device_object.get("objectList")
        if not isinstance(raw_object_list, list) or not raw_object_list:
            return None, 0, ["objectList"]

        expected_keys: list[str] = []
        for raw_identifier in raw_object_list:
            try:
                object_identifier = ObjectIdentifier(raw_identifier)
            except Exception:
                continue
            if ObjectType(object_identifier[0]) == ObjectType("device"):
                continue
            if ObjectType(object_identifier[0]) not in self.vendor_info.registered_object_classes:
                continue
            expected_keys.append(self.identifier_to_string(object_identifier))

        fresh = self._fresh_discovery_properties.get(device_key, {})
        missing = [
            object_key
            for object_key in expected_keys
            if "objectIdentifier" not in fresh.get(object_key, set())
            or object_key not in device_payload
        ]
        if missing:
            return None, len(expected_keys), missing

        filtered_device = {device_key: device_object}
        filtered_device.update(
            {
                object_key: device_payload[object_key]
                for object_key in expected_keys
                if object_key in device_payload
            }
        )
        safe_payload = jsonable_encoder({device_key: filtered_device})
        return safe_payload, len(expected_keys), []

    async def _save_inventory_cache_if_complete(
        self, device_identifier: ObjectIdentifier
    ) -> None:
        device_key = self.identifier_to_string(device_identifier)
        payload, object_count, missing = self._complete_device_inventory_snapshot(
            device_identifier
        )
        self.inventory_cache_diagnostics.update(
            {
                "save_attempted": True,
                "candidate_objects": object_count,
                "candidate_missing": len(missing),
                "candidate_missing_examples": missing[:5],
                "last_error": None,
            }
        )
        if payload is None:
            self.inventory_cache_diagnostics["last_error"] = "fresh_inventory_incomplete"
            LOGGER.warning(
                "BACnet inventory cache not replaced for %s: fresh inventory incomplete (%s/%s missing; examples=%s)",
                device_key,
                len(missing),
                object_count,
                missing[:5],
            )
            return

        try:
            result = await asyncio.to_thread(
                self.inventory_cache.store_device,
                device_key,
                payload,
                object_count,
            )
        except Exception as err:
            self.inventory_cache_diagnostics["last_error"] = str(err)
            LOGGER.warning("Failed to store BACnet inventory cache for %s: %s", device_key, err)
            return

        self.inventory_cache_diagnostics.update(
            {
                "last_saved_device": device_key if result["saved"] else None,
                "last_saved_objects": object_count if result["saved"] else 0,
                "save_deferred": bool(result["deferred"]),
            }
        )
        if result["saved"]:
            LOGGER.info(
                "Stored complete BACnet inventory cache: device=%s objects=%s",
                device_key,
                object_count,
            )
        else:
            LOGGER.warning(
                "Smaller BACnet inventory cache candidate deferred: device=%s objects=%s confirmation=%s/3",
                device_key,
                object_count,
                result["confirmations"],
            )

    def get_config_from_addon_config(self, device_identifier: ObjectIdentifier) -> dict:
        specific_config = next(
            (
                config
                for config in self.addon_device_config
                if config.get("deviceID")
                == f"{device_identifier[0]}:{device_identifier[1]}"
            ),
            None,
        )
        if specific_config:
            return specific_config

        all_config = next(
            (
                config
                for config in self.addon_device_config
                if config.get("deviceID") == f"all"
            ),
            None,
        )
        if all_config:
            return all_config

        return dict()

    def _target_key(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
    ) -> tuple[str, str]:
        return (
            self.identifier_to_string(ObjectIdentifier(device_identifier)),
            self.identifier_to_string(ObjectIdentifier(object_identifier)),
        )

    def _cov_limit_for_device(self, device_identifier: ObjectIdentifier) -> int:
        config = self.get_config_from_addon_config(ObjectIdentifier(device_identifier))
        try:
            return max(0, int(config.get("CoV_limit", 20)))
        except (TypeError, ValueError):
            return 20

    def _ensure_target_status(
        self,
        target: tuple[str, str],
        requested_mode: str | None = None,
    ) -> dict[str, Any]:
        status = self.target_status.setdefault(
            target,
            {
                "device_id": target[0],
                "object_id": target[1],
                "requested_mode": requested_mode or self.subscription_mode,
                "state": "waiting",
                "subscription_confirmed_at": None,
                "last_cov_at": None,
                "last_poll_at": None,
                "last_value_at": None,
                "fallback_active": False,
                "fallback_reason": None,
                "last_error": None,
            },
        )
        if requested_mode:
            status["requested_mode"] = requested_mode
        return status

    def target_status_snapshot(self) -> list[dict[str, Any]]:
        """Return serializable per-target transport and freshness diagnostics."""
        now = time.time()
        snapshot = []
        for target in sorted(self.target_status):
            status = dict(self.target_status[target])
            status["subscription_confirmed"] = bool(
                status.get("subscription_confirmed_at")
            )
            for field in (
                "subscription_confirmed_at",
                "last_cov_at",
                "last_poll_at",
                "last_value_at",
            ):
                timestamp = status.get(field)
                status[f"{field.removesuffix('_at')}_age_seconds"] = (
                    round(now - timestamp, 1) if timestamp else None
                )
            snapshot.append(status)
        return snapshot

    def _mark_target_update(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
        source: str,
    ) -> None:
        target = self._target_key(device_identifier, object_identifier)
        status = self._ensure_target_status(target)
        now = time.time()
        status["last_value_at"] = now
        status["last_error"] = None
        if source == "cov":
            status["last_cov_at"] = now
            status["state"] = "cov_active"
            self._cancel_cov_fallback(target)
        elif source == "poll":
            status["last_poll_at"] = now
            status["state"] = (
                "polling_fallback" if status.get("fallback_active") else "polling"
            )

    def _cancel_cov_fallback(self, target: tuple[str, str]) -> None:
        task = self.cov_fallback_tasks.pop(target, None)
        if task is not None and not task.done():
            task.cancel()
        self.managed_poll_targets.discard(target)
        status = self.target_status.get(target)
        if status:
            status["fallback_active"] = False
            status["fallback_reason"] = None

    async def _ensure_cov_polling_fallback(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
        reason: str,
    ) -> None:
        target = self._target_key(device_identifier, object_identifier)
        existing = self.cov_fallback_tasks.get(target)
        if existing is not None and not existing.done():
            return

        status = self._ensure_target_status(target, self.subscription_mode)
        status["fallback_active"] = True
        status["fallback_reason"] = reason
        status["state"] = "polling_fallback"
        self.managed_poll_targets.add(target)
        if reason == "cov_limit":
            self.subscription_diagnostics["cov_limit_fallbacks"] += 1
        elif reason == "cov_silent":
            self.subscription_diagnostics["cov_silence_fallbacks"] += 1

        # A silent confirmed subscription still consumes capacity on the remote
        # device. Cancel it before polling so fragile controllers regain the slot.
        if reason == "cov_silent":
            task_name_prefix = f"{target[0]},{target[1]},"
            for subscription_task in list(self.subscription_tasks):
                if (
                    subscription_task.get_name().startswith(task_name_prefix)
                    and subscription_task is not asyncio.current_task()
                    and not subscription_task.done()
                ):
                    subscription_task.cancel()
            self.managed_cov_task_names.discard(
                f"{target[0]},{target[1]},confirmed"
            )

        task = asyncio.create_task(
            self.poll_task(
                device_identifier=ObjectIdentifier(device_identifier),
                object_list=[ObjectIdentifier(object_identifier)],
                poll_rate=(
                    self.managed_poll_rate
                    if self.subscription_mode
                    in {"integration_controlled", "managed_polling", "managed_cov"}
                    else max(
                        30,
                        int(
                            self.get_config_from_addon_config(device_identifier).get(
                                "slow_poll_rate", 600
                            )
                        ),
                    )
                ),
                property_list=[PropertyIdentifier("presentValue")],
            ),
            name=f"cov-fallback-{target[0]}-{target[1]}",
        )
        self.cov_fallback_tasks[target] = task
        LOGGER.warning(
            "Polling fallback active for %s %s (%s)",
            target[0],
            target[1],
            reason,
        )

    async def _cov_value_watchdog(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
    ) -> None:
        target = self._target_key(device_identifier, object_identifier)
        try:
            await asyncio.sleep(self.managed_cov_fallback_timeout)
            if self.managed_cov_subscription_delay:
                await asyncio.sleep(
                    (ObjectIdentifier(object_identifier)[1] % 20)
                    * self.managed_cov_subscription_delay
                )
            status = self.target_status.get(target)
            if status and status.get("last_cov_at") is None:
                await self._ensure_cov_polling_fallback(
                    device_identifier,
                    object_identifier,
                    "cov_silent",
                )
        except asyncio.CancelledError:
            return

    def _cancel_target_runtime(self, target: tuple[str, str]) -> None:
        self._cancel_cov_fallback(target)
        watchdog = self.cov_watchdog_tasks.pop(target, None)
        if watchdog is not None and not watchdog.done():
            watchdog.cancel()
        self.managed_poll_targets.discard(target)

    async def generate_specific_tasks(
        self, device_identifier: ObjectIdentifier
    ) -> None:
        """Handle generating tasks for specific identifiers after reading object."""

        specific_config = [
            config
            for config in self.addon_device_config
            if config.get("deviceID")
            == f"{device_identifier[0]}:{device_identifier[1]}"
        ]

        if not specific_config:
            # assume generic handling
            await self.generate_generic_tasks(device_identifier=device_identifier)
            return

        if len(specific_config) > 1:
            # duplicate
            return

        index = self.addon_device_config.index(specific_config[0])

        config = self.addon_device_config[index]

        if self.subscription_mode not in {"integration_controlled", "managed_polling", "managed_cov"} and config.get("quick_poll_list", []):
            await self.create_poll_task(
                device_identifier=device_identifier,
                object_list=config.get("quick_poll_list"),
                poll_rate=config.get("quick_poll_rate", 30),
            )

        if self.subscription_mode in {"integration_controlled", "managed_polling", "managed_cov"}:
            object_list = []
        elif "all" in config.get("slow_poll_list", []):
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList")

            if device_identifier in object_list:
                object_list.remove(device_identifier)

        elif config.get("slow_poll_list", []):
            object_list = config.get("slow_poll_list", [])
        else:
            object_list = []

        if object_list:
            await self.create_poll_task(
                device_identifier=device_identifier,
                object_list=object_list,
                poll_rate=config.get("slow_poll_rate", 600),
            )

        if self.subscription_mode in {"integration_controlled", "managed_polling", "managed_cov"}:
            LOGGER.info("Managed subscription mode active; skipping configured subscriptions")
        elif "all" in config.get("CoV_list", []):
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList")

            if device_identifier in object_list:
                object_list.remove(device_identifier)

            object_list = [
                object_identifier
                for object_identifier in object_list
                if object_identifier[0] in subscribable_objects
            ]

            for object_identifier in object_list:
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get(
                        "CoV_lifetime", self.default_subscription_lifetime
                    ),
                )
                await asyncio.sleep(0)

        elif config.get("CoV_list", []):
            for object_identifier in config.get("CoV_list"):
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get("CoV_lifetime"),
                )
                await asyncio.sleep(0)

        return

    async def generate_generic_tasks(self, device_identifier: ObjectIdentifier) -> None:
        specific_config = [
            config
            for config in self.addon_device_config
            if config.get("deviceID") == "all"
        ]

        if not specific_config:
            LOGGER.warning(
                "No device rule for %s; automatic subscribe-all is disabled for safety",
                device_identifier,
            )
            return

        index = self.addon_device_config.index(specific_config[0])

        config = self.addon_device_config[index]

        if self.subscription_mode not in {"integration_controlled", "managed_polling", "managed_cov"} and config.get("quick_poll_list", []):
            await self.create_poll_task(
                device_identifier=device_identifier,
                object_list=config.get("quick_poll_list"),
                poll_rate=config.get("quick_poll_rate", 30),
            )

        if self.subscription_mode in {"integration_controlled", "managed_polling", "managed_cov"}:
            object_list = []
        elif "all" in config.get("slow_poll_list", []):
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList")

            if device_identifier in object_list:
                object_list.remove(device_identifier)

        elif config.get("slow_poll_list", []):
            object_list = config.get("slow_poll_list")
        else:
            object_list = []

        if object_list:
            await self.create_poll_task(
                device_identifier=device_identifier,
                object_list=object_list,
                poll_rate=config.get(
                    "slow_poll_rate", self.default_subscription_lifetime
                ),
            )

        if self.subscription_mode in {"integration_controlled", "managed_polling", "managed_cov"}:
            LOGGER.info("Managed subscription mode active; skipping configured subscriptions")
        elif "all" in config.get("CoV_list", []):
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList")
            if device_identifier in object_list:
                object_list.remove(device_identifier)

            object_list = [
                object_identifier
                for object_identifier in object_list
                if object_identifier[0] in subscribable_objects
            ]

            for object_identifier in object_list:
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get("CoV_lifetime", 600),
                )
                await asyncio.sleep(0)

        elif config.get("CoV_list", []):
            for object_identifier in config.get("CoV_list"):
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get("CoV_lifetime", 600),
                )
                await asyncio.sleep(0)

        return

    async def poll_task(
        self,
        device_identifier: ObjectIdentifier,
        object_list: list[ObjectIdentifier],
        poll_rate: int = 30,
        property_list: list[PropertyIdentifier] | None = None,
    ) -> None:
        LOGGER.debug(f"TASK: {device_identifier} {object_list} {device_identifier}")
        properties = property_list or object_properties_to_read_periodically

        try:
            services_supported = self.bacnet_device_dict[
                f"device:{device_identifier[1]}"
            ][f"device:{device_identifier[1]}"].get(
                "protocolServicesSupported", ServicesSupported()
            )

            while True:
                for object_identifier in object_list:
                    object_class = self.vendor_info.get_object_class(
                        object_identifier[0]
                    )

                    if object_class is None:
                        LOGGER.warning(
                            f"Object type is unknown: {device_identifier}, {object_identifier}"
                        )
                        continue

                    if services_supported["read-property-multiple"] == 1:
                        try:
                            response = await self.read_property_multiple(
                                address=self.dev_to_addr(device_identifier),
                                parameter_list=[
                                    object_identifier,
                                    properties,
                                ],
                            )
                        except ErrorRejectAbortNack as err:
                            LOGGER.error(
                                f"Read multiple error: {device_identifier} {object_identifier}: {err}"
                            )
                            continue
                        else:
                            for (
                                object_identifier,
                                property_identifier,
                                property_array_index,
                                property_value,
                            ) in response:
                                if property_value is not ErrorType:
                                    self.dict_updater(
                                        device_identifier=device_identifier,
                                        object_identifier=object_identifier,
                                        property_identifier=property_identifier,
                                        property_value=property_value,
                                        update_source="poll",
                                    )
                    else:
                        for property_id in properties:
                            property_class = object_class.get_property_type(property_id)

                            if property_class is None:
                                continue

                            try:
                                response = await self.read_property(
                                    address=self.dev_to_addr(device_identifier),
                                    objid=object_identifier,
                                    prop=property_id,
                                )
                            except ErrorRejectAbortNack as err:
                                LOGGER.error(
                                    f"Read error: {device_identifier} {object_identifier} {property_id}: {err}"
                                )
                                continue
                            else:
                                if response is not ErrorType:
                                    self.dict_updater(
                                        device_identifier=device_identifier,
                                        object_identifier=object_identifier,
                                        property_identifier=property_id,
                                        property_value=response,
                                        update_source="poll",
                                    )

                await asyncio.sleep(poll_rate)

        except asyncio.CancelledError as err:
            LOGGER.info(f"Poll task for {device_identifier} cancelled")

        except Exception as err:
            LOGGER.error(err)

    async def replace_managed_targets(self, targets: list[tuple]) -> dict:
        """Apply integration targets while retaining BACnet safety guardrails."""
        managed_modes = {
            "integration_controlled",
            "managed_polling",
            "managed_cov",
        }
        if self.subscription_mode not in managed_modes:
            return {"accepted": False, "mode": self.subscription_mode, "targets": 0}

        requested_modes: dict[tuple[str, str], str] = {}
        identifiers: dict[
            tuple[str, str], tuple[ObjectIdentifier, ObjectIdentifier]
        ] = {}
        for entry in targets:
            device_identifier = ObjectIdentifier(entry[0])
            object_identifier = ObjectIdentifier(entry[1])
            requested_mode = str(entry[2]).lower() if len(entry) > 2 else "polling"
            if self.subscription_mode == "managed_polling":
                requested_mode = "polling"
            elif self.subscription_mode == "managed_cov":
                requested_mode = "cov"
            if requested_mode not in {"cov", "polling", "disabled"}:
                requested_mode = "polling"
            target = self._target_key(device_identifier, object_identifier)
            requested_modes[target] = requested_mode
            identifiers[target] = (device_identifier, object_identifier)

        all_requested = set(requested_modes)
        disabled_targets = {
            target for target, mode in requested_modes.items() if mode == "disabled"
        }
        active_targets = all_requested - disabled_targets
        removed_targets = set(self.target_status) - all_requested
        for target in removed_targets:
            self._cancel_target_runtime(target)
            self.target_status.pop(target, None)

        for target, requested_mode in requested_modes.items():
            status = self._ensure_target_status(target, requested_mode)
            if requested_mode == "disabled":
                self._cancel_target_runtime(target)
                status["state"] = "disabled"

        cov_requested: dict[ObjectIdentifier, list[ObjectIdentifier]] = {}
        poll_requested: dict[ObjectIdentifier, list[ObjectIdentifier]] = {}
        for target in active_targets:
            device_identifier, object_identifier = identifiers[target]
            if requested_modes[target] == "cov":
                cov_requested.setdefault(device_identifier, []).append(
                    object_identifier
                )
            else:
                poll_requested.setdefault(device_identifier, []).append(
                    object_identifier
                )

        cov_grouped: dict[ObjectIdentifier, list[ObjectIdentifier]] = {}
        overflow_targets: list[tuple[ObjectIdentifier, ObjectIdentifier]] = []
        for device_identifier, object_list in cov_requested.items():
            cov_limit = self._cov_limit_for_device(device_identifier)
            cov_candidates: list[ObjectIdentifier] = []
            retained_fallbacks: list[ObjectIdentifier] = []
            for object_identifier in dict.fromkeys(object_list):
                target = self._target_key(device_identifier, object_identifier)
                status = self.target_status.get(target, {})
                if status.get("fallback_active") and status.get(
                    "fallback_reason"
                ) in {"cov_silent", "cov_failed"}:
                    retained_fallbacks.append(object_identifier)
                else:
                    cov_candidates.append(object_identifier)
            cov_grouped[device_identifier] = cov_candidates[:cov_limit]
            overflow_targets.extend(
                (device_identifier, object_identifier)
                for object_identifier in retained_fallbacks
                + cov_candidates[cov_limit:]
            )

        desired_names = {
            f"{self.identifier_to_string(device_identifier)},{self.identifier_to_string(object_identifier)},confirmed"
            for device_identifier, object_list in cov_grouped.items()
            for object_identifier in object_list
        }
        explicit_poll_targets = {
            self._target_key(device_identifier, object_identifier)
            for device_identifier, object_list in poll_requested.items()
            for object_identifier in object_list
        }
        overflow_keys = {
            self._target_key(device_identifier, object_identifier)
            for device_identifier, object_identifier in overflow_targets
        }
        active_names = {
            task.get_name()
            for task in self.subscription_tasks
            if not task.done() and not task.cancelling()
        }
        active_fallbacks = {
            target
            for target, task in self.cov_fallback_tasks.items()
            if not task.done()
        }
        polling_tasks_ready = all(
            task is not None and not task.done()
            for task in self.managed_poll_tasks.values()
        ) and (not poll_requested or bool(self.managed_poll_tasks))
        if (
            requested_modes == self.managed_requested_modes
            and desired_names <= active_names
            and overflow_keys <= active_fallbacks
            and polling_tasks_ready
        ):
            return self._managed_target_response(unchanged=True)

        previous_names = self.managed_cov_task_names
        self.managed_targets = active_targets
        self.managed_disabled_targets = disabled_targets
        self.managed_requested_modes = requested_modes
        self.pending_managed_updates.clear()
        self.subscription_diagnostics["managed_target_updates"] += 1
        self.managed_cov_task_names = desired_names

        old_poll_tasks = self.managed_poll_tasks
        self.managed_poll_tasks = {}
        for device_identifier, object_list in poll_requested.items():
            task_key = self.identifier_to_string(device_identifier)
            self.managed_poll_tasks[task_key] = asyncio.create_task(
                self.poll_task(
                    device_identifier=device_identifier,
                    object_list=list(dict.fromkeys(object_list)),
                    poll_rate=self.managed_poll_rate,
                    property_list=[PropertyIdentifier("presentValue")],
                ),
                name=f"managed-poll-{task_key}",
            )
        for task in old_poll_tasks.values():
            task.cancel()
        for target in explicit_poll_targets:
            self._cancel_cov_fallback(target)
            status = self._ensure_target_status(target, "polling")
            status["state"] = "polling"
        self.managed_poll_targets = explicit_poll_targets | overflow_keys

        if (
            self.managed_cov_reconcile_task is not None
            and not self.managed_cov_reconcile_task.done()
        ):
            self.managed_cov_reconcile_task.cancel()
        self.managed_cov_reconcile_task = asyncio.create_task(
            self._reconcile_managed_cov_targets(
                cov_grouped,
                desired_names,
                previous_names,
                overflow_targets,
            ),
            name="managed-cov-reconcile",
        )
        return self._managed_target_response(reconcile_scheduled=True)

    def _managed_target_response(self, **extra) -> dict:
        """Return a stable summary for integrations and the WebUI."""
        return {
            "accepted": True,
            "mode": self.subscription_mode,
            "strategy": (
                "integration" if self.subscription_mode == "integration_controlled"
                else "cov" if self.subscription_mode == "managed_cov"
                else "polling"
            ),
            "targets": len(self.managed_targets),
            "cov_targets": len(self.managed_cov_task_names),
            "polling_targets": len(self.managed_poll_targets),
            "disabled_targets": len(self.managed_disabled_targets),
            "poll_rate": self.managed_poll_rate,
            **extra,
        }

    def consume_managed_delta(self) -> dict:
        """Return and clear changed managed objects as a nested payload."""
        changed = self.pending_managed_updates
        self.pending_managed_updates = set()
        payload: dict = {}
        for device_id, object_id in changed:
            object_payload = self.bacnet_device_dict.get(device_id, {}).get(object_id)
            if object_payload is None:
                continue
            payload.setdefault(device_id, {})[object_id] = object_payload
        return payload

    async def _reconcile_managed_cov_targets(
        self,
        grouped: dict[ObjectIdentifier, list[ObjectIdentifier]],
        desired_names: set[str],
        previous_names: set[str],
        overflow_targets: list[tuple[ObjectIdentifier, ObjectIdentifier]],
    ) -> None:
        """Reconcile managed COV tasks without blocking the HTTP request."""
        try:
            for task in list(self.subscription_tasks):
                if (
                    task.get_name() in previous_names
                    and task.get_name() not in desired_names
                ):
                    task.cancel()

            desired_targets = {
                self._target_key(device_identifier, object_identifier)
                for device_identifier, object_list in grouped.items()
                for object_identifier in object_list
            }
            for target in desired_targets:
                self._cancel_cov_fallback(target)

            for device_identifier, object_identifier in overflow_targets:
                await self._ensure_cov_polling_fallback(
                    device_identifier,
                    object_identifier,
                    "cov_limit",
                )

            for device_identifier, object_list in grouped.items():
                config = self.get_config_from_addon_config(device_identifier)
                for object_identifier in dict.fromkeys(object_list):
                    await self.create_subscription_task(
                        device_identifier=device_identifier,
                        object_identifier=object_identifier,
                        confirmed_notifications=True,
                        lifetime=config.get(
                            "CoV_lifetime", self.default_subscription_lifetime
                        ),
                    )
        except asyncio.CancelledError:
            LOGGER.info("Managed COV reconciliation replaced by a newer target list")
        except Exception as err:
            self.subscription_diagnostics["subscription_failures"] += 1
            LOGGER.error(f"Managed COV reconciliation failed: {err}")

    async def create_poll_task(
        self,
        device_identifier: ObjectIdentifier,
        object_list: list[ObjectIdentifier],
        poll_rate: int = 30,
    ) -> None:
        """Create a task that'll poll every so many seconds."""
        try:
            LOGGER.debug(
                f"Creating poll task: {device_identifier} {object_list} {poll_rate}"
            )

            device_identifier = ObjectIdentifier(device_identifier)

            if not self.bacnet_device_dict.get(f"device:{device_identifier[1]}"):
                await asyncio.sleep(15)

            if not self.bacnet_device_dict.get(f"device:{device_identifier[1]}"):
                self.who_is(device_identifier[1], device_identifier[1])
                await asyncio.sleep(45)

            if not self.bacnet_device_dict.get(f"device:{device_identifier[1]}"):
                LOGGER.warning(
                    f"{device_identifier} did not respond the requests. No polling possible."
                )
                return

            objects_to_poll: list = []

            for object_identifier in object_list:
                object_identifier = ObjectIdentifier(object_identifier)

                if not self.bacnet_device_dict[f"device:{device_identifier[1]}"].get(
                    f"{object_identifier[0]}:{object_identifier[1]}"
                ):
                    try:
                        response = await self.read_property(
                            address=self.dev_to_addr(device_identifier),
                            objid=object_identifier,
                            prop=PropertyIdentifier("presentValue"),
                        )
                    except ErrorRejectAbortNack as err:
                        LOGGER.warning(
                            f"{device_identifier} {object_identifier} failed to read: {err}"
                        )
                        LOGGER.info(
                            f"{device_identifier} {object_identifier} won't get polled."
                        )
                        continue

                objects_to_poll.append(object_identifier)

            if not objects_to_poll:
                LOGGER.warning(f"No objects to poll for {device_identifier}.")
                return

            task = asyncio.create_task(
                self.poll_task(device_identifier, objects_to_poll, poll_rate),
                name=f"{device_identifier[0]}:{device_identifier[1]}",
            )

            self.poll_tasks.append(task)

        except Exception as err:
            LOGGER.error(
                f"Failed to create polling task {device_identifier}, {object_identifier}"
            )

    def deep_update(
        self, mapping: Dict[KeyType, Any], *updating_mappings: Dict[KeyType, Any]
    ) -> Dict[KeyType, Any]:
        for updating_mapping in updating_mappings:
            for k, v in updating_mapping.items():
                if (
                    k in mapping
                    and isinstance(mapping[k], dict)
                    and isinstance(v, dict)
                ):
                    mapping[k] = self.deep_update(mapping[k], v)
                else:
                    mapping[k] = v
        self.update_event.set()
        # LOGGER.debug(f"Updating {updating_mapping}")
        return mapping

    def dev_to_addr(self, dev: ObjectIdentifier) -> Address | None:

        for address, device_info in self.device_info_cache.address_cache.items():
            if device_info.device_instance == dev[1]:
                return address

        return None

    def addr_to_dev(self, addr: Address) -> ObjectIdentifier | None:
        for address in self.device_info_cache.address_cache:
            if addr == address:
                return ObjectIdentifier(
                    f"device:{self.device_info_cache.address_cache[address].device_instance}"
                )
        return None

    async def do_WhoIsRequest(self, apdu) -> None:
        """Handle incoming Who Is request."""
        LOGGER.info(f"Received Who Is Request from {apdu.pduSource}")
        await super().do_WhoIsRequest(apdu)

    async def do_IAmRequest(self, apdu) -> None:
        """Handle incoming I Am request."""

        LOGGER.info(f"I Am from {apdu.iAmDeviceIdentifier}")

        device_id = apdu.iAmDeviceIdentifier[1]

        if device_id in self.device_info_cache.instance_cache:
            LOGGER.debug(f"Device {apdu.iAmDeviceIdentifier} already in cache!")
            await self.device_info_cache.set_device_info(apdu)
            in_cache = True
        else:
            await self.device_info_cache.set_device_info(apdu)
            in_cache = False

        await super().do_IAmRequest(apdu)

        if not in_cache:
            await self.i_am_queue.put(apdu)
            return

        config = self.get_config_from_addon_config(apdu.iAmDeviceIdentifier)

        if config.get("reread_on_iam", True):
            # Check if object list is still the same, otherwise read entire dict again
            await self.handle_object_list_check(apdu)

        if config.get("resub_on_iam", True):
            # Check if CoV tasks are still active, otherwise resub.
            await self.handle_cov_check(apdu.iAmDeviceIdentifier)

    async def handle_object_list_check(self, apdu) -> None:

        device_id = apdu.iAmDeviceIdentifier[1]

        old_object_list = self.bacnet_device_dict[
            f"device:{apdu.iAmDeviceIdentifier[1]}"
        ][f"device:{apdu.iAmDeviceIdentifier[1]}"].get("objectList")

        if not await self.read_multiple_device_props(apdu=apdu):
            LOGGER.warning(f"Failed to get: {device_id}, {device_id}")
            if self.bacnet_device_dict.get(f"device:{device_id}"):
                self.bacnet_device_dict.pop(f"device:{device_id}")

        new_object_list = self.bacnet_device_dict[
            f"device:{apdu.iAmDeviceIdentifier[1]}"
        ][f"device:{apdu.iAmDeviceIdentifier[1]}"].get("objectList")

        if apdu.iAmDeviceIdentifier in new_object_list:
            new_object_list.remove(apdu.iAmDeviceIdentifier)

        if list(old_object_list) != list(new_object_list):
            LOGGER.debug(
                f"Object lists aren't equal!... {old_object_list} -> {new_object_list}"
            )

            await self.read_multiple_objects(apdu.iAmDeviceIdentifier)

    def identifier_to_string(self, object_identifier) -> str:
        return f"{object_identifier[0].attr}:{object_identifier[1]}"

    def task_in_tasklist(self, task_name) -> bool:
        return any(
            task_name in task.get_name()
            and not task.done()
            and not task.cancelling()
            for task in self.subscription_tasks
        )

    async def handle_cov_check(self, device_identifier) -> None:

        if self.subscription_mode in {"managed_cov", "integration_controlled"}:
            device_key = self.identifier_to_string(device_identifier)
            config = self.get_config_from_addon_config(device_identifier)
            for target_device, target_object in self.managed_targets:
                if target_device != device_key:
                    continue
                if self.managed_requested_modes.get(
                    (target_device, target_object)
                ) != "cov":
                    continue
                status = self.target_status.get((target_device, target_object), {})
                if status.get("fallback_active") and status.get(
                    "fallback_reason"
                ) in {"cov_silent", "cov_failed"}:
                    continue
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=ObjectIdentifier(target_object),
                    confirmed_notifications=True,
                    lifetime=config.get(
                        "CoV_lifetime", self.default_subscription_lifetime
                    ),
                )
            return

        if self.subscription_mode == "managed_polling":
            return

        device_string = self.identifier_to_string(device_identifier)

        if self.addon_device_config is None:
            return

        specific_config = [
            config
            for config in self.addon_device_config
            if config.get("deviceID")
            == f"{device_identifier[0]}:{device_identifier[1]}"
        ]

        if not specific_config:
            specific_config = [
                config
                for config in self.addon_device_config
                if config.get("deviceID") == "all"
            ]
            if not specific_config:
                return

        index = self.addon_device_config.index(specific_config[0])

        config = self.addon_device_config[index]

        if "all" in config.get("CoV_list", []):
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList")

            if device_identifier in object_list:
                object_list.remove(device_identifier)

            object_list = [
                object_identifier
                for object_identifier in object_list
                if object_identifier[0] in subscribable_objects
            ]

            for object_identifier in object_list:

                task_name = f"{self.identifier_to_string(device_identifier)},{self.identifier_to_string(object_identifier)},confirmed"

                if self.task_in_tasklist(task_name):
                    continue

                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get(
                        "CoV_lifetime", self.default_subscription_lifetime
                    ),
                )
                await asyncio.sleep(0)

        elif config.get("CoV_list", []):

            for object_identifier in config.get("CoV_list"):

                task_name = f"{self.identifier_to_string(device_identifier)},{self.identifier_to_string(object_identifier)},confirmed"

                if self.task_in_tasklist(task_name):
                    continue

                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=object_identifier,
                    confirmed_notifications=True,
                    lifetime=config.get("CoV_lifetime"),
                )
                await asyncio.sleep(0)

    async def IAm_handler(self):
        """Do the things when receiving I Am requests"""

        while True:
            discovery_device_key = None
            try:
                apdu = await self.i_am_queue.get()

                device_id = apdu.iAmDeviceIdentifier[1]
                discovery_device_key = self._begin_fresh_discovery(
                    apdu.iAmDeviceIdentifier
                )

                # if failed stop handling response
                if not await self.read_multiple_device_props(apdu=apdu):
                    LOGGER.warning(f"Failed to get: {device_id}, {device_id}")
                    if self.bacnet_device_dict.get(f"device:{device_id}"):
                        self.bacnet_device_dict.pop(f"device:{device_id}")
                    continue

                if not self.bacnet_device_dict.get(f"device:{device_id}"):
                    LOGGER.warning(f"Failed to get: {device_id}")
                    continue

                if not self.bacnet_device_dict[f"device:{device_id}"].get(
                    f"device:{device_id}"
                ):
                    LOGGER.warning(f"Failed to get: {device_id}, {device_id}")
                    continue

                services_supported = self.bacnet_device_dict[f"device:{device_id}"][
                    f"device:{device_id}"
                ].get("protocolServicesSupported", ServicesSupported())

                if services_supported["read-property-multiple"] == 1:
                    inventory_read_success = await self.read_multiple_objects(
                        device_identifier=apdu.iAmDeviceIdentifier
                    )
                else:
                    inventory_read_success = await self.read_objects(
                        device_identifier=apdu.iAmDeviceIdentifier
                    )

                if not inventory_read_success:
                    LOGGER.warning(
                        "BACnet discovery for device:%s reported one or more read failures; validating the fresh inventory before caching",
                        device_id,
                    )
                await self._save_inventory_cache_if_complete(
                    apdu.iAmDeviceIdentifier
                )

                if self.addon_device_config:
                    await self.generate_specific_tasks(
                        device_identifier=apdu.iAmDeviceIdentifier
                    )
                else:
                    LOGGER.warning(
                        "No device configuration present; skipping automatic subscriptions for %s",
                        apdu.iAmDeviceIdentifier,
                    )

                self._end_fresh_discovery(discovery_device_key)
                discovery_device_key = None

            except Exception as err:
                LOGGER.error(f"I Am Handler failed {apdu.iAmDeviceIdentifier}: {err}")
            finally:
                if discovery_device_key is not None:
                    self._end_fresh_discovery(discovery_device_key)

    def dict_updater(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
        property_identifier: PropertyIdentifier,
        property_value,
        update_source: str | None = None,
    ):
        if isinstance(property_value, ErrorType):
            return
        elif property_value is None or property_identifier is None:
            LOGGER.debug(
                f"NoneType property (identifier) value: {device_identifier}, {object_identifier}, {property_identifier} {property_value}"
            )
            return
        elif isinstance(property_value, float):
            if isnan(property_value):
                LOGGER.warning(
                    f"Ignoring property: {device_identifier}, {object_identifier}, {property_identifier}... NaN value: {property_value}"
                )
                property_value = 0
                return
            if isinf(property_value):
                LOGGER.warning(
                    f"Ignoring property: {device_identifier}, {object_identifier}, {property_identifier}... Inf value: {property_value}"
                )
                property_value = 0
                return
            property_value = round(property_value, 4)
        elif isinstance(property_value, AnyAtomic):
            LOGGER.debug(
                f"AnyAtomic property value: {device_identifier}, {object_identifier}, {property_identifier} {property_value}"
            )
            property_value = property_value.get_value()

        if isinstance(property_value, list):
            prop_list: list = []
            for val in property_value:
                if isinstance(val, ObjectIdentifier):
                    prop_list.append(
                        [
                            val[0].attr,
                            val[1],
                        ]
                    )

        if isinstance(property_value, list) and all(
            isinstance(item, ReadAccessResult) for item in property_value
        ):
            LOGGER.debug(
                f"ReadAccessResult property value: {device_identifier}, {object_identifier}, {property_identifier} {property_value}"
            )
            return  # ignore for now...

        if isinstance(property_value, ObjectIdentifier):
            self.deep_update(
                self.bacnet_device_dict,
                {
                    f"{device_identifier[0]}:{device_identifier[1]}": {
                        f"{object_identifier[0].attr}:{object_identifier[1]}": {
                            property_identifier.attr: (
                                property_value[0].attr,
                                property_value[1],
                            )
                        }
                    }
                },
            )
        elif isinstance(
            property_value,
            (EventState, DeviceStatus, EngineeringUnits, Reliability, BinaryPV),
        ):
            self.deep_update(
                self.bacnet_device_dict,
                {
                    f"{device_identifier[0]}:{device_identifier[1]}": {
                        f"{object_identifier[0].attr}:{object_identifier[1]}": {
                            property_identifier.attr: property_value.attr,
                        }
                    }
                },
            )
        elif isinstance(property_value, OctetString):
            self.deep_update(
                self.bacnet_device_dict,
                {
                    f"{device_identifier[0]}:{device_identifier[1]}": {
                        f"{object_identifier[0].attr}:{object_identifier[1]}": {
                            property_identifier.attr: octetstring_encode(property_value)
                        }
                    }
                },
            )
        else:
            self.deep_update(
                self.bacnet_device_dict,
                {
                    f"{device_identifier[0]}:{device_identifier[1]}": {
                        f"{object_identifier[0].attr}:{object_identifier[1]}": {
                            property_identifier.attr: property_value
                        }
                    }
                },
            )

        device_key = f"{device_identifier[0].attr}:{device_identifier[1]}"
        if device_key in self._active_discovery_devices:
            object_key = f"{object_identifier[0].attr}:{object_identifier[1]}"
            property_key = getattr(property_identifier, "attr", str(property_identifier))
            self._fresh_discovery_properties.setdefault(device_key, {}).setdefault(
                object_key, set()
            ).add(property_key)

        if self.subscription_mode in {"managed_cov", "integration_controlled"}:
            target = (
                f"{device_identifier[0].attr}:{device_identifier[1]}",
                f"{object_identifier[0].attr}:{object_identifier[1]}",
            )
            if target in self.managed_targets:
                self.pending_managed_updates.add(target)

        if update_source in {"cov", "poll"}:
            self._mark_target_update(
                device_identifier,
                object_identifier,
                update_source,
            )

    async def read_multiple_device_props(self, apdu) -> bool:
        try:  # Send readPropertyMultiple and get response
            device_identifier = ObjectIdentifier(apdu.iAmDeviceIdentifier)
            parameter_list = [device_identifier, device_properties_to_read]

            LOGGER.debug(f"Reading device properties of {device_identifier}")

            response = await self.read_property_multiple(
                address=apdu.pduSource, parameter_list=parameter_list
            )

        except ErrorRejectAbortNack as err:
            LOGGER.error(f"Error reading device props: {device_identifier}: {err}")

            if "segmentation-not-supported" in str(err):
                return await self.read_device_props(apdu)
            elif "unrecognized-service" in str(err):
                return await self.read_device_props(apdu)
            elif "no-response" in str(err):
                return False
            else:
                return False

        except AttributeError as err:
            LOGGER.error(
                f"Attribute error reading device props: {device_identifier}: {err}"
            )
            return False
        else:
            for (
                object_identifier,
                property_identifier,
                property_array_index,
                property_value,
            ) in response:
                if property_value is not ErrorType:
                    self.dict_updater(
                        device_identifier=device_identifier,
                        object_identifier=object_identifier,
                        property_identifier=property_identifier,
                        property_value=property_value,
                        update_source="cov",
                    )
            return True

    async def read_device_props(self, apdu):
        address = apdu.pduSource
        device_identifier = apdu.iAmDeviceIdentifier

        LOGGER.debug(f"Reading device properties of {device_identifier} one by one.")

        for property_id in device_properties_to_read:
            if property_id == PropertyIdentifier("objectList"):
                continue

            try:
                response = await self.read_property(
                    address=address, objid=device_identifier, prop=property_id
                )
            except ErrorRejectAbortNack as err:
                LOGGER.error(
                    f"Error reading device properties one by one: {device_identifier}: {property_id} {err}"
                )

                if "no-response" in str(err):
                    return False

                continue
            except AttributeError as err:
                LOGGER.error(
                    f"Attribute error reading device properties one by one: {device_identifier}: {property_id} {err}"
                )
                continue
            except ValueError as err:
                LOGGER.error(
                    f"ValueError reading device props one by one: {device_identifier}: {property_id} {err}"
                )
                continue
            except Exception as err:
                LOGGER.error(
                    f"Exception reading device props one by one: {device_identifier}: {property_id} {err}"
                )
                continue
            else:
                if response is not ErrorType:
                    self.dict_updater(
                        device_identifier=device_identifier,
                        object_identifier=device_identifier,
                        property_identifier=property_id,
                        property_value=response,
                    )

        if await self.read_object_list_property(device_identifier):
            return True
        else:
            return False

    async def read_object_list_property(self, device_identifier) -> bool:
        """Read object list property in the smallest possible way."""
        address = self.dev_to_addr(dev=device_identifier)

        LOGGER.debug(f"Reading objectList property of {device_identifier} one by one.")

        try:
            object_amount = await self.read_property(
                address=address,
                objid=device_identifier,
                prop=PropertyIdentifier("objectList"),
                array_index=0,
            )

            if object_amount == 0:
                return False
        except ErrorRejectAbortNack as err:
            LOGGER.warning(
                f"Error getting object list size for {device_identifier} at {address}: {err}"
            )
            return False

        object_list = []

        try:
            async def read_object_identifier(number):
                async with self.discovery_read_semaphore:
                    return await self.read_property(
                        address=address,
                        objid=device_identifier,
                        prop=PropertyIdentifier("objectList"),
                        array_index=number,
                    )

            object_list = list(
                await asyncio.gather(
                    *(
                        read_object_identifier(number)
                        for number in range(1, object_amount + 1)
                    )
                )
            )

            self.dict_updater(
                device_identifier=device_identifier,
                object_identifier=device_identifier,
                property_identifier=PropertyIdentifier("objectList"),
                property_value=object_list,
            )
        except ErrorRejectAbortNack as err:
            LOGGER.warning(
                f"Error getting object list size for {device_identifier} at {address}: {err}"
            )
            return False
        else:
            return True

    async def read_multiple_objects(self, device_identifier):
        """Read all objects from a device."""
        LOGGER.info(f"Reading objects from objectList of {device_identifier}...")
        device_identifier = ObjectIdentifier(device_identifier)
        object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
            f"device:{device_identifier[1]}"
        ]["objectList"]

        async def read_one_object(obj_id):
            if not isinstance(obj_id, ObjectIdentifier):
                obj_id = ObjectIdentifier(obj_id)

            if (
                ObjectType(obj_id[0]) == ObjectType("device")
                or ObjectType(obj_id[0])
                not in self.vendor_info.registered_object_classes
            ):
                return "skipped"

            parameter_list = [obj_id, object_properties_to_read_once]

            try:  # Send readPropertyMultiple and get response
                async with self.discovery_read_semaphore:
                    response = await self.read_property_multiple(
                        address=self.dev_to_addr(device_identifier),
                        parameter_list=parameter_list,
                    )

            except ErrorRejectAbortNack as err:
                LOGGER.error(
                    f"Error while reading object list: {device_identifier}: {obj_id} {err}"
                )

                if "unrecognized-service" in str(err):
                    return "fallback"
                elif "segmentation-not-supported" in str(err):
                    return "fallback"
                elif "no-response" in str(err):
                    return "failed"
                return "failed"

            except AssertionError as err:
                LOGGER.error(
                    f"Assertion error for: {device_identifier}: {obj_id} {err}"
                )
                return "failed"

            except AttributeError as err:
                LOGGER.error(
                    f"Attribute error while reading object list: {device_identifier}: {obj_id} {err}"
                )
                return "failed"
            else:
                for (
                    object_identifier,
                    property_identifier,
                    property_array_index,
                    property_value,
                ) in response:
                    if property_value is not ErrorType:
                        self.dict_updater(
                            device_identifier=device_identifier,
                            object_identifier=object_identifier,
                            property_identifier=property_identifier,
                            property_value=property_value,
                        )
                return "ok"

        results = await asyncio.gather(
            *(read_one_object(obj_id) for obj_id in object_list),
            return_exceptions=True,
        )

        if any(result == "fallback" for result in results):
            LOGGER.info(
                "ReadPropertyMultiple is unavailable; using bounded single-property discovery for %s",
                device_identifier,
            )
            return await self.read_objects(device_identifier)

        if any(result == "failed" or isinstance(result, Exception) for result in results):
            LOGGER.warning(
                "Some BACnet objects could not be read during discovery of %s",
                device_identifier,
            )
            return False

        return True

    async def read_objects(self, device_identifier):
        try:
            object_list = self.bacnet_device_dict[f"device:{device_identifier[1]}"][
                f"device:{device_identifier[1]}"
            ].get("objectList", [])

            async def read_one_object(obj_id):
                if not isinstance(obj_id, ObjectIdentifier):
                    obj_id = ObjectIdentifier(obj_id)

                if (
                    ObjectType(obj_id[0]) == ObjectType("device")
                    or ObjectType(obj_id[0])
                    not in self.vendor_info.registered_object_classes
                ):
                    return True

                object_class = self.vendor_info.get_object_class(obj_id[0])

                if object_class is None:
                    LOGGER.warning(
                        f"Object type is unknown: {device_identifier}, {obj_id}"
                    )
                    return True

                for property_id in object_properties_to_read_once:
                    property_class = object_class.get_property_type(property_id)

                    if property_class is None:
                        continue

                    try:
                        async with self.discovery_read_semaphore:
                            response = await self.read_property(
                                address=self.dev_to_addr(device_identifier),
                                objid=obj_id,
                                prop=property_id,
                            )
                    except ErrorRejectAbortNack as err:
                        LOGGER.error(
                            f"Error reading object list one by one: {device_identifier} {obj_id} {property_id}: {err}"
                        )
                        if "no-response" in str(err):
                            return False
                        continue
                    else:
                        if response is not ErrorType:
                            self.dict_updater(
                                device_identifier=device_identifier,
                                object_identifier=obj_id,
                                property_identifier=property_id,
                                property_value=response,
                            )

                return True

            results = await asyncio.gather(
                *(read_one_object(obj_id) for obj_id in object_list),
                return_exceptions=True,
            )
            if any(result is False or isinstance(result, Exception) for result in results):
                LOGGER.warning(
                    "Some single-property BACnet discovery reads failed for %s",
                    device_identifier,
                )
                return False
            return True

        except AttributeError as err:
            LOGGER.error(
                f"Attribute error reading object list one by one: {device_identifier}: {err}"
            )
            return False

    async def read_multiple_objects_periodically(self, device_identifier):
        """Read objects after a set time."""

        for obj_id in self.bacnet_device_dict[device_identifier]:
            if not isinstance(obj_id, ObjectIdentifier):
                obj_id = ObjectIdentifier(obj_id)
                device_identifier = ObjectIdentifier(device_identifier)

            if (
                ObjectType(obj_id[0]) == ObjectType("device")
                or ObjectType(obj_id[0])
                not in self.vendor_info.registered_object_classes
            ):
                continue

            parameter_list = [obj_id, object_properties_to_read_periodically]

            try:  # Send readPropertyMultiple and get response
                response = await self.read_property_multiple(
                    address=self.dev_to_addr(ObjectIdentifier(device_identifier)),
                    parameter_list=parameter_list,
                )

            except ErrorRejectAbortNack as err:
                LOGGER.error(
                    f"Error reading objects periodically:{device_identifier}, {obj_id}: {err}"
                )
                if "unrecognized-service" in str(err):
                    await self.read_objects_periodically(device_identifier)
                    return
                elif "segmentation-not-supported" in str(err):
                    await self.read_objects_periodically(device_identifier)
                    return
                elif "no-response" in str(err):
                    return False

            except AttributeError as err:
                LOGGER.error(f"Attribute error: {obj_id}: {err}")

            else:
                for (
                    object_identifier,
                    property_identifier,
                    property_array_index,
                    property_value,
                ) in response:
                    if property_value is not ErrorType:
                        self.dict_updater(
                            device_identifier=device_identifier,
                            object_identifier=object_identifier,
                            property_identifier=property_identifier,
                            property_value=property_value,
                        )

    async def read_objects_periodically(self, device_identifier):
        """Read objects if regular way failed."""
        LOGGER.info(f"Reading objects for {device_identifier}...")
        for obj_id in self.bacnet_device_dict[device_identifier]:
            if not isinstance(obj_id, ObjectIdentifier):
                obj_id = ObjectIdentifier(obj_id)
                device_identifier = ObjectIdentifier(device_identifier)

            if (
                ObjectType(obj_id[0]) == ObjectType("device")
                or ObjectType(obj_id[0])
                not in self.vendor_info.registered_object_classes
            ):
                continue

            object_class = self.vendor_info.get_object_class(obj_id[0])

            if object_class is None:
                LOGGER.warning(f"Object type is unknown: {device_identifier}, {obj_id}")
                continue

            for property_id in object_properties_to_read_periodically:
                property_class = object_class.get_property_type(property_id)

                if property_class is None:
                    continue

                try:
                    response = await self.read_property(
                        address=self.dev_to_addr(device_identifier),
                        objid=obj_id,
                        prop=property_id,
                    )

                except ErrorRejectAbortNack as err:
                    LOGGER.error(
                        f"Error reading objects one by one periodically: {device_identifier} {obj_id} {property_id}: {err}"
                    )
                    if "no-response" in str(err):
                        return False
                    continue
                except AttributeError as err:
                    LOGGER.error(f"Attribute error: {obj_id}: {err}")
                else:
                    if response is not ErrorType:
                        self.dict_updater(
                            device_identifier=device_identifier,
                            object_identifier=obj_id,
                            property_identifier=property_id,
                            property_value=response,
                        )

    async def subscribe_object_list(self, device_identifier):
        """ "Subscribe to selected objects."""  # Maybe make a blacklist to exclude objects we dont want to subscribe to.
        for object_id in self.bacnet_device_dict[f"device:{device_identifier[1]}"]:
            if ObjectIdentifier(object_id)[0] in self.subscription_list:
                await self.create_subscription_task(
                    device_identifier=device_identifier,
                    object_identifier=ObjectIdentifier(object_id),
                    confirmed_notifications=True,
                    lifetime=self.default_subscription_lifetime,
                )
                await asyncio.sleep(0)

    async def create_subscription_task(
        self,
        device_identifier: ObjectIdentifier,
        object_identifier: ObjectIdentifier,
        confirmed_notifications: bool,
        lifetime: int | None = None,
    ):
        device_address = self.dev_to_addr(ObjectIdentifier(device_identifier))
        if confirmed_notifications:
            notifications = "confirmed"
        else:
            notifications = "unconfirmed"

        object_identifier = ObjectIdentifier(object_identifier)

        task_name = f"{device_identifier[0].attr}:{device_identifier[1]},{object_identifier[0].attr}:{object_identifier[1]},{notifications}"
        target = self._target_key(device_identifier, object_identifier)
        self._ensure_target_status(target, self.subscription_mode)
        if any(
            task.get_name() == task_name
            and not task.done()
            and not task.cancelling()
            for task in self.subscription_tasks
        ):
            self.subscription_diagnostics[
                "duplicate_task_creation_attempts"
            ] += 1
            LOGGER.debug(f"Subscription task already active: {task_name}")
            return False

        device_prefix = f"{device_identifier[0].attr}:{device_identifier[1]},"
        active_for_device = sum(
            task.get_name().startswith(device_prefix)
            and not task.done()
            and not task.cancelling()
            for task in self.subscription_tasks
        )
        cov_limit = self._cov_limit_for_device(device_identifier)
        if active_for_device >= cov_limit:
            target = self._target_key(device_identifier, object_identifier)
            status = self._ensure_target_status(target, self.subscription_mode)
            status["state"] = "polling_fallback"
            status["last_error"] = f"COV limit {cov_limit} reached"
            await self._ensure_cov_polling_fallback(
                device_identifier,
                object_identifier,
                "cov_limit",
            )
            await asyncio.sleep(self.managed_cov_subscription_delay)
            return False

        LOGGER.debug(
            f"Creating {notifications} subscription task {object_identifier} of {device_identifier}"
        )
        self.subscription_diagnostics["tasks_created"] += 1

        task = asyncio.create_task(
            self.subscription_task(
                device_address=device_address,
                object_identifier=ObjectIdentifier(object_identifier),
                confirmed_notification=confirmed_notifications,
                lifetime=lifetime,
            ),
            name=task_name,
        )
        task.add_done_callback(self._subscription_task_done)
        self.subscription_tasks.append(task)
        await asyncio.sleep(self.managed_cov_subscription_delay)
        return True

    def _subscription_task_done(self, task: asyncio.Task) -> None:
        """Remove completed COV tasks even when device cleanup raises an error."""
        if task in self.subscription_tasks:
            self.subscription_tasks.remove(task)

    async def subscription_task(
        self,
        device_address: Address,
        object_identifier: ObjectIdentifier,
        confirmed_notification: bool,
        lifetime: int | None = None,
    ) -> None:
        """Task with context manager to handle CoV."""

        device_identifier = self.addr_to_dev(addr=device_address)

        if confirmed_notification:
            notifications = "confirmed"
        else:
            notifications = "unconfirmed"

        task_name = f"{device_identifier[0].attr}:{device_identifier[1]},{object_identifier[0].attr}:{object_identifier[1]},{notifications}"
        target = self._target_key(device_identifier, object_identifier)
        status = self._ensure_target_status(target, self.subscription_mode)
        status["state"] = "subscribing"
        status["last_error"] = None

        unsubscribe_cov_request = None

        try:
            async with self.change_of_value(
                address=device_address,
                monitored_object_identifier=object_identifier,
                subscriber_process_identifier=None,
                issue_confirmed_notifications=confirmed_notification,
                lifetime=lifetime,
            ) as subscription:
                status["subscription_confirmed_at"] = time.time()
                status["state"] = "cov_waiting"
                old_watchdog = self.cov_watchdog_tasks.pop(target, None)
                if old_watchdog is not None and not old_watchdog.done():
                    old_watchdog.cancel()
                self.cov_watchdog_tasks[target] = asyncio.create_task(
                    self._cov_value_watchdog(
                        device_identifier,
                        object_identifier,
                    ),
                    name=f"cov-watchdog-{target[0]}-{target[1]}",
                )
                # create a request to cancel the subscription
                unsubscribe_cov_request = SubscribeCOVRequest(
                    subscriberProcessIdentifier=subscription.subscriber_process_identifier,
                    monitoredObjectIdentifier=subscription.monitored_object_identifier,
                    destination=subscription.address,
                )

                unsubscribe_cov_request.pduDestination = device_address

                LOGGER.debug(f"Created {task_name} subscription task successfully")
                self.subscription_diagnostics["subscriptions_established"] += 1

                while True:
                    try:
                        property_identifier, property_value = await asyncio.wait_for(
                            subscription.get_value(), 10
                        )
                    except asyncio.TimeoutError:
                        # check if address has changes
                        if subscription.address != self.dev_to_addr(
                            dev=device_identifier
                        ):
                            old_key = (
                                subscription.address,
                                subscription.subscriber_process_identifier,
                            )
                            self._cov_contexts.pop(old_key)

                            subscription.address = self.dev_to_addr(
                                dev=device_identifier
                            )

                            new_key = (
                                subscription.address,
                                subscription.subscriber_process_identifier,
                            )

                            self._cov_contexts[new_key] = subscription

                        if not isinstance(
                            subscription.refresh_subscription_task, asyncio.Task
                        ):
                            continue

                        if subscription.refresh_subscription_task.done():
                            # check for exceptions (gets raised by result if there is)
                            subscription.refresh_subscription_task.result()

                        continue

                    except Exception:
                        raise

                    object_class = self.vendor_info.get_object_class(
                        subscription.monitored_object_identifier[0]
                    )
                    property_type = object_class.get_property_type(property_identifier)

                    if property_type is None or property_value is None:
                        LOGGER.warning(
                            f"NoneType property: {subscription.monitored_object_identifier} {property_identifier} {property_value}"
                        )
                        continue
                    elif property_identifier not in object_properties_to_read_once:
                        LOGGER.warning(
                            f"Ignoring property: {subscription.monitored_object_identifier[0]} {property_identifier} {property_value}"
                        )
                        continue

                    LOGGER.debug(
                        f"{notifications} CoV: {device_identifier} {object_identifier} {property_identifier} {property_value}"
                    )
                    self.subscription_diagnostics["cov_values_received"] += 1

                    self.dict_updater(
                        device_identifier=device_identifier,
                        object_identifier=object_identifier,
                        property_identifier=property_identifier,
                        property_value=property_value,
                        update_source="cov",
                    )

        except ErrorRejectAbortNack as err:
            self.subscription_diagnostics["subscription_failures"] += 1
            status["state"] = "polling_fallback"
            status["last_error"] = str(err)
            LOGGER.error(
                f"ErrorRejectAbortNack: {self.addr_to_dev(device_address)}, {object_identifier}: {err}"
            )
            await self._ensure_cov_polling_fallback(
                device_identifier,
                object_identifier,
                "cov_failed",
            )

        except AbortPDU as err:
            self.subscription_diagnostics["subscription_failures"] += 1
            status["state"] = "polling_fallback"
            status["last_error"] = str(err)
            LOGGER.error(f"{err}")
            await self._ensure_cov_polling_fallback(
                device_identifier,
                object_identifier,
                "cov_failed",
            )

        except asyncio.CancelledError as err:
            self.subscription_diagnostics["subscription_cancellations"] += 1
            LOGGER.debug(
                f"Cancelling subscription task: {device_identifier}, {object_identifier}: {err}"
            )

            # send the request, wait for the response
            if unsubscribe_cov_request:
                response = await self.request(unsubscribe_cov_request)

        except Exception as err:
            self.subscription_diagnostics["subscription_failures"] += 1
            status["state"] = "polling_fallback"
            status["last_error"] = str(err)
            LOGGER.error(f"Error: {device_identifier}, {object_identifier}: {err}")
            await self._ensure_cov_polling_fallback(
                device_identifier,
                object_identifier,
                "cov_failed",
            )

            # send the request, wait for the response
            if unsubscribe_cov_request:
                response = await self.request(unsubscribe_cov_request)

    async def end_subscription_tasks(self):
        tasks = list(self.subscription_tasks)
        tasks.extend(self.cov_fallback_tasks.values())
        tasks.extend(self.cov_watchdog_tasks.values())
        tasks.extend(self.managed_poll_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            _, pending = await asyncio.wait(tasks, timeout=5)
            if pending:
                LOGGER.warning(
                    "Timed out while stopping %s BACnet background tasks",
                    len(pending),
                )
        self.subscription_tasks.clear()
        self.cov_fallback_tasks.clear()
        self.cov_watchdog_tasks.clear()
        self.managed_poll_tasks.clear()
        LOGGER.info("Cancelled all subscriptions")

    async def do_ConfirmedCOVNotificationRequest(
        self, apdu: ConfirmedCOVNotificationRequest
    ) -> None:

        address = apdu.pduSource
        subscriber_process_identifier = apdu.subscriberProcessIdentifier

        # find the context
        scm = self._cov_contexts.get((address, subscriber_process_identifier), None)

        if not scm:
            await asyncio.sleep(0.1)
            scm = self._cov_contexts.get((address, subscriber_process_identifier), None)

        if (not scm) or (
            apdu.monitoredObjectIdentifier != scm.monitored_object_identifier
        ):
            raise ServicesError(errorCode="unknownSubscription")

        # queue the property values
        for property_value in apdu.listOfValues:
            await scm.put(property_value)

        # success
        resp = SimpleAckPDU(context=apdu)

        # return the result
        await self.response(resp)

    async def do_ReadPropertyRequest(self, apdu: ReadPropertyRequest) -> None:
        try:
            await super().do_ReadPropertyRequest(apdu)
        except (Exception, AttributeError) as err:
            await super().do_ReadPropertyRequest(apdu)
            LOGGER.warning(
                f"{self.addr_to_dev(apdu.pduSource)} tried to read {apdu.objectIdentifier} {apdu.propertyIdentifier}: {err}"
            )

    async def do_ReadPropertyMultipleRequest(
        self, apdu: ReadPropertyMultipleRequest
    ) -> None:
        try:
            await super().do_ReadPropertyMultipleRequest(apdu)
        except (Exception, AttributeError) as err:
            for read_access_spec in apdu.listOfReadAccessSpecs:
                property_list = [
                    property_id.propertyIdentifier
                    for property_id in read_access_spec.listOfPropertyReferences
                ]

                LOGGER.warning(
                    f"{self.addr_to_dev(apdu.pduSource)} failed to read {read_access_spec.objectIdentifier} {property_list}: {err}"
                )
            await super().do_ReadPropertyMultipleRequest(apdu)
