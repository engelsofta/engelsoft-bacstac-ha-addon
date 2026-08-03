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

# ===================================================
# Global variables
# ===================================================

bacnet_device_dict: dict
bacnet_application: Application | None = None
activeSockets: list = []
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
    if (
        getattr(application, "subscription_mode", None)
        not in {"managed_cov", "integration_controlled"}
        or not getattr(application, "managed_targets", None)
    ):
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
    version="1.4.1",
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


def sidebar_status() -> dict:
    """Build the compact transport summary shown on every WebUI page."""
    application = bacnet_application
    mode = getattr(application, "subscription_mode", "starting")
    labels = {
        "integration_controlled": "Integrationsgesteuert",
        "managed_polling": "Verwaltetes Polling",
        "managed_cov": "COV bevorzugt",
        "legacy": "Legacy / manuell",
        "starting": "Wird gestartet",
    }
    statuses = getattr(application, "target_status", {}).values()
    return {
        "mode": mode,
        "label": labels.get(mode, mode),
        "targets": len(getattr(application, "managed_targets", [])),
        "cov": len(getattr(application, "managed_cov_task_names", [])),
        "polling": len(getattr(application, "managed_poll_targets", [])),
        "disabled": len(getattr(application, "managed_disabled_targets", [])),
        "fallback": sum(bool(item.get("fallback_active")) for item in statuses),
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
        },
    )


@app.get("/subscriptions", response_class=HTMLResponse, tags=["Webpages"])
async def subscriptions(request: Request):
    """Page to see subscription ID's."""
    subs_as_string: list = []
    global sub_list

    return templates.TemplateResponse(
        "subscriptions.html",
        {
            "request": request,
            "subs": sub_list,
            "sidebar": sidebar_status(),
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
        "subscription_mode": getattr(application, "subscription_mode", "starting"),
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

    except Exception as err:
        LOGGER.error(f"{err} on subscribe from API DELETE request")
        return status.HTTP_400_BAD_REQUEST


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """This function will be called whenever a new client connects to the server."""
    await websocket.accept()

    LOGGER.debug(f"Accepted websocket: {websocket.url}")

    # Start a task to write data to the websocket
    write_task = asyncio.create_task(websocket_writer(websocket))

    activeSockets.append(websocket)

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
            write_task.cancel()
            activeSockets.remove(websocket)
            LOGGER.error(f"Disconnected with Exception... {err}")
            return
        except WebSocketDisconnect as err:
            write_task.cancel()
            activeSockets.remove(websocket)
            LOGGER.info(f"Disconnected websocket: {err}")
            return
        except Exception as err:
            write_task.cancel()
            activeSockets.remove(websocket)
            LOGGER.error(f"Disconnected with Exception {err}")


async def websocket_writer(websocket: WebSocket):
    """Writer task for when a websocket is opened"""
    try:
        global bacnet_device_dict
        data_to_send = jsonable_encoder(websocket_snapshot())
        if not is_valid_json(data_to_send):
            LOGGER.warning(f"Websocket dict isn't converted to JSON!")
        else:
            await websocket.send_json(data_to_send)
            diagnostic_counters["websocket_initial_snapshots"] += 1
        LOGGER.debug("Passed send_json test")
        while True:
            if events.val_updated_event.is_set():
                # Clear before consuming/sending so an update arriving during the
                # send sets the event again instead of being cleared afterwards.
                events.val_updated_event.clear()
                application = bacnet_application
                managed_delta = (
                    getattr(application, "subscription_mode", None)
                    in {"managed_cov", "integration_controlled"}
                )
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
                for websocket in activeSockets:
                    await websocket.send_json(data_to_send)
                    diagnostic_counters["websocket_update_snapshots"] += 1
                    if managed_delta:
                        diagnostic_counters["websocket_delta_messages"] += 1
                        diagnostic_counters["websocket_delta_objects"] += sum(
                            len(objects) for objects in dict_to_send.values()
                        )
            else:
                await asyncio.sleep(1)

    except asyncio.CancelledError as err:
        LOGGER.debug(f"Websocket writer cancelled: {err}")

    except WebSocketDisconnect as err:
        LOGGER.info(f"Websocket disconnected: {err}")

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
