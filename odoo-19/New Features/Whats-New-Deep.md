---
type: new-feature
tags: [odoo, odoo19, deep-dive, new-features, technical, html-editor, iot, webauthn, passkey, peppol, cloud-storage, subcontracting, pos, data-recycle]
created: 2026-04-14
---

# Odoo 19 New Features: Deep Technical Dive

Comprehensive technical documentation of Odoo 19's most significant architectural systems. Each section traces through actual Odoo 19 Community Edition source code, explaining the design decisions, implementation patterns, and integration points.

**Source verified against:** `~/odoo/odoo19/odoo/addons/`

> **Companion doc:** [New Features/What's New](New Features/What's New.md) for a high-level overview. This document is the technical companion for developers who need to understand how things actually work.

---

## 1. HTML Editor Plugin Architecture

**Module:** `html_editor` | **Key files:** `models/html_field_history_mixin.py`, `models/diff_utils.py`

### 1.1 Architecture Overview

The Odoo 19 HTML editor is built as a plugin-based system on top of the OWL (Odoo Web Library) framework. The architecture separates the core engine from feature plugins, enabling selective loading based on context.

```
html_editor/static/src/
├── core/                       # Core editor engine
│   ├── editor.js              # Main OdooEditor class
│   ├── plugin.js              # Base Plugin class
│   └── selection.js           # Selection/cursor management
├── main/                       # Built-in plugins (always loaded)
│   ├── format/               # Bold, italic, underline, strikethrough
│   ├── heading/               # H1-H6, paragraph
│   ├── list/                  # Ordered, unordered, checklist
│   ├── link/                  # Hyperlink management
│   ├── table/                 # Table insert/edit/delete
│   ├── image/                 # Image embedding
│   ├── align/                 # Text alignment
│   └── sanitize/             # DOMPurify-based sanitization
├── others/                     # Optional plugins (loaded per context)
│   ├── collaboration/          # Real-time co-editing via Odoo Bus
│   ├── embedded_components/    # Odoo record embedding (form, kanban)
│   ├── qweb_plugin/           # QWeb template insertion
│   └── dynamic_placeholder/   # Dynamic content placeholders
├── components/                 # UI components
│   ├── toolbar/               # Formatting toolbar
│   ├── media_dialog/          # Media picker dialog
│   └── link_popover/          # Enhanced link editing popover
└── services/
    └── html_editor_service.js  # Odoo web service integration
```

### 1.2 Plugin System Internals

Every plugin extends the base `Plugin` class:

```javascript
// html_editor/static/src/core/plugin.js (conceptual)
class Plugin {
    constructor(editor) {
        this.editor = editor;
        this._beforeEnter = [];
        this._afterEnter = [];
    }

    /**
     * Lifecycle: called before content is inserted into the DOM.
     * Use for sanitization, transformation.
     */
    beforeInput(event) {
        for (const handler of this._beforeEnter) {
            handler(event);
        }
    }

    /**
     * Lifecycle: called after content is inserted.
     * Use for post-processing, focus management.
     */
    afterInput(event) {
        for (const handler of this._afterEnter) {
            handler(event);
        }
    }

    /**
     * Called when the toolbar button is clicked.
     */
    execute(command, value) { }

    /**
     * Update toolbar state based on current selection.
     */
    activate() { }
}
```

**Key design decisions:**

1. **Plugin composition**: Plugins are composed via dependency injection. The editor holds all plugin instances and dispatches events to them in order.

2. **Command pattern**: All formatting operations go through a normalized `execCommand(name, value)` interface, making it trivial to add new formatting options.

3. **Observer pattern**: Plugins register lifecycle hooks (`_beforeEnter`, `_afterEnter`) without modifying each other.

### 1.3 Collaboration via Odoo Bus

Real-time co-editing uses the Odoo Bus (`bus.bus`) for message passing:

```javascript
// Collaboration plugin (conceptual)
class CollaborationPlugin extends Plugin {
    setup() {
        this._super();
        this.channel = `html_editor_collaboration:${this.editor.options.resModel}:${this.editor.options.resId}`;
    }

    start() {
        this.env.bus.addEventListener('notification', this._onBusNotification.bind(this));
        this.env.services.bus.start();
        this._subscribeToChannel();
    }

    _subscribeToChannel() {
        this.env.services.rpc('/bus/im/subscribe', {
            channels: [this.channel],
        });
    }

    _onBusNotification(event) {
        const [channel, message] = event.detail;
        if (channel !== this.channel) return;
        this._applyRemoteChange(message);
    }

    _applyRemoteChange(change) {
        // Apply remote cursor positions, content patches
        this.editor.applyPatch(change.patch);
        this._updateCursors(change.cursors);
    }
}
```

The server publishes changes via `mail.thread` message mechanism, enabling the same infrastructure used for chatters and notifications.

### 1.4 Powerbox (Command Palette)

The powerbox provides a keyboard-driven interface for inserting content:

```
User types "/" in the editor
    ↓
Powerbox overlay appears with filtered command list
    ↓
Arrow keys navigate, Enter inserts
    ↓
Plugin handles insertion
```

Commands are defined per plugin:

```javascript
// Example powerbox command registration
registerCommand({
    id: 'insertTable',
    name: 'Insert Table',
    icon: 'fa-table',
    description: 'Insert a table',
    action: (editor) => {
        editor.execCommand('insertTable', { rows: 3, cols: 3 });
    },
    sequence: 10,
});
```

### 1.5 DOMPurify Sanitization

All HTML content is sanitized before storage using DOMPurify, a mature XSS prevention library:

```javascript
// From: html_editor/static/src/main/sanitize/sanitize.js
const ALLOWED_TAGS = [
    'p', 'br', 'span', 'strong', 'em', 'u', 's',
    'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'li',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'a', 'img', 'div', 'blockquote', 'pre', 'code',
    // Odoo-specific
    'o-table', 'o-colorpicker', 'o-mail-emoji',
];

const ALLOWED_ATTR = [
    'href', 'src', 'alt', 'title', 'class', 'style',
    'target', 'rel', 'data-oe-model', 'data-oe-id',
    'data-oe-field', 'data-oe-type',
];

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    // Force all links to open in new tab and add noopener
    if (node.tagName === 'A') {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
    }
});

function sanitize(html) {
    return DOMPurify.sanitize(html, {
        ALLOWED_TAGS,
        ALLOWED_ATTR,
        ALLOW_DATA_ATTR: false,
        FORBID_TAGS: ['script', 'style', 'iframe'],
    });
}
```

The server-side also applies sanitization via `html_field_history_mixin` requiring `sanitize=True` on all versioned fields.

### 1.6 History Tracking: HtmlFieldHistoryMixin

The `html_field_history_mixin` (`models/html_field_history_mixin.py`) provides automatic version history for HTML fields using diff-based storage.

#### Data Model

```python
class HtmlFieldHistoryMixin(models.AbstractModel):
    _name = 'html.field.history.mixin'
    _html_field_history_size_limit = 300  # revisions per field

    # Stores patch + metadata per revision, NOT full content
    html_field_history = fields.Json(prefetch=False)

    # Computed: same structure minus the patch (for display)
    html_field_history_metadata = fields.Json(compute='_compute_metadata')
```

**Why `prefetch=False`?** When the ORM prefetches fields, it loads all stored JSON for every record in the browse set. For records with large HTML histories (megabytes of diffs), this causes memory bloat. `prefetch=False` defers loading until the field is explicitly accessed in Python.

#### How Revisions Are Recorded

The `write()` override intercepts saves and generates diffs:

