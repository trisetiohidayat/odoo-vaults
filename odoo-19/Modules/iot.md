---
type: module
title: "IoT — Internet of Things Device Management"
description: "Odoo IoT system: IoT Box management, device drivers, WebSocket communication, and hardware integration for printers, scales, cameras, and displays."
source_path: ~/odoo/odoo19/odoo/addons/iot_drivers/ + iot_base + iot_box_image
tags:
  - odoo
  - odoo19
  - module
  - iot
  - hardware
  - websocket
  - device_drivers
related_modules:
  - stock
  - point_of_sale
  - mrp
  - hr
  - quality
created: 2026-04-11
version: "1.0"
---

## Quick Access

### Related Flows
- [Flows/Stock/receipt-flow](receipt-flow.md) — Barcode scanner use in inventory
- [Flows/POS/pos-session-flow](pos-session-flow.md) — Receipt printer and cash drawer integration

### Related Modules
- [Modules/Stock](Stock.md) — Barcode scanner integration
- [Modules/POS](pos.md) — Receipt printer and cash drawer
- [Modules/MRP](MRP.md) — Manufacturing device control

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | IoT (three sub-modules) |
| **Sub-modules** | `iot_base`, `iot_drivers`, `iot_box_image` |
| **Category** | Hardware / IoT |
| **Summary** | Connect Odoo to physical hardware via IoT Box |
| **Depends** | `web` (iot_base), none installable (iot_drivers, iot_box_image) |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

### Description

The Odoo IoT system is a **three-part architecture**:

```
┌─────────────────────────────────────────────────────────┐
│                   Odoo Server (Database)                 │
│  iot.box  ──  iot.device  ──  iot.device.type         │
│  (Enterprise Edition models)                             │
└──────────────────────┬──────────────────────────────────┘
                       │ WebSocket / HTTP
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  IoT Box (Edge Device)                    │
│  ┌──────────────────────────────────────────────────┐  │
│  │  iot_drivers (Linux service / IoT Box OS)       │  │
│  │                                                   │  │
│  │  Manager Thread ──► WebsocketClient ──► Odoo    │  │
│  │       │                                           │  │
│  │  ┌────▼─────┐  ┌────────────┐  ┌────────────┐  │  │
│  │  │Interface  │  │  Drivers   │  │   Event    │  │  │
│  │  │(USB/Serial│  │(Printer/   │  │  Manager   │  │  │
│  │  │ Network)  │  │ Scale/Cam) │  │            │  │  │
│  │  └───────────┘  └────────────┘  └────────────┘  │  │
│  └──────────────────────────────────────────────────┘  │
│  Hardware: USB devices, Serial devices, Network devices │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  iot_base (Frontend Assets)               │
│  JavaScript: DeviceController, HTTP client, longpolling │
└─────────────────────────────────────────────────────────┘
```

**Important:** The actual Odoo database models (`iot.box`, `iot.device`, `iot.device.type`) are in **Enterprise Edition**. The Community Edition `addons/` directory only contains:
- `iot_base` — Frontend JavaScript assets for the Odoo web client
- `iot_drivers` — Software that runs **on** the IoT Box (not in the Odoo DB)
- `iot_box_image` — Files used to build the IoT Box OS image

---

## Three Sub-Modules

### `iot_base` — Frontend Assets

**Purpose:** Provides JavaScript utilities for the Odoo web client to communicate with IoT devices.

**Files:**
- `static/src/device_controller.js` — `DeviceController` class
- `static/src/network_utils/http.js` — HTTP client for IoT device communication
- `static/src/network_utils/longpolling.js` — Longpolling for real-time device events

**Key Class: `DeviceController`** (JavaScript)

```javascript
export class DeviceController {
    constructor(iotLongpolling, deviceInfo) {
        this.iotIp = deviceInfo.iot_ip;        // IoT Box IP address
        this.identifier = deviceInfo.identifier;  // Device UUID
        this.iotId = deviceInfo.iot_id?.id;    // Odoo record ID
        this.manual_measurement = deviceInfo.manual_measurement;
    }

    // Send action to the device (e.g., print receipt)
    action(data, fallback = false) {
        return this.iotLongpolling.action(this.iotIp, this.identifier, data, fallback);
    }

    // Register a listener for device events (e.g., scale weight change)
    addListener(callback, fallback = true) {
        return this.iotLongpolling.addListener(this.iotIp, [this.identifier], this.id, callback, fallback);
    }

    // Unregister listener
    removeListener() {
        return this.iotLongpolling.removeListener(this.iotIp, this.identifier, this.id);
    }
}
```

