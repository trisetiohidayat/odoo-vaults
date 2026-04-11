---
Module: l10n_jo_edi_extended
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #jordan #jofotara
---

# l10n_jo_edi_extended

## Overview
Extends [[Modules/l10n_jo_edi]] with additional JoFotara features:
1. Support for additional **invoice types** and **payment methods**
2. **Demo mode** for testing without live JoFotara API
3. Enhanced partner and configuration options

## EDI Format / Standard
Same as [[Modules/l10n_jo_edi]] — UBL 2.1 JoFotara profile.

## Dependencies
- `l10n_jo_edi` — Base Jordanian EDI module

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountMove` | `account.move` | `account.move` | Extended invoice type and payment method fields for JoFotara |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Extended send wizard with demo mode support |
| `ResCompany` | `res.company` | `res.company` | Demo mode flag and extended configuration |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings with demo mode toggle |

## Data Files
- `views/account_move_views.xml` — Extended move form views
- `views/res_config_settings_views.xml` — Extended settings form
- `demo/demo_company.xml` — Demo company for testing

## How It Works

### Invoice Types
Extends the base JoFotara invoice type handling with additional document types as supported by the platform.

### Payment Methods
Adds payment method codes beyond the basic UBL payment means, mapped to JoFotara requirements.

### Demo Mode
When demo mode is enabled:
- API calls are simulated (not sent to live JoFotara)
- Invoice XML is still generated correctly
- User can test full workflow without live credentials
- Useful for training and development environments

## Installation
Auto-installs with `l10n_jo_edi`. No separate activation needed.

## Historical Notes
- **Odoo 18**: New module added alongside the base `l10n_jo_edi` to allow incremental feature activation