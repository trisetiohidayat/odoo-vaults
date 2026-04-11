# bus — Instant Messaging Bus

**Module:** `bus` | **Category:** Hidden | **Depends:** `base`, `web`
**License:** LGPL-3 | **Auto-install:** `True` | **Author:** Odoo S.A.

---

## Overview

The `bus` module is Odoo's real-time event distribution layer. It provides a pub/sub notification system that drives live UI updates across the web client, WebSocket connections, and HTTP long-polling fallback. Every interactive Odoo session depends on `bus` — it is the nervous system connecting server-side events to browser-side reactions.

> *"Instant Messaging Bus allow you to send messages to users, in live."* — `__manifest__.py` description

```
bus module dependency graph:
  base ──────► web ──────► bus
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   bus.bus model    ir.websocket       WebsocketController
   (notification     abstract model      /websocket
    storage)         (subscription       /websocket/health
                     logic)              /websocket/peek_notifications
                                         /websocket/on_closed
```

---

## Architecture

### Two Transport Layers

The bus supports two notification transports, selected automatically based on client capabilities:

| Transport | Route | Auth | Fallback Order |
|---|---|---|---|
| **WebSocket** | `POST /websocket` | `public` | Preferred |
| **HTTP Long-Polling** | `POST /websocket/peek_notifications` | `public` | Fallback |

Both ultimately read from `bus.bus` and deliver the same notification format. The WebSocket path is handled by `WebsocketConnectionHandler` in `websocket.py`. The HTTP path is a standard JSON-RPC endpoint that mimics WebSocket behavior via repeated polling.

### PostgreSQL LISTEN/NOTIFY Loop

The server-side dispatcher (`ImDispatch` daemon thread) maintains a dedicated connection to the `postgres` **system database** (not the tenant DB). It issues `LISTEN imbus` and blocks on `selector.select(TIMEOUT)` (50-second timeout). When `bus.bus` records are created, a `NOTIFY imbus, <payload>` fires on the **tenant DB**, waking the dispatcher through the system's notification mechanism. The dispatcher decodes the channel list and triggers `websocket.trigger_notification_dispatching()` for every subscribed websocket.

```
Python process (bus daemon)                PostgreSQL (system)
      │                                          │
      ├── LISTEN imbus ──────────────────────►   │
      │                                          │
      ▼ (blocks on select(50s timeout))         │
      .                                          .
      .          [COMMIT triggers NOTIFY]        .
      .          [NOTIFY imbus, payload]  ───────┤
      │                                          │
      ◄── conn.poll() returns notifies ──────────│
      │                                          │
      ├── decode payload (orjson.loads)          │
      ├── collect subscribed websockets          │
      └── trigger_notification_dispatching()      │
           └── browser receives via WS           │
```

**Critical design note:** `ImDispatch` connects to the system `postgres` database, not the tenant database. This allows the bus to receive notifications from any database on the PostgreSQL cluster, supporting multi-database scenarios. However, the `NOTIFY` is called on the **tenant DB connection** (via a separate cursor opened in the postcommit hook) — the dispatcher listens on the system DB, meaning all tenant DBs share the same notification channel name `imbus`. This is intentional: the payload includes the DB name as the first element of the channel tuple, so the dispatcher can filter which websockets (serving which database) receive each notification.

### Notification Lifecycle

```
1. _bus_send() or _sendone() called
       │
       ▼
2. Values staged in cr.precommit.data["bus.bus.values"]  (list of dicts)
       │
       ▼ (triggered at precommit hook registration)
3. bus.bus records CREATED in a single batch INSERT
       │
       ▼ (postcommit hook fires after DB commit)
4. cr.postcommit.data["bus.bus.channels"].add(channel)
       │
       ▼ (postcommit hook)
5. get_notify_payloads() builds JSON payload(s) recursively
       │
       ▼
6. New PostgreSQL connection (tenant DB): SELECT pg_notify('imbus', payload)
       │
       ▼ (notify wakes ImDispatch.loop())
7. ImDispatch relays to subscribed websockets
       │
       ▼
8. Browser receives notification, fires event on EventBus
```

---

## Models

### bus.bus — Communication Bus

**File:** `models/bus.py`

