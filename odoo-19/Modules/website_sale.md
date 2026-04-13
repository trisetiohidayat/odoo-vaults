---
type: module
module: website_sale
tags: [odoo, odoo19, website, ecommerce, sale, cart, payment, checkout, shop]
created: 2026-04-11
---

# eCommerce Module (website_sale)

## Overview

| Property | Value |
|----------|-------|
| **Name** | eCommerce |
| **Technical Name** | `website_sale` |
| **Category** | Website/eCommerce |
| **Version** | 19.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

The website_sale module transforms Odoo into a full-featured e-commerce platform. It enables online product catalogs, shopping cart management, checkout flows, payment processing, order management, and multi-website support with different pricelists.

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `website` | Website framework |
| `sale` | Sales management |
| `website_payment` | Online payments |
| `website_mail` | Website email templates |
| `portal_rating` | Customer ratings |
| `digest` | KPI digest emails |
| `delivery` | Shipping methods |
| `html_builder` | HTML rendering |

---

## What website_sale Adds on Top of sale

The `website_sale` module extends the base `sale` module with:

1. **Website-specific cart** - Session-based shopping cart
2. **Public product catalog** - Browse products without login
3. **Pricelist per website** - Different pricing per website
4. **Multi-company e-commerce** - Sell from different companies
5. **Fiscal position auto-detection** - Based on delivery address
6. **Abandoned cart recovery** - Email reminders for incomplete orders
7. **Payment provider selection** - Choose payment method at checkout

---

## Key Models

| Model | Technical Name | Description |
|-------|----------------|-------------|
| Website | `website` | Website with e-commerce settings |
| Sale Order | `sale.order` | Extended with website fields |
| Sale Order Line | `sale.order.line` | Extended with cart fields |
| Product Template | `product.template` | Extended with website fields |
| Product Public Category | `product.public.category` | Website product categories |
| Product Pricelist | `product.pricelist` | Extended with website visibility |
| Website Sale Extra Field | `website.sale.extra.field` | Custom checkout fields |

---

## website (E-commerce Extension)

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/website.py`  
**Inherits:** `website`

### E-commerce Website Fields

```python
# Sales Team Configuration
salesperson_id = fields.Many2one(
    'res.users',
    string="Salesperson",
    domain=[('share', '=', False)],
)

salesteam_id = fields.Many2one(
    'crm.team',
    string="Sales Team",
    default=_default_salesteam_id,
)

# Cart Settings
add_to_cart_action = fields.Selection([
    ('stay', "Stay on Product Page"),
    ('go_to_cart', "Go to cart"),
], default='stay')

cart_abandoned_delay = fields.Float(
    string="Abandoned Delay",
    default=10.0  # hours
)

send_abandoned_cart_email = fields.Boolean(
    string="Send email to customers who abandoned their cart."
)

cart_recovery_mail_template_id = fields.Many2one(
    'mail.template',
    string="Cart Recovery Email",
    domain=[('model', '=', 'sale.order')],
)

# Checkout Configuration
account_on_checkout = fields.Selection([
    ('optional', "Optional"),
    ('disabled', "Disabled (buy as guest)"),
    ('mandatory', "Mandatory (no guest checkout)"),
], default='optional')

show_line_subtotals_tax_selection = fields.Selection([
    ('tax_excluded', "Tax Excluded"),
    ('tax_included', "Tax Included"),
])

# Shop Layout Settings
shop_page_container = fields.Selection([
    ('regular', "Regular"),
    ('fluid', "Full-width"),
], default='regular')

shop_ppg = fields.Integer(
    string="Number of products in the grid",
    default=21
)

shop_ppr = fields.Integer(
    string="Number of grid columns",
    default=3
)

shop_default_sort = fields.Selection(
    selection='_get_product_sort_mapping',
    required=True,
    default='website_sequence asc'
)
```

### Session Cache Keys

```python
CART_SESSION_CACHE_KEY = 'sale_order_id'
FISCAL_POSITION_SESSION_CACHE_KEY = 'fiscal_position_id'
PRICELIST_SESSION_CACHE_KEY = 'website_sale_current_pl'
PRICELIST_SELECTED_SESSION_CACHE_KEY = 'website_sale_selected_pl_id'
```

---

## sale.order (Website Extension)

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/sale_order.py`  
**Inherits:** `sale.order`

### Website-specific Fields

