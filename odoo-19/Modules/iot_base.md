---
uuid: iot-base-001
module: iot_base
type: module
tags: [odoo, odoo19, iot, hardware, frontend]
---

# IoT Base

> **Source location:** `~/odoo/odoo19/odoo/addons/iot_base/`
> **Note:** This module contains only frontend (JavaScript) code. The Odoo server-side models (`iot.box`, `iot.device`, `iot.config.input`) live in the Enterprise `iot` module which is not in the CE codebase.

## Overview

- **Name:** IoT Base
- **Category:** Hidden
- **Depends:** `web`
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Installable:** `True` — can be installed independently

`iot_base` is the foundational frontend module for the Odoo IoT ecosystem. It provides the JavaScript client-side infrastructure used by the web client to discover, communicate with, and control hardware peripherals (IoT boxes, printers, scales, etc.) connected to the Odoo server. It ships zero Python code — everything is pure JavaScript that runs in the browser.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Odoo Web Client (Browser)                   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    iot_base JavaScript                        │   │
│  │                                                             │   │
│  │  ┌─────────────────────┐  ┌────────────────────────────────┐│   │
│  │  │ DeviceController    │  │ IoTLongpolling Service         ││   │
│  │  │  - action()         │  │  - addListener()               ││   │
│  │  │  - addListener()    │  │  - removeListener()            ││   │
│  │  │  - removeListener() │  │  - startPolling()             ││   │
│  │  └──────────┬──────────┘  │  - _rpcIoT()                 ││   │
│  │             │               └──────────────┬───────────────┘│   │
│  │             │                              │                   │   │
│  │  ┌──────────┴──────────────────────────────▼───────────────┐ │   │
│  │  │              network_utils/http.js                      │ │   │
│  │  │               - formatEndpoint()                       │ │   │
│  │  │               - post()                                  │ │   │
│  │  └──────────────────────────────┬───────────────────────────┘ │   │
│  └───────────────────────────────┼───────────────────────────────┘   │
└────────────────────────────────┼────────────────────────────────────┘
                                 │ HTTP / JSON-RPC
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    IoT Box (iot_drivers on RPi/Windows)            │
│  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐  │
│  │ DriverController│  │ ProxyController│  │ HomepageController    │  │
│  │ /iot_drivers/ │  │ /hw_proxy/    │  │ /                   │  │
│  └───────┬──────┘  └───────┬───────┘  └────────────────────────┘  │
└──────────┼────────────────┼─────────────────────────────────────────┘
           │                 │
           ▼                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Odoo Server Database (iot.box, iot.device models)       │
│                (these models are in the Enterprise `iot` module)      │
└─────────────────────────────────────────────────────────────────────┘
```

## Module Contents

### JavaScript Assets (`web.assets_backend`)

```python
# __manifest__.py
'assets': {
    'web.assets_backend': [
        'iot_base/static/src/network_utils/*',
        'iot_base/static/src/device_controller.js',
    ],
}
```

#### File: `static/src/device_controller.js`

The `DeviceController` class is the primary public API consumed by other Odoo JavaScript modules (e.g., Point of Sale, Weighing Scale integrations).

```javascript
export class DeviceController {
    constructor(iotLongpolling, deviceInfo) {
        this.id          = uniqueId('listener-');
        this.iotIp       = deviceInfo.iot_ip;
        this.identifier  = deviceInfo.identifier;
        this.iotId       = deviceInfo.iot_id?.id;
        this.manual_measurement = deviceInfo.manual_measurement;
        this.iotLongpolling = iotLongpolling;
    }

    // Send an action to the device (e.g., print receipt, weigh item)
    action(data, fallback = false) {
        return this.iotLongpolling.action(this.iotIp, this.identifier, data, fallback);
    }

    // Register a callback to be notified when the device emits an event
    addListener(callback, fallback = true) {
        return this.iotLongpolling.addListener(
            this.iotIp, [this.identifier], this.id, callback, fallback
        );
    }

    // Unregister the listener
    removeListener() {
        return this.iotLongpolling.removeListener(this.iotIp, this.identifier, this.id);
    }
}
```

**Key design point:** `DeviceController` is a thin wrapper around `IoTLongpolling`. It does not communicate directly — every call goes through the longpolling service, which handles the HTTP transport and retry logic.

#### File: `static/src/network_utils/http.js`

Low-level HTTP utility that formats and sends JSON-RPC requests to IoT boxes.

```javascript
// Formats endpoint URL: preserves HTTPS context when browser is on HTTPS
export function formatEndpoint(ip, route, forceHttp = false) {
    const protocol = forceHttp ? "http:" : window.location.protocol;
    const rawIp    = forceHttp ? ip.replace(/^(\d+)-(\d+)-(\d+)-(\d+).*/, "$1.$2.$3.$4") : ip;
    return `${protocol}//${rawIp}${route}`;
}