The core notification storage table. Extremely lightweight by design — only two columns besides the implicit `id` and `create_date`.

| Field | Type | Description |
|---|---|---|
| `channel` | `Char` | JSON-serialized channel identifier. Format depends on channel type (see below). |
| `message` | `Char` | JSON-serialized notification envelope: `{"type": <str>, "payload": <any>}` |

**Why `channel` and `message` are both `Char`:**
Both are stored as JSON strings. This enables direct SQL `WHERE channel IN (...)` filtering without application-level deserialization for the poll query. The JSON structures are:

- **Record channel:** `["dbname", "model_name", record_id]` — e.g., `["mydb", "res.partner", 42]`
- **Partner channel:** `["dbname", "res.partner", id]` — resolved from `res.users` via `_bus_channel()`
- **Group channel:** `["dbname", "group:base.group_user"]` — string format with `group:` prefix
- **Broadcast channel:** `["dbname", "broadcast"]` — system-wide, subscribed by all clients
- **Subchannel:** `["dbname", "model_name", record_id, "subchannel_name"]`

**Channel normalization (`channel_with_db`):**
```python
def channel_with_db(dbname, channel):
    if isinstance(channel, models.Model):        # record channel
        return (dbname, channel._name, channel.id)
    if isinstance(channel, tuple) and len(channel) == 2 and isinstance(channel[0], models.Model):  # subchannel
        return (dbname, channel[0]._name, channel[0].id, channel[1])
    if isinstance(channel, str):                 # string channel
        return (dbname, channel)
    return channel
```
This is called at both send-time (via `_sendone`) and poll-time (via `_poll`), ensuring all channels are consistently prefixed with the DB name.

#### Methods

##### `@api.autovacuum _gc_messages()` — Garbage Collector

Removes `bus.bus` rows older than `bus.gc_retention_seconds` (system parameter, default **24 hours**). Uses direct SQL:

```python
self.env.cr.execute("DELETE FROM bus_bus WHERE create_date < %s", (timeout_ago,))
```

This bypasses ORM overhead — critical because millions of rows can accumulate on high-traffic instances. No `unlink()` call, no override hooks, no `bus.bus` model recomputation triggered. Runs as an Odoo cron job via the autovacuum mechanism (decorated with `@api.autovacuum`).

**GC configuration:** The retention period is configurable via `ir.config_parameter` key `bus.gc_retention_seconds`. Default: `60 * 60 * 24` (86400 seconds = 24 hours).

##### `@api.model _sendone(target, notification_type, message)` — Low-level Unicast Send

```python
self._ensure_hooks()
channel = channel_with_db(self.env.cr.dbname, target)
self.env.cr.precommit.data["bus.bus.values"].append({
    "channel": json_dump(channel),
    "message": json_dump({"type": notification_type, "payload": message}),
})
self.env.cr.postcommit.data["bus.bus.channels"].add(channel)
```

- `target`: A channel — can be a `models.Model` record (resolved via `channel_with_db`), a tuple for subchannels, or a string channel name.
- `notification_type`: String identifier for the notification class on the client (e.g., `"livechat.message"`, `"mail.record/insert"`, `"simple_notification"`).
- `message`: Arbitrary Python object — serialized to JSON as the `payload`.

**Precommit/postcommit batching:** Multiple `_sendone` calls within the same transaction all append to `cr.precommit.data["bus.bus.values"]`. A single precommit hook fires once to do a batch `create()` when the first listener is registered. Postcommit hooks fire after commit. This means the actual DB insert happens once per transaction, not once per notification.

**Security note from code:** *"When using `_sendone` directly, `target` (if str) should not be guessable by an attacker."* String channels with predictable names can be subscribed to by any client. Use record channels or `_bus_send` for secure notifications.

##### `@api.model _poll(channels, last=0, ignore_ids=None)` — Fetch Pending Notifications

```python
if last == 0:  # first poll
    timeout_ago = fields.Datetime.now() - datetime.timedelta(seconds=TIMEOUT)
    domain = [('create_date', '>', timeout_ago)]  # last 50s of notifications
else:  # reconnect — get all unread
    domain = [('id', '>', last)]
if ignore_ids:
    domain.append(("id", "not in", ignore_ids))
channels = [json_dump(channel_with_db(self.env.cr.dbname, c)) for c in channels]
domain.append(('channel', 'in', channels))
notifications = self.sudo().search_read(domain, ["message"])
# Returns: [{id, message: {type, payload}}]
```

