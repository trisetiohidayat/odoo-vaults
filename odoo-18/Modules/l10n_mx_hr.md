---
Module: l10n_mx_hr
Version: 18.0
Type: l10n/mexico-hr
Tags: #odoo18 #l10n #accounting #mexico #hr
---

# l10n_mx_hr — Mexico Employees

## Overview
Mexico-specific HR module adding CURP (Clave Unica de Registro de Poblacion) and RFC (Registro Federal de Contribuyentes) fields to the employee form. These are mandatory fields for Mexican payroll compliance and NÓMINA Cfdi (payroll electronic invoice).

## Country/Region
Mexico (MX)

## Dependencies
- hr

## Key Models

### `hr.employee` (Extended)
Inherits: `hr.employee`
Added fields:
- `l10n_mx_curp` (Char): CURP — 18-character unique identity number for Mexican citizens
- `l10n_mx_rfc` (Char): RFC — Federal taxpayer registry number

Both fields are restricted to `hr.group_hr_user` group and have `tracking=True`.

## Data Files
- `views/hr_employee_views.xml`: CURP and RFC fields on employee form
- `data/l10n_mx_hr_demo.xml`: Demo employee data with CURP/RFC

## Installation
Install with HR. Fields appear on employee form for users in HR group.

## Historical Notes
New in Odoo 18 as a dedicated Mexico HR module. CURP and RFC are required for NÓMINA Cfdi (payroll receipts), which Mexico mandated for electronic payroll since 2019. The separate module allows non-Mexican companies using the HR app to avoid loading these fields.
