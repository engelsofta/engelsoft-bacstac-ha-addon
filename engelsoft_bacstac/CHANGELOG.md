﻿<!-- https://developers.home-assistant.io/docs/add-ons/presentation#keeping-a-changelog -->

<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->

# 1.2.5
03/08/2026

## Fixed
- Made the COV confirmation counter use every COV target requested by the integration as its total from the beginning, instead of growing the total alongside the throttled subscription build.

# 1.2.4
03/08/2026

## Improved
- Added a live `confirmed COV / active COV` counter based on successful BACnet subscription acknowledgements to the target-status header.
- Added a visible selection counter and disabled the manual COV removal action until at least one active subscription is selected.
- Kept confirmed COV subscriptions active when no initial notification arrives and added control polling that falls back permanently only after a polled value changes without a matching COV notification.

# 1.2.3
03/08/2026

## Fixed
- Prevented the update-control summary from overflowing behind the target and action panels.
- Kept navigation and mode summary on one clean row on wide screens and added controlled wrapping with automatic row height on narrower layouts.
- Prevented repeated identical integration target lists from restarting an in-progress throttled COV build, which could leave later targets waiting indefinitely.

## Improved
- Merged the separate active-COV task list into the main target status table.
- Added clear COV-active and Confirmed/Unconfirmed indicators plus in-row selection for manual removal.
- Made every target table column sortable with natural object ordering and numeric age sorting.
- Added automatic target-status updates while the page is open, preserving the selected filter, sort order and checked COV tasks.

# 1.2.2
03/08/2026

## Fixed
- Busted the Home Assistant Ingress stylesheet cache so the target status page no longer falls back to an outdated unstyled layout.

## Improved
- Redesigned the large target status list with search, transport filters, visible result count, status badges, sticky headers and a bounded scrolling area.
- Hid disabled targets from the default view and replaced internal state names with readable German labels.
- Improved responsive behavior for the target toolbar on narrow screens.

# 1.2.1
03/08/2026

## Fixed
- Replaced one WebSocket writer per client with a single safe broadcaster, preventing duplicate and concurrent sends when the WebUI and integration are connected together.
- Grouped COV polling fallbacks into one polling worker per BACnet device instead of creating one infinite task per object.
- Made legacy subscribe and unsubscribe API calls return an immediate explicit acknowledgement and reflected them in integration-controlled diagnostics.
- Reduced repeated per-object COV-limit fallback messages to debug level after the first device warning.

# 1.2.0
03/08/2026

## Security and reliability
- Added an integration-controlled hybrid mode that accepts COV, polling or disabled per target while retaining all BACnet safety limits.
- Added a prominent WebUI status strip showing the active control mode and COV, polling, fallback and disabled target counts.
- Changed the fresh-install default from legacy subscriptions to managed polling.
- Changed the legacy default COV list from `all` to an empty list.
- Added a configurable per-device COV limit, defaulting to 20; excess targets automatically use polling.
- Added configurable pacing between COV subscription requests.
- Added automatic polling fallback when a COV request fails or a confirmed subscription delivers no value.
- Downgraded harmless duplicate subscription requests from error to debug logging.
- Added per-target diagnostics for subscription confirmation, last COV update, last poll and current value age.

# 1.1.0
02/08/2026

## Added
- Added a polished light theme while preserving the existing Engelsoft dark theme.
- Added automatic theme synchronization with Home Assistant Ingress and a browser color-scheme fallback.

# 1.0.2
02/08/2026

## Fixed
- Restored the WebSocket runtime required by the WebUI and Engelsoft Beacon BACnet/IP integration.
- Adjusted the nginx worker connection count to the container's open-file limit to avoid a misleading startup warning.

# 1.0.1
02/08/2026

## Fixed
- Restored executable permissions for all s6 service entry points so the add-on can start correctly.
- Added a container-build safeguard that enforces the required executable permissions on every supported platform.

# 1.0.0
01/08/2026

## Changed
- Established Engelsoft BACstac as an independently maintained Home Assistant app.
- Redesigned the WebUI with the Engelsoft anthracite and gold visual style.
- Updated the header, navigation, panels, forms and device browser across all WebUI pages.
- Improved the responsive layout for tablets and mobile devices.
- Focused published architecture support on amd64 and aarch64, matching the current Home Assistant BuildKit workflow.
- Added complete German translations and documented the update modes used with Engelsoft Beacon BACnet/IP in all supported languages.