// Sends a POST to the IoT box
export async function post(ip, route, params = {}, timeout = 6000, headers = {}, abortSignal = null, useLna = false) {
    const endpoint = formatEndpoint(ip, route, useLna);
    const timeoutSignal = AbortSignal.timeout(timeout);
    const response = await browser.fetch(endpoint, {
        body: JSON.stringify({ params }),
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        signal: abortSignal
            ? AbortSignal.any([abortSignal, timeoutSignal])
            : timeoutSignal,
        targetAddressSpace: useLna ? "local" : undefined,
    });
    return response.json();
}
```

**HTTPS awareness:** If the Odoo web client is served over HTTPS, `formatEndpoint` automatically uses HTTPS to contact the IoT box. The `useLna` flag (Local Network Access) forces HTTP over the local network when the browser supports the LNA feature.

**IP address translation:** IoT boxes on the local network may register with Odoo using a dotted-IP-in-domain format (e.g., `192-168-1-100.myserver.com`). The regex `ip.replace(/^(\d+)-(\d+)-(\d+)-(\d+).*/, "$1.$2.$3.$4")` reverses this encoding back to a real IP for direct local access.

#### File: `static/src/network_utils/longpolling.js`

`IoTLongpolling` is the core service that manages persistent HTTP connections to IoT boxes. It implements a **long-polling** pattern (periodic HTTP polling) for receiving device events, and an **action** pattern for sending commands.

```javascript
export class IoTLongpolling {
    static serviceDependencies = ["notification", "orm"];

    actionRoute = '/iot_drivers/action';
    pollRoute  = '/iot_drivers/event';

    rpcDelay    = 1500;    // Initial polling interval (ms)
    maxRpcDelay = 15000;   // Maximum polling interval (ms)

    async addListener(iot_ip, devices, listener_id, callback, fallback = true) {
        // Register devices + session, restart polling
        if (!this._listeners[iot_ip]) {
            this._listeners[iot_ip] = {
                last_event: 0,
                devices: {},
                session_id: this._session_id,
                abortController: null,
            };
        }
        for (const device of devices) {
            this._listeners[iot_ip].devices[device] = { listener_id, device_identifier: device, callback };
        }
        this.stopPolling(iot_ip);
        this.startPolling(iot_ip, fallback);
    }

    action(iot_ip, device_identifier, data, fallback = false) {
        // Send action request; response handled via longpoll
        return this._rpcIoT(iot_ip, this.actionRoute, {
            session_id: this._session_id,
            device_identifier,
            data,
        }, undefined, fallback);
    }

    async startPolling(iot_ip, fallback = true) {
        if (!this._listeners[iot_ip].abortController) {
            this._poll(iot_ip, fallback);
        }
    }

    _poll(iot_ip, fallback) {
        // Backend enforces 50s max; add 10s buffer
        this._rpcIoT(iot_ip, this.pollRoute, { listener }, 60000, fallback).then(
            (result) => {
                this._retries = 0;
                if (result.result?.session_id === this._session_id) {
                    this._onSuccess(iot_ip, result.result);
                }
                // Continue polling
                if (Object.keys(this._listeners[iot_ip].devices || {}).length > 0) {
                    this._poll(iot_ip);
                }
            },
            (e) => {
                if (e.name === "TimeoutError") this._onError();
            }
        );
    }

    _onError() {
        this._retries++;
        // Exponential backoff up to maxRpcDelay
        this._delayedStartPolling(Math.min(this.rpcDelay * this._retries, this.maxRpcDelay));
    }

