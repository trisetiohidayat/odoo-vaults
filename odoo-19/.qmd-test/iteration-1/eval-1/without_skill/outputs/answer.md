# Difference Between `_inherit` and `_inherits` in Odoo

## `_inherit` — Classic (Extension) Inheritance

`_inherit` extends or modifies an existing model. It adds fields, override methods, and extra behavior to the parent model. The child model **replaces** the parent model in the registry — only one model entry exists.

**Use case:** You want to add fields or override methods of an existing model.

```python
from odoo import models

class ExtensionModel(models.Model):
    _name = 'extension.model'
    _inherit = 'res.partner'  # Extends res.partner

    x_custom_field = fields.Char(string="Custom Field")
```

In this example, `extension.model` adds `x_custom_field` to `res.partner`. When you install a module with this model, the `res.partner` form now has the extra field. You **can** override existing methods by defining a method with the same name.

**Key behavior:**
- Single entry in the registry (the parent is replaced)
- All `_inherit` chains merge into one model
- If multiple modules inherit the same model, all fields accumulate
- You can override methods of the parent

---

## `_inherits` — Delegation (Multi-table) Inheritance

`_inherits` creates a **new model** that stores data in its own table, while delegating unresolved field lookups to the parent model via a Many2one relationship. The child model has its own table with a foreign key to the parent's table.

**Use case:** You want to create a specialized subtype of an existing model.

```python
from odoo import models, fields

class Employee(models.Model):
    _name = 'specialized.employee'
    _inherits = {'res.partner': 'partner_id'}  # Delegation inheritance

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    employee_code = fields.Char(string="Employee Code")
```

Now `specialized.employee` has its own table, but field lookups not found in `specialized.employee` are delegated to `res.partner` through `partner_id`. In the UI, the employee record looks and behaves like a partner record for delegated fields (name, email, address, etc.).

**Key behavior:**
- Two database tables (child table + parent table via Many2one)
- Creating a child record automatically creates the parent record
- Deleting the child cascades-deletes the parent
- The child is a distinct model in the registry — the parent is not replaced
- You **cannot** override parent methods with `_inherits`

---

## Side-by-Side Comparison

| Aspect               | `_inherit`                          | `_inherits`                              |
|----------------------|-------------------------------------|------------------------------------------|
| Registry entry       | Single (replaces parent)            | Two (child + parent both exist)          |
| Database table       | Single table                        | Two tables (child + delegated parent)     |
| Method overriding    | Yes                                 | No (delegation, not extension)            |
| Use case             | Extend/modify existing model        | Create a specialized subtype             |
| Deleting child       | N/A                                 | Cascades to parent via FK                |
| Multiple inheritance | `_inherit = ['a', 'b']` merges all  | Only one parent allowed                  |

---

## Practical Example: When to Use Which

### `_inherit` — Adding a field to `res.partner`
```python
class ResPartnerExtension(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    loyalty_points = fields.Integer(string="Loyalty Points")
```
This adds `loyalty_points` to every partner in the system.

### `_inherits` — Creating a `hospital.patient` subtype of `res.partner`
```python
class HospitalPatient(models.Model):
    _name = 'hospital.patient'
    _inherits = {'res.partner': 'partner_id'}

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    blood_type = fields.Selection([('A', 'A'), ('B', 'B'), ('O', 'O'), ('AB', 'AB')], string="Blood Type")
```
`hospital.patient` is a distinct model, but it automatically inherits all partner fields (name, address, email, etc.) via delegation.