| Parameter | Behavior |
|---|---|
| `last=0` (first poll) | Returns all messages in the 50-second rolling window |
| `last>0` (reconnect) | Returns all notifications with `id > last` (includes old ones beyond the 50s window) |
| `ignore_ids` | Excludes specific notification IDs from results (client already processed them) |

**Timeout constant:** `TIMEOUT = 50` (line 25 of `models/bus.py`). This is the long-polling timeout and the age threshold for the first-poll buffer.

##### `_bus_last_id()` — Returns Highest Notification ID

```python
last = self.env['bus.bus'].search([], order='id desc', limit=1)
return last.id if last else 0
```

Used by `_prepare_subscribe_data` to validate the `last` parameter. If the client claims `last=N` but no notification with ID >= N exists, the server resets `last=0`. This prevents replay attacks where a client requests notifications with IDs that don't exist yet.

#### GC Behavior Matrix

| Scenario | What Happens |
|---|---|
| High traffic, default GC (24h) | `bus.bus` table can grow to millions of rows; direct SQL delete is safe but VACUUM may be heavy |
| Very short GC (e.g., 1h) | Notifications from brief disconnects (< 1h) still delivered; longer disconnects lose notifications |
| Very long GC (e.g., 7 days) | High storage; VACUUM may struggle on large tables |
| GC disabled (`gc_retention_seconds=0`) | Messages never deleted; table grows indefinitely |

---

### bus.listener.mixin — Send Notifications from Any Model

**File:** `models/bus_listener_mixin.py`

Abstract mixin (`_name = 'bus.listener.mixin'`) that adds the `_bus_send` convenience method and `_bus_channel()` hook to any model. Any model inheriting from this mixin automatically gets notification support.

```python
class BusListenerMixin(models.AbstractModel):
    _name = 'bus.listener.mixin'

    def _bus_send(self, notification_type, message, /, *, subchannel=None):
        for record in self:
            main_channel = record
            while (new_main_channel := main_channel._bus_channel()) != main_channel:
                main_channel = new_main_channel
            assert isinstance(main_channel, models.Model)
            if not main_channel:
                continue
            main_channel.ensure_one()
            channel = main_channel if subchannel is None else (main_channel, subchannel)
            self.env["bus.bus"]._sendone(channel, notification_type, message)

    def _bus_channel(self):
        return self  # default: the record itself is the channel
```

**Channel resolution loop:**
The `while` loop handles chain-based channel resolution. For example, `res.users` overrides `_bus_channel()` to return `self.partner_id`, so calling `_bus_send` on a user record resolves the channel to their partner. The loop continues until `_bus_channel()` returns itself (stable point).

**Parameters:**
- `notification_type` (positional): The notification type string.
- `message` (positional): The payload object.
- `subchannel` (keyword-only): Optional subchannel. When provided, channel becomes `(main_channel, subchannel)` — enabling multi-topic subscriptions on a single record, e.g., different event types on the same `crm.lead`.

#### Channel Resolution for Mixin Classes

| Class | Inherits | `_bus_channel()` returns | Channel becomes |
|---|---|---|---|
| `res.partner` | `bus.listener.mixin` | `self` | `("db", "res.partner", id)` |
| `res.users` | `res.users`, `bus.listener.mixin` | `self.partner_id` | `("db", "res.partner", partner_id)` |
| `res.groups` | `res.groups`, `bus.listener.mixin` | `self` | `("db", "res.groups", id)` |
| `res.users.settings` | `res.users.settings`, `bus.listener.mixin` | `self.user_id` | `("db", "res.users", user_id)` |
| `ir.attachment` | `ir.attachment`, `bus.listener.mixin` | `self.env.user` | `("db", "res.users", user_id)` |

**Note on `res.users`:** Resolves to `partner_id` because `_build_bus_channel_list` also adds `self.env.user.partner_id` as a channel for logged-in users. Notifying a user via their `res.users` record actually delivers to their partner channel.

