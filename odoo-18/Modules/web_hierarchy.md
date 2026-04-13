---
Module: web_hierarchy
Version: 18.0
Type: addon
Tags: #web, #hierarchy, #view, #tree, #org-chart
---

# web_hierarchy — Hierarchy View

## Module Overview

**Category:** Hidden
**Depends:** `web`
**License:** LGPL-3
**Installable:** True

Adds a hierarchical tree view renderer to Odoo's view system. Displays any model as an expandable/collapsible tree (org-chart style), with support for expand-all, drag-and-drop reparenting, and inline record creation. The view reads data from any model's `read_group` using a `parent_path` or `parent_id` field.

## Data Files

- `data/hierarchy_view.xml` — Example view definitions for `res.partner`

## Static Assets

**JS (`web.assets_backend`):**
- `web_hierarchy/static/src/js/hierarchy_controller.js` — Main view controller (extends `OwlController`)
- `web_hierarchy/static/src/js/hierarchy_renderer.js` — Tree renderer (OWL component)
- `web_hierarchy/static/src/js/hierarchy_model.js` — Data fetching via `read_group`
- `web_hierarchy/static/src/js/hierarchy_view.js` — View factory
- `web_hierarchy/static/src/js/renderer/line.js` — Individual node renderer (OWL component)

**SCSS:**
- `web_hierarchy/static/src/scss/hierarchy_view.scss` — Main styles
- `web_hierarchy/static/src/scss/hierarchy_variables.scss` — SCSS variables

**Dark mode:**
- `web_hierarchy/static/src/scss/hierarchy.dark.scss` — Dark theme overrides

**Tests:**
- `web_hierarchy/static/tests/**/*` — QUnit tests

## Models

No Python model files — pure JavaScript/CSS view renderer.

---

## View Declaration

```xml
<record id="view_hierarchy_partner" model="ir.ui.view">
    <field name="model">res.partner</field>
    <field name="arch" type="xml">
        <hierarchy banner_destination="form" limit="80">
            <field name="display_name"/>
            <field name="parent_id"/>
            <!-- additional fields -->
        </hierarchy>
    </field>
</record>
```

## `<hierarchy>` View Attributes

| Attribute | Values | Default | Description |
|-----------|--------|---------|-------------|
| `banner_destination` | `form`, `edit` | `form` | Click on node opens form view (`form`) or edit mode (`edit`) |
| `limit` | integer | `80` | Records fetched per expand request |
| `create_inline` | `1`, `0` | `0` | Enable inline child record creation |
| `draggable` | `1`, `0` | `0` | Enable drag-and-drop reparenting |
| `default_order` | field names | — | Override default ordering |

## Data Model

The hierarchy view uses `read_group` with `parent_path` or `parent_id` field grouping:

- If the model has `parent_path` (char, computed from parent hierarchy), the view uses it for tree structure
- If the model has `parent_id` (Many2one self-referential), the view fetches child records per node

## Key Features

- **Expand/collapse** — Nodes can be expanded to show children, collapsed to hide
- **Drag and drop** — Records can be dragged to reparent them (if the model supports `parent_id` writing)
- **Inline creation** — Add child records directly from a node
- **Dark mode** — Full dark theme support via `_assets_backend_lazy_dark` bundle
- **Lazy loading** — Children are loaded on demand when a node is expanded (uses `limit` attribute)
- **Expand all** — Top-level toolbar button to expand the entire tree
- **OWL-based** — Entire view is implemented as an OWL component for reactivity

## What It Extends

- `web.view_registry` — registers the `hierarchy` view type

---

## Key Behavior

- The hierarchy view is a pure JavaScript view — no server-side Python models.
- It reads data using `read_group` with grouping on `parent_path` or `parent_id` — the model must have one of these fields.
- The `draggable="1"` attribute enables drag-and-drop, which calls `write({'parent_id': new_parent_id})` on the dragged record — the model must allow writing `parent_id`.
- `create_inline="1"` adds an inline "Add" button to each node, opening a quick-create form for child records.
- The view requires `limit` records per expand; large hierarchies should use reasonable limits to avoid performance issues.

---

## See Also

- [Modules/Web](odoo-18/Modules/web.md) (`web`) — view registry and base view system
- [Modules/Project](odoo-18/Modules/project.md) (`project`) — uses hierarchy view for task breakdown
- [Modules/CRM](odoo-18/Modules/CRM.md) — uses hierarchy view for pipeline management