```python
# Website Reference
website_id = fields.Many2one(
    'website',
    string="Website",
    readonly=True,
    help="Website through which this order was placed"
)

# Cart State
cart_recovery_email_sent = fields.Boolean(
    string="Cart recovery email already sent"
)

shop_warning = fields.Char(
    string="Warning",
    help="Displays stock/warning messages to customer"
)

# Computed Cart Info
website_order_line = fields.One2many(
    'sale.order.line',
    string="Order Lines displayed on Website",
    compute='_compute_website_order_line',
)

amount_delivery = fields.Monetary(
    string="Delivery Amount",
    compute='_compute_amount_delivery',
)

cart_quantity = fields.Integer(
    string="Cart Quantity",
    compute='_compute_cart_info'
)

only_services = fields.Boolean(
    string="Only Services",
    compute='_compute_cart_info'
)

is_abandoned_cart = fields.Boolean(
    string="Abandoned Cart",
    compute='_compute_abandoned_cart',
    search='_search_abandoned_cart'
)
```

### Abandoned Cart Detection

```python
@api.depends('website_id', 'date_order', 'order_line', 'state', 'partner_id')
def _compute_abandoned_cart(self):
    for order in self:
        if order.website_id and order.state == 'draft' and order.date_order:
            public_partner_id = order.website_id.user_id.partner_id
            abandoned_delay = order.website_id.cart_abandoned_delay or 1.0
            abandoned_datetime = datetime.utcnow() - relativedelta(hours=abandoned_delay)
            
            order.is_abandoned_cart = bool(
                order.date_order <= abandoned_datetime
                and order.partner_id != public_partner_id
                and order.order_line
            )
        else:
            order.is_abandoned_cart = False
```

### Cart Methods

```python
def _cart_add(self, product_id, quantity=1.0, **kwargs):
    """Add product to cart, create order if needed"""
    
def _cart_find_product_line(
    self,
    product_id,
    uom_id,
    linked_line_id=False,
    no_variant_attribute_value_ids=None,
    **kwargs
):
    """Find existing cart line for product"""
    
def _cart_update_line_quantity(self, line_id, quantity, **kwargs):
    """Update quantity of cart line"""
    
def _verify_cart_after_update(self):
    """Global checks after cart updates"""
```

### Cart Workflow

```python
# 1. Get or create cart
order = self.website_sale_order()

# 2. Add product to cart
order._cart_add(product_id, qty)

# 3. Update address (triggers fiscal position detection)
order._update_address(partner_id, ['partner_shipping_id', 'partner_invoice_id'])

# 4. Select delivery method
order._set_delivery_method(carrier_id)

# 5. Verify before payment
order._check_cart_is_ready_to_be_paid()

# 6. Confirm order
order.action_confirm()
```

### Delivery Integration

```python
def _get_delivery_methods(self):
    """Get available delivery methods for order"""
    return self.env['delivery.carrier'].sudo().search([
        ('website_published', '=', True),
        *self.env['delivery.carrier']._check_company_domain(self.company_id),
    ]).filtered(lambda carrier: carrier._is_available_for_order(self))

def _set_delivery_method(self, delivery_method, rate=None):
    """Set delivery method and create delivery line"""
    self.ensure_one()
    self._remove_delivery_line()
    
    if not delivery_method or not self._has_deliverable_products():
        return
        
    rate = rate or delivery_method.rate_shipment(self)
    if rate.get('success'):
        self.set_delivery_line(delivery_method, rate['price'])

def _has_deliverable_products(self):
    """Check if order has physical products (not services)"""
    return bool(self.order_line.product_id) and not self.only_services
```

### Address Update & Fiscal Position

```python
def _update_address(self, partner_id, fnames=None):
    """Update address and auto-detect fiscal position"""
    fpos_before = self.fiscal_position_id
    
    self.write(dict.fromkeys(fnames, partner_id))
    
    # Auto-detect fiscal position based on new address
    fpos_changed = fpos_before != self.fiscal_position_id
    if fpos_changed:
        self._recompute_taxes()
        # Cache for session
        request.session[FISCAL_POSITION_SESSION_CACHE_KEY] = self.fiscal_position_id.id
```

### Cart Recovery

```python
def _cart_recovery_email_send(self):
    """Send abandoned cart recovery email"""
    sent_orders = self.env['sale.order']
    for order in self:
        template = order._get_cart_recovery_template()
        if template:
            order._portal_ensure_token()
            template.send_mail(order.id)
            sent_orders |= order
    sent_orders.write({'cart_recovery_email_sent': True})
```