```python
def write(self, vals):
    # Step 1: Snapshot current values BEFORE write (and before sanitize)
    rec_db_contents = {}
    versioned_fields = self._get_versioned_fields()
    vals_contain_versioned_fields = set(vals).intersection(versioned_fields)

    if vals_contain_versioned_fields:
        for rec in self:
            rec_db_contents[rec.id] = {f: rec[f] for f in versioned_fields}

    # Step 2: Perform the actual write (HTML gets sanitized here)
    write_result = super().write(vals)

    if not vals_contain_versioned_fields:
        return write_result

    # Step 3: Generate patch between pre-write and post-write content
    for rec in self:
        new_revisions = False
        history_revs = rec.html_field_history or {}

        for field in versioned_fields:
            old_content = rec_db_contents[rec.id].get(field) or ""
            new_content = rec[field] or ""

            if new_content != old_content:
                patch = generate_patch(new_content, old_content)
                revision_id = (
                    (history_revs[field][0]["revision_id"] + 1)
                    if history_revs[field]
                    else 1
                )
                history_revs[field].insert(0, {
                    "patch": patch,
                    "revision_id": revision_id,
                    "create_date": self.env.cr.now().isoformat(),
                    "create_uid": self.env.uid,
                    "create_user_name": self.env.user.name,
                })
                # Enforce size limit
                history_revs[field] = history_revs[field][:rec._html_field_history_size_limit]
                new_revisions = True

        if new_revisions:
            # Second write to persist the history
            super(HtmlFieldHistoryMixin, rec).write({
                "html_field_history": history_revs
            })

    return write_result
```

#### Key Implementation Notes

1. **sanitize=True required**: The mixin enforces that all versioned fields have `sanitize=True`. This is critical because patches are generated from sanitized content, not raw input.

2. **Patch format**: The `diff_utils.py` uses a custom patch format with line-based operations:
   - `+@pos,<end>:text` — insert text at position
   - `-@pos,<end>` — delete text at position
   - `R@pos,<end>:text` — replace text at position

3. **Restoration via apply_patch**: To reconstruct content at revision N, the system starts from current content and applies patches in reverse order (newest to oldest) until reaching the target revision.

4. **Security via `cr.now()`**: Uses `self.env.cr.now()` instead of `fields.Datetime.now()` to get server-side time directly from the database connection cursor.

### 1.7 Embedded Components

The `embedded_components` plugin lets users embed Odoo views (form, kanban, list) directly inside HTML content:

```javascript
// Concept: embedded_components plugin
class EmbeddedComponentsPlugin extends Plugin {
    handleEmbeddedView(node) {
        // Intercept clicks on embedded elements
        if (node.hasAttribute('data-oe-embedded-view')) {
            const model = node.getAttribute('data-oe-model');
            const viewType = node.getAttribute('data-oe-view-type');
            const resId = node.getAttribute('data-oe-id');

            this.env.services.dialog.add(FormViewDialog, {
                resModel: model,
                resId: parseInt(resId),
            });
        }
    }
}
```

### 1.8 Asset Bundles

The HTML editor uses carefully curated asset bundles to deliver only what's needed:

| Bundle | Used In | Key Contents |
|--------|---------|-------------|
| `html_editor.assets_editor` | Backend form fields | Full editor + all plugins |
| `html_editor.assets_readonly` | Public pages | View-only rendering, no toolbar |
| `html_editor.assets_media_dialog` | Backend + Frontend | Media picker, image cropper |
| `html_editor.assets_image_cropper` | Image editing | Cropper.js + WebGL filters |
| `html_editor.assets_history_diff` | History panel | diff2html library for side-by-side diffs |
| `html_editor.assets_prism` | Code blocks | Prism.js syntax highlighting |

This separation ensures the backend loads only the editor code it needs, while the frontend loads a minimal read-only renderer.

---

## 2. IoT Driver Framework

**Module:** `iot_drivers` (runs on IoT box) | **Key files:** `main.py`, `driver.py`, `websocket_client.py`, `event_manager.py`

### 2.1 System Overview

The IoT framework enables bidirectional communication between the Odoo server and hardware devices connected to an IoT box (typically a Raspberry Pi running the IoT box image). The system is split into two parts:

- **Server side** (`iot_base` module): Odoo backend that manages device registration, sends commands, and receives events
- **Box side** (`iot_drivers` module): Python daemon running on the IoT box that discovers devices, executes commands, and maintains a WebSocket connection to the server

```
┌──────────────────────────────────┐     WebSocket TLS     ┌──────────────────────┐
│       Odoo Server                │◄────────────────────►│   IoT Box (RPi)       │
│  ┌────────────────────────────┐  │                      │  ┌────────────────┐  │
│  │ iot_base module            │  │                      │  │ Manager Thread  │  │
│  │  - Device management UI    │  │                      │  │  (main.py)     │  │
│  │  - /iot/setup endpoint     │  │                      │  │  - Registers   │  │
│  │  - WebSocket channel       │  │                      │  │  - Monitors    │  │
│  └────────────────────────────┘  │                      │  │  - Schedules   │  │
│                                  │                      │  └───────┬────────┘  │
└──────────────────────────────────┘                      │          │            │
                                                            │  ┌───────▼────────┐  │
┌──────────────────────────────────┐                      │  │ WebsocketClient  │  │
│  IoT Handlers (downloaded)     │                      │  │  (websocket)     │  │
│  ┌────────────────────────────┐  │                      │  └────────────────┘  │
│  │ printer_driver_L.py        │  │                      │                      │
│  │ serial_scale_driver.py    │  │                      │  ┌────────────────┐  │
│  │ display_driver_L.py        │  │                      │  │ Driver Threads │  │
│  └────────────────────────────┘  │                      │  │ (per device)   │  │
└──────────────────────────────────┘                      │  └────────────────┘  │
                                                            │                      │
┌──────────────────────────────────┐                      │  ┌────────────────┐  │
│  Hardware Interfaces             │                      │  │  Interface     │  │
│  ┌────────────────────────────┐  │                      │  │  Threads        │  │
│  │ USB Interface (Linux)     │  │                      │  │  (per port)    │  │
│  │ Serial Interface          │  │                      │  └────────────────┘  │
│  │ Network Interface         │  │                      └──────────────────────┘
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

### 2.2 Manager Thread (main.py)

The `Manager` class runs as a daemon thread on the IoT box and orchestrates the entire lifecycle:

```python
class Manager(Thread):
    ws_channel = ""  # WebSocket channel assigned by Odoo server

    def run(self):
        # 1. IoT Box setup (Raspberry Pi specific)
        if IS_RPI:
            # Remount root FS as writable (IoT image mounts it read-only)
            subprocess.run(["sudo", "mount", "-o", "remount,rw", "/"], check=False)
            subprocess.run(["sudo", "mount", "-o", "remount,rw", "/root_bypass_ramdisks/"], check=False)
            # Reconnect WiFi if configured
            wifi.reconnect(
                helpers.get_conf('wifi_ssid'),
                helpers.get_conf('wifi_password')
            )

        # 2. Start nginx for local web interface
        helpers.start_nginx_server()

        # 3. Log IoT box version
        _logger.info("IoT Box Image version: %s", helpers.get_version(detailed_version=True))

        # 4. Ensure correct git branch
        upgrade.check_git_branch()

        # 5. Generate and set Odoo server password
        if IS_RPI and helpers.get_odoo_server_url():
            helpers.generate_password()

        # 6. Ensure TLS certificate validity
        certificate.ensure_validity()

        # 7. Register IoT box in database BEFORE downloading handlers
        # (handlers cannot be downloaded if box is not registered)
        self._send_all_devices()

        # 8. Download and load custom device handlers from Odoo server
        helpers.download_iot_handlers()
        helpers.load_iot_handlers()

        # 9. Start interface listeners (USB, Serial, Network)
        for interface in interfaces.values():
            interface().start()

        # 10. Schedule daily maintenance tasks
        schedule.every().day.at("00:00").do(certificate.ensure_validity)
        schedule.every().day.at("00:00").do(helpers.reset_log_level)
        schedule.every().day.at("00:00").do(upgrade.check_git_branch)

        # 11. Establish WebSocket connection
        ws_client = WebsocketClient(self.ws_channel)
        if ws_client:
            ws_client.start()

        # 12. Main monitoring loop (every 3 seconds)
        while True:
            try:
                if self._get_changes_to_send():
                    self._send_all_devices()
                if IS_RPI and helpers.get_ip() != '10.11.12.1':
                    wifi.reconnect(
                        helpers.get_conf('wifi_ssid'),
                        helpers.get_conf('wifi_password')
                    )
                time.sleep(3)
                schedule.run_pending()
            except Exception:
                # Manager loop must never crash
                _logger.exception("Manager loop unexpected error")
