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
  - "[Tools/Modules Inventory](Tools/Modules-Inventory.md)"
  - "[Documentation/Upgrade-Plan/CHECKPOINT-master](Documentation/Upgrade-Plan/CHECKPOINT-master.md)"
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
| **Documentation** | [Modules/HR](Modules/HR.md) |
| **What it does** | Employee records, departments, contracts, org chart |
| **Key Flows** | [Flows/HR/employee-creation-flow](Flows/HR/employee-creation-flow.md) |
| **Key Sub-Modules** | [Modules/hr_holidays](Modules/hr_holidays.md) — Leave management |
| | [Modules/hr_attendance](Modules/hr_attendance.md) — Attendance & check-in |
| | [Modules/hr_expense](Modules/hr_expense.md) — Expense claims |
| | [Modules/hr_recruitment](Modules/hr_recruitment.md) — Applicant tracking |
| | [Modules/hr_fleet](Modules/hr_fleet.md) — Company vehicle fleet |

---

### Sales (Sale)

| Item | Details |
|------|---------|
| **Module** | `sale` |
| **Documentation** | [Modules/Sale](Modules/Sale.md) |
| **What it does** | Quotation → Sales Order → Invoice |
| **Key Flows** | [Flows/Sale/quotation-to-sale-order-flow](Flows/Sale/quotation-to-sale-order-flow.md) |
| | [Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md) |
| | [Flows/Sale/sale-to-invoice-flow](Flows/Sale/sale-to-invoice-flow.md) |
| | [Flows/Cross-Module/sale-stock-account-flow](Flows/Cross-Module/sale-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/sale_management](Modules/sale_management.md) — Sales management |
| | [Modules/sale_timesheet](Modules/sale_timesheet.md) — Time & material invoicing |
| | [Modules/sale_loyalty](Modules/sale_loyalty.md) — Loyalty & coupons |
| | [Modules/sale_margin](Modules/sale_margin.md) — Margin analysis |
| | [Modules/sale_project](Modules/sale_project.md) — Project invoicing |

---

### Inventory (Stock)

| Item | Details |
|------|---------|
| **Module** | `stock` |
| **Documentation** | [Modules/Stock](Modules/Stock.md) |
| **What it does** | Warehouse, transfers, quants, lots |
| **Key Flows** | [Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md) |
| | [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) |
| | [Flows/Stock/internal-transfer-flow](Flows/Stock/internal-transfer-flow.md) |
| | [Flows/Cross-Module/sale-stock-account-flow](Flows/Cross-Module/sale-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/stock_account](Modules/stock_account.md) — Inventory valuation |
| | [Modules/stock_delivery](Modules/stock_delivery.md) — Shipping integration |
| | [Modules/stock_landed_costs](Modules/stock_landed_costs.md) — Landed cost allocation |
| | [Modules/stock_picking_batch](Modules/stock_picking_batch.md) — Batch picking |

---

### Purchase

| Item | Details |
|------|---------|
| **Module** | `purchase` |
| **Documentation** | [Modules/Purchase](Modules/Purchase.md) |
| **What it does** | RFQ → Purchase Order → Receipt → Vendor Bill |
| **Key Flows** | [Flows/Purchase/purchase-order-creation-flow](Flows/Purchase/purchase-order-creation-flow.md) |
| | [Flows/Purchase/purchase-order-receipt-flow](Flows/Purchase/purchase-order-receipt-flow.md) |
| | [Flows/Purchase/purchase-to-bill-flow](Flows/Purchase/purchase-to-bill-flow.md) |
| | [Flows/Cross-Module/purchase-stock-account-flow](Flows/Cross-Module/purchase-stock-account-flow.md) |
| **Key Sub-Modules** | [Modules/purchase_stock](Modules/purchase_stock.md) — PO→Receipt integration |
| | [Modules/purchase_requisition](Modules/purchase_requisition.md) — Purchase framework agreements |

---

### Accounting (Account)

