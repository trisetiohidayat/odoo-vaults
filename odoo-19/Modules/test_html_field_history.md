---
type: module
module: test_html_field_history
tags: [odoo, odoo19, test, html_editor, html_field_history, revision, audit-trail]
created: 2026-04-06
---

# Test HTML Field History

## Overview

| Property | Value |
|----------|-------|
| **Name** | Test HTML Field History |
| **Technical** | `test_html_field_history` |
| **Category** | Hidden (Test Module) |
| **Depends** | `html_editor` |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Description

Test module for the HTML field history/audit trail feature (part of the `html_editor` framework). Provides a test model with versioned HTML fields to verify that the HTML editor's versioning system correctly tracks and restores prior versions of rich-text fields.

This module is **test-only** and is not installed in production databases. It validates the behavior of `html.field.history.mixin` — the mixin that powers collaborative editing history and audit trails for `Html` fields.

## Module Structure

```
test_html_field_history/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── model_html_field_history_test.py   # Test model definition
└── tests/
    ├── __init__.py
    └── test_model.py                      # Unit tests
```

## Models

### `html.field.history.test`

A minimal test model that inherits from `html.field.history.mixin`. Used exclusively to test the history tracking behavior without coupling to any real business model.

**File:** `models/model_html_field_history_test.py`

```python
class HtmlFieldHistoryTest(models.Model):
    _name = 'html.field.history.test'
    _description = "Test html_field_history Model"
    _inherit = ["html.field.history.mixin"]

    def _get_versioned_fields(self):
        return [
            HtmlFieldHistoryTest.versioned_field_1.name,
            HtmlFieldHistoryTest.versioned_field_2.name,
        ]

    versioned_field_1 = fields.Html(string="vf1")
    versioned_field_2 = fields.Html(string="vf2", sanitize=False)
```

**Design Notes:**

- Two versioned fields are declared: `versioned_field_1` (sanitized) and `versioned_field_2` (non-sanitized)
- `_get_versioned_fields()` returns the field names that should be tracked
- `versioned_field_1` has `sanitize=True` (default for `Html`), meaning the mixin enforces that revisions can only be stored for sanitized HTML
- `versioned_field_2` has `sanitize=False`, which triggers a `ValidationError` if the mixin attempts to version it (since the mixin requires `sanitize=True`)

### `html.field.history.mixin`

This is the mixin being tested, provided by the `html_editor` module. It provides:

| Attribute/Method | Description |
|-----------------|-------------|
| `html_field_history` | Computed field (Json) — stores revision records per versioned field |
| `html_field_history_metadata` | Computed field (Json) — stores metadata (count, latest) per field |
| `_get_versioned_fields()` | Abstract method — subclasses must override to declare tracked fields |
| `_update_html_field_history()` | Called on write — creates revision entries when field value changes |

**Revision Data Structure:**

```python
# Example html_field_history structure for one field:
{
    "versioned_field_1": [
        {
            "id": <revision_id>,
            "date": <datetime>,
            "patch": <string>,  # JSON Patch (RFC 6902) from previous value
            "value": <string>,  # Full sanitized HTML at this revision
            "user_id": <user_id>,
        },
        # ... more revisions
    ]
}
```

**Metadata Structure:**

```python
# Example html_field_history_metadata structure:
{
    "versioned_field_1": [
        {
            "id": <revision_id>,
            "date": <datetime>,
            "user_id": <user_id>,
            "field": "versioned_field_1",
        }
    ]
}
```

## Tests

**File:** `tests/test_model.py`

### Test Cases

#### `test_html_field_history_write`

Tests basic revision creation on write operations.

```python
def test_html_field_history_write(self):
    # 1. Create record — no revision should be generated
    rec1 = self.env["html.field.history.test"].create({
        "versioned_field_1": "mock content",
    })
    assert rec1.html_field_history == False, "Record creation should not generate revisions"
    assert rec1.html_field_history_metadata == False, "No metadata without revisions"

    # 2. Write new value — creates exactly 1 revision
    rec1.write({"versioned_field_1": "mock content 2"})
    assert len(rec1.html_field_history["versioned_field_1"]) == 1
    assert len(rec1.html_field_history_metadata["versioned_field_1"]) == 1
    assert rec1.versioned_field_1 == "<p>mock content 2</p>"  # auto-p wrapped

    # 3. Write None — creates a revision (tracks the change to empty)
    rec1.write({"versioned_field_1": None})
    assert len(rec1.html_field_history["versioned_field_1"]) == 3

    # 4. Non-versioned field has no history
    assert rec1.html_field_history["versioned_field_2"] == False
```

