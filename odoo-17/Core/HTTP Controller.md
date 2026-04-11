---
tags: [odoo, odoo17, http, controller]
---

# HTTP Controller

**File:** `odoo/odoo/http.py`

## @http.route

```python
@http.route('/my/route', type='http', auth='user', website=True)
def my_route(self, **kwargs):
    return request.render('module.template', {})
```

## Request Object

```python
request.env['model.name']  # env with website context
request.params              # query/form parameters
request.httprequest         # raw werkzeug request
request.session             # session data
request.render(template, qcontext)  # render template
```

## Response Methods

| Method | Use Case |
|--------|----------|
| `request.render()` | Render QWeb template |
| `request.make_json_response()` | JSON response |
| `request.redirect()` | HTTP redirect |
| `request.redirect_with_hash()` | Redirect preserving URL |

## Session Management

```python
request.session.setdefault('key', 'value')
session_uid = request.session.uid
```

## See Also
- [[Snippets/Controller Snippets]] — Code templates
- [[Core/API]] — Decorators