## Maintenance
- Removed generated Python bytecode, Visual Studio workspace data and an unused legacy WebUI image.
- Migrated the container definition away from the deprecated build.yaml workflow to an explicit multi-platform base image.
- Removed obsolete WebUI JavaScript left behind by earlier navigation and device-list implementations.
- Preserved compatibility for the public vendorID and maxApduLenghtAccepted configuration keys.
- Removed the unused read-write mount of the complete Home Assistant configuration directory.
- Corrected the foreignTTL and segmentation option schemas.
- Removed the legacy Home Assistant entity-to-BACnet object exporter, its configuration, background tasks, dependencies and Home Assistant Core API permission. Entity creation in Home Assistant is handled by Engelsoft Beacon BACnet/IP.

## Attribution
- Derived from the Bepacom BACnet/IP add-on under the Apache License 2.0.

---

The entries below document the inherited upstream history before the Engelsoft 1.0.0 release.

# 1.5.1-diagnostics.19
19/07/2026

## Fixed
- Explicitly set the Home Assistant Ingress sidebar title to Engelsoft BACstac.

# 1.5.1-diagnostics.18
19/07/2026

## Changed
- Removed the legacy I Am, Who Is and Read All Devices action panel from the WebUI.
- Expanded the main content area while retaining the command API endpoints for diagnostics.

# 1.5.1-diagnostics.17
19/07/2026

## Changed
- Simplified the WebUI navigation by removing the Swagger, Redoc, About, log download and add-on page links.

# 1.5.1-diagnostics.16
19/07/2026

## Fixed
- Added explicit WebUI stylesheet cache busting so Home Assistant Ingress cannot retain the legacy red and white design after an update.

# 1.5.1-diagnostics.15
19/07/2026

## Changed
- Redesigned the complete add-on WebUI to match the Engelsoft Home Assistant integration.
- Added a compact dark dashboard layout, card-based controls and responsive mobile views.
- Improved navigation, forms, device browsing, subscription rows and EDE file selection.

# 1.5.1-diagnostics.14
19/07/2026

## Changed
- Replaced the Supervisor icon, repository logo and WebUI branding image with the Engelsoft BACstac artwork.
- The WebUI branding image is now bundled locally instead of being loaded from an external website.

# 1.5.1-diagnostics.13
19/07/2026

## Changed
- Renamed the add-on and its visible interface branding to Engelsoft BACstac.

# 1.5.1-diagnostics.12
19/07/2026

## Fixed
- Cache candidates are now always evaluated by the strict per-object completeness check, even if an individual BACnet read reported a failure.
- Inventory cache diagnostics now include the attempted candidate size, missing-object count, examples and the last rejection reason.

# 1.5.1-diagnostics.11
19/07/2026

## Added
- Added a versioned SQLite inventory cache with checksum and age validation.
- Cached BACnet inventory is available immediately after an add-on restart.
- Cache replacement requires a complete fresh discovery of every listed object.
- Inventory decreases larger than two objects require three identical complete discoveries before replacing the known-good cache.
- Cache diagnostics are exposed through the existing subscription diagnostics endpoint.

# 1.5.1-diagnostics.10
19/07/2026

## Changed
- Initial BACnet object discovery now uses a conservative maximum of three concurrent read requests.
- Object-list array reads and the single-property discovery fallback use the same concurrency limit.
- Managed COV targets, delta WebSocket updates and diagnostics remain unchanged.

# 1.5.1
07/09/2024

## Fixed
- Fixed monitoring of CoV subscriptions failing due to loss of connection. CoV tasks will now get removed after trying to resub without response when the CoV lifetime has passed.
- If address changed since last I Am request, it'll get updated internally now.

