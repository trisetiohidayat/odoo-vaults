---
tags: [odoo, odoo17, snippets]
---

# Controller Snippets

## Basic Controller

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my/page', type='http', auth='public', website=True)
    def index(self, **kwargs):
        return request.render('my_module.index', {
            'partner': request.env.user.partner_id,
        })
```

## JSON Controller

```python
@http.route('/my/data', type='json', auth='user')
    def get_data(self, **kwargs):
        return {
            'name': 'Test',
            'values': [1, 2, 3],
        }
```

## Auth Types

| Type | Description |
|------|-------------|
| `public` | Anyone (no login) |
| `user` | Must be logged in |
| `public` + `website=True` | Public with website session |
| `api_key` | API key authentication |

## Response Types

```python
# HTML
return request.render('module.template', {})

# JSON
return request.make_json_response({'key': 'value'})

# Redirect
return request.redirect('/web')

# File download
return request.make_response(
    file_content,
    headers=[('Content-Type', 'application/pdf')]
)
```

## Decorators

```python
@http.route('/page', type='http', auth='user', website=True,
            csrf=True, cors='*')
```

- `type='http'` — HTML response
- `type='json'` — JSON response
- `auth` — Authentication type
- `website=True` — Website-specific routing
- `csrf=True` — CSRF protection (default True)
- `cors='*'` — CORS headers

## See Also
- [Core/HTTP Controller](Core/HTTP-Controller.md) — Full controller reference
- [Patterns/Inheritance Patterns](Patterns/Inheritance-Patterns.md) — Controller extension
