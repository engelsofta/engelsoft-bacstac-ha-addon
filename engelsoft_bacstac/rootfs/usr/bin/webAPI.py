"""API script for BACnet add-on.

Modified by engelsofta in 2026; derived from the Bepacom BACnet/IP add-on.
"""

import asyncio
import codecs
import csv
import json
import os
import shutil
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from random import choice, randint
from typing import Annotated, Any, Callable, Union

from bacpypes3.basetypes import (EngineeringUnits, ObjectIdentifier,
                                 ObjectType, ObjectTypesSupported,
                                 PropertyIdentifier)
from bacpypes3.ipv4.app import Application
from const import LOGGER
from fastapi import (FastAPI, Path, Query, Request, Response, UploadFile,
                     WebSocket, WebSocketDisconnect, status)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import parse_obj_as
from device_protection import remove_rule, upsert_rule
from runtime_settings import load as load_runtime_settings, save as save_runtime_settings

# ===================================================
# Global variables
# ===================================================

bacnet_device_dict: dict
bacnet_application: Application | None = None
activeSockets: list = []
activeV2Sockets: list = []
websocket_broadcast_task: asyncio.Task | None = None
protocol_sequence = 0
EDE_files: list = []
sub_list: list = []

who_is_func: Callable
i_am_func: Callable
ingress: str

log_path: str | None = None

diagnostics_started_at = time.time()
diagnostic_counters = {
    "api_subscribe_requests": 0,
    "api_unsubscribe_requests": 0,
    "duplicate_subscribe_requests": 0,
    "managed_target_requests": 0,
    "managed_target_rejections": 0,
    "websocket_initial_snapshots": 0,
    "websocket_update_snapshots": 0,
    "websocket_delta_messages": 0,
    "websocket_delta_objects": 0,
    "websocket_delta_properties": 0,
    "protocol_v2_connections": 0,
    "protocol_v2_commands": 0,
    "protocol_v2_errors": 0,
}

PROTOCOL_VERSION = 2
PROTOCOL_CAPABILITIES = [
    "inventory", "managed_targets", "managed_snapshot", "point_events",
    "write_property", "release_priority", "diagnostics", "resync",
]


def _configured_api_token() -> str:
    """Read the optional shared secret from Home Assistant app options."""
    try:
        with open("/data/options.json", encoding="utf-8") as options_file:
            return str(json.load(options_file).get("api_token") or "")
    except (OSError, ValueError, TypeError):
        return ""


def protocol_info() -> dict:
    """Return the stable compatibility contract used by integrations."""
    return {
        "product": "engelsoft-bacstac",
        "app_version": app.version,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_versions": [PROTOCOL_VERSION],
        "capabilities": PROTOCOL_CAPABILITIES,
        "bacnet": {
            "ready": bacnet_application is not None,
            "device_count": sum(
                1 for key in bacnet_device_dict if str(key).startswith("device:")
            ),
        },
    }


def deep_update(mapping: dict, *updating_mappings: dict) -> dict:
    updated_mapping = mapping.copy()
    for updating_mapping in updating_mappings:
        for k, v in updating_mapping.items():
            if (
                k in updated_mapping
                and isinstance(updated_mapping[k], dict)
                and isinstance(v, dict)
            ):
                updated_mapping[k] = deep_update(updated_mapping[k], v)
            else:
                updated_mapping[k] = v
    return updated_mapping


def is_valid_json(data: dict):
    try:
        json.dumps(data)
        return True
    except Exception as err:
        LOGGER.warning(f"Error converting to JSON: {err}")
        return False


def websocket_snapshot() -> dict:
    """Return the full or managed-COV-filtered WebSocket snapshot."""
    source = bacnet_device_dict
    if EDE_files:
        for file in EDE_files:
            source = deep_update(source, file)

    application = bacnet_application
    if not getattr(application, "managed_targets", None):
        return source

    filtered: dict = {}
    for device_id, object_id in application.managed_targets:
        object_payload = source.get(device_id, {}).get(object_id)
        if object_payload is None:
            continue
        filtered.setdefault(device_id, {})[object_id] = object_payload
    return filtered


@dataclass
class EventStruct:
    """Events and Queue's for BACnetIOHandler"""

    write_queue: asyncio.Queue = asyncio.Queue()
    sub_queue: asyncio.Queue = asyncio.Queue()
    unsub_queue: asyncio.Queue = asyncio.Queue()
    val_updated_event: asyncio.Event = asyncio.Event()
    read_event: asyncio.Event = asyncio.Event()
    who_is_event: asyncio.Event = asyncio.Event()
    i_am_event: asyncio.Event = asyncio.Event()
    startup_complete_event: asyncio.Event = asyncio.Event()


events = EventStruct()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager of FastAPI."""
    # Do nothing on startup
    await events.startup_complete_event.wait()
    await asyncio.sleep(5)
    yield
    # Do nothing on shutdown


description = """
# Engelsoft BACstac API