| Item | Details |
|------|---------|
| **Module** | `account` |
| **Documentation** | [Modules/Account](Modules/Account.md) |
| **What it does** | Invoices, journals, payments, tax, reconciliation |
| **Key Flows** | [Flows/Account/invoice-creation-flow](Flows/Account/invoice-creation-flow.md) |
| | [Flows/Account/invoice-post-flow](Flows/Account/invoice-post-flow.md) |
| | [Flows/Account/payment-flow](Flows/Account/payment-flow.md) |
| **Key Sub-Modules** | [Modules/account_payment](Modules/account_payment.md) — Payment processing |
| | [Modules/account_fleet](Modules/account_fleet.md) — Fleet accounting |
| | [Modules/account_peppol](Modules/account_peppol.md) — Peppol EDI |
| | [Modules/account_edi](Modules/account_edi.md) — EDI framework |

---

## Tier 2 — Operational

*These modules run day-to-day business operations.*

### CRM

| Item | Details |
|------|---------|
| **Module** | `crm` |
| **Documentation** | [Modules/CRM](Modules/CRM.md) |
| **What it does** | Lead/opportunity pipeline, sales forecasting |
| **Key Sub-Modules** | [Modules/crm_iap_enrich](Modules/crm_iap_enrich.md) — Lead data enrichment |
| | [Modules/crm_sms](Modules/crm_sms.md) — SMS integration |
| **Related Flow** | [Flows/Cross-Module/sale-stock-account-flow](Flows/Cross-Module/sale-stock-account-flow.md) (leads to SO) |

---

### Manufacturing (MRP)

| Item | Details |
|------|---------|
| **Module** | `mrp` |
| **Documentation** | [Modules/MRP](Modules/MRP.md) |
| **What it does** | Work orders, BOMs, production planning |
| **Key Sub-Modules** | [Modules/mrp_account](Modules/mrp_account.md) — Manufacturing costing |
| | [Modules/mrp_repair](Modules/mrp_repair.md) — Repair orders |
| | [Modules/mrp_subcontracting](Modules/mrp_subcontracting.md) — Subcontracting flows |
| **Related Flow** | [Flows/Cross-Module/sale-stock-account-flow](Flows/Cross-Module/sale-stock-account-flow.md) (production→delivery) |

---

### Project

| Item | Details |
|------|---------|
| **Module** | `project` |
| **Documentation** | [Modules/Project](Modules/Project.md) |
| **What it does** | Project management, tasks, timesheets |
| **Key Sub-Modules** | [Modules/project_account](Modules/project_account.md) — Project billing |
| | [Modules/project_hr_expense](Modules/project_hr_expense.md) — Project expense tracking |
| | [Modules/project_mrp](Modules/project_mrp.md) — Manufacturing projects |
| | [Modules/project_todo](Modules/project_todo.md) — Task management |
| **Related Flow** | [Flows/Sale/sale-to-invoice-flow](Flows/Sale/sale-to-invoice-flow.md) (time→invoice via sale_timesheet) |

---

### Point of Sale (POS)

| Item | Details |
|------|---------|
| **Module** | `point_of_sale` |
| **Documentation** | [Modules/POS](Modules/POS.md) |
| **What it does** | Retail POS, sessions, orders, cash management |
| **Key Sub-Modules** | [Modules/pos_restaurant](Modules/pos_restaurant.md) — Restaurant POS |
| | [Modules/pos_self_order](Modules/pos_self_order.md) — Self-order kiosk |
| | [Modules/pos_loyalty](Modules/pos_loyalty.md) — POS loyalty program |
| | [Modules/pos_sale](Modules/pos_sale.md) — POS linked to Sale orders |
| | [Modules/pos_adyen](Modules/pos_adyen.md) — Adyen payment terminal |
| | [Modules/pos_stripe](Modules/pos_stripe.md) — Stripe payment terminal |

---

### Helpdesk

| Item | Details |
|------|---------|
| **Module** | `helpdesk` |
| **Documentation** | [Modules/helpdesk](Modules/helpdesk.md) |
| **What it does** | Customer tickets, SLA management, team routing |
| **Related Modules** | [Modules/mail](Modules/mail.md) — Ticket notifications |
| | [Modules/portal](Modules/portal.md) — Customer portal tickets |

