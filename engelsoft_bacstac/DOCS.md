<!-- Modified by engelsofta in 2026 for Engelsoft BACstac; derived from the Bepacom BACnet/IP add-on. -->
# Engelsoft BACstac

Engelsoft BACstac is intended to be a bridge between the BACnet/IP network and Home Assistant.

The goal of this add-on is to add BACnet functionality to Home Assistant so these devices can be displayed on the dashboard.

The add-on is not directly responsible for generating entities in Home Assistant. For that, use the accompanying [BACnet integration](https://github.com/Bepacom-Raalte/Bepacom-BACnet-IP-Integration/tree/main).

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

After installing the add-on, there are 2 ways you can turn data into Home Assistant entities.

### Integration

The first and recommended way is to use the accompanying [BACnet integration](https://github.com/Bepacom-Raalte/Bepacom-BACnet-IP-Integration/tree/main).
Installation instructions are included in the README.md file. The installation is straightforward, like any other custom integration.

### RESTful Sensor

The second way to use this add-on to get data into Home Assistant is through the [RESTful Sensor](https://www.home-assistant.io/integrations/sensor.rest/) or through [RESTful](https://www.home-assistant.io/integrations/rest).
These are Home Assistant native integrations that will do requests to API endpoints. This has to be configured in your Configuration.yaml file.
An example of setting up one RESTful sensor:

```
sensor:
  - platform: rest
    name: Humidity
    state_class: measurement
    unit_of_measurement: "%"
    method: GET
    resource: http://<app-hostname>:8099/apiv1/device:100/analogInput:1/presentValue
```


## API Points

You'll be able to find all API points in the Web UI. All outside access to the API and Web UI is blocked. 
Only through Home Assistant the API can be accessed. 
This means everything inside Home Assistant is allowed to communicate with the add-on while other devices are not.

### API V1

**Device Identifiers** get written as "device:number", so if a device has an identifier of 100, the notation for API will be "device:100".

**Object Identifiers** apply the same notation. The object name will be camelCase. An example notation for an AnalogInput 1 would be "analogInput:1".

**Property Identifiers** also apply camelCase logic. An object identifier will be written as "objectIdentifier". 
Fortunately, you only need to write the value for writing properties.

#### GET

- /apiv1/json								- Return a full list of all device data.
- /apiv1/command/whois						- Make the add-on do a Who Is request.
- /apiv1/command/iam						- Make the add-on do an I Am request.
- /apiv1/command/readall					- Make the add-on read everything.
- /apiv1/commission/ede					    - Read uploaded EDE files.
- /apiv1/{deviceid}							- Retrieve all data from a specific device.
- /apiv1/{deviceid}/{objectid}				- Retrieve all data from an object from a specific device.
- /apiv1/{deviceid}/{objectid}/{propertyid}	- Retrieve a property value from an object in a specific device.

#### POST

- /apiv1/commission/ede						- Post EDE files
- /apiv1/{deviceid}/{objectid}				- Write data to be written to a BACnet object
- /apiv1/subscribe/{deviceid}/{objectid}	- Upload an EDE file

#### DELETE

- /apiv1/commission/ede						- Remove an EDE file with the corresponding device identifier
- /apiv1/subscribe/{deviceid}/{objectid}	- Remove a CoV subscription

### API V2

API V2 is in progress and improves the usability of the add-on.

#### POST

- /apiv1/{deviceid}/{objectid}/{propertyid}	- Write a property value to an object in a specific device.


## Configuration

**Note**: _Remember to restart the add-on when the configuration is changed._

Example add-on configuration:

```yaml
objectName: Engelsoft BACstac
address: auto
objectIdentifier: 420
subscription_mode: managed_polling
managed_poll_rate: 10
managed_cov_subscription_delay: 1
managed_cov_fallback_timeout: 30
defaultPriority: 15
devices_setup:
  - deviceID: all
    CoV_lifetime: 600
    CoV_limit: 20
    CoV_list: []
    quick_poll_rate: 5
    quick_poll_list: []
    slow_poll_rate: 600
    slow_poll_list:
      - all
  - deviceID: device:1835087
    CoV_lifetime: 600
    CoV_list: []
    quick_poll_rate: 5
    quick_poll_list:
      - analogInput:0
      - analogInput:1
      - analogInput:2
    slow_poll_rate: 300
    slow_poll_list:
      - all
loglevel: WARNING
segmentation: segmentedBoth
vendorID: 15
maxApduLenghtAccepted: 1476
maxSegmentsAccepted: 64
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

### Option: `defaultPriority` BACnet write priority fallback
This priority is used only when the integration or API does not provide one.
Low numbers have higher priority. Keep the fallback at 15 or 16 unless you
understand how command prioritization affects the target BACnet controller.

### Options: safe update handling

- `integration_controlled`: The integration selects `cov`, `polling` or `disabled` for every target. BACstac still enforces the per-device COV limit, subscription pacing and automatic polling fallback. Targets without an explicit mode use polling for backward compatibility.
- `subscription_mode`: `managed_polling` is the safe default. Engelsoft Beacon BACnet/IP sends the required targets to the add-on and BACstac polls only those targets. `managed_cov` uses COV where possible and automatically polls excess, failed or silent COV targets. `legacy` uses only the static `devices_setup` rules.
- `managed_poll_rate`: Polling interval in seconds for integration-managed targets.
- `managed_cov_subscription_delay`: Delay in seconds between COV subscription requests. A value of 1 avoids sending a burst of requests to sensitive controllers.
- `managed_cov_fallback_timeout`: Time in seconds after a confirmed COV subscription before control polling begins. The COV subscription remains active and permanent polling fallback happens only after repeated polls prove a value change without a matching COV notification.

The **Subscriptions** page shows the state of every managed target, when its COV subscription was confirmed, the last COV notification, the last poll and the age of its current value.

In `integration_controlled` mode the integration can send an `update_mode` with
each target to `POST /apiv1/managed/targets`:

```json
{"targets": [
  {"device_id": "device:21", "object_id": "analogInput:403", "update_mode": "cov"},
  {"device_id": "device:21", "object_id": "analogInput:404", "update_mode": "polling"},
  {"device_id": "device:21", "object_id": "analogInput:405", "update_mode": "disabled"}
]}
```

The WebUI status strip makes the active control mode and the current COV,
polling, fallback and disabled target counts visible on every page.

### Option: `devices_setup` Device Setup

The `devices_setup` configuration is a list of configurations for specific devices. 
Each list entry will contain a deviceID along with settings for Change of Value as well as polling.

```yaml
devices_setup:
  - deviceID: device:1835087
    CoV_lifetime: 600
    CoV_limit: 20
    CoV_list: []
    quick_poll_rate: 5
    quick_poll_list: []
    slow_poll_rate: 600
    slow_poll_list:
      - all
```

- `deviceID` This key contains the device identifier (in "device:xxxx" format where xxxx is the number) for the device you want the following options to count for. A special "all" key will make the settings below a general configuration.
- `CoV_lifetime` This key contains the lifetime for each CoV subscription made. This value is in seconds and can be between 60 and 28800. The add-on will automatically resubscribe once the lifetime has passed.
- `CoV_limit` limits simultaneous COV subscriptions for this device. The default is 20. Additional integration-managed targets automatically use polling. Set it to 0 to disable COV for the device.
- `CoV_list` contains each object identifier (in `object:xxxx` form) that legacy mode should subscribe to. It is empty by default. The special `all` value can create a very large number of subscriptions and should only be used when the device's documented COV capacity is known; the configured COV limit still applies.
```yaml
analogInput
analogOutput
analogValue
binaryInput
binaryOutput
binaryValue
multiStateInput
multiStateOutput
multiStateValue
```
- `quick_poll_rate` This key contains the rate at which quick poll objects have to be read. This is in seconds, between 3 and 30.
- `quick_poll_list` This key contains a list containing each object identifier the add-on has to poll at the poll rate defined above. The list can be empty if no quick polling is desired.
- `slow_poll_rate` This key contains the rate at which quick poll objects have to be read. This is in seconds, between 30 and 3000.
- `slow_poll_list` This key contains a list containing each object identifier the add-on has to poll at the poll rate defined above. The list can be empty if no slow polling is desired. A special "all" key will make the add-on poll all objects of the device.
- `resub_on_iam` Resubscribe to an object with CoV when an I-Am request has been received. When the lifetime of the object has passed, enabling this key will result in the resubscription of a CoV subscription. Otherwise it'll just update any new information of the device.
- `reread_on_iam` Reread the object list when an I-Am request has been received. This key will result in all objects of this device to be read again.

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

### Option: `vendorID` Vendor Identifier
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

### Option: `maxApduLength` Maximum APDU Length Accepted
Maximum size a BACnet message/segment is allowed to be. 
A common BACnet/IP value and the default for the add-on is 1476, and a common BACnet/MSTP value is 480.


### Network port: `80/TCP`
Port which the integration should connect to. If you leave this empty, the integration should connect to port 8099.

### Network port: `47808/UDP`
BACnet/IP port. The add-on seems to work if you leave this empty. Feel free to set it to empty if opening it causes issues.

## Problems

### I can't start the add-on when my Node-Red is also running

If you're using Node-Red for BACnet applications, chances are very high it's also using the BACnet port 47808.
This is causing a conflict between te add-ons, as we need the 47808 port as well for our BACnet/IP duties.
Removing the BACnet part from your Node-Red should solve this issue. 
You could also try to remove all ports to see if this works, but this hasn't been tested.
If this doesn't work, please check the webserver port isn't conflicting with another add-on either.


## Credits

Engelsoft BACstac is maintained by `engelsofta` and derived from the original Bepacom BACnet/IP add-on. See `NOTICE` and `LICENSE` in the repository root.
