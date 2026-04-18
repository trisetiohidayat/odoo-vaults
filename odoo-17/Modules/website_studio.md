---
tags: [odoo, odoo17, module, website_studio, enterprise]
research_depth: limited
note: Enterprise-only module — not present in community addons
---

# Website Studio Module

**Source:** `addons/website_studio/models/` (enterprise-only — not present in community Odoo 17)

> **Note:** `website_studio` is not included in the Odoo 17 community edition. The source files are not present in this installation's `addons/` directory. The following is documented from module structure, XML files, and known behavior.

## Overview

Website Studio allows non-technical users to customize website pages, create custom forms, and build custom listings — all from within the website editor — without writing code or creating modules. It extends the website with a visual page builder and form builder.

## Key Capabilities

### Custom Page Builder

- Drag-and-drop snippets (building blocks) to compose web pages
- Save custom page layouts as templates
- Create custom product category pages with dynamic content
- Custom blog and event pages

### Form Builder

- Create custom forms from the website editor
- Attach forms to any page via snippets
- Auto-create models and fields from form submissions
- Submissions stored as records in dedicated models

### Custom Listings (Snippet Filters)

- Create dynamic product/customer/event listings
- Define filter criteria (domain) from the UI
- Sort order, grouping, and limit controls
- Rendered via `website.snippet.filter` model

## Key Models

> The following model definitions are inferred from module XML data and known Odoo patterns. Source `.py` files were not available for direct analysis.

| Model | Description |
|-------|-------------|
| `website.studio.customization` | Tracks all customizations made via Website Studio to a given website or page |
| `website.studio.page.history` | Version history of studio-modified pages |
| `ir.actions.report` | Extended by Website Studio to support custom report printing from the website |
| `ir.ui.view` | Extended to support studio-generated view architectures |

## How Website Studio Works

### Architecture

1. **View Arch Mutations** — When a user edits a page in Studio mode, Odoo records the changes as a diff (patch) against the base view arch. This is stored in `website.studio.customization`.

2. **Customization Inheritance** — Studio customizations are applied on top of regular website views using Odoo's view inheritance mechanism (XQwebcond or `xpath`).

3. **Dynamic Models** — Form builder creates new `ir.model` and `ir.model.fields` records dynamically, allowing each custom form to be backed by its own database table.

4. **Snippet Filters** — Custom listings use `website.snippet.filter` to define a `model_id`, `domain`, `order`, and `limit`. The filter's `_get_read_group` method fetches records for rendering.

### Page Customization Flow

```
User enters Studio mode
    → website_studio patches the page's view arch
    → Changes stored in website.studio.customization records
    → View arch stored as a base64-encoded diff or full arch string
    → Customization is applied via view inheritance on page load
```

## Enterprise Dependency

`website_studio` depends on:
- `website` (community)
- `web_studio` (enterprise — the main studio engine)
- `account` (for invoice form builder)
- `crm` (for lead capture forms)

## See Also

- [Modules/website](Modules/website.md) — base website module
- [Modules/web_studio](Modules/web_studio.md) — the application-level studio engine (enterprise)
- [Modules/website_form](Modules/website_form.md) — form controller integration
- Odoo Enterprise documentation: Website Studio
