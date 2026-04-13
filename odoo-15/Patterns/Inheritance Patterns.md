# Inheritance Patterns

Dokumentasi Odoo 15 untuk model inheritance mechanisms.

## Three Types of Inheritance

### 1. Extension (`_inherit` with same `_name`)

Model mewarisi semua field, method, dan behavior dari parent, lalu extend dengan field/method baru.

```python
# Parent model
class OriginalModel(models.Model):
    _name = 'original.model'
    _description = 'Original Model'

    name = fields.Char('Name')
    code = fields.Char('Code')

    def do_something(self):
        pass

# Child model - EXTENDS the parent
class ExtendedModel(models.Model):
    _name = 'original.model'  # SAME name = extend
    _inherit = 'original.model'

    new_field = fields.Char('New Field')

    # Override existing method
    def do_something(self):
        # Call parent
        result = super().do_something()
        # Add extension
        return result + " extended"
```

**Result:** Single model `original.model` dengan semua field parent + `new_field`.

### 2. Classical / Parallel Inheritance (`_inherit` with different `_name`)

Multiple inheritance. Child mengambil semua dari parent yang di-inherit.

```python
class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'
    _inherit = ['parent.model.1', 'parent.model.2']

    # Own fields
    name = fields.Char('Name')

# Result: my.model has fields from model.1 AND model.2
```

**Use case:** Mixin behavior dari multiple sources. Berbeda dengan OOP Python inheritance — ini adalah mechanism Odoo yang memetakan semua parent fields ke model baru.

### 3. Delegation (`_inherits`)

Komposisi via foreign key. Child memiliki semua parent field, diakses via `parent_id` field.

```python
class ParentModel(models.Model):
    _name = 'parent.model'
    _description = 'Parent Model'

    name = fields.Char('Name')
    email = fields.Char('Email')

class ChildModel(models.Model):
    _name = 'child.model'
    _description = 'Child Model'
    _inherits = {'parent.model': 'parent_id'}

    # Own fields only
    child_field = fields.Char('Child Field')

    # Inherited fields accessible directly:
    # self.name -> self.parent_id.name
    # self.email -> self.parent_id.email
```

**Behavior:**
- `child.model` punya FK ke `parent.model` (field `parent_id`)
- Semua field parent otomatis accessible di child
- Child record otomatis membuat parent record (via `_inherits`)
- Delete child → delete parent (cascade)

## Comparison Table

| Aspect | Extension (`_inherit` same name) | Classical (`_inherit` diff name) | Delegation (`_inherits`) |
|---|---|---|---|
| Model count | 1 | 1+ (merged) | 2 (separate tables) |
| Parent fields | In same table | In same table | Via FK |
| Method override | Yes (super()) | Yes | No (separate model) |
| Cascade delete | N/A | N/A | Yes (parent deleted) |
| Use case | Extend existing model | Mixin behaviors | Object composition |

## Mixin Pattern (Abstract Model)

Abstract model untuk reuse behavior tanpa standalone table.

```python
# Abstract mixin - provides common fields and methods
class AbstractMixin(models.AbstractModel):
    _name = 'abstract.mixin'
    _description = 'Abstract Mixin'

    create_date = fields.Datetime('Create Date', readonly=True)
    write_date = fields.Datetime('Write Date', readonly=True)

    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record._name}[{record.id}]"

# Use mixin in concrete model
class MyConcreteModel(models.Model):
    _name = 'my.concrete'
    _inherit = ['abstract.mixin', 'other.mixin']

    name = fields.Char('Name')

    # Has all fields and methods from abstract.mixin
```

**Key:** `_register` is False untuk abstract models. Tidak membuat database table.

## Extension Patterns

### Add Field to Existing Model

```python
# Extend sale.order to add custom field
class SaleOrderExt(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    x_custom_field = fields.Char('Custom Field')
```

### Add Method to Existing Model

```python
class SaleOrderExt(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def _compute_x_total_weight(self):
        for order in self:
            order.x_total_weight = sum(order.mapped('order_line.weight'))

    x_total_weight = fields.Float(
        'Total Weight',
        compute='_compute_x_total_weight',
        store=True,
    )
```

### Override Existing Method

```python
class SaleOrderExt(models.Model):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def action_confirm(self):
        # Custom logic before
        self._validate_custom_constraint()
        # Call parent
        result = super().action_confirm()
        # Custom logic after
        self._post_confirm_actions()
        return result
```

## See Also
- [[Core/BaseModel]] — Model definition basics
- [[Core/API]] — @api.depends, @api.onchange
- [[Modules/Sale]] — Sale order inheritance examples
- [[Modules/Stock]] — Stock picking inheritance examples