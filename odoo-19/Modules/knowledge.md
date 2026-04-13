---
type: module
title: "Knowledge — Internal Wiki & Knowledge Base"
description: "Knowledge management module for internal articles, categories, tags, and collaborative writing. Integrates with Mail and Discuss."
source_path: ~/odoo/odoo19/odoo/addons/knowledge/
tags:
  - odoo
  - odoo19
  - module
  - knowledge
  - wiki
  - content
related_modules:
  - mail
  - discuss
  - portal
created: 2026-04-07
version: "1.0"
---

## Quick Access

### 🔗 Related Modules
- [Modules/mail](mail.md) — Article notifications and comments
- [Modules/mail](mail.md) — Collaborative workspace channels
- [Modules/Portal](portal.md) — Public article sharing

---

## Module Overview

| Property | Value |
|----------|-------|
| **Name** | Knowledge |
| **Technical Name** | `knowledge` |
| **Category** | Content / Knowledge Management |
| **Summary** | Internal wiki, articles, and knowledge base |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Installable** | Yes |

### Description

The Knowledge module provides an internal wiki and knowledge base for organizations. It enables collaborative writing, article organization, and sharing. Articles can be private, shared with specific teams, or published to a portal.

Key capabilities:
- Hierarchical article categories
- Rich-text article editing
- Collaborative editing with access control
- Article sharing via internal or public links
- Integration with Mail (comment threads on articles)
- Integration with Discuss (workspace channels)

---

## Key Models

### 1. Knowledge Article (`knowledge.article`)

The central model for knowledge articles.

**Key Fields:**
- `name` — Article title
- `body` — HTML article content
- `category_id` — Parent category
- `child_ids` — Child articles
- `parent_id` — Parent article
- `is_private` — Privacy flag
- `article_properties` — Custom properties (JSON)
- `owner_id` — Responsible user
- `editor_ids` — Users who can edit
- `belong_to_channel` — Associated channel
- `internal_permission` — Access level (write/read/none)
- `kanban_dashboard_state` — Kanban state

**Article Properties:**
Articles support dynamic properties via JSON — you can add custom fields at the article level without altering the database schema.

---

### 2. Knowledge Category (`knowledge.category`)

Organizes articles into hierarchical categories.

**Key Fields:**
- `name` — Category name
- `parent_id` — Parent category
- `child_ids` — Child categories
- `article_ids` — Articles in this category

---

### 3. Knowledge Tag (`knowledge.tag`)

Tags for cross-category article classification.

**Key Fields:**
- `name` — Tag name
- `color` — Display color
- `article_ids` — Tagged articles

---

## Common Workflows

### Article Creation
1. Go to **Knowledge → Articles**
2. Click **Create** — choose workspace (private/team/shared)
3. Enter article title and body (rich text editor)
4. Set access permissions (owner, editors, readers)
5. Add to category via **Properties** panel
6. Click **Save**

### Article Sharing
1. Open an article
2. Click **Share** — choose sharing method:
   - **Internal**: Share with specific users/teams
   - **Public**: Generate public link (if Portal enabled)
3. Configure read/write access per recipient

### Collaborative Editing
1. Multiple users open the same article
2. Odoo tracks presence (who is viewing)
3. Changes are saved automatically
4. Mail thread on article captures change history

---

## Related Modules

| Module | Purpose |
|--------|---------|
| [Modules/mail](mail.md) | Article comment threads |
| `discuss` | Workspace channel integration |
| `portal` | Public article portal |
| `website` | Public-facing knowledge base |

---

*Source module: `~/odoo/odoo19/odoo/addons/knowledge/`*