---

## Tier 3 — Supporting

*Specialist modules that support core operations.*

### Product

| Item | Details |
|------|---------|
| **Module** | `product` |
| **Documentation** | [Modules/Product](Modules/Product.md) |
| **What it does** | Product templates, variants, pricelists, routes |
| **Key Sub-Modules** | [Modules/product_margin](Modules/product_margin.md) — Margin analysis |
| | [Modules/product_expiry](Modules/product_expiry.md) — Lot expiry tracking |
| | [Modules/product_matrix](Modules/product_matrix.md) — Grid product configurator |

---

### Quality

| Item | Details |
|------|---------|
| **Module** | `quality` |
| **Documentation** | [Modules/quality](Modules/quality.md) |
| **What it does** | Quality checks, control points, alerts |
| **Related Modules** | [Modules/stock](Modules/stock.md) — QC on receipts |
| | [Modules/mrp](Modules/mrp.md) — QC on production |

---

## Tier 4 — Advanced

*Advanced modules for developers, IT, and specialized business needs.*

### Website / E-Commerce

| Item | Details |
|------|---------|
| **Module** | `website` |
| **Documentation** | [Modules/website](Modules/website.md) |
| **What it does** | Website builder, CMS, SEO |
| **Key Sub-Modules** | [Modules/website_sale](Modules/website_sale.md) — E-commerce shop |
| | [Modules/website_sale_stock](Modules/website_sale_stock.md) — Inventory sync to web |
| | [Modules/website_slides](Modules/website_slides.md) — Course/knowledge platform |
| | [Modules/website_payment](Modules/website_payment.md) — Online payments |
| | [Modules/website_crm](Modules/website_crm.md) — Website lead capture |

---

### IoT — Hardware

| Item | Details |
|------|---------|
| **Module** | `iot_base` + `iot_drivers` |
| **Documentation** | [Modules/iot](Modules/iot.md) |
| **What it does** | IoT box and device management |
| **Device Types** | Receipt printers, barcode scanners, scales, displays |
| **Related Modules** | [Modules/Stock](Modules/Stock.md) — Barcode scanner integration |
| | [Modules/POS](Modules/POS.md) — Receipt printer integration |

---

### Studio — No-Code Builder

| Item | Details |
|------|---------|
| **Module** | `studio` (part of `web`) |
| **Documentation** | [Modules/studio](Modules/studio.md) |
| **What it does** | Visual app builder, custom models/fields/views |
| **Audience** | Power users, functional consultants |
| **Note** | Enterprise only |

---

### Knowledge — Wiki

| Item | Details |
|------|---------|
| **Module** | `knowledge` |
| **Documentation** | [Modules/knowledge](Modules/knowledge.md) |
| **What it does** | Internal wiki, articles, collaborative writing |
| **Related Modules** | [Modules/mail](Modules/mail.md) — Article comment threads |
| | [Modules/mail](Modules/mail.md) — Workspace channels |

---

### Rental / Asset Lease

| Item | Details |
|------|---------|
| **Module** | `rental` |
| **Documentation** | [Modules/rental](Modules/rental.md) |
| **What it does** | Equipment rental, contracts, pickup/return |
| **Related Modules** | [Modules/Sale](Modules/Sale.md) — Rental quotations |
| | [Modules/Stock](Modules/Stock.md) — Rental inventory |
| | [Modules/Fleet](Modules/Fleet.md) — Vehicle rental |

---

## Utilities

*Foundation modules that everything else depends on.*

### Base

| Item | Details |
|------|---------|
| **Module** | `base` |
| **Documentation** | [Modules/base_setup](Modules/base_setup.md) |
| **What it does** | Company, user, currency, locale, sequence defaults |
| **Key Sub-Modules** | [Modules/base_vat](Modules/base_vat.md) — VAT/TAX ID validation |
| | [Modules/base_iban](Modules/base_iban.md) — IBAN bank account support |
| | [Modules/base_address_extended](Modules/base_address_extended.md) — Address formatting |
| | [Modules/base_geolocalize](Modules/base_geolocalize.md) — GPS geolocation |

