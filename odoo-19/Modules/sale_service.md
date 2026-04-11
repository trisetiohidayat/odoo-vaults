---
tags:
  - #odoo19
  - #modules
  - #sale
  - #service
---

# sale_service

**Module:** `sale_service`
**Path:** `odoo/addons/sale_service/`
**Dependencies:** `sale_management`
**Category:** Sales/Sales
**License:** LGPL-3

---

## Overview

`sale_service` adalah module fondasi yang menyediakan layer service-aware untuk Sales Order Lines. Module ini menentukan **apa yang membuat sebuah product line menjadi "service"**, serta menyediakan infrastruktur untuk searching dan displaying service lines secara efisien. Module ini adalah **prerequisite** untuk `sale_project` dan menyediakan domain helpers yang digunakan di banyak tempat dalam ekosistem sales-service-project.

**Important:** `sale_service` **tidak** membuat project/task secara otomatis. Itu adalah tanggung jawab `sale_project` yang depend pada `sale_service`. `sale_service` murni menyediakan:
1. `is_service` field computation
2. Domain helpers untuk filtering service SOLs
3. Performance-optimized name search
4. Display name formatting dengan price

---

## Historical Note

`sale_service` adalah module yang sudah ada sejak lama di Odoo. Ini adalah **predecessor** dari `sale_purchase` -- pada versi lama Odoo, mekanisme task creation dari SOL ditangani sepenuhnya di `sale_service`. Dengan refactoring di Odoo 17+, banyak logic dipindah keluar ke:
- `sale_project` (task/project creation)
- `sale_purchase` (PO generation)
- `sale_timesheet` (timesheet billing)

---

## Models

### `sale.order.line` (from `sale_service/models/sale_order_line.py`)

Module ini melakukan **classical inheritance** pada `sale.order.line` untuk menambahkan kemampuan service-aware.

---

### `is_service` Field

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    _name_search_services_index = models.Index(
        "(order_id DESC, sequence, id) WHERE is_service IS TRUE"
    )

    is_service = fields.Boolean(
        "Is a Service", 
        compute='_compute_is_service', 
        store=True, 
        compute_sudo=True,
        export_string_translation=False
    )

    @api.depends('product_id.type')
    def _compute_is_service(self):
        self.fetch(['is_service', 'product_id'])
        self.product_id.fetch(['type'])
        for so_line in self:
            so_line.is_service = so_line.product_id.type == 'service'
```

#### `is_service` Behavior

| Product Type | `is_service` |
|-------------|-------------|
| `service` | `True` |
| `product` | `False` |
| `consu` (consumable) | `False` |
| `any上記以外` | `False` |

#### Database Optimization

```python
def _auto_init(self):
    """
    Create column to stop ORM from computing it himself (too slow).
    Instead, we manually populate via SQL on install/upgrade.
    """
    if not column_exists(self.env.cr, 'sale_order_line', 'is_service'):
        create_column(self.env.cr, 'sale_order_line', 'is_service', 'bool')
        self.env.cr.execute("""
            UPDATE sale_order_line line
            SET is_service = (pt.type = 'service')
            FROM product_product pp
            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
            WHERE pp.id = line.product_id
        """)
    return super()._auto_init()
```

**Performance insight:** `is_service` adalah stored computed field. Kenapa? Karena `is_service` di-filter di **hampir setiap query** yang melibatkan SOL dan project/task. Tanpa store, setiap kanban/list view load akan recalculate semua SOL.

**Index:** `_name_search_services_index` adalah partial B-tree index yang hanya mengindeks rows dengan `is_service = TRUE`. Ini membuat name search untuk service lines sangat cepat.

---

### Domain Helper: `_domain_sale_line_service()`

```python
def _domain_sale_line_service(self, **kwargs):
    """
    Get the default generic services domain for sale.order.line.
    You can filter out domain leafs by passing kwargs of the form 'check_<leaf_field>=False'.
    Only 'is_service' cannot be disabled.
    """
    domain = [('is_service', '=', True)]
    if kwargs.get("check_is_expense", True):
        domain.append(('is_expense', '=', False))
    if kwargs.get("check_state", True):
        domain.append(('state', '=', 'sale'))
    return domain
```

#### Usage in `sale_project`

`sale_project/models/project_project.py`:
```python
def _domain_sale_line_id(self):
    return Domain.AND([
        self.env['sale.order.line']._sellable_lines_domain(),
        self.env['sale.order.line']._domain_sale_line_service(),
        [('order_partner_id', '=?', "partner_id")],
    ])
```

`sale_project/models/project_task.py`:
```python
def _domain_sale_line_id(self):
    domain = Domain.AND([
        self.env['sale.order.line']._sellable_lines_domain(),
        self.env['sale.order.line']._domain_sale_line_service(),
        ['|',
            ('order_partner_id.commercial_partner_id.id', 'parent_of', unquote('partner_id if partner_id else []')),
            ('order_partner_id', '=?', unquote('partner_id')),
        ],
    ])
    return domain
```

#### `kwargs` Flags

| Flag | Default | Effect |
|------|---------|--------|
| `check_is_expense` | `True` | Filter out `is_expense = True` (expense-based SOL tidak muncul di project SOL selector) |
| `check_state` | `True` | Filter `state = 'sale'` (hanya confirmed SOL) |
| Any other | N/A | No effect |

**Use case untuk override flags:**
- `sale_purchase` mungkin butuh `check_is_expense=False` untuk expense-based SOL
- Reports mungkin butuh `check_state=False` untuk melihat semua SOL

---

### Performance-Optimized Name Search

```python
@api.model
def name_search(self, name='', domain=None, operator='ilike', limit=100):
    domain = domain or []
    # Optimization for SOL services name_search
    if (domain 
        and ('is_service', '=', True) in domain 
        and operator in ('like', 'ilike') 
        and limit is not None):
        # Use pre-filtered index untuk speed
        sols = self.search_fetch(
            domain, 
            ['display_name'], 
            limit=limit, 
            order='order_id.id DESC, sequence, id',  # sesuai index
        )
        return [(sol.id, sol.display_name) for sol in sols]
    return super().name_search(name, domain, operator, limit)
