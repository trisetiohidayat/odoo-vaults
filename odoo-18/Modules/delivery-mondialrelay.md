---
Module: delivery_mondialrelay
Version: Odoo 18
Type: Integration
Tags: [odoo, odoo18, delivery, mondial-relay, shipping, point-relais, stock]
RelatedModules: [stock_delivery, delivery]
---

# delivery_mondialrelay — Mondial Relay Point-Relais Delivery

> Integrates Odoo with Mondial Relay, a European parcel delivery network featuring 15,000+ Point Relais pickup/delivery points. Allows customers to select a nearby parcel shop as their delivery address during checkout.

**Depends:** `stock_delivery`
**Category:** Inventory/Delivery
**Version:** 0.1

---

## Overview

Mondial Relay is a carrier aggregator — it is not a fully-featured carrier in the Odoo sense (no rate shopping, no label generation). Instead, `delivery_mondialrelay` provides:

1. A **Point Relais selection widget** in the delivery carrier wizard
2. A **delivery address override** — when a Point Relais is selected, the SO's delivery address is replaced with the relay point's partner record
3. A **tracking link** generator pointing to Mondial Relay's public tracking page
4. A **validation gate** in `sale.order` confirmation — carrier and shipping address must both be Mondial Relay compatible

The module does **not** implement the Mondial Relay WebService API. The Point Relais selection is powered by a frontend widget that queries Mondial Relay's public endpoint directly from the browser. Odoo stores the selected relay point as a child partner of the customer.

---

## Key Concepts

### Point Relais Flow

```
Customer selects "Mondial Relay" as delivery method
         │
         ▼
choose.delivery.carrier wizard opens
  (widget: mondialrelay_relay)
         │
         ▼
Frontend JS widget loads Mondial Relay's public API
  Customer searches by zip/country, selects a Point Relais
         │
         ▼
Widget stores selected relay as JSON in:
  choose.delivery.carrier.mondialrelay_last_selected
         │
         ▼
button_confirm() called
  ├── Validates relay was selected (raises if not)
  ├── Calls partner_id._mondialrelay_search_or_create(data)
  │     Creates/resuses res.partner with ref='MR#[relay_id]'
  └── Updates sale.order.partner_shipping_id → relay partner
         │
         ▼
Sale order confirmed → stock.picking created
  Carrier tracking ref set by carrier (or manually)
  Partner shipping address = relay point partner
         │
         ▼
Tracking link in picking → Mondial Relay public tracking URL
```

---

## Models

### `delivery.carrier` — Extended

```python
class DeliveryCarrierMondialRelay(models.Model):
    _inherit = 'delivery.carrier'
```

#### Fields Added

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `is_mondialrelay` | Boolean (computed, searchable) | — | True if `product_id.default_code == 'MR'` |
| `mondialrelay_brand` | Char (default=`'BDTEST  '`) | — | Brand/tracker code assigned by Mondial Relay (visible in tracking URL) |
| `mondialrelay_packagetype` | Char (default=`"24R"`) | `base.group_system` | Package type code (24R = standard parcel) |

#### `is_mondialrelay` Compute

```python
@api.depends('product_id.default_code')
def _compute_is_mondialrelay(self):
    for c in self:
        c.is_mondialrelay = c.product_id.default_code == "MR"
```

The carrier is identified as a Mondial Relay carrier by its **product reference code** (`MR`), not by a separate flag. This is the primary discriminator used throughout the module.

#### `is_mondialrelay` Search

```python
def _search_is_mondialrelay(self, operator, value):
    if operator not in ('=', '!=') or not isinstance(value, bool):
        raise UserError(_("Operation not supported"))
    if not value:
        operator = '!=' if operator == '=' else '='
    return [('product_id.default_code', operator, 'MR')]
```

Allows domain queries like `[('is_mondialrelay', '=', True)]` in search views.

#### Tracking Link Methods

**`fixed_get_tracking_link(picking)`**
```python
def fixed_get_tracking_link(self, picking):
    if self.is_mondialrelay:
        return self.base_on_rule_get_tracking_link(picking)
    return super().fixed_get_tracking_link(picking)
```

Mondial Relay delegates tracking to `base_on_rule_get_tracking_link` (the standard rate-rule tracker), not the flat-rate tracker.

**`base_on_rule_get_tracking_link(picking)`**
```python
def base_on_rule_get_tracking_link(self, picking):
    if self.is_mondialrelay:
        return 'https://www.mondialrelay.com/public/permanent/tracking.aspx'
           '?ens=%(brand)s&exp=%(track)s&language=%(lang)s' % {
                'brand': picking.carrier_id.mondialrelay_brand,
                'track': picking.carrier_tracking_ref,
                'lang': (picking.partner_id.lang or 'fr').split('_')[0],
            }
    return super().base_on_rule_get_tracking_link(picking)
```

Generates a direct link to the public tracking page. The language is extracted from the partner's lang (e.g., `fr_FR` → `fr`).

---

### `res.partner` — Extended