---

### Mail

| Item | Details |
|------|---------|
| **Module** | `mail` |
| **Documentation** | [Modules/mail](Modules/mail.md) |
| **What it does** | Email, messaging, mail templates, follow/unfollow |
| **Key Sub-Modules** | [Modules/mail_group](Modules/mail_group.md) — Group messaging |
| | [Modules/mail_plugin](Modules/mail_plugin.md) — Email plugin |
| **Related Modules** | [Modules/portal](Modules/portal.md) — Customer portal messaging |

---

### Resource

| Item | Details |
|------|---------|
| **Module** | `resource` |
| **Documentation** | [Modules/resource](Modules/resource.md) |
| **What it does** | Working hours, calendars, resource planning |
| **Related Modules** | [Modules/HR](Modules/HR.md) — Employee scheduling |
| | [Modules/calendar](Modules/calendar.md) — Meetings and scheduling |

---

### Calendar

| Item | Details |
|------|---------|
| **Module** | `calendar` |
| **Documentation** | [Modules/calendar](Modules/calendar.md) |
| **What it does** | Meeting scheduling, reminders, calendar views |
| **Key Sub-Modules** | [Modules/calendar_sms](Modules/calendar_sms.md) — SMS reminders |
| | [Modules/microsoft_calendar](Modules/microsoft_calendar.md) — Outlook sync |

---

## All Modules Index

> A complete alphabetical index of all module documentation files in this vault.

### A

| Module | File | Category |
|--------|------|----------|
| account | [Modules/Account](Modules/Account.md) | Tier 1 — Accounting |
| account_fleet | [Modules/account_fleet](Modules/account_fleet.md) | Accounting extension |
| account_payment | [Modules/account_payment](Modules/account_payment.md) | Payment processing |
| account_peppol | [Modules/account_peppol](Modules/account_peppol.md) | Peppol EDI |
| account_edi | [Modules/account_edi](Modules/account_edi.md) | EDI framework |
| analytic | [Modules/analytic](Modules/analytic.md) | Analytic accounting |
| auth_* | Multiple | Authentication modules |
| availability | — | (part of stock) |

### B–C

| Module | File | Category |
|--------|------|----------|
| barcodes | [Modules/barcodes](Modules/barcodes.md) | Barcode scanning |
| board | [Modules/board](Modules/board.md) | Dashboard kanban |
| bus | [Modules/bus](Modules/bus.md) | Real-time bus |
| calendar | [Modules/calendar](Modules/calendar.md) | Utility — Scheduling |
| contacts | [Modules/contacts](Modules/contacts.md) | Contact management |
| crm | [Modules/CRM](Modules/CRM.md) | Tier 2 — CRM |

### D–F

| Module | File | Category |
|--------|------|----------|
| delivery | [Modules/delivery](Modules/delivery.md) | Shipping methods |
| digest | [Modules/digest](Modules/digest.md) | KPI dashboards |
| event | [Modules/event](Modules/event.md) | Event management |
| fleet | [Modules/fleet](Modules/fleet.md) | Vehicle fleet |

### G–H

| Module | File | Category |
|--------|------|----------|
| gamification | [Modules/gamification](Modules/gamification.md) | Challenges & badges |
| google_* | Multiple | Google integrations |
| helpdesk | [Modules/helpdesk](Modules/helpdesk.md) | Tier 2 — Helpdesk |
| hr | [Modules/HR](Modules/HR.md) | Tier 1 — HR |
| hr_holidays | [Modules/hr_holidays](Modules/hr_holidays.md) | Leave management |
| hr_attendance | [Modules/hr_attendance](Modules/hr_attendance.md) | Attendance |

### I–K

| Module | File | Category |
|--------|------|----------|
| iot | [Modules/iot](Modules/iot.md) | Tier 4 — IoT |
| knowledge | [Modules/knowledge](Modules/knowledge.md) | Tier 4 — Wiki |

