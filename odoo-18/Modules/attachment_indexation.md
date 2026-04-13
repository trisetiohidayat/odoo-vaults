---
Module: attachment_indexation
Version: 18.0
Type: addon
Tags: #attachment #search #indexing
---

# attachment_indexation

Attachment indexing and enhanced document search. Enables full-text search on PDF, ODT, XLSX, and DOCX file attachments, and moves the attachment view to the top of form views.

## Module Overview

**Category:** Hidden/Tools
**Depends:** `web`
**Version:** 2.1
**License:** LGPL-3

## What It Does

Two main features:

1. **Document Indexation** — Extracts text content from binary file types for search indexing:
   - PDF (via `pdfminer.six` Python library)
   - ODT (OpenDocument Text)
   - XLSX (Excel)
   - DOCX (Word)

2. **Attachment on Form Top** — Moves the attachment widget to the top of form views for better UX.

## Extends

- `web` — web client enhancement

## Key Details

- No Python models; uses Odoo's attachment indexing infrastructure
- PDF indexing requires `pdfminer.six` to be installed separately
- Works with `ir.attachment` records; indexed content feeds into Odoo's global search

---

*See also: [Modules/web](web.md)*
