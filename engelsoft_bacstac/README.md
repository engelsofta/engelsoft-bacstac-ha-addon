<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->

# Engelsoft BACstac

> **Companion required:** BACstac provides the BACnet/IP connection for
> [**Engelsoft Beacon BACnet/IP**](https://github.com/engelsofta/ha-bepacom-bacnet).
> Install the integration as well to create devices and entities in Home Assistant.

BACstac discovers BACnet/IP devices, reads their objects and values, manages COV
subscriptions and polling, and supplies the results to the companion integration
through a local connection.

New installations start with managed polling. Optional COV subscriptions are
limited per device and created at a controlled pace. Objects fall back to polling
if confirmed subscriptions stop delivering values.

## Highlights

- Automatic discovery of BACnet/IP devices and objects.
- Integration-controlled COV, polling and disabled targets, with COV limits and automatic polling fallback.
- Live target status: COV confirmation, latest notification, latest poll and value age.
- Validated inventory cache for restarts.
- BACnet reads and writes with configurable write priority.
- Normal BACnet/IP operation or foreign-device registration with a BBMD.
- Matching Engelsoft glass design, bundled backgrounds and automatic light/dark mode.
- Responsive icon navigation for Devices, Updates, EDE files and the companion BACnet Explorer.
- Device search, object details, device protection and runtime settings that apply without restarting.
- German and English Web UI; German, English and Dutch configuration descriptions.
- Prebuilt images for `amd64` and `aarch64`.

## Web UI

Open **Web UI** on the add-on page. Use **Devices** to inspect objects and device
protection, **Updates** for COV/polling status, and **EDE files** to manage imports.
The **Runtime** tab under Devices contains live update settings. The Explorer
icon opens the companion integration in Home Assistant.

The navigation appears on the left on desktop and above the content on narrow
screens. Background images are included in the add-on itself.

See the **Documentation** tab or [DOCS.md](DOCS.md) for connection options,
networking and configuration details.

## Support

Check the add-on log and update-target status before reporting an issue at
[GitHub Issues](https://github.com/engelsofta/engelsoft-bacstac-ha-addon/issues).

## License and origin

Engelsoft BACstac is a substantially modified continuation of the
[Bepacom BACnet/IP add-on](https://github.com/Bepacom-Raalte/bepacom-HA-Addons),
distributed under the Apache License 2.0. Original license and origin notices are
preserved in [LICENSE](../LICENSE) and [NOTICE](../NOTICE).
