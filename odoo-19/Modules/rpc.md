---
uuid: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b
tags:
  - odoo
  - odoo19
  - modules
  - integration
  - api
  - xmlrpc
  - jsonrpc
  - web_api
---

# RPC Endpoints (`rpc`)

## Overview

| Attribute | Value |
|-----------|-------|
| **Module** | `rpc` |
| **Category** | Extra Tools (Hidden) |
| **Depends** | `base` |
| **Auto-install** | True |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Source** | `odoo/addons/rpc/` |

## Description

The `rpc` module provides the **standard XML-RPC and JSON-RPC endpoints** that allow external programs to programmatically access Odoo models. These are the oldest and most widely-used external API mechanisms for Odoo, supported by client libraries in virtually every programming language.

**Important:** These endpoints are **deprecated in Odoo 19** and **scheduled for removal in Odoo 20**. Odoo recommends migrating to the [Odoo Web API](https://www.odoo.com/documentation/17.0/developer/reference/external_api.html) (which uses `/web` routes under the `web` controller framework).

## Module Structure

```
rpc/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py         # Defines deprecation notice and RPC_DEPRECATION_NOTICE
│   ├── jsonrpc.py          # JSON-RPC controller
│   └── xmlrpc.py           # XML-RPC controller
└── tests/
    └── test_xmlrpc.py      # Endpoint tests
```

## Endpoints

| Endpoint | Type | Version | Standard | faultCode | Status |
|----------|------|---------|----------|-----------|--------|
| `/jsonrpc` | JSON-RPC 2.0 | — | Compatible | N/A | Deprecated |
| `/xmlrpc` | XML-RPC v1 | Legacy | Non-compliant | String | Deprecated |
| `/xmlrpc/2` | XML-RPC v2 | Standard | Compliant | Integer | Deprecated |
| `/web/version` | HTTP JSON | — | Odoo-specific | — | Deprecated |
| `/json/version` | HTTP JSON | — | Odoo-specific | — | Deprecated |

## Deprecation Notice

Every RPC call triggers this warning in the Odoo log:

```
The /xmlrpc, /xmlrpc/2 and /jsonrpc endpoints are deprecated in Odoo 19
and scheduled for removal in Odoo 20. Please report the problem to the
client making the request.
Mute this logger: --log-handler %s:ERROR
https://www.odoo.com/documentation/latest/developer/reference/external_api.html#migrating-from-xml-rpc-json-rpc
```

To mute these warnings in production, add to `odoo.conf`:
```
log_handler = odoo.addons.rpc.controllers:ERROR
```

## Controllers

### `jsonrpc.py` — JSON-RPC Controller

**File:** `controllers/jsonrpc.py`

```python
class JSONRPC(Controller):
    @route('/jsonrpc', type='jsonrpc', auth="none", save_session=False)
    def jsonrpc(self, service, method, args):
        logger.warning(RPC_DEPRECATION_NOTICE, __name__)
        _check_request()
        return dispatch_rpc(service, method, args)
```

**Characteristics:**
- `type='jsonrpc'`: Odoo's JSON-RPC dispatcher (not the standard JSON-RPC 2.0 spec, but similar)
- `auth="none"`: No authentication required — authentication is handled by the dispatched method (e.g., `common.authenticate`)
- `save_session=False`: No session is created or updated

**JSON-RPC Request Format:**

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "service": "object",
    "method": "execute_kw",
    "args": ["dbname", uid, "password", "model.name", "method_name", [arg1, arg2], {kwarg: value}]
  },
  "id": 1
}
```

**Key difference from XML-RPC:** The JSON-RPC endpoint dispatches to Odoo's internal `dispatch_rpc()` function, which is shared with XML-RPC. Both ultimately call the same ORM methods.

### `xmlrpc.py` — XML-RPC Controller

**File:** `controllers/xmlrpc.py`

#### v1 Endpoint (Legacy)

```python
@route("/xmlrpc/<service>", auth="none", methods=["POST"], csrf=False, save_session=False)
def xmlrpc_1(self, service):
    # Returns faultCode as strings (non-compliant)
    # Kept for backwards compatibility with very old clients
