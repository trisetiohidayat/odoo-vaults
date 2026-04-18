---
title: Debugging Guide
description: Comprehensive guide for debugging Odoo 19 applications — logging, shell, SQL, HTTP/RPC debugging, error deep dive, profiling, and developer mode tricks
tags: [odoo, odoo19, debugging, troubleshooting, developer-tools, testing]
created: 2026-04-14
---

# Debugging Guide

> **Prerequisite reading:** [Core/API](../Core/API.md) for decorator patterns, [Core/BaseModel](../Core/BaseModel.md) for ORM internals, [Patterns/Workflow Patterns](../Patterns/Workflow Patterns.md) for state machine debugging

---

## Table of Contents

1. [Logging Patterns](#1-logging-patterns)
2. [Odoo Shell](#2-odoo-shell)
3. [SQL Debugging](#3-sql-debugging)
4. [HTTP Debugging](#4-http-debugging)
5. [RPC Debugging](#5-rpc-debugging)
6. [Error Deep Dive](#6-error-deep-dive)
7. [Memory Profiling](#7-memory-profiling)
8. [Common Bug Patterns](#8-common-bug-patterns)
9. [Traceback Reading](#9-traceback-reading)
10. [Developer Mode Tricks](#10-developer-mode-tricks)
11. [Debugging Workflow Patterns](#11-debugging-workflow-patterns)

---

## 1. Logging Patterns

### 1.1 Logger Setup

Odoo uses Python's `logging` module with a structured hierarchy. Every module should declare its own logger:

```python
# At the top of every model/controller file
import logging

_logger = logging.getLogger(__name__)
```

The `__name__` pattern ensures loggers are named after the module path (e.g., `odoo.addons.sale.models.sale_order`), making it easy to filter logs by component.

### 1.2 Log Levels and When to Use Each

| Level | Use Case | Example |
|-------|----------|---------|
| `_logger.debug()` | Detailed flow tracing, variable states in complex logic | `"Order %s state transition: %s → %s"`, loop iterations |
| `_logger.info()` | Business milestones, significant operations | `"Invoice %s posted"`, `"Cron job started"` |
| `_logger.warning()` | Recoverable issues, unexpected but non-fatal conditions | `"Currency rate missing for %s, using 1.0"`, deprecated API usage |
| `_logger.error()` | Operation failures that need attention | `"Failed to send email for order %s"`, `"Webhook delivery failed"` |
| `_logger.exception()` | Error with full traceback context | Used in `except` blocks to include stack trace |

**Example: Production-ready logging in a model method**

```python
import logging
from odoo import fields, models, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def action_confirm(self):
        """Confirm sale order with comprehensive logging."""
        _logger.info("Starting confirmation for %d order(s): %s",
                     len(self), self.ids)

        for order in self:
            try:
                # Validation with debug detail
                if not order.order_line:
                    _logger.warning("Order %s has no lines, skipping confirmation",
                                   order.name)
                    raise UserError(_("Order must have at least one product line"))

                _logger.debug("Order %s validation passed. Amount: %s",
                              order.name, order.amount_total)

                # Core operation
                result = super().action_confirm()

                _logger.info("Order %s confirmed successfully. State: %s",
                             order.name, order.state)

                # Side effects logged
                if order.picking_ids:
                    _logger.info("Created %d delivery pickings for order %s",
                                 len(order.picking_ids), order.name)

            except Exception as e:
                _logger.exception("Failed to confirm order %s: %s",
                                  order.name, str(e))
                raise

        return result
```

### 1.3 Configuring Log Levels in `odoo.conf`

```ini
[options]
# Log output destination
logfile = /var/log/odoo/odoo.log

# Master log level: debug, info, warning, error, critical
log_level = info

# SQL query logging (very verbose — use for debugging only)
# log_level = debug_sql  # Odoo 16+
# Or in older versions:
# osv_memory_age = 60
# osv_memory_count_limit = 500

# Per-module log level override (more granular control)
# Syntax: module_path=level
# Examples:
#   odoo.addons.sale=debug
#   odoo.models=warning
#   odoo.sql_db=info

# PostgreSQL pool logging (shows connection pool events)
log_levels = sqlalchemy.pool:WARNING, sqlalchemy.engine:WARNING
```

**Effective log filtering strategy for development:**

```ini
# During debugging — set to DEBUG to see everything
log_level = debug

# In production — set to INFO and only enable specific modules
log_level = info
# odoo.addons.my_module = debug
# odoo.addons.account = warning
```

### 1.4 Structured Logging with Context

Use contextual logging to track operations across the request lifecycle:

```python
# Add context to logs across method calls
def _send_notification(self):
    for record in self:
        # Augment log context with record identifiers
        _logger.info(
            "Sending notification",
            extra={
                'order_id': record.id,
                'order_name': record.name,
                'partner_id': record.partner_id.id,
                'company_id': record.company_id.id,
            }
        )
        # ... send logic

# Reading contextual logs in production
# grep "order_id=42" /var/log/odoo/odoo.log
```

### 1.5 The `@api.model` Logging Gotcha

A common mistake: `@api.model` methods run as superuser without an active record, so debug logging inside them won't show record-specific data:

```python
# WRONG — self is empty recordset in @api.model
@api.model
def get_sequence(self):
    _logger.debug("Current state: %s", self.mapped('name'))  # Empty!
    return self.env['ir.sequence'].next_by_code('my.code')

# CORRECT — use env directly
@api.model
def get_sequence(self):
    _logger.debug("Computing sequence for company: %s",
                  self.env.company.id)
    return self.env['ir.sequence'].next_by_code('my.code')
```

---

## 2. Odoo Shell

### 2.1 Starting the Odoo Shell

The Odoo shell provides an interactive Python REPL with full ORM access, bypassing the HTTP layer. It is the most powerful debugging tool for investigating model state, testing method calls, and reproducing bugs.

```bash
# Basic shell startup
./odoo-bin shell -c /path/to/odoo19.conf -d roedl

# With --interactive flag for better REPL
./odoo-bin shell -c /path/to/odoo19.conf -d roedl --interactive=ipython

# Without config file (uses defaults)
./odoo-bin shell -d roedl --no-http
```

**What the shell initializes:**
- `self` — a `models.MetaModel` singleton for model access
- `env` — the `Environment` (equivalent to `self.env`)
- `cr` — the database cursor
- `uid` — current user ID (superuser by default in shell)
- `context` — the context dictionary

### 2.2 Essential Shell Commands

```python
# Navigate the shell
env['sale.order']           # Access model
env['sale.order'].search([])  # Search records
env['sale.order'].browse(1) # Browse by ID

# Check current user
uid   # returns: 1 (admin/superuser in shell)
user = env.user  # Current user record

# Check company context
env.companies  # Multi-company recordset
env.company    # Current active company

# Inspect model structure
env['sale.order']._fields  # All fields on model
env['sale.order']._methods  # All methods
env['sale.order'].fields_get()  # Detailed field metadata

# Check installed modules
env['ir.module.module'].search([('name', 'like', 'sale')])
```

### 2.3 Interactive Debugging Workflow

```python
# Step 1: Reproduce the bug scenario
order = env['sale.order'].browse(42)
order.action_confirm()

# Step 2: Inspect state before and after
order.state  # Check state transition
order.order_line  # Check related lines
order.picking_ids  # Check if picking created

# Step 3: Test alternative approach
# If the bug is in validation, test what values pass
env['sale.order'].create({
    'partner_id': order.partner_id.id,
    'order_line': [(0, 0, {
        'product_id': env['product.product'].search([], limit=1).id,
        'product_uom_qty': 1,
        'price_unit': 100,
    })]
})

# Step 4: Call methods with debugging
# Insert debug logging into method chain
result = order._compute_amount()
order.invalidate_recordset()  # Force recalculation
order.refresh()  # Reload from DB

# Step 5: Direct SQL for data verification
cr.execute("SELECT id, name, state FROM sale_order WHERE id = %s", (42,))
print(cr.fetchone())  # (42, 'S00042', 'sale')
```

### 2.4 Exploring Model Metadata

```python
# Get field definitions with details
fields_info = env['sale.order'].fields_get(
    ['name', 'partner_id', 'amount_total', 'state'],
    attributes=['type', 'string', 'help', 'required', 'readonly']
)
for name, info in fields_info.items():
    print(f"{name}: {info}")

# Check if a field is stored
env['sale.order']._fields['amount_total'].store  # True/False

# Check compute method
field = env['sale.order']._fields['amount_total']
print(f"Computed: {field.compute}")
print(f"Depends: {field.depends}")

# Check inheritance chain
print(env['sale.order']._inherit)  # List of parent models
```

### 2.5 Testing CRUD Operations

```python
# CREATE
new_record = env['res.partner'].create({
    'name': 'Debug Test Vendor',
    'email': 'debug@test.com',
    'supplier_rank': 1,
})
print(f"Created: {new_record.id}")

# READ
record = env['res.partner'].browse(new_record.id)
print(record.name, record.email)

# UPDATE
record.write({'phone': '+1234567890'})
record.invalidate_recordset()
print(record.phone)

# DELETE
record.unlink()

# SEARCH with complex domains
vendors = env['res.partner'].search([
    ('supplier_rank', '>', 0),
    '|',
    ('country_id.code', '=', 'ID'),
    ('country_id.code', '=', 'SG'),
    ('active', '=', True),
])
```

### 2.6 Simulating User Context

```python
# Switch to a specific user (respects ACL)
user2 = env.ref('base.user_admin')
env2 = env(user=user2.id)

# Test with regular user permissions
order_user = env2['sale.order'].browse(42)
order_user.read(['name', 'state'])  # Respects user's access rights

# Check access rights
env['sale.order'].check_access_rights('write')  # True/False
env['sale.order'].browse(42).check_access_rule('write')  # Check record rules

# Test multi-company filtering
env['res.partner'].with_context(
    allowed_company_ids=[1, 2]
).search_read([], ['name', 'company_id'])
```

---

## 3. SQL Debugging

### 3.1 Enabling SQL Query Logging

**Option A: Via `odoo.conf`**

```ini
[options]
# Enable SQL logging (Odoo 16+)
log_level = debug_sql

# Alternative: log_level = debug also shows SQL
log_level = debug
```

**Option B: At runtime via shell**

```python
# Enable SQL logging temporarily
import logging
logging.getLogger('odoo.sql_db').setLevel(logging.DEBUG)

# Disable after debugging
logging.getLogger('odoo.sql_db').setLevel(logging.INFO)
```

**Option C: Using PostgreSQL-side logging**

```sql
-- In psql, enable query logging
-- Edit postgresql.conf:
-- log_statement = 'all'
-- log_duration = on
-- log_min_duration_statement = 0

-- Or dynamically:
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();
```

### 3.2 Direct SQL Execution in Odoo Shell

```python
# Execute raw SQL (bypasses ORM)
cr.execute("SELECT id, name, state, amount_total FROM sale_order LIMIT 5")
results = cr.fetchall()
for row in results:
    print(f"ID: {row[0]}, Name: {row[1]}, State: {row[2]}, Amount: {row[3]}")

# With parameters (safe from SQL injection)
cr.execute(
    "SELECT id, name FROM sale_order WHERE state = %s AND amount_total > %s",
    ('sale', 1000)
)
print(cr.fetchall())

# Inspect query plan
cr.execute("EXPLAIN ANALYZE SELECT * FROM sale_order WHERE partner_id = 1")
for row in cr.fetchall():
    print(row)

# Check table structure
cr.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'sale_order'
    ORDER BY ordinal_position
""")
for col in cr.fetchall():
    print(col)
```

### 3.3 Transaction Management in Shell

```python
# Default: all operations are in a transaction
# In shell, each command is auto-committed unless you manage transactions:

# Start explicit transaction
cr.execute("BEGIN")

# Perform operations
cr.execute("INSERT INTO res_partner (name, create_date) VALUES ('Test', NOW()) RETURNING id")
new_id = cr.fetchone()[0]

# Rollback if needed
cr.execute("ROLLBACK")

# Commit explicitly
cr.execute("COMMIT")

# Check transaction state
print(f"In transaction: {cr._in_transaction}")

# Savepoint for testing
cr.execute("SAVEPOINT test_savepoint")
cr.execute("ROLLBACK TO SAVEPOINT test_savepoint")
cr.execute("RELEASE SAVEPOINT test_savepoint")
```

### 3.4 Diagnosing N+1 Queries

**Detecting N+1 in logs:**

When SQL logging is on, look for repeated identical queries:

```
# BAD pattern — same query repeated many times
SELECT * FROM res_partner WHERE id = 1
SELECT * FROM res_partner WHERE id = 2
SELECT * FROM res_partner WHERE id = 3
... (for each order in a loop)

# GOOD pattern — single query with IN clause
SELECT * FROM res_partner WHERE id IN (1, 2, 3, 4, 5, ...)
```

**Profiling query count per operation:**

```python
from odoo.sql_db import Cursor

# Wrap an operation and count queries
class QueryCounter:
    def __init__(self, cr):
        self.cr = cr
        self.count = 0
        self._original_execute = cr.execute

    def __enter__(self):
        # Store original execute
        self._original_execute = self.cr.execute
        # Monkey-patch to count
        def counting_execute(query, params=None):
            self.count += 1
            _logger.debug("Query #%d: %s", self.count, query[:100])
            return self._original_execute(query, params)

        self.cr.execute = counting_execute
        return self

    def __exit__(self, *args):
        self.cr.execute = self._original_execute

# Usage
with QueryCounter(cr):
    orders = env['sale.order'].search([], limit=100)
    for order in orders:
        _ = order.partner_id.name  # Each access triggers a query

print(f"Total queries executed: {count_queries.count}")
```

**Fixing N+1 in code:**

```python
# BAD: N+1 query
for order in orders:
    print(order.partner_id.name)

# GOOD: Pre-fetch with mapped
partner_names = orders.mapped('partner_id.name')

# GOOD: Use read() to load specific fields
orders.read(['name', 'partner_id', 'amount_total'])

# GOOD: Use read_group for aggregations
summary = env['sale.order'].read_group(
    domain=[],
    fields=['amount_total:sum', 'partner_id'],
    groupby=['partner_id']
)

# GOOD: Conditional prefetch
# Enable auto_join for specific one2many relationships
order_line = fields.One2many('sale.order.line', 'order_id', auto_join=True)
```

### 3.5 Index Analysis with SQL

```python
# Check existing indexes on a table
cr.execute("""
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'sale_order'
    ORDER BY indexname
""")

# Check if index is used in query
cr.execute("EXPLAIN SELECT * FROM sale_order WHERE partner_id = 1")
# Look for "Index Scan" vs "Seq Scan"

# Add index programmatically (in model _auto_init)
def _auto_init(self):
    res = super()._auto_init()
    self.env.cr.execute("""
        CREATE INDEX IF NOT EXISTS sale_order_date_partner_idx
        ON sale_order (date_order, partner_id)
    """)
    return res

# Check index usage statistics
cr.execute("""
    SELECT relname, indexrelname, idx_scan, idx_tup_read
    FROM pg_stat_user_indexes
    WHERE relname = 'sale_order'
    ORDER BY idx_scan DESC
""")
```

---

## 4. HTTP Debugging

### 4.1 Debugging `@http.route` Controllers

**Setting up a debug controller:**

```python
from odoo import http
from odoo.http import request, Response
import json
import logging

_logger = logging.getLogger(__name__)


class DebugController(http.Controller):

    @http.route('/debug/api/test', type='json', auth='user',
                website=False)
    def debug_api(self, **kwargs):
        """
        Debug endpoint — logs all incoming request data.
        Use during development to inspect request structure.
        """
        _logger.info("=== DEBUG API START ===")
        _logger.info("User: %s (ID: %s)", request.env.user.name, request.uid)
        _logger.info("Context: %s", request.context)
        _logger.info(" kwargs: %s", kwargs)
        _logger.info("Session: %s", dict(request.session))

        # Log all HTTP headers
        for header, value in request.httprequest.headers.items():
            _logger.debug("Header %s: %s", header, value)

        return {
            'status': 'ok',
            'user': request.env.user.name,
            'debug_kwargs': kwargs,
        }

    @http.route('/debug/api/echo', type='json', auth='public')
    def echo(self, payload=None):
        """Echo back the payload for testing."""
        _logger.debug("Received payload: %s", payload)
        return {'echo': payload}

    @http.route('/debug/trace', type='http', auth='user')
    def trace_session(self):
        """Output comprehensive session and environment info."""
        values = {
            'uid': request.uid,
            'user': request.env.user.name,
            'user_login': request.env.user.login,
            'company': request.env.company.name,
            'companies': request.env.companies.mapped('name'),
            'lang': request.env.user.lang,
            'tz': request.env.user.tz,
            'is_admin': request.env.user._is_admin(),
            'context': {k: str(v) for k, v in request.context.items()},
        }
        return Response(
            json.dumps(values, indent=2, default=str),
            mimetype='application/json'
        )
```

### 4.2 JSON vs HTTP Response Types

| Type | Use When | Debugging Notes |
|------|----------|----------------|
| `type='json'` | API endpoints, AJAX calls | Auto-serializes return, handles errors gracefully |
| `type='http'` | Form submissions, page renders | Full control over response, must set headers manually |
| `type='binary'` | File downloads | Check `Content-Disposition`, `Content-Length` headers |

**Debug JSON response issues:**

```python
@http.route('/debug/json/test', type='json', auth='user')
def json_test(self):
    # Wrap in try/except to see full error
    try:
        result = self._do_something()
        return result
    except Exception as e:
        _logger.exception("JSON endpoint failed")
        # Return error in structured format
        return {'error': str(e), 'type': type(e).__name__}

# In browser console:
fetch('/debug/json/test')
  .then(r => r.json())
  .then(data => console.log(data))
  .catch(err => console.error('Error:', err))
```

### 4.3 CORS Configuration for API Debugging

```python
@http.route('/debug/api/cors', type='json', auth='public',
            cors='*',  # Allow all origins for debugging
            csrf=False)  # Disable CSRF for testing (NEVER do this in production!)
def cors_endpoint(self, **post):
    # Add CORS headers manually if needed
    response = Response(json.dumps({'status': 'ok'}), mimetype='application/json')
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# ALWAYS use CSRF in production:
# csrf=True (default) requires token from form
# Add @csrf_exempt decorator only for webhook endpoints
```

### 4.4 Testing JSON Endpoints with curl

```bash
# Login and get session cookie
curl -c cookies.txt -X POST \
  http://localhost:8069/web/login \
  -d "login=admin&password=admin"

# Test JSON endpoint with auth
curl -b cookies.txt \
  -X POST http://localhost:8069/api/vendors \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Vendor", "email": "test@vendor.com"}'

# Test public endpoint
curl -X GET "http://localhost:8069/debug/api/echo?payload=hello"

# Verbose HTTP debugging
curl -v -X GET http://localhost:8069/debug/api/test

# Time the response
curl -w "\nTime: %{time_total}s\n" \
  http://localhost:8069/api/vendors

# Check response headers
curl -I http://localhost:8069/web/login
```

### 4.5 Inspecting the Request Object

```python
@http.route('/debug/request/inspect', type='http', auth='user')
def inspect_request(self):
    """Output all available request data as JSON."""
    req = request.httprequest

    data = {
        # URL information
        'method': req.method,
        'path': req.path,
        'full_path': req.full_path,
        'query_string': req.query_string.decode('utf-8'),
        'url': req.url,

        # Headers
        'headers': dict(req.headers),
        'user_agent': req.user_agent.string if req.user_agent else None,
        'remote_addr': req.remote_addr,

        # Body
        'content_type': req.content_type,
        'content_length': req.content_length,

        # Session
        'session_id': request.session.sid,
        'session_uid': request.session.uid,
        'session_context': dict(request.session.context),

        # Odoo-specific
        'odoo_db': request.session.db,
        'odoo_uid': request.uid,
    }

    return Response(
        json.dumps(data, indent=2, default=str),
        mimetype='application/json'
    )
```

---

## 5. RPC Debugging

### 5.1 XML-RPC Call Structure

Odoo's XML-RPC interface exposes all ORM methods via two endpoints:
- `/xmlrpc/2/common` — authentication and metadata
- `/xmlrpc/2/object` — execute ORM methods on models

**Debugging XML-RPC with Python:**

```python
import xmlrpc.client
import json

url = 'http://localhost:8069'
db = 'roedl'
username = 'admin'
password = 'admin'

# Step 1: Authenticate
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

print(f"Authenticated UID: {uid}")

# Step 2: Get model metadata
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# search() returns record IDs
vendor_ids = models.execute_kw(
    db, uid, password,
    'res.partner',
    'search',
    [['supplier_rank', '>', 0](['supplier_rank',-'>',-0.md)],
    {'limit': 5}
)
print(f"Vendor IDs: {vendor_ids}")

# search_read() returns full records
vendors = models.execute_kw(
    db, uid, password,
    'res.partner',
    'search_read',
    [['supplier_rank', '>', 0](['supplier_rank',-'>',-0.md)],
    {'fields': ['id', 'name', 'email', 'phone'], 'limit': 5}
)
print(json.dumps(vendors, indent=2))

# inspect() — get model fields
fields_info = models.execute_kw(
    db, uid, password,
    'res.partner',
    'fields_get',
    [],
    {'attributes': ['string', 'type', 'required']}
)
print(json.dumps(fields_info, indent=2))
```

### 5.2 Debugging External API Calls

**Capturing request/response for external APIs:**

```python
import requests
import logging

_logger = logging.getLogger(__name__)

class ExternalAPIIntegration(models.Model):
    _name = 'external.api.integration'

    def _call_with_debug(self, url, method='GET', data=None, headers=None):
        """
        Wrapper for external API calls with comprehensive logging.
        """
        _logger.info("=== EXTERNAL API CALL ===")
        _logger.info("URL: %s %s", method, url)
        _logger.info("Headers: %s", headers)

        if data:
            _logger.debug("Request body: %s", json.dumps(data, indent=2))

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unknown HTTP method: {method}")

            _logger.info("Response status: %d", response.status_code)
            _logger.info("Response headers: %s", dict(response.headers))
            _logger.debug("Response body: %s", response.text[:1000])

            response.raise_for_status()
            return response.json() if response.text else {}

        except requests.RequestException as e:
            _logger.error("External API call failed: %s", str(e))
            _logger.error("Request URL: %s", url)
            _logger.error("Request data: %s", data)
            if hasattr(e, 'response') and e.response:
                _logger.error("Response body: %s", e.response.text)
            raise
```

### 5.3 JSON-RPC Debugging

```python
import json
import requests

url = 'http://localhost:8069/jsonrpc'

def jsonrpc_call(method, service, svc_method, args):
    """Generic JSON-RPC call with error handling."""
    payload = {
        'jsonrpc': '2.0',
        'method': 'call',
        'params': {
            'service': service,
            'method': svc_method,
            'args': args,
        },
        'id': 1
    }

    _logger.debug("JSON-RPC Request: %s", json.dumps(payload, indent=2))

    response = requests.post(
        url,
        json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=30
    )

    result = response.json()
    _logger.debug("JSON-RPC Response: %s", json.dumps(result, indent=2))

    if 'error' in result:
        _logger.error("JSON-RPC Error: %s", result['error'])
        raise Exception(result['error'])

    return result.get('result')

# Example: Authenticate
uid = jsonrpc_call('call', 'common', 'authenticate',
                   ['roedl', 'admin', 'admin', {}])
print(f"UID: {uid}")

# Example: Search
vendors = jsonrpc_call('call', 'object', 'execute_kw', [
    'roedl', uid, 'admin',
    'res.partner',
    'search_read',
    [['supplier_rank', '>', 0](['supplier_rank',-'>',-0.md)],
    {'fields': ['name', 'email'], 'limit': 10}
])
print(vendors)
```

### 5.4 RPC Error Response Analysis

```python
# Common XML-RPC error patterns and how to debug them

# Error: Authentication failed
# Response: <faultString>AccessError: Access rights violation</faultString>
# Debug: Check uid, password, and database name

# Error: Missing record
# Response: <faultString>MissingError: Record does not exist or has been deleted</faultString>
# Debug: Verify the record ID exists in database

# Error: Permission denied
# Response: <faultString>AccessError: Access rights violation</faultString>
# Debug: Check ir.model.access.csv and record rules

# Error: Validation error
# Response: <faultString>UserError: Description of validation failure</faultString>
# Debug: Check @api.constrains, @api.onchange, required fields

# Inspect full error structure
def inspect_rpc_error(response):
    if hasattr(response, 'faultString'):
        print(f"Error type: XML-RPC Fault")
        print(f"Error message: {response.faultString}")
    elif isinstance(response, dict) and 'error' in response:
        print(f"Error type: JSON-RPC Error")
        print(f"Error code: {response['error'].get('code')}")
        print(f"Error message: {response['error'].get('message')}")
        print(f"Error data: {response['error'].get('data')}")
```

---

## 6. Error Deep Dive

> **Reference:** See [Core/Exceptions](../Core/Exceptions.md) for the complete exception hierarchy

### 6.1 AccessError (ACL Violations)

**Root cause:** User lacks read/write/create/unlink permission on the model, or record rule filters out the record.

**Debugging steps:**

```python
# Step 1: Identify the exact permission that's failing
env['sale.order'].check_access_rights('write')  # Returns False

# Step 2: Check which ACL rules apply to this model
acls = env['ir.model.access'].search([('model_id.model', '=', 'sale.order')])
for acl in acls:
    print(f"Group: {acl.group_id.name}, Read: {acl.perm_read}, Write: {acl.perm_write}")

# Step 3: Check record rules
rules = env['ir.rule'].search([('model_id.model', '=', 'sale.order')])
for rule in rules:
    print(f"Rule: {rule.name}, Domain: {rule.domain_force}")

# Step 4: Test what records user can see
accessible = env['sale.order'].with_user(user).search([])
print(f"User {user.name} can see {len(accessible)} of {env['sale.order'].search_count([])} records")

# Step 5: Diagnose with sudo
# Temporarily test with elevated permissions
try:
    result = env['sale.order'].sudo().browse(record_id).write({'name': 'Test'})
except AccessError as e:
    _logger.error("Access denied even with sudo — check model ACL")
```

**Common scenarios:**
- Missing `ir.model.access.csv` entry for custom model
- Record rule filtering out all records
- Field-level security (`groups` attribute blocking access)
- Model not added to any installed module's security file

### 6.2 MissingError (Record Not Found)

**Root cause:** Code references a record that doesn't exist or was deleted.

**Example traceback:**
```
odoo.exceptions.MissingError: Record does not exist or has been deleted.
Record: sale.order, id 99999, user 1
```

**Debugging:**

```python
# Check if record exists
record = env['sale.order'].browse(99999)
print(f"Exists: {record.exists()}")  # Returns False if deleted

# Check audit trail — who deleted it and when
# Via shell:
cr.execute("""
    SELECT id, create_uid, create_date, write_uid, write_date
    FROM sale_order WHERE id = 99999
""")

# Check if ID was re-used (deleted and created new record)
# Odoo does NOT reuse IDs — each delete creates a gap

# Debug: Where the missing reference came from
# Search for all references to the missing ID
cr.execute("""
    SELECT model, table_name
    FROM ir_model
    WHERE model IN (
        SELECT DISTINCT model FROM ir_attachment WHERE res_id = 99999
        UNION
        SELECT DISTINCT model FROM sale_order_line WHERE order_id = 99999
    )
""")

# Fix: Catch MissingError and handle gracefully
from odoo.exceptions import MissingError

def safe_delete(self, record_id):
    try:
        record = self.browse(record_id)
        if record.exists():
            record.unlink()
        else:
            _logger.warning("Record %s already deleted", record_id)
    except MissingError:
        _logger.info("Record %s not found, skipping deletion", record_id)
```

### 6.3 ValidationError (User-Facing Validation)

**Root cause:** Business rule violation — data doesn't satisfy constraints defined via `@api.constrains`, SQL constraints, or required field checks.

**Key distinction from `UserError`:**
- `ValidationError` is raised by the ORM framework via `@api.constrains` decorators
- `UserError` is raised by model code for business logic validation

**Debugging:**

```python
# In @api.constrains — check which fields triggered the error
@api.constrains('partner_id', 'date_order')
def _check_valid_order(self):
    for order in self:
        if order.partner_id and not order.partner_id.active:
            raise ValidationError(
                _("Cannot create order for inactive partner '%s'")
                % order.partner_id.name
            )

# Debug: Print all field values at validation time
@api.constrains('field1', 'field2')
def _check_debug(self):
    for record in self:
        _logger.debug("Validating record ID=%d, field1=%s, field2=%s",
                      record.id, record.field1, record.field2)
    # ... validation logic

# Test validation in shell
order = env['sale.order'].browse(42)
order.write({'partner_id': partner_id})  # Will raise ValidationError if inactive
```

### 6.4 UserError vs ValidationError Decision Guide

| Scenario | Use | Reason |
|----------|-----|--------|
| `@api.constrains` decorator | `ValidationError` | Framework expects this type |
| Form-level validation | `UserError` | More user-friendly message |
| Database constraint violation | `ValidationError` | Data integrity issue |
| Business rule that user can fix | `UserError` | Actionable by user |
| Locked record modification | `UserError` | "Cannot modify locked order" |
| Required field missing | `ValidationError` | Framework validation |

```python
# Both can be raised from any method
def action_confirm(self):
    for order in self:
        if not order.partner_id:
            # Required field check — ValidationError
            raise ValidationError(_("Customer is required"))

        if order.state == 'done':
            # Business rule — UserError (user can't undo a locked order)
            raise UserError(_("Cannot confirm a locked order"))

# The key difference: UserError displays in a user-friendly dialog
# ValidationError is typically shown inline on the form
```

### 6.5 Traceback Patterns by Error Type

```
AccessError:
  File ".../models.py", line 123, in write
    self.check_access_rights('write')
  File ".../osv.py", line 123, in check_access_rights
    raise AccessError(msg)

MissingError:
  File ".../models.py", line 456, in _compute_related
    raise MissingError(msg)

ValidationError:
  File ".../models.py", line 78, in _check_constraint
    raise ValidationError(msg)
  File ".../api.py", line 456, in wrapped
    return f(self, ...)  # @api.constrains decorator

UserError:
  File ".../models.py", line 234, in action_confirm
    raise UserError(msg)
```

### 6.6 Handling Multiple Errors

```python
from odoo.exceptions import ValidationError, UserError

def validate_order(self):
    errors = []

    for order in self:
        if not order.partner_id:
            errors.append(f"Order {order.name}: Customer is required")
        if not order.order_line:
            errors.append(f"Order {order.name}: At least one product line required")
        if order.amount_total <= 0:
            errors.append(f"Order {order.name}: Total amount must be positive")

    if errors:
        raise ValidationError(
            _("Please fix the following errors:\n") + "\n".join(f"• {e}" for e in errors)
        )
```

---

## 7. Memory Profiling

### 7.1 Detecting Memory Leaks in Odoo

Memory leaks in Odoo typically occur from:
- Large recordsets kept in memory (especially with computed fields)
- Unbounded one2many relationships loaded eagerly
- Circular references between records
- Growing cache size in long-running workers

**Symptom check:** Worker memory grows continuously over days/weeks, requiring restart.

### 7.2 Using `objgraph` for Memory Profiling

```python
# Install: pip install objgraph

# In a long-running script or cron job:
import objgraph
import gc

# Force garbage collection first
gc.collect()

# Get top objects in memory
print("Top 20 types in memory:")
objgraph.show_most_common_types(limit=20)

# Get growth over time
print("\nObjects that grew:")
objgraph.show_growth()

# Find what's holding a specific object
recordset = env['sale.order'].search([], limit=100)
objgraph.find_backlog(recordset)  # What holds this reference

# Show reference chain (why object not garbage collected)
objgraph.show_backrefs(
    env['sale.order'].browse(1),
    max_depth=5,
    filter=lambda x: not str(type(x)).startswith('<class')
)
```

### 7.3 Tracking Large Recordsets

```python
def _debug_large_recordset(self):
    """Debug method to track recordset size and memory."""
    records = self.search([])

    _logger.info("Recordset size: %d records", len(records))
    _logger.info("Recordset type: %s", type(records))
    _logger.info("Recordset ids: first=%d, last=%d",
                  records.ids[0] if records else None,
                  records.ids[-1] if records else None)

    # Memory estimate (rough)
    estimated_memory = len(records) * 500  # ~500 bytes per record
    _logger.info("Estimated memory: ~%d KB", estimated_memory / 1024)

    # Check if lazy loading is working
    _logger.debug("Prefetch fields: %s", records._prefetch)
    return records
```

### 7.4 Preventing Memory Issues in Code

```python
# Pattern 1: Batch processing with explicit cleanup
def process_large_dataset(self):
    BATCH_SIZE = 1000
    all_ids = self.search([], order='id').ids

    for i in range(0, len(all_ids), BATCH_SIZE):
        batch = self.browse(all_ids[i:i + BATCH_SIZE])

        # Process batch
        for record in batch:
            self._process_single(record)

        # Explicitly dereference to allow GC
        batch.invalidate_recordset()

        # Commit per batch to free memory
        self.env.cr.commit()

# Pattern 2: Use read() instead of browse() for large datasets
def read_large_dataset(self):
    # Instead of:
    records = self.search([])  # Keeps all IDs in memory
    for r in records:
        pass  # Iterating triggers lazy loading

    # Do:
    records = self.search([])
    data = records.read(['field1', 'field2'])  # Single query, releases browse
    for item in data:
        self._process_item(item)  # Works on plain dicts

# Pattern 3: Clear environment after heavy operations
def heavy_operation(self):
    try:
        result = self._do_heavy_computation()
        return result
    finally:
        # Clear caches
        self.env.clear()
        # Or if needed, recreate environment
        # new_env = self.env(self.env.cr, self.env.uid, {})
```

### 7.5 Monitoring Odoo Worker Memory

```bash
# Check worker memory usage
ps aux | grep odoo | grep python

# Check memory per worker (via PID)
pid=12345
ps -o pid,rss,vsz,comm -p $pid

# In odoo.conf, configure worker memory limits
# [worker]
# limit_memory_soft = 2147483648  # 2GB soft limit
# limit_memory_hard = 4294967296  # 4GB hard limit

# Restart workers automatically on memory spike
# [worker]
# limit_memory_soft = 2147483648
# max_cron_threads = 2
# worker_timeout = 300
```

---

## 8. Common Bug Patterns

### 8.1 Forgotten `super()` in Method Override

**The problem:** Overriding a method but not calling the parent means all inherited behavior is skipped.

```python
# WRONG — misses parent validation and side effects
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def action_confirm(self):
        # No super() call — parent logic completely replaced
        self.write({'state': 'sale'})
        return True

# CORRECT — call super() to preserve parent behavior
class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def action_confirm(self):
        # Custom validation before parent
        for order in self:
            if not order.partner_id:
                raise UserError(_("Customer is required"))

        # Call parent
        result = super().action_confirm()

        # Custom logic after parent
        for order in self:
            _logger.info("Order %s confirmed by user %s",
                         order.name, self.env.user.name)

        return result
```

**Detection:** Compare behavior before/after upgrade. If related features (picking creation, invoice generation) stopped working, check if `super()` was forgotten in overrides.

### 8.2 Wrong `@api.model` vs `@api.depends`

**The problem:** `@api.model` methods run on empty recordset with superuser privileges, while `@api.depends` methods run with the current user's ACL on actual records.

```python
# WRONG — @api.model has no active record
@api.model
def _compute_name(self):
    for record in self:  # self is empty!
        record.name = record.partner_id.name  # AttributeError

# CORRECT — use @api.depends for record processing
@api.depends('partner_id.name')
def _compute_name(self):
    for record in self:
        record.name = record.partner_id.name if record.partner_id else ''

# When you DO need @api.model (no record needed):
@api.model
def get_default_warehouse(self):
    # env access works fine
    return self.env.company.warehouse_id

# When you need both (record + elevated privileges):
def _compute_sensitive_field(self):
    for record in self:
        # Use sudo for the computation only
        record.x_sensitive = record.sudo()._internal_method()
```

### 8.3 Circular Dependencies

**The problem:** Model A imports Model B's fields, while Model B imports Model A's methods.

**Symptom:**
```
ImportError: cannot import name 'sale_order' from partially initialized module
```

**Fix pattern:**

```python
# Option 1: Move to a shared mixin
# Instead of circular inheritance, create a third model
class SaleOrderMixin(models.AbstractModel):
    _name = 'sale.order.mixin'

    x_shared_field = fields.Char()

# Option 2: Use string reference instead of direct import
class A(models.Model):
    _name = 'model.a'

    b_id = fields.Many2one('model.b')  # String, not imported

class B(models.Model):
    _name = 'model.b'

    @api.onchange('a_id')  # String reference — avoids circular
    def _on_a_change(self):
        pass

# Option 3: Lazy evaluation
class A(models.Model):
    _name = 'model.a'

    @api.constrains('b_id')
    def _check_b(self):
        # Import inside method to avoid circular at module load
        from . import b_model
        b_model.validate_b(self.b_id)
```

### 8.4 Forgetting `store=True` on Computed Fields

```python
# WRONG — computed but not stored, recalculated every access
amount_words = fields.Char(
    compute='_compute_amount_words',
    help="Amount in words (not stored, recalculated each time)"
)
# Performance: Every read triggers full computation for all records in view

# CORRECT — store if queried frequently or used in search/domain
amount_words = fields.Char(
    compute='_compute_amount_words',
    store=True,  # Stored in DB, updated when dependencies change
    index=True,   # If used in search
)

# CORRECT for very expensive, rarely-accessed computations
amount_words = fields.Char(
    compute='_compute_amount_words',
    store=False,  # Don't store
    compute_sudo=True,  # Run as superuser to avoid ACL issues
)
```

### 8.5 Field Definition Order Matters in XML

```python
# WRONG — field defined AFTER it is referenced in domain
<field name="state"/>
<field name="date_closed" invisible="state != 'done'"/>

# CORRECT — dependent fields defined before their dependents
<field name="state"/>
<field name="date_done"/>
<field name="picking_ids"/>

# Check: In XML, fields referenced in attrs/invisible/domain must appear
# above the field that uses them
```

### 8.6 Recordset Not Invalidated After Direct SQL

```python
# WRONG — direct SQL update doesn't invalidate Odoo cache
cr.execute("UPDATE sale_order SET state = 'sale' WHERE id = %s", [order_id])
order = env['sale.order'].browse(order_id)
print(order.state)  # Returns OLD cached value!

# CORRECT — invalidate the cache
cr.execute("UPDATE sale_order SET state = 'sale' WHERE id = %s", [order_id])
order = env['sale.order'].browse(order_id)
order.invalidate_recordset()  # Force reload from DB
order.refresh()
print(order.state)  # Returns NEW value
```

---

## 9. Traceback Reading

### 9.1 Anatomy of an Odoo Traceback

```
Traceback (most recent call last):
  File "/home/odoo/odoo/http.py", line 456, in dispatch
    result = self._dispatch(func, args)
  File "/home/odoo/odoo/http.py", line 123, line 234, in _handle_exception
    return request.redirect_with_hash('/web/cause/500')
  File "/home/odoo/odoo/http.py", line 123, line 789, in _handle_exception
    raise e
  File "/home/odoo/odoo/api.py", line 456, in wrapped
    return f(self, args, **kwargs)
  File "/home/odoo/odoo/models.py", line 789, in write
    vals = self._update(vals)
  File "/home/odoo/odoo/models.py", line 234, in _update
    self.check_field_access_rights('write', vals)
  File "/home/odoo/odoo/models.py", line 567, in check_field_access_rights
    raise AccessError(msg)
```

**Reading order:** Read from bottom to top — the last line before the exception is the actual error source.

### 9.2 Common Traceback Patterns

**Pattern: Decorator wrapper traceback**
```
odoo.tools.convert.iteriter_iterable(self, args, **kwargs)
odoo.api.wrapped(...)
  └─ This shows the decorator — keep going UP
    └─ Your actual method starts here
```

**Pattern: Model inheritance traceback**
```
File "models/vendor.py", line 45, in action_confirm
  self.write({'state': 'sale'})
File "odoo/addons/sale/models/sale_order.py", line 123, in action_confirm
  result = super().action_confirm()
File "odoo/addons/base/models/res_partner.py", line 78, in write
  vals = self._update(vals)
  └─ Root cause: ACL check failed in base write()
```

**Pattern: Foreign key / constraint error**
```
ProgrammingError: insert or update on table "sale_order_line"
violates foreign key constraint "sale_order_line_order_id_fkey"
DETAIL: Key (order_id)=(99999) is not present in table "sale_order".
```
→ The `order_id` being set does not exist. Either the order was deleted, or the ID is wrong.

### 9.3 Mapping Line Numbers to Source

```bash
# When traceback shows a line number, find the exact file:
# Traceback shows: File ".../models/sale_order.py", line 123

# Method 1: Grep for the function
grep -n "def action_confirm" custom_addons_19/roedl/sale/models/sale_order.py

# Method 2: Check the file around the line number
sed -n '115,130p' custom_addons_19/roedl/sale/models/sale_order.py

# Method 3: Use the full traceback path
# The path in traceback is the FULL path — use it directly
```

### 9.4 Handling Multi-line Error Messages

```python
# ValidationError messages can span multiple lines
# Example traceback for long ValidationError:
"""
ValidationError: ("Please fix the following errors:
• Order SO001: Customer is required
• Order SO002: Date is required
• Order SO003: At least one product line required", None)
"""

# Parse it:
error_msg = str(validation_error)
lines = error_msg.split('\n')
for line in lines:
    if line.startswith('•'):
        print(f"Individual error: {line}")
```

---

## 10. Developer Mode Tricks

### 10.1 Developer Mode Activation

**Via URL:** Append `?debug=1` to any Odoo URL
- `http://localhost:8069/web?debug=1` — enables debug menu
- `http://localhost:8069/web?debug=assets` — enables assets debugging

**Via user interface:**
Settings → Dashboard → Developer Mode (first bullet)
Settings → Users & Companies → Select user → Developer Mode = True

**Via database:**
```sql
UPDATE res_users SET debug_mode = true WHERE id = 1;
```

### 10.2 Debug Assets Mode

When `debug=assets` is active:
- CSS and JS files are loaded individually (not bundled)
- Each file is editable in the browser
- Changes reflect immediately without server restart
- Essential for web client debugging

```
URL with debug=assets:
http://localhost:8069/web#debug=assets

Shows: Individual JS files in Network tab instead of bundle
```

### 10.3 Showing SQL in UI

With developer mode enabled:

1. **Activate SQL logging:** Settings → Developer → Manage Logs → Enable SQL
2. **See SQL in form view:** Click the SQL icon (eye with `{}`) on any form to see queries executed
3. **View performance:** Each query shows execution time in the debug panel

**From the web client:**
- Press `F12` to open DevTools
- Go to Network tab
- Filter by `sql` or `object` to see RPC calls with SQL

### 10.4 Interactive Technical Menu

With developer mode ON, a "Technical" menu appears in Settings:

| Menu Item | Purpose |
|-----------|---------|
| Views | Edit/view architecture, override views |
| Models | Inspect model fields, methods, inheritance |
| Scheduled Actions | Enable/disable cron jobs, view execution logs |
| Email Templates | View and edit email templates |
| Workflows | View workflow definitions (legacy, still in DB) |
| Low-Level Objects | Inspect ir.actions, ir.filters, etc. |

### 10.5 Fields and Views Management

**In developer mode, you can:**
- Edit views directly in the UI (for temporary debugging)
- Inspect any field's XML arch definition
- See which inherited views contribute to the final form
- Use "View Inheritance" to see extended views
- View "Manage Filters" to inspect search domains

**Quick inspect trick:**
1. Press `Ctrl + Alt + D` (or click the bug icon)
2. Click any field to see its properties
3. Shows: model, field name, type, stored/computed, dependencies

### 10.6 Debugging Computed Fields in UI

```python
# Add debug output to computed fields
@api.depends('partner_id', 'date_order')
def _compute_amount_total(self):
    for record in self:
        start = fields.Datetime.now()
        # ... computation ...
        elapsed = (fields.Datetime.now() - start).total_seconds()

        if elapsed > 0.5:  # Log if computation takes > 500ms
            _logger.warning(
                "Slow computed field on %s (ID %d): %.3fs",
                self._name, record.id, elapsed
            )

        record.amount_total = computed_value
```

### 10.7 Quick Test Without Code Change

Use the "Execute Python" technical feature:
1. Settings → Developer → Execute Python Code
2. Enter arbitrary Python with `self` and `env` in scope
3. Useful for: mass updating records, running migration scripts, testing queries

```python
# Example: fix all orders with missing warehouse
orders = env['sale.order'].search([('warehouse_id', '=', False)])
orders.write({'warehouse_id': env.ref('stock.warehouse0').id})
print(f"Updated {len(orders)} orders")
```

---

## 11. Debugging Workflow Patterns

### 11.1 Systematic Debugging Checklist

```
1. REPRODUCE — Can you reproduce the error consistently?
   ↓ No → Check data, check user context, check environment
   ↓ Yes → Continue

2. ISOLATE — Narrow down to the minimal scenario
   - Try with admin/sudo: does it work?
   - Try on a fresh database: does it work?
   - Try with minimal data: does it work?

3. LOCATE — Find the exact code that fails
   - Check the traceback line numbers
   - Check if the error is in custom or core code
   - Check if inheritance changes behavior

4. UNDERSTAND — Why does it fail?
   - What are the preconditions?
   - What assumption is violated?
   - Is it a data issue or a code bug?

5. FIX — Apply the fix
   - Is there a super() call missing?
   - Is there a field definition missing?
   - Is there a permission issue?

6. VERIFY — Test the fix
   - Does it work in dev?
   - Does it work in staging?
   - Does it cover edge cases?
```

### 11.2 Debugging by Error Type

| Error Type | First Step | Key Files to Check |
|------------|-----------|-------------------|
| AccessError | Check ACL CSV | `security/ir.model.access.csv` |
| MissingError | Check if record exists | Shell: `browse(id).exists()` |
| ValidationError | Check @api.constrains | Model file |
| UserError | Check business logic | Model method |
| ImportError | Check __manifest__.py | Module init files |
| AttributeError | Check _inherit chain | Model and parent classes |
| DatabaseError | Check SQL constraints | Model _sql_constraints |

### 11.3 Debugging Test Failures

```python
# When a test fails, add diagnostic output
def test_vendor_invoice_flow(self):
    # Create minimal test data
    vendor = self.create_vendor()
    product = self.create_product()

    # Get state before action
    _logger.debug("Before action: vendor state = %s, balance = %s",
                  vendor.state, vendor.total_due)

    # Perform action
    invoice = self.create_invoice(vendor, product)
    invoice.action_post()

    # Check state after
    _logger.debug("After action: invoice state = %s, payment_state = %s",
                  invoice.state, invoice.payment_state)

    # Assert with helpful message
    self.assertEqual(invoice.state, 'posted',
                    f"Expected state='posted', got '{invoice.state}'. "
                    f"Invoice: {invoice.name}, Partner: {invoice.partner_id.name}")
```

---

## Related Links

- [Core/API](../Core/API.md) — API decorators, onchange, depends
- [Core/BaseModel](../Core/BaseModel.md) — ORM internals, CRUD operations
- [Core/Exceptions](../Core/Exceptions.md) — Exception hierarchy (UserError, ValidationError, AccessError, MissingError)
- [Patterns/Workflow Patterns](../Patterns/Workflow Patterns.md) — State machines, action methods
- [Tools/Testing-Guide](Testing-Guide.md) — Writing and running tests
- [Core/Fields](../Core/Fields.md) — Field types, computed fields, storage