**How the Odoo web client uses it:**
1. When loading a form with an IoT device field (e.g., POS terminal), the JS creates a `DeviceController`
2. The controller connects to the IoT Box via longpolling/WebSocket
3. Device actions (print, weigh, capture image) are sent via the controller
4. Device events (scale reading, barcode scan) are received via listeners

---

### `iot_drivers` — IoT Box Software

**Purpose:** Runs on the IoT Box as a Linux/Windows service. Responsible for:
- Detecting connected hardware
- Loading device drivers
- Managing WebSocket connection to Odoo
- Handling device actions and events

**Architecture:**

```
main.py (Manager Thread)
    │
    ├── connection_manager.py (ConnectionManager Thread)
    │       │ Polls iot-proxy.odoo.com for pairing result
    │       └── Registers IoT Box with Odoo database
    │
    ├── WebsocketClient (Thread)
    │       │ Maintains persistent WebSocket to Odoo server
    │       └── Routes messages: iot_action, server_clear, restart_odoo, etc.
    │
    ├── interfaces/ (detection threads)
    │       ├── usb_interface_L.py     — USB detection (Linux)
    │       ├── serial_interface.py      — Serial port detection
    │       ├── printer_interface_L/W   — Printer detection
    │       └── display_interface_L.py  — Display detection
    │
    ├── drivers/ (device handlers)
    │       ├── printer_driver_L.py    — ESC/POS receipt printers (Linux)
    │       ├── printer_driver_W.py     — ESC/POS receipt printers (Windows)
    │       ├── printer_driver_base.py — Common printer logic
    │       ├── serial_scale_driver.py  — Weighing scales (serial)
    │       └── display_driver_L.py     — Customer displays (Linux)
    │
    └── event_manager.py (EventManager)
            Routes device events back to Odoo via WebSocket or HTTP
```

---

## Core Threading Classes

### `Manager` (main.py)

The main orchestration thread running on the IoT Box.

```python
class Manager(Thread):
    def run(self):
        # 1. Mount filesystems (Raspberry Pi)
        if IS_RPI:
            subprocess.run(["sudo", "mount", "-o", "remount,rw", "/"])

        # 2. WiFi reconnect
        wifi.reconnect(wifi_ssid, wifi_password)

        # 3. Start nginx
        helpers.start_nginx_server()

        # 4. Check git branch / update
        upgrade.check_git_branch()

        # 5. Generate Odoo password (Raspberry Pi)
        if IS_RPI and helpers.get_odoo_server_url():
            helpers.generate_password()

        # 6. Ensure SSL certificate validity
        certificate.ensure_validity()

        # 7. Register with Odoo database (creates/updates iot.box record)
        self._send_all_devices()

        # 8. Download and load IoT handlers (drivers)
        helpers.download_iot_handlers()
        helpers.load_iot_handlers()

        # 9. Start all interface threads (device detection)
        for interface in interfaces.values():
            interface().start()

        # 10. Start WebSocket to Odoo server
        ws_client = WebsocketClient(self.ws_channel)
        if ws_client:
            ws_client.start()

        # 11. Main loop: check for device changes every 3 seconds
        while True:
            if self._get_changes_to_send():
                self._send_all_devices()  # Notify Odoo of device changes
            time.sleep(3)
```

**Device Registration (`_send_all_devices`):**

```python
def _send_all_devices(self, server_url=None):
    iot_box = {
        'identifier': self.identifier,      # Hardware UUID (from device tree/BIOS)
        'mac': helpers.get_mac_address(),   # MAC address
        'ip': self.domain,                   # IP-based domain (e.g., "192-168-1-10.example.com")
        'token': helpers.get_token(),        # Odoo session token
        'version': self.version,            # IoT Box image version
    }
    devices_list = {}
    for device in self.previous_iot_devices.values():
        devices_list[device.device_identifier] = {
            'name': device.device_name,
            'type': device.device_type,
            'manufacturer': device.device_manufacturer,
            'connection': device.device_connection,
            'subtype': device.device_subtype if device.device_type == 'printer' else '',
        }

    requests.post(server_url + "/iot/setup", json={'params': {
        'iot_box': iot_box, 'devices': devices_list
    }})
```