```

#### Device Change Detection

The `_get_changes_to_send()` method efficiently detects what changed:

```python
def _get_changes_to_send(self):
    current_devices = set(iot_devices.keys()) | set(unsupported_devices.keys())
    previous_devices = (set(self.previous_iot_devices.keys()) |
                        set(self.previous_unsupported_devices.keys()))
    if current_devices != previous_devices:
        # Device added or removed
        self.previous_iot_devices = iot_devices.copy()
        self.previous_unsupported_devices = unsupported_devices.copy()
        return True

    # IP address change
    new_domain = self._get_domain()
    if self.domain != new_domain:
        self.domain = new_domain
        return True

    # Version change (e.g., after IoT box software update)
    new_version = helpers.get_version(detailed_version=True)
    if self.version != new_version:
        self.version = new_version
        return True

    return False
```

#### Device Registration

`_send_all_devices()` posts IoT box info to the Odoo server:

```python
def _send_all_devices(self, server_url=None):
    iot_box = {
        'identifier': self.identifier,       # Unique per IoT box hardware
        'mac': helpers.get_mac_address(),
        'ip': self.domain,                    # e.g., 192-168-1-1.example.com
        'token': helpers.get_token(),         # Auth token for WebSocket
        'version': self.version,              # IoT box image version
    }
    devices_list = {}
    for device in self.previous_iot_devices.values():
        devices_list[device.device_identifier] = {
            'name': device.device_name,
            'type': device.device_type,       # printer, scale, camera, payment
            'manufacturer': device.device_manufacturer,
            'connection': device.device_connection,  # usb, serial, network
            'subtype': (device.device_subtype
                        if device.device_type == 'printer' else ''),
        }
    devices_list.update(self.previous_unsupported_devices)

    # Retry up to 5 times with exponential backoff
    delay = .5
    for attempt in range(1, 6):
        try:
            response = requests.post(
                server_url + "/iot/setup",
                json={'params': {'iot_box': iot_box, 'devices': devices_list}},
                timeout=5,
            )
            response.raise_for_status()
            self.ws_channel = response.json().get('result', '')
            break
        except requests.exceptions.RequestException:
            if attempt < 5:
                time.sleep(delay)
                delay *= 2  # Exponential backoff
```

### 2.3 Driver Base Class (driver.py)

The `Driver` class is the foundation for all hardware drivers. Every driver subclass is automatically registered via `__init_subclass__`:

```python
class Driver(Thread):
    """Hook to register the driver into the drivers list."""
    connection_type = ''    # Override: 'usb', 'serial', 'network', 'bluetooth'
    priority = 0            # Higher priority drivers are tried first

    def __init__(self, identifier, device):
        super().__init__(daemon=True)
        self.dev = device
        self.device_identifier = identifier
        self.device_name = ''
        self.device_connection = ''
        self.device_type = ''
        self.device_manufacturer = ''
        self.data = {'value': '', 'result': ''}
        self._actions = {}          # action_name -> method
        self._stopped = Event()
        self._recent_action_ids = LRU(256)  # Deduplication cache

    def __init_subclass__(cls):
        """Auto-registration: every Driver subclass joins the drivers list."""
        super().__init_subclass__()
        if cls not in drivers:
            drivers.append(cls)
```

#### Auto-registration Pattern

The `__init_subclass__` hook means that simply defining a subclass registers it:

```python
# Any module can define a custom driver — it auto-joins the registry
class PrinterDriver(Driver):
    connection_type = 'usb'
    priority = 10

    @classmethod
    def supported(cls, device):
        # Check vendor/product IDs
        return device.get('vendor_id') == '0x04b8'

# Now `PrinterDriver` is in `drivers` automatically
```

#### Action Dispatch

The `action()` method dispatches incoming commands to registered handler methods:

```python
@toggleable
def action(self, data):
    """Execute an action on the device.

    :param dict data: Contains 'action' (method name), 'action_unique_id',
                      'session_id', and action-specific parameters.
    """
    action = data.get('action', '')
    action_unique_id = data.get('action_unique_id')

    # Deduplication: ignore duplicate action IDs
    if action_unique_id in self._recent_action_ids:
        _logger.warning("Duplicate action %s id %s received, ignoring",
                        action, action_unique_id)
        return
    self._recent_action_ids[action_unique_id] = action_unique_id

    self.data["owner"] = data.get('session_id')
    base_response = {
        'action_args': {**data},
        'session_id': data.get('session_id'),
    }

    try:
        result = self._actions[action](data)
        response = {
            'status': 'success',
            'result': result,
            **base_response,
        }
    except Exception as e:
        if action_unique_id:
            self._recent_action_ids.pop(action_unique_id, None)
        _logger.exception("Error executing action %s with params %s", action, data)
        response = {
            'status': 'error',
            'result': str(e),
            **base_response,
        }

    # Printers and payment terminals handle their own events
    # (paper low, waiting for card, etc.) via polling
    if self.device_type not in ["printer", "payment"]:
        event_manager.device_changed(self, response)
```

#### LRU Cache for Action Deduplication

The `_recent_action_ids` LRU cache prevents duplicate actions from being processed twice if the Odoo server retries a request. Once an action ID is processed, it's cached for the lifetime of the driver thread.

### 2.4 WebSocket Client (websocket_client.py)

The `WebsocketClient` maintains a persistent TLS WebSocket connection to the Odoo server:

```python
class WebsocketClient(Thread):
    def __init__(self, channel, server_url=None):
        self.channel = channel
        self.last_message_id = int(helpers.get_conf('last_websocket_message_id') or 0)
        self.server_url = server_url
        # Convert HTTP URL to WS URL
        url_parsed = urllib.parse.urlsplit(server_url)
        scheme = url_parsed.scheme.replace("http", "ws", 1)
        self.websocket_url = urllib.parse.urlunsplit(
            (scheme, url_parsed.netloc, 'websocket', '', ''))
        super().__init__(daemon=True)

    def run(self):
        if self.db_name:
            # Obtain session cookie from Odoo login
            session_response = requests.get(
                self.server_url + "/web/login?db=" + self.db_name,
                allow_redirects=False, timeout=10,
            )
            if session_response.status_code in [200, 302]:
                self.session_id = session_response.cookies['session_id']

        self.ws = websocket.WebSocketApp(
            self.websocket_url,
            header={
                "User-Agent": "OdooIoTBox/1.0",
                "Cookie": f"session_id={self.session_id}",
            },
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=on_error,
            on_close=self.on_close,
        )

        # Reconnect automatically on disconnect (reconnect=10 seconds)
        while True:
            try:
                self.ws.run_forever(reconnect=10)
            except Exception:
                _logger.exception("Unexpected exception in WebSocket")
            time.sleep(10)
