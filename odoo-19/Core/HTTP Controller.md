---
type: core
module: http
tags: [odoo, odoo19, http, controller, web, api]
created: 2026-04-06
---

# HTTP Controller

## Overview

Controllers handle HTTP requests for web interface.

**Location:** `~/odoo/odoo19/odoo/odoo/http.py`

## Basic Controller

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my/module/page', type='http', auth='user')
    def my_page(self, **kwargs):
        values = {
            'partner': request.env.user.partner_id,
        }
        return http.request.render('my_module.template', values)
```

## @http.route Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `route` | string/tuple | URL path(s) |
| `type` | http/json | Response type |
| `auth` | user/public/none | Authentication |
| `methods` | list | Allowed HTTP methods |
| `csrf` | bool | CSRF protection (default: True) |
| `website` | bool | Website mode |
| `sitemap` | bool | Sitemap inclusion |

## Authentication

```python
# Login required
@http.route('/page', auth='user')

# Public access
@http.route('/page', auth='public')

# No session check
@http.route('/page', auth='none')
```

## JSON API

```python
@http.route('/my/module/json', type='json', auth='user')
def my_json(self, **kwargs):
    records = request.env['my.model'].search([])
    return {
        'status': 'ok',
        'data': records.read(['name', 'active']),
    }
```

## Response Types

```python
# HTML Template
return http.request.render('module.template', values)

# JSON
return {'key': 'value'}

# Redirect
return http.redirect('/web/login')

# File
return http.request.make_response(data, headers=[
    ('Content-Type', 'application/pdf'),
])
```

## Related

- [Core/BaseModel](odoo-18/Core/BaseModel.md) - Models in controllers
- [Core/Fields](odoo-18/Core/Fields.md) - Field types
- [Core/API](odoo-18/Core/API.md) - ORM access
- [Core/Exceptions](odoo-18/Core/Exceptions.md) - Error handling
- [Modules/Sale](odoo-18/Modules/sale.md) - Example controller
