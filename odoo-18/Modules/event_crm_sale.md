---
Module: event_crm_sale
Version: 18.0.0
Type: addon
Tags: #odoo18 #event #crm #sale
---

## Overview

Bridges event registrations linked to sale orders with CRM lead generation. Overrides `_get_lead_grouping` on `event.registration` to group leads by `sale_order_id` instead of by partner — ensuring all registrations from the same order generate/update a single lead.

**Depends:** `event_sale`, `crm`

**Key Behavior:** When a rule triggers lead generation, registrations with the same `sale_order_id` are grouped together so that one order produces one lead.

---

## Models

### `event.registration` (Inherited)

**Inherited from:** `event.registration`

| Method | Returns | Note |
|--------|---------|------|
| `_get_lead_grouping(rules, rule_to_new_regs)` | dict | Adds `sale_order_id`-based grouping for registrations with a linked SO |