## Added
- Added resubscribing CoV to an object after the subscription had been timed out due to no response. [#52](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/52)
- `resub_on_iam` and `reread_on_iam` options under `devices_setup` in the add-on configuration. [#57](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/57)

## Dependencies
- ⬆️ Bumped base-python image to version v14.0.1.


# 1.5.0
13/08/2024

## Added
- Reading resolution property now. Integration will use it once it's updated as well. [#46](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/46)
- Added devices_setup configuration option to allow the user to configure behaviour. See Documentation for usage. [#43](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/discussions/43)
- Updated DOCS.md
- Added units for entity to BACnet translation. [#47](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/47)\
- Added array index to apiv2 writes.

## Fixed
- If an entity has units that can't be translated, it'll result in the noUnit property value. [#47](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/47)
- Fixed infinite loop causing BACpypes3 to get stuck when sending too many subscribe requests.(since v1.4.1b4)
- Fixed sending error reply too soon when receiving values before receiving confirmation of subscription. (since v1.4.1b4)
- Fixed certain exceptions getting exceptions.
- Now detecting predictable interface names using auto detection of IP address. [#66](https://github.com/Bepacom-Raalte/bepacom-HA-Addons/issues/66)
- Fixed an issue where OctetString would cause the API to fail.

## Changed
- Subscribing to properties now creates tasks that should maintain CoV subscription.
- Setting up of the python program now solely relies on options.json.

## Dependencies
- ⬆️ Bumped base-python image to version v14.0.0.
- ⬆️ Bumped bacpypes3 to version v0.0.98.
- ⬆️ Bumped pydantic to version v1.10.17.
- ⬆️ Bumped jinja2 to version v3.1.4.
- ⬆️ Bumped uvicorn to version v0.30.1.
- ⬆️ Bumped requests to version 2.32.3.


# 1.4.0
27/03/2024

## Added
- Logs are exportable through the web UI, with a max size of 15MB.
- Logging formatting improved with timestamps.

## Fixed
- Fixed read results being interpreted as a falsy value and thus being discarded.
- Fixed handling of no replies to reading device properties.
- Infinite or NaN properties now get ignored instead of set to 0.
- Handling I Am requests one by one now.
- Prevent basically infinite loop of reading objects.
- Prevent reading of properties not belonging to object when reading one by one.
- Filtering out ReadAccessResult value type.
- JSON check before sending through websocket.

## Dependencies

- ⬆️ Bumped python-multipart to version 0.0.9.
- ⬆️ Bumped Uvicorn to version 0.27.1.


# 1.3.3
22/02/2024

## Fixed

- Fixed handling for devices that don't support ReadMultipleServices. [#14](https://github.com/Bepacom-Raalte/Bepacom-BACnet-IP-Integration/issues/14)
- Reading will now look at protocolServicesSupported. 
- Made configuration sequence more universal. This is irrelevant for users, but great for debugging.

## Dependencies

- ⬆️ Bumped base-python image to version v13.1.2.


# 1.3.2
01/02/2024

_You can add our integration repository now on HACS as custom repository!_

## Added

- serialNumber device property now gets read from device.

## Fixed

- Fixed apiv1 not doing anything with an empty presentValue.
- Fixed write error not being caught causing the writer task to fail.

## Changed

- Port 80 now disabled by default. Can be turned on if you want to use a custom port.
- Update interval default value changed to 600.

## Dependencies

- ⬆️ Bumped base-python image to version v13.1.0.
- ⬆️ Bumped FastAPI to version 0.108.0.
- ⬆️ Bumped python-multipart to version 0.0.7.
- ⬆️ Bumped Jinja2 to version 3.1.3.
- ⬆️ Bumped Uvicorn to version 0.27.0.


# 1.3.1
29/01/2024

## Added

- Add-on port for the integration can now be changed. _Please update your integration with the latest version (0.1.0) from GitHub!_

## Changed

- Apiv2 write now allows for empty value. Can be used as a release when writing with priorities.
- Web UI page now uses apiv2 for writing. This allows for sending with priorities.
- Based on whether an entity has units when it's unavailable, the add-on will turn the entity into an analog or character object.

## Dependencies

- ⬆️ Bumped base-python image to version v13.0.1.


# 1.3.0
09/01/2024

Happy new year everyone!

## Added

- Certain entity types can now become BACnet objects!
- Using Home Assistant API to fetch data from entities.
- "No segmentation supported" way for reading object list added.
- maxApduLenghtAccepted and maxSegmentsAccepted back in configuration as unused options.
- Added name and description to the Subscriptions configuration option. 
- WebUI components like .css should now be available when served through https.

## Fixed

- Fixed defaultPriority not being sent by default.
- Fixed update event for websocket not getting set.
- Fixed handling of uncalled for I Am requests. These will now also be cached.
- Forced ForeignTTL to be integer.

## Dependencies

- ⬆️ Bumped base-python image to version v13.0.0.
- ⬆️ Bumped FastAPI to version 0.108.0.
- ⬆️ Bumped Uvicorn to version 0.25.0.


# 1.2.0
9/12/2023

- Foreign device mode is working. Use the Foreign BBMD Address in the configuration.
- Added configurable subscriptions in the add-on configuration!
- Changed init-nginx service to not use ifconfig.
- ⬆️ Bumped base-python image to version v12.0.2.
- ⬆️ Bumped BACpypes3 to version 0.0.86.
- ⬆️ Bumped FastAPI to version 0.104.1.
- ⬆️ Bumped Uvicorn to version 0.24.0.
- ⬆️ Bumped Websockets to version 12.0.


# 1.1.3
15/9/2023

- Fixed Float value not getting handled correctly when parsing JSON.
- Removed legacy Home Assistant discovery.
- ⬆️ Bumped base-python image to version v11.0.5.
- ⬆️ Bumped BACpypes3 to version 0.0.79.


# 1.1.2
9/8/2023

- Fixed getting rejection PDU stopping subscribing process.
- ⬆️ Bumped base-python image to version v11.0.4.
- ⬆️ Bumped FastAPI to version 0.101.0.
- ⬆️ Bumped Uvicorn to version 0.23.2.


# 1.1.1
7/8/2023
- Subscriptions no longer indefinite as some devices don't support it.
- Subscriptions can be deleted through the UI.
- Subscriptions get renewed automatically.


# 1.1.0

7/8/2023
- NGINX now waits until the API is available before starting.
- Copied CoV method of legacy version. This will stop the system from being overwhelmed and hanging.
- NGINX using templates to dynamically add own IP.


# 1.0.6

10/7/2023
- Configuration options are now dropdown menu's, reducing configuration page clutter.
- Fixed segmentation issue, segmentation now gets passed down to requests.
- Removed the "fall back" functionality where the add-on reads every object of the object list seperately.
- Punched a hole in NGINX to allow the device's own IP to communicate with the API.


# 1.0.5

10/7/2023
- segmentation-not-supported error while reading objectlist solved.
- Allowing more internal Home Assistant IP's.


# 1.0.4

10/7/2023
- Base image to hassio-addons/addon-base-python image.
- Library versions are more closely guarded now.
- Added segmentation option back in.
- Trying to log abort PDU's. Issue with Priva devices not supporting segmentation.
- Reading objectList last to get most info from the device without getting an error.


# 1.0.3

29/6/2023
- EDE files give out correct data through API now.
- Increased sleeping time during startup to give the add-on enough chance to catch all BACnet data.


# 1.0.2

28/6/2023
- Fixed an issue where empty websockets would remain in memory.
- CoV is now indefinite, because of lack of lifetime. Siemens PXC4 doesn't work with lifetime = 0.
- Removed excessive logging.


# 1.0.1

20/6/2023
- Updated web UI main page to make navigation a little easier.
- Unsubscribing now gets done when the add-on closes.
- All errors now really should be caught instead of dumping tracelogs.
- Updated translations.
- EDE files show up on the web UI now once uploaded.


# 1.0.0

16/06/2023
- Rewrote the backbones of the program. Now using BACpypes3 instead of BACpypes.
- Removed certain configuration options that have no effect.
- New API points!
- Subscription page on the web UI now functions like the EDE page where you can add or remove subscriptions easily.
- CIDR notation gets discovered when using "auto" as ip address setting.
- Can configure the rate at which all objects get updated.
- Catching more errors so the logs don't get spammed with trace logs.
- This update _may_ break a thing or two. Please make an Issue on GitHub to get it solved.


## 0.2.1

01/06/2023
- Rounding of long float values. It's now rounding at the first decimal.
- LAN IP detection still works automatically, and only shuts down if it's automatic in config. If it's not auto, you can manually write an IP and not shut down.
- Add-on uses image from GitHub now, decreasing install time.
- fixed presentvalue not doing anything for EDE files


## 0.2.0

01/06/2023
- Added commissioning API points!
- Now it's possible to load EDE files in the add-on.
- This allows the integration generate placeholder entities in Home Assistant until the real device gets connected to the network.
- EDE files that have been loaded can be deleted.
- A restart of the add-on will remove the EDE files from the add-on.
- Web UI pages allow easy adding and removing.


## 0.1.6

30/05/2023
- Bumped Alpine base image to 3.18.
- Python version is now 3.11.
- Packages on GitHub renamed to bacnet-interface instead of null.


## 0.1.5

11/05/2023
- Updated web UI page to include Redoc API documentation.
- Viewing API documentation works now.
- API documentation now uses ingress.
- Made loglevel a mandatory configuration.


## 0.1.4

09/05/2023
- Updated configuration to include Write Request Priority.
- Updated DOCS to reflect the change.
- We appreciate the feedback!!


## 0.1.3

12/4/2023
- Readme updated to include integration.
- NGINX now blocks everything from outside.
- Trying to automatically get the ethernet adapter from the host device.
- FastAPI to include lifetime now instead of on_startup().


## 0.1.2

16/02/2023
- Dutch translations added.
- Log level can be adjusted. Defaults to WARNING now.
- Read request every 60 seconds asking for values that can change, instead of asking for static values. This reduces network traffic.
- WebUI has tooltips now. Buttons or fields should explain what they do.


## 0.1.1

15/02/2023
- Bumped up FastAPI to version 0.92.0 for security reasons.
- Restructured S6-overlay processes. One shots for initialisations, longruns for actual processes.
- Discovery enabled for if it's possible to discovery integration in the future.
- Added automatic ethernet adapter detection. Won't work in every case, but it'll help a lot of people out.
- BACnet subscriptions now have a lifetime instead of none. Increases compatability.
- BACnet subscriptions last maximum time and get resubscribed every 60 seconds along with a read request.
- Websockets can handle multiple clients now.
- Configuration of the add-on has been simplified.
- Added some API tests internally.
- API has an endpoint that let's you subscribe now.
- Flask no longer included, FastAPI handles everything now, along with uvicorn.
- WebUI gets updated over websocket. This means values are the same as in the API.
- WebUI can write now as well.
- WebUI has gotten a makeover in general.
- WebUI Subscription page can actually subscribe now.
- This add-on runs on Raspberry Pi 3 as it would on an Intel NUC. This means Raspberry Pi is supported.


# 0.1.0

10/1/2022
- API now has more datatypes
- objectIdentifier, statusFlags became list.
- notificationClass added as object as well as a property to access through API.
- Multi State stateText and numberOfStates have been added.
- Attempting to get min and max presentValue's from objects now.
- Altered webUI page to be a little functional. It has 3 buttons you can press to call a service like I Am or Who Is.
- Formatting of code now uses Black and Isort.
- Removed unused packages from Dockerfile: 'nmap' and 'iproute2'.
- Added a read all command, so all devices can be read again on command.
- Bumped version to '0.1.0' as the add-on ready to be used.


## 0.0.5

02/01/2023
- Added write functionality through API
- Added multiple API points. You can find them through going to /docs
- Who Is and I Am can be received and sent through host network. This is possible through Home Assistant Supervised
- Add-on is now matching requirements for this project. Error handling etc. will be improved later, as will code optimisations.


## 0.0.4

21/12/2022
- Zeroconf removed, not functional for add-on. If this was a core add-on, would be using DHCP.
- FastAPI running on a separate thread
- Created BACnetIOHandler class to serve as BACnet application
- BACnet devices will automatically be subscribed to
- FastAPI program converts the BACnet dictionary it gets from BACnetIOHandler to a bite sized dictionary containing only the essentials for Home Assistant
- API can do get request on /apiv1/json
- Can connect to websocket on ws://ip:port/ws
- Websocket will automatically push updates on Change Of Value
- Changed icon to Bepacom logo


## 0.0.3

07/11/2022
- Added FastAPI to function as API in the future
- Changed webserver to Uvicorn
- Changed program to split into multiple files
- BACnet device can be detected
- WebUI can be loaded, it's just an example page now
- API and web UI are split into different paths, /apiv1/ and /webapp/
- Zeroconf added, unsure if functioning


## 0.0.2

31/10/2022
- WhoIsIAmProgram Running
- Nginx set up to work correctly with Flask webserver
- Flask and BACpypes happily working together <3


## 0.0.1

 21/10/2022
- Getting started...
