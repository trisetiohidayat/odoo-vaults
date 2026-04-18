---
title: "Odoo CLI Commands Reference — odoo-bin"
date: 2026-04-15
tags: [odoo, odoo19, cli, odoo-bin, command-line, shell, scaffold, module]
type: concept
sources: 1
synced_from: odoo-minimal
sync_date: 2026-04-17
source_path: wiki/concepts/odoo-cli-commands.md
---


# Odoo CLI Commands Reference — odoo-bin

## Overview

Odoo CLI via `odoo-bin` (or `odoo`) provides subcommands for server management, database operations, module management, shell access, and scaffolding. All commands support `--addons-path` as a shared global option.

**Source**: `odoo/cli/command.py` + `odoo/cli/*.py`

## Command Discovery

```python
# odoo/cli/command.py

# Command registration via subclassing
class Command:
    name = None          # CLI subcommand name
    description = None   # Help text
    epilog = None       # Footer text

    def __init_subclass__(cls):
        cls.name = cls.name or cls.__name__.lower()
        commands[cls.name] = cls  # Auto-register

    def run(self, args):
        """Override this to implement command logic."""
        raise NotImplementedError()
```

Commands are auto-discovered from:
1. `odoo/cli/<name>.py` — built-in commands
2. `<addon>/cli/<name>.py` — addon commands (via `--addons-path`)

## Command Architecture

```
odoo [global-options] <command> [command-options]

Global options:
  --addons-path=PATH1[,PATH2]  — addon directories (shared by all commands)
```

### main() Dispatch

```python
# odoo/cli/command.py:109-139
def main():
    args = sys.argv[1:]

    # Parse --addons-path first
    if args[0].startswith('--addons-path='):
        config._parse_config([args[0]])
        args = args[1:]

    # Determine command
    if args and not args[0].startswith('-'):
        command_name = args[0]   # odoo db → command="db"
        args = args[1:]
    elif '-h' in args or '--help' in args:
        command_name = 'help'
    else:
        command_name = 'server'  # Default command

    command = find_command(command_name)
    command().run(args)
```

## Built-in Commands

### 1. server (default)

Default command — starts the Odoo HTTP server.

```bash
odoo-bin                          # Default: starts server
odoo-bin --config=odoo.conf      # Use config file
odoo-bin -d mydb                 # Auto-create/open database
odoo-bin -i base                 # Install base module on startup
odoo-bin --dev=all               # Dev mode (reload, etc.)
odoo-bin --stop-after-init       # Stop after init (for scripts)
```

**Key options:**
- `--config FILE` — configuration file
- `-c FILE` — alias for --config
- `-d DB` — database name(s)
- `-i MODULES` — modules to install (`-i base`)
- `-u MODULES` — modules to upgrade
- `--stop-after-init` — exit after initialization
- `--dev-mode MODE` — dev mode: `reload`, `xml`, `qweb`, `werkzeug`, `all`
- `--load server-wide-module` — load server-wide modules (comma-separated)
- `--no-xmlrpc` / `--no-jsonrpc` — disable RPC endpoints
- `--proxy-mode` — enable reverse proxy mode (X-Forwarded-* headers)

### 2. db — Database Management

```bash
# Create and initialize
odoo-bin db init mydb                              # Create + install base modules
odoo-bin db init mydb --with-demo                  # With demo data
odoo-bin db init mydb --language de_DE             # Non-English
odoo-bin db init mydb --country ID --force         # Indonesian company

# Load dump
odoo-bin db load [-f] [-n] [dbname] <dump.zip>     # Load from file/URL
odoo-bin db load -n mydb https://example.com/dump.zip  # Load + neutralize

# Dump database
odoo-bin db dump mydb [path.zip]                   # Zip with filestore
odoo-bin db dump mydb --format dump                # pg_dump format
odoo-bin db dump mydb --no-filestore               # Without attachments

# Duplicate
odoo-bin db duplicate source_db target_db          # Copy database
odoo-bin db duplicate -f source_db target_db      # Force overwrite
odoo-bin db duplicate -n source_db target_db      # Neutralize on copy

# Rename
odoo-bin db rename old_name new_name              # Rename + filestore

# Drop
odoo-bin db drop mydb                             # Delete + filestore
```

### 3. shell — Interactive Python Shell

```bash
odoo-bin shell -d mydb                            # Interactive shell with env
odoo-bin shell                                    # No DB — limited
odoo-bin shell --shell-interface ipython          # Force IPython
odoo-bin shell --shell-interface bpython          # Force bpython
odoo-bin shell --shell-interface ptpython         # Force ptpython
odoo-bin shell --shell-file startup.py            # Run script on start
```

