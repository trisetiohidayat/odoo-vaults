---
type: snippets
name: Controller Snippets
version: Odoo 18
tags: [snippets, controller, http, web]
source: ~/odoo/odoo18/odoo/odoo/http.py
---

# Controller Snippets

## Basic Controller

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my/page', type='http', auth='user', website=True)
    def my_page(self, **kwargs):
        values = {
            'partner': request.env.user.partner_id,
        }
        return request.render('module.my_template', values)

    @http.route('/my/page/json', type='json', auth='user')
    def my_page_json(self, **kwargs):
        return {'status': 'ok', 'data': []}
```

## JSON Controller

```python
    @http.route('/my/api/records', type='json', auth='user', csrf=False)
    def get_records(self, limit=20, offset=0, **kwargs):
        records = request.env['my.model'].search_read(
            [],
            ['name', 'state'],
            limit=limit,
            offset=offset
        )
        return {
            'records': records,
            'total': request.env['my.model'].search_count([]),
        }
```

## File Download

```python
    @http.route('/my/download/<int:attachment_id>', type='http', auth='user')
    def download_attachment(self, attachment_id):
        attachment = request.env['ir.attachment'].browse(attachment_id)
        if not attachment.exists():
            return request.not_found()
        return http.Stream.from_attachment(attachment).get_response()
```

## Redirect with Warning

```python
    @http.route('/my/confirm/<int:order_id>', type='http', auth='user')
    def confirm_order(self, order_id):
        order = request.env['sale.order'].browse(order_id)
        if order.state != 'draft':
            return request.redirect('/my/orders?error=cannot_confirm')
        order.action_confirm()
        return request.redirect('/my/orders')
```

---

## Related Links
- [[Core/HTTP Controller]] — Full controller reference
- [[Snippets/Model Snippets]] — Model templates