```python
class ResPartnerMondialRelay(models.Model):
    _inherit = 'res.partner'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `is_mondialrelay` | Boolean (computed) | True if `ref` starts with `'MR#'` |

#### `is_mondialrelay` Compute

```python
@api.depends('ref')
def _compute_is_mondialrelay(self):
    for p in self:
        p.is_mondialrelay = p.ref and p.ref.startswith('MR#')
```

Point Relais partners are identified by their reference starting with `MR#`.

#### `_mondialrelay_search_or_create(data)`

Core method for creating/retrieving Point Relais delivery addresses:

```python
@api.model
def _mondialrelay_search_or_create(self, data):
    ref = 'MR#%s' % data['id']           # e.g., "MR#FR12345"
    partner = self.search([
        ('id', 'child_of', self.commercial_partner_id.ids),
        ('ref', '=', ref),
        ('street', '=', data['street']),  # fast consistency check
        ('zip', '=', data['zip']),
    ])
    if not partner:
        partner = self.create({
            'ref': ref,
            'name': data['name'],           # "Mondial Relay - RELAIS COLIS..."
            'street': data['street'],
            'street2': data['street2'],
            'zip': data['zip'],
            'city': data['city'],
            'country_id': self.env.ref('base.%s' % data['country_code']).id,
            'type': 'delivery',              # delivery address type
            'parent_id': self.id,            # child of commercial partner
        })
    return partner
```

**Key design decisions:**
- `parent_id = self` — relay points are **child contacts** of the customer's commercial partner, not standalone records
- `type = 'delivery'` — marked as delivery address, prevents it from being used for invoicing
- `id` from the frontend JSON is encoded in the `ref` field — used as the search key
- Street and zip are included in the search to handle relay point changes (if a relay with the same ID but different address exists, it creates a new record)
- `country_id` is looked up by ISO code: `base.fr`, `base.be`, etc.

#### `_avatar_get_placeholder_path()`

```python
def _avatar_get_placeholder_path(self):
    if self.is_mondialrelay:
        return "delivery_mondialrelay/static/src/img/truck_mr.png"
    return super()._avatar_get_placeholder_path()
```

Displays a truck icon for Point Relais delivery addresses instead of the default partner avatar.

---

### `sale.order` — Extended

```python
class SaleOrderMondialRelay(models.Model):
    _inherit = 'sale.order'
```

#### Validation Gate: `action_confirm()`

```python
def action_confirm(self):
    unmatch = self.filtered(
        lambda so: so.carrier_id.is_mondialrelay != so.partner_shipping_id.is_mondialrelay
    )
    if unmatch:
        error = _('Mondial Relay mismatching between delivery method and shipping address.')
        if len(self) > 1:
            error += ' (%s)' % ','.join(unmatch.mapped('name'))
        raise UserError(error)
    return super().action_confirm()
```

**Rule:** The delivery carrier and the shipping address must both be (or both not be) Mondial Relay. A mismatch is blocked:

| Carrier | Shipping Address | Result |
|---------|-----------------|--------|
| Mondial Relay (`is_mondialrelay=True`) | Point Relais (`is_mondialrelay=True`) | OK |
| Standard carrier (`is_mondialrelay=False`) | Standard address | OK |
| Mondial Relay | Standard address | **BLOCKED** — UserError |
| Standard carrier | Point Relais address | **BLOCKED** — UserError |

This prevents shipping via a standard carrier to a relay point or shipping via Mondial Relay to a home address.

---

### `choose.delivery.carrier` — Extended (Wizard)

Located in `wizard/choose_delivery_carrier.py`. This is the delivery method selection step in the e-commerce or backend SO flow.

```python
class ChooseDeliveryCarrier(models.TransientModel):
    _inherit = 'choose.delivery.carrier'
```

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `shipping_zip` | Char (related) | Zip from `order_id.partner_shipping_id.zip` |
| `shipping_country_code` | Char (related) | Country code from `order_id.partner_shipping_id.country_id.code` |
| `is_mondialrelay` | Boolean (computed) | `carrier_id.product_id.default_code == "MR"` |
| `mondialrelay_last_selected` | Char | JSON string of selected Point Relais (widget stores here) |
| `mondialrelay_last_selected_id` | Char (computed) | `{country_code}-{relay_id}` formatted from shipping partner's ref |
| `mondialrelay_brand` | Char (related) | From `carrier_id.mondialrelay_brand` |
| `mondialrelay_colLivMod` | Char (related) | From `carrier_id.mondialrelay_packagetype` (Colis/Livraison Mode) |
| `mondialrelay_allowed_countries` | Char (computed) | Comma-separated country codes the carrier serves |

#### `mondialrelay_last_selected_id` Compute

```python
@api.depends('carrier_id', 'order_id.partner_shipping_id')
def _compute_mr_last_selected_id(self):
    self.ensure_one()
    if self.order_id.partner_shipping_id.is_mondialrelay:
        self.mondialrelay_last_selected_id = '%s-%s' % (
            self.shipping_country_code,
            self.order_id.partner_shipping_id.ref.lstrip('MR#'),
        )
    else:
        self.mondialrelay_last_selected_id = ''
```

