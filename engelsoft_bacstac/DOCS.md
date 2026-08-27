<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->
# Engelsoft BACstac

Engelsoft BACstac is intended to be a bridge between the BACnet/IP network and Home Assistant.

The goal of this add-on is to add BACnet functionality to Home Assistant so these devices can be displayed on the dashboard.

The add-on is not directly responsible for generating entities in Home Assistant. For that, use the accompanying [Engelsoft Beacon BACnet/IP integration](https://github.com/engelsofta/ha-bepacom-bacnet).

This add-on works on Home Assistant OS as well as Home Assistant Supervised.

This edition is maintained by [engelsofta](https://github.com/engelsofta). It is derived from the Bepacom BACnet/IP add-on under the Apache License 2.0.


## Installation

1. Add `https://github.com/engelsofta/engelsoft-bacstac-ha-addon` as a custom repository in the Home Assistant app store.
2. Select Engelsoft BACstac and click "Install".
3. Start the "Engelsoft BACstac" app.
4. Check the logs of "Engelsoft BACstac" to see if everything went
   well.
5. Now your Home Assistant host is a virtual BACnet/IP device!


## Usage

Use the accompanying [Engelsoft Beacon BACnet/IP integration](https://github.com/engelsofta/ha-bepacom-bacnet) to create and manage Home Assistant devices and entities. The integration also controls which BACnet objects use COV, polling or no updates and sends supported write commands back through BACstac.

## Internal integration connection

BACstac provides a local HTTP/WebSocket interface on TCP port `8099`. This
interface is required for communication with Engelsoft Beacon BACnet/IP and is
not intended as a separate public API or as a replacement for the companion
integration. Access is restricted to Home Assistant, loopback and the add-on
host addresses.

Protocol V2 carries inventory, point changes, managed update targets, writes,
priority releases and diagnostics between the two components. Legacy protocol
endpoints remain in the program for compatibility, but new installations should
use Engelsoft Beacon instead of configuring REST sensors or calling endpoints
manually.

If an `api_token` is configured, enter the same token in Engelsoft Beacon. The
token is never required for BACnet devices themselves.


## Configuration

**Note**: _Remember to restart the add-on when the configuration is changed._

Example add-on configuration:

```yaml
objectName: Engelsoft BACstac
address: auto
objectIdentifier: 420
loglevel: WARNING
segmentation: segmentedBoth
vendorIdentifier: 15
maxApduLengthAccepted: 1476
maxSegmentsAccepted: 64
api_token: ""
```

### Option: `objectName` Device Name
The Object Name that this device will get. This will be seen by other devices on the BACnet network.

### Option: `address` Interface IP
The address of the BACnet/IP interface.
You can write the IP yourself or use "auto" to let the add-on automatically try to get the right IP address.
If you want to write your IP manually, don't forget to put the CIDR behind the IP. For example: 192.168.2.11/24.
If you use subnet mask of 255.255.255.0, just put /24 behind your IP address. 
If you have a subnet of 255.255.0.0 then your CIDR notation would be /16

### Option: `objectIdentifier` Device ID
The Object Identifier that this device will get. This will be seen by other devices on the BACnet network. **Make sure it's unique in your network!**

### Option: `api_token` Integration Access Token
Optional shared secret for the internal connection to Engelsoft Beacon BACnet/IP. Configure the same token in both components, or leave it empty in both.

### Live update settings

Polling interval, COV registration delay, COV verification time and fallback write priority are configured under **Devices → Operation** in the sidebar. They are stored persistently and applied without restarting the add-on.

### Options: safe update handling

- Engelsoft Beacon BACnet/IP selects `cov`, `polling` or `disabled` for every target. BACstac enforces the per-device COV limit, subscription pacing and automatic polling fallback. Targets without an explicit update mode use polling for backward compatibility.

The **Subscriptions** page shows the state of every managed target, when its COV subscription was confirmed, the last COV notification, the last poll and the age of its current value.

Managed polling schedules cycle starts at `managed_poll_rate`. Each BACnet read
has a bounded timeout and a failed object does not stop the remaining cycle.
The Subscriptions page marks the affected target as **Polling disturbed** until
a later read succeeds. With many or slow targets, a cycle can still take longer
than the requested interval; the diagnostics report its actual duration.

### Device-friendly initial discovery

<!-- Changed by engelsofta in 2026: document paced discovery. -->
At startup, BACstac still reads the device inventory so its objects are available
to the Home Assistant integration. These discovery requests are sent one at a
time with a short pause. Where supported, BACstac first reads `propertyList` and
then requests only properties advertised by the object. Older devices without
`propertyList` use a compact compatibility set. A timeout stops the current
discovery pass and activates a short per-device backoff, preventing an
unresponsive or resource-limited gateway from being hammered by the remaining
inventory requests.

Engelsoft Beacon sends the selected `cov`, `polling` or `disabled` mode for
each managed target through the internal Protocol V2 connection. No manual connection
configuration is required.

The WebUI status strip shows the current COV, polling, fallback and disabled
target counts on every page.

### Device protection

Device protection is configured on the **Devices** page of the add-on sidebar. The global rule applies to every discovered BACnet device. Selecting a device lets you create an override for that device. Object selection and transport remain controlled by the Home Assistant integration.

- **COV lifetime** controls how long a subscription remains valid before it is renewed (60–28800 seconds).
- **Maximum COV subscriptions** limits simultaneous subscriptions per device (0–1000). Additional targets use polling; 0 disables COV for that device.
- **Renew COV after I-Am** restores missing subscriptions after a device announces itself again.
- **Check object list after I-Am** re-reads the device object list after an I-Am message.

Changes are stored persistently and applied while the add-on is running. Writes requested by Engelsoft Beacon remain available even though the manual write form was removed from the sidebar.

The following properties will be read each poll:
- presentValue
- statusFlags
- outOfService
- eventState
- reliability
- covIncrement

### Option: `foreignBBMD` BACnet/IP Broadcast Management Device Address
If you have your BACnet/IP network on another subnet, write the IP of your BBMD device here. This way, the add-on can communicate with the BBMD.
Otherwise keep this option empty.

### Option: `foreignTTL` Foreign TTL
Time To Live of foreign packets.

### Option: `loglevel` Level of logging
The verbosity of the logs in the add-on. 
There are 5 levels of logging:
- DEBUG: You'll get too much info. Only useful for development.
- INFO: You'll receive a lot of info that could be useful for troubleshooting.
- WARNING: You'll only receive logs if something went wrong.
- ERROR: You'll only see errors pop up.
- CRITICAL: You want to ignore everything that's happening.

Usually WARNING is sufficient.

### Option: `vendorIdentifier` Vendor Identifier
Identifier of the vendor of the interface. As we don't have an official identifier, put anything you want in here.

### Option: `segmentation` Segmentation Supported
Segmentation type of the add-on. Recommended to leave on SegmentedBoth for the best compatibility.
Segmentation is whether the device supports splitting up large BACnet messages. 
A BACnet message will be split based on the maximum APDU length accepted. 
This is usually the case when using Read Property Multiple requests.
- segmentedBoth allows both the incoming and outgoing messaged to be split up. 
- segmentedTransmit allows only sending split messages.
- segmentedReceive allows only incoming messages to be segmented.
- noSegmentation allows no segmentation.

### Option: `maxSegmentsAccepted` Maximum Segments Accepted
The amount of segments that the device can accept at most for a single service request. Default is 64 segments.

### Option: `maxApduLengthAccepted` Maximum APDU Length Accepted
Maximum size a BACnet message/segment is allowed to be. 
The built-in fallback is `480`. A value of `1476` is common for BACnet/IP and can be configured when supported by the network and devices.


### Network port: `47808/UDP`
BACnet/IP uses UDP port `47808` by default. Keep this port available to BACstac and do not run another BACnet stack on the same Home Assistant host and port.

## Problems

### I can't start the add-on when my Node-RED is also running

Node-RED or another standalone BACnet integration may already be using UDP port
`47808`. Only one BACnet stack can bind this address and port on the Home
Assistant host. Stop or reconfigure the competing BACnet application before
starting BACstac. Changing the integration port `8099` does not resolve a
BACnet UDP port conflict.


## Credits

Engelsoft BACstac is maintained by `engelsofta` and derived from the original Bepacom BACnet/IP add-on. See `NOTICE` and `LICENSE` in the repository root.
