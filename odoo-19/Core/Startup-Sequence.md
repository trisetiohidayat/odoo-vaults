---
title: "Odoo Startup Sequence — From odoo-bin to Ready"
date: 2026-04-15
tags: [odoo, odoo19, startup, odoo-bin, registry, loading, sequence, boot]
type: concept
sources: 1
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/startup-sequence.md
---


# Odoo Startup Sequence — From `odoo-bin` to Ready

## Overview

Complete startup sequence dari menjalankan `odoo-bin` hingga Odoo siap menerima HTTP requests dan cron jobs. Analisis berdasarkan `server.py` dan `orm/registry.py` di Odoo 19.

## Startup Sequence (Complete)

```
odoo-bin (entry point)
  └─► odoo/cli/main.py
        └─► odoo/cli/server.py → server.start()
              └─► load_server_wide_modules()
                    └─► load_openerp_module('base')
                    └─► load_openerp_module('rpc')     # if in server_wide_modules
                    └─► load_openerp_module('web')
                          └─► web/__init__.py
                                └─► Registers: web.Web, web.Home, bus.controllers.main

              └─► preload_registries(dbnames)
                    └─► Registry.new(dbname, update_module=True)
                          └─► load_modules() [from odoo/modules/loading.py]
                                └─► STEP 1: Load 'base'
                                └─► STEP 2: Mark auto-install modules
                                └─► STEP 3: Load loop (until stable)
                                └─► STEP 4: Apply migrations
                                └─► STEP 5: Finalize (translations, cleanup)
                                └─► STEP 6: Return registry

HTTP Server Start (after registry ready)
  └─► odoo.http.root mounted
  └─► WebSocket longpolling started
  └─► Cron workers spawned
  └─► Odoo ready on port 8069
```

## Stage 1: `odoo-bin` Entry Point

```bash
odoo-bin = python3 -m odoo
# or: ./odoo-bin (wrapper script)
```

Wrapper script just calls `odoo.cli.main()`.

## Stage 2: CLI Command

```python
# odoo/cli/server.py
def run():
    check_root_user()
    check_postgres_user()
    report_configuration()

    if config['init']['base']:
        # Auto-init base if requested
        from odoo.service import db
        db._create_database(...)

    rc = server.start(preload=config['db_name'], stop=stop)
    return rc
```

## Stage 3: `server.start()`

```python
# odoo/service/server.py
def start(preload=None, stop=False):
    load_server_wide_modules()        # ← KEY STEP 1
    import odoo.http                  # ← KEY STEP 2: loads web controllers

    if odoo.evented:
        server = GeventServer(odoo.http.root)
    elif config['workers']:
        server = PreforkServer(odoo.http.root)
    else:
        server = ThreadedServer(odoo.http.root)

    server.start()
```

### `load_server_wide_modules()`

```python
def load_server_wide_modules():
    from odoo.modules.module import load_openerp_module
    with gc.disabling_gc():
        for m in config['server_wide_modules']:  # ['base', 'rpc', 'web'] by default
            load_openerp_module(m)
```

**Effect**: Imports Python code for `base`, `rpc`, `web` **before** any database access. These modules register:
- `base`: ORM models, fields, decorators
- `rpc`: XMLRPC/JSONRPC controllers
- `web`: HTTP controllers (Home, WebClient), asset bundles

**Critical**: `web` must be loaded **before** HTTP server starts because `odoo.http.root` is defined by `web`.

## Stage 4: Registry Preload

```python
def preload_registries(dbnames):
    for dbname in dbnames:
        registry = Registry.new(
            dbname,
            update_module=True,    # ← triggers module loading
            install_modules=config['init'],    # e.g., {'base': True}
            upgrade_modules=config['update'],  # e.g., {'sale': 'upgrade'}
            reinit_modules=config['reinit'],   # re-init modules
        )
```

## Stage 5: `Registry.new()` → `load_modules()`

**Source**: `odoo/orm/registry.py:129` + `odoo/modules/loading.py`

```python
# odoo/orm/registry.py
def new(db_name, update_module=False, install_modules=None, ...):
    # ... registry creation ...
    if first_registry and not update_module:
        pass  # reuse existing registry
    else:
        load_modules(
            cr, registry,
            update_module=update_module,
            install_modules=install_modules,
            ...)
```

See [module-loading-sequence](module-loading-sequence.md) for full detail of `load_modules()`.

## Stage 6: HTTP Server

```python
# After Registry ready:
server.start()

# Types of servers:
# - GeventServer: evented/async mode
# - PreforkServer: multiprocessing (workers mode)
# - ThreadedServer: single-process with threads
```

### HTTP Endpoints Available

```
8069/tcp   HTTP    → web.WebClient + all web controllers
8071/tcp   XMLRPC  → rpc.XMLRPCController
8072/tcp   Longpolling → bus polling (WebSocket via polling)
```

## Startup Timeline (in order)

| Step | Action | File |
|------|--------|------|
| 1 | Parse config, init logging | `tools/config.py` |
| 2 | Initialize database connection pool | `sql_db.py` |
| 3 | Load server-wide Python modules | `server.py:load_server_wide_modules()` |
| 4 | Register HTTP routes/controllers | `http.py` (after web import) |
| 5 | Create Registry for database | `orm/registry.py:new()` |
| 6 | Load 'base' module | `loading.py:load_modules()` |
| 7 | Cascade install auto-install deps | `loading.py` |
| 8 | Apply migrations | `migration.py` |
| 9 | Start HTTP server | `server.py:start()` |
| 10 | Spawn cron workers | `server.py` |

## Minimal vs Full Startup

| Aspect | Minimal (14 modules) | Full (~300 modules) |
|--------|--------------------|--------------------|
| **Modules loaded** | 14 | ~300 |
| **Registry build time** | ~1-3s | ~10-30s |
| **Tables created** | ~50 | ~300+ |
| **Startup memory** | ~100-200MB | ~500-1000MB |
| **Asset bundles** | 14 modules' assets | All modules' assets |
| **HTTP ready at** | ~5-10s | ~30-60s |

## Preload Database Option

```bash
# Preload database at startup (without starting HTTP)
odoo --preload-db=mydb --stop-after-init

# This runs: Registry.new('mydb', update_module=False)
# Skips HTTP server, useful for scripts
```

## Watchdog (Dev Mode)

In development mode, Odoo uses `watchdog` to monitor file changes:

```python
# odoo/service/server.py
if inotify:
    inotify_adapter = inotify.Adapter()
    inotify_adapter.add_watch(addons_path, INOTIFY_LISTEN_EVENTS)
elif watchdog:
    observer = Observer()
    for path in addons_path:
        observer.schedule(handler, path, recursive=True)
    observer.start()
```

File changes trigger registry reload without full restart.

## Relasi dengan Konsep Lain

- [module-loading-sequence](module-loading-sequence.md) — load_modules() detail (STEP 1-6)
- [server-wide-modules](Core/Server-Wide-Modules.md) — server_wide_modules = ['base', 'rpc', 'web']
- [odoo-minimal-installation](odoo-minimal-installation.md) — 14 modules loaded in minimal vs ~300 in full
- [ir-module-module-deep-dive](ir-module-module-deep-dive.md) — Registry.new() creates module records
- [manifest-schema](Snippets/Manifest-Schema.md) — bootstrap=True loads translations before login
