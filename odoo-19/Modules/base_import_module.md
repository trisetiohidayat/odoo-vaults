---
title: "Base Import Module"
module: base_import_module
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Base Import Module

## Overview

Module `base_import_module` — auto-generated from source code.

**Source:** `addons/base_import_module/`
**Models:** 4
**Fields:** 10
**Methods:** 10

## Models

### base.import.module (`base.import.module`)

Import Module

**File:** `base_import_module.py` | Class: `BaseImportModule`

#### Fields (7)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `module_file` | `Binary` | — | — | — | — | Y |
| `state` | `Selection` | — | — | — | — | — |
| `import_message` | `Text` | — | — | — | — | — |
| `force` | `Boolean` | — | — | — | — | — |
| `with_demo` | `Boolean` | — | — | — | — | — |
| `modules_dependencies` | `Text` | — | — | — | — | — |
| `fp` | `BytesIO` | — | — | — | — | — |


#### Methods (3)

| Method | Description |
|--------|-------------|
| `import_module` | |
| `get_dependencies_to_install_names` | |
| `action_module_open` | |


### ir.http (`ir.http`)

—

**File:** `ir_http.py` | Class: `IrHttp`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### ir.module.module (`ir.module.module`)

SELECT ia.id
                FROM ir_attachment ia
                JOIN ir_model_data imd
                ON ia.id = imd.res_id
                AND imd.model = 'ir.attachment'
                AND imd.

**File:** `ir_module.py` | Class: `IrModuleModule`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `imported` | `Boolean` | — | — | — | — | — |
| `module_type` | `Selection` | — | — | — | — | — |
| `translation_importer` | `TranslationImporter` | — | — | — | — | — |


#### Methods (7)

| Method | Description |
|--------|-------------|
| `module_uninstall` | |
| `web_search_read` | |
| `more_info` | |
| `web_read` | |
| `button_upgrade` | |
| `button_immediate_install_app` | |
| `search_panel_select_range` | |


### ir.ui.view (`ir.ui.view`)

SELECT max(v.id)
               FROM ir_ui_view v
          LEFT JOIN ir_model_data md ON (md.model = 'ir.ui.view' AND md.res_id = v.id)
          LEFT JOIN ir_module_module m ON (m.name = md.module)


**File:** `ir_ui_view.py` | Class: `IrUiView`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [[Modules/Base]]
- [[Modules/Base]]
