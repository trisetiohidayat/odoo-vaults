---
type: module
name: bus
version: Odoo 18
tags: [module, bus, websocket, realtime, notifications, presence]
source: ~/odoo/odoo18/odoo/addons/bus/
---

# bus

Real-time event bus — PostgreSQL pub/sub, WebSocket infrastructure, presence tracking.

**Source:** `addons/bus/`
**Depends:** `base`

---

## Architecture

```
bus.bus (PostgreSQL table)
  └─► NOTIFY imbus  (via pg_notify)
        └─► ImDispatch.loop() [Python background thread]
              └─► WebSocket.trigger_notification_dispatching()
                    └─► Client JS receives notification
                          └─► Frontend store updated
                                └─► UI re-renders
```

---

## `bus.bus` — Communication Bus

```python
class ImBus(models.Model):
    _name = 'bus.bus'
```

| Field | Type | Description |
|-------|------|-------------|
| `channel` | Char | JSON-serialized channel name/tuple |
| `message` | Char | JSON-serialized notification payload |

**Constants:**
| Constant | Value | Description |
|----------|-------|-------------|
| `TIMEOUT` | 50 seconds | Long-polling timeout |
| `DEFAULT_GC_RETENTION_SECONDS` | 86400 (24h) | Notification TTL |
| `NOTIFY_PAYLOAD_MAX_LENGTH` | 8000 bytes | Max `pg_notify` payload size |

**Key Methods:**

`_sendone(target, notification_type, message)`
```python
# Appends to precommit buffer — actual DB insert happens at commit time
self.env.cr.precommit.data["bus.bus.values"].append({
    "channel": json_dump(channel),
    "message": json_dump({"type": notification_type, "payload": message}),
})
self.env.cr.postcommit.data["bus.bus.channels"].add(channel)
```

`_poll(channels, last=0, ignore_ids=None)` — Long-polling
- `last=0`: Returns notifications from last 50 seconds
- `last>0`: Returns notifications with `id > last` (unread since last poll)
- Returns: `[{id, message: {type, payload}}]`

`_gc_messages()` — `@api.autovacuum` cron. Deletes entries older than `bus.gc_retention_seconds`. Default 24h.

**Helper Functions:**

```python
def channel_with_db(dbname, channel):
    # str channel → (dbname, channel)
    # Model record → (dbname, model._name, model.id)
    # (model, str) → (dbname, model._name, model.id, str)

def get_notify_payloads(channels):
    # Recursively splits payloads exceeding NOTIFY_PAYLOAD_MAX_LENGTH
    # Clients receive multiple payloads for one logical notification
```

**Failure Modes:**
- Transaction rollback → notification never sent (by design)
- Payload size exceeded → split into multiple `pg_notify` calls
- `ODOO_NOTIFY_FUNCTION` env var → replace `pg_notify` with custom function

---

## `bus.listener.mixin` — Abstract Mixin

```python
class BusListenerMixin(models.AbstractModel):
    _name = "bus.listener.mixin"
```

**Methods:**
```python
def _bus_send(self, notification_type, message, subchannel=None):
    # Sends to self._bus_channel() or (self._bus_channel(), subchannel)
    self.env["bus.bus"]._sendone(channel, notification_type, message)

def _bus_channel(self):
    # Override to customize channel. Default: return self
    self.ensure_one()
    return self
```

**Models inheriting this mixin:**

| Model | `_bus_channel` Override |
|-------|------------------------|
| `mail.message` | Returns `(self._name, self.id)` |
| `res.users` | `self.partner_id` |
| `res.partner` | Default (returns `self`) |
| `res.groups` | Default |
| `res.users.settings` | `self.user_id._bus_channel()` |
| `mail.guest` | Default |
| `mail.link.preview` | `self.message_id._bus_channel()` |

**Note:** `res.users.settings` has conflicting `_bus_channel` in `bus` (→ `partner_id`) and `mail` (→ `user_id._bus_channel()`). Both resolve identically; `mail` takes precedence via MRO.

---

## `bus.presence` — User Presence