**Why `ir.attachment` resolves to `env.user`:** Attachments are private to the uploader. Sending `_bus_send` on an attachment notifies the uploading user, not anyone else.

---

### ir.websocket — WebSocket Subscription Logic

**File:** `models/ir_websocket.py` (abstract model `_name = 'ir.websocket'`)

Handles WebSocket event processing and subscription management. This is the server-side counterpart to the browser-side `bus_service`. Mixed into `ir.http` via `ir_http.py`.

#### `_build_bus_channel_list(channels)` — Augment Channel List

```python
def _build_bus_channel_list(self, channels):
    req = request or wsrequest
    channels.append('broadcast')                   # 1. System-wide broadcast channel
    channels.extend(self.env.user.all_group_ids)  # 2. All group IDs (e.g., base.group_user)
    if req.session.uid:
        channels.append(self.env.user.partner_id) # 3. User's partner record channel
    return channels
```

Every connected client is always subscribed to `'broadcast'`. Groups are added as string channels (e.g., `"base.group_user"`). Logged-in users also subscribe to their partner record channel for person-to-person notifications.

#### `_prepare_subscribe_data(channels, last)` — Validate and Normalize

```python
if not all(isinstance(c, str) for c in channels):
    raise ValueError("bus.Bus only string channels are allowed.")
last = 0 if last > self.env["bus.bus"].sudo()._bus_last_id() else last
return {"channels": OrderedSet(self._build_bus_channel_list(list(channels))), "last": last}
```

- **Type check:** Raises `ValueError` if any channel is not a string (the `channel_with_db` function handles conversion at send/poll time, but subscription channels must be strings)
- **Replay protection:** If `last` exceeds the highest existing notification ID, reset to `0`
- **Server-side augmentation:** `_build_bus_channel_list` is called here to add `broadcast`, groups, and partner channel

#### `_subscribe(og_data)` — Register WebSocket Interest

```python
def _subscribe(self, og_data):
    data = self._prepare_subscribe_data(og_data["channels"], og_data["last"])
    dispatch.subscribe(data["channels"], data["last"], self.env.registry.db_name, wsrequest.ws)
    self._after_subscribe_data(data)
```

Calls the `ImDispatch.subscribe()` method to register the WebSocket. The `dispatch` object is the module-level singleton `ImDispatch` instance.

#### `_on_websocket_closed(cookies)` — Disconnect Hook

Override in custom modules to handle disconnection-side effects (e.g., update presence status, clear typing indicators). Called by the `/websocket/on_closed` route and from `WebsocketConnectionHandler` when the socket closes.

#### `_authenticate()` — WebSocket Authentication

```python
@classmethod
def _authenticate(cls):
    if wsrequest.session.uid is not None:
        if not security.check_session(wsrequest.session, wsrequest.env, wsrequest):
            wsrequest.session.logout(keep_db=True)
            raise SessionExpiredException()
    else:
        public_user = wsrequest.env.ref('base.public_user')
        wsrequest.update_env(user=public_user.id)
```

Authenticated sessions are verified via `security.check_session`. Unauthenticated/public connections run as `base.public_user`, meaning they receive `broadcast` and group channels but **not** partner-specific notifications.

---

### ir.model — Model Definitions for Live Synchronization

**File:** `models/ir_model.py` (extends `ir.model`)

**Method:** `_get_model_definitions(model_names_to_fetch)` — Returns field metadata for requested models

Used by the web client to synchronize field definitions after live notifications report that a model changed (e.g., a custom field was added via studio). The client calls `POST /bus/get_model_definitions` to get updated field metadata without a full page reload.

**Attributes returned per field:**
- `name`, `type`, `string` — Basic field metadata
- `relation` — Related model for relational fields (filtered: only included if related model is also in `model_names_to_fetch`)
- `required`, `readonly` — Constraints
- `selection` — Options for Selection fields
- `definition_record`, `definition_record_field`, `model_field` — For computed fields with dynamic definitions (e.g., property fields)
- `inverse_fname_by_model_name` — Inverse field names, filtered by access rights and `model_names_to_fetch`
- `model_name_ref_fname` — For `many2one_reference` fields, the name of the field holding the referenced model name

**Access filtering:** `model._has_field_access(field, 'read')` is checked for inverse fields — users only see inverse field names for models they have read access to.

