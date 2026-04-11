---
Module: l10n_mt_pos
Version: 1.0
Type: l10n/malta/pos
Tags: #odoo18 #l10n #malta #pos #exo-number #compliance
---

# l10n_mt_pos

## Overview
Malta POS compliance module. Generates and attaches a "Compliance Letter" (EXO Number certificate) to Point of Sale receipts. The EXO (Exempt Organisation) Number is issued by the Maltese Commissioner for Revenue and is required on receipts for VAT-exempt or special-category transactions in Malta. The module also provides a wizard to generate and preview the compliance letter.

## Country
Malta

## Dependencies
- `point_of_sale` (Point of Sale application)

## Key Models
No Python models. Module is primarily XML views, wizards, and report definitions.

## Data Files
- `wizards/compliance_letter_view.xml` -- Wizard form to generate and preview compliance letter
- `reports/compliance_letter_report.xml` -- QWeb report for the compliance letter (EXO Number certificate)
- `security/ir.model.access.csv` -- Access rights for compliance letter wizard

## Compliance Letter (EXO Number)
The EXO Number is a unique identifier assigned by the Maltese tax authority (CfR) to vendors making exempt supplies. The compliance letter attached to POS receipts includes:
- Trader name and VAT number
- EXO Number issued by CfR
- Date of issue
- Description of exempt supplies on the receipt
- Reference to Legal Notice (LN 294/2013)

## Installation
Auto-installs when `point_of_sale` is installed and the company country is Malta. Requires Malta VAT number configured on the company.

## Historical Notes
- Odoo 18: New module
- Malta's special-category transactions (exempt supplies, Tour Operator Margin Scheme) require EXO Number documentation per EU VAT Directive 2006/112/EC and Maltese VAT Act (Cap. 406)
