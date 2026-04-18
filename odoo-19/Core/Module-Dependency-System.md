---
title: "Module Dependency System"
date: 2026-04-15
tags: [odoo, odoo19, modules, dependency, ir.module.module, manifest]
sources: 2
type: concept
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/module-dependency-system.md
---


# Module Dependency System

## Definisi

**Module Dependency System** adalah infrastruktur Odoo yang mengelola relasi antar module, urutan instalasi, dan lifecycle module (install, upgrade, uninstall). Sistem ini diimplementasikan melalui model `ir.module.module` dan `ir.module.module.dependency`, serta `ModuleGraph` di server.

Pemahaman ini kritis untuk [odoo-minimal-installation](odoo-minimal-installation.md) karena menentukan module apa yang **harus** ada sebelum module lain bisa diinstall.

## Model Utama

### `ir.module.module`

Model utama yang merepresentasikan setiap module Odoo:

```python
class Module(models.Model):
    _name = "ir.module.module"

    name = fields.Char()           # Technical name (e.g., 'sale')
    state = fields.Selection([     # Current state
        ('uninstallable', 'Not Installable'),
        ('uninstalled', 'Not Installed'),
        ('installed', 'Installed'),
        ('upgrade', 'In Upgrade'),
        ('to upgrade', 'To Be Upgraded'),
        ('to remove', 'To Be Removed'),
        ('to install', 'To Be Installed'),
    ])
    auto_install = fields.Boolean()  # Auto-install flag
    dependencies_id = fields.One2many('ir.module.module.dependency', ...)
```

### `ir.module.module.dependency`

Model yang merepresentasikan satu dependency antara dua module:

```python
class ModuleDependency(models.Model):
    _name = "ir.module.module.dependency"

    module_id = fields.Many2one('ir.module.module')  # Module yang bergantung
    name = fields.Char()                              # Nama module yang dibutuhkan
    depend_id = fields.Many2one('ir.module.module')  # Reference ke module tsb
    state = fields.Selection()                         # State dari dep module
    auto_install_required = fields.Boolean(           # Blocking flag untuk auto_install
        default=True,
    )
```

## ModuleGraph

`ModuleGraph` adalah struktur data di `odoo/modules/module_graph.py` yang merepresentasikan dependency graph dan menentukan urutan loading:

```python
# Dari loading.py (STEP 1)
graph = ModuleGraph(cr, mode='update' if update_module else 'load')
graph.extend(['base'])  # Mulai dari base

# STEP 3: Extend dengan module yang perlu diload
env.cr.execute("SELECT name from ir_module_module WHERE state IN %s", [states])
module_list = [name for (name,) in env.cr.fetchall() if name not in graph]
graph.extend(module_list)
```

`ModuleGraph.extend()` melakukan **topological sort** — memastikan dep selalu dimuat sebelum module yang membutuhkannya.

## `__manifest__.py` — Deklarasi Dependencies

Setiap module mendeklarasikan dependensinya di `__manifest__.py`:

```python
{
    'name': 'Sale',
    'version': '1.0',
    'depends': [
        'base',
        'product',
        'analytic',
        'account',
    ],
    'auto_install': False,
    'installable': True,
    'category': 'Sales/Sales',
}
```

### Field Penting di Manifest

| Field | Tipe | Default | Keterangan |
|-------|------|---------|------------|
| `depends` | `list[str]` | `[]` | Module yang harus terinstall dulu |
| `auto_install` | `bool\|list` | `False` | Trigger auto-install |
| `installable` | `bool` | `True` | Bisa diinstall user |
| `category` | `str` | `''` | Kategori (Hidden = tidak tampil di Apps) |
| `version` | `str` | `'1.0'` | Versi module |

## Hierarki Dependencies (Odoo 19)

Berdasarkan analisis source code, berikut level dependency dari `base`:

### Level 0 (No deps / kernel)
```
base (odoo/odoo/addons/base)
  depends: [] — kernel, tidak ada dep
```

