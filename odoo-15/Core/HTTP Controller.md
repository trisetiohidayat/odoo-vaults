# HTTP Controller

Dokumentasi Odoo 15 untuk web controller. Source: `odoo/odoo/http.py`

## Controller Base

```python
import odoo
from odoo import http

class MyController(http.Controller):
    _name = 'my.module.controller'
    _description = 'My Controller'
    _inherit = []  # or list of controllers to extend
    _log_access = False
```

## Routes (@http.route)

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my/module/page', type='http', auth='user', website=True)
    def page(self):
        return http.request.render('my_module.template', {})

    @http.route('/my/module/data', type='json', auth='user')
    def data(self):
        return {'result': 'ok'}

    # Multiple routes
    @http.route(['/path1', '/path2'], type='http', auth='user')
    def multi_path(self):
        pass

    # With parameters
    @http.route('/my/module/<model("my.model"):record>', type='http', auth='user')
    def with_record(self, record):
        return http.request.render('my_module.detail', {
            'record': record,
        })

    @http.route('/my/module/<int:id>', type='http', auth='user')
    def with_id(self, id):
        return http.request.render('my_module.detail', {
            'record': request.env['my.model'].browse(id),
        })

    @http.route('/my/module/<string:name>', type='http', auth='user')
    def with_name(self, name):
        pass
```

### Route Parameters

| Parameter | Type | Options | Description |
|---|---|---|---|
| `route` | str/list | - | URL path (can be list for multiple) |
| `type` | str | `'http'` / `'json'` | Response type |
| `auth` | str | `'none'`, `'public'`, `'user'`, `'api'` | Authentication type |
| `website` | bool | - | Enable website routing |
| `sitemap` | bool | - | Include in sitemap |
| `methods` | list | - | Allowed HTTP methods (GET, POST, etc.) |
| `csrf` | bool | - | Enable CSRF protection (default True for http) |
| `csrf` | bool | - | Disabled for json type by default |
| `login` | str | - | Forced login redirect |
| `redirect` | str | - | Redirect URL after login |
| `cors` | str | - | CORS allowed origins |
| `maxsize` | int | - | Max response size |

### Auth Types

| Auth | Behavior |
|---|---|
| `'none'` | Public access, no session |
| `'public'` | Public user (website visitor) |
| `'user'` | Must be logged in |
| `'api'` | API key authentication |

### CSRF Protection

```python
# Default for type='http': csrf=True
# Disable for form submissions:
@http.route('/my/form', type='http', auth='user', csrf=True/False)

# For json: csrf=False by default
```

## Request Object

```python
from odoo import http

class MyController(http.Controller):

    @http.route('/my/module/action', auth='user')
    def action(self):
        # Current request
        request = http.request

        # GET parameters
        request.params.get('key')

        # POST parameters
        request.httprequest.form  # form data
        request.httprequest.files  # file uploads

        # Session
        request.session  # session dict
        request.session.uid  # logged in user
        request.session.get_context()  # context

        # Context
        request.env  # environment
        request.env.context  # context dict

        # Common use: qweb render
        return request.render('module.template_id', {
            'qweb_var': value,
        })
```

## Response Types

### HTML Response (QWeb)

```python
return http.request.render('my_module.template', {
    'values': data,
})

# With status code
return http.request.render('my_module.template', {}, status=404)
```

### JSON Response

```python
# type='json' routes
return {
    'jsonrpc': '2.0',
    'id': None,
    'result': {...},
}
# Auto-wrapped in Response by JsonRpc
```

### Redirect

```python
# Redirect to another page
return request.redirect('/web/login')

# With query params
return request.redirect('/my/page?param=value')

# 302 redirect
return werkzeug.wrappers.Response(
    status=302,
    headers=[('Location', '/web/login')],
)
```

### XML Response

```python
from odoo.tools.safe_eval import safe_eval

xml_data = '<?xml version="1.0"?><data>...</data>'
return request.make_response(
    xml_data.encode('utf-8'),
    [('Content-Type', 'application/xml')],
)
```

### Binary Response

```python
# File download
return http.request.make_response(
    file_content,
    [('Content-Type', 'application/pdf')],
    [('Content-Disposition', 'attachment; filename="report.pdf"')],
)

# With dynamic filename
response = http.request.make_response(file_content, headers)
response.headers['Content-Disposition'] = 'attachment; filename="file.pdf"'
return response
```

## Model Access in Controller

```python
def action(self):
    # Use request.env like in ORM
    records = request.env['my.model'].sudo().search([...])

    # With specific user
    records = request.env['my.model'].with_user(uid).search([...])

    # With context
    records = request.env['my.model'].with_context(tz='UTC').search([...])
```

## Error Handling

```python
from odoo.exceptions import ValidationError, AccessError
from odoo import _

class MyController(http.Controller):

    @http.route('/my/module/action', auth='user')
    def action(self, **kwargs):
        try:
            result = self._do_something(kwargs)
            return request.render('my_module.success', {'result': result})
        except ValidationError as e:
            return request.render('my_module.error', {
                'error': str(e),
            })
        except AccessError:
            return request.not_found()
```

### HTTP Error Responses

```python
# 404 Not Found
return request.not_found()

# 403 Forbidden
return request.redirect('/web/database/selector')

# 500 Internal Error
return request.render('web.http_error', {
    'status_code': 500,
    'status_text': 'Internal Error',
})
```

## Session Management

```python
# Get session
session = http.request.session

# Session data
session.uid           # User ID
session.login         # Login name
session.session_token # Token for auth
session.context       # Context dict

# Set session data
session['my_key'] = 'value'

# Clear session
session.logout()
```

## Model Controller Pattern (CRUD via JSON)

```python
from odoo.http import request, JsonRequest

class MyAPIController(http.Controller):

    @http.route('/api/my/model', type='json', auth='api', methods=['POST'])
    def create(self, vals, **kwargs):
        record = request.env['my.model'].create(vals)
        return {'id': record.id, 'name': record.name}

    @http.route('/api/my/model/<int:id>', type='json', auth='api', methods=['GET'])
    def read(self, id, **kwargs):
        record = request.env['my.model'].browse(id)
        return {
            'id': record.id,
            'name': record.name,
            'value': record.value,
        }

    @http.route('/api/my/model/<int:id>', type='json', auth='api', methods=['PUT'])
    def write(self, id, vals, **kwargs):
        record = request.env['my.model'].browse(id)
        record.write(vals)
        return {'result': True}

    @http.route('/api/my/model/<int:id>', type='json', auth='api', methods=['DELETE'])
    def unlink(self, id, **kwargs):
        record = request.env['my.model'].browse(id)
        record.unlink()
        return {'result': True}
```

## See Also
- [Snippets/Controller Snippets](Snippets/Controller Snippets.md) — Code templates
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — Auth types, access control
- [Core/Exceptions](Core/Exceptions.md) — Error handling