Pre-selects the previously chosen relay in the widget if the shipping address is already a relay point.

#### `mondialrelay_allowed_countries` Compute

```python
@api.depends('carrier_id')
def _compute_mr_allowed_countries(self):
    self.ensure_one()
    self.mondialrelay_allowed_countries = ','.join(
        self.carrier_id.country_ids.mapped('code')
    ).upper() or ''
```

Passes carrier country restrictions to the frontend widget (so it pre-filters available relay points).

#### `button_confirm()` — Override

```python
def button_confirm(self):
    if self.carrier_id.is_mondialrelay:
        if not self.mondialrelay_last_selected:
            raise ValidationError(_('Please, choose a Parcel Point'))
        data = json_safe.loads(self.mondialrelay_last_selected)
        partner_shipping = self.order_id.partner_id._mondialrelay_search_or_create({
            'id': data['id'],
            'name': data['name'],
            'street': data['street'],
            'street2': data['street2'],
            'zip': data['zip'],
            'city': data['city'],
            'country_code': data['country'][:2].lower(),
        })
        if partner_shipping != self.order_id.partner_shipping_id:
            self.order_id.partner_shipping_id = partner_shipping

    return super().button_confirm()
```

Mandatory relay selection is enforced before proceeding.

---

## Frontend Widget

The Point Relais selection is powered by a JavaScript widget (`mondialrelay_relay`) loaded via web assets:

```
'web.assets_backend': [
    'delivery_mondialrelay/static/src/components/**/*.js',
    'delivery_mondialrelay/static/src/scss/mondialrelay.scss',
]
```

Widget responsibilities:
1. Load Mondial Relay's public Point Relais search API (external JS)
2. Render the selection interface in the wizard
3. Store the selected relay as a JSON string in `mondialrelay_last_selected`
4. Use `mondialrelay_brand`, `mondialrelay_colLivMod`, `mondialrelay_allowed_countries`, `shipping_zip`, `shipping_country_code` from the wizard fields to configure the API query
5. Show previously selected relay (`mondialrelay_last_selected_id`) on re-render

---

## Stock Picking Extension

`stock.picking` is **not** directly extended by `delivery_mondialrelay`. However:

- When a SO is confirmed with a Mondial Relay carrier, the resulting `stock.picking` inherits the `partner_shipping_id` which is now the Point Relais child partner
- The carrier's `base_on_rule_get_tracking_link()` is called by `stock.picking`'s standard tracking link method
- The tracking URL uses `picking.carrier_tracking_ref` (set manually or by the label API)

The picking's delivery address will correctly show the relay point's address because `partner_shipping_id` was set to the relay partner during `button_confirm()`.

---

## Master Data (noupdate=1)

The module ships pre-configured data:

### Product

| Field | Value |
|-------|-------|
| `name` | `Mondial Relay` |
| `default_code` | `MR` |
| `type` | `service` |
| `sale_ok` | `False` |
| `purchase_ok` | `False` |
| `list_price` | `5.0` |
| `invoice_policy` | `order` |

The product is **not** sold directly — it is used as the delivery product on the carrier.

### Pre-configured Carriers

Three `delivery.carrier` records are created (BE/LU, FR/NL, ES), each:
- `delivery_type = 'base_on_rule'` (uses price rules, not an external API)
- `integration_level = 'rate'` (shows rate but no automatic label)
- Linked to the `MR` product
- Country-restricted to their respective regions

Pricing rules use `base_on_rule` with `max_value` (weight-based tiers).

---

## L4: Architecture Notes

**No WebService implementation:** This module does not call the Mondial Relay API for rates or labels. It relies on:
- `base_on_rule` delivery type for pricing (configured via `delivery.price.rule`)
- Manual or external tracking number entry
- Public-facing widget JS loaded from Mondial Relay's CDN or bundled assets

**Child partner pattern:** The relay point is stored as a `delivery`-type child partner of the customer. This is important because:
- The customer's commercial partner (`commercial_partner_id`) is preserved
- Invoices always go to the parent
- Delivery addresses can be managed alongside regular addresses in `res.partner`
- The `is_mondialrelay` computed field uses `ref.startswith('MR#')` which naturally only matches child records

**MR# reference encoding:** The `ref = 'MR#' + relay_id` pattern ensures:
- Unique identification per relay per customer
- Searchable via standard partner search
- The country code prefix in `mondialrelay_last_selected_id` (`FR-12345`) is derived from stripping `MR#` from the ref and prepending the country

**Mismatch prevention:** The `sale.order.action_confirm()` override acts as a consistency guard. Without it, a user could:
- Select Mondial Relay carrier
- Forget to pick a relay point (or pick one then change the address manually)
- Confirm the order with a home address but a relay carrier → shipment would fail

**Image assets:** The module ships a placeholder truck icon (`truck_mr.png`) shown in the partner avatar for relay points, distinguishing them visually from regular delivery addresses.
