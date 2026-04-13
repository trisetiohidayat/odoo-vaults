# Odoo 19 social_media Module - Social Media Links

### Module Info: `/Users/tri-mac/odoo/odoo19/odoo/addons/social_media/__manifest__.py`

| Property | Value |
|----------|-------|
| Name | Social Media |
| Version | 0.1 |
| Category | Marketing/Social Marketing |
| Depends | `base` |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Application | No |

---

### Module Structure

```
social_media/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_company.py         # Social media URL fields on company
│   └── website.py             # Social link widget for websites
├── views/
│   ├── res_company_views.xml  # Company form view with social fields
│   └── website_templates.xml # QWeb snippets for social links
├── data/
│   └── res_company_demo.xml  # Demo company with social links
└── static/
    └── src/
        └── scss/
            └── social_media.scss
```

---

### Core Extensions

The `social_media` module adds social media profile URL fields to two models: `res.company` (for company settings) and the website `social.additional.link` model (for per-website social links).

---

### 1. Res Company Extension

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/social_media/models/res_company.py`

#### Fields Added to `res.company`

| Field | Type | Description |
|-------|------|-------------|
| `social_twitter` | Char | Twitter/X profile URL |
| `social_facebook` | Char | Facebook page URL |
| `social_linkedin` | Char | LinkedIn company page URL |
| `social_youtube` | Char | YouTube channel URL |
| `social_instagram` | Char | Instagram profile URL |
| `social_other` | Char | Any other social media URL |

All fields are:
- Type: `Char`
- Indexed: `True` (for search performance)
- `copy=False` (not duplicated on company copy)
- No tracking (not tracked in mail.thread history)

#### Template Usage

These fields are referenced in QWeb email templates via:

```xml
<t t-out="company.social_twitter"/>
<t t-out="company.social_facebook"/>
```

---

### 2. Website Social Link Model

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/social_media/models/website.py`

#### Model: `website.social.additional.link`

| Property | Value |
|----------|-------|
| `_name` | `website.social.additional.link` |
| `_description` | "Social Media Link" |
| `_order` | `sequence` |

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Link label (e.g., "Newsletter") |
| `url` | Char | Full URL (e.g., "https://...") |
| `link_style` | Char | CSS class/style for the link |
| `social_id` | Many2one (website.social.link) | Social network reference |
| `website_id` | Many2one (website) | Website scope (multi-website) |
| `sequence` | Integer | Display order |

#### Key Methods

- Standard CRUD (create, write, unlink) - no special overrides

---

### 3. Website Social Link Master Model

**File:** `/Users/tri-mac/odoo/odoo19/odoo/addons/social_media/models/website.py`

#### Model: `website.social.link`

| Property | Value |
|----------|-------|
| `_name` | `website.social.link` |
| `_description` | "Social Network" |

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Network name (required) |
| `icon` | Char | Font-awesome icon class (e.g., `fa-twitter`) |
| `social_link` | Char | Default/base URL for this network |

This is a master/reference table. Each record represents one social network (Twitter, Facebook, etc.). Website-specific links reference these via `social_id`.

---

### Views

**`views/res_company_views.xml`** - Company form view adds social media field group:

```xml
<group string="Social Media" name="social_media">
    <field name="social_twitter"/>
    <field name="social_facebook"/>
    <field name="social_linkedin"/>
    <field name="social_youtube"/>
    <field name="social_instagram"/>
    <field name="social_other"/>
</group>
```

---

### Design Patterns

#### Field Inheritance
The module uses classic `_inherit = 'res.company'` pattern to add fields without creating a new model.

#### Multi-Website Support
The `website.social.additional.link` model includes `website_id` for per-website social link overrides, supporting multi-website Odoo installations.

#### Icon-Based Display
Social media links on websites use Font-Awesome icon classes (`fa-twitter`, `fa-facebook`, etc.) for visual display in website themes.

---

### Access Control

| Model | Groups | Permissions |
|-------|--------|------------|
| `res.company` | All users (via company) | Read social fields, Write requires admin |
| `website.social.link` | Website editor | Create/Edit |
| `website.social.additional.link` | Website editor | Create/Edit |

---

### Integration Points

| Integration | Model | Usage |
|-------------|-------|-------|
| Email templates | `mail.template` | `company.social_*` in QWeb |
| Website | `website` | Social links snippet in footer |
| Company reports | `report` | Social media links in letterheads |

---

### See Also

- [Modules/Website](website.md) - Website builder integration
- [Modules/Mail](mail.md) - Email template system
- [Modules/Company](Modules/Company.md) - res.company model
