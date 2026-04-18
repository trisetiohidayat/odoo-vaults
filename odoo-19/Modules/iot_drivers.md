---
uuid: iot-drivers-001
module: iot_drivers
type: module
tags: [odoo, odoo19, iot, hardware, drivers]
---

# IoT Drivers

> **Source location:** `~/odoo/odoo19/odoo/addons/iot_drivers/`
> **Note:** This module runs on **IoT box hardware** (Raspberry Pi or Windows IoT), not on the Odoo server. It is marked `installable: False` in the manifest and is pre-installed in the IoT box image.

## Overview

- **Name:** Hardware Proxy
- **Category:** Hidden
- **Installable:** `False` — this is a framework module pre-installed in the IoT box image
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Sequence:** 6

`iot_drivers` is the daemon that runs on an IoT box (Raspberry Pi or Windows IoT). It manages the full lifecycle of hardware peripherals — discovery, driver assignment, action dispatch, and bidirectional communication with the Odoo server. It is not installed from an Odoo addon ZIP; it is baked into the IoT box image and starts automatically when the box boots.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       IoT Box (Raspberry Pi / Windows IoT)                  │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │  Manager (daemon thread)                                             │ │
│  │                                                                       │ │
│  │  1. Wi-Fi reconnect (RPi)                                             │ │
│  │  2. nginx server start                                               │ │
│  │  3. certificate.ensure_validity()    ← daily cron                   │ │
│  │  4. upgrade.check_git_branch()     ← daily cron                     │ │
│  │  5. helpers.reset_log_level()      ← daily cron                     │ │
│  │  6. manager._send_all_devices()    ← every 3 seconds                 │ │
│  │  7. WebsocketClient.start()                                         │ │
│  │                                                                       │ │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────────┐ │ │
│  │  │ ConnectionManager   │  │  WebsocketClient                       │ │ │
│  │  │ (pairing thread)   │  │  - subscribes to bus channel          │ │ │
│  │  │ - polls odoo.com   │  │  - handles: iot_action, restart_odoo, │ │ │
│  │  │ - exchanges keys   │  │    server_update, webrtc_offer, etc. │ │ │
│  │  │ - gets server URL  │  │                                        │ │ │
│  │  └──────────────────────┘  └──────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  └───────────────────────────┬─────────────────────────────────────────┘ │
│                              │                                           │
│  ┌───────────────────────────▼─────────────────────────────────────────┐ │
│  │  Interface threads (USB, Serial, Printer, etc.)                     │ │
│  │                                                                       │ │
│  │  Interface.__init_subclass__() auto-registers into interfaces{}      │ │
│  │  Interface.run() loop: get_devices() → add/remove_device()           │ │
│  │                                                                       │ │
│  │  ┌──────────────┐  ┌──────────────────────────────────────────────┐ │ │
│  │  │ Driver threads │  │  Driver registry (drivers[])                │ │ │
│  │  │ per device    │  │  Driver.__init_subclass__() auto-registers │ │ │
│  │  │ - action()    │  │  .supported() — device claim check           │ │ │
│  │  │ - disconnect()│  │  .action(data) — dispatch to _actions dict  │ │ │
│  │  └──────────────┘  └──────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────────────┐ │ │
│  │  │  EventManager (global singleton)                                 │ │ │
│  │  │  device_changed(device, data) → sends to bus.bus websocket       │ │ │
│  │  └─────────────────────────────────────────────────────────────────┘ │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  HTTP Routes (Odoo's built-in WSGI server)                            │ │
│  │                                                                        │ │
│  │  /hw_proxy/hello              → ping                                 │ │
│  │  /hw_proxy/status_json        → driver statuses                      │ │
│  │  /iot_drivers/action          → dispatch device action                │ │
│  │  /iot_drivers/event           → long-polling for device events        │ │
│  │  /iot_drivers/...            → homepage, logs, Wi-Fi, credentials   │ │
│  │  /iot/box/send_websocket      → receive action result from box       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────┘
           │                              │
           │ HTTPS + TLS cert             │ WebSocket (bus.bus channel)
           ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────────────────────┐
│   Odoo Server Database  │    │         Odoo Web Client (Browser)        │
│                         │    │                                          │
│  iot.box record        │    │  IoTLongpolling (iot_base JS)            │
│  iot.device records     │    │  DeviceController                        │
│  bus.bus notifications  │    │                                          │
└─────────────────────────┘    └─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────┐
│   iot-proxy.odoo.com    │
│                         │
│  /odoo-enterprise/      │
│   iot/connect-box       │
│  → pairing exchange     │
└─────────────────────────┘
```

## Directory Structure

```
iot_drivers/
├── __init__.py
├── __manifest__.py
├── main.py                    # Manager daemon + global registries (drivers, interfaces, iot_devices)
├── driver.py                  # Base Driver class
├── interface.py               # Base Interface class (device discovery)
├── event_manager.py           # Event bus for device → server communication
├── websocket_client.py        # WebSocket client (bus.bus channel)
├── webrtc_client.py           # WebRTC client (camera/video streams)
├── connection_manager.py       # Pairing flow (polls iot-proxy.odoo.com)
├── http.py                    # WSGI dispatcher patch (JSON-RPC 403 handling)
├── browser.py                # Kiosk browser management
├── exception_logger.py         # Server-side exception logging
├── server_logger.py           # Client-side log forwarding to Odoo server
│
├── controllers/
│   ├── __init__.py
│   ├── homepage.py            # IoT box homepage (status, logs, config UI)
│   ├── proxy.py              # Legacy hw_proxy endpoints
│   └── driver.py             # DriverController + event long-polling
│
├── tools/
│   ├── __init__.py
│   ├── helpers.py            # Config, network, IO utilities
│   ├── certificate.py        # TLS certificate management
│   ├── wifi.py              # NetworkManager / Wi-Fi + access point
│   ├── route.py             # @iot_route decorator (auth=none, save_session=False)
│   ├── system.py            # Platform detection (IS_RPI, IS_WINDOWS, IS_TEST)
│   └── upgrade.py           # Git branch management
│
├── cli/
│   └── genproxytoken.py      # CLI to generate proxy token
│
└── iot_handlers/            # Dynamically downloaded from Odoo server
    ├── drivers/              # Printer, scale, display, keyboard, etc.
    │   ├── printer_driver_L.py
    │   ├── printer_driver_W.py
    │   ├── printer_driver_base.py
    │   ├── serial_scale_driver.py
    │   ├── serial_base_driver.py
    │   ├── display_driver_L.py
    │   ├── keyboard_usb_driver_L.py
    │   └── l10n_*_serial_driver.py
    └── interfaces/           # Device discovery interfaces
        ├── usb_interface_L.py
        ├── serial_interface.py
        ├── printer_interface_L.py
        ├── printer_interface_W.py
        └── display_interface_L.py
```

## Global Registries (`main.py`)

The module maintains three global dictionaries that are shared across all threads:

```python
# main.py
drivers = []             # List of Driver subclasses (auto-registered via __init_subclass__)
interfaces = {}           # Dict: Interface name → Interface class (auto-registered)
iot_devices = {}          # Dict: device_identifier → Driver instance (active devices)
unsupported_devices = {}   # Dict: device_identifier → dict (detected but no driver)
```

## Manager Daemon (`main.py`)

The `Manager` class is the main entry point. It is started as a **daemon thread** when `main.py` is imported.

```python
class Manager(Thread):
    ws_channel = ""  # WebSocket channel returned by server at /iot/setup

    def __init__(self):
        super().__init__(daemon=True)
        self.identifier = helpers.get_identifier()    # RPi serial or Windows UUID
        self.domain     = self._get_domain()         # IP-based domain for IoT box
        self.version    = helpers.get_version(detailed_version=True)
        self.previous_iot_devices = {}
        self.previous_unsupported_devices = {}

    def run(self):
        """Startup sequence on IoT box boot."""
        if IS_RPI:
            subprocess.run(["sudo", "mount", "-o", "remount,rw", "/"], check=False)
            subprocess.run(["sudo", "mount", "-o", "remount,rw", "/root_bypass_ramdisks/"], check=False)
            wifi.reconnect(helpers.get_conf('wifi_ssid'), helpers.get_conf('wifi_password'))

        helpers.start_nginx_server()
        _logger.info("IoT Box Image version: %s", helpers.get_version(detailed_version=True))
        upgrade.check_git_branch()

        if IS_RPI and helpers.get_odoo_server_url():
            helpers.generate_password()

        certificate.ensure_validity()

        # CRITICAL: Register IoT box with DB BEFORE downloading handlers
        # because handlers cannot be assigned without a known box identifier
        self._send_all_devices()
        helpers.download_iot_handlers()
        helpers.load_iot_handlers()

        # Start all Interface threads (device discovery)
        for interface in interfaces.values():
            interface().start()

        # Daily scheduled tasks
        schedule.every().day.at("00:00").do(certificate.ensure_validity)
        schedule.every().day.at("00:00").do(helpers.reset_log_level)
        schedule.every().day.at("00:00").do(upgrade.check_git_branch)

        # WebSocket connection to Odoo server
        ws_client = WebsocketClient(self.ws_channel)
        if ws_client:
            ws_client.start()

        # Device change polling loop (every 3 seconds)
        while True:
            try:
                if self._get_changes_to_send():
                    self._send_all_devices()
                if IS_RPI and helpers.get_ip() != '10.11.12.1':
                    wifi.reconnect(...)  # Reconnect Wi-Fi if lost
                time.sleep(3)
                schedule.run_pending()
            except Exception:
                _logger.exception("Manager loop unexpected error")

manager = Manager()
manager.start()
```

**Important startup invariant:** The IoT box MUST register itself with the Odoo database (`_send_all_devices`) before downloading IoT handlers. If the box has no identifier in the database, the server cannot assign drivers to it.

## Driver Base Class (`driver.py`)

Every hardware driver inherits from `Driver`. The `__init_subclass__` hook **auto-registers** all driver subclasses into the global `drivers` list.

```python
class Driver(Thread):
    connection_type = ''   # Override: 'usb', 'serial', 'network', etc.
    priority = 0           # Override: higher priority wins when multiple drivers match

    def __init__(self, identifier, device):
        super().__init__(daemon=True)
        self.dev                 = device
        self.device_identifier   = identifier
        self.device_name         = ''
        self.device_connection    = ''
        self.device_type         = ''
        self.device_manufacturer = ''
        self.data                = {'value': '', 'result': ''}
        self._actions           = {}    # Override: {'print': self.print_receipt, ...}
        self._stopped            = Event()
        self._recent_action_ids = LRU(256)

    def __init_subclass__(cls):
        super().__init_subclass__()
        if cls not in drivers:
            drivers.append(cls)   # Auto-registration!

    @classmethod
    def supported(cls, device):
        """Override to claim this device. Return True if this driver owns the device."""
        return False

    @toggleable
    def action(self, data):
        """Entry point for all device actions. Dispatches to named handler."""
        action            = data.get('action', '')
        action_unique_id  = data.get('action_unique_id')
        if action_unique_id and action_unique_id in self._recent_action_ids:
            _logger.warning("Duplicate action %s id %s received, ignoring", action, action_unique_id)
            return
        if action_unique_id:
            self._recent_action_ids[action_unique_id] = action_unique_id

        self.data["owner"] = data.get('session_id')
        base_response = {'action_args': {**data}, 'session_id': data.get('session_id')}

        try:
            response = {
                'status': 'success',
                'result': self._actions[action](data),
                **base_response
            }
        except Exception as e:
            if action_unique_id:
                self._recent_action_ids.pop(action_unique_id, None)
            _logger.exception("Error while executing action %s", action)
            response = {'status': 'error', 'result': str(e), **base_response}

        # Notify Odoo server via event (printers and payment terminals handle their own events)
        if self.device_type not in ["printer", "payment"]:
            event_manager.device_changed(self, response)

    def disconnect(self):
        self._stopped.set()
        del iot_devices[self.device_identifier]
```

### Action Dispatch Table

The `_actions` dict maps action names to methods. Example from a printer driver:

```python
class PrinterDriver(Driver):
    connection_type = 'network'
    priority = 1
    device_type = 'printer'

    _actions = {
        'print':         self.print_receipt,
        'print_status':  self.print_status,
        'open_cashbox':  self.open_cashbox,
    }

    def supported(cls, device):
        # Check device matches this printer's pattern
        return device.get('manufacturer') == 'Epson'
```

## Interface Base Class (`interface.py`)

Interfaces handle **device discovery** — scanning for hardware and matching it to drivers. Each interface runs in its own thread. The `__init_subclass__` hook auto-registers into `interfaces{}`.

```python
class Interface(Thread):
    _loop_delay = 3          # Seconds between device scans (0 = scan once only)
    connection_type = ''     # Override: 'usb', 'serial', 'network'
    allow_unsupported = False

    def __init_subclass__(cls):
        super().__init_subclass__()
        interfaces[cls.__name__] = cls  # Auto-registration!

    def run(self):
        while self.connection_type and self.drivers:
            self.update_iot_devices(self.get_devices())
            if not self._loop_delay:
                break
            time.sleep(self._loop_delay)

    def add_device(self, identifier, device):
        """Match a detected device to a driver."""
        supported_driver = next(
            (d for d in self.drivers if d.supported(device)),
            None
        )
        if supported_driver:
            d = supported_driver(identifier, device)
            iot_devices[identifier] = d
            d.start()   # Start the driver's thread
        elif self.allow_unsupported:
            unsupported_devices[identifier] = {...}

    def remove_device(self, identifier):
        """Called when a device is unplugged or no longer detected."""
        if identifier in iot_devices:
            iot_devices[identifier].disconnect()
            del iot_devices[identifier]
```

## WebSocketClient (`websocket_client.py`)

The `WebsocketClient` maintains a persistent WebSocket connection to the Odoo server, subscribing to the `bus.bus` channel for the IoT box. It runs in its own thread and handles reconnection automatically.

```python
class WebsocketClient(Thread):
    channel = ""

    def on_message(self, ws, messages):
        for message in json.loads(messages):
            self.last_message_id = message['id']
            payload = message['message']['payload']

            if helpers.get_identifier() not in payload.get('iot_identifiers', []):
                continue

            match message['message']['type']:

                case 'iot_action':
                    for device_id in payload['device_identifiers']:
                        if device_id in iot_devices:
                            iot_devices[device_id].action(payload)
                        else:
                            # Device not connected — notify server
                            send_to_controller({
                                'session_id': payload.get('session_id'),
                                'iot_box_identifier': helpers.get_identifier(),
                                'device_identifier': device_id,
                                'status': 'disconnected',
                            })

                case 'server_clear':
                    helpers.disconnect_from_server()

                case 'server_update':
                    helpers.update_conf({'remote_server': payload['server_url']})

                case 'restart_odoo':
                    send_to_controller({...})
                    ws.close()
                    helpers.odoo_restart()

                case 'webrtc_offer':
                    answer = webrtc_client.offer(payload['offer'])
                    send_to_controller({'answer': answer}, method="webrtc_answer")

                case 'remote_debug':
                    helpers.toggle_remote_connection(payload.get("token", ""))
                    send_to_controller({'result': {'enabled': helpers.is_ngrok_enabled()}})

                case 'test_connection':
                    send_to_controller({
                        'result': {
                            'lan_quality': helpers.check_network(),
                            'wan_quality': helpers.check_network("www.odoo.com"),
                        }
                    })

                case 'bundle_changed':
                    upgrade.check_git_branch()

    def on_close(self, ws, ...):
        helpers.update_conf({'last_websocket_message_id': self.last_message_id})
```

The `send_to_controller()` function posts results back to the server:

```python
@helpers.require_db
def send_to_controller(params, method="send_websocket", server_url=None):
    requests.post(
        f"{server_url}/iot/box/{method}",
        json={'params': params},
        timeout=5,
    )
```

## Handler Loading (`helpers.py`)

Drivers and interfaces are **dynamically downloaded** from the Odoo server and loaded at runtime:

```python
def download_iot_handlers(auto=True, server_url=None):
    """POST to /iot/get_handlers, receive a ZIP, extract to iot_handlers/"""
    response = requests.post(
        server_url + '/iot/get_handlers',
        data={'identifier': get_identifier(), 'auto': auto},
        headers={'If-None-Match': etag} if etag else None,
        timeout=8,
    )
    # Extract ZIP to iot_handlers/
    zip_file.extractall(path)

def load_iot_handlers():
    """Dynamically import Python files from iot_handlers/drivers and iot_handlers/interfaces"""
    for directory in ['interfaces', 'drivers']:
        path = file_path(f'iot_drivers/iot_handlers/{directory}')
        for file in get_handlers_files_to_load(path):
            spec = util.spec_from_file_location(name, file_path)
            module = util.module_from_spec(spec)
            spec.loader.exec_module(module)  # Driver classes auto-register via __init_subclass__!

def get_handlers_files_to_load(handler_path):
    """Filter by platform suffix: _L=RPi/Linux, _W=Windows, no suffix=both"""
    if IS_RPI:
        return [x.name for x in Path(handler_path).glob('*[^_W].*')]
    elif IS_WINDOWS:
        return [x.name for x in Path(handler_path).glob('*[^_L].*')]
    return []
```

## Certificate Management (`certificate.py`)

TLS certificates are required for HTTPS communication between the IoT box and the Odoo server.

```python
def ensure_validity():
    """Daily cron: validate or refresh the TLS certificate."""
    inform_database(get_certificate_end_date() or download_odoo_certificate())

def get_certificate_end_date():
    """Check if certificate is valid (not expired, not expiring within 10 days)."""
    path = Path('/etc/ssl/certs/nginx-cert.crt')
    cert = x509.load_pem_x509_certificate(path.read_bytes())
    # Skip if CN == 'OdooTempIoTBoxCertificate' (temporary cert)
    if datetime.now() > cert.not_valid_after_utc - timedelta(days=10):
        return None
    return str(cert.not_valid_after_utc)

def download_odoo_certificate():
    """Request a real certificate from odoo.com using db_uuid + enterprise_code."""
    response = requests.post(
        'https://www.odoo.com/odoo-enterprise/iot/x509',
        json={'params': {'db_uuid': db_uuid, 'enterprise_code': enterprise_code}},
        timeout=95,
    )
    # Save certificate + private key to /etc/ssl/
    # Start nginx; return cert end date
```

**Certificate end date reporting:** `inform_database()` POSTs the certificate expiry date to `/iot/box/update_certificate_status`, allowing the Odoo database to warn administrators before expiration.

## ConnectionManager Pairing Flow (`connection_manager.py`)

When an IoT box is first powered on with no server configured, it enters the **pairing flow**:

```
1. Box has no remote_server → ConnectionManager polls iot-proxy.odoo.com
2. POST /odoo-enterprise/iot/connect-box  { serial_number }
3. Server returns { pairing_code, pairing_uuid }
4. Box prints pairing code on connected printer
5. User enters pairing code in Odoo UI (Settings → IoT → Pair a Box)
6. Server returns { url, token, db_uuid, enterprise_code }
7. Box saves credentials to odoo.conf
8. Box restarts; Manager now points to the real database
```

```python
class ConnectionManager(Thread):
    def run(self):
        while True:
            while self._should_poll_to_connect_database():
                if not self.iot_box_registered:
                    self._register_iot_box()   # Get pairing code from iot-proxy.odoo.com
                self._poll_pairing_result()   # Check if server URL is ready
                time.sleep(self._get_next_polling_interval())
            time.sleep(5)
```

## Decorators

Two important decorators control function availability:

### `@require_db`

Guards functions that require an active Odoo server connection. Returns `None` silently if the box is offline or not yet paired.

```python
def require_db(function):
    def wrapper(*args, **kwargs):
        server_url = get_odoo_server_url()
        iot_box_ip = get_ip()
        if not iot_box_ip or iot_box_ip == "10.11.12.1" or not server_url:
            return  # Silently skip
        kwargs['server_url'] = server_url  # Inject server URL as kwarg
        return function(*args, **kwargs)
    return wrapper
```

### `@toggleable`

Disables functions via `devtools` configuration in `odoo.conf`. Allows remote disabling of actions and long-polling for development/debugging.

## Daily Cron Tasks

At 00:00 every day, the Manager's `schedule` loop runs:

| Task | Function | Purpose |
|------|----------|---------|
| Certificate check | `certificate.ensure_validity()` | Renew TLS cert if expiring |
| Log reset | `helpers.reset_log_level()` | Reset debug log level after 7 days |
| Git branch check | `upgrade.check_git_branch()` | Verify box runs correct Odoo version |

## IoT Handlers (Downloaded Drivers)

The `iot_handlers/` directory contains platform-specific drivers:

| File | Platform | Description |
|------|----------|-------------|
| `printer_driver_L.py` | Linux/RPi | CUPS printer, ESC/POS |
| `printer_driver_W.py` | Windows | Windows printer spooler |
| `printer_driver_base.py` | Both | Shared printer base class |
| `serial_scale_driver.py` | Both | Weighing scales via serial |
| `serial_base_driver.py` | Both | Base for serial protocol drivers |
| `display_driver_L.py` | Linux/RPi | Customer display (POS) |
| `keyboard_usb_driver_L.py` | Linux/RPi | USB barcode scanner (keyboard emulation) |
| `l10n_ke_edi_serial_driver.py` | Both | Kenya e-invoicing (serial) |
| `l10n_eg_drivers.py` | Both | Egypt fiscal device drivers |

Interface files in `iot_handlers/interfaces/`:

| File | Platform | Description |
|------|----------|-------------|
| `usb_interface_L.py` | Linux/RPi | USB device enumeration via `/sys/bus/usb/` |
| `serial_interface.py` | Both | Serial port enumeration via PySerial |
| `printer_interface_L.py` | Linux/RPi | CUPS printer discovery |
| `printer_interface_W.py` | Windows | Windows printer spooler discovery |
| `display_interface_L.py` | Linux/RPi | Serial display discovery |

## Related Documentation

- [[Modules/iot_base|iot_base]] — the companion frontend module (JavaScript client-side)
- [[New Features/What's New|What's New]] — Odoo 18→19 IoT changes
- [[New Features/Whats-New-Deep|Whats-New-Deep]] — detailed version diffs
- [[Modules/bus|bus — Notification Bus]] — `bus.bus` WebSocket channel used for IoT→server events

## Key Design Principles

1. **Auto-registration via `__init_subclass__`:** Both `Driver` and `Interface` use Python's `__init_subclass__` hook to auto-register subclasses into global lists. No manual registration needed — subclassing is sufficient.

2. **Handlers downloaded from server:** Drivers are not baked into the image; they are fetched from the Odoo server via `/iot/get_handlers`. This allows adding new device support without reflashing the IoT box.

3. **Thread-per-device model:** Each detected device gets its own `Driver` thread, allowing parallel operation of multiple peripherals.

4. **Idempotent action dispatch:** The `_recent_action_ids` LRU cache prevents duplicate action execution when messages are retried (at-least-once delivery guarantee).

5. **`@require_db` as a guard:** Functions that need the Odoo server silently skip when offline. This allows the IoT box to boot and function even before pairing is complete.

6. **Certificate rotation without downtime:** Nginx is restarted after certificate installation; Odoo service restarts after config updates, ensuring zero-touch reconnection.

## Notes

- **No Python models** — `iot_drivers` defines no ORM models. All state is in-memory or persisted in `odoo.conf`.
- **`installable: False`** — Cannot be installed via the Odoo apps UI. It is part of the IoT box image.
- **`schedule` library** — The `schedule` module (not Odoo's cron) handles daily/periodic tasks within the Python process.
- **`db_list()` override** (`http.py`) — The IoT box overrides `db_list()` to return an empty list, preventing the Odoo web login page from listing databases.
- **RPi-specific filesystem note:** The RPi IoT box has a ramdisk (`/root_bypass_ramdisks/`) for persistent storage across reboots. Network configuration files are synced there to survive reboots without a persistent root filesystem.