```

Uses `xmlrpc_handle_exception_string()` which produces fault strings like:
```xml
< faults>
   <fault>
      <value><string>warning -- Warning\n\nCustomer is required</string></value>
   </fault>
</faultString>
```

#### v2 Endpoint (Standard)

```python
@route("/xmlrpc/2/<service>", auth="none", methods=["POST"], csrf=False, save_session=False)
def xmlrpc_2(self, service):
    # Returns faultCode as integers (compliant)
```

Uses `xmlrpc_handle_exception_int()` which produces fault integers:

| Integer | Constant | Maps to Odoo Exception |
|--------|----------|----------------------|
| 1 | `RPC_FAULT_CODE_CLIENT_ERROR` / `RPC_FAULT_CODE_APPLICATION_ERROR` | Other exceptions (includes traceback) |
| 2 | `RPC_FAULT_CODE_WARNING` | `RedirectWarning`, `UserError` |
| 3 | `RPC_FAULT_CODE_ACCESS_DENIED` | `AccessDenied` |
| 4 | `RPC_FAULT_CODE_ACCESS_ERROR` | `AccessError` |

**Common Entry Point:**

Both v1 and v2 share the same `_xmlrpc()` method:

```python
def _xmlrpc(self, service):
    data = request.httprequest.get_data()
    params, method = xmlrpc.client.loads(data, use_datetime=True)
    result = dispatch_rpc(service, method, params)
    return dumps((result,))
```

## `OdooMarshaller` — Custom XML Marshalling

**File:** `controllers/xmlrpc.py`

Odoo extends Python's `xmlrpc.client.Marshaller` to handle Odoo's specific Python types that standard XML-RPC cannot represent natively:

```python
class OdooMarshaller(xmlrpc.client.Marshaller):
    dispatch = dict(xmlrpc.client.Marshaller.dispatch)

    def dump_frozen_dict(self, value, write):
        # frozendict → dict (Odoo's immutable dict used for context)
        value = dict(value)
        self.dump_struct(value, write)

    def dump_bytes(self, value, write):
        # bytes → base64-decoded string (historical Odoo convention)
        # Python 3 bytes need explicit decoding, not Binary wrapper
        self.dump_unicode(value.decode(), write)

    def dump_datetime(self, value, write):
        # datetime → ISO string (not datetime Binary)
        value = Datetime.to_string(value)
        self.dump_unicode(value, write)

    def dump_date(self, value, write):
        # date → ISO string
        value = Date.to_string(value)
        self.dump_unicode(value, write)

    def dump_lazy(self, value, write):
        # lazy → unwrap and dispatch by underlying type
        v = value._value
        return self.dispatch[type(v)](self, v, write)

    def dump_unicode(self, value, write):
        # Remove XML 1.0 illegal control characters
        return super().dump_unicode(value.translate(CONTROL_CHARACTERS), write)
```

**Type Dispatch Table:**

```python
dispatch[frozendict] = dump_frozen_dict   # Immutable context dicts
dispatch[bytes] = dump_bytes              # Binary fields
dispatch[datetime] = dump_datetime       # Datetime fields
dispatch[date] = dump_date               # Date fields
dispatch[lazy] = dump_lazy               # Lazy evaluation wrappers
dispatch[str] = dump_unicode            # String with control char stripping
dispatch[Command] = dispatch[int]       # ORM Command tuples as integers
dispatch[defaultdict] = dispatch[dict] # Default dicts as regular dicts
dispatch[Markup] = lambda self, value, write: self.dispatch[str](self, str(value), write)
# Markup (HTML) → string, not HTML-encoded
```

**Control Character Handling:**

```python
CONTROL_CHARACTERS = dict.fromkeys(set(range(32)) - {9, 10, 13})
```

XML 1.0 prohibits control characters (0x00–0x1F) except tab (`\t`), newline (`\n`), and carriage return (`\r`). The `dump_unicode` override strips these, preventing malformed XML that would break many XML-RPC clients.

## Session Management — `_check_request()`

**File:** `controllers/__init__.py`

```python
def _check_request():
    if request.db:
        request.env.cr.close()
