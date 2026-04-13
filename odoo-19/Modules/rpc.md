# RPC Endpoints

## Overview

- **Description**: Provides standard XML-RPC and JSON-RPC endpoints used to programmatically access Odoo models.
- **Category**: Extra Tools
- **Dependencies**: `base`
- **Auto-install**: Yes
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Module**: `rpc`

## Key Features

- **XML-RPC endpoint** at `/xmlrpc/<service>` (v1, legacy) and `/xmlrpc/2/<service>` (v2, current)
- **JSON-RPC endpoint** at `/jsonrpc`
- **Version endpoint** at `/web/version` and `/json/version`
- **DEPRECATED in Odoo 19**: These endpoints are deprecated and scheduled for removal in Odoo 20. See the deprecation notice logged as a warning when called.

## Controllers

### `rpc.controllers.jsonrpc.JSONRPC`
Handles JSON-RPC requests.

**Route**: `/jsonrpc` (type='jsonrpc', auth='none')

```python
def jsonrpc(self, service, method, args):
    """Method used by client APIs to contact Odoo."""
    return dispatch_rpc(service, method, args)
```

### `rpc.controllers.xmlrpc.XMLRPC`
Handles XML-RPC requests.

**Routes**:
- `/xmlrpc/<service>` — v1 endpoint, returns faultCode as strings (legacy, non-compliant)
- `/xmlrpc/2/<service>` — v2 endpoint, returns faultCode as integers (current standard)

Both dispatch to `_xmlrpc(service)` which loads the request data, dispatches the RPC call, and returns the marshalled response.

### Marshalling (`rpc.controllers.xmlrpc.OdooMarshaller`)
Custom `xmlrpc.client.Marshaller` subclass that handles Odoo's specific types:

| Type | Handling |
|------|----------|
| `frozendict` | Dumped as struct |
| `bytes` | Decoded to base64 string |
| `datetime` | Serialized as ISO string via `Datetime.to_string()` |
| `date` | Serialized as ISO string via `Date.to_string()` |
| `lazy` | Unwrapped to underlying value |
| `Markup` | Cast to string |
| `Command` | Treated as integer |
| `defaultdict` | Treated as dict |

### Error Handling
Two modes depending on endpoint version:

**String mode (v1)**: Returns fault messages like `warning -- Warning\n\n{e}`
- `RedirectWarning` → code `warning`
- `MissingError` → code `warning`
- `AccessError` → code `warning`
- `AccessDenied` → code `AccessDenied`
- `UserError` → code `warning`

**Integer mode (v2)**:
- `RedirectWarning` → code `2` (RPC_FAULT_CODE_WARNING)
- `AccessError` → code `4` (RPC_FAULT_CODE_ACCESS_ERROR)
- `AccessDenied` → code `3` (RPC_FAULT_CODE_ACCESS_DENIED)
- `UserError` → code `2` (RPC_FAULT_CODE_WARNING)
- Other exceptions → code `1` (RPC_FAULT_CODE_APPLICATION_ERROR) with full traceback

## Deprecation Notice

```
The /xmlrpc, /xmlrpc/2 and /jsonrpc endpoints are deprecated in Odoo 19
and scheduled for removal in Odoo 20. Please report the problem to the
client making the request.
```

A warning is logged on every RPC call. Clients should migrate to the Odoo Web API (`/web`) before Odoo 20.

## Usage

```python
import xmlrpc.client

# Connect
common = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/2/common')
uid = common.authenticate('db', 'user', 'password', {})
models = xmlrpc.client.ServerProxy('http://localhost:8069/xmlrpc/2/object')
models.execute_kw('db', uid, 'password', 'res.partner', 'search_read', [[]], {'fields': ['name', 'email']})
```

## Related
- [Modules/api_doc](modules/api_doc.md) — API documentation module
- [Modules/web](modules/web.md) — Odoo Web controller framework