```

#### Message Types Handled

The WebSocket client dispatches incoming messages by type:

| Type | Handler | Description |
|------|---------|-------------|
| `iot_action` | Dispatches to device driver | Odoo server sends command to device |
| `server_clear` | Disconnect and reconnect | Database was cleared |
| `server_update` | Update configuration | New server URL received |
| `restart_odoo` | Restart Odoo service | Software update applied |
| `webrtc_offer` | Answer video call | Remote display camera support |
| `remote_debug` | Toggle ngrok tunnel | Developer remote debugging |
| `test_connection` | Network quality check | Latency measurement |
| `bundle_changed` | Check git branch | Detects database upgrade |

### 2.5 Event Manager (event_manager.py)

The `EventManager` provides a pub/sub system for device events:

```python
class EventManager:
    def __init__(self):
        self.events = []        # All recent events
        self.sessions = {}     # Active polling sessions by client

    def device_changed(self, device, data=None):
        """Publish a device event to all subscribed sessions."""
        data = data or (request.params.get('data', {}) if request else {})

        event = {
            **device.data,
            'device_identifier': device.device_identifier,
            'time': time.time(),
            **data,
        }

        # Forward to WebRTC client if active
        if webrtc_client:
            webrtc_client.send(event)

        self.events.append(event)

        # Wake up any longpolling sessions subscribed to this device
        for session_id, session in self.sessions.items():
            session_devices = session['devices']
            if (any(d in [device.device_identifier, device.device_type]
                    for d in session_devices)
                and not session['event'].is_set()):
                session['result'] = event
                session['event'].set()  # Wake up the polling request

    def add_request(self, listener):
        """Register a new longpolling listener session."""
        session_id = listener['session_id']
        session = {
            'session_id': session_id,
            'devices': listener['devices'],
            'event': Event(),       # Threading Event for blocking wait
            'result': {},
            'time_request': time.time(),
        }
        self._delete_expired_sessions(ttl=70)
        self.sessions[session_id] = session
        return session
```

### 2.6 Certificate Management

TLS certificates are managed by `iot_drivers/tools/certificate.py`:

```python
def ensure_validity():
    """Check and renew the IoT box TLS certificate.

    Certificates are used for:
    1. HTTPS communication with the Odoo server
    2. mTLS (mutual TLS) authentication of the IoT box
    3. Secure WebSocket connection

    Runs daily via schedule.every().day.at("00:00").
    """
    cert_path = helpers.get_conf('cert_path')
    if not cert_path or not os.path.exists(cert_path):
        _generate_certificate()
        return

    # Check expiration
    cert = load_pem_x509_certificate(open(cert_path, 'rb').read())
    if cert.not_valid_after_utc < datetime.now(timezone.utc) + timedelta(days=30):
        _generate_certificate()
```

### 2.7 Practical Extension Point

To create a custom IoT driver:

```python
from odoo.addons.iot_drivers.driver import Driver
from odoo.addons.iot_drivers.tools.helpers import toggleable

class MyScaleDriver(Driver):
    connection_type = 'serial'
    priority = 20  # Higher than default drivers

    @classmethod
    def supported(cls, device):
        # Check if this device is a supported scale
        return (
            device.get('connection_type') == 'serial'
            and device.get('manufacturer') == 'MyScaleCo'
        )

    def __init__(self, identifier, device):
        super().__init__(identifier, device)
        self.device_name = device.get('name', 'My Scale')
        self.device_type = 'scale'
        self.device_manufacturer = 'MyScaleCo'
        self.device_connection = 'serial'
        self._actions = {
            'get_weight': self._action_get_weight,
            'tare': self._action_tare,
            'calibrate': self._action_calibrate,
        }

    @toggleable
    def _action_get_weight(self, data):
        """Read current weight from scale."""
        raw = self._read_serial()
        return self._parse_weight(raw)

    @toggleable
    def _action_tare(self, data):
        """Set tare (zero) on scale."""
        return self._send_command('TARE')
```

---

## 3. WebAuthn Passkey Internals

**Module:** `auth_passkey` | **Key files:** `models/auth_passkey_key.py`

### 3.1 What Are Passkeys?

Passkeys implement the FIDO2/WebAuthn standard using asymmetric cryptography:

- **Private key**: Stored on user's device (phone, laptop, security key)
- **Public key**: Stored in the Odoo database
- **Challenge-response**: Server sends random challenge, device signs it with private key

This eliminates phishing, credential theft, and replay attacks. Even if the Odoo database is compromised, attackers cannot use stored public keys to authenticate.

### 3.2 Architecture

```
User Browser (WebAuthn API)                    Odoo Server
────────────────────────────                  ───────────────
1. User clicks "Login with Passkey"  ────────►  2. _start_auth() generates challenge
                                            ◄──── 3. Returns authentication options

4. navigator.credentials.get() prompts user
5. User verifies (biometric/PIN)

6. Returns signed assertion  ──────────────►  7. _verify_auth() validates
                                            ◄──── 8. Session established
```

### 3.3 Registration Flow

```python
@api.model
def _start_registration(self):
    """Generate registration options sent to the browser.

    The browser uses these options to prompt the user to create a passkey.
    """
    registration_options = json.loads(options_to_json(generate_registration_options(
        rp_id=url_parse(self.get_base_url()).host,
        rp_name='Odoo',
        user_id=str(self.env.user.id).encode(),
        user_name=self.env.user.login,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,
            # The authenticator MUST store the credential
            # (enables passwordless login from any device)
            user_verification=UserVerificationRequirement.REQUIRED,
            # User MUST verify with biometric/PIN before use
        )
    )))
    # Store challenge in session — consumed on verification
    request.session['webauthn_challenge'] = registration_options['challenge']
    return registration_options

@api.model
def _verify_registration_options(self, registration):
    """Verify the registration response from the browser.

    This confirms the passkey was created by a legitimate authenticator
    for this specific RP (Relying Party / Odoo instance).
    """
    parsed_url = url_parse(self.get_base_url())
    verification = verify_registration_response(
        credential=registration,
        expected_challenge=base64url_to_bytes(self._get_session_challenge()),
        expected_origin=parsed_url.replace(path='').to_url(),
        expected_rp_id=parsed_url.host,
        require_user_verification=True,
    )
    return {
        'credential_id': verification.credential_id,      # Stored for auth lookup
        'credential_publickey': verification.credential_publickey,  # Stored for verification
    }
```

### 3.4 Credential Storage

```python
class AuthPasskeyKey(models.Model):
    _name = 'auth.passkey.key'

    name = fields.Char(required=True)  # User-friendly label: "MacBook Pro Touch ID"
    credential_identifier = fields.Char(required=True)  # base64url-encoded credential ID
    public_key = fields.Char(           # Stored separately from ORM
        required=True,
        groups='base.group_system',    # Hidden from regular users
        compute='_compute_public_key',
        inverse='_inverse_public_key',  # Empty inverse — no ORM storage
    )
    sign_count = fields.Integer(
        default=0,
        groups='base.group_system',
        # Incremented after each auth — prevents replay attacks
    )
    create_uid = fields.Many2one('res.users', index=True)

    _unique_identifier = models.Constraint(
        'UNIQUE(credential_identifier)',
        'The credential identifier should be unique.',
    )
