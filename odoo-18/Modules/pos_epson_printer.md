---
Module: pos_epson_printer
Version: 18.0.0
Type: addon
Tags: #odoo18 #pos_epson_printer #printer #epson #epos #iot
---

## Overview

Enables Epson ePOS printers (TM series, TM-mobile, TM-T88, etc.) as POS receipt printers. Supports both IP address and serial-number-based (wildcard certificate) connections. Also supports Epson TM-T20, TM-T82II, TM-T88V, TM-T100.

**Depends:** `point_of_sale`

---

## Models

### `pos.printer` (Extension)
**Inheritance:** `pos.printer`

| Field | Type | Notes |
|---|---|---|
| `printer_type` | Selection (extends) | Adds `('epson_epos', 'Use an Epson printer')` |
| `epson_printer_ip` | Char | IP address or serial number, default '0.0.0.0' |

**Methods:**
- `_load_pos_data_fields(config_id)` -> adds `'epson_printer_ip'`
- `_constrains_epson_printer_ip()` -> `@api.constrains`: raises ValidationError if `printer_type='epson_epos'` and `epson_printer_ip` empty
- `_onchange_epson_printer_ip()` -> calls `format_epson_certified_domain(epson_printer_ip)` to transform serial number to domain name

---

### `pos.config` (Extension)
**Inheritance:** `pos.config`

| Field | Type | Notes |
|---|---|---|
| `epson_printer_ip` | Char | Local IP or serial number |

**Methods:**
- `_onchange_epson_printer_ip()` -> delegates to `format_epson_certified_domain`

---

### `res.config.settings` (Extension)
**Inheritance:** `res.config.settings`

| Field | Type | Notes |
|---|---|---|
| `pos_epson_printer_ip` | Char (compute+store) | Related to `pos_config_id.epson_printer_ip` |

**Methods:**
- `_compute_pos_iface_cashdrawer()` -> adds depends for cashdrawer display when epson_printer_ip is set
- `_is_cashdrawer_displayed(res_config)` -> True if parent says so OR (`pos_other_devices` AND `epson_printer_ip` set)
- `_compute_pos_epson_printer_ip()` -> syncs from `pos_config_id.epson_printer_ip`
- `_onchange_epson_printer_ip()` -> formats the IP/serial using `format_epson_certified_domain`

---

## Security / Data

No security files. No data files.

---

## Critical Notes

1. **Serial number -> domain conversion:** When a printer serial number (not IP) is provided, `format_epson_certified_domain` converts it to a domain name using SHA256+base32 hashing. This maps to the printer's wildcard TLS certificate from Epson (`*.omnilinkcert.epson.biz`). Example: serial `ABC123` -> `j6b5...abc123.omnilinkcert.epson.biz`. This allows TLS authentication without manually installing certificates per printer.

2. **`format_epson_certified_domain` algorithm:**
   - SHA256 hash of serial number
   - Base32 encode, strip padding
   - Lowercase
   - Prepend to `omnilinkcert.epson.biz`
   - If input contains a `.`, treat as IP address and return unchanged

3. **Printer type selection:** `pos.printer` gets the new `epson_epos` printer type. Multiple printers can be configured — both Epson and other types simultaneously.

4. **JS assets:** The actual printer communication (ePOS SDK JavaScript) is in `static/src/app/epson_printer.js` and `static/src/app/components/epos_templates.xml`. The Python models only provide field storage and formatting.