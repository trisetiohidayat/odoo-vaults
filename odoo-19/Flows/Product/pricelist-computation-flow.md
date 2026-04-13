---
type: flow
title: "Pricelist Computation Flow"
primary_model: product.pricelist
trigger: "System — SO line product_id + pricelist_id set"
cross_module: true
models_touched:
  - product.pricelist
  - product.pricelist.item
  - product.product
  - product.template
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Product/product-creation-flow](Flows/Product/product-creation-flow.md)"
  - "[Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md)"
source_module: product
created: 2026-04-07
version: "1.0"
---

# Pricelist Computation Flow

## Overview

This flow describes how Odoo 19 computes the unit price for a product on a sale order line, from the moment a user selects a product in a `sale.order.line` record through the final `price_unit` assignment. The primary entry point is the `sale.order.line._onchange_product_id()` onchange, which delegates to `product.pricelist._get_product_price()`, which then calls the pricelist's `_compute_price_rule()`. This method walks the sorted pricelist rules, applies the first matching rule, computes the price using fixed/percentage/formula logic, applies any available discount, and rounds to the UoM precision. The flow covers variant pricing (via `product.template.attribute.line.price_extra`), BOM-based costing for kit products, and the multi-step rule application cascade.

## Trigger Point

**System event:** When `product_id` is set (or changed) on a `sale.order.line`, the onchange `_onchange_product_id()` fires. This method needs `pricelist_id` to be already set (or resolved via partner's default pricelist). If `pricelist_id` is not yet known, the system falls back to the partner's assigned pricelist or the company's default sale pricelist.

**Primary user action:** User selects a product in the Sale Order line form. The `product_id` field change triggers the cascade.

**Alternative triggers:**
- `sale.order.line.write({'product_id': ...})` — API/import update
- `pricelist_id` changed on `sale.order` header (recomputes all lines)
- Product quantity changed (quantity-based rules require re-evaluation)
- `sale.order._onchange_partner_id()` updates pricelist, which then re-evaluates line prices
- `sale.order.line._onchange_uom()` triggers UoM-specific rounding

---

## Complete Method Chain

```
1. sale.order.line._onchange_product_id()
   │
   ├─► 2. IF pricelist_id not set:
   │      └─► 3. partner_id.property_product_pricelist fetched
   │            └─► 4. IF still none:
   │                   └─► 5. company.default_sale_pricelist fallback
   │
   ├─► 6. product.pricelist._get_product_price(product_id, quantity, uom_id)
   │     └─► 7. _get_product_price_rule(product_id, quantity, uom_id)
   │           └─► 8. _compute_price_rule(product_id, quantity, uom_id, partner_id=False)
   │                 ├─► 9. _get_applicable_rules(product_id, quantity, uom_id, partner)
   │                 │     ├─► 10. Search product_pricelist_item with:
   │                 │     │      applied_on IN ['0_product_variant','1_product','2_category','3_global']
   │                 │     │      min_quantity <= quantity
   │                 │     │      date_start <= now <= date_end (if set)
   │                 │     │      Order by: min_sequence ASC, id DESC
   │                 │     └─► 11. Return sorted item list
   │                 │
   │                 ├─► 12. IF item found:
   │                 │      └─► 13. item._compute_price(product_id, qty, uom, price_rule)
   │                 │            ├─► 14. IF compute_price == 'fixed':
   │                 │            │      └─► 15. price = fixed_price (from item)
   │                 │            │
   │                 │            ├─► 16. IF compute_price == 'percentage':
   │                 │            │      ├─► 17. base_price = _compute_base_price()
   │                 │            │      │     └─► 18. base = 'list_price' → product.list_price
   │                 │            │      │           base = 'standard_price' → product.standard_price
   │                 │            │      │           base = 'pricelist' → recursive get_product_price()
   │                 │            │      └─► 19. price = base_price * (1 - percent_price / 100)
   │                 │            │
   │                 │            └─► 20. IF compute_price == 'formula':
   │                 │                   ├─► 21. base_price = _compute_base_price() (see step 17)
   │                 │                   ├─► 22. price_discount applied: price -= base_price * (price_discount/100)
   │                 │                   ├─► 23. price_markup applied: price += base_price * (price_markup/100)
   │                 │                   ├─► 24. price_round applied: price = round(price / price_round) * price_round
   │                 │                   ├─► 25. price_surcharge added: price += price_surcharge
   │                 │                   ├─► 26. price_min_margin enforced: price = max(price, base_price + price_min_margin)
   │                 │                   ├─► 27. price_max_margin enforced: price = min(price, base_price + price_max_margin)
   │                 │                   └─► 28. ps (price surcharge) + pw (percent discount) variables available
   │                 │
   │                 └─► 29. _apply_both() if discount field present
   │                       └─► 30. _apply_multiple() for multi-step discounts
   │
   ├─► 31. sale.order.line._onchange_uom()
   │     └─► 32. uom.uom._compute_quantity() rounding applied
   │           └─► 33. price_unit rounded to uom.uom.rounding precision
   │
   ├─► 34. mrp.bom._compute_scrap() (IF product is kit/bom)
   │     └─► 35. BOM component costs summed → effective product cost used as base_price
   │
   ├─► 36. product.template.attribute.line.price_extra added
   │     └─► 37. price_extra = SUM(attribute_value_id.price_extra) per matching attribute line
   │           └─► 38. lst_price = list_price + price_extra (variant-specific)
   │
   ├─► 39. sale.order.line.write({'price_unit': computed_price})
   │     └─► 40. sale.order.line.write({'discount': discount_pct}) (if applicable)
   │
   └─► 41. sale.order._compute_amount() recalculates line subtotal
         └─► 42. taxes_id applied → tax amount computed → total updated
```

---

## Decision Tree

```
User/System sets product_id on sale.order.line
│
├─► pricelist_id already set on line?
│  ├─► YES → Use that pricelist
│  └─► NO → Resolve via partner.sale_type or fallback to company default
│
├─► get_product_price(product_id, qty, uom) called
│  │
│  ├─► Rules found for this product?
│  │  ├─► YES → Sort by min_sequence (asc), pick lowest sequence rule
│  │  │      ├─► Rule applied_on = '0_product_variant':
│  │  │      │      └─► Price computed from rule + variant price_extra
│  │  │      ├─► Rule applied_on = '1_product':
│  │  │      │      └─► Price computed from rule + template price
│  │  │      ├─► Rule applied_on = '2_category':
│  │  │      │      └─► Price computed from rule + product list_price
│  │  │      └─► Rule applied_on = '3_global':
│  │  │             └─► Price computed from rule + list_price
│  │  │
│  │  └─► NO → Use product's list_price as fallback
│  │
│  └─► Variant price_extra present?
│       ├─► YES → Add price_extra from matching attribute values
│       └─► NO → Use template list_price
│
├─► compute_price type on matched rule?
│  ├─► 'fixed' → Use fixed_price from item
│  ├─► 'percentage' → base_price * (1 - percent_price/100)
│  └─► 'formula' → Evaluate with pct_margin, pnt, pw, ps, prestrice variables
│
├─► uom_id different from product.uom_id?
│  ├─► YES → Convert price using UoM factor
│  └─► NO → No conversion
│
├─► discount field on sale order line?
│  ├─► YES → _apply_both() tries to split into fixed + percentage
│  └─► NO → price_unit = computed_price
│
└─► ALWAYS:
   └─► price_unit written to sale.order.line
        └─► tax lines recomputed via _compute_tax_id()
             └─► sale.order.amount_total updated
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `product_pricelist` | Read (no change) | `id`, `name`, `currency_id`, `company_id`, `item_ids` |
| `product_pricelist_item` | Read (no change) | `id`, `pricelist_id`, `applied_on`, `compute_price`, `fixed_price`, `percent_price`, `price_discount`, `price_markup`, `price_round`, `price_surcharge`, `min_quantity`, `min_sequence`, `base` |
| `product_product` | Read (no change) | `id`, `list_price`, `standard_price`, `price_extra`, `product_tmpl_id` |
| `product_template` | Read (no change) | `id`, `list_price`, `standard_price`, `uom_id` |
| `product_template_attribute_line` | Read (no change) | `id`, `product_tmpl_id`, `attribute_id`, `value_ids`, `price_extra` |
| `product_template_attribute_value` | Read (no change) | `id`, `price_extra`, `product_attribute_value_id` |
| `sale_order_line` | Updated | `price_unit`, `discount`, `product_uom_qty` |
| `uom_uom` | Read (no change) | `id`, `factor`, `rounding`, `category_id` |
| `mrp_bom` | Read (no change) | BOM lines read if product is kit (for cost computation) |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No matching pricelist item for product | No error — fallback to `list_price` | Behavior: price_unit = product.list_price |
| Circular pricelist reference | `ValidationError` ("Error! You cannot create recursive pricelists.") | `_check_pricelist_recursion()` on `product.pricelist.item` |
| Pricelist currency mismatch with sale order | `UserError` ("Currency mismatch") | `sale.order` validates currency against pricelist currency on `_onchange_pricelist_id()` |
| Pricelist rule date range invalid (end < start) | `ValidationError` ("End date must be greater than start date") | `_check_date_range()` on `product.pricelist.item` |
| Minimum margin > maximum margin | `ValidationError` ("Min margin must be <= Max margin") | `_check_margin()` on `product.pricelist.item` |
| `base = 'pricelist'` with no base_pricelist_id | `ValidationError` ("Base pricelist required") | `_check_base_pricelist_id()` on `product.pricelist.item` |
| Quantity-based rule with negative min_quantity | `ValidationError` | Constraint on `min_quantity >= 0` in field definition |
| UoM not same category as product UoM | `UserError` ("Conversion not possible") | `_onchange_uom()` checks UoM category consistency |
| Applied_on = '1_product' with no product_tmpl_id | `ValidationError` | `_check_product_consistency()` on `product.pricelist.item` |
| Archived pricelist used in SO | `UserError` ("Pricelist is not active") | Checked when pricelist_id is written to SO |
| Product without list_price (price = 0) | No error — price_unit = 0 | Valid in Odoo (free product scenario) |
| Pricelist rule with future date_start only | No error — rule skipped until date reached | Date range check in `_get_applicable_rules()` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Price unit written to SO line | `sale.order.line` | `price_unit` updated; `discount` set if applicable |
| SO amount recomputed | `sale.order` | `_compute_amount()` recalculates tax and total |
| Tax lines recomputed | `account.tax` | Tax computation triggered by price_unit change |
| Product variant price_extra added | `product.product` | Variant's extra price from attribute values added to base price |
| BOM cost included in price base | `mrp.bom` | For kit products, BOM component costs used as base_price |
| Discount stored on line | `sale.order.line` | `discount` field set via `_apply_both()` if available |
| UoM rounding applied | `uom.uom` | Price rounded to UoM's precision (`rounding` field) |
| Fiscal position applied to taxes | `account.fiscal.position` | Taxes remapped on SO line if fiscal position set |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `_onchange_product_id()` | Current user | Read on `product.product`, `sale.order` | No write during onchange |
| `get_product_price()` | Current user | Read on `product.pricelist`, `product.pricelist.item` | Respects record rules on items |
| `_get_applicable_rules()` | Current user | Read on `product.pricelist.item` | Filtered by company_id + active |
| `_compute_price()` | Current user | Read on `product.pricelist.item` | Price computation is read-only |
| `_compute_base_price()` | Current user | Read on `product.product`, `product.template` | Only visible list_price/standard_price used |
| `write({'price_unit': ...})` | Current user | Write on `sale.order.line` | Requires `sale.group_sale_salesman` |
| `write({'discount': ...})` | Current user | Write on `sale.order.line` | Discount field ACL |
| `sale.order._compute_amount()` | Current user | Read on `sale.order.line`, `account.tax` | No write |
| `price_extra` from variant attributes | Current user | Read on `product.template.attribute.value` | Only active attribute values |

**Key principle:** All price computation runs as the **current logged-in user**. Users without read access to a pricelist will not have its rules applied — the system will fall back to the next visible pricelist or the product's `list_price`.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-11    ✅ INSIDE transaction  — onchange + rule search (read-only)
Steps 12-30   ✅ INSIDE transaction  — price computation (read-only)
Step 31-33   ✅ INSIDE transaction  — UoM rounding (read-only)
Steps 34-38  ✅ INSIDE transaction  — BOM/variant price extras (read-only)
Steps 39-40  ✅ INSIDE transaction  — write price_unit + discount to SO line
Steps 41-42  ✅ INSIDE transaction  — tax and amount recompute (same SO record)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `_onchange_product_id()` | Atomic (within onchange) | Rolled back with form; no persisted change |
| `_compute_price_rule()` | Atomic (read-only) | Rolled back with form |
| `write({'price_unit': ...})` | Atomic | Committed if form saved; rolled back if save fails |
| Tax recompute | Atomic (within SO write) | Rolled back with SO save |
| Pricelist rule deletion (external) | N/A | Does not affect in-flight computation |

**Rule of thumb:** All onchange-triggered price computation is **read-only** — it only reads from `product.pricelist`, `product.pricelist.item`, and `product.product` tables. The only writes are `sale.order.line.price_unit` and `discount` fields, which are part of the same onchange-triggered write batch. There are no external calls, queue jobs, or mail notifications triggered by the price computation itself.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| User changes product, then immediately changes back | Last `_onchange_product_id()` result wins; no cumulative effect |
| Two users open same SO line simultaneously and both change product | Last write wins; race condition possible but not dangerous (price_unit overwritten) |
| SO saved, then user opens and re-selects same product | `_onchange_product_id()` re-fires; same price result — idempotent at record level |
| Pricelist rule added after SO created | Changing `pricelist_id` on SO header triggers `_compute_price_rule()` on all lines — price may change |
| Quantity updated on line with quantity-based rule | `_onchange_product_id()` fires again (or dedicated `_onchange_product_uom_qty()`), rule re-evaluated — correct behavior |
| Pricelist item date range expires mid-SO lifecycle | Price does NOT automatically update on existing lines; only new line creation or manual re-trigger gets new price |
| `sale.order.line.copy()` duplicates line | New line runs `_onchange_product_id()` from scratch with same vals — price recomputed |

**Non-idempotent operations in this flow:**
- **Discount field**: If a manual discount was set by the user, `_onchange_product_id()` will overwrite it (unless protected by `discount_text` or similar field)
- **Pricelist deletion**: If a pricelist is deleted while an SO references it, price_unit becomes 0 or falls back to list_price — dangerous
- **Currency change on pricelist mid-SO**: All lines maintain old currency until manually updated — can cause currency mismatch

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Price fetch entry | `get_product_price()` | Custom price fetching | self, product_id, qty, uom_id | Extend in `product.pricelist` |
| Rule selection | `_get_applicable_rules()` | Custom rule filtering | self, product_id, qty, uom_id | Replace domain filter |
| Base price computation | `_compute_base_price()` | Custom base price for formula | self, product_id, rule | Override for special base logic |
| Price calculation | `_compute_price()` | Custom price calculation (item level) | self, product_id, qty, uom | `super()._compute_price()` then adjust |
| Formula evaluation | `_price_compute()` on template | Custom price compute method | self, price_type | Extend template `_price_compute()` |
| Variant extra price | `_get_no_variant_attributes_price_extra()` | Extra price from non-variant attrs | self | Extend for custom attribute pricing |
| SO line price assignment | `_onchange_product_id()` | Custom price assignment logic | self | Extend sale.order.line onchange |
| Discount splitting | `_apply_both()` | Split discount into fixed + % | self | Override for custom discount logic |

**Standard override pattern:**
```python
# CORRECT — extend pricelist price computation
class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    def _compute_price_rule(self, products, quantity, uom_id, date=False, partner=False):
        # Custom rule filtering before standard logic
        result = super()._compute_price_rule(products, quantity, uom_id, date, partner)
        # Post-process result for custom pricing
        for product_id, (price, rule_id) in result.items():
            if self.env.context.get('is_premium_customer'):
                result[product_id] = (price * 0.9, rule_id)
        return result

# CORRECT — extend SO line onchange
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _onchange_product_id(self):
        result = super()._onchange_product_id()
        # Custom logic after price unit set
        self._compute_margin()
        return result
```

**Deprecated override points to avoid:**
- Overriding `_price_get()` directly (use `_get_product_price()` instead)
- `@api.one` on any pricelist method (removed in Odoo 19)
- Hardcoding rule logic in `_get_applicable_rules()` without `super()` call (breaks upgrades)

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Price unit set by onchange | Manual override | User overwrites `price_unit` manually | Onchange re-fires on any product/pricelist change |
| Discount set via `_apply_both()` | Manual edit | User changes `discount` field | Overridden if product_id or pricelist_id changes |
| SO line created with price | SO line deleted | `unlink()` on `sale.order.line` | No rollback of price computation history |
| SO amount recomputed | Revert line price_unit | Write original price back | Does not auto-revert; manual action required |
| BOM cost recalculation | Revert to list_price base | Change rule base from 'standard_price' to 'list_price' | Only affects future lines |
| Variant price_extra changed | Update attribute value price_extra | Write new `price_extra` on `product.attribute.value` | Does not retroactively update SO lines |

**Important:** Once a `sale.order.line` is confirmed (SO state moved to `sale` or beyond), changing the `price_unit` requires unlocking the line for editing or cancelling and recreating. Pricelist re-evaluation does **not** automatically update confirmed lines.

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `_onchange_product_id()` | Select product in SO line form | Per line |
| User action | `_onchange_pricelist_id()` on SO header | Change pricelist on order | Per order (recomputes all lines) |
| User action | `_onchange_partner_id()` on SO | Partner change triggers pricelist switch | Per order |
| API | `sale.order.line.write({'product_id': id})` | External system sets product | Per call |
| Import | `base_import.import` | CSV import of sale order lines | Bulk |
| Automated action | `base.automation` rule | On condition (e.g., quantity change) | Rule-based |
| Onchange cascade | `_onchange_uom()` | UoM change on line triggers recompute | Per line |
| Quantity change | `_onchange_product_uom_qty()` | Quantity-based price rule re-evaluation | Per line |
| Pricing module | `website_sale._cart_update()` | E-commerce adds to cart | Per cart update |
| POS | `pos.config` pricing | Point of Sale price lookup | Per product scan |

**For AI reasoning:** When asked "what price does customer see?", trace through: partner's pricelist → applicable rule priority → compute_price type → base_price → discount → rounding → UoM conversion.

---

## Related

- [Modules/product](Modules/product.md) — Product module reference (pricelist, template, variant)
- [Modules/Sale](Modules/Sale.md) — Sale order line model
- [Flows/Product/product-creation-flow](Flows/Product/product-creation-flow.md) — How products are created before pricing
- [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) — Full sale order lifecycle
- [Core/API](Core/API.md) — @api.depends, @api.onchange decorator patterns
- [Modules/Stock](Modules/Stock.md) — BOM/kit product stock valuation
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine pattern for SO