---

### `ConnectionManager` (connection_manager.py)

Manages the pairing process between the IoT Box and an Odoo database.

```python
class ConnectionManager(Thread):
    def run(self):
        while True:
            while self._should_poll_to_connect_database():
                if not self.iot_box_registered:
                    self._register_iot_box()   # Get pairing code from iot-proxy.odoo.com
                self._poll_pairing_result()   # Check if user entered code in Odoo
                time.sleep(self._get_next_polling_interval())
            time.sleep(5)

    def _register_iot_box(self):
        # Calls iot-proxy.odoo.com to get a pairing code
        req = requests.post(
            'https://iot-proxy.odoo.com/odoo-enterprise/iot/connect-box',
            json={'params': {'pairing_code': ..., 'serial_number': ...}}
        )
        # Response: { pairing_code, pairing_uuid }
        self.pairing_code = req['pairing_code']
```

**Pairing Flow:**
```
IoT Box boots (no server configured)
        |
        v
ConnectionManager polls iot-proxy.odoo.com
        |
        v
Gets pairing code (e.g., "ABCD-1234")
        |
        v
User goes to Odoo → IoT → Boxes → New
Enters pairing code
        |
        v
Odoo registers box, returns server URL + token
        |
        v
IoT Box saves to odoo.conf: remote_server, token, db_uuid
        |
        v
Manager sends /iot/setup with device list
        |
        v
WebSocket channel established
```

---

### `WebsocketClient` (websocket_client.py)

Maintains a persistent WebSocket connection to the Odoo server for real-time bidirectional communication.

```python
class WebsocketClient(Thread):
    def on_message(self, ws, messages):
        for message in json.loads(messages):
            payload = message['message']['payload']

            match message['message']['type']:
                case 'iot_action':
                    # Odoo → IoT Box: trigger device action
                    for device_identifier in payload['device_identifiers']:
                        main.iot_devices[device_identifier].action(payload)

                case 'server_clear':
                    # Disconnect from current server
                    helpers.disconnect_from_server()

                case 'restart_odoo':
                    # Restart the Odoo service on IoT Box
                    helpers.odoo_restart()

                case 'webrtc_offer':
                    # Camera WebRTC negotiation
                    answer = webrtc_client.offer(payload['offer'])
                    send_to_controller({'answer': answer}, method="webrtc_answer")

                case 'test_connection':
                    # Network quality check
                    send_to_controller({'result': {
                        'lan_quality': helpers.check_network(),
                        'wan_quality': helpers.check_network("www.odoo.com"),
                    }})

                case 'bundle_changed':
                    # Odoo DB was upgraded — refresh git branch
                    upgrade.check_git_branch()
```

---

### `Interface` (interface.py)

Base class for device detection. Each interface runs as a separate thread polling for hardware.

```python
class Interface(Thread):
    connection_type = ''
    _loop_delay = 3  # Poll every 3 seconds

    def run(self):
        while self.connection_type and self.drivers:
            self.update_iot_devices(self.get_devices())
            time.sleep(self._loop_delay)

    def update_iot_devices(self, devices=None):
        added = devices.keys() - self._detected_devices
        removed = self._detected_devices - devices.keys()

        for identifier in removed:
            self.remove_device(identifier)

        for identifier in added:
            self.add_device(identifier, devices[identifier])

    def add_device(self, identifier, device):
        # Find a matching driver
        supported_driver = next(
            (driver for driver in self.drivers if driver.supported(device)),
            None
        )
        if supported_driver:
            d = supported_driver(identifier, device)
            iot_devices[identifier] = d
            d.start()  # Start driver thread
```

---

### `Driver` (driver.py)

Base class for device handlers. Each driver runs as its own thread.

