---
type: core
name: HTTP Controller
version: Odoo 18
tags: [core, http, controller, web]
source: ~/odoo/odoo18/odoo/odoo/http.py
---

# HTTP Controller

Web request handlers for Odoo via `http.Controller`.

## Basic Controller

```python
from odoo import http
from odoo.http import request

class SaleController(http.Controller):

    @http.route('/my/sales', type='http', auth='user', website=True)
    def my_sales(self):
        orders = request.env['sale.order'].search([])
        return request.render('module.template', {'orders': orders})

    @http.route('/my/sales/json', type='json', auth='user')
    def my_sales_json(self):
        orders = request.env['sale.order'].search_read([], ['name', 'state', 'date_order'])
        return {'orders': orders}
```

## Auth Types

| Auth | Description |
|------|-------------|
| `user` | Requires logged-in user (default) |
| `public` | Allows public/guest access |
| `none` | No auth — use for internal routes only |
| `api_key` | Authenticate via API key |

## Route Parameters

```python
@http.route('/sale/order/<int:order_id>/confirm',
            type='http',     # 'http' or 'json'
            auth='user',      # auth type
            website=True,     # make available in website routing
            sitemap=False,    # skip sitemap generation
            csrf=True,        # CSRF protection (True default)
            methods=['POST'], # allowed HTTP methods
            login=None,       # force specific login
           )
```

## Request/Response

```python
# GET params
@http.route('/search', type='http', auth='user')
def search(self, q='', limit=10, **kwargs):
    query = request.params.get('q', '')

# JSON response
return request.make_json_response({'status': 'ok', 'data': result})

# HTTP redirect
return request.redirect('/my/home')

# File response
return request.make_response(
    pdf_bytes,
    headers=[('Content-Type', 'application/pdf'),
             ('Content-Disposition', 'attachment; filename=report.pdf')]
)

# Binary file from attachment
return http.Stream.from_attachment(attachment).get_response()
```

## Decorators

```python
# Validate CSRF only for non-API routes
@http.route('/submit', type='http', csrf=False)
def submit(self):
    pass  # use for AJAX APIs

# website=True routes automatically get website layout
@http.route('/page', type='http', auth='user', website=True)
def page(self, **kwargs):
    return request.render('module.my_template', {})
```

---

## Related Links
- [Core/Exceptions](Core/Exceptions.md) — Error handling
- [Snippets/Controller Snippets](Snippets/Controller Snippets.md) — Copy-paste templates
