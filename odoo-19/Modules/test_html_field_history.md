# Test HTML Field History (`test_html_field_history`)

**Category:** Hidden
**Depends:** `html_editor`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Test module for the HTML field history/audit trail feature (part of [Modules/html_builder](Modules/html_builder.md)/[Modules/html_editor](Modules/html_editor.md)). Provides a test model with versioned HTML fields to verify that the HTML editor's versioning system correctly tracks and restores prior versions of rich-text fields.

## Models

### `html.field.history.test`
**Fields:** `name`, `description` (HTML versioned field)

**Methods:**
- `_get_versioned_fields()` — Declares which fields are versioned. Returns `['description']`.

## Related

This module tests the versioning system used by the HTML editor for collaborative editing history and audit trails.