---

## product.template (Website Extension)

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/product_template.py`  
**Inherits:** `rating.mixin`, `product.template`, `website.seo.metadata`, `website.published.multi.mixin`, `website.searchable.mixin`

### Website Fields

```python
# Website Visibility
website_id = fields.Many2one(
    'website',
    string='Website',
    index=True,
    help="Leave empty to show on all websites"
)

website_sequence = fields.Integer(
    string='Website Sequence',
    default=lambda self: self._default_website_sequence(),
)

website_published = fields.Boolean(
    'Available on the website',
    compute='_compute_website_published',
    inverse='_inverse_website_published',
    store=True
)

# Product Display
website_ribbon_id = fields.Many2one(
    'product.ribbon',
    string='Ribbon',
    help='Sale ribbon displayed on website'
)

base_unit_count = fields.Float(
    'Base Unit Count',
    default=1,
)

base_unit_id = fields.Many2one(
    'website_sale_extra_field.website_base_unit',
    string='Base Unit',
)

# Related Products
alternative_product_ids = fields.Many2many(
    'product.template',
    'product_alternative_rel',
    'src_id', 'dst_id',
    string='Alternative Products',
    help='Other products shown as alternatives'
)

accessory_product_ids = fields.Many2many(
    'product.product',
    'product_accessory_rel',
    'src_id', 'dest_id',
    string='Accessory Products',
    help='Products suggested in the cart'
)

alternative_product_count = fields.Integer(
    string='Alternative count',
    compute='_compute_alternative_product_count'
)

# Pricing Display
compare_list_price = fields.Float(
    'Compare to Price',
    help="Slash is displayed on the product page if you set this field"
)
```

### Product Visibility Computation

```python
@api.depends('sale_ok', 'website_id', 'company_id')
def _compute_website_published(self):
    for product in self:
        product.website_published = (
            product.sale_ok
            and (
                not product.website_id
                or product.website_id == request.website
            )
            and (
                not product.company_id
                or product.company_id == request.website.company_id
            )
        )
```

### Website Search

```python
@api.model
def _search_get_detail(self, website, order, options):
    """Enable website search integration"""
    return {
        'model': 'product.template',
        'base_domain': [('sale_ok', '=', True)],
        'search_fields': ['name', 'default_code', 'description_sale'],
        'fetch_fields': ['name', 'default_code', 'list_price'],
        'mapping': {
            'name': {'name': 'name', 'type': 'text'},
            'description': {'name': 'description_sale', 'type': 'text'},
            'price': {
                'name': 'list_price',
                'type': 'numeric',
                'format': lambda val, options: options.get('currency').format(val)
            },
        },
        'icon': '/website_sale/static/src/img/shop.png'
    }
```

---

## product.public.category

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/product_public_category.py`

### Fields

```python
name = fields.Char(
    'Category Name',
    required=True,
    translate=True
)

parent_id = fields.Many2one(
    'product.public.category',
    'Parent Category',
    index=True,
    ondelete='cascade'
)

sequence = fields.Integer(
    'Sequence',
    help="Lower number = higher priority",
    index=True
)

parent_path = fields.Char(
    index=True,
    unaccent=False
)

website_id = fields.Many2one(
    'website',
    'Website',
    index=True,
    help="Leave empty to show on all websites"
)

product_tmpl_ids = fields.Many2many(
    'product.template',
    'product_public_category_product_template_rel',
    'category_id', 'product_template_id',
    string='Products'
)

sequence = fields.Integer(default=10)
```

### Category Hierarchy

Uses `parent_path` for efficient hierarchy queries:

```
Electronics
└── Computers
    ├── Laptops
    └── Desktops
    └── Tablets
```

---

## website_sale_order_line (Extension)

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/sale_order_line.py`

### Additional Fields

```python
# Cart line identification
shop_warning = fields.Char(
    string="Warning",
    help="Displays stock warnings on cart line"
)

# Combination info stored for cart
product_no_variant_attribute_value_ids = fields.Many2many(
    'product.template.attribute.value',
    string='Extra Attributes Value'
)

product_custom_attribute_value_ids = fields.One2many(
    'product.custom.attribute.value',
    'sale_order_line_id',
    string='Custom Values'
)

