---
type: guide
title: "Odoo 19 Installed Modules Dashboard"
module: all
audience: business-consultant, developer, ai-reasoning
level: 1
prerequisites:
  - odoo19_installed
  - vault_navigated
estimated_time: "~5 minutes"
related_guides:
  - "[[Tools/Modules Inventory]]"
  - "[[Documentation/Upgrade-Plan/CHECKPOINT-master]]"
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Odoo 19 Installed Modules Dashboard

> **Quick Summary:** Entry-point dashboard for navigating all Odoo 19 module documentation in this vault. Organized by tier — find the right module fast.

**Audience:** Functional Consultants, Developers, AI Assistants
**Difficulty:** Easy

---

## Quick Access by Tier

Jump to your tier of interest:

| Tier | Audience | Modules |
|------|----------|---------|
| [[#tier-1-critical-business]] | Core business process owners | HR, Sale, Stock, Purchase, Account |
| [[#tier-2-operational]] | Department managers, ops leads | CRM, MRP, Project, POS, Helpdesk |
| [[#tier-3-supporting]] | Specialists, analysts | Product, Quality |
| [[#tier-4-advanced]] | Developers, IT | Website, Studio, IoT, Knowledge, Rental |
| [[#utilities]] | System admins | Base, Mail, Resource, Calendar |

---

## Tier 1 — Critical Business

*These modules power the core quote-to-cash and purchase-to-pay cycles.*

### Human Resources (HR)

| Item | Details |
|------|---------|
| **Module** | `hr` |
| **Documentation** | [[Modules/HR]] |
| **What it does** | Employee records, departments, contracts, org chart |
| **Key Flows** | [[Flows/HR/employee-creation-flow]] |
| **Key Sub-Modules** | [[Modules/hr_holidays]] — Leave management |
| | [[Modules/hr_attendance]] — Attendance & check-in |
| | [[Modules/hr_expense]] — Expense claims |
| | [[Modules/hr_recruitment]] — Applicant tracking |
| | [[Modules/hr_fleet]] — Company vehicle fleet |

---

### Sales (Sale)

| Item | Details |
|------|---------|
| **Module** | `sale` |
| **Documentation** | [[Modules/Sale]] |
| **What it does** | Quotation → Sales Order → Invoice |
| **Key Flows** | [[Flows/Sale/quotation-to-sale-order-flow]] |
| | [[Flows/Sale/sale-to-delivery-flow]] |
| | [[Flows/Sale/sale-to-invoice-flow]] |
| | [[Flows/Cross-Module/sale-stock-account-flow]] |
| **Key Sub-Modules** | [[Modules/sale_management]] — Sales management |
| | [[Modules/sale_timesheet]] — Time & material invoicing |
| | [[Modules/sale_loyalty]] — Loyalty & coupons |
| | [[Modules/sale_margin]] — Margin analysis |
| | [[Modules/sale_project]] — Project invoicing |

---

### Inventory (Stock)

| Item | Details |
|------|---------|
| **Module** | `stock` |
| **Documentation** | [[Modules/Stock]] |
| **What it does** | Warehouse, transfers, quants, lots |
| **Key Flows** | [[Flows/Stock/receipt-flow]] |
| | [[Flows/Stock/delivery-flow]] |
| | [[Flows/Stock/internal-transfer-flow]] |
| | [[Flows/Cross-Module/sale-stock-account-flow]] |
| **Key Sub-Modules** | [[Modules/stock_account]] — Inventory valuation |
| | [[Modules/stock_delivery]] — Shipping integration |
| | [[Modules/stock_landed_costs]] — Landed cost allocation |
| | [[Modules/stock_picking_batch]] — Batch picking |

---

### Purchase

| Item | Details |
|------|---------|
| **Module** | `purchase` |
| **Documentation** | [[Modules/Purchase]] |
| **What it does** | RFQ → Purchase Order → Receipt → Vendor Bill |
| **Key Flows** | [[Flows/Purchase/purchase-order-creation-flow]] |
| | [[Flows/Purchase/purchase-order-receipt-flow]] |
| | [[Flows/Purchase/purchase-to-bill-flow]] |
| | [[Flows/Cross-Module/purchase-stock-account-flow]] |
| **Key Sub-Modules** | [[Modules/purchase_stock]] — PO→Receipt integration |
| | [[Modules/purchase_requisition]] — Purchase framework agreements |

---

### Accounting (Account)

| Item | Details |
|------|---------|
| **Module** | `account` |
| **Documentation** | [[Modules/Account]] |
| **What it does** | Invoices, journals, payments, tax, reconciliation |
| **Key Flows** | [[Flows/Account/invoice-creation-flow]] |
| | [[Flows/Account/invoice-post-flow]] |
| | [[Flows/Account/payment-flow]] |
| **Key Sub-Modules** | [[Modules/account_payment]] — Payment processing |
| | [[Modules/account_fleet]] — Fleet accounting |
| | [[Modules/account_peppol]] — Peppol EDI |
| | [[Modules/account_edi]] — EDI framework |

---

## Tier 2 — Operational

*These modules run day-to-day business operations.*

### CRM

| Item | Details |
|------|---------|
| **Module** | `crm` |
| **Documentation** | [[Modules/CRM]] |
| **What it does** | Lead/opportunity pipeline, sales forecasting |
| **Key Sub-Modules** | [[Modules/crm_iap_enrich]] — Lead data enrichment |
| | [[Modules/crm_sms]] — SMS integration |
| **Related Flow** | [[Flows/Cross-Module/sale-stock-account-flow]] (leads to SO) |

---

### Manufacturing (MRP)

| Item | Details |
|------|---------|
| **Module** | `mrp` |
| **Documentation** | [[Modules/MRP]] |
| **What it does** | Work orders, BOMs, production planning |
| **Key Sub-Modules** | [[Modules/mrp_account]] — Manufacturing costing |
| | [[Modules/mrp_repair]] — Repair orders |
| | [[Modules/mrp_subcontracting]] — Subcontracting flows |
| **Related Flow** | [[Flows/Cross-Module/sale-stock-account-flow]] (production→delivery) |

---

### Project

| Item | Details |
|------|---------|
| **Module** | `project` |
| **Documentation** | [[Modules/Project]] |
| **What it does** | Project management, tasks, timesheets |
| **Key Sub-Modules** | [[Modules/project_account]] — Project billing |
| | [[Modules/project_hr_expense]] — Project expense tracking |
| | [[Modules/project_mrp]] — Manufacturing projects |
| | [[Modules/project_todo]] — Task management |
| **Related Flow** | [[Flows/Sale/sale-to-invoice-flow]] (time→invoice via sale_timesheet) |

---

### Point of Sale (POS)

| Item | Details |
|------|---------|
| **Module** | `point_of_sale` |
| **Documentation** | [[Modules/POS]] |
| **What it does** | Retail POS, sessions, orders, cash management |
| **Key Sub-Modules** | [[Modules/pos_restaurant]] — Restaurant POS |
| | [[Modules/pos_self_order]] — Self-order kiosk |
| | [[Modules/pos_loyalty]] — POS loyalty program |
| | [[Modules/pos_sale]] — POS linked to Sale orders |
| | [[Modules/pos_adyen]] — Adyen payment terminal |
| | [[Modules/pos_stripe]] — Stripe payment terminal |

---

### Helpdesk

| Item | Details |
|------|---------|
| **Module** | `helpdesk` |
| **Documentation** | [[Modules/helpdesk]] |
| **What it does** | Customer tickets, SLA management, team routing |
| **Related Modules** | [[Modules/mail]] — Ticket notifications |
| | [[Modules/portal]] — Customer portal tickets |

---

## Tier 3 — Supporting

*Specialist modules that support core operations.*

### Product

| Item | Details |
|------|---------|
| **Module** | `product` |
| **Documentation** | [[Modules/Product]] |
| **What it does** | Product templates, variants, pricelists, routes |
| **Key Sub-Modules** | [[Modules/product_margin]] — Margin analysis |
| | [[Modules/product_expiry]] — Lot expiry tracking |
| | [[Modules/product_matrix]] — Grid product configurator |

---

### Quality

| Item | Details |
|------|---------|
| **Module** | `quality` |
| **Documentation** | [[Modules/quality]] |
| **What it does** | Quality checks, control points, alerts |
| **Related Modules** | [[Modules/stock]] — QC on receipts |
| | [[Modules/mrp]] — QC on production |

---

## Tier 4 — Advanced

*Advanced modules for developers, IT, and specialized business needs.*

### Website / E-Commerce

| Item | Details |
|------|---------|
| **Module** | `website` |
| **Documentation** | [[Modules/website]] |
| **What it does** | Website builder, CMS, SEO |
| **Key Sub-Modules** | [[Modules/website_sale]] — E-commerce shop |
| | [[Modules/website_sale_stock]] — Inventory sync to web |
| | [[Modules/website_slides]] — Course/knowledge platform |
| | [[Modules/website_payment]] — Online payments |
| | [[Modules/website_crm]] — Website lead capture |

---

### IoT — Hardware

| Item | Details |
|------|---------|
| **Module** | `iot_base` + `iot_drivers` |
| **Documentation** | [[Modules/iot]] |
| **What it does** | IoT box and device management |
| **Device Types** | Receipt printers, barcode scanners, scales, displays |
| **Related Modules** | [[Modules/Stock]] — Barcode scanner integration |
| | [[Modules/POS]] — Receipt printer integration |

---

### Studio — No-Code Builder

| Item | Details |
|------|---------|
| **Module** | `studio` (part of `web`) |
| **Documentation** | [[Modules/studio]] |
| **What it does** | Visual app builder, custom models/fields/views |
| **Audience** | Power users, functional consultants |
| **Note** | Enterprise only |

---

### Knowledge — Wiki

| Item | Details |
|------|---------|
| **Module** | `knowledge` |
| **Documentation** | [[Modules/knowledge]] |
| **What it does** | Internal wiki, articles, collaborative writing |
| **Related Modules** | [[Modules/mail]] — Article comment threads |
| | [[Modules/mail]] — Workspace channels |

---

### Rental / Asset Lease

| Item | Details |
|------|---------|
| **Module** | `rental` |
| **Documentation** | [[Modules/rental]] |
| **What it does** | Equipment rental, contracts, pickup/return |
| **Related Modules** | [[Modules/Sale]] — Rental quotations |
| | [[Modules/Stock]] — Rental inventory |
| | [[Modules/Fleet]] — Vehicle rental |

---

## Utilities

*Foundation modules that everything else depends on.*

### Base

| Item | Details |
|------|---------|
| **Module** | `base` |
| **Documentation** | [[Modules/base_setup]] |
| **What it does** | Company, user, currency, locale, sequence defaults |
| **Key Sub-Modules** | [[Modules/base_vat]] — VAT/TAX ID validation |
| | [[Modules/base_iban]] — IBAN bank account support |
| | [[Modules/base_address_extended]] — Address formatting |
| | [[Modules/base_geolocalize]] — GPS geolocation |

---

### Mail

| Item | Details |
|------|---------|
| **Module** | `mail` |
| **Documentation** | [[Modules/mail]] |
| **What it does** | Email, messaging, mail templates, follow/unfollow |
| **Key Sub-Modules** | [[Modules/mail_group]] — Group messaging |
| | [[Modules/mail_plugin]] — Email plugin |
| **Related Modules** | [[Modules/portal]] — Customer portal messaging |

---

### Resource

| Item | Details |
|------|---------|
| **Module** | `resource` |
| **Documentation** | [[Modules/resource]] |
| **What it does** | Working hours, calendars, resource planning |
| **Related Modules** | [[Modules/HR]] — Employee scheduling |
| | [[Modules/calendar]] — Meetings and scheduling |

---

### Calendar

| Item | Details |
|------|---------|
| **Module** | `calendar` |
| **Documentation** | [[Modules/calendar]] |
| **What it does** | Meeting scheduling, reminders, calendar views |
| **Key Sub-Modules** | [[Modules/calendar_sms]] — SMS reminders |
| | [[Modules/microsoft_calendar]] — Outlook sync |

---

## All Modules Index

> A complete alphabetical index of all module documentation files in this vault.

### A

| Module | File | Category |
|--------|------|----------|
| account | [[Modules/Account]] | Tier 1 — Accounting |
| account_fleet | [[Modules/account_fleet]] | Accounting extension |
| account_payment | [[Modules/account_payment]] | Payment processing |
| account_peppol | [[Modules/account_peppol]] | Peppol EDI |
| account_edi | [[Modules/account_edi]] | EDI framework |
| analytic | [[Modules/analytic]] | Analytic accounting |
| auth_* | Multiple | Authentication modules |
| availability | — | (part of stock) |

### B–C

| Module | File | Category |
|--------|------|----------|
| barcodes | [[Modules/barcodes]] | Barcode scanning |
| board | [[Modules/board]] | Dashboard kanban |
| bus | [[Modules/bus]] | Real-time bus |
| calendar | [[Modules/calendar]] | Utility — Scheduling |
| contacts | [[Modules/contacts]] | Contact management |
| crm | [[Modules/CRM]] | Tier 2 — CRM |

### D–F

| Module | File | Category |
|--------|------|----------|
| delivery | [[Modules/delivery]] | Shipping methods |
| digest | [[Modules/digest]] | KPI dashboards |
| event | [[Modules/event]] | Event management |
| fleet | [[Modules/fleet]] | Vehicle fleet |

### G–H

| Module | File | Category |
|--------|------|----------|
| gamification | [[Modules/gamification]] | Challenges & badges |
| google_* | Multiple | Google integrations |
| helpdesk | [[Modules/helpdesk]] | Tier 2 — Helpdesk |
| hr | [[Modules/HR]] | Tier 1 — HR |
| hr_holidays | [[Modules/hr_holidays]] | Leave management |
| hr_attendance | [[Modules/hr_attendance]] | Attendance |

### I–K

| Module | File | Category |
|--------|------|----------|
| iot | [[Modules/iot]] | Tier 4 — IoT |
| knowledge | [[Modules/knowledge]] | Tier 4 — Wiki |

### L–M

| Module | File | Category |
|--------|------|----------|
| l10n_* | [[Modules/l10n_id]] and 80+ others | Country localizations |
| loyalty | [[Modules/loyalty]] | Loyalty programs |
| mail | [[Modules/mail]] | Utility — Email |
| mass_mailing | [[Modules/mass_mailing]] | Email campaigns |
| mrp | [[Modules/MRP]] | Tier 2 — Manufacturing |

### N–P

| Module | File | Category |
|--------|------|----------|
| note | (note module) | Sticky notes |
| payment | [[Modules/payment]] | Payment provider framework |
| point_of_sale | [[Modules/POS]] | Tier 2 — POS |
| portal | [[Modules/portal]] | Customer portal |
| product | [[Modules/Product]] | Tier 3 — Product |
| project | [[Modules/Project]] | Tier 2 — Project |

### Q–R

| Module | File | Category |
|--------|------|----------|
| quality | [[Modules/quality]] | Tier 3 — Quality |
| rental | [[Modules/rental]] | Tier 4 — Rental |
| repair | [[Modules/repair]] | After-sale repair |
| resource | [[Modules/resource]] | Utility — Resource |

### S

| Module | File | Category |
|--------|------|----------|
| sale | [[Modules/Sale]] | Tier 1 — Sales |
| sale_management | [[Modules/sale_management]] | Sales extension |
| sale_timesheet | [[Modules/sale_timesheet]] | Time billing |
| sale_loyalty | [[Modules/sale_loyalty]] | Loyalty |
| sale_project | [[Modules/sale_project]] | Project billing |
| sale_stock | [[Modules/sale_stock]] | Sale↔Stock integration |
| sms | [[Modules/sms]] | SMS gateway |
| spreadsheet | [[Modules/spreadsheet]] | Spreadsheet engine |
| stock | [[Modules/Stock]] | Tier 1 — Inventory |
| stock_account | [[Modules/stock_account]] | Inventory valuation |
| studio | [[Modules/studio]] | Tier 4 — App Builder |

### T–W

| Module | File | Category |
|--------|------|----------|
| test_* | Multiple | Test modules (ignore) |
| uom | [[Modules/uom]] | Unit of measure |
| utm | [[Modules/utm]] | Marketing tracking |
| web | [[Modules/web]] | Web framework |
| website | [[Modules/website]] | Tier 4 — Website |
| website_sale | [[Modules/website_sale]] | E-commerce |
| website_slides | [[Modules/website_slides]] | E-learning |

---

## Localization Modules

> Country-specific accounting localizations. All documented in `Modules/l10n_*.md`.

| Region | Key Modules |
|--------|-------------|
| **Americas** | l10n_us, l10n_mx, l10n_br, l10n_co, l10n_pe, l10n_cl, l10n_ar, l10n_ec |
| **Europe** | l10n_de, l10n_fr, l10n_it, l10n_es, l10n_nl, l10n_be, l10n_at, l10n_ch, l10n_pl, l10n_ro |
| **Asia-Pacific** | l10n_id, l10n_in, l10n_vn, l10n_th, l10n_my, l10n_sg, l10n_ph, l10n_cn, l10n_jp, l10n_kr, l10n_tw |
| **Middle East** | l10n_sa, l10n_ae, l10n_eg, l10n_tr, l10n_il |
| **Africa** | l10n_za, l10n_ke, l10n_ng, l10n_ma |
| **EDI / Tax Reports** | l10n_it_edi, l10n_es_edi_sii, l10n_es_edi_facturae, l10n_id_efaktur_coretax, l10n_br_edi, l10n_in_ewaybill |

See [[Modules/l10n_id]] for full Indonesian example. See [[Modules/l10n_de]], [[Modules/l10n_us]], [[Modules/l10n_fr]] for quick-access versions.

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| Guide | [[Documentation/Upgrade-Plan/CHECKPOINT-master]] | Coverage progress tracker |
| Guide | [[Tools/Modules Inventory]] | Full module catalog |
| Pattern | [[Patterns/Workflow Patterns]] | Cross-module flow design |
| Snippet | [[Snippets/Model Snippets]] | Code templates |
| Core | [[Core/BaseModel]] | ORM foundation |
