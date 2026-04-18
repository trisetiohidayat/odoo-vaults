---
title: "Server-Wide Modules"
date: 2026-04-15
tags: [odoo, odoo19, server, configuration, modules, startup]
sources: 2
type: concept
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/server-wide-modules.md
---


# Server-Wide Modules

## Definisi

**Server-Wide Modules** adalah module yang dimuat oleh Odoo server pada saat startup, **sebelum** database-specific modules dimuat. Mereka tersedia di semua databases pada server tersebut, bukan hanya database tertentu.

Dikonfigurasi via `--load` flag atau `server_wide_modules` di `odoo.conf`.

Ini bagian penting dari [odoo-minimal-installation](odoo-minimal-installation.md) karena merupakan layer pertama yang dimuat.

## Konfigurasi

### Di Command Line
```bash
# Explicit minimal
./odoo-bin --load=base,web

# Default (jika tidak diset)
./odoo-bin --load=base,rpc,web

# Extended
./odoo-bin --load=base,rpc,web,my_custom_server_module
```

### Di odoo.conf
```ini
[options]
# Minimal possible:
server_wide_modules = base,web

# Default:
server_wide_modules = base,rpc,web

# Extended untuk API server:
server_wide_modules = base,rpc,web,api_doc
```

## Constants di Source Code

Dari `odoo/odoo/tools/config.py`:

```python
DEFAULT_SERVER_WIDE_MODULES = ['base', 'rpc', 'web']
REQUIRED_SERVER_WIDE_MODULES = ['base', 'web']
```

**`DEFAULT_SERVER_WIDE_MODULES`**: Module yang diload jika `--load` tidak diset.

**`REQUIRED_SERVER_WIDE_MODULES`**: Module yang **wajib** ada — Odoo akan menambahkannya secara paksa jika tidak disebutkan:

```python
# Dari config.py
if not self['server_wide_modules']:
    self._runtime_options['server_wide_modules'] = DEFAULT_SERVER_WIDE_MODULES
else:
    for mod in REQUIRED_SERVER_WIDE_MODULES:
        if mod not in self['server_wide_modules']:
            # Paksa tambahkan module yang required
            self._runtime_options['server_wide_modules'] = [mod] + self['server_wide_modules']
```

## Tiga Module Default

### 1. `base` — Kernel (REQUIRED)
- Root module, tidak ada dependency
- Menyediakan ORM, models fundamental (res.users, ir.model, dll)
- **Wajib ada** — tanpanya Odoo tidak bisa berjalan

### 2. `web` — Web Client (REQUIRED)
- Web client framework (Owl JS, routing, assets)
- HTTP controllers untuk rendering views
- **Wajib ada** — tanpanya web UI tidak tersedia
- auto_install: True, depends: ['base']

### 3. `rpc` — RPC Endpoints (DEFAULT, optional)
- XML-RPC endpoint (`/xmlrpc/2/`)
- JSON-RPC endpoint (`/web/dataset/call_kw`)
- Bisa dihilangkan jika server hanya digunakan headless/internal
- auto_install: True, depends: ['base']

## Perbedaan Server-Wide vs DB Modules

| Aspek | Server-Wide | DB Modules |
|-------|------------|------------|
| Scope | Semua databases di server | Hanya database tertentu |
| Dimuat kapan | Server startup | Request ke database |
| Kontrol | `--load` / `server_wide_modules` | `ir.module.module` state |
| Bisa berbeda per DB | Tidak | Ya |
| Contoh | base, web, rpc | sale, account, hr |

## Minimal Possible Configuration

```ini
# odoo-minimal.conf
[options]
# Hanya base dan web (tanpa rpc)
server_wide_modules = base,web
db_host = localhost
db_name = mydb
addons_path = /path/to/odoo/odoo/addons,/path/to/odoo/addons
without_demo = all
```

```bash
./odoo-bin -c odoo-minimal.conf -i base --stop-after-init
```

**Catatan**: Menghilangkan `rpc` berarti external API (XML-RPC, JSON-RPC) tidak tersedia. Cocok untuk setup yang hanya menggunakan web UI.

## Kapan Module Bisa Jadi Server-Wide?

Tidak semua module cocok menjadi server-wide. Module yang cocok:
- Tidak bergantung pada data database tertentu
- Menyediakan HTTP controllers yang perlu tersedia server-wide
- Menyediakan infrastructure untuk modules lain

Custom module bisa menjadi server-wide jika perlu diload sebelum DB selection (misalnya, custom login page atau custom session handler).

## Kaitannya dengan Module Loading

Dalam `loading.py`, server-wide modules dimuat pertama kali sebagai bagian dari `STEP 1`:

```python
# STEP 1: LOAD BASE (dan server-wide modules lainnya)
graph = ModuleGraph(cr, mode='update' if update_module else 'load')
graph.extend(['base'])  # base selalu pertama

# Server-wide modules sudah dimuat sebelum ini via service initialization
```

## Relasi dengan Konsep Lain

- [odoo-minimal-installation](odoo-minimal-installation.md) — server_wide_modules adalah lapisan pertama minimal install
- [module-dependency-system](Core/Module-Dependency-System.md) — dependency graph berlaku juga untuk server-wide modules
- [odoo-base-module](odoo-base-module.md) — selalu ada di server-wide modules
- [module-loading-sequence](module-loading-sequence.md) — urutan: server-wide → db modules → auto-install

## Referensi Source Code

- `odoo/odoo/tools/config.py:30` — `DEFAULT_SERVER_WIDE_MODULES` dan `REQUIRED_SERVER_WIDE_MODULES`
- `odoo/odoo/tools/config.py:249` — `--load` option definition
- `odoo/odoo/tools/config.py:660` — enforcement of REQUIRED_SERVER_WIDE_MODULES