**Assertions verified:**
- Creation does NOT generate a revision (only writes do)
- Each write to a versioned field creates a new revision entry
- The JSON Patch (`patch` field) contains an RFC 6902 patch from previous value
- Sanitized fields auto-wrap plain text in `<p>` tags
- Non-versioned fields are excluded from history

#### `test_html_field_history_batch_write`

Tests that batch `write()` on multiple records creates one revision per record.

```python
def test_html_field_history_batch_write(self):
    rec1 = self.env["html.field.history.test"].create({
        "versioned_field_1": 'rec1 initial content',
        "versioned_field_2": 'text',
    })
    rec2 = self.env["html.field.history.test"].create({
        "versioned_field_1": 'rec2 initial value',
    })

    # Batch write on two records
    (rec1 + rec2).write({
        "versioned_field_1": "field has been batch overwritten",
    })

    # rec1: has history, sanitized, non-versioned field unchanged
    assert len(rec1.html_field_history["versioned_field_1"]) == 1
    assert rec1.html_field_history["versioned_field_1"][0]["patch"] == 'R@1:<p>rec1 initial content'
    assert rec1.versioned_field_2 == 'text'  # not versioned, preserved as-is

    # rec2: has history
    assert len(rec2.html_field_history["versioned_field_1"]) == 1
    assert rec2.html_field_history["versioned_field_1"][0]["patch"] == 'R@1:<p>rec2 initial value'
```

**Assertions verified:**
- Batch write returns `True` (standard Odoo behavior)
- Each record gets its own revision entry with its own patch
- Non-versioned fields on each record are not affected by the batch write
- The patch format `R@1:<p>...` indicates a **Replace** operation at index 1

#### `test_html_field_history_revision_are_sanitized`

Tests that malicious HTML in revisions is stripped before storage.

```python
def test_html_field_history_revision_are_sanitized(self):
    rec1 = self.env["html.field.history.test"].create({
        "versioned_field_1": "mock content",
    })

    # Write unsafe HTML (iframe injection)
    rec1.write({
        "versioned_field_1": 'scam <iframe src="http://not.secure.scam" />'
    })

    # Current value is sanitized
    assert rec1.versioned_field_1 == "<p>scam </p>"
    assert "iframe" not in rec1.versioned_field_1

    # Revision patch does NOT contain the unsafe content
    revision = rec1.html_field_history["versioned_field_1"][0]
    assert "iframe" not in str(revision)  # Sanitized before storage
    assert "not.secure.scam" not in str(revision)

    # Subsequent writes also exclude unsafe content from revisions
    rec1.write({"versioned_field_1": "not a scam"})
    assert len(rec1.html_field_history["versioned_field_1"]) == 2
    assert "iframe" not in str(rec1.html_field_history["versioned_field_1"])
```

**Assertions verified:**
- The current field value is properly sanitized
- **Critically**: the revision stored in history is ALSO sanitized before being written
- Unsafe content (`<iframe>`, external URLs) never reaches the revision storage
- This prevents replay attacks where an attacker could restore a malicious revision later

#### `test_html_field_history_write` (ValidationError for non-sanitized)

Tests that the mixin prevents versioning of non-sanitized fields.

```python
def test_html_field_history_write(self):
    rec2 = self.env["html.field.history.test"].create({
        "versioned_field_2": "mock content",  # sanitize=False
    })

    # Attempting to create a revision on a non-sanitized field raises ValidationError
    with self.assertRaises(ValidationError, msg=(
        "We should not be able to version a field that is not declared as sanitize=True"
    )):
        rec2.write({"versioned_field_2": "mock content 2"})
```

**Assertions verified:**
- `ValidationError` is raised when trying to write to a versioned field that has `sanitize=False`
- This is a deliberate safety feature: non-sanitized HTML can contain scripts or malicious content, so the mixin refuses to create revision history for them

## What Gets Tested

| Test Category | What Is Verified |
|--------------|-----------------|
| Revision creation | Write operations create revision entries; creation does not |
| Batch write | Multiple records get separate revisions |
| Sanitization | Unsafe HTML is stripped before being stored in revisions |
| Security | Malicious HTML cannot be persisted in revision history |
| Non-sanitized fields | `ValidationError` when attempting to version `sanitize=False` fields |
| Empty values | Writing `None` to a versioned field creates a revision (tracks deletion) |
| Patch format | JSON Patch format (`R@N:`) correctly represents the change |
| Metadata | `html_field_history_metadata` stays in sync with revision count |

## Related

- [Modules/html_editor](html_editor.md) — HTML rich text editor component
- [Modules/html_builder](html_builder.md) — HTML field builder utilities
- [Core/API](Core/API.md) — `@api.constrains` and ValidationError handling