    setLna(isLnaEnabled) { this.useLna = isLnaEnabled; }
}
```

Registered as an Odoo service:
```javascript
registry.category('services').add('iot_longpolling', iotLongpollingService);
```

## How Device Communication Works

### Sending an Action (Odoo -> IoT Box)

```
1. User triggers action in Odoo web client
2. JavaScript calls:  iotLongpolling.action(iot_ip, device_id, { action: 'print', ... })
3. POST /iot_drivers/action  { session_id, device_identifier, data }
4. DriverController receives request, dispatches to device driver
5. Driver executes hardware action (print, weigh, etc.)
6. Driver calls event_manager.device_changed() with result
7. Result stored in event queue
8. Next long-poll returns the result to browser
```

### Receiving an Event (IoT Box -> Odoo)

```
1. IoT box detects hardware event (button press, barcode scan, etc.)
2. Interface thread calls event_manager.device_changed(device, data)
3. event_manager sends event via websocket to Odoo server
4. Odoo broadcasts to all subscribed browser sessions
5. Browser long-polling receives the event
6. IoTLongpolling._onSuccess() fires the registered callback
7. Callback updates Odoo UI (e.g., POS order line added)
```

### Long-Polling Timeout and Retry

The backend (`DriverController.event`) enforces a **50-second maximum** poll window. The client (`IoTLongpolling`) adds a 10-second buffer (60s total) to avoid premature timeout. On any polling error:

- `_retries` counter increments
- Next poll is delayed by `rpcDelay * _retries` milliseconds
- Maximum backoff is capped at `maxRpcDelay = 15000 ms` (15 seconds)
- On `AbortError` (normal stop), no warning is shown

## Security Notes

| Concern | How Addressed |
|---------|---------------|
| HTTPS context preservation | `formatEndpoint()` mirrors `window.location.protocol` |
| Local Network Access (LNA) | `useLna` flag forces HTTP to `targetAddressSpace: local` |
| Session isolation | Each `IoTLongpolling` instance has its own `_session_id` (UUID) |
| AbortController per listener | Polling can be cancelled per IoT-box without affecting others |
| Error notifications | `_doWarnFail()` shows Odoo notification only when `fallback=false` |

## WebSocket Channel Mechanism (bus.bus)

While `IoTLongpolling` uses HTTP long-polling, the primary bidirectional channel between the IoT box and the Odoo server is a **WebSocket** connection managed by `iot_drivers.websocket_client.WebsocketClient`. The WebSocket client subscribes to a unique `channel` per IoT box (returned by the server at `/iot/setup`). This channel name is stored in `manager.ws_channel`.

```
IoT Box                    Odoo Server
   │                            │
   │─────── WebSocket Connect ────►
   │       (subscribe to         │
   │        channel: UUID)        │
   │                            │
   │◄────── iot_action msg ───────│  (server pushes action to box)
   │       { device_identifiers,  │
   │         session_id, action }  │
   │                            │
   │─────── send_to_controller ──►│  (box reports result back)
   │       POST /iot/box/         │
   │        send_websocket         │
```

The frontend (`iot_base`) is not directly involved in WebSocket communication — that is handled entirely by the IoT box daemon (`iot_drivers.main.Manager`).

## Odoo Server-Side Models (Enterprise)

The following models are defined in the **Enterprise** `iot` module (not present in the CE codebase):

| Model | Table | Description |
|-------|-------|-------------|
| `iot.box` | `iot_box` | Represents a physical IoT box. Stores identifier, MAC address, IP, token, version, company assignment. Managed via `iot_drivers/iot` module server-side. |
| `iot.device` | `iot_device` | Represents a hardware peripheral attached to an IoT box. Fields: name, type, manufacturer, connection type, associated box, company. |
| `iot.device.deprecated` | `iot_device_deprecated` | Legacy model for devices that have been replaced. |
| `iot.config.input` | `iot_config_input` | Key-value configuration pairs synced to the IoT box. Used to pass per-device settings (e.g., scale calibration, printer language) from Odoo to the box's handlers. |

These models are **not** in the CE codebase. The security/irrule design for these models typically restricts access by `iot_box_id` (device-level) and `company_id` (multi-company).

## Dependency Graph

```
iot_base
  └─ depends: web
       (no Python code, only JS loaded into web.assets_backend)

Odoo server (Enterprise iot module)
  ├─ iot.box ←─────── (populated by IoT box at /iot/setup)
  ├─ iot.device
  ├─ iot.config.input
  └─ iot.device.deprecated

iot_drivers (on IoT box hardware)
  ├─ subscribes to bus.bus channel (per iot.box)
  ├─ downloads drivers from Odoo server at /iot/get_handlers
  └─ reports device list at /iot/setup
