---
type: snippet
tags: [odoo, odoo19, snippet, controller, template, http]
created: 2026-04-06
---

# Controller Snippets

## Basic Controller

```python
from odoo import http
from odoo.http import request

class MyController(http.Controller):

    @http.route('/my/module/page', type='http', auth='user')
    def my_page(self, **kwargs):
        values = {
            'data': 'Hello World',
        }
        return http.request.render('my_module.template', values)
```

## JSON Controller

```python
@http.route('/my/module/json', type='json', auth='user')
def my_json(self, **kwargs):
    records = request.env['my.model'].search([])
    return {
        'status': 'ok',
        'count': len(records),
        'data': records.read(['name', 'active']),
    }
```

## With Parameters

```python
@http.route('/my/module/<int:record_id>', type='http', auth='user')
def my_record(self, record_id, **kwargs):
    record = request.env['my.model'].browse(record_id)
    if not record.exists():
        return request.not_found()
    return http.request.render('my_module.record', {
        'record': record,
    })
```

## Website Controller

```python
@http.route(['/page/<model("my.model"):record>'],
            type='http', auth="public", website=True, sitemap=True)
def page(self, record, **kwargs):
    return http.request.render('my_module.page', {
        'record': record,
    })
```

## Form Submission

```python
@http.route('/my/module/submit', type='http', auth='user',
            methods=['POST'], csrf=False)
def submit(self, **post):
    # Process form
    name = post.get('name')

    record = request.env['my.model'].create({
        'name': name,
    })

    return http.request.redirect('/my/module/%d' % record.id)
```

## Multi-record Route

```python
@http.route('/my/module/list/<ids>', type='http', auth='user')
def my_list(self, ids, **kwargs):
    # ids = "1,2,3"
    record_ids = [int(i) for i in ids.split(',')]
    records = request.env['my.model'].browse(record_ids)

    return http.request.render('my_module.list', {
        'records': records,
    })
```

## Related

- [Core/HTTP Controller](odoo-18/Core/HTTP Controller.md) - Full controller reference
- [Core/BaseModel](Core/BaseModel.md) - Models in controllers
- [Core/API](Core/API.md) - ORM access
- [Core/Exceptions](Core/Exceptions.md) - Error handling