```

This function closes the database cursor immediately after dispatching the RPC call. The implications are:

1. **No session affinity**: The cursor is closed, so subsequent RPC calls start fresh
2. **No prefetching**: Related records are not prefetched across calls
3. **No transaction state**: Each RPC call is independent; no shared transaction

This is a performance and security measure: it ensures each RPC request is fully committed/rolled back before returning, and no cursor state leaks between calls.

## Version Endpoint

**File:** `controllers/__init__.py`

```python
class RPC(XMLRPC, JSONRPC):
    @route(['/web/version', '/json/version'], type='http', auth='none', readonly=True)
    def version(self):
        return request.make_json_response({
            'version_info': odoo.release.version_info,
            'version': odoo.release.version,
        })
```

Returns Odoo version information as a JSON response (not JSON-RPC format). Useful for client libraries to detect the Odoo version.

## Common Service Methods

The `dispatch_rpc()` function dispatches calls to named services:

| Service | Methods |
|---------|---------|
| `common` | `authenticate()`, `version()`, `about()`, `login()` |
| `db` | `db_exist()`, `list()`, `create_database()`, `dump()`, `restore()` |
| `object` | `execute_kw()`, `execute()` |
| `report` | `render_report()` |

### Authentication Flow

```python
# 1. Get UID
common = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/2/common')
uid = common.authenticate('db', 'user', 'password', {})