---

### Models that Use bus.listener.mixin

These models extend `bus.listener.mixin` to gain `_bus_send()` capability. They are listed in `models/__init__.py`.

| Model File | Inherits | `_bus_channel()` | Purpose |
|---|---|---|---|
| `res_users.py` | `res.users` + `bus.listener.mixin` | `self.partner_id` | User-to-user notifications |
| `res_partner.py` | `res.partner` + `bus.listener.mixin` | `self` (default) | Partner record channel |
| `res_groups.py` | `res.groups` + `bus.listener.mixin` | `self` (default) | Group-based notifications |
| `res_users_settings.py` | `res.users.settings` + `bus.listener.mixin` | `self.user_id` | User settings changes |
| `ir_attachment.py` | `ir.attachment` + `bus.listener.mixin` | `self.env.user` | Attachment-related notifications |

---

## HTTP Routes

All routes are defined in `controllers/websocket.py` (`WebsocketController`) and `controllers/main.py` (`BusController`).

### WebSocket Handshake
**`POST /websocket`** — `type="http"`, `auth="public"`, `websocket=True`

Accepts the WebSocket upgrade handshake. The `version` parameter is compared against `WebsocketConnectionHandler._VERSION`. Mismatched versions cause the server to return `426 Upgrade Required`, forcing the browser to reload the worker bundle.

### Health Check
**`GET /websocket/health`** — `auth="none"`, `save_session=False`

```python
return {'status': 'pass'}  # JSON, no-store headers
```

Used by load balancers and monitoring probes. Does not check authentication, database connectivity, or WebSocket state — only confirms the HTTP endpoint is responding.

### Long-Polling Notification Peek
**`POST /websocket/peek_notifications`** — `type="jsonrpc"`, `auth="public"`

HTTP fallback for environments that cannot use WebSocket (corporate proxies, older browsers).

| Parameter | Description |
|---|---|
| `channels` | List of channel names to subscribe to |
| `last` | Last known notification ID from previous poll |
| `is_first_poll` | On first poll, sets `session['is_websocket_session'] = True` |

**Session expiry detection:** If `is_first_poll=False` but `'is_websocket_session'` is not in the session, raises `SessionExpiredException`. This catches the case where the session expired between polls.

### WebSocket Close Notification
**`POST /websocket/on_closed`** — `type="jsonrpc"`, `auth="public"`

Called by the browser when a WebSocket closes. Allows the server to clean up subscriptions proactively. Used primarily by **Odoo.sh** infrastructure (which may proxy WebSocket connections and needs to track connection lifecycle at the routing layer).

### WebSocket Worker Bundle
**`GET /bus/websocket_worker_bundle`** — `auth="public"`

Returns the bundled WebSocket worker JavaScript as a static asset. The `v` query parameter is used for cache-busting in the browser. Serves the bundle registered under `bus.websocket_worker_assets` which includes `web/static/src/module_loader.js` and all files from `bus/static/src/workers/`.

### Model Definitions
**`POST /bus/get_model_definitions`** — `auth="user"`

```python
def get_model_definitions(self, model_names_to_fetch, **kwargs):
    return json.dumps(request.env['ir.model']._get_model_definitions(
        json.loads(model_names_to_fetch)
    ))
```

The `model_names_to_fetch` parameter is sent as a JSON-encoded string in the request body (not as a JSON body), requiring `json.loads()` on the server side.

### Missed Notifications Detection
**`POST /bus/has_missed_notifications`** — `auth="public"`

```python
return request.env["bus.bus"].sudo().search_count([("id", "=", last_notification_id)]) == 0
```

Checks whether a `bus.bus` notification with a given ID still exists. If the notification was garbage-collected (deleted by GC), the client knows it missed notifications during a disconnect and must refresh from the ORM.

---

## Security

### Access Control

| Resource | read | write | create | unlink |
|---|---|---|---|---|
| `bus.bus` | 0 | 0 | 0 | 0 |

The `bus.bus` model has **all ACL flags set to `0`** in `security/ir.model.access.csv`. Direct ORM access is blocked for all users including admin. All actual access flows through:

- `_poll()` — uses `sudo()` internally to read notification records
- `_gc_messages()` — uses `self.sudo()` to delete old messages
- `_sendone()` — adds to precommit buffer; the final `create()` uses `self.sudo()`
- Direct SQL in `_gc_messages()` — bypasses ACL entirely (superuser cursor)

### WebSocket Authentication

| Session Type | Access Level |
|---|---|
| Authenticated (`session.uid` set) | `broadcast` + all groups + partner channel |
| Unauthenticated / public | `broadcast` + public group channels only |

Public users run as `base.public_user` via `_authenticate()`. They cannot receive partner-specific notifications.

### Channel Safety

The `_sendone` docstring explicitly warns: *"When using `_sendone` directly, `target` (if str) should not be guessable by an attacker."* String channels like `broadcast` are safe (anyone can receive them). A string channel like `"payment_token_123"` would be guessable and unsafe for sensitive data. Use record channels instead.

### Admin Password Warning

`controllers/home.py` overrides `Home._login_redirect` to send a real-time notification when an admin logs in with the default password `'admin'` from a non-private IP address:

```python
admin.with_context(...)._bus_send(
    "simple_notification",
    {"type": "danger", "message": "...", "sticky": True}
)
```

This uses `bus.listener.mixin` on the admin's `res.partner` record as the channel.

---

## ImDispatch Thread

**File:** `models/bus.py`

A `threading.Thread` daemon that bridges PostgreSQL LISTEN/NOTIFY to WebSocket dispatch. Initialized as a module-level singleton: `dispatch = ImDispatch()`.

```python
class ImDispatch(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True, name=f'{__name__}.Bus')
        self._channels_to_ws = {}  # channel_hash → set of websocket objects

    def subscribe(self, channels, last, db, websocket):
        channels = {hashable(channel_with_db(db, c)) for c in channels}
        for channel in channels:
            self._channels_to_ws.setdefault(channel, set()).add(websocket)
        outdated_channels = websocket._channels - channels
        self._clear_outdated_channels(websocket, outdated_channels)
        websocket.subscribe(channels, last)

    def _clear_outdated_channels(self, websocket, outdated_channels):
        for channel in outdated_channels:
            self._channels_to_ws[channel].remove(websocket)
            if not self._channels_to_ws[channel]:
                self._channels_to_ws.pop(channel)

    def loop(self):
        # Connects to SYSTEM postgres DB (not tenant DB)
        with odoo.sql_db.db_connect('postgres').cursor() as cr, \
             selectors.DefaultSelector() as sel:
            cr.execute("listen imbus")
            cr.commit()
            conn = cr._cnx
            sel.register(conn, selectors.EVENT_READ)
            while not stop_event.is_set():
                if sel.select(TIMEOUT):  # 50s timeout
                    conn.poll()
                    channels = []
                    while conn.notifies:
                        channels.extend(orjson.loads(conn.notifies.pop().payload))
                    websockets = set()
                    for channel in channels:
                        websockets.update(self._channels_to_ws.get(hashable(channel), []))
                    for websocket in websockets:
                        websocket.trigger_notification_dispatching()
```

**Lazy start:** `subscribe()` checks `if not self.is_alive()` before `self.start()`. This allows the thread to be initialized before the server is fully started.

**Error recovery:** If the loop encounters a `PoolError` or `InterfaceError` and `stop_event.is_set()` (server shutting down), it continues without sleeping. Otherwise, it logs the exception and sleeps for `TIMEOUT` (50s) before retrying. This means a database connectivity issue causes a 50-second blackout before retry.

**Cursor management:** Opens its own connection to the `postgres` system database (not the tenant DB) via `odoo.sql_db.db_connect('postgres').cursor()`. This is a separate, dedicated connection that is never shared with the ORM cursor pool.

---

## Performance Considerations

### Notification Payload Splitting

When the channel list in a single `NOTIFY` call exceeds `NOTIFY_PAYLOAD_MAX_LENGTH` (default **8000 bytes**), the payload is recursively split in half:

```python
def get_notify_payloads(channels):
    payload = json_dump(channels)
    if len(channels) == 1 or len(payload.encode()) < NOTIFY_PAYLOAD_MAX_LENGTH:
        return [payload]
    else:
        pivot = math.ceil(len(channels) / 2)
        return (get_notify_payloads(channels[:pivot]) +
                get_notify_payloads(channels[pivot:]))
```