```

**Critical design**: The `public_key` field uses an empty inverse. The actual cryptographic key is stored via raw SQL after ORM create to prevent it from being logged by the ORM:

```python
def make_key(self, registration=None):
    verification = request.env['auth.passkey.key']._verify_registration_options(
        registration
    )
    # ORM create — stores credential_id, sets create_uid
    self.env.user.write({
        'auth_passkey_key_ids': [Command.create({
            'name': self.name,
            'credential_identifier': bytes_to_base64url(
                verification['credential_id']
            ),
        })]
    })
    passkey = self.env.user.auth_passkey_key_ids[0]
    # Raw SQL for the actual public key — avoids ORM logging
    self.env.cr.execute(SQL(
        "UPDATE auth_passkey_key SET public_key = %s WHERE id = %s",
        base64.urlsafe_b64encode(verification['credential_publickey']).decode(),
        passkey.id,
    ))
```

### 3.5 Authentication Verification

```python
@api.model
def _verify_auth(self, auth, public_key, sign_count):
    """Verify the authentication assertion from the browser.

    Checks:
    1. Challenge matches session
    2. Origin (https://domain.com) matches RP ID
    3. Credential was created by this authenticator
    4. User verified identity (biometric/PIN)
    5. Sign count > stored count (prevents replay)
    """
    parsed_url = url_parse(self.get_base_url())
    auth_verification = verify_authentication_response(
        credential=auth,
        expected_challenge=base64url_to_bytes(self._get_session_challenge()),
        expected_origin=parsed_url.replace(path='').to_url(),
        expected_rp_id=parsed_url.host,
        credential_public_key=base64url_to_bytes(public_key),
        credential_current_sign_count=sign_count,
        require_user_verification=True,
    )
    return auth_verification.new_sign_count  # Update stored sign count
```

### 3.6 Session Token Recomputation

When a passkey is added or deleted, the session token must be invalidated and recomputed because the token computation includes passkey key IDs:

```python
# From res_users.py
def _get_session_token_fields(self):
    return super()._get_session_token_fields() | {'auth_passkey_key_ids'}

def _get_session_token_query_params(self):
    params = super()._get_session_token_query_params()
    params['select'] = SQL(
        "%s, ARRAY_AGG(key.id ORDER BY key.id DESC) "
        "FILTER (WHERE key.id IS NOT NULL) as auth_passkey_key_ids",
        params['select']
    )
    params['joins'] = SQL(
        "%s LEFT JOIN auth_passkey_key key ON res_users.id = key.create_uid",
        params['joins']
    )
    return params
```

This ensures a stolen passkey cannot be used with any existing session.

### 3.7 Identity Check Requirement

Both creating and deleting passkeys require the user to re-authenticate via `check_identity`:

```python
@check_identity
def action_delete_passkey(self):
    """Delete a passkey after confirming user identity."""
    for key in self:
        if key.create_uid.id == self.env.user.id:
            self.env.user.write({
                'auth_passkey_key_ids': [Command.delete(key.id)]
            })
            new_token = self.env.user._compute_session_token(
                request.session.sid
            )
            request.session.session_token = new_token
```

---

## 4. PEPPOL E-Invoicing

**Module:** `account_peppol` | **Key file:** `models/res_company.py`

### 4.1 What is PEPPOL?

PEPPOL (Pan-European Public Procurement OnLine) is a network for exchanging electronic documents using standardized UBL 2.1 format. It is mandatory for B2G (business-to-government) invoicing in most EU countries and growing for B2B.

Odoo 19's PEPPOL integration handles:
- Registration as a PEPPOL participant
- Sending invoices in Peppol BIS Billing 3.0 UBL format
- Receiving invoices from other PEPPOL participants
- Automatic endpoint discovery via the PEPPOL SMP (Service Metadata Publisher)

### 4.2 Participant Registration State Machine

```python
account_peppol_proxy_state = fields.Selection([
    ('not_registered', 'Not registered'),
    ('sender', 'Can send but not receive'),
    ('smp_registration', 'Can send, pending registration to receive'),
    ('receiver', 'Can send and receive'),
    ('rejected', 'Rejected'),
], string='PEPPOL status', default='not_registered')
```

The registration wizard guides companies through identification, contact details, endpoint selection, and SMP registration.

### 4.3 Endpoint Rules Per Country

PEPPOL endpoints use different identification schemes depending on the country. The `res_company.py` defines validation rules:

```python
# Validation rules: EAS code -> validation function
PEPPOL_ENDPOINT_RULES = {
    '0007': _cc_checker('se', 'orgnr'),   # Sweden: 10-digit org number
    '0088': ean.is_valid,                  # Generic: EAN-13
    '0184': _cc_checker('dk', 'cvr'),      # Denmark: CVR number
    '0192': _cc_checker('no', 'orgnr'),   # Norway: 9-digit org number
    '0208': _cc_checker('be', 'vat'),      # Belgium: 10-digit VAT
}
```

The `_cc_checker` helper uses the `stdnum` library to validate against country-specific registries:

```python
def _cc_checker(country_code, code_type):
    """Create a validator for a specific country/number type."""
    return lambda endpoint: get_cc_module(country_code, code_type).is_valid(endpoint)
```

For countries where validation is optional (warning only):

```python
PEPPOL_ENDPOINT_WARNINGS = {
    '0151': _cc_checker('au', 'abn'),     # Australia
    '0201': lambda ep: bool(re.match('[0-9a-zA-Z]{6}$', ep)),  # Greece: 6-char code
    '0210': _cc_checker('it', 'codicefiscale'),   # Italy: personal tax code
    '0211': _cc_checker('it', 'iva'),     # Italy: VAT number
}
```

Endpoint sanitizers normalize input before validation:

```python
PEPPOL_ENDPOINT_SANITIZERS = {
    '0007': _re_sanitizer(r'\d{10}'),   # Sweden: extract 10 digits
    '0184': _re_sanitizer(r'\d{8}'),    # Denmark: extract 8 digits
    '0192': _re_sanitizer(r'\d{9}'),    # Norway: extract 9 digits
    '0208': _re_sanitizer(r'\d{10}'),  # Belgium: extract 10 digits
}
```

### 4.4 Phone Number Validation

PEPPOL registration requires mobile number verification:

```python
def _sanitize_peppol_phone_number(self, phone_number=None):
    if not phonenumbers:
        raise ValidationError(_("Please install the phonenumbers library."))

    phone_number = phone_number or self.account_peppol_phone_number
    if not phone_number.startswith('+'):
        phone_number = f'+{phone_number}'

    phone_nbr = phonenumbers.parse(phone_number)
    country_code = phonenumbers.phonenumberutil.region_code_for_number(phone_nbr)

    if country_code not in PEPPOL_LIST or not phonenumbers.is_valid_number(phone_nbr):
        raise ValidationError(_("Invalid phone number format."))
```

Only European countries in `PEPPOL_LIST` are supported.

### 4.5 EDI Proxy Architecture

Odoo uses the `account_edi_proxy_client` infrastructure as a relay:

```
Company A (behind firewall) → Odoo EDI Proxy → PEPPOL Network → Odoo EDI Proxy → Company B
```

This allows companies without direct PEPPOL access point subscriptions to participate:

```python
account_peppol_edi_user = fields.Many2one(
    'account_edi_proxy_client.user',
    string='PEPPOL EDI User',
    compute='_compute_account_peppol_edi_user',
)

@api.depends('account_edi_proxy_client_ids')
def _compute_account_peppol_edi_user(self):
    for company in self:
        company.account_peppol_edi_user = company.account_edi_proxy_client_ids.filtered(
            lambda u: u.proxy_type == 'peppol'
        )