# 2. Use UID in subsequent calls
models = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/2/object')
result = models.execute_kw(
    'db', uid, 'password',
    'res.partner',      # Model
    'search_read',       # Method
    [['customer_rank', '>', 0](['customer_rank',-'>',-0.md)],  # Domain
    {'fields': ['name', 'email'], 'limit': 5}  # kwargs
)
```

## Error Handling Matrix

### v1 (String faultCode) — `xmlrpc_handle_exception_string()`

| Odoo Exception | faultString | faultCode |
|----------------|-------------|-----------|
| `RedirectWarning` | `warning -- Warning\n\n{message}` | `warning` |
| `MissingError` | `warning -- MissingError\n\n{message}` | `warning` |
| `AccessError` | `warning -- AccessError\n\n{message}` | `warning` |
| `AccessDenied` | `AccessDenied` | `AccessDenied` |
| `UserError` | `warning -- UserError\n\n{message}` | `warning` |
| Other exceptions | Full traceback as string | N/A |

### v2 (Integer faultCode) — `xmlrpc_handle_exception_int()`

| Odoo Exception | faultCode | Notes |
|----------------|-----------|-------|
| `RedirectWarning` | 2 (`RPC_FAULT_CODE_WARNING`) | — |
| `AccessError` | 4 (`RPC_FAULT_CODE_ACCESS_ERROR`) | — |
| `AccessDenied` | 3 (`RPC_FAULT_CODE_ACCESS_DENIED`) | — |
| `UserError` | 2 (`RPC_FAULT_CODE_WARNING`) | — |
| Other exceptions | 1 (`RPC_FAULT_CODE_APPLICATION_ERROR`) | Full traceback in fault string |

## Client Library Examples

### Python (standard library)

```python
import xmlrpc.client

# Connect
url = 'http://localhost:8069/xmlrpc/2/common'
common = xmlrpc.client.ServerProxy(url)
uid = common.authenticate('mydb', 'admin', 'admin', {})

# ORM operations
models = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/2/object')

# Search
partner_ids = models.execute_kw(
    'mydb', uid, 'admin',
    'res.partner', 'search',
    [['is_company', '=', True](['is_company',-'=',-True.md)],
    {'limit': 10}
)

# Read
partners = models.execute_kw(
    'mydb', uid, 'admin',
    'res.partner', 'read',
    [partner_ids],
    {'fields': ['name', 'email', 'country_id']}
)

# Search Read
partners = models.execute_kw(
    'mydb', uid, 'admin',
    'res.partner', 'search_read',
    [['is_company', '=', True](['is_company',-'=',-True.md)],
    {'fields': ['name', 'email'], 'limit': 5}
)

# Create
new_id = models.execute_kw(
    'mydb', uid, 'admin',
    'res.partner', 'create',
    [{'name': 'New Partner', 'email': 'new@example.com'}]
)

# Write
models.execute_kw(
    'mydb', uid, 'admin',
    'res.partner', 'write',
    [[new_id], {'phone': '+123456789'}]
)
```

### PHP (using pear XML-RPC)

```php
require_once 'XML/RPC2/Client.php';

$client = XML_RPC2_Client::create('http://localhost:8069/xmlrpc/2/common');
$uid = $client->authenticate('mydb', 'admin', 'admin');

$client = XML_RPC2_Client::create('http://localhost:8069/xmlrpc/2/object');
$result = $client->execute_kw(
    'mydb', $uid, 'admin',
    'res.partner', 'search_read',
    [['customer_rank', '>', 0](['customer_rank',-'>',-0.md)],
    ['fields' => ['name', 'email'], 'limit' => 5]
);
```

## Migration to Web API (Odoo 20+)

Since `/xmlrpc` and `/jsonrpc` are removed in Odoo 20, clients must migrate to the Odoo Web API. The Web API uses:

### Authentication

```python
# Session-based (cookie)
# POST /web/login with db, login, password
# Response includes session_id cookie

# Token-based (API key)
# POST /web/api/authenticate with db, login, api_key
# Response includes session_id cookie
```

### API Calls

```python
# Session cookie authentication
import requests

session = requests.Session()
login = session.post('http://localhost:8069/web/login', data={
    'db': 'mydb',
    'login': 'admin',
    'password': 'admin',
})

# Use session cookie for authenticated calls
response = session.post('http://localhost:8069/web/dataset/call_kw', json={
    'model': 'res.partner',
    'method': 'search_read',
    'args': [['is_company', '=', True](['is_company',-'=',-True.md)],
    'kwargs': {'fields': ['name', 'email'], 'limit': 5},
})
data = response.json()['result']
```

See the [official migration guide](https://www.odoo.com/documentation/latest/developer/reference/external_api.html#migrating-from-xml-rpc-json-rpc) for the complete migration path.

## Security Considerations

1. **`auth="none"`**: RPC endpoints do not require a session cookie, meaning authentication is entirely the responsibility of the dispatched method
2. **No CSRF**: `csrf=False` is set because XML-RPC and JSON-RPC are inherently stateless
3. **No rate limiting**: Built-in RPC endpoints have no rate limiting (consider a reverse proxy like nginx)
4. **Credential exposure**: Plain HTTP transmits credentials in clear text; always use HTTPS in production
5. **XML injection**: The `CONTROL_CHARACTERS` handling prevents malformed XML injection attacks
6. **Access control**: Model-level access rules (`ir.model.access`) still apply — UID determines accessible records

## Performance Considerations

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| No prefetching | N+1 queries if looping over records | Use `search_read` instead of multiple `read` calls |
| No cursor reuse | Connection overhead per request | Use connection pooling at the reverse proxy |
| No caching | Repeated queries | Implement caching in client or use `read_group` |
| Large result sets | Memory pressure | Always use `limit` and `offset` |
| Synchronous | Blocking I/O | Use async libraries for high-throughput clients |

## Related

- [Modules/web](Modules/web.md) — Odoo Web controller framework (replacement API)
- [Modules/api_doc](Modules/api_doc.md) — API documentation module
- [Modules/web_unsplash](Modules/web_unsplash.md) — Example of REST API controller pattern
- [Core/HTTP Controller](Core/HTTP%20Controller.md) — Odoo Web controller documentation