Each chunk triggers a separate `pg_notify('imbus', chunk)`. For most deployments this never triggers. On Odoo.sh with many concurrent sessions, this protects against PostgreSQL's notification payload limits.

**Configuration:** `ODOO_NOTIFY_PAYLOAD_MAX_LENGTH` environment variable (default: 8000 bytes).

**Custom notify function:** `ODOO_NOTIFY_FUNCTION` environment variable allows replacing `pg_notify` with a custom PostgreSQL function for multi-tenant routing or logging.

### Bus Bus Table Growth

At high traffic (e.g., 10,000 connected users, livechat, stock updates, CRM changes), the `bus.bus` table sees high insert rates. The autovacuum GC keeps it manageable, but:
- The `create_date` index is used by the GC DELETE — ensure PostgreSQL `VACUUM` runs regularly
- High-frequency bursts (e.g., mass import) can cause temporary table growth between GC runs
- Direct SQL delete (`DELETE FROM bus_bus WHERE create_date < %s`) is atomic and does not trigger ORM callbacks, but holds a lock on the table

### Precommit/Postcommit Batching

Multiple `_sendone` calls within the same transaction accumulate in `cr.precommit.data["bus.bus.values"]`. The precommit hook creates records in a **single batch INSERT** (not one INSERT per notification). This minimizes DB round-trips during high-frequency notification bursts (e.g., stock moves updating many users simultaneously).

### orjson Performance

The `tools/orjson.py` wrapper provides a C-based JSON encoder/decoder when `orjson` is installed:

```python
try:
    import orjson
    def dumps(value): return orjson.dumps(value)
    def loads(value): return orjson.loads(value)
except ImportError:
    import json
    def dumps(value): return json.dumps(value, separators=(",", ":")).encode()
    def loads(value): return json.loads(value)
```

orjson is significantly faster for large payloads (model definitions, long notification lists). Both `_poll` and `ImDispatch.loop` use it for JSON serialization/deserialization.

### WebSocket Worker Threading

The `websocket.py` file implements a full WebSocket server using:
- `PollablePriorityQueue` — priority queue with `socketpair` for cross-thread notification dispatch
- `WebsocketConnectionHandler` — per-connection state machine
- `selectors.DefaultSelector()` — I/O multiplexing for many concurrent connections

Connections are stored in `WeakSet` for automatic cleanup on garbage collection. The priority queue ensures notification ordering is preserved across threads.

---

## Odoo 18 → Odoo 19 Changes

| Feature | Odoo 18 | Odoo 19 |
|---|---|---|
| **WebSocket support** | Not present | Added as preferred transport via `WebsocketConnectionHandler` |
| **HTTP long-polling** | Only transport | Still supported as fallback |
| **PostgreSQL NOTIFY payload splitting** | Not present | Added `get_notify_payloads()` for payloads > 8000 bytes |
| **Dedicated dispatcher cursor** | Used ORM cursors | `ImDispatch.loop()` opens own connection to `postgres` system DB |
| `_bus_channel()` chain resolution | Not documented | Loop-based resolution supports multi-hop chains |
| `_prepare_subscribe_data` replay protection | Not present | Validates `last` against `_bus_last_id()` |
| `orjson` tools module | Not present | Added with graceful fallback |
| `ignore_ids` in `_poll` | Not present | Added to prevent duplicate delivery |
| Long-polling session expiry detection | Not present | `is_websocket_session` flag in session |
| Model definition sync endpoint | Not present | `POST /bus/get_model_definitions` |
| Configurable GC retention | Hardcoded | `bus.gc_retention_seconds` via `ir.config_parameter` |
| Admin password warning notification | Not present | Added via `controllers/home.py` override |

---

## Auto-install Behavior

`bus` is marked `auto_install: True` with dependencies on `base` and `web`. Since `web` depends on `bus`, it is installed automatically on every standard Odoo installation. You cannot uninstall `bus` without also uninstalling `web`, which would break the web client entirely.

---

## Static Assets (Frontend)