### L–M

| Module | File | Category |
|--------|------|----------|
| l10n_* | [Modules/l10n_id](Modules/l10n_id.md) and 80+ others | Country localizations |
| loyalty | [Modules/loyalty](Modules/loyalty.md) | Loyalty programs |
| mail | [Modules/mail](Modules/mail.md) | Utility — Email |
| mass_mailing | [Modules/mass_mailing](Modules/mass_mailing.md) | Email campaigns |
| mrp | [Modules/MRP](Modules/MRP.md) | Tier 2 — Manufacturing |

### N–P

| Module | File | Category |
|--------|------|----------|
| note | (note module) | Sticky notes |
| payment | [Modules/payment](Modules/payment.md) | Payment provider framework |
| point_of_sale | [Modules/POS](Modules/POS.md) | Tier 2 — POS |
| portal | [Modules/portal](Modules/portal.md) | Customer portal |
| product | [Modules/Product](Modules/Product.md) | Tier 3 — Product |
| project | [Modules/Project](Modules/Project.md) | Tier 2 — Project |

### Q–R

| Module | File | Category |
|--------|------|----------|
| quality | [Modules/quality](Modules/quality.md) | Tier 3 — Quality |
| rental | [Modules/rental](Modules/rental.md) | Tier 4 — Rental |
| repair | [Modules/repair](Modules/repair.md) | After-sale repair |
| resource | [Modules/resource](Modules/resource.md) | Utility — Resource |

### S

| Module | File | Category |
|--------|------|----------|
| sale | [Modules/Sale](Modules/Sale.md) | Tier 1 — Sales |
| sale_management | [Modules/sale_management](Modules/sale_management.md) | Sales extension |
| sale_timesheet | [Modules/sale_timesheet](Modules/sale_timesheet.md) | Time billing |
| sale_loyalty | [Modules/sale_loyalty](Modules/sale_loyalty.md) | Loyalty |
| sale_project | [Modules/sale_project](Modules/sale_project.md) | Project billing |
| sale_stock | [Modules/sale_stock](Modules/sale_stock.md) | Sale↔Stock integration |
| sms | [Modules/sms](Modules/sms.md) | SMS gateway |
| spreadsheet | [Modules/spreadsheet](Modules/spreadsheet.md) | Spreadsheet engine |
| stock | [Modules/Stock](Modules/Stock.md) | Tier 1 — Inventory |
| stock_account | [Modules/stock_account](Modules/stock_account.md) | Inventory valuation |
| studio | [Modules/studio](Modules/studio.md) | Tier 4 — App Builder |

### T–W

| Module | File | Category |
|--------|------|----------|
| test_* | Multiple | Test modules (ignore) |
| uom | [Modules/uom](Modules/uom.md) | Unit of measure |
| utm | [Modules/utm](Modules/utm.md) | Marketing tracking |
| web | [Modules/web](Modules/web.md) | Web framework |
| website | [Modules/website](Modules/website.md) | Tier 4 — Website |
| website_sale | [Modules/website_sale](Modules/website_sale.md) | E-commerce |
| website_slides | [Modules/website_slides](Modules/website_slides.md) | E-learning |

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

See [Modules/l10n_id](Modules/l10n_id.md) for full Indonesian example. See [Modules/l10n_de](Modules/l10n_de.md), [Modules/l10n_us](Modules/l10n_us.md), [Modules/l10n_fr](Modules/l10n_fr.md) for quick-access versions.

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| Guide | [Documentation/Upgrade-Plan/CHECKPOINT-master](Documentation/Upgrade-Plan/CHECKPOINT-master.md) | Coverage progress tracker |
| Guide | [Tools/Modules Inventory](Tools/Modules-Inventory.md) | Full module catalog |
| Pattern | [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) | Cross-module flow design |
| Snippet | [Snippets/Model Snippets](Snippets/Model-Snippets.md) | Code templates |
| Core | [Core/BaseModel](Core/BaseModel.md) | ORM foundation |