```

### 4.6 Supported Document Types

```python
def _peppol_modules_document_types(self):
    """Returns supported document types from all installed modules."""
    return {
        'default': {
            "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::"
            "Invoice##urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1":
                "Peppol BIS Billing UBL Invoice V3",
            "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2::"
            "CreditNote##urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:peppol.eu:2017:poacc:billing:3.0::2.1":
                "Peppol BIS Billing UBL CreditNote V3",
            # Self-billing variants
            "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::"
            "Invoice##urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:peppol.eu:2017:poacc:selfbilling:3.0::2.1":
                "Peppol BIS Self-Billing UBL Invoice V3",
            # Country-specific variants
            "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::"
            "Invoice##urn:cen.eu:en16931:2017#compliant#"
            "urn:fdc:nen.nl:nlcius:v1.0::2.1":
                "SI-UBL 2.0 Invoice (Netherlands)",
            "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2::"
            "Invoice##urn:cen.eu:en16931:2017#compliant#"
            "urn:xeinkauf.de:kosit:xrechnung_3.0::2.1":
                "XRechnung UBL Invoice V2.0 (Germany)",
        }
    }
```

---

## 5. Cloud Storage Architecture

**Modules:** `cloud_storage`, `cloud_storage_azure`, `cloud_storage_google`

### 5.1 Architecture Overview

The cloud storage module provides a unified API for storing Odoo `ir.attachment` files in external cloud providers instead of the local filesystem:

```
ir.attachment (ORM)
    │
    ├──► Local storage (default)
    │         └── Files stored in /filestore/<db>/...
    │
    └──► Cloud storage provider
              ├──► cloud_storage_azure: Azure Blob Storage
              │         └── Uses Azure SDK: BlobServiceClient, generate_blob_sas
              │         └── SAS v4 tokens for time-limited access
              │
              └──► cloud_storage_google: Google Cloud Storage
                        └── Uses google-cloud-storage SDK
                        └── Signed URLs via IAM service account
```

### 5.2 How It Works

**Step 1: Configuration**
Admin configures credentials in Settings:
- Azure: Storage account name + account key, OR SAS token
- Google: Service account JSON credentials, OR HMAC access key/secret

**Step 2: Storage Decision**
When `ir.attachment.create()` is called, `cloud_storage` determines the storage backend:
```python
def _determine_storage_backend(self):
    if self.env['ir.config_parameter'].sudo().get_param('cloud_storage.provider'):
        return 'cloud'  # Delegate to cloud provider
    return 'file'      # Local filestore
```

**Step 3: Upload**
File is uploaded via the provider SDK; Odoo stores the cloud URL in `ir_attachment.store_fname`:
```python
# Azure Blob Storage upload
blob_client = container_client.get_blob_client(filename)
blob_client.upload_blob(file_content)
# Store URL: https://<account>.blob.core.windows.net/<container>/<path>
```

**Step 4: Retrieval**
Attachment URLs in the mail composer point to **signed cloud storage URLs** (time-limited access tokens):
```python
def _generate_signed_url(self):
    """Generate time-limited SAS URL for Azure Blob Storage."""
    from azure.storage.blob import generate_blob_sas
    sas_token = generate_blob_sas(
        account_name=self._account_name,
        account_key=self._account_key,
        container_name=self._container,
        blob_name=blob_path,
        expiry=datetime.utcnow() + timedelta(hours=1),
    )
    return f"{base_url}?{sas_token}"
```

### 5.3 Key Benefit

Moving attachments to cloud storage offloads file I/O from the Odoo server, reducing:
- Disk usage on the Odoo server
- Backup size
- Load on the filesystem

This is especially valuable for companies with high email volumes or many document uploads.

### 5.4 Uninstall Hook

`cloud_storage_azure` has an `uninstall_hook` to clean up configuration:

```python
def _uninstall_hook(self):
    """Clean up Azure-specific configuration on module uninstall."""
    ICP = self.env['ir.config_parameter'].sudo()
    for key in ['cloud_storage_azure_account_name',
                'cloud_storage_azure_container',
                'cloud_storage_azure_sas_token']:
        ICP.set_param(key, False)
```

---

## 6. Subcontracting Portal

**Module:** `mrp_subcontracting` | **Key file:** `models/mrp_production.py`

### 6.1 Subcontracting Workflow

```
Owner/Buyer                          Subcontractor (Portal User)
──────────────                       ───────────────────────────
1. Create subcontracting PO
2. Generate MO (mrp.production)
3. Send components to subcontractor
                                      4. View MO in portal
                                      5. Record component consumption
                                      6. Mark operations done
4. Receive finished goods
5. Update stock
```

The portal interface allows subcontractors to consume components, record lot/serial numbers, and mark production done — without access to the full Odoo backend.

### 6.2 Model Extensions

The `mrp.production` model is extended with subcontracting-specific fields:

```python
class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Restricts portal access to the specific subcontractor
    subcontractor_id = fields.Many2one(
        'res.partner',
        string="Subcontractor",
        help="Used to restrict access to the portal user through Record Rules"
    )

    # Filters the product list shown in the portal
    bom_product_ids = fields.Many2many(
        'product.product',
        compute="_compute_bom_product_ids",
        help="List of Products used in the BoM, "
             "used to filter the list of products in the subcontracting portal view"
    )

    # Inverse of move_line_raw_ids for portal component recording
    move_line_raw_ids = fields.One2many(
        'stock.move.line',
        string="Detail Component",
        inverse='_inverse_move_line_raw_ids',
        compute='_compute_move_line_raw_ids',
    )

    incoming_picking = fields.Many2one(
        related='move_finished_ids.move_dest_ids.picking_id'
    )
```

### 6.3 Record Rule Security

Portal security uses `ir.rule` to enforce isolation:

```xml
<record id="rule_subcontracting_portal" model="ir.rule">
    <field name="name">Subcontractor: own productions only</field>
    <field name="model_id" ref="model_mrp_production"/>
    <field name="domain_force">
        [('subcontractor_id', '=', user.partner_id.id)]
    </field>
    <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
</record>
```

This ensures each subcontractor can only see production orders assigned to their own partner record.

### 6.4 Writeable Fields for Portal Users

The portal user can only write to specific fields. Any other field write is denied:

```python
def _get_writeable_fields_portal_user(self):
    """Fields a portal user can write on mrp.production."""
    return ['move_line_raw_ids', 'lot_producing_ids', 'qty_producing', 'product_qty']

def write(self, vals):
    if self.env.user._is_portal() and not self.env.su:
        unauthorized_fields = set(vals.keys()) - set(self._get_writeable_fields_portal_user())
        if unauthorized_fields:
            raise AccessError(_(
                "You cannot write on fields %s in mrp.production.",
                ', '.join(unauthorized_fields)
            ))
    # ... rest of write logic
```

### 6.5 Component Tracking via Move Line Inverse

The `_inverse_move_line_raw_ids` method handles portal users recording component consumption:

```python
def _inverse_move_line_raw_ids(self):
    for production in self:
        line_by_product = defaultdict(lambda: self.env['stock.move.line'])
        for line in production.move_line_raw_ids:
            line_by_product[line.product_id] |= line

        for move in production.move_raw_ids:
            move.move_line_ids = line_by_product.pop(move.product_id,
                                                      self.env['stock.move.line'])

        # Any remaining lines are for new products not in the BoM
        for product_id, lines in line_by_product.items():
            qty = sum(
                line.product_uom_id._compute_quantity(line.quantity, product_id.uom_id)
                for line in lines
            )
            move = production._get_move_raw_values(product_id, qty, product_id.uom_id)
            move['additional'] = True
            production.move_raw_ids = [(0, 0, move)]
            production.move_raw_ids.filtered(
                lambda m: m.product_id == product_id
            )[:1].move_line_ids = lines
