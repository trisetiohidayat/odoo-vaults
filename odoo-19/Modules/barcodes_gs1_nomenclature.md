---
title: "Barcodes Gs1 Nomenclature"
module: barcodes_gs1_nomenclature
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Barcodes Gs1 Nomenclature

## Overview

Module `barcodes_gs1_nomenclature` — auto-generated from source code.

**Source:** `addons/barcodes_gs1_nomenclature/`
**Models:** 3
**Fields:** 9
**Methods:** 5

## Models

### barcode.nomenclature (`barcode.nomenclature`)

Converts a GS1 date into a datetime.date.

        :param gs1_date: A year formated as yymmdd
        :type gs1_date: str
        :return: converted date
        :rtype: datetime.date

**File:** `barcode_nomenclature.py` | Class: `BarcodeNomenclature`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `is_gs1_nomenclature` | `Boolean` | — | — | — | — | — |
| `gs1_separator_fnc1` | `Char` | — | — | Y | — | — |
| `domain` | `Domain` | — | — | — | — | — |


#### Methods (4)

| Method | Description |
|--------|-------------|
| `gs1_date_to_date` | |
| `parse_gs1_rule_pattern` | |
| `gs1_decompose_extended` | |
| `parse_nomenclature_barcode` | |


### barcode.rule (`barcode.rule`)

—

**File:** `barcode_rule.py` | Class: `BarcodeRule`

#### Fields (6)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `encoding` | `Selection` | — | — | — | — | — |
| `type` | `Selection` | — | — | — | — | — |
| `is_gs1_nomenclature` | `Boolean` | — | — | Y | — | — |
| `gs1_content_type` | `Selection` | — | — | — | — | — |
| `gs1_decimal_usage` | `Boolean` | — | — | — | — | — |
| `associated_uom_id` | `Many2one` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### ir.http (`ir.http`)

—

**File:** `ir_http.py` | Class: `IrHttp`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `session_info` | |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
