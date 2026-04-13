# res.partner — Partners & Contacts

Dokumentasi Odoo 15 untuk Partner model. Source: `odoo/addons/base/models/res_partner.py`

## Model

```python
class Partner(models.Model):
    _name = "res.partner"
    _description = "Contact"
    _order = "display_name"
```

## Key Fields

### Identification

| Field | Type | Description |
|---|---|---|
| `name` | Char | Contact name |
| `display_name` | Char | Full display name (computed) |
| `ref` | Char | Reference/Code |
| `active` | Boolean | Active |
| `company_id` | Many2one(res.company) | Company |
| `company_name` | Char | Company name (for individual) |

### Type & Category

| Field | Type | Description |
|---|---|---|
| `type` | Selection | contact/invoice/delivery/private |
| `category_id` | Many2many(res.partner.category) | Tags/Categories |
| `title` | Many2one(res.partner.title) | Title (Mr/Ms/Dr) |
| `function` | Char | Job position |
| `lang` | Many2one(res.lang) | Language |

### Contact Info

| Field | Type | Description |
|---|---|---|
| `email` | Char | Email |
| `email_formatted` | Char | Formatted email (Name <email>) |
| `phone` | Char | Phone |
| `mobile` | Char | Mobile |
| `fax` | Char | Fax |

### Address Fields

| Field | Type | Description |
|---|---|---|
| `street` | Char | Street |
| `street2` | Char | Street 2 |
| `city` | Char | City |
| `zip` | Char | ZIP |
| `state_id` | Many2one(res.country.state) | State |
| `country_id` | Many2one(res.country) | Country |

### Address Formatting

```python
# Format address via country
city = fields.Char(related='country_id.code', string='Country Code', readonly=True)
```

### Parent/Child Hierarchy

| Field | Type | Description |
|---|---|---|
| `parent_id` | Many2one(res.partner) | Parent company |
| `child_ids` | One2many(res.partner) | Contact children |
| `is_company` | Boolean | Is a company |

### Commercial Fields

| Field | Type | Description |
|---|---|---|
| `commercial_partner_id` | Many2one(res.partner) | Commercial entity (top parent) |
| `commercial_company_name` | Char | Commercial company name |
| `commercial_country_id` | Many2one(res.country) | Commercial country |

### Banking & Finance

| Field | Type | Description |
|---|---|---|
| `bank_ids` | One2many(res.partner.bank) | Bank accounts |
| `property_account_receivable_id` | Many2one | Receivable account |
| `property_account_payable_id` | Many2one | Payable account |
| `property_payment_term_id` | Many2one | Customer payment terms |
| `property_supplier_payment_term_id` | Many2one | Vendor payment terms |

### Company Fields

| Field | Type | Description |
|---|---|---|
| `user_ids` | Many2many(res.users) | Users (employees) |
| `image_128` | Binary | Small image |

### Statistics Fields (Read-only)

| Field | Type | Description |
|---|---|---|
| `sale_order_count` | Integer | Number of sales orders |
| `purchase_order_count` | Integer | Number of purchase orders |
| `invoice_count` | Integer | Number of invoices |
| `debts` | Float | Total outstanding |

### Partner Categories

```python
class PartnerCategory(models.Model):
    _name = "res.partner.category"
    _description = "Partner Tags"

    name = fields.Char('Category Name', required=True, translate=True)
    parent_id = fields.Many2one('res.partner.category', 'Parent Category', index=True)
    child_ids = fields.One2many('res.partner.category', 'parent_id', 'Child Categories')
```

### Partner Banks

```python
class ResPartnerBank(models.Model):
    _name = "res.partner.bank"
    _description = "Bank Accounts"

    acc_number = fields.Char('Account Number', required=True)
    sanitized_acc_number = fields.Char(compute='_compute_sanitized_acc_number')
    partner_id = fields.Many2one('res.partner', 'Account Holder', required=True)
    bank_id = fields.Many2one('res.bank', 'Bank')
    bank_name = fields.Char('Bank Name')
    company_id = fields.Many2one('res.company')
    currency_id = fields.Many2one('res.currency')
    acc_type = fields.Char('Account Type')
```

## Commercial Partner Pattern

```python
# Every contact has commercial_partner_id pointing to top-level commercial entity
commercial_partner_id = fields.Many2one(
    'res.partner',
    'Commercial Entity',
    compute='_compute_commercial_partner',
    store=True,
    index=True,
)

# Used for:
# - Commercial pricing (from commercial partner's pricelist)
# - Tax rules (commercial partner's fiscal position)
# - Access control (sales team, etc.)
```

## Address Type Pattern

```python
# Contact types for different addresses
type = fields.Selection([
    ('contact', 'Contact'),
    ('invoice', 'Invoice Address'),
    ('delivery', 'Shipping Address'),
    ('other', 'Other Address'),
    ('private', 'Private Address'),
], string='Address Type', default='contact')
```

## Contact Hierarchy

```
Company (is_company=True)
├── Contact 1 (type=contact)
├── Contact 2 (type=contact, child of company)
│   └── Private Address (type=private)
├── Invoice Address (type=invoice)
└── Delivery Address (type=delivery)
```

## Key Computed Methods

```python
# Display name: "[company] name" or just "name"
@api.depends('name', 'parent_id.display_name')
def _compute_display_name(self):
    for partner in self:
        partner.display_name = ...

# Commercial partner
@api.depends('parent_id.commercial_partner_id')
def _compute_commercial_partner(self):
    for partner in self:
        if partner.is_company or not partner.parent_id:
            partner.commercial_partner_id = partner
        else:
            partner.commercial_partner_id = partner.parent_id.commercial_partner_id

# Email formatted
@api.depends('name', 'email')
def _compute_email_formatted(self):
    for partner in self:
        if partner.name and partner.email:
            partner.email_formatted = '"%s" <%s>' % (partner.name, partner.email)
```

## See Also
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — Partner-based access rules
- [Modules/Sale](odoo-18/Modules/sale.md) — Customer in sale order
- [Modules/Purchase](odoo-18/Modules/purchase.md) — Vendor in purchase order
- [Modules/Account](odoo-18/Modules/account.md) — Partner in invoice