```

### 6.6 Custom Asset Bundle

The subcontracting portal uses its own asset bundle (`mrp_subcontracting.webclient`) that includes a self-contained copy of the OWL framework, Bootstrap SCSS, and jQuery. This allows the portal to render independently from the main Odoo backend session, enabling subcontractors to work via the portal URL without a full backend login.

---

## 7. POS Self-Order

**Module:** `pos_self_order` | **Key files:** `models/pos_session.py`, `models/pos_order.py`, `models/pos_config.py`

### 7.1 Architecture Overview

The self-order system enables customers to place orders via their smartphone by scanning a QR code, without needing the POS terminal or a server.

```
┌─────────────────────────┐     QR Code      ┌──────────────────────────┐
│   POS Backend           │◄──────────────►│   Customer Smartphone      │
│   (POS app)            │                 │   (Web browser)           │
│                         │                 │                          │
│  ┌──────────────────┐  │                 │  /pos-self-order/<token>  │
│  │ QR generation    │  │                 │  Product catalog         │
│  │ for each table   │  │                 │  Cart management         │
│  └────────┬─────────┘  │                 │  Order submission        │
│           │            │                 │  Payment initiation      │
│  ┌────────▼─────────┐  │                 └────────────┬─────────────┘
│  │ Order sync      │  │                              │
│  │ via Bus/bus     │  │                              │ JSON-RPC
│  └────────┬─────────┘  │                              │
│           │            │                              ▼
└───────────┼────────────┘                    ┌──────────────────────────┐
            │                                 │   Payment Terminal      │
            ▼                                 │   (integrated)          │
┌─────────────────────────┐                   └──────────────────────────┘
│   Order appears on     │
│   POS screen in        │
│   real-time            │
└─────────────────────────┘
```

### 7.2 Session Configuration (pos_config.py)

```python
class PosConfig(models.Model):
    _inherit = "pos.config"

    # Three modes: nothing, consultation, mobile, kiosk
    self_ordering_mode = fields.Selection([
        ("nothing", "Disable"),
        ("consultation", "QR menu"),           # Browse only
        ("mobile", "QR menu + Ordering"),       # Full ordering
        ("kiosk", "Kiosk"),                    # Standalone kiosk
    ], string="Self Ordering Mode", default="nothing")

    # Service delivery: pickup at counter or delivery to table
    self_ordering_service_mode = fields.Selection([
        ("counter", "Pickup zone"),
        ("table", "Table"),
    ], string="Self Ordering Service Mode", default="counter")

    # Languages
    self_ordering_default_language_id = fields.Many2one("res.lang")
    self_ordering_available_language_ids = fields.Many2many("res.lang")

    # Images and branding
    self_ordering_image_home_ids = fields.Many2many('ir.attachment')
    self_ordering_image_background_ids = fields.Many2many('ir.attachment')

    # Default user for unauthenticated access
    self_ordering_default_user_id = fields.Many2one("res.users")
```

### 7.3 Session Data Loading (pos_session.py)

The `_load_pos_self_data_domain()` method filters which session data is sent to the self-order frontend:

```python
@api.model
def _load_pos_self_data_domain(self, data, config):
    """Only send the current session's data to self-order frontend."""
    return [('config_id', '=', config.id), ('state', '=', 'opened')]

def _load_pos_data_read(self, records, config):
    """Add self-ordering availability flag to session data."""
    read_records = super()._load_pos_data_read(records, config)
    if not read_records:
        return read_records

    record = read_records[0]
    record['_self_ordering'] = (
        self.env["pos.config"]
        .sudo()
        .search_count([
            *self.env["pos.config"]._check_company_domain(self.env.company),
            '|',
            ("self_ordering_mode", "=", "kiosk"),
            ("self_ordering_mode", "=", "mobile"),
        ], limit=1) > 0
    )
    return read_records
```

### 7.4 Order Synchronization (pos_order.py)

Orders placed via the self-order portal sync to the POS session:

```python
class PosOrder(models.Model):
    _inherit = "pos.order"

    source = fields.Selection(selection_add=[
        ('mobile', 'Self-Order Mobile'),
        ('kiosk', 'Self-Order Kiosk')
    ])

    self_ordering_table_id = fields.Many2one(
        'restaurant.table',
        string='Table reference',
        readonly=True
    )

    def _send_notification(self, order_ids):
        """Push order state changes to the POS terminal."""
        config_ids = order_ids.config_id
        for config in config_ids:
            # Notify the POS app of a new/changed order
            config.notify_synchronisation(
                config.current_session_id.id,
                self.env.context.get('device_identifier', 0)
            )
            config._notify('ORDER_STATE_CHANGED', {})

    def _send_payment_result(self, payment_result):
        """Push payment result back to the self-order frontend."""
        self.ensure_one()
        self.config_id._notify('PAYMENT_STATUS', {
            'payment_result': payment_result,
            'data': {
                'pos.order': self.read(
                    self._load_pos_self_data_fields(self.config_id),
                    load=False
                ),
            }
        })
        if payment_result == 'Success':
            self._send_order()

    def _load_pos_self_data_fields(self, config):
        """Fields sent to the self-order frontend for an order."""
        return [
            'id', 'uuid', 'name', 'display_name', 'access_token',
            'last_order_preparation_change', 'date_order', 'amount_total',
            'amount_paid', 'amount_return', 'user_id', 'amount_tax',
            'lines', 'pricelist_id', 'company_id', 'country_code',
            'sequence_number', 'session_id', 'config_id', 'currency_id',
            'currency_rate', 'is_refund', 'has_refundable_lines', 'state',
            'account_move', 'preset_id', 'floating_order_name',
            'customer_count', 'source', 'partner_id', 'email', 'mobile',
            'table_id', 'self_ordering_table_id',
        ]
```

### 7.5 Preset Orders

Preset orders allow restaurants to pre-configure common orders for quick ordering:

```python
# From: pos_self_order/models/pos_preset.py
# Presets are pre-defined product bundles with a fixed price
class PosPreset(models.Model):
    _name = 'pos.preset'

    name = fields.Char(required=True)
    product_ids = fields.Many2many('product.product')
    price = fields.Monetary()
    mail_template_id = fields.Many2one('mail.template')
```

### 7.6 IndexedDB Caching (Offline Support)

The self-order frontend uses IndexedDB to cache the product catalog:

```javascript
// Cached data structure
const cache = {
    products: [...],      // id, name, price, description, image
    categories: [...],   // id, name, sequence, parent_id
    session_config: {...}, // active products, prices, restrictions
    last_sync: timestamp,
};

// Sync strategy
async function syncWithServer() {
    if (navigator.onLine) {
        const products = await rpc('/pos-self-order/products', {
            session_token: currentToken,
        });
        await db.products.clear();
        await db.products.bulkAdd(products);
    }
}
```

This enables customers to browse the menu during temporary network outages. Orders are submitted when connectivity is restored.

---

## 8. Data Recycler

**Module:** `data_recycle` | **Key files:** `models/data_recycle_model.py`, `models/data_recycle_record.py`

### 8.1 Architecture Overview

The `data_recycle` module provides automated data lifecycle management, enabling administrators to define retention policies that automatically archive or delete records based on age and custom criteria.

```
┌──────────────────────────────────────────────────────┐
│  data.recycle.model  (retention rule definition)      │
│  ┌────────────────────────────────────────────────┐  │
│  │  res_model_id: account.move                     │  │
│  │  recycle_action: unlink (or archive)            │  │
│  │  recycle_mode: automatic (or manual)             │  │
│  │  time_field_id: invoice_date                    │  │
│  │  time_field_delta: 24                         │  │
│  │  time_field_delta_unit: months                 │  │
│  │  domain: [('state', '=', 'posted')]           │  │
│  └────────────────────────────────────────────────┘  │
│                        │                              │
│                        ▼                              │
│  Cron: _cron_recycle_records (daily)                 │
│                        │                              │
│                        ▼                              │
│  ┌────────────────────────────────────────────────┐  │
│  │  data.recycle.record  (staged for action)      │  │
│  │  Created per matching record                    │  │
│  │  User reviews in UI or auto-processes           │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### 8.2 Recycle Model Definition

