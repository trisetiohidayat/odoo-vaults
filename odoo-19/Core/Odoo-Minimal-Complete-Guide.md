---
title: "Odoo Minimal — Complete Guide"
date: 2026-04-15
tags: [odoo, odoo19, minimal, synthesis, guide, complete]
type: synthesis
sources: 5
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/synthesis/odoo-minimal-complete-guide.md
---


# Odoo Minimal — Complete Guide

## Thesis

**Odoo bisa berjalan normal sebagai platform ERP dengan hanya 14 module** — semua essential infrastructure tersedia, dan custom modules bisa dibuat tanpa module bisnis apapun. Ini adalah konfigurasi optimal untuk development, testing, dan headless/API deployments.

---

## 1. Apa itu "Odoo Minimal"?

"Minimal Odoo" berarti Odoo berjalan dengan **hanya module-module essential** — module yang diperlukan agar platform berfungsi, tanpa modul bisnis (accounting, sales, HR, inventory, dll).

Setelah minimal install (`-i base`), yang tersedia:
- ✅ Web UI dengan login
- ✅ ORM dan model infrastructure
- ✅ XML-RPC / JSON-RPC API
- ✅ Real-time WebSocket (bus)
- ✅ Rich text editor (html_editor)
- ✅ User authentication (termasuk TOTP, passkey)
- ✅ File attachments
- ✅ Translations
- ✅ Company dan partner management

---

## 2. The 14 Essential Modules

| Module | Dependency Chain | Tujuan |
|--------|-----------------|--------|
| `base` | (root) | ORM, fundamental models |
| `web` | base | Web client, HTTP routing |
| `rpc` | base | XML-RPC/JSON-RPC |
| `bus` | base + web | WebSocket, real-time |
| `html_editor` | base + bus + web | WYSIWYG editor |
| `api_doc` | web | API documentation |
| `auth_totp` | web | Two-factor auth |
| `auth_passkey` | base_setup + web | Passkey/WebAuthn |
| `base_import` | web | Data import |
| `base_import_module` | web | Module import |
| `base_setup` | base + web | Initial setup |
| `iap` | web + base_setup | In-App Purchase |
| `web_tour` | web | Onboarding tours |
| `web_unsplash` | base_setup + html_editor | Image picker |

**Tidak ada module bisnis dalam daftar ini.** `mail`, `sale`, `account`, dll bukan part of minimal.

---

## 3. Cara Membuat Minimal Odoo

### Satu Command

```bash
./odoo-bin -d mydb -i base --without-demo=all --stop-after-init
```

### Dengan Config File

```ini
# odoo-minimal.conf
[options]
db_host = localhost
db_name = mydb
db_user = odoo
server_wide_modules = base,web,rpc
addons_path = /opt/odoo/odoo/addons,/opt/odoo/addons
without_demo = all
```

```bash
./odoo-bin -c odoo-minimal.conf -i base --stop-after-init
```

### Verifikasi

```bash
# Di database: hanya 14 module
psql mydb -c "SELECT name, state FROM ir_module_module WHERE state = 'installed' ORDER BY name;"
```

---

## 4. Anatomy of Minimal Database

**13 tabel SQL bootstrap** (dari base_data.sql):
```
ir_actions, ir_act_window, ir_act_report_xml,
ir_act_url, ir_act_server, ir_act_client,
res_users, res_groups, ir_module_category,
ir_module_module, ir_module_module_dependency,
ir_model_data, res_currency, res_company, res_partner
```

**~35 tabel ORM tambahan** (dari 14 modules via ORM):
```
ir_model, ir_model_fields, ir_model_access, ir_rule,
ir_ui_view, ir_ui_menu, ir_config_parameter,
ir_cron, ir_attachment, ir_sequence, ir_translation,
res_country, res_lang, bus_bus, ...
```

**Total: ~50 tabel**, vs ~300+ untuk full install.

---

## 5. Module Loading Sequence

```
Server startup
  └── Load Python code (framework)

DB Request
  └── load_modules() called

STEP 1: Load 'base'
  └── execute base_data.sql
  └── Install base Python models
  └── Load base XML/CSV data

STEP 2: Auto-install cascade
  base → web, rpc
  web → api_doc, auth_totp, base_import, base_import_module, web_tour
  base+web → bus, base_setup
  bus+base+web → html_editor
  base_setup+web → auth_passkey, iap
  base_setup+html_editor → web_unsplash

STEP 3: Registry setup
  └── All ~50 tables created
  └── Server ready for requests
```

---

## 6. Key Configuration Parameters

| Parameter | Minimal Value | Default |
|-----------|--------------|---------|
| `server_wide_modules` | `base,web` | `base,rpc,web` |
| `without_demo` | `all` | `False` |
| `--skip-auto-install` | (optional) | disabled |
| `addons_path` | framework only | all addons |

---

## 7. Use Cases

