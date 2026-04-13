# Controller Snippets

Code templates untuk membuat web controller Odoo 15.

## Basic Controller

```python
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class MyController(http.Controller):

    @http.route('/my_module/page', type='http', auth='public', website=True)
    def page(self, **kwargs):
        return http.request.render('my_module.page_template', {})

    @http.route('/my_module/data', type='json', auth='user')
    def data(self, **kwargs):
        return {'result': 'ok'}
```

## Route with Parameters

```python
from odoo import http
from odoo.http import request, Response
import json


class ProductController(http.Controller):

    # Path parameter (model browse)
    @http.route('/my_module/product/<model("product.product"):product>',
                type='http', auth='public', website=True)
    def product_detail(self, product, **kwargs):
        return request.render('my_module.product_detail', {
            'product': product,
        })

    # Integer ID parameter
    @http.route('/my_module/product/<int:product_id>', type='http',
                auth='user', website=True)
    def product_by_id(self, product_id, **kwargs):
        product = request.env['product.product'].browse(product_id)
        if not product.exists():
            return request.not_found()
        return request.render('my_module.product_detail', {
            'product': product,
        })

    # String parameter
    @http.route('/my_module/search/<string:query>', type='http',
                auth='user', website=True)
    def search(self, query, **kwargs):
        products = request.env['product.product'].search([
            ('name', 'ilike', query),
        ], limit=20)
        return request.render('my_module.product_list', {
            'products': products,
            'query': query,
        })
```

## Form Submission

```python
from odoo import http, _
from odoo.exceptions import ValidationError


class ContactController(http.Controller):

    @http.route('/my_module/contact/submit', type='http', auth='public',
                website=True, csrf=True)
    def contact_submit(self, **post):
        # Validate
        if not post.get('name'):
            return request.render('my_module.contact_error', {
                'error': _('Name is required'),
            })

        # Create record
        request.env['crm.lead'].sudo().create({
            'name': post.get('name'),
            'email_from': post.get('email'),
            'phone': post.get('phone'),
            'description': post.get('message'),
            'team_id': False,
        })

        return request.render('my_module.contact_success', {})

    @http.route('/my_module/contact/ajax', type='json', auth='public',
                csrf=False)
    def contact_ajax(self, **data):
        try:
            record = request.env['crm.lead'].sudo().create({
                'name': data.get('name', ''),
                'email_from': data.get('email', ''),
                'description': data.get('message', ''),
            })
            return {'success': True, 'id': record.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}
```

## JSON API

```python
from odoo import http
from odoo.http import request, JsonRpcResponse
import json


class APIController(http.Controller):

    @http.route('/api/v1/my_model', type='json', auth='api', methods=['POST'])
    def create_my_model(self, vals, **kwargs):
        """Create new record"""
        record = request.env['my.model'].create(vals)
        return {'id': record.id, 'name': record.name}

    @http.route('/api/v1/my_model/<int:id>', type='json', auth='api', methods=['GET'])
    def read_my_model(self, id, **kwargs):
        """Read single record"""
        record = request.env['my.model'].browse(id)
        if not record.exists():
            return {'error': 'Record not found'}, 404
        fields = kwargs.get('fields', ['name', 'code', 'state'])
        data = record.read(fields)[0]
        return data

    @http.route('/api/v1/my_model/<int:id>', type='json', auth='api', methods=['PUT'])
    def update_my_model(self, id, vals, **kwargs):
        """Update record"""
        record = request.env['my.model'].browse(id)
        record.write(vals)
        return {'result': True}

    @http.route('/api/v1/my_model/<int:id>', type='json', auth='api', methods=['DELETE'])
    def delete_my_model(self, id, **kwargs):
        """Delete record"""
        record = request.env['my.model'].browse(id)
        record.unlink()
        return {'result': True}

    @http.route('/api/v1/my_model/search', type='json', auth='api', methods=['POST'])
    def search_my_model(self, domain=None, fields=None, offset=0, limit=100, **kwargs):
        """Search records"""
        domain = domain or []
        records = request.env['my.model'].search(domain, offset=offset, limit=limit)
        if fields:
            return records.read(fields)
        return records.read()
```

## Session Management

```python
from odoo import http


class SessionController(http.Controller):

    @http.route('/my_module/check_session', type='http', auth='none')
    def check_session(self, **kwargs):
        session = http.request.session
        if session.uid:
            user = http.request.env['res.users'].browse(session.uid)
            return {'logged_in': True, 'user': user.name}
        return {'logged_in': False}

    @http.route('/my_module/set_session_data', type='json', auth='user')
    def set_data(self, key, value, **kwargs):
        http.request.session[key] = value
        return {'result': 'ok'}

    @http.route('/my_module/get_session_data', type='json', auth='user')
    def get_data(self, key, **kwargs):
        return {'key': key, 'value': http.request.session.get(key)}

    @http.route('/my_module/logout', type='http', auth='user')
    def logout(self, **kwargs):
        http.request.session.logout(keep_db=True)
        return http.request.redirect('/web/login')
```

## QWeb Rendering

```python
from odoo import http


class ReportController(http.Controller):

    @http.route('/my_module/report/<int:id>', type='http', auth='user')
    def get_report(self, id, **kwargs):
        record = http.request.env['my.model'].browse(id)
        return http.request.render('my_module.report_template', {
            'docs': record,
            'data': {
                'company': http.request.env.company,
                'user': http.request.env.user,
                'print_date': http.request.fields.Date.today(),
            },
        })
```

## Redirect with Error

```python
from odoo import http
from odoo.exceptions import UserError


class FormController(http.Controller):

    @http.route('/my_module/process', type='http', auth='user',
                website=True, csrf=True)
    def process(self, **post):
        try:
            record = http.request.env['my.model'].create({
                'name': post.get('name'),
            })
            return http.request.redirect('/my_module/success/%d' % record.id)
        except UserError as e:
            return http.request.render('my_module.error_page', {
                'error': str(e),
            })
```

## See Also
- [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) — HTTP controller reference
- [Core/Exceptions](odoo-18/Core/Exceptions.md) — Error handling
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — Auth types