### Level 1 (depends only on base)
```
web          depends: [base]     auto_install: True
rpc          depends: [base]     auto_install: True
uom          depends: [base]     auto_install: False
social_media depends: [base]     auto_install: False
l10n_fr      depends: [base]     auto_install: False (user choice)
l10n_us      depends: [base]     auto_install: False
```

### Level 2 (depends on web/rpc + base)
```
bus          depends: [base, web]       auto_install: True
base_setup   depends: [base, web]       auto_install: True
api_doc      depends: [web]             auto_install: True
auth_totp    depends: [web]             auto_install: True
base_import  depends: [web]             auto_install: True
web_tour     depends: [web]             auto_install: True
```

### Level 3 (depends on bus/base_setup)
```
html_editor  depends: [base, bus, web]    auto_install: True
auth_passkey depends: [base_setup, web]   auto_install: True
iap          depends: [web, base_setup]   auto_install: True
mail         depends: [base, base_setup, bus, web_tour, html_editor]
                                           auto_install: False  ← PENTING
```

### Level 4 (depends on html_editor)
```
web_unsplash depends: [base_setup, html_editor]  auto_install: True
```

## Downstream Dependencies

Method `downstream_dependencies()` menemukan module yang **bergantung** pada module tertentu:

```python
# Contoh: module apa saja yang ikut ter-affect jika 'mail' di-uninstall?
mail_module = env['ir.module.module'].search([('name', '=', 'mail')])
downstream = mail_module.downstream_dependencies()
# Returns: discuss, calendar, sale, crm, project, etc.
```

Ini critical untuk **uninstall** — Odoo tidak akan uninstall module yang masih dibutuhkan module lain yang terinstall.

## State Transitions

```
uninstallable ← (tidak bisa install, dep tidak terpenuhi)

uninstalled → [button_install()] → to install → [loading] → installed
              [button_upgrade()]                             ↓
                                                    to upgrade → installed
installed   → [button_uninstall()] → to remove → uninstalled
```

## Query Berguna

```sql
-- Semua module yang terinstall
SELECT name, latest_version FROM ir_module_module
WHERE state = 'installed' ORDER BY name;

-- Dependency tree untuk module tertentu
SELECT d.name as depends_on, m.name as module, d.auto_install_required
FROM ir_module_module_dependency d
JOIN ir_module_module m ON m.id = d.module_id
WHERE m.name = 'mail';

-- Module yang tidak punya upstream (tidak dibutuhkan module lain)
SELECT name FROM ir_module_module m
WHERE state = 'installed'
AND NOT EXISTS (
    SELECT 1 FROM ir_module_module_dependency d WHERE d.name = m.name
);
```

## Kontrol Manual Dependencies

Untuk custom module, deklarasikan deps dengan tepat:

```python
# __manifest__.py
{
    'name': 'My Custom Module',
    'depends': [
        'base',      # SELALU butuh base
        'mail',      # Jika butuh chatter/messaging
        'web',       # Jika butuh web client features
    ],
    'auto_install': False,  # Jangan auto-install
}
```

**Anti-pattern**: Mendeklare dep yang tidak benar-benar dibutuhkan — ini akan memaksa dep untuk terinstall dan membuat lingkungan tidak minimal.

## Relasi dengan Konsep Lain

- [auto-install-mechanism](auto-install-mechanism.md) — menggunakan dependency graph untuk trigger installation
- [odoo-minimal-installation](odoo-minimal-installation.md) — hasil dari dependency resolution
- [odoo-base-module](odoo-base-module.md) — root dari semua dependency graph
- [server-wide-modules](server-wide-modules.md) — module yang dimuat di luar dependency graph regular
- [module-loading-sequence](module-loading-sequence.md) — urutan loading berdasarkan dependency graph

## Referensi Source Code

- `odoo/odoo/modules/module_graph.py` — ModuleGraph implementation
- `odoo/odoo/modules/loading.py:376` — `graph.extend(['base'])` — start of dependency resolution
- `odoo/addons/base/models/ir_module.py:299` — `auto_install` field definition
- `odoo/addons/base/models/ir_module.py:1011` — `auto_install_required` field