```python
class BusPresence(models.Model):
    _name = 'bus.presence'
    _log_access = False
```

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | Many2one (unique) | User |
| `last_poll` | Datetime | Last poll time |
| `last_presence` | Datetime | Last meaningful action |
| `status` | Selection | online / away / offline |

**Timers:**
| Timer | Threshold | Description |
|-------|-----------|-------------|
| `DISCONNECTION_TIMER` | 65s | Force offline after no poll |
| `AWAY_TIMER` | 30 min | Mark away after inactivity |
| `UPDATE_PRESENCE_DELAY` | 60s | Min between updates |
| `PRESENCE_OUTDATED_TIMER` | 12 hours | Cron cleanup threshold |

**Key Methods:**

```python
def update_presence(self, inactivity_period, identity_field, identity_value):
    # status = 'away' if inactivity_period > AWAY_TIMER * 1000 else 'online'
    # Uses mute_logger to suppress expected PG serialization errors
    with tools.mute_logger('odoo.sql_db'):
        self._update_presence(...)
        self.env.cr.commit()  # commit independently
```

**Failure Modes:**
- Multi-tab concurrency → `PG_CONCURRENCY_EXCEPTIONS_TO_RETRY` caught and rolled back (non-critical)
- Browser crash without disconnect → stays "online" until `DISCONNECTION_TIMER` (65s)
- Guest presence → tracked via `im_status` on `mail.guest`, computed from `bus.presence`

---

## `ir.websocket` — WebSocket Infrastructure

```python
class IrWebsocket(models.AbstractModel):
    _name = 'ir.websocket'
```

**Key Methods:**

`_build_bus_channel_list(channels)`
```python
channels.append('broadcast')
channels.extend(self.env.user.groups_id)
if req.session.uid:
    channels.append(self.env.user.partner_id)
return channels
```

`_prepare_subscribe_data(channels, last)`
- Validates all channels are strings
- `last > current_max_id` → resets to `0`
- Computes missed presence updates from channels

**WebSocket version:** Exposed as `websocket_worker_version` in `session_info()`.

---

## Extensions (from other modules via `_inherit`)

### `res.users` — from `bus` module
```python
class ResUsers(models.Model):
    _inherit = ["res.users", "bus.listener.mixin"]

def _bus_channel(self):
    return self.partner_id._bus_channel()
```

### `res.partner` — from `bus` module
```python
class ResPartner(models.Model):
    _inherit = ["res.partner", "bus.listener.mixin"]
# _compute_im_status: partners with users → most active status; else → 'im_partner'
```

### `res.groups` — from `bus` module
No additional fields. Inherits `bus.listener.mixin` for group change broadcasts.

### `res.users.settings` — from `bus` + `mail` (MRO conflict)
```python
# bus: _bus_channel → user_id._bus_channel()
# mail: same (both resolve to partner_id channel)
```

---

## Real-Time Notification Flow

```
User Action
  └─► record._notify_thread(message)
       └─► bus.bus._sendone(channel, 'mail.message/...', payload)
            └─► cr.precommit: INSERT INTO bus_bus
                 └─► cr.postcommit: SELECT pg_notify('imbus', payload)

ImDispatch.loop() [Background thread]
  └─► conn.poll() → conn.notifies
       └─► WebSocket.trigger_notification_dispatching()
            └─► Client JS
                 └─► Frontend store → UI
```

---

## Failure Modes

| Component | Failure | Handling |
|-----------|---------|----------|
| `bus.bus._sendone` | Transaction rollback | No notification sent — by design |
| `bus.bus._poll` | `last > current_max_id` | Returns `[]`, client re-fetches from 0 |
| `ImDispatch.loop` | `InterfaceError` (DB lost) | Sleeps 50s then retries |
| `ImDispatch.loop` | `RuntimeError` (stale channels) | Suppressed, clears stale channels |
| `bus.presence` | PG serialization error | `mute_logger` + rollback; non-critical |
| `ir.websocket` | Non-string channel | `ValueError` raised |

---

## Related Links
- [Modules/mail](Modules/mail.md) — Main consumer of bus notifications
- [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) — WebSocket endpoints
- [Modules/web](Modules/web.md) — Session info with websocket version
