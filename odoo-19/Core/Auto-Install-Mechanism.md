---
title: "Auto-Install Mechanism"
date: 2026-04-15
tags: [odoo, odoo19, auto_install, modules, dependency]
sources: 2
type: concept
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/auto-install-mechanism.md
---


# Auto-Install Mechanism

## Definisi

**Auto-install** adalah mekanisme Odoo dimana sebuah module secara otomatis terinstall ketika semua dependensinya sudah terinstall — tanpa intervensi user. Ini dikendalikan oleh field `auto_install` di `__manifest__.py`.

Mekanisme ini penting untuk memahami [odoo-minimal-installation](odoo-minimal-installation.md) karena menentukan module apa saja yang ikut terinstall ketika kamu install satu module.

## `auto_install` Field di `__manifest__.py`

Field ini bisa bernilai tiga tipe:

### 1. `auto_install: False` (Default)
Module **tidak** akan auto-install. User harus install manual.

```python
# __manifest__.py
{
    'name': 'Sale',
    'depends': ['product', 'account'],
    'auto_install': False,  # default — user install manual
}
```

### 2. `auto_install: True`
Module otomatis install ketika **semua** deps di `depends` sudah terinstall.

```python
# __manifest__.py
{
    'name': 'Web',
    'depends': ['base'],
    'auto_install': True,  # install otomatis ketika 'base' terinstall
}
```

### 3. `auto_install: [list_of_deps]`
Module otomatis install ketika **deps yang disebutkan dalam list** sudah terinstall — bukan semua deps di `depends`.

```python
# Contoh: l10n_bg (lokalisasi Bulgaria)
{
    'name': 'Bulgaria - Accounting',
    'depends': ['account', 'base'],
    'auto_install': ['account'],  # install otomatis ketika 'account' saja yang terinstall
}
```

Ini memungkinkan **partial dependency triggering** — berguna untuk lokalisasi dan glue modules.

## Jumlah Module dengan auto_install di Odoo 19

| Tipe | Jumlah |
|------|--------|
| `auto_install: True` | 241 |
| `auto_install: [list]` | 142 |
| **Total auto_install** | **383** |

Dari 383 module auto_install, hanya **14 yang terinstall** saat minimal install (`-i base`), karena sisanya memerlukan deps bisnis (account, sale, hr, dll) yang tidak ada.

## Algoritma Auto-Install (Simulasi)

Dari source code `odoo/addons/base/models/ir_module.py`:

```python
# Simplified dari button_install()
def must_install(module):
    """Returns True if module should be auto-installed"""
    states = {dep.state for dep in module.dependencies_id
              if dep.auto_install_required}
    return states <= {'installed', 'to install', 'to upgrade'}

# Loop: terus cek sampai tidak ada lagi yang bisa di-install
auto_domain = [('state', '=', 'uninstalled'), ('auto_install', '=', True)]
modules_to_install = self.search(auto_domain).filtered(must_install)
```

**Iterasi loop**:
1. Install module yang diminta (`-i base`)
2. Cek semua module `uninstalled` dengan `auto_install=True`
3. Jika semua `auto_install_required` deps sudah `installed` → tambahkan ke install queue
4. Ulangi sampai tidak ada lagi candidates
5. Install semua module dalam queue

## Field `auto_install_required` di Dependencies

Ini field kunci di model `ir.module.module.dependency`:

```python
# odoo/addons/base/models/ir_module.py
class ModuleDependency(models.Model):
    _name = "ir.module.module.dependency"

    auto_install_required = fields.Boolean(
        default=True,
        help="Whether this dependency blocks auto-installation"
    )
```

Ketika `auto_install` adalah list (e.g., `['account']`), hanya deps dalam list itu yang di-set `auto_install_required=True`. Deps lainnya tidak memblokir auto-install.

## Skip Auto-Install

Dengan flag `--skip-auto-install`, seluruh mekanisme auto-install dinonaktifkan:

```python
# Dari ir_module.py
if config.get('skip_auto_install'):
    modules = None  # tidak ada yang di-auto-install
else:
    modules = self.search(auto_domain).filtered(must_install)
```

```bash
# Contoh penggunaan
./odoo-bin -d mydb -i base --skip-auto-install --stop-after-init
```

## 14 Module Auto-Installed pada `-i base`

Berikut chain auto-install lengkap ketika hanya `base` yang diinisialisasi:

```
Iterasi 1:
  base (installed) → triggers:
    web (deps: [base]) ✓

Iterasi 2:
  web (installed) → triggers:
    rpc (deps: [base]) ✓
    api_doc (deps: [web]) ✓
    auth_totp (deps: [web]) ✓
    base_import (deps: [web]) ✓
    base_import_module (deps: [web]) ✓
    web_tour (deps: [web]) ✓

Iterasi 3:
  base + web installed → triggers:
    bus (deps: [base, web]) ✓
    base_setup (deps: [base, web]) ✓

Iterasi 4:
  base_setup + web installed → triggers:
    auth_passkey (deps: [base_setup, web]) ✓
    iap (deps: [web, base_setup]) ✓

  bus + base + web installed → triggers:
    html_editor (deps: [base, bus, web]) ✓

Iterasi 5:
  base_setup + html_editor installed → triggers:
    web_unsplash (deps: [base_setup, html_editor]) ✓

TOTAL: 14 modules
```

## Auto-Install di Konteks Glue Modules

Banyak module auto_install adalah **glue modules** — penghubung antara dua module yang tidak saling tahu:

```python
# Contoh: sale_purchase_project
{
    'name': 'Sale Purchase Project',
    'depends': ['sale_project', 'purchase_project'],
    'auto_install': True,  # install otomatis saat keduanya ada
}
```

Ini penting karena:
- `sale_project` tidak tahu tentang `purchase_project`
- `purchase_project` tidak tahu tentang `sale_project`
- Glue module menyediakan integrasi tanpa coupling langsung

## Lokalisasi dengan auto_install List

142 dari 383 auto_install modules menggunakan format list, mayoritas adalah lokalisasi:

```python
# l10n_id (lokalisasi Indonesia)
{
    'depends': ['account', 'base'],
    'auto_install': ['account'],  # install otomatis saat account terinstall
}
```

Artinya: **install `account` → otomatis install lokalisasi negara pengguna** (jika tersedia).

## Relasi dengan Konsep Lain

- [odoo-minimal-installation](odoo-minimal-installation.md) — hasil praktis dari mekanisme ini
- [module-dependency-system](module-dependency-system.md) — sistem dependency yang mendukung auto_install
- [odoo-base-module](odoo-base-module.md) — module pertama yang memicu chain auto-install
- [server-wide-modules](server-wide-modules.md) — module yang dimuat sebelum auto-install

## Referensi Source Code

- `odoo/addons/base/models/ir_module.py:407` — `button_install()` dan `must_install()` logic
- `odoo/addons/base/models/ir_module.py:824` — `_update_dependencies()` untuk set `auto_install_required`
- `odoo/tools/config.py:237` — `--skip-auto-install` flag definition