```

**Performance insight:** Tanpa optimization ini, name_search untuk service SOL akan JOIN ke `sale_order` table yang sangat besar. Dengan partial index + `search_fetch`, query langsung baca dari index tanpa full table scan.

---

### Display Name Formatting

```python
def _additional_name_per_id(self):
    name_per_id = super()._additional_name_per_id() if not self.env.context.get('hide_partner_ref') else {}
    if not self.env.context.get('with_price_unit'):
        return name_per_id

    # Group by (order, product) untuk mengelompokkan SOL yang sama
    sols_list = [list(sols) for dummy, sols in groupby(
        self, lambda sol: (sol.order_id, sol.product_id)
    )]
    for sols in sols_list:
        # Hanya process jika semua SOL adalah service dan ada lebih dari 1
        if len(sols) <= 1 or not all(sol.is_service for sol in sols):
            continue
        for line in sols:
            additional_name = name_per_id.get(line.id)
            name = format_amount(self.env, line.price_unit, line.currency_id)
            if additional_name:
                name += f' {additional_name}'
            name_per_id[line.id] = f'- {name}'

    return name_per_id
```

**Effect:** Ketika `with_price_unit` context aktif (misalnya di project/task kanban view), SOL display name berubah dari:
```
[Laptop] - John Doe - Standard
```
menjadi:
```
[Laptop] - John Doe - Standard - $150.00
```

Ini membantu user membedakan antar SOL dengan harga berbeda.

---

## How `is_service` Drives Other Modules

### In `sale_project`

1. **Project creation:** `allow_billable = True` hanya untuk project dari service SOL
2. **Task SOL selector:** Domain `_domain_sale_line_service()` memastikan hanya service SOL yang bisa diassign ke task
3. **Milestone:** `qty_delivered_method = 'milestones'` hanya untuk service products

### In `sale_purchase`

```python
# sale_purchase/models/sale_order_line.py
def _purchase_service_generation(self):
    for line in self:
        if line.product_id.service_to_purchase and not line.purchase_line_count:
            # service_to_purchase implies is_service
            line._purchase_service_create()
```

### In `sale_timesheet`

```python
# Timesheet validation
def _validate_timesheet(self, values):
    # ...
    if line.so_line.is_service:
        # Service-specific validation
```

---

## Relationship: `is_service` vs `is_expense`

| Field | Set By | Purpose |
|-------|--------|---------|
| `is_service` | `sale_service` | Product type = service |
| `is_expense` | `sale_expense` | SOL dibuat dari expense reimbursement |

**Constraint in `sale_project`:**
```python
@api.constrains('sale_line_id')
def _check_sale_line_type(self):
    if task.sale_line_id:
        if not task.sale_line_id.is_service or task.sale_line_id.is_expense:
            raise ValidationError(_(
                'Cannot link expense SOL to task'
            ))
```

**Key insight:** Expense-based SOL (`is_expense=True`) tetap `is_service=True` tapi **tidak bisa** di-link ke task di project billing context. Mereka menggunakan flow berbeda (`sale_expense`).

---

## `service_tracking` vs `is_service`

Dua concept berbeda namun saling terkait:

| Concept | Where Defined | What it Controls |
|---------|--------------|-----------------|
| `is_service` | `sale_service` (compute) | Apakah product type = service |
| `service_tracking` | `sale` (on `product.product`) | Bagaimana SOL berinteraksi dengan project/task |

### `service_tracking` Options

| Value | Label | Behavior on SO Confirm |
|-------|-------|------------------------|
| `'no_project'` | No tracking | Buat analytic account only |
| `'task_in_project'` | Create a task in an existing project | Buat task di project yang dipilih |
| `'project_only'` | Create a task in a new project | Buat project baru + task |
| `'task_global'` | Create a task | Buat global task (tanpa project) |

**Correlation:**
- `service_tracking` != `'no_project'` → SOL terkait project/task
- Project/task creation logic ada di `sale_project`, dipicu via `_timesheet_service_generation()`

---

## Key Extension Points

| Extension Point | Method | Purpose |
|----------------|--------|---------|
| Service definition | `_compute_is_service()` | Override untuk custom "service" criteria |
| Service domain | `_domain_sale_line_service()` | Override untuk custom filtering rules |
| Name search | `name_search()` | Override untuk custom SOL search behavior |
| Display name | `_additional_name_per_id()` | Override untuk custom display format |

---

## Module Dependency Diagram

```
sale_service (base service layer)
  │
  ├── sale_management
  │     └── sale
  │
  ├── sale_project (depends on sale_service)
  │     ├── project_account
  │     │     ├── project
  │     │     └── account
  │     └── sale_service ← uses is_service, _domain_sale_line_service()
  │
  ├── sale_purchase (does NOT depend on sale_service)
  │     ├── sale
  │     └── purchase
  │
  └── sale_timesheet (depends on sale_service)
        ├── project
        ├── sale_service ← uses is_service
        └── hr_timesheet
```

---

## See Also

- [[Modules/sale_project]] -- Project/task creation dari SOL (depends on sale_service)
- [[Modules/sale_purchase]] -- PO generation dari SOL (independent from sale_service)
- [[Modules/sale_expense]] -- Expense reinvoicing (sets is_expense)
- [[Modules/sale]] -- Base sale.order.line model
- [[Core/Fields]] -- Field types, compute fields, store parameter