```

## Related Documentation

- [[New Features/What's New|What's New]] — Odoo 18→19 IoT changes
- [[New Features/Whats-New-Deep|Whats-New-Deep]] — detailed version diffs
- [[Modules/bus|bus — Notification Bus]] — the `bus.bus` channel mechanism used for real-time events
- [[Modules/iot_drivers|iot_drivers]] — the companion module that runs on the IoT box hardware

## Notes

- `iot_base` is **installable independently** — it has no Python code, only JavaScript assets.
- The module's primary role is to provide the `iot_longpolling` Odoo service, which other modules (POS, Weighing Scale, etc.) consume via the `DeviceController` API.
- The `iot_drivers` module uses a **different asset bundle** (`iot_drivers.assets`) to ensure its static files only load on the IoT homepage, not on every backend page.
- No ACLs or record rules are defined here — this module has no Python models.
- The `_session_id` (UUID) in `IoTLongpolling` serves as the client-side session identifier passed to the IoT box in every request.

## Platform Detection and IoT Box Identification

The IoT box identifies itself to the Odoo server via a unique identifier:

| Platform | Identifier Source | Method |
|----------|------------------|--------|
| Raspberry Pi | Device tree serial number | `/sys/firmware/devetree/base/serial-number` |
| Windows IoT | Motherboard UUID | PowerShell `Get-CimInstance Win32_ComputerSystemProduct` |
| Test mode | Static string | `'test_identifier'` |

The identifier is used in several places:

```javascript
// IoTLongpolling sends identifier in every poll request
this._listeners[iot_ip].devices[device] = {
    listener_id: listener_id,
    device_identifier: device,    // passed to IoT box in poll
};
```

```python
# helpers.py in iot_drivers
@cache
def get_identifier():
    if IS_RPI:
        return read_file_first_line('/sys/firmware/devetree/base/serial-number').strip("\x00")
    elif IS_TEST:
        return 'test_identifier'
    # Windows: try motherboard UUID, fallback to random hex
    command = ['powershell', '-Command', "(Get-CimInstance Win32_ComputerSystemProduct).UUID"]
    ...
```

## Event Flow: Barcode Scan in POS

To illustrate the full round-trip, here is the complete flow for a barcode scan captured by a USB barcode scanner (keyboard emulation) in the Point of Sale:

```
1. User scans barcode at POS terminal
   → USB HID keyboard emulation: barcode characters sent as keyboard events

2. POS JavaScript (not iot_base) captures keystrokes,
   detects barcode complete (Enter key),
   calls:  iotLongpolling.action(iot_ip, scanner_id, { action: 'scan', value: '123456789' })

3. POST /iot_drivers/action
   { session_id, device_identifier, data: { action: 'scan', value: '123456789' } }
   → DriverController receives → keyboard_usb_driver_L.action()

4. keyboard_usb_driver emits event:
   event_manager.device_changed(driver, { barcode: '123456789', ... })

5. event_manager sends to Odoo server via websocket:
   POST /iot/box/send_websocket  { device_identifier, barcode: '123456789', ... }

6. Odoo server broadcasts to all sessions subscribed to bus.bus

7. POS JavaScript receives via websocket:
   → OdooLongpolling (odoo/addons/bus/models/bus.js) receives the notification

8. POS adds the scanned product to the order:
   pos_model.add_product(barcode='123456789')
```

Note: `iot_base`'s `IoTLongpolling` is specifically for **IoT box** communication, not the Odoo server's own notification bus. The Odoo server uses a separate `im_bus` and `bus` mechanism for internal notifications.

## Using DeviceController in Custom Modules

To integrate with IoT devices from a custom JavaScript module:

```javascript
/** @odoo-module */
import { registry } from "@web/core/registry";
import { DeviceController } from "@iot_base/device_controller";

const iotLongpollingService = registry.category("services").get("iot_longpolling");

async function useScale(deviceInfo) {
    // deviceInfo comes from the Odoo server model (iot.device record)
    const controller = new DeviceController(iotLongpollingService, {
        iot_ip: deviceInfo.iot_id.ip,
        identifier: deviceInfo.identifier,
        iot_id: deviceInfo,
    });

    // Add a listener for weight events (scale measurement)
    controller.addListener((event) => {
        console.log("Weight received:", event.value);
        // Update POS order line with weight
    });

    // Request a weight measurement from the scale
    // (actual action name depends on the scale driver)
    await controller.action({
        action: "get_weight",
    });
}
```

## Related Odoo JavaScript Services

| Service Name | Module | Purpose |
|-------------|--------|---------|
| `iot_longpolling` | iot_base | HTTP long-polling to IoT boxes |
| `bus_service` | bus | WebSocket to Odoo server (bus.bus) |
| `notification` | web | Toast notifications |
| `orm` | web | ORM read/write via RPC |

`iot_base`'s `IoTLongpolling` uses the Odoo `notification` service to show errors when long-polling fails (if `fallback=false`).