| Bundle | Files | Used In |
|---|---|---|
| `web.assets_backend` | All `bus/static/src/*.js` | Backend web client |
| `web.assets_frontend` | All `bus/static/src/*.js` | Website / frontend |
| `web.assets_unit_tests` | `bus/static/tests/**/*` | Test suite |
| `bus.websocket_worker_assets` | `web/static/src/module_loader.js` + `bus/static/src/workers/*` | Served via `/bus/websocket_worker_bundle` |

**Assets removed per context:**
- `bus/static/src/workers/bus_worker_script.js` — removed from both backend and frontend (superseded by worker service)
- `bus/static/src/services/assets_watchdog_service.js` — removed from frontend (backend only)
- `bus/static/src/simple_notification_service.js` — removed from frontend (backend only)

The Web worker handles the WebSocket connection in a background thread, preventing blocking of the main UI thread.

---

## Key Constants

| Constant | Value | Location |
|---|---|---|
| `TIMEOUT` | `50` (seconds) | `models/bus.py` — long-polling select timeout and GC age threshold |
| `DEFAULT_GC_RETENTION_SECONDS` | `86400` (24 hours) | `models/bus.py` |
| `ODOO_NOTIFY_FUNCTION` | `'pg_notify'` (env: `ODOO_NOTIFY_FUNCTION`) | `models/bus.py` |
| `NOTIFY_PAYLOAD_MAX_LENGTH` | `8000` bytes (env: `ODOO_NOTIFY_PAYLOAD_MAX_LENGTH`) | `models/bus.py` |
| `MAX_TRY_ON_POOL_ERROR` | `10` | `websocket.py` — cursor acquisition retries |
| `DELAY_ON_POOL_ERROR` | `0.15` (seconds) | `websocket.py` — base delay between retries |
| `JITTER_ON_POOL_ERROR` | `0.3` (seconds) | `websocket.py` — random jitter range |

---

## Failure Modes

| Failure Mode | Symptom | Cause | Recovery |
|---|---|---|---|
| PostgreSQL `listen imbus` disconnects | WebSocket connections freeze | DB connection dropped (restart, network) | `ImDispatch.loop()` recovers on next iteration after sleeping 50s |
| `bus.bus` table grows unbounded | High disk usage, slow VACUUM | GC not running or `gc_retention_seconds` too high | Increase vacuum frequency or lower retention |
| WebSocket worker version mismatch | Browser shows 426, closes connection | Server restarted with new worker version | Browser auto-reloads page (handled by worker) |
| Session expired during long-poll | `SessionExpiredException` on next poll | User session timed out | Client re-authenticates and resubscribes |
| Very large notification payload | Multiple `pg_notify` calls | Many channels in one notification | Split happens automatically; possible order issues if client uses multiple channels |
| Notification GC'd before delivery | Client misses update, detects via `/bus/has_missed_notifications` | User disconnected > 24h | Client refreshes from ORM on detecting gap |
| `orjson` not installed | Slower JSON serialization | Package not in environment | Degrades gracefully to stdlib `json` |
| PoolError in ImDispatch | Dispatcher sleeps 50s, then retries | Database connection pool exhausted | `stop_event` check prevents crash on shutdown |
| PostgreSQL NOTIFY dropped | Some clients miss notification | High system load, notification buffer overflow | Client reconnect triggers `_poll` and catches up |

---

## Dependencies & Cross-Module Relations

| Model | Relation |
|---|---|
| `bus.bus` | Standalone notification table; no ORM foreign keys |
| `ir.websocket` | Mixed into `ir.http` via `ir_http.py` |
| `bus.listener.mixin` | Mixed into: `res.partner`, `res.users`, `res.groups`, `res.users.settings`, `ir.attachment` |
| `ImDispatch` | Module-level singleton; referenced by `websocket.py` and `ir_websocket.py` |
| `WebsocketConnectionHandler` | Referenced by `ir_http.py` to expose `_VERSION` in session info |

### Odoo.sh Integration

The `/websocket/on_closed` route is primarily for Odoo.sh, which proxies WebSocket connections through its own infrastructure. When a WebSocket closes, Odoo.sh needs to notify the Odoo server so it can clean up subscriptions and update any presence/availability states.

---

## Tags
`#odoo` `#odoo19` `#modules` `#real-time` `#websocket` `#bus` `#notifications` `#long-polling`