```python
class Driver(Thread):
    connection_type = ''
    priority = 0

    def __init__(self, identifier, device):
        super().__init__(daemon=True)
        self.device_identifier = identifier
        self.device_name = ''
        self.device_type = ''
        self.device_manufacturer = ''
        self.device_connection = ''
        self.data = {'value': '', 'result': ''}
        self._actions = {}    # {action_name: method}
        self._stopped = Event()

    def action(self, data):
        """Called when Odoo sends a command to this device."""
        action = data.get('action', '')
        response = {'status': 'success', 'result': self._actions[action](data), ...}
        # For non-printer/payment devices, notify Odoo immediately
        if self.device_type not in ["printer", "payment"]:
            event_manager.device_changed(self, response)

    def disconnect(self):
        self._stopped.set()
        del iot_devices[self.device_identifier]
```

---

### `EventManager` (event_manager.py)

Routes device events back to the Odoo server via multiple channels:

```python
class EventManager:
    def device_changed(self, device, data=None):
        event = {
            **device.data,
            'device_identifier': device.device_identifier,
            'time': time.time(),
        }

        # 1. Send to Odoo via HTTP (iot/box/send_websocket route)
        send_to_controller({
            **event,
            'iot_box_identifier': helpers.get_identifier(),
        })

        # 2. Send via WebRTC (for camera streams)
        if webrtc_client:
            webrtc_client.send(event)

        # 3. Store in local events list (for longpolling)
        self.events.append(event)

        # 4. Wake up any waiting longpolling sessions
        for session_id, session in self.sessions.items():
            if device.device_identifier in session['devices']:
                session['result'] = event
                session['event'].set()
```

---

## Device Drivers

### Printer Driver (`printer_driver_base.py`)

Supports ESC/POS printers via USB or network.

**Supported Printer Types:**
- `receipt_printer` — Standard receipt printers (thermal)
- `label_printer` — Label printers (ZPL-compatible)

**Supported Commands:**
```python
self._actions.update({
    'cashbox': self.open_cashbox,      # Open cash drawer
    'print_receipt': self.print_receipt,  # Print receipt
    'status': self.print_status,       # Print status / pairing code
})
```

**Printer Communication:**

The driver uses the `escpos` library (python-escpos) for ESC/POS protocol:
```python
from escpos.escpos import EscposIO
from escpos.printer import Usb

def print_receipt(self, data):
    receipt_data = b64decode(data['receipt'])
    with EscposIO(self.escpos_device) as p:
        p.text(receipt_data)
        p.cut()
```

**USB Retry Pattern:**

Due to USB hardware quirks, a retry mechanism is applied:
```python
# Monkeypatch USB read with retry
escpos.printer.Usb._read = _read_escpos_with_retry  # 5 retries with 50ms delay
```

### Serial Scale Driver (`serial_scale_driver.py`)

Reads weight from weighing scales connected via serial port (RS-232).

The driver parses weight data from serial input (different protocols for different scale brands) and exposes:
```python
self.data = {
    'value': weight_kg,       # Current weight
    'unit': 'kg',             # Unit of measurement
    'result': 'ok',          # Status
}
```

### Display Driver (`display_driver_L.py`)

Drives customer-facing LCD/LED displays. Typically used in POS to show the current order total.

Receives commands to display text on the display screen connected to the IoT Box.

---

## HTTP Controller Routes (iot_drivers)

**Location:** `controllers/homepage.py`

The IoT Box runs its own Odoo-compatible HTTP server (nginx + Werkzeug) to serve:
- `/` — IoT Box status page (HTML)
- `/logs` — Log viewer page
- `/status` — Status display page
- `/iot_drivers/ping` — Heartbeat check
- `/iot_drivers/data` — Device and system information
- `/iot_drivers/connect_to_server` — Save server credentials
- `/iot_drivers/save_credential` — Save db_uuid and enterprise_code
- `/iot_drivers/wifi` — WiFi network listing
- `/iot_drivers/restart_odoo_service` — Restart Odoo service
- `/iot_drivers/log_levels` — Log level configuration
- `/iot_drivers/is_ngrok_enabled` — Remote access status

**Important: All routes use `auth='none'`**

Since the IoT Box has no database access during startup, routes must be unauthenticated:

```python
@route.iot_route('/iot_drivers/ping', type='http', cors='*')
def ping(self):
    return json.dumps({
        'status': 'success',
        'message': 'pong',
    })
```

