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
  - "[Tools/Modules Inventory](tools/modules-inventory.md)"
  - "[Documentation/Upgrade-Plan/CHECKPOINT-master](documentation/upgrade-plan/checkpoint-master.md)"
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
| [#tier-1-critical-business](#tier-1-critical-business.md) | Core business process owners | HR, Sale, Stock, Purchase, Account |
| [#tier-2-operational](#tier-2-operational.md) | Department managers, ops leads | CRM, MRP, Project, POS, Helpdesk |
| [#tier-3-supporting](#tier-3-supporting.md) | Specialists, analysts | Product, Quality |
| [#tier-4-advanced](#tier-4-advanced.md) | Developers, IT | Website, Studio, IoT, Knowledge, Rental |
| [#utilities](#utilities.md) | System admins | Base, Mail, Resource, Calendar |

---

## Tier 1 — Critical Business

*These modules power the core quote-to-cash and purchase-to-pay cycles.*

### Human Resources (HR)

| Item | Details |
|------|---------|
| **Module** | `hr` |
| **Documentation** | [Modules/HR](modules/hr.md) |
| **What it does** | Employee records, departments, contracts, org chart |
| **Key Flows** | [Flows/HR/employee-creation-flow](flows/hr/employee-creation-flow.md) |
| **Key Sub-Modules** | [Modules/hr_holidays](modules/hr_holidays.md) — Leave management |
| | [Modules/hr_attendance](modules/hr_attendance.md) — Attendance & check-in |
| | [Modules/hr_expense](modules/hr_expense.md) — Expense claims |
| | [Modules/hr_recruitment](modules/hr_recruitment.md) — Applicant tracking |
| | [Modules/hr_fleet](modules/hr_fleet.md) — Company vehicle fleet |

---

### Sales (Sale)

| Item | Details |
|------|---------|
| **Module** | `sale` |
| **Documentation** | [Modules/Sale](modules/sale.md) |
| **What it does** | Quotation → Sales Order → Invoice |
| **Key Flows** | [Flows/Sale/quotation-to-sale-order-flow](flows/sale/quotation-to-sale-order-flow.md) |
| | [Flows/Sale/sale-to-delivery-flow](flows/sale/sale-to-delivery-flow.md) |
| | [Flows/Sale/sale-to-invoice-flow](flows/sale/sale-to-invoice-flow.md) |
| | [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/sale_management](modules/sale_management.md) — Sales management |
| | [Modules/sale_timesheet](modules/sale_timesheet.md) — Time & material invoicing |
| | [Modules/sale_loyalty](modules/sale_loyalty.md) — Loyalty & coupons |
| | [Modules/sale_margin](modules/sale_margin.md) — Margin analysis |
| | [Modules/sale_project](modules/sale_project.md) — Project invoicing |

---

### Inventory (Stock)

| Item | Details |
|------|---------|
| **Module** | `stock` |
| **Documentation** | [Modules/Stock](modules/stock.md) |
| **What it does** | Warehouse, transfers, quants, lots |
| **Key Flows** | [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) |
| | [Flows/Stock/delivery-flow](flows/stock/delivery-flow.md) |
| | [Flows/Stock/internal-transfer-flow](flows/stock/internal-transfer-flow.md) |
| | [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/stock_account](modules/stock_account.md) — Inventory valuation |
| | [Modules/stock_delivery](modules/stock_delivery.md) — Shipping integration |
| | [Modules/stock_landed_costs](modules/stock_landed_costs.md) — Landed cost allocation |
| | [Modules/stock_picking_batch](modules/stock_picking_batch.md) — Batch picking |

---

### Purchase

| Item | Details |
|------|---------|
| **Module** | `purchase` |
| **Documentation** | [Modules/Purchase](modules/purchase.md) |
| **What it does** | RFQ → Purchase Order → Receipt → Vendor Bill |
| **Key Flows** | [Flows/Purchase/purchase-order-creation-flow](flows/purchase/purchase-order-creation-flow.md) |
| | [Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md) |
| | [Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md) |
| | [Flows/Cross-Module/purchase-stock-account-flow](flows/cross-module/purchase-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/purchase_stock](modules/purchase_stock.md) — PO→Receipt integration |
| | [Modules/purchase_requisition](modules/purchase_requisition.md) — Purchase framework agreements |

---

### Accounting (Account)

| Item | Details |
|------|---------|
| **Module** | `account` |
| **Documentation** | [Modules/Account](modules/account.md) |
| **What it does** | Invoices, journals, payments, tax, reconciliation |
| **Key Flows** | [Flows/Account/invoice-creation-flow](flows/account/invoice-creation-flow.md) |
| | [Flows/Account/invoice-post-flow](flows/account/invoice-post-flow.md) |
| | [Flows/Account/payment-flow](flows/account/payment-flow.md) |
| **Key Sub-Modules** | [Modules/account_payment](modules/account_payment.md) — Payment processing |
| | [Modules/account_fleet](modules/account_fleet.md) — Fleet accounting |
| | [Modules/account_peppol](modules/account_peppol.md) — Peppol EDI |
| | [Modules/account_edi](modules/account_edi.md) — EDI framework |

---

## Tier 2 — Operational

*These modules run day-to-day business operations.*

### CRM

| Item | Details |
|------|---------|
| **Module** | `crm` |
| **Documentation** | [Modules/CRM](modules/crm.md) |
| **What it does** | Lead/opportunity pipeline, sales forecasting |
| **Key Sub-Modules** | [Modules/crm_iap_enrich](modules/crm_iap_enrich.md) — Lead data enrichment |
| | [Modules/crm_sms](modules/crm_sms.md) — SMS integration |
| **Related Flow** | [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) (leads to SO) |

---

### Manufacturing (MRP)

| Item | Details |
|------|---------|
| **Module** | `mrp` |
| **Documentation** | [Modules/MRP](modules/mrp.md) |
| **What it does** | Work orders, BOMs, production planning |
| **Key Sub-Modules** | [Modules/mrp_account](modules/mrp_account.md) — Manufacturing costing |
| | [Modules/mrp_repair](modules/mrp_repair.md) — Repair orders |
| | [Modules/mrp_subcontracting](modules/mrp_subcontracting.md) — Subcontracting flows |
| **Related Flow** | [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) (production→delivery) |

---

### Project

| Item | Details |
|------|---------|
| **Module** | `project` |
| **Documentation** | [Modules/Project](modules/project.md) |
| **What it does** | Project management, tasks, timesheets |
| **Key Sub-Modules** | [Modules/project_account](modules/project_account.md) — Project billing |
| | [Modules/project_hr_expense](modules/project_hr_expense.md) — Project expense tracking |
| | [Modules/project_mrp](modules/project_mrp.md) — Manufacturing projects |
| | [Modules/project_todo](modules/project_todo.md) — Task management |
| **Related Flow** | [Flows/Sale/sale-to-invoice-flow](flows/sale/sale-to-invoice-flow.md) (time→invoice via sale_timesheet) |

---

### Point of Sale (POS)

| Item | Details |
|------|---------|
| **Module** | `point_of_sale` |
| **Documentation** | [Modules/POS](modules/pos.md) |
| **What it does** | Retail POS, sessions, orders, cash management |
| **Key Sub-Modules** | [Modules/pos_restaurant](modules/pos_restaurant.md) — Restaurant POS |
| | [Modules/pos_self_order](modules/pos_self_order.md) — Self-order kiosk |
| | [Modules/pos_loyalty](modules/pos_loyalty.md) — POS loyalty program |
| | [Modules/pos_sale](modules/pos_sale.md) — POS linked to Sale orders |
| | [Modules/pos_adyen](modules/pos_adyen.md) — Adyen payment terminal |
| | [Modules/pos_stripe](modules/pos_stripe.md) — Stripe payment terminal |

---

### Helpdesk

| Item | Details |
|------|---------|
| **Module** | `helpdesk` |
| **Documentation** | [Modules/helpdesk](modules/helpdesk.md) |
| **What it does** | Customer tickets, SLA management, team routing |
| **Related Modules** | [Modules/mail](modules/mail.md) — Ticket notifications |
| | [Modules/portal](modules/portal.md) — Customer portal tickets |

---

## Tier 3 — Supporting

*Specialist modules that support core operations.*

### Product

| Item | Details |
|------|---------|
| **Module** | `product` |
| **Documentation** | [Modules/Product](modules/product.md) |
| **What it does** | Product templates, variants, pricelists, routes |
| **Key Sub-Modules** | [Modules/product_margin](modules/product_margin.md) — Margin analysis |
| | [Modules/product_expiry](modules/product_expiry.md) — Lot expiry tracking |
| | [Modules/product_matrix](modules/product_matrix.md) — Grid product configurator |

---

### Quality

| Item | Details |
|------|---------|
| **Module** | `quality` |
| **Documentation** | [Modules/quality](modules/quality.md) |
| **What it does** | Quality checks, control points, alerts |
| **Related Modules** | [Modules/stock](modules/stock.md) — QC on receipts |
| | [Modules/mrp](modules/mrp.md) — QC on production |

---

## Tier 4 — Advanced

*Advanced modules for developers, IT, and specialized business needs.*

### Website / E-Commerce

| Item | Details |
|------|---------|
| **Module** | `website` |
| **Documentation** | [Modules/website](modules/website.md) |
| **What it does** | Website builder, CMS, SEO |
| **Key Sub-Modules** | [Modules/website_sale](modules/website_sale.md) — E-commerce shop |
| | [Modules/website_sale_stock](modules/website_sale_stock.md) — Inventory sync to web |
| | [Modules/website_slides](modules/website_slides.md) — Course/knowledge platform |
| | [Modules/website_payment](modules/website_payment.md) — Online payments |
| | [Modules/website_crm](modules/website_crm.md) — Website lead capture |

---

### IoT — Hardware

| Item | Details |
|------|---------|
| **Module** | `iot_base` + `iot_drivers` |
| **Documentation** | [Modules/iot](modules/iot.md) |
| **What it does** | IoT box and device management |
| **Device Types** | Receipt printers, barcode scanners, scales, displays |
| **Related Modules** | [Modules/Stock](modules/stock.md) — Barcode scanner integration |
| | [Modules/POS](modules/pos.md) — Receipt printer integration |

---

### Studio — No-Code Builder

| Item | Details |
|------|---------|
| **Module** | `studio` (part of `web`) |
| **Documentation** | [Modules/studio](modules/studio.md) |
| **What it does** | Visual app builder, custom models/fields/views |
| **Audience** | Power users, functional consultants |
| **Note** | Enterprise only |

---

### Knowledge — Wiki

| Item | Details |
|------|---------|
| **Module** | `knowledge` |
| **Documentation** | [Modules/knowledge](modules/knowledge.md) |
| **What it does** | Internal wiki, articles, collaborative writing |
| **Related Modules** | [Modules/mail](modules/mail.md) — Article comment threads |
| | [Modules/mail](modules/mail.md) — Workspace channels |

---

### Rental / Asset Lease

| Item | Details |
|------|---------|
| **Module** | `rental` |
| **Documentation** | [Modules/rental](modules/rental.md) |
| **What it does** | Equipment rental, contracts, pickup/return |
| **Related Modules** | [Modules/Sale](modules/sale.md) — Rental quotations |
| | [Modules/Stock](modules/stock.md) — Rental inventory |
| | [Modules/Fleet](modules/fleet.md) — Vehicle rental |

---

## Utilities

*Foundation modules that everything else depends on.*

### Base

| Item | Details |
|------|---------|
| **Module** | `base` |
| **Documentation** | [Modules/base_setup](modules/base_setup.md) |
| **What it does** | Company, user, currency, locale, sequence defaults |
| **Key Sub-Modules** | [Modules/base_vat](modules/base_vat.md) — VAT/TAX ID validation |
| | [Modules/base_iban](modules/base_iban.md) — IBAN bank account support |
| | [Modules/base_address_extended](modules/base_address_extended.md) — Address formatting |
| | [Modules/base_geolocalize](modules/base_geolocalize.md) — GPS geolocation |

---

### Mail

| Item | Details |
|------|---------|
| **Module** | `mail` |
| **Documentation** | [Modules/mail](modules/mail.md) |
| **What it does** | Email, messaging, mail templates, follow/unfollow |
| **Key Sub-Modules** | [Modules/mail_group](modules/mail_group.md) — Group messaging |
| | [Modules/mail_plugin](modules/mail_plugin.md) — Email plugin |
| **Related Modules** | [Modules/portal](modules/portal.md) — Customer portal messaging |

---

### Resource

| Item | Details |
|------|---------|
| **Module** | `resource` |
| **Documentation** | [Modules/resource](modules/resource.md) |
| **What it does** | Working hours, calendars, resource planning |
| **Related Modules** | [Modules/HR](modules/hr.md) — Employee scheduling |
| | [Modules/calendar](modules/calendar.md) — Meetings and scheduling |

---

### Calendar

| Item | Details |
|------|---------|
| **Module** | `calendar` |
| **Documentation** | [Modules/calendar](modules/calendar.md) |
| **What it does** | Meeting scheduling, reminders, calendar views |
| **Key Sub-Modules** | [Modules/calendar_sms](modules/calendar_sms.md) — SMS reminders |
| | [Modules/microsoft_calendar](modules/microsoft_calendar.md) — Outlook sync |

---

## All Modules Index

> A complete alphabetical index of all module documentation files in this vault.

### A

| Module | File | Category |
|--------|------|----------|
| account | [Modules/Account](modules/account.md) | Tier 1 — Accounting |
| account_fleet | [Modules/account_fleet](modules/account_fleet.md) | Accounting extension |
| account_payment | [Modules/account_payment](modules/account_payment.md) | Payment processing |
| account_peppol | [Modules/account_peppol](modules/account_peppol.md) | Peppol EDI |
| account_edi | [Modules/account_edi](modules/account_edi.md) | EDI framework |
| analytic | [Modules/analytic](modules/analytic.md) | Analytic accounting |
| auth_* | Multiple | Authentication modules |
| availability | — | (part of stock) |

### B–C

| Module | File | Category |
|--------|------|----------|
| barcodes | [Modules/barcodes](modules/barcodes.md) | Barcode scanning |
| board | [Modules/board](modules/board.md) | Dashboard kanban |
| bus | [Modules/bus](modules/bus.md) | Real-time bus |
| calendar | [Modules/calendar](modules/calendar.md) | Utility — Scheduling |
| contacts | [Modules/contacts](modules/contacts.md) | Contact management |
| crm | [Modules/CRM](modules/crm.md) | Tier 2 — CRM |

### D–F

| Module | File | Category |
|--------|------|----------|
| delivery | [Modules/delivery](modules/delivery.md) | Shipping methods |
| digest | [Modules/digest](modules/digest.md) | KPI dashboards |
| event | [Modules/event](modules/event.md) | Event management |
| fleet | [Modules/fleet](modules/fleet.md) | Vehicle fleet |

### G–H

| Module | File | Category |
|--------|------|----------|
| gamification | [Modules/gamification](modules/gamification.md) | Challenges & badges |
| google_* | Multiple | Google integrations |
| helpdesk | [Modules/helpdesk](modules/helpdesk.md) | Tier 2 — Helpdesk |
| hr | [Modules/HR](modules/hr.md) | Tier 1 — HR |
| hr_holidays | [Modules/hr_holidays](modules/hr_holidays.md) | Leave management |
| hr_attendance | [Modules/hr_attendance](modules/hr_attendance.md) | Attendance |

### I–K

| Module | File | Category |
|--------|------|----------|
| iot | [Modules/iot](modules/iot.md) | Tier 4 — IoT |
| knowledge | [Modules/knowledge](modules/knowledge.md) | Tier 4 — Wiki |

### L–M

| Module | File | Category |
|--------|------|----------|
| l10n_* | [Modules/l10n_id](modules/l10n_id.md) and 80+ others | Country localizations |
| loyalty | [Modules/loyalty](modules/loyalty.md) | Loyalty programs |
| mail | [Modules/mail](modules/mail.md) | Utility — Email |
| mass_mailing | [Modules/mass_mailing](modules/mass_mailing.md) | Email campaigns |
| mrp | [Modules/MRP](modules/mrp.md) | Tier 2 — Manufacturing |

### N–P

| Module | File | Category |
|--------|------|----------|
| note | (note module) | Sticky notes |
| payment | [Modules/payment](modules/payment.md) | Payment provider framework |
| point_of_sale | [Modules/POS](modules/pos.md) | Tier 2 — POS |
| portal | [Modules/portal](modules/portal.md) | Customer portal |
| product | [Modules/Product](modules/product.md) | Tier 3 — Product |
| project | [Modules/Project](modules/project.md) | Tier 2 — Project |

### Q–R

| Module | File | Category |
|--------|------|----------|
| quality | [Modules/quality](modules/quality.md) | Tier 3 — Quality |
| rental | [Modules/rental](modules/rental.md) | Tier 4 — Rental |
| repair | [Modules/repair](modules/repair.md) | After-sale repair |
| resource | [Modules/resource](modules/resource.md) | Utility — Resource |

### S

| Module | File | Category |
|--------|------|----------|
| sale | [Modules/Sale](modules/sale.md) | Tier 1 — Sales |
| sale_management | [Modules/sale_management](modules/sale_management.md) | Sales extension |
| sale_timesheet | [Modules/sale_timesheet](modules/sale_timesheet.md) | Time billing |
| sale_loyalty | [Modules/sale_loyalty](modules/sale_loyalty.md) | Loyalty |
| sale_project | [Modules/sale_project](modules/sale_project.md) | Project billing |
| sale_stock | [Modules/sale_stock](modules/sale_stock.md) | Sale↔Stock integration |
| sms | [Modules/sms](modules/sms.md) | SMS gateway |
| spreadsheet | [Modules/spreadsheet](modules/spreadsheet.md) | Spreadsheet engine |
| stock | [Modules/Stock](modules/stock.md) | Tier 1 — Inventory |
| stock_account | [Modules/stock_account](modules/stock_account.md) | Inventory valuation |
| studio | [Modules/studio](modules/studio.md) | Tier 4 — App Builder |

### T–W

| Module | File | Category |
|--------|------|----------|
| test_* | Multiple | Test modules (ignore) |
| uom | [Modules/uom](modules/uom.md) | Unit of measure |
| utm | [Modules/utm](modules/utm.md) | Marketing tracking |
| web | [Modules/web](modules/web.md) | Web framework |
| website | [Modules/website](modules/website.md) | Tier 4 — Website |
| website_sale | [Modules/website_sale](modules/website_sale.md) | E-commerce |
| website_slides | [Modules/website_slides](modules/website_slides.md) | E-learning |

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

See [Modules/l10n_id](modules/l10n_id.md) for full Indonesian example. See [Modules/l10n_de](modules/l10n_de.md), [Modules/l10n_us](modules/l10n_us.md), [Modules/l10n_fr](modules/l10n_fr.md) for quick-access versions.

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| Guide | [Documentation/Upgrade-Plan/CHECKPOINT-master](documentation/upgrade-plan/checkpoint-master.md) | Coverage progress tracker |
| Guide | [Tools/Modules Inventory](tools/modules-inventory.md) | Full module catalog |
| Pattern | [Patterns/Workflow Patterns](patterns/workflow-patterns.md) | Cross-module flow design |
| Snippet | [Snippets/Model Snippets](snippets/model-snippets.md) | Code templates |
| Core | [Core/BaseModel](core/basemodel.md) | ORM foundation |