| Use Case | Install Command | Modules |
|----------|----------------|---------|
| Pure development | `-i base` | 14 |
| API server | `-i base` (no web needed) | 14 |
| + Chatter | `-i base,mail` | ~20 |
| + Accounting | `-i base,account` | ~25 |
| + Full ERP | `-i base,sale,purchase,account,stock` | ~45 |

---

## 8. What "Minimal" Doesn't Mean

> [!contradiction]
> Common misconception: "minimal" means only `base` module. **This is wrong.**
> With `-i base`, Odoo installs 14 modules via auto_install cascade.
> True "only base" requires `--skip-auto-install` but then web UI breaks.

"Minimal" = smallest set where Odoo functions normally as a platform.

---

## 9. Development in Minimal Odoo

**Available without extra deps**:
- `env['res.users']` — users
- `env['res.partner']` — contacts
- `env['res.company']` — companies
- `env['ir.model']` — model registry
- `env['ir.cron']` — scheduled jobs
- `env['ir.config_parameter']` — settings
- `env['bus.bus']` — real-time messaging

**Custom module deps**: Start with `['base']`, add only what you need.

---

## 10. Summary Decision Tree

```
Do you need Odoo as a platform?
  YES → -i base (14 modules)

Do you need email/chatter?
  YES → add 'mail' to -i

Do you need financial reports?
  YES → add 'account'

Do you need sales workflows?
  YES → add 'sale'

Do you need inventory?
  YES → add 'stock'
```

---

## Supporting Evidence

**Installation & Core:**
- [odoo-minimal-installation](odoo-minimal-installation.md) — 14 modules list and commands
- [auto-install-mechanism](auto-install-mechanism.md) — why 14 not 1 or 100
- [module-dependency-system](module-dependency-system.md) — dependency graph resolution
- [server-wide-modules](server-wide-modules.md) — base + web are REQUIRED
- [module-loading-sequence](module-loading-sequence.md) — 6-step loading process
- [startup-sequence](startup-sequence.md) — odoo-bin to HTTP ready (10-step timeline)

**Database & Data:**
- [database-structure-minimal-install](database-structure-minimal-install.md) — ~50 tables after minimal
- [custom-module-in-minimal-env](custom-module-in-minimal-env.md) — how to develop in minimal
- [module-lifecycle-hooks](module-lifecycle-hooks.md) — post_init/uninstall/pre_init hooks in detail
- [manifest-schema](manifest-schema.md) — __manifest__.py complete reference (32 fields, 632 modules analyzed)

**Module Entities:**
- [odoo-base-module](odoo-base-module.md) — the kernel
- [odoo-web-module](odoo-web-module.md) — HTTP routing layer
- [odoo-rpc-module](odoo-rpc-module.md) — XMLRPC deprecated, new /json/2 API
- [bus-module](bus-module.md) — real-time WebSocket infrastructure
- [mail-module](mail-module.md) — NOT essential (auto_install: False)

**Configuration & Deployment:**
- [odoo-conf-minimal-reference](odoo-conf-minimal-reference.md) — config reference
- [docker-minimal-deployment](docker-minimal-deployment.md) — Docker/Odoo.sh deployment guide

**Comparisons:**
- [odoo19-vs-odoo18-minimal](odoo19-vs-odoo18-minimal.md) — Odoo 19 adds rpc + api_doc, changes auth_passkey
- [enterprise-vs-community-minimal](enterprise-vs-community-minimal.md) — Enterprise adds 5 modules, web_enterprise replaces UI


---

## Open Questions (Answered)

1. **Can Odoo run with fewer than 14 modules without breaking anything?**
   → **No.** `server_wide_modules` (base, web, rpc) CANNOT be uninstalled (code enforced in `button_uninstall()`). Other auto-install modules can be uninstalled individually but will re-install on next module operation if deps still satisfied. True "only base" with `--skip-auto-install` breaks web UI.

2. **What is the performance difference between minimal and full install?**
   → [TODO — see performance-profiling gap]

3. **How do enterprise modules affect the minimal install count?**
   → Enterprise adds 5 auto-install modules: `web_enterprise` (replaces web assets), `web_cohort`, `web_gantt`, `web_grid`, `web_map`. Community 14 + Enterprise 5 = ~19 total. Enterprise also provides 743 total modules vs Community's ~300+.

4. **Is there a way to disable specific auto-install modules (like web_unsplash)?**
   → Only via `--skip-auto-install` (skips ALL auto-install, breaks web UI), or manually uninstall after install (will re-install if any module operation runs). See [uninstall-auto-install-modules](uninstall-auto-install-modules.md).

5. **What makes 14 modules vs 1 or 100?**
   → 3 server_wide modules (base, rpc, web) cannot be removed. The remaining 11 auto-install because they depend only on base+web, which are always present. See [auto-install-mechanism](auto-install-mechanism.md).

6. **Why does Odoo 19 have 14 modules vs ~12 in Odoo 18?**
   → Odoo 19 added 2 new auto-install modules: `rpc` (separated from web) and `auth_passkey` (changed from manual to auto-install). See [odoo19-vs-odoo18-minimal](odoo19-vs-odoo18-minimal.md).