The `@route.iot_route` decorator (defined in `tools/route.py`) is a wrapper that sets:
```python
def iot_route(route=None, linux_only=False, **kwargs):
    if 'auth' not in kwargs:
        kwargs['auth'] = 'none'       # No DB auth needed
    if 'save_session' not in kwargs:
        kwargs['save_session'] = False  # No session management
```

---

## Odoo Server Communication

### Registration: `POST /iot/setup`

When the IoT Box starts, it calls this endpoint to register itself and its devices with the Odoo database:

```python
# Sent by IoT Box (main.py _send_all_devices)
requests.post(
    server_url + "/iot/setup",
    json={
        'params': {
            'iot_box': {
                'identifier': 'RPI-serial-number',
                'mac': 'b8:27:eb:xx:xx:xx',
                'ip': '192-168-1-10.example.com',
                'token': 'session-token',
                'version': 'K-23.11-16.0.0#abc123',
            },
            'devices': {
                'USB-printer-001': {
                    'name': 'Epson TM-T88',
                    'type': 'printer',
                    'manufacturer': 'Epson',
                    'connection': 'usb',
                    'subtype': 'receipt_printer',
                },
                'SERIAL-scale-001': {
                    'name': 'Toledo Scale',
                    'type': 'scale',
                    'manufacturer': 'Toledo',
                    'connection': 'serial',
                },
            }
        }
    }
)

# Response from Odoo
{
    'result': 'websocket_channel_name'  # e.g., "iot_abc123def456"
}
```

### Receiving Actions: WebSocket `iot_action`

When Odoo needs to trigger a device action (e.g., print a receipt):

```python
# Odoo sends via WebSocket
{
    'event_name': 'subscribe',
    'data': {
        'channels': ['iot_abc123def456'],
        'identifier': 'RPI-serial-number',
    }
}

# Later, a message is sent:
{
    'message': {
        'type': 'iot_action',
        'payload': {
            'device_identifiers': ['USB-printer-001'],
            'action': 'print_receipt',
            'receipt': '<base64-receipt-data>',
            'session_id': 'uuid',
        }
    }
}
```

### Event Notification: HTTP `/iot/box/send_websocket`

When a device reports an event (e.g., scale weight change):

```python
# IoT Box calls Odoo
requests.post(
    server_url + "/iot/box/send_websocket",
    json={'params': {
        'device_identifier': 'SERIAL-scale-001',
        'iot_box_identifier': 'RPI-serial-number',
        'value': '2.450',
        'result': 'ok',
        'session_id': 'session-uuid',
    }}
)
```

---

## Proxy Controller (`controllers/proxy.py`)

Legacy hardware proxy routes for backward compatibility:

```python
@route.iot_route('/hw_proxy/hello', type='http', cors='*')
def hello(self):
    return "ping"

@route.iot_route('/hw_proxy/status_json', type='jsonrpc', cors='*')
def status_json(self):
    return {
        driver: instance.get_status()
        for driver, instance in proxy_drivers.items()
    }
```

---

## Configuration Files (IoT Box Side)

The IoT Box stores configuration in `odoo.conf`-style files:

| Key | Description |
|-----|-------------|
| `remote_server` | Odoo server URL |
| `token` | Authentication token |
| `db_uuid` | Database UUID |
| `enterprise_code` | Enterprise license code |
| `db_name` | Database name |
| `wifi_ssid` | WiFi network name |
| `wifi_password` | WiFi password |
| `subject` | SSL certificate subject |
| `longpolling` | Longpolling port override |
| `last_websocket_message_id` | Last processed WebSocket message |

Managed via:
```python
helpers.update_conf({'key': 'value'})
helpers.get_conf('key')
helpers.save_conf_server(url, token, db_uuid, enterprise_code)
```

---

## IoT Box Identification

The IoT Box identifier is determined at startup:

```python
@cache
def get_identifier():
    if IS_RPI:
        # Raspberry Pi: read hardware serial from device tree
        return read_file_first_line('/sys/firmware/devetree/base/serial-number').strip("\x00")
    elif IS_WINDOWS:
        # Windows: read motherboard UUID via PowerShell
        command = ['powershell', '-Command', "(Get-CimInstance Win32_ComputerSystemProduct).UUID"]
        return subprocess.run(...).stdout.decode().strip()
    else:
        # Fallback: generate random identifier
        return secrets.token_hex()
```