is_original_line = fields.Boolean(
    help="True if this is the original cart line before optional products"
)
```

---

## Checkout Flow

### Step 1: Cart Review
```
/shop/cart
```
- View cart contents
- Update quantities
- Remove items
- See delivery estimates

### Step 2: Address
```
/shop/address
```
- Select or create delivery address
- Auto-detects fiscal position based on country
- Triggers tax recalculation

### Step 3: Delivery Method
```
/shop/pay
```
- Select shipping carrier
- Shows delivery cost
- Updates order total

### Step 4: Payment
```
/payment
```
- Select payment provider
- Process transaction
- Confirm order

### Step 5: Confirmation
```
/shop/confirmation
```
- Order summary
- Payment status
- Tracking information

---

## Pricelist System

### How Pricelists Work

```python
# Website selects pricelist based on:
# 1. Partner-specific pricelist (from partner)
# 2. GeoIP-based pricelist (from country)
# 3. Default website pricelist

pricelist_id = fields.Many2one(
    'product.pricelist',
    string='Pricelist',
    compute='_compute_pricelist_id',
    inverse='_inverse_pricelist_id'
)
```

### Session-based Pricelist

```python
# Store selected pricelist in session
request.session[PRICELIST_SESSION_CACHE_KEY] = pricelist.id

# User-explicit selection is remembered
request.session[PRICELIST_SELECTED_SESSION_CACHE_KEY] = selected_pl_id
```

---

## Payment Integration

### Payment Provider Selection

```python
# On checkout, available providers are filtered by:
# 1. Website visibility
# 2. Company match
# 3. Country restrictions
# 4. Currency support

def _get_payment_provider(self):
    """Get available payment providers"""
    return self.env['payment.provider'].sudo().search([
        ('state', 'in', ['enabled', 'test']),
        ('website_id', 'in', [False, self.website_id.id]),
    ]).filtered(
        lambda p: (
            not p.company_id or p.company_id == self.company_id
        ) and (
            not p.country_ids or self.partner_id.country_id in p.country_ids
        )
    )
```

---

## Wishlist (product.wishlist)

**File:** `~/odoo/odoo19/odoo/addons/website_sale/models/product_wishlist.py`

### Fields

```python
product_id = fields.Many2one('product.product', required=True)
partner_id = fields.Many2one('res.partner', required=True)
pricelist_id = fields.Many2one('product.pricelist', required=True)
website_id = fields.Many2one('website', required=True)
currency_id = fields.Many2one('res.currency', required=True)
price = fields.Monetary('Price')
```

### Wishlist Methods

```python
def add_to_wishlist(self, product_id, partner_id=None):
    """Add product to wishlist"""
    
def _check_wishlist_validity(self):
    """Check if wishlist item is still valid"""
    
def _is_product_still_available(self):
    """Check if product is still for sale"""
```

---

## Compare Products

### Implementation

Products can be compared using `product.compare_list_price`:

```python
compare_list_price = fields.Float(
    'Compare to Price',
    help="Slash is displayed if this is higher than list_price"
)
```

### Compare Route

```
/shop/compare
```

Shows side-by-side comparison of selected products.

---

## SEO and Meta Tags

### Product SEO

```python
# product.template inherits website.seo.metadata
website_meta_title = fields.Char()
website_meta_description = fields.Text()
website_meta_keywords = fields.Text()
website_meta_og_img = fields.Image()
```

### Dynamic Meta from Product

```python
def _compute_website_meta(self):
    """Set meta tags from product fields"""
    self.website_meta_title = self.seo_name or self.name
    self.website_meta_description = self.description_sale
    self.website_meta_keywords = self.default_code
```

---

## Model Relationships

```
website
    |
    +--< sale.order (website_id)
    |       |
    |       +--< sale.order.line
    |               |
    |               +-- product.product (product_id)
    |               |
    |               +-- product.template.attribute.value (no_variant)
    |
    +--< product.template (website_id)
    |       |
    |       +--< product.public.category
    |
    +--< product.pricelist (website_ids)

sale.order
    |
    +-- website_id -> website
    +-- fiscal_position_id (auto-detected)
    +-- pricelist_id (website-selected)
    +-- carrier_id (delivery)
    +-- partner_id -> res.partner
```

---

## Related Documentation

- [Modules/website](modules/website.md) - Website framework
- [Modules/sale](modules/sale.md) - Sales management
- [Modules/product](modules/product.md) - Product management
- [Modules/delivery](modules/delivery.md) - Shipping methods
- [Modules/payment](modules/payment.md) - Payment providers