```python
class DataRecycleModel(models.Model):
    _name = 'data.recycle.model'

    res_model_id = fields.Many2one(
        'ir.model',
        string='Model',
        required=True,
        ondelete='cascade'
    )
    res_model_name = fields.Char(
        related='res_model_id.model',
        string='Model Name',
        readonly=True,
        store=True
    )

    # Action: archive or unlink
    recycle_action = fields.Selection([
        ('archive', 'Archive'),
        ('unlink', 'Delete'),
    ], string="Recycle Action", default='unlink', required=True)

    # Mode: manual (review first) or automatic
    recycle_mode = fields.Selection([
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
    ], string='Recycle Mode', default='manual', required=True)

    # Time-based criteria
    time_field_id = fields.Many2one(
        'ir.model.fields',
        string='Time Field',
        domain="[('model_id', '=', res_model_id), "
               " ('ttype', 'in', ('date', 'datetime')), ('store', '=', True)]",
        ondelete='cascade',
    )
    time_field_delta = fields.Integer(string='Delta', default=1)
    time_field_delta_unit = fields.Selection([
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ], string='Delta Unit', default='months')

    # Optional domain filter
    domain = fields.Char(string="Filter", compute='_compute_domain',
                         readonly=False, store=True)

    # Manual mode notifications
    notify_user_ids = fields.Many2many('res.users', string='Notify Users')
    notify_frequency = fields.Integer(default=1)
    notify_frequency_period = fields.Selection([
        ('days', 'Days'), ('weeks', 'Weeks'), ('months', 'Months')
    ], default='weeks')
```

### 8.3 Batch Processing (Record Matching)

The `_recycle_records()` method identifies matching records in batches:

```python
def _recycle_records(self, batch_commits=False):
    """Find records matching recycle rules and stage them."""
    DR_CREATE_STEP_AUTO = 5000    # Smaller batches for auto mode
    DR_CREATE_STEP_MANUAL = 50000  # Larger batches for manual mode

    for recycle_model in self:
        # Build domain from rule + time criteria
        rule_domain = Domain(
            ast.literal_eval(recycle_model.domain)
        ) if recycle_model.domain else Domain.TRUE

        if recycle_model.time_field_id:
            delta = relativedelta(**{
                recycle_model.time_field_delta_unit:
                    recycle_model.time_field_delta
            })
            now = (fields.Date.today()
                   if recycle_model.time_field_id.ttype == 'date'
                   else fields.Datetime.now())
            rule_domain &= Domain(
                (recycle_model.time_field_id.name, '<=', now - delta)
            )

        model = self.env[recycle_model.res_model_name]
        if recycle_model.include_archived:
            model = model.with_context(active_test=False)

        records_to_recycle = model.search(rule_domain)
        records_to_create = [
            {'res_id': record.id, 'recycle_model_id': recycle_model.id}
            for record in records_to_recycle
            if record.id not in mapped_existing_records[recycle_model]
        ]

        if recycle_model.recycle_mode == 'automatic':
            for batch in split_every(DR_CREATE_STEP_AUTO, records_to_create):
                self.env['data_recycle.record'].create(batch).action_validate()
                if batch_commits:
                    self.env.cr.commit()
        else:  # manual mode
            for batch in split_every(DR_CREATE_STEP_MANUAL, records_to_create):
                self.env['data_recycle.record'].create(batch)
```

### 8.4 Record Validation and Execution

```python
class DataRecycleRecord(models.Model):
    _name = 'data_recycle.record'

    recycle_model_id = fields.Many2one('data.recycle.model')
    res_id = fields.Integer('Record ID', index=True)
    res_model_name = fields.Char(related='recycle_model_id.res_model_name')

    def _original_records(self):
        """Load the original records from the target model."""
        # Batch-load records to minimize DB round-trips
        records_per_model = defaultdict(list)
        for record in self.filtered(lambda r: r.res_model_name):
            records_per_model[record.res_model_name].append(record.res_id)

        for model, record_ids in records_per_model.items():
            recs = (self.env[model]
                    .with_context(active_test=False)
                    .sudo()
                    .browse(record_ids)
                    .exists())
            yield from recs

    def action_validate(self):
        """Execute the recycle action on all staged records."""
        record_ids_to_archive = defaultdict(list)
        record_ids_to_unlink = defaultdict(list)

        for record in self:
            original = self._original_records().get(
                (record.res_model_name, record.res_id)
            )
            if not original:
                continue  # Already deleted

            if record.recycle_model_id.recycle_action == "archive":
                record_ids_to_archive[original._name].append(original.id)
            elif record.recycle_model_id.recycle_action == "unlink":
                record_ids_to_unlink[original._name].append(original.id)

            record.unlink()  # Remove the recycle record after action

        # Batch archive/unlink
        for model_name, ids in record_ids_to_archive.items():
            self.env[model_name].sudo().browse(ids).action_archive()
        for model_name, ids in record_ids_to_unlink.items():
            self.env[model_name].sudo().browse(ids).unlink()

    def action_discard(self):
        """User manually excludes a record from recycling."""
        self.write({'active': False})
```

### 8.5 Use Cases

| Rule | Model | Time Field | Action | Purpose |
|------|-------|-----------|--------|---------|
| Draft quotations | `sale.order` | `date_order` | Delete | Clean up old quotes |
| Inactive partners | `res.partner` | `write_date` | Archive | GDPR compliance |
| Read notifications | `mail.notification` | `create_date` | Delete | Privacy cleanup |
| Old sessions | `pos.session` | `create_date` | Archive | Data retention |
| Test records | `crm.lead` | `create_date` | Delete | Test data cleanup |

---

## Cross-Module Dependencies

```
auth_passkey
  └── depends: base_setup, web
        └── Extends: res.users (auth_passkey_key_ids)

html_editor
  └── depends: base, bus, web
        └── Extends: ir.attachment, ir.ui.view, ir.http
        └── Provides: html_field_history_mixin

iot_base
  └── depends: web
        └── Server-side device management

iot_drivers
  └── depends: (standalone, IoT box only)
        └── Uses: websocket-client, certificate, helpers, wifi tools

account_peppol
  └── depends: account_edi_proxy_client, account_edi_ubl_cii
        └── Extends: res.company

cloud_storage
  └── depends: base_setup, mail
        └── Providers: cloud_storage_azure, cloud_storage_google

mrp_subcontracting
  └── depends: mrp
        └── Extends: mrp.production, stock.picking, stock.move
        └── Provides: subcontracting_portal (website controller)

pos_self_order
  └── depends: pos_restaurant, http_routing, link_tracker
        └── Extends: pos.config, pos.session, product.product
```

---

## Related Documents

- [New Features/What's New](New Features/What's New.md) — High-level feature summary
- [New Features/API Changes](New Features/API Changes.md) — API change reference
- [Core/BaseModel](BaseModel.md) — ORM model internals
- [Core/Fields](Fields.md) — Field type reference
- [Core/API](API.md) — Decorator reference
- [Patterns/Security Patterns](Security Patterns.md) — Security design
- [Patterns/Workflow Patterns](Workflow Patterns.md) — State machine patterns
- [Modules/Stock](Stock.md) — Stock and subcontracting
- [Modules/Account](Account.md) — PEPPOL and invoicing
- [Modules/MRP](MRP.md) — Manufacturing and subcontracting
- [Modules/POS](pos.md) — Point of Sale