---

## Key Concepts

### IoT Box vs. IoT Device

| Concept | Description |
|---------|-------------|
| **IoT Box** | The physical edge computer (Raspberry Pi or Windows VM). Has one identifier. Communicates with Odoo via WebSocket. Runs `iot_drivers` service. |
| **IoT Device** | Hardware attached to the IoT Box (printer, scale, camera). Has its own identifier. Communicates via driver. |

### Connection Types

| Type | Description |
|------|-------------|
| `usb` | USB-connected devices (printers, some scales) |
| `serial` | RS-232 serial devices (older scales, some displays) |
| `network` | Network-connected devices (network printers) |

### Device Types

| Type | Used By | Driver |
|------|---------|--------|
| `printer` | POS, Stock | `printer_driver_L/W.py` |
| `scale` | POS (weighing products), Stock | `serial_scale_driver.py` |
| `camera` | Quality control, MRP | WebRTC via `webrtc_client.py` |
| `display` | POS (customer-facing display) | `display_driver_L.py` |
| `keyboard` | Barcode scanners via USB-HID | `keyboard_usb_driver_L.py` |
| `payment` | POS payment terminals | Via `proxy_drivers` |

---

## Pairing Code Flow (User Perspective)

```
1. Flash IoT Box image onto Raspberry Pi / install virtual IoT
2. Connect IoT Box to network
3. IoT Box auto-connects to iot-proxy.odoo.com
4. Display shows pairing code: "ABCD-1234"
5. Odoo → IoT → Boxes → New → Enter pairing code
6. Odoo saves server URL + token
7. IoT Box saves credentials, reboots
8. IoT Box connects to Odoo, sends device list
9. Devices appear in Odoo: IoT → Devices
10. Assign devices to POS / Stock operations
```

---

## Source Files Reference

### iot_base (Frontend, CE)

| File | Role |
|------|------|
| `__manifest__.py` | Static asset registration |
| `static/src/device_controller.js` | `DeviceController` JS class |
| `static/src/network_utils/http.js` | HTTP client for device actions |
| `static/src/network_utils/longpolling.js` | Longpolling for device events |

### iot_drivers (IoT Box Software, runs ON the box)

| File | Role |
|------|------|
| `main.py` | `Manager` thread — startup, device detection loop |
| `connection_manager.py` | `ConnectionManager` thread — pairing process |
| `websocket_client.py` | `WebsocketClient` thread — real-time Odoo communication |
| `driver.py` | `Driver` base class |
| `interface.py` | `Interface` base class |
| `event_manager.py` | `EventManager` — routes events back to Odoo |
| `controllers/homepage.py` | IoT Box HTTP routes (status page, config) |
| `controllers/proxy.py` | Legacy hardware proxy routes |
| `controllers/driver.py` | Device-specific HTTP routes |
| `iot_handlers/drivers/printer_driver_base.py` | ESC/POS printer driver |
| `iot_handlers/drivers/printer_driver_L.py` | Linux printer specifics |
| `iot_handlers/drivers/printer_driver_W.py` | Windows printer specifics |
| `iot_handlers/drivers/serial_scale_driver.py` | Weighing scale driver |
| `iot_handlers/drivers/display_driver_L.py` | Customer display driver |
| `iot_handlers/interfaces/usb_interface_L.py` | USB device detection (Linux) |
| `iot_handlers/interfaces/serial_interface.py` | Serial port detection |
| `tools/helpers.py` | Config management, network utils, nginx, git |
| `tools/route.py` | `@iot_route` decorator (auth=none, save_session=False) |
| `tools/wifi.py` | WiFi management (Raspberry Pi) |
| `tools/certificate.py` | SSL certificate management |
| `tools/upgrade.py` | Git branch management, image updates |
| `tools/system.py` | `IS_RPI`, `IS_WINDOWS`, `IS_TEST` detection |

### iot_box_image

Files used to build the IoT Box OS image (Docker/image build configs). Not an installable Odoo module.

---

*Source: `~/odoo/odoo19/odoo/addons/iot_drivers/` and `~/odoo/odoo19/odoo/addons/iot_base/`*

*Note: Actual database models (`iot.box`, `iot.device`, `iot.device.type`) are in Enterprise Edition.*