## Use

This API can be used within Home Assistant. Outside connections are blocked unless they connect through the ingress link.
The BACnet integration will use the websocket and API points to receive and write data for the corresponding entities.

## Suggestions

Please submit suggestions and issues in the [GitHub repository](https://github.com/engelsofta/engelsoft-bacstac-ha-addon).

"""

tags_metadata = [
    {"name": "Webpages", "description": "Accessible web pages."},
    {
        "name": "apiv1",
        "description": "Legacy API meant to be replaced by V2 in the future.",
    },
    {"name": "apiv2", "description": "API V2."},
]


def get_ingress_url() -> str:
    """Return Home Assistant Ingress URL"""
    try:
        with open("ingress.ini", "r") as ingress:
            url = ingress.read()
            newURL = url.replace("/webapp", "")
            return newURL
    except:
        return ""


app = FastAPI(
    lifespan=lifespan,
    title="Engelsoft BACstac API",
    description=description,
    version="1.3.0",
    contact={
        "name": "Engelsoft BACstac",
        "url": "https://github.com/engelsofta/engelsoft-bacstac-ha-addon/issues",
    },
    root_path=get_ingress_url(),
    openapi_tags=tags_metadata,
)


path_str = os.path.dirname(os.path.realpath(__file__))

app.mount(
    "/static",
    StaticFiles(directory=f"{path_str}/static"),
    name="static",
)

templates = Jinja2Templates(directory=f"{path_str}/templates")


@app.get("/health", tags=["Protocol V2"])
async def health():
    """Small endpoint that remains useful when the event channel is down."""
    return {"status": "ok", "bacnet_ready": bacnet_application is not None}


@app.get("/bepacom/info", tags=["Protocol V2"])
async def bepacom_info():
    """Advertise product identity, protocol version and optional features."""
    return protocol_info()


def sidebar_status() -> dict:
    """Build the compact transport summary shown on every WebUI page."""
    application = bacnet_application
    ready = application is not None
    statuses = getattr(application, "target_status", {}).values()
    return {
        "mode": "integration_controlled" if ready else "starting",
        "label": "Integrationsgesteuert" if ready else "Wird gestartet",
        "targets": len(getattr(application, "managed_targets", [])),
        "cov": len(getattr(application, "managed_cov_task_names", [])),
        "polling": len(getattr(application, "managed_poll_targets", [])),
        "disabled": len(getattr(application, "managed_disabled_targets", [])),
        "fallback": sum(bool(item.get("fallback_active")) for item in statuses),
    }


def _device_details(device_id: str, payload: dict) -> dict:
    """Return compact display properties for one discovered BACnet device."""
    device_object = payload.get(device_id, {}) if isinstance(payload, dict) else {}
    object_count = max(0, len(payload) - (1 if device_id in payload else 0))
    properties = {
        "name": device_object.get("objectName", device_id),
        "vendor": device_object.get("vendorName", "—"),
        "model": device_object.get("modelName", "—"),
        "firmware": device_object.get(
            "firmwareRevision", device_object.get("applicationSoftwareVersion", "—")
        ),
        "status": device_object.get("systemStatus", "—"),
        "segmentation": device_object.get("segmentationSupported", "—"),
        "address": device_object.get("address", "—"),
        "objects": object_count,
    }
    application = bacnet_application
    if application is not None:
        try:
            address = application.dev_to_addr(ObjectIdentifier(device_id))
            if address is not None:
                properties["address"] = str(address)
        except Exception:
            pass
    return {key: jsonable_encoder(value) for key, value in properties.items()}


def device_protection_payload() -> dict:
    """Build device properties and effective protection rules for the UI."""
    application = bacnet_application
    rules = list(getattr(application, "addon_device_config", []) or [])
    default = next((rule for rule in rules if rule.get("deviceID") == "all"), {})
    overrides = {
        rule.get("deviceID"): rule
        for rule in rules
        if rule.get("deviceID") and rule.get("deviceID") != "all"
    }
    devices = []
    for device_id, payload in sorted(bacnet_device_dict.items()):
        if not str(device_id).startswith("device:"):
            continue
        override = overrides.get(device_id)
        requested_cov = sum(
            mode == "cov" and target[0] == device_id
            for target, mode in getattr(application, "managed_requested_modes", {}).items()
        )
        active_cov = sum(
            task.get_name().startswith(f"{device_id},")
            and not task.done()
            and not task.cancelling()
            for task in getattr(application, "subscription_tasks", [])
        )
        address = _device_details(device_id, payload).get("address", "—")
        devices.append(
            {
                "deviceID": device_id,
                "properties": _device_details(device_id, payload),
                "rule": override or default,
                "has_override": override is not None,
                "connection_status": "online" if address != "—" else "cached",
                "cov_requested": requested_cov,
                "cov_active": active_cov,
            }
        )
    discovered_ids = {device["deviceID"] for device in devices}
    for device_id, override in sorted(overrides.items()):
        if device_id in discovered_ids:
            continue
        devices.append(
            {
                "deviceID": device_id,
                "properties": {
                    "name": "Nicht aktuell erreichbar",
                    "vendor": "—",
                    "model": "—",
                    "firmware": "—",
                    "status": "Offline / nicht entdeckt",
                    "segmentation": "—",
                    "address": "—",
                    "objects": 0,
                },
                "rule": override,
                "has_override": True,
                "connection_status": "offline",
                "cov_requested": 0,
                "cov_active": 0,
            }
        )
    return {"default": default, "devices": devices}


def runtime_settings_payload() -> dict:
    application = bacnet_application
    if application is None:
        return load_runtime_settings()
    return {
        "managed_poll_rate": application.managed_poll_rate,
        "managed_cov_subscription_delay_ms": round(application.managed_cov_subscription_delay_seconds * 1000),
        "managed_cov_fallback_timeout": application.managed_cov_fallback_timeout,
        "defaultPriority": getattr(application, "default_write_priority", 15),
    }


@app.get("/webapp", response_class=HTMLResponse, tags=["Webpages"])
async def webapp(request: Request):
    """Index and main page of the add-on."""
    dict_to_send = bacnet_device_dict
    if EDE_files:
        for file in EDE_files:
            dict_to_send = deep_update(dict_to_send, file)

    dict_to_send = jsonable_encoder(dict_to_send)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "bacnet_devices": dict_to_send,
            "sidebar": sidebar_status(),
            "device_protection": device_protection_payload(),
        },
    )


@app.get("/apiv1/device-protection", tags=["apiv1"])
async def get_device_protection():
    """Return persistent per-device safety settings."""
    return device_protection_payload()


@app.get("/apiv1/runtime-settings", tags=["apiv1"])
async def get_runtime_settings():
    return runtime_settings_payload()


@app.put("/apiv1/runtime-settings", tags=["apiv1"])
async def set_runtime_settings(request: Request):
    application = bacnet_application
    if application is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        settings = save_runtime_settings(await request.json())
    except (TypeError, ValueError, OSError) as err:
        return Response(content=str(err), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    application.managed_poll_rate = settings["managed_poll_rate"]
    application.managed_cov_subscription_delay_seconds = settings["managed_cov_subscription_delay_ms"] / 1000
    application.managed_cov_fallback_timeout = settings["managed_cov_fallback_timeout"]
    application.default_write_priority = settings["defaultPriority"]
    await application.reapply_managed_targets()
    return settings


@app.get("/apiv1/devices/{device_id}/objects", tags=["apiv1"])
async def get_device_objects(device_id: str, query: str = ""):
    """Load object metadata only when a device is expanded."""
    payload = bacnet_device_dict.get(device_id)
    if payload is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    needle = query.casefold().strip()
    result = []
    for object_id, properties in payload.items():
        if object_id == device_id or not isinstance(properties, dict):
            continue
        searchable = f"{object_id} {properties.get('objectName', '')} {properties.get('description', '')}".casefold()
        if needle and needle not in searchable:
            continue
        result.append({"object_id": object_id, "properties": jsonable_encoder(properties)})
    return {"device_id": device_id, "objects": result}


@app.put("/apiv1/device-protection/{device_id}", tags=["apiv1"])
async def set_device_protection(device_id: str, request: Request):
    """Persist a rule and re-apply the current integration target plan live."""
    application = bacnet_application
    if application is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    try:
        values = await request.json()
        if not isinstance(values, dict):
            raise TypeError("Expected a JSON object")
        application.addon_device_config = upsert_rule(
            list(application.addon_device_config), device_id, values
        )
    except (TypeError, ValueError, OSError) as err:
        return Response(content=str(err), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    await application.reapply_managed_targets()
    return device_protection_payload()


@app.delete("/apiv1/device-protection/{device_id}", tags=["apiv1"])
async def delete_device_protection(device_id: str):
    """Remove a device override and immediately use the global defaults."""
    application = bacnet_application
    if application is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    application.addon_device_config = remove_rule(
        list(application.addon_device_config), device_id
    )
    await application.reapply_managed_targets()
    return device_protection_payload()


@app.get("/subscriptions", response_class=HTMLResponse, tags=["Webpages"])
async def subscriptions(request: Request):
    """Page to see subscription ID's."""
    subs_as_string: list = []
    global sub_list

    return templates.TemplateResponse(
        "subscriptions.html",
        {
            "request": request,
            "sidebar": sidebar_status(),
            "targets": (
                bacnet_application.target_status_snapshot()
                if bacnet_application is not None
                else []
            ),
        },
    )


@app.get("/subscriptions/targets", response_class=HTMLResponse, tags=["Webpages"])
async def subscription_targets(request: Request):
    """Return the live target rows without reloading the complete page."""
    return templates.TemplateResponse(
        "target_rows.html",
        {
            "request": request,
            "targets": (
                bacnet_application.target_status_snapshot()
                if bacnet_application is not None
                else []
            ),
        },
    )


@app.get("/ede", response_class=HTMLResponse, tags=["Webpages"])
async def ede(request: Request):
    """Page to see EDE files uploaded."""
    return templates.TemplateResponse(
        "ede.html",
        {"request": request, "files": EDE_files, "sidebar": sidebar_status()},
    )


@app.get("/apiv1/json", tags=["apiv1"])
async def get_entire_dict():
    """Return all devices and their values."""
    dict_to_send = bacnet_device_dict
    if EDE_files:
        for file in EDE_files:
            dict_to_send = deep_update(dict_to_send, file)

    data_to_send = jsonable_encoder(dict_to_send)

    return data_to_send


@app.get("/apiv1/diagnostics/subscriptions", tags=["apiv1"])
async def get_subscription_diagnostics():
    """Return read-only subscription and WebSocket runtime diagnostics."""
    application = bacnet_application
    tasks = list(getattr(application, "subscription_tasks", []))
    task_details = [
        {
            "name": task.get_name(),
            "state": (
                "cancelled"
                if task.cancelled()
                else "done"
                if task.done()
                else "active"
            ),
        }
        for task in tasks
    ]
    active_tasks = [task for task in tasks if not task.done()]
    names = [task.get_name() for task in active_tasks]

    return {
        "ready": application is not None,
        "subscription_mode": "integration_controlled" if application else "starting",
        "managed_poll_rate": getattr(application, "managed_poll_rate", None),
        "managed_targets": len(getattr(application, "managed_targets", [])),
        "managed_poll_targets": len(getattr(application, "managed_poll_targets", [])),
        "managed_cov_targets": len(getattr(application, "managed_cov_task_names", [])),
        "managed_disabled_targets": len(
            getattr(application, "managed_disabled_targets", [])
        ),
        "managed_requested_modes": {
            f"{device_id}/{object_id}": mode
            for (device_id, object_id), mode in getattr(
                application, "managed_requested_modes", {}
            ).items()
        },
        "target_status": (
            application.target_status_snapshot() if application is not None else []
        ),
        "active_managed_poll_tasks": sum(
            not task.done()
            for task in getattr(application, "managed_poll_tasks", {}).values()
        ),
        "uptime_seconds": round(time.time() - diagnostics_started_at, 1),
        "active_subscription_tasks": len(active_tasks),
        "tracked_subscription_tasks": len(tasks),
        "duplicate_active_task_names": len(names) - len(set(names)),
        "active_websocket_clients": len(activeSockets),
        "active_protocol_v2_clients": len(activeV2Sockets),
        **diagnostic_counters,
        **getattr(application, "subscription_diagnostics", {}),
        "inventory_cache": getattr(
            application, "inventory_cache_diagnostics", {}
        ),
        "subscriptions": task_details,
    }


@app.post("/apiv1/managed/targets", tags=["apiv1"])
async def set_managed_targets(request: Request):
    """Replace integration-managed targets and their requested transports."""
    diagnostic_counters["managed_target_requests"] += 1
    application = bacnet_application
    if application is None:
        return {"accepted": False, "mode": "starting", "targets": 0}

    payload = await request.json()
    raw_targets = payload.get("targets", []) if isinstance(payload, dict) else []
    targets = []
    try:
        for target in raw_targets:
            device_id = str(target["device_id"])
            object_id = str(target["object_id"])
            update_mode = str(
                target.get("update_mode", target.get("mode", "polling"))
            ).lower()
            update_mode = {
                "push": "cov",
                "subscribe": "cov",
                "managed_cov": "cov",
                "poll": "polling",
                "managed_polling": "polling",
                "off": "disabled",
                "none": "disabled",
            }.get(update_mode, update_mode)
            if update_mode not in {"cov", "polling", "disabled"}:
                raise ValueError(f"unsupported update_mode: {update_mode}")
            if ":" not in device_id and "," not in device_id:
                device_id = f"device:{device_id}"
            targets.append(
                (
                    ObjectIdentifier(device_id),
                    ObjectIdentifier(object_id),
                    update_mode,
                )
            )
    except (KeyError, TypeError, ValueError) as err:
        diagnostic_counters["managed_target_rejections"] += 1
        LOGGER.warning(f"Invalid managed target payload: {err}")
        return {"accepted": False, "error": "invalid_targets", "targets": 0}

    return await application.replace_managed_targets(targets)


@app.get("/apiv1/command/whois", status_code=status.HTTP_200_OK, tags=["apiv1"])
async def whois_command():
    """Send a Who Is Request over the BACnet network."""
    response = await who_is_func()

    if response:
        return status.HTTP_200_OK
    return status.HTTP_400_BAD_REQUEST


@app.get("/apiv1/command/iam", tags=["apiv1"])
async def iam_command():
    """Send an I Am Request over the BACnet network."""

    response = i_am_func()

    return status.HTTP_200_OK


@app.get("/apiv1/command/readall", tags=["apiv1"])
async def read_all_command():
    """Send a Read Request to all devices on the BACnet network."""
    events.read_event.set()
    return status.HTTP_200_OK


@app.get("/apiv1/commissioning/ede", tags=["apiv1"])
async def read_ede_files():
    """Read currently uploaded EDE files."""
    return EDE_files


@app.post("/apiv1/commissioning/ede", status_code=status.HTTP_200_OK, tags=["apiv1"])
async def upload_ede_files(
    response: Response, EDE: UploadFile | None, stateTexts: UploadFile | None = None
):
    """Upload EDE files to show up as placeholder in the object lists."""

    object_keys = ObjectTypesSupported
    bacnet_units = EngineeringUnits
    deviceDict = {}
    liststart = False
    stateTextsList = []
    statecounter = 0

    if stateTexts:
        csvStateText = csv.reader(
            codecs.iterdecode(stateTexts.file, "utf-8"), delimiter=";"
        )
        for row in csvStateText:
            if statecounter >= 2:
                row.pop(0)
                stateTextsList.append(row)
            statecounter += 1

    csvEDE = csv.reader(codecs.iterdecode(EDE.file, "utf-8"), delimiter=";")

    for row in csvEDE:
        if liststart:
            dev_instance = row[1]
            obj_name = row[2]
            obj_type = ObjectType(row[3])

            obj_instance = row[4]
            desc = row[5]

            if "binary" in str(obj_type):
                present_value = choice(["active", "inactive"])
            else:
                present_value = randint(0, 4)

            try:
                state_text = row[13]
            except:
                state_text = None

            try:
                unit = EngineeringUnits(row[14])
            except:
                unit = None

            obj_dict = {}
            obj_dict = {
                "objectIdentifier": [obj_type.attr, obj_instance],
                "objectType": obj_type.attr,
                "objectName": obj_name,
                "description": desc,
            }

            if stateTextsList and "binary" in str(obj_type.attr):
                obj_dict["inactiveText"] = stateTextsList[int(state_text)][0]
                obj_dict["activeText"] = stateTextsList[int(state_text)][1]
            elif stateTextsList and state_text:
                obj_dict["stateText"] = stateTextsList[int(state_text) - 1]
                obj_dict["numberOfStates"] = len(stateTextsList[int(state_text) - 1])

            if unit:
                obj_dict["units"] = unit.attr

            if obj_type == ObjectType("device"):
                obj_dict["modelName"] = "EDE File"
                obj_dict["vendorName"] = "Engelsoft BACstac"
                obj_dict["description"] = "Placeholder"
            else:
                obj_dict["presentValue"] = present_value

            deviceDict = deep_update(
                deviceDict,
                {
                    f"device:{dev_instance}": {
                        f"{obj_type.attr}:{obj_instance}": obj_dict
                    }
                },
            )

        if row[0] == "# keyname":
            liststart = True

    if list(deviceDict)[0] in list(bacnet_device_dict):
        LOGGER.warning("Device ID already in use.")
        response.status_code = status.HTTP_409_CONFLICT
        return "This device already exists as a device in the BACnet/IP network"

    for file in EDE_files:
        if file.keys() in deviceDict.keys():
            LOGGER.warning("EDE already loaded.")
            response.status_code = status.HTTP_409_CONFLICT
            return "This device already exists as EDE file"

    EDE_files.append(deviceDict)

    return deviceDict


@app.delete("/apiv1/commissioning/ede", tags=["apiv1"])
async def delete_ede_file(device_ids: Annotated[list[str] | None, Query()] = None):
    """Delete EDE files to stop letting them show up in API calls."""
    LOGGER.debug(f"EDE Files loaded: {len(EDE_files)}")
    EDE_files[:] = [
        dictionary
        for dictionary in EDE_files
        if all(device not in dictionary for device in device_ids)
    ]
    LOGGER.debug(f"EDE Files loaded: {len(EDE_files)}")
    return True


@app.get("/apiv1/diagnostics/logs", tags=["apiv1"])
async def download_logs():
    """Download add-on logs."""
    global log_path
    if log_path:
        dupe_path = shutil.copyfile(
            log_path, log_path.replace("share", "usr/bin") + "2"
        )
        return FileResponse(
            path=dupe_path,
            media_type="application/octet-stream",
            filename="bacnet_addon_logs.txt",
        )
    else:
        return status.HTTP_404_NOT_FOUND


# Any commands or not variable paths should go above here... FastAPI will use it as a variable if you make a new path below this.


@app.get("/apiv1/{deviceid}", tags=["apiv1"])
async def read_deviceid_dict(deviceid: str):
    """Read a device."""
    global bacnet_device_dict
    var = bacnet_device_dict
    try:
        return var[deviceid]
    except Exception as e:
        return "Error: " + str(e)


@app.get("/apiv1/{deviceid}/{objectid}", tags=["apiv1"])
async def read_objectid_dict(deviceid: str, objectid: str):
    """Read an object from a device."""
    try:
        global bacnet_device_dict
        var = bacnet_device_dict
        for key in var[deviceid].keys():
            if key.lower() == objectid:
                objectid = key
        return var[deviceid][objectid]
    except Exception as e:
        return "Error: " + str(e)


@app.get("/apiv1/{deviceid}/{objectid}/{propertyid}", tags=["apiv1"])
async def read_objectid_property(deviceid: str, objectid: str, propertyid: str):
    """Read a property of an object from a device."""
    global bacnet_device_dict
    var = bacnet_device_dict
    try:
        return var[deviceid][objectid][propertyid]
    except Exception as e:
        return "Error: " + str(e)


@app.post("/apiv1/{deviceid}/{objectid}", tags=["apiv1"])
async def write_property(
    deviceid: str = Path(description="device:instance"),
    objectid: str = Path(description="object:instance"),
    objectName: Union[str, None] = None,
    description: Union[str, None] = None,
    presentValue: Union[int, float, str, None] = None,
    outOfService: Union[bool, None] = None,
    covIncrement: Union[int, float, None] = None,
):
    """Write to a property of an object from a device."""
    property_dict: dict[dict, Any] = {}
    global writeQueue

    try:
        if objectName != None:
            property_dict.update({"objectName": objectName})
        if description != None:
            property_dict.update({"description": description})
        if presentValue != None:
            property_dict.update({"presentValue": presentValue})
        if outOfService != None:
            property_dict.update({"outOfService": outOfService})
        if covIncrement != None:
            property_dict.update({"covIncrement": covIncrement})

        if property_dict:
            for key, val in property_dict.items():
                await events.write_queue.put(
                    [
                        ObjectIdentifier(deviceid),
                        ObjectIdentifier(objectid),
                        PropertyIdentifier(key),
                        val,
                        None,
                        None,
                    ]
                )
        else:
            write_req = (
                ObjectIdentifier(deviceid),
                ObjectIdentifier(objectid),
                PropertyIdentifier("presentValue"),
                None,
                None,
                None,
            )
            await events.write_queue.put(write_req)

        LOGGER.info("Successfully put in Write Queue")
        return status.HTTP_200_OK

    except Exception as err:
        LOGGER.warning(f"Failed write request: {err}")
        return status.HTTP_400_BAD_REQUEST


@app.post("/apiv1/subscribe/{deviceid}/{objectid}", tags=["apiv1"])
async def subscribe_objectid(
    deviceid: str, objectid: str, confirmationType: str, lifetime: int | None = None
):
    """Subscribe to an object of a device."""
    try:
        diagnostic_counters["api_subscribe_requests"] += 1
        deviceid = ObjectIdentifier(deviceid)
        objectid = ObjectIdentifier(objectid)
        if confirmationType.lower() in ("confirmed", "true"):
            notifications = True
        elif confirmationType.lower() in ("unconfirmed", "false"):
            notifications = False
        else:
            return status.HTTP_400_BAD_REQUEST

        sub_tuple = (
            deviceid,
            objectid,
            notifications,
            lifetime,
        )

        await events.sub_queue.put(sub_tuple)
        return {"accepted": True, "queued": True}

    except Exception as err:
        LOGGER.error(f"{err} on subscribe from API POST request")
        return status.HTTP_400_BAD_REQUEST


@app.delete("/apiv1/subscribe/{deviceid}/{objectid}", tags=["apiv1"])
async def unsubscribe_objectid(deviceid: str, objectid: str):
    """Subscribe to an object of a device."""
    try:
        diagnostic_counters["api_unsubscribe_requests"] += 1
        LOGGER.debug(f"{deviceid}, {objectid}")
        deviceid = ObjectIdentifier(deviceid)
        objectid = ObjectIdentifier(objectid)

        sub_tuple = (
            deviceid,
            objectid,
        )

        await events.unsub_queue.put(sub_tuple)
        return {"accepted": True, "queued": True}

    except Exception as err:
        LOGGER.error(f"{err} on subscribe from API DELETE request")
        return status.HTTP_400_BAD_REQUEST


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """This function will be called whenever a new client connects to the server."""
    await websocket.accept()

    LOGGER.debug(f"Accepted websocket: {websocket.url}")

    activeSockets.append(websocket)
    data_to_send = jsonable_encoder(websocket_snapshot())
    if is_valid_json(data_to_send):
        await websocket.send_json(data_to_send)
        diagnostic_counters["websocket_initial_snapshots"] += 1

    global websocket_broadcast_task
    if websocket_broadcast_task is None or websocket_broadcast_task.done():
        websocket_broadcast_task = asyncio.create_task(
            websocket_writer(), name="websocket-broadcaster"
        )

    while True:
        try:
            data = await websocket.receive()
            LOGGER.debug(f"Data received: {data}")
            if data["type"] == "websocket.disconnect":
                raise WebSocketDisconnect

            if data["type"] == "websocket.receive" and "device:" in data["text"]:
                message = data["text"]
                try:
                    message = json.loads(message)
                except Exception as err:
                    LOGGER.warning(
                        f"message: {message} is not processed as it's not valid JSON {err}"
                    )
                    LOGGER.warning(
                        'Do it as the following example: {"device:100":{"analogInput:1":{"presentValue":1}}}'
                    )
                    continue
                if isinstance(message, dict):
                    device_identifier = next(iter(message.keys()))
                    object_identifier = next(iter(message[device_identifier].keys()))
                    property_identifier = next(
                        iter(message[device_identifier][object_identifier].keys())
                    )
                    value = message[device_identifier][object_identifier][
                        property_identifier
                    ]

                    if not isinstance(device_identifier, ObjectIdentifier):
                        device_identifier = ObjectIdentifier(device_identifier)
                    if not isinstance(object_identifier, ObjectIdentifier):
                        object_identifier = ObjectIdentifier(object_identifier)
                    if not isinstance(property_identifier, PropertyIdentifier):
                        property_identifier = PropertyIdentifier(property_identifier)

                    await events.write_queue.put(
                        [
                            device_identifier,
                            object_identifier,
                            property_identifier,
                            value,
                            None,
                            None,
                        ]
                    )

                else:
                    LOGGER.warning(f"message: {message} is not processed")

        except (RuntimeError, asyncio.CancelledError) as err:
            if websocket in activeSockets:
                activeSockets.remove(websocket)
            LOGGER.error(f"Disconnected with Exception... {err}")
            return
        except WebSocketDisconnect as err:
            if websocket in activeSockets:
                activeSockets.remove(websocket)
            LOGGER.info(f"Disconnected websocket: {err}")
            return
        except Exception as err:
            if websocket in activeSockets:
                activeSockets.remove(websocket)
            LOGGER.error(f"Disconnected with Exception {err}")
            return


def _v2_result(request_id: Any, payload: Any = None, *, error: dict | None = None) -> dict:
    message = {"type": "result", "id": request_id, "success": error is None}
    if error is None:
        message["payload"] = payload
    else:
        message["error"] = error
    return message


async def _v2_set_targets(payload: dict) -> dict:
    """Apply managed targets sent over protocol V2."""
    application = bacnet_application
    if application is None:
        raise RuntimeError("BACnet application is still starting")
    targets = []
    for target in payload.get("targets", []):
        device_id = str(target["device_id"])
        object_id = str(target["object_id"])
        mode = str(target.get("update_mode", target.get("mode", "polling"))).lower()
        mode = {"push": "cov", "subscribe": "cov", "poll": "polling", "off": "disabled"}.get(mode, mode)
        if mode not in {"cov", "polling", "disabled"}:
            raise ValueError(f"unsupported update mode: {mode}")
        if ":" not in device_id and "," not in device_id:
            device_id = f"device:{device_id}"
        targets.append((ObjectIdentifier(device_id), ObjectIdentifier(object_id), mode))
    return await application.replace_managed_targets(targets)


async def _v2_write(payload: dict) -> dict:
    """Queue one BACnet property write sent over protocol V2."""
    device_id = str(payload["device_id"])
    if ":" not in device_id and "," not in device_id:
        device_id = f"device:{device_id}"
    await events.write_queue.put([
        ObjectIdentifier(device_id),
        ObjectIdentifier(str(payload["object_id"])),
        PropertyIdentifier(str(payload.get("property", "presentValue"))),
        payload.get("value"),
        payload.get("array_index"),
        payload.get("priority"),
    ])
    return {"accepted": True, "queued": True}


@app.websocket("/ws/v2")
async def websocket_v2(websocket: WebSocket):
    """Bidirectional, versioned integration channel."""
    global websocket_broadcast_task
    await websocket.accept()
    activeV2Sockets.append(websocket)
    diagnostic_counters["protocol_v2_connections"] += 1
    try:
        hello = await asyncio.wait_for(websocket.receive_json(), timeout=10)
        configured_token = _configured_api_token()
        if configured_token and hello.get("token") != configured_token:
            await websocket.send_json({"type": "error", "error": {"code": "authentication_failed", "message": "Invalid API token"}})
            await websocket.close(code=1008)
            return
        offered_versions = hello.get("protocol_versions")
        if not isinstance(offered_versions, list):
            offered_versions = [hello.get("protocol_version")]
        if hello.get("type") != "hello" or PROTOCOL_VERSION not in offered_versions:
            await websocket.send_json({"type": "error", "error": {"code": "protocol_incompatible", "message": "Protocol V2 required"}})
            await websocket.close(code=1002)
            return
        await websocket.send_json({"type": "welcome", **protocol_info()})
        await websocket.send_json({"type": "event", "event": "snapshot", "sequence": protocol_sequence, "payload": jsonable_encoder(websocket_snapshot())})

        if websocket_broadcast_task is None or websocket_broadcast_task.done():
            websocket_broadcast_task = asyncio.create_task(websocket_writer(), name="websocket-broadcaster")

        while True:
            message = await websocket.receive_json()
            if message.get("type") != "command":
                continue
            diagnostic_counters["protocol_v2_commands"] += 1
            request_id = message.get("id")
            command = message.get("command")
            payload = message.get("payload") or {}
            try:
                if command in {"get_inventory", "resync"}:
                    result = websocket_snapshot()
                elif command == "set_targets":
                    result = await _v2_set_targets(payload)
                elif command in {"write_property", "release_priority"}:
                    if command == "release_priority":
                        payload = {**payload, "property": "presentValue", "value": None}
                    result = await _v2_write(payload)
                elif command == "get_diagnostics":
                    result = await get_subscription_diagnostics()
                else:
                    raise ValueError(f"unsupported command: {command}")
                await websocket.send_json(_v2_result(request_id, jsonable_encoder(result)))
            except Exception as err:
                diagnostic_counters["protocol_v2_errors"] += 1
                await websocket.send_json(_v2_result(request_id, error={"code": "command_failed", "message": str(err)}))
    except (WebSocketDisconnect, asyncio.CancelledError, asyncio.TimeoutError):
        pass
    finally:
        if websocket in activeV2Sockets:
            activeV2Sockets.remove(websocket)


async def websocket_writer():
    """Broadcast updates once to every connected WebSocket client."""
    try:
        while True:
            if events.val_updated_event.is_set():
                # Clear before consuming/sending so an update arriving during the
                # send sets the event again instead of being cleared afterwards.
                events.val_updated_event.clear()
                application = bacnet_application
                managed_delta = application is not None
                if managed_delta:
                    dict_to_send = application.consume_managed_delta()
                else:
                    dict_to_send = websocket_snapshot()
                if not dict_to_send:
                    continue
                data_to_send = jsonable_encoder(dict_to_send)
                if not is_valid_json(data_to_send):
                    LOGGER.warning(f"Websocket dict isn't converted to JSON!")
                    continue
                for socket in list(activeSockets):
                    try:
                        await socket.send_json(data_to_send)
                        diagnostic_counters["websocket_update_snapshots"] += 1
                        if managed_delta:
                            diagnostic_counters["websocket_delta_messages"] += 1
                            diagnostic_counters["websocket_delta_objects"] += sum(
                                len(objects) for objects in dict_to_send.values()
                            )
                            diagnostic_counters["websocket_delta_properties"] += sum(
                                len(properties)
                                for objects in dict_to_send.values()
                                for properties in objects.values()
                            )
                    except Exception as err:
                        if socket in activeSockets:
                            activeSockets.remove(socket)
                        LOGGER.debug(f"Removed disconnected WebSocket: {err}")
                global protocol_sequence
                protocol_sequence += 1
                v2_message = {
                    "type": "event",
                    "event": "point_changes",
                    "sequence": protocol_sequence,
                    "payload": data_to_send,
                }
                for socket in list(activeV2Sockets):
                    try:
                        await socket.send_json(v2_message)
                    except Exception as err:
                        if socket in activeV2Sockets:
                            activeV2Sockets.remove(socket)
                        LOGGER.debug(f"Removed disconnected V2 WebSocket: {err}")
            else:
                await asyncio.sleep(1)

    except asyncio.CancelledError as err:
        LOGGER.debug(f"Websocket writer cancelled: {err}")

    except Exception as err:
        LOGGER.error(f"Error during writing: {err}")


@app.post("/apiv2/{deviceid}/{objectid}/{property}", tags=["apiv2"])
async def write_property(
    deviceid: str = Path(description="device:instance"),
    objectid: str = Path(description="object:instance"),
    property: str = Path(description="property, for example presentValue"),
    value: str | int | float | bool | None = Query(
        default=None, description="Property value"
    ),
    array_index: int | None = Query(
        default=None, description="Array index, usually left empty"
    ),
    priority: int | None = Query(default=None, description="Write priority"),
):
    """Write to a property of an object from a device."""
    property_dict: dict[dict, Any] = {}
    dict_to_write: dict[dict, Any] = {}

    def is_bool(input_val) -> bool:
        if isinstance(input_val, bool):
            return True
        if isinstance(input_val, str):
            return input_val.lower() in ("true", "false")
        return False

    try:
        deviceid = ObjectIdentifier(deviceid)
        objectid = ObjectIdentifier(objectid)
        property = PropertyIdentifier(property)

        if is_bool(value):
            value = parse_obj_as(bool, value)

    except Exception as err:
        LOGGER.error(f"Error while trying to make a write request: {err}")
        return status.HTTP_400_BAD_REQUEST

    LOGGER.error(f"{deviceid}, {objectid}, {property}, {value}, {priority}")

    await events.write_queue.put(
        [deviceid, objectid, property, value, array_index, priority]
    )
