# Modules Inventory

Daftar semua module yang tersedia di Odoo 15 Community Edition.
Source: `/addons/` directory

## Module Categories

### Core / System Modules

| Module | Description |
|---|---|
| `base` | Core functionality, res.partner, res.users, ir.model |
| `board` | Dashboard view |
| `bus` | Bus/notification system |
| `calendar` | Calendar events |
| `digest` | Periodic email digests |
| `fetchmail` | Email fetching (IMAP/POP) |
| `google_account` | Google integration |
| `microsoft_account` | Microsoft integration |
| `web` | Web client core |
| `web_editor` | WYSIWYG editor |
| `web_tour` | Interactive tours |
| `web_unsplash` | Unsplash image integration |

### Address & Localization

| Module | Description |
|---|---|
| `base_address_city` | City/state on address |
| `base_address_extended` | Extended address fields |
| `base_iban` | IBAN validation |
| `base_vat` | VAT number validation |
| `base_geolocalize` | Geo-location |
| `l10n_*` | Country-specific localization (30+ modules) |

### Authentication

| Module | Description |
|---|---|
| `auth_ldap` | LDAP authentication |
| `auth_oauth` | OAuth providers (Google, etc.) |
| `auth_signup` | User registration/signup |
| `auth_totp` | Time-based OTP (2FA) |
| `auth_totp_mail` | OTP via email |
| `auth_totp_portal` | OTP for portal users |
| `auth_password_policy` | Password strength policy |

### Base Functionality

| Module | Description |
|---|---|
| `base_import` | CSV/Excel import |
| `base_import_module` | Module import |
| `base_sparse_field` | Sparse field type |
| `base_setup` | Initial setup wizard |
| `base_automation` | Automated actions |
| `attachment_indexation` | File indexing for search |

### Marketing

| Module | Description |
|---|---|
| `mass_mailing` | Email marketing |
| `mass_mailing_event` | Event email |
| `mass_mailing_crm` | CRM email marketing |
| `mass_mailing_slides` | E-learning email |
| `crm_iap_enrich` | Lead enrichment (paid) |
| `crm_iap_mine` | Lead mining |
| `marketing_crm` | Marketing automation |

### CRM

| Module | Description |
|---|---|
| `crm` | Core CRM (leads, opportunities) |
| `crm_livechat` | Live chat leads |
| `crm_mail_plugin` | Email integration |
| `crm_sms` | SMS integration |

### Sale

| Module | Description |
|---|---|
| `sale` | Quotations, Sales Orders |
| `sale_management` | Sale agreements, report |
| `sale_product_matrix` | Grid product configuration |
| `sale_project` | Sale + Project integration |
| `sale_quotation_builder` | Quotation template builder |
| `sale_stock` | Sale + Stock delivery |
| `sale_timesheet` | Time tracking in sale |

### Purchase

| Module | Description |
|---|---|
| `purchase` | Purchase orders, RFQs |
| `purchase_requisition` | Purchase agreements |
| `purchase_product_matrix` | Product matrix |

### Stock / Inventory

| Module | Description |
|---|---|
| `stock` | Warehouse management |
| `stock_account` | Stock valuation |
| `stock_landed_costs` | Landed cost allocation |
| `stock_picking_batch` | Batch picking |
| `stock_scrap` | Scrap management |
| `mrp_subcontracting` | Subcontracting |

### Manufacturing (MRP)

| Module | Description |
|---|---|
| `mrp` | Manufacturing orders, BoM |
| `mrp_account` | MRP cost accounting |
| `mrp_product_expiry` | Product expiry tracking |
| `mrp_repair` | Repair orders |
| `mrp_subcontracting` | Subcontracting |
| `mrp_workorder` | Work orders |

### Accounting

| Module | Description |
|---|---|
| `account` | Core accounting, invoices, journal entries |
| `account_accountant` | Accounting full features |
| `account_asset` | Asset management |
| `account_budget` | Budget management |
| `account_check_printing` | Check printing |
| `account_debit_note` | Debit notes |
| `account_fleet` | Fleet expenses |
| `account_payment` | Payment providers |
| `account_qr_code_sepa` | SEPA QR codes |
| `account_sales_reports` | Sales reports |
| `account_tax_python` | Python tax computation |

### E-commerce / Website

| Module | Description |
|---|---|
| `website` | Website builder |
| `website_blog` | Blog |
| `website_crm` | Website lead capture |
| `website_event` | Events |
| `website_event_sale` | Event tickets |
| `website_forum` | Forum |
| `website_livechat` | Live chat |
| `website_mail` | Website mail |
| `website_mass_mailing` | Mass mailing |
| `website_profile` | User profiles |
| `website_sale` | eCommerce |
| `website_sale_comparison` | Product comparison |
| `website_sale_delivery` | Delivery methods |
| `website_sale_product_configurator` | Product configurator |
| `website_slides` | E-learning |
| `website_social` | Social media |

### Project & Timesheet

| Module | Description |
|---|---|
| `project` | Project management |
| `project_forecast` | Resource forecasting |
| `project_timesheet` | Time tracking |
| `project_purchase` | Project + Purchase |
| `sale_timesheet` | Billable time |
| `hr_timesheet` | Employee timesheet |

### Human Resources

| Module | Description |
|---|---|
| `hr` | Employees, departments |
| `hr_attendance` | Attendance tracking |
| `hr_contract` | Contracts |
| `hr_expense` | Expense claims |
| `hr_holidays` | Leave management |
| `hr_recruitment` | Recruitment |
| `hr_skills` | Skills management |
| `hr_work_entry` | Work entries |

### Messaging & Communication

| Module | Description |
|---|---|
| `mail` | Email, messaging, channels |
| `mail_bot` | Mail bot |
| `mail_group` | Mail groups |
| `mail_plugin` | Email plugins |

### SMS & Phone

| Module | Description |
|---|---|
| `sms` | SMS sending |
| `phone` | VoIP telephony |
| `phone_blacklist` | Phone number blacklist |

### Events

| Module | Description |
|---|---|
| `event` | Event management |
| `event_booth` | Booth management |
| `event_sale` | Ticket sales |
| `event_booth_sale` | Booth reservations |

### Loyalty & Coupons

| Module | Description |
|---|---|
| `loyalty` | Loyalty programs |
| `loyalty_giftcard` | Gift cards |
| `loyalty_coupon` | Coupons |
| `coupon` | Promotional coupons |

### Point of Sale

| Module | Description |
|---|---|
| `point_of_sale` | POS terminal |
| `pos_restaurant` | Restaurant POS |
| `pos_blackbox_be` | Belgian black box |

### Spreadsheet

| Module | Description |
|---|---|
| `spreadsheet` | Spreadsheet engine |
| `spreadsheet_account` | Accounting charts |

### Documents

| Module | Description |
|---|---|
| `documents` | Document management |
| `documents_hr` | HR documents |
| `documents_project` | Project documents |

### Approvals

| Module | Description |
|---|---|
| `approval` | Approval workflow |
| `approval_routing` | Multi-level approval |

### Quality

| Module | Description |
|---|---|
| `quality` | Quality control |
| `quality_mrp` | MRP quality checks |

### Maintenance

| Module | Description |
|---|---|
| `maintenance` | Equipment maintenance |

### Timesheet & Planning

| Module | Description |
|---|---|
| `planning` | Resource planning |

### Helpdesk

| Module | Description |
|---|---|
| `helpdesk` | Helpdesk/ticket system |

## See Also
- [[Modules/Sale]] — Sale order models
- [[Modules/Stock]] — Stock models
- [[Modules/Account]] — Accounting models
- [[Modules/Project]] — Project models