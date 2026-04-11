# Test Import Export (`test_import_export`)

**Category:** Hidden
**Depends:** `web`, `base_import`, `website`
**Installable:** True
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Test module for Odoo's import and export functionality. Provides test models exercising various field types (relational fields, computed fields, recursive O2M, inheritance chains) to verify the robustness of the import/export engine.

## Models

### `export.aggregator` — O2M parent model
**Fields:** `name`, `child_ids` (O2M to `export.aggregator.one2many`)

### `export.aggregator.one2many` / `export.aggregator.admin.only` — Child models

### `export.one2many.child` — Simple O2M child
**Fields:** `name`, `parent_id`

### `export.one2many.multiple` — Multiple O2M children
**Fields:** `name`, `child1_ids`, `child2_ids`

### `export.one2many.multiple.child` — Child of multiple O2M
**Methods:**
- `_compute_display_name()` — Computed name field.

### `export.one2many.recursive` — Recursive O2M (parent_id self-reference)
Tests import of hierarchical/self-referencing structures.

### `export.many2many.other` — M2M test model
**Fields:** `name`, `tag_ids` (M2M)

### `export.selection.with.default` — Selection field with default

### `export.unique` — Unique constraint test model
**Fields:** `name` (Char, unique), `value`

### `export.inherits.parent` / `export.inherits.child` — Inheritance test
Tests import of `/_inherits` delegated records (stored in parent table via foreign key).

### `export.m2o.str` / `export.m2o.str.child` — M2O with stored name
Tests importing Many2one by name string when the related record name is stored.

### `export.with.required.field` — Required field test model
**Fields:** `name`, `required_field` (Char, required)

### `export.many2one.required.subfield` — M2O required subfield test

### `with.non.demo.constraint` — Constraint test model
**Methods:**
- `_check_name_starts_with_uppercase_except_demo_data()` — SQL constraint validation.

### Import Test Models (`models_import.py`)

- `import.char` / `import.char.required` / `import.char.readonly` / `import.char.noreadonly` / `import.char.stillreadonly` — Character field import variants
- `import.m2o` / `import.m2o.related` / `import.m2o.required` / `import.m2o.required.related` — Many2one import variants
- `import.o2m` / `import.o2m.child` — One2many import
- `import.preview` — Import preview model
- `import.float` — Float field import
- `import.complex` — Complex multi-field import
- `import.properties.definition` / `import.properties` / `property.inherits` / `path.to.property` — Property field import tests

### Helper Functions

- `selection_fn(records)` — Selection field value generator for tests
- `compute_fn(records)` — Computed field generator
- `inverse_fn(records)` — Inverse computed field
- `generic_compute_display_name(self)` / `generic_search_display_name(operator, value)` — Generic name field accessor/search

## Data

- `security/ir.model.access.csv` — Access rights for import/export test models