**Available in shell:**
```python
env           # odoo.api.Environment (admin)
self          # env.user
odoo / openerp  # the odoo module
env['res.partner'].search([])  # Full ORM access
env.cr                               # Database cursor
```

**Supported shells (in priority order):**
1. `ipython` — recommended, rich autocompletion
2. `ptpython` — alternative REPL
3. `bpython` — alternative REPL
4. `python` — standard library fallback

### 4. module — Module Management

```bash
# Install modules (requires running server or -d)
odoo-bin module install sale stock -d mydb

# Upgrade modules (re-loads code + data)
odoo-bin module upgrade base web -d mydb

# Uninstall modules
odoo-bin module uninstall sale -d mydb

# Force demo data
odoo-bin module force-demo -d mydb
```

### 5. scaffold — Generate Module Skeleton

```bash
odoo-bin scaffold my_module /path/to/addons/
```

Creates:
```
my_module/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── models.py
├── views/
│   └── views.xml
├── controllers/
│   ├── __init__.py
│   └── controllers.py
├── demo/
│   └── demo.xml
└── security/
    └── ir.model.access.csv
```

### 6. populate — Database Population

```bash
odoo-bin populate -d mydb                           # Fill with sample data
odoo-bin populate -d mydb --size=small            # small / medium / large
odoo-bin populate -d mydb sale,crm                # Only specific models
```

### 7. i18n — Internationalization

```bash
odoo-bin i18n [lang]                              # Update translation terms
odoo-bin i18n --languages=en_US,id_ID            # Specify languages
```

### 8. start — Quick Start

```bash
odoo-bin start                                     # Start server in current dir
odoo-bin start --addons-path=./custom_addons      # With custom addons
```

### 9. cloc — Count Lines of Code

```bash
odoo-bin cloc                                      # Count all modules
odoo-bin cloc addons/base                          # Specific module
odoo-bin cloc --addons-path=addons,custom         # Multiple paths
```

### 10. help — Help

```bash
odoo-bin help                                     # List all commands
odoo-bin help db                                  # Help for specific command
```

### 11. neutralize — Database Neutralization

```bash
odoo-bin neutralize -d mydb                       # Neutralize for production
# Disables:
# - Scheduled actions
# - External API credentials
# - Webhooks
# - Demo data flags
```

### 12. obfuscate — Data Obfuscation

```bash
odoo-bin obfuscate -d mydb                        # Anonymize personal data
```

### 13. deploy — Deployment

```bash
odoo-bin deploy <archive.zip> <destination>
```

### 14. upgrade_code — Code Upgrade Tool

```bash
odoo-bin upgrade_code <command>                   # Upgrade path management
```

## Key Server Config Options

```bash
# Database
-d, --database              # Database name
-F, --db-filter             # Regex filter for DB list
--db_host                   # PostgreSQL host
--db_port                   # PostgreSQL port
-u, --db_user               # PostgreSQL user
-w, --db_password           # PostgreSQL password
--db_sslmode                # SSL mode (require, prefer, disable)

# HTTP Server
--http-port PORT            # HTTP port (default 8069)
--longpolling-port PORT     # Bus notifications (default 8072)
-p, --proxy-port            # Reverse proxy port

# Server-wide modules
--load server_wide_modules  # Default: base,web,rpc

# Logging
--logfile FILE              # Log file
--log-level LEVEL           # debug, info, warning, error
--log-db DB                 # Log to DB (ir.logging)
--log-handler MODULE:LEVEL  # Per-module log level
--dev-mode [all,reload,...] # Development mode flags

# Performance
--workers N                 # Number of workers
--max-cron-threads N       # Max cron worker threads
--gevent N                  # Gevent mode (N workers)
--preload                   # Preload DB list
--no-xmlrpc                 # Disable XMLRPC
--no-jsonrpc                # Disable JSONRPC
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Database error |
| 77 | Skip/test not applicable |

## Minimal Environment — CLI Usage

For a minimal Odoo install:

```bash
# Start minimal server
odoo-bin -d mydb --no-xmlrpc

# Initialize new minimal DB
odoo-bin db init mydb --with-demo

# Shell access for debugging
odoo-bin shell -d mydb

# Module management
odoo-bin module install my_custom_module -d mydb
odoo-bin module upgrade my_custom_module -d mydb
```

## Relation dengan Konsep Lain

- [startup-sequence](Core/Startup-Sequence.md) — what happens after `odoo-bin server` runs
- [server-wide-modules](Core/Server-Wide-Modules.md) — `--load` option, REQUIRED_SERVER_WIDE_MODULES
- [custom-module-in-minimal-env](custom-module-in-minimal-env.md) — scaffolding a custom module
- [odoo-conf-minimal-reference](odoo-conf-minimal-reference.md) — odoo.conf equivalent of CLI options
