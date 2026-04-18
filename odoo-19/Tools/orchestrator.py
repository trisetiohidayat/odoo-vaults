#!/usr/bin/env python3
"""
orchestrator.py — Auto-fill vault documentation by connecting research tools.

Pipeline:
  gap_analyzer  →  scan stubs + check completeness
  scanner_model →  extract models/fields/methods from source
  doc_generator  →  produce markdown from scanned data
  checkpoint    →  save progress, resume on restart

Usage:
    python3 orchestrator.py --list              # Show gaps without running
    python3 orchestrator.py --module sale       # Fill specific module
    python3 orchestrator.py --stubs-only        # Only fill non-l10n stubs
    python3 orchestrator.py --dry-run          # Preview without writing
    python3 orchestrator.py --resume            # Resume from checkpoint

Config:
    ODOO_SOURCE   = /Users/tri-mac/odoo/odoo19/odoo/addons
    VAULT_ROOT    = /Users/tri-mac/odoo-vaults/odoo-19
    VAULT_MODULES = VAULT_ROOT/Modules
    CHECKPOINT    = VAULT_ROOT/.orchestrator_checkpoint.json
"""

import os
import re
import sys
import json
import time
import argparse
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path

# ── CONFIG ───────────────────────────────────────────────────────────────────

ODOO_SOURCE   = Path("/Users/tri-mac/odoo/odoo19/odoo/addons")
VAULT_ROOT    = Path("/Users/tri-mac/odoo-vaults/odoo-19")
VAULT_MODULES = VAULT_ROOT / "Modules"
CHECKPOINT_FILE = VAULT_ROOT / ".orchestrator_checkpoint.json"

# Skip these prefixes (too low-value to auto-generate)
SKIP_PREFIXES = ("l10n_", "test_")

# Minimum size to consider a module "documented"
MIN_DOC_SIZE = 15_000  # bytes

# ── SCANNERS ──────────────────────────────────────────────────────────────────

def scan_source_modules():
    """Return sorted list of module names from Odoo source."""
    modules = []
    for d in sorted(ODOO_SOURCE.iterdir()):
        if d.is_dir() and (d / "__manifest__.py").exists():
            modules.append(d.name)
    return modules


def scan_stub_modules():
    """Return list of stub modules (non-l10n, < 2KB, < 150 words)."""
    stubs = []
    for f in VAULT_MODULES.glob("*.md"):
        name = f.stem.replace(" ", "-")
        if name.startswith(SKIP_PREFIXES):
            continue
        sz = f.stat().st_size
        wc = len(f.read_text(errors="ignore").split())
        if sz < 2000 and wc < 150:
            stubs.append(name)
    return stubs


def scan_module_models(module_name):
    """Scan a module and return its models with fields and methods.

    Handles both standalone models (_name) and extension models (_inherit).
    """
    module_path = ODOO_SOURCE / module_name / "models"
    if not module_path.exists():
        return []

    models = []
    for py_file in sorted(module_path.glob("*.py")):
        if py_file.name == "__init__.py":
            continue

        content = py_file.read_text(errors="ignore")
        class_pattern = re.compile(
            r"^class\s+([A-Z][A-Za-z0-9_]+)\s*\([^)]*models[^)]*\):",
            re.MULTILINE,
        )

        for match in class_pattern.finditer(content):
            class_name = match.group(1)
            class_start = match.start()
            next_class = class_pattern.search(content[class_start + 1:])
            end = class_start + 1 + (next_class.start() if next_class else len(content))
            class_body = content[class_start:end]

            # Determine model name
            name_match = re.search(r'_name\s*=\s*["\']([^"\']+)["\']', class_body)
            if name_match:
                model_name = name_match.group(1)
            else:
                inherit_match = re.search(r'_inherit\s*=\s*["\']([^"\']+)["\']', class_body)
                if inherit_match:
                    model_name = inherit_match.group(1)
                else:
                    model_name = class_name  # fallback

            # Fields — match field definitions
            fields = []
            field_pattern = re.compile(r"^(\s*)(\w+)\s*=\s*(?:fields\.)?(\w+)\(", re.MULTILINE)
            for fm in field_pattern.finditer(class_body):
                fname, ftype = fm.group(2), fm.group(3)
                if fname.startswith("_") or not ftype[0].isupper():
                    continue
                field_def = class_body[fm.start() : fm.start() + 300]
                fields.append({
                    "name": fname,
                    "type": ftype,
                    "compute": "compute" in field_def,
                    "onchange": "onchange" in field_def,
                    "related": "related" in field_def,
                    "store": "store" in field_def,
                    "required": "required" in field_def,
                    "inverse": "inverse" in field_def,
                    "selection": "selection" in field_def and ftype == "Selection",
                })

            # Methods — match public methods
            methods = []
            method_pattern = re.compile(r"^    def\s+(\w+)\s*\(self[^)]*\):", re.MULTILINE)
            for mm in method_pattern.finditer(class_body):
                mname = mm.group(1)
                if not mname.startswith("_"):
                    methods.append({"name": mname})

            # Docstring
            docm = re.search(r'"""(.*?)"""', class_body, re.DOTALL)
            docstring = docm.group(1).strip()[:200] if docm else ""

            models.append({
                "name": model_name,
                "class": class_name,
                "file": py_file.name,
                "fields": fields,
                "methods": methods,
                "description": docstring,
                "field_count": len(fields),
                "method_count": len(methods),
            })

    return models


# ── TEMPLATES ──────────────────────────────────────────────────────────────────

MODEL_SECTION = """### {model_name} (`{model_name}`)

{description}

**File:** `{file}` | Class: `{class_name}`

#### Fields ({count})

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
{field_rows}

#### Methods ({method_count})

| Method | Description |
|--------|-------------|
{method_rows}

"""

MODULE_TEMPLATE = """---
title: "{title}"
module: {module}
type: module
generated: {today}
generator: orchestrator.py
---

# {title}

## Overview

Module `{module}` — auto-generated from source code.

**Source:** `addons/{module}/`
**Models:** {model_count}
**Fields:** {field_count}
**Methods:** {method_count}

## Models

{content}

## Related

- [[Modules/Base]]
- [[Modules/{category}]]
"""


def generate_module_doc(module_name, models):
    """Generate markdown for a module."""
    today = date.today().isoformat()
    title = " ".join(p.capitalize() for p in module_name.replace("_", " ").split())

    content = ""
    total_fields = 0
    total_methods = 0

    for model in models[:20]:  # cap at 20 models
        field_rows = ""
        for f in model["fields"][:40]:  # cap at 40 fields
            total_fields += 1
            field_rows += (
                f"| `{f['name']}` | `{f['type']}` "
                f"| {'Y' if f['compute'] else '—'} "
                f"| {'Y' if f['onchange'] else '—'} "
                f"| {'Y' if f['related'] else '—'} "
                f"| {'Y' if f['store'] else '—'} "
                f"| {'Y' if f['required'] else '—'} |\n"
            )

        method_rows = ""
        for m in model["methods"][:15]:
            total_methods += 1
            method_rows += f"| `{m['name']}` | |\n"

        if not field_rows:
            field_rows = "| — | — | — | — | — | — | — |\n"
        if not method_rows:
            method_rows = "| — | — |\n"

        content += MODEL_SECTION.format(
            model_name=model["name"],
            file=model["file"],
            class_name=model["class"],
            description=model["description"] or "—",
            count=len(model["fields"]),
            field_rows=field_rows,
            method_count=len(model["methods"]),
            method_rows=method_rows,
        )

    if not content:
        content = "\n*No models found in this module.*\n"

    # Category for "Related" link
    category_map = {
        "sale": "Sale", "stock": "Stock", "account": "Account",
        "purchase": "Purchase", "mrp": "MRP", "crm": "CRM",
        "hr": "HR", "project": "Project", "website": "Website",
    }
    category = next(
        (v for k, v in category_map.items() if module_name.startswith(k)),
        "Base",
    )

    return MODULE_TEMPLATE.format(
        title=title,
        module=module_name,
        today=today,
        content=content,
        model_count=len(models),
        field_count=total_fields,
        method_count=total_methods,
        category=category,
    )


# ── CHECKPOINT ─────────────────────────────────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        return json.loads(CHECKPOINT_FILE.read_text())
    return {"done": [], "failed": []}


def save_checkpoint(state):
    state["last_run"] = datetime.now().isoformat()
    CHECKPOINT_FILE.write_text(json.dumps(state, indent=2))


# ── ORCHESTRATOR ─────────────────────────────────────────────────────────────

def process_module(module_name, dry_run=False, verbose=False):
    """Run pipeline for one module. Returns status string."""
    dest_file = VAULT_MODULES / f"{module_name}.md"

    if verbose:
        print(f"Processing: {module_name}")

    # Skip if already well-documented
    if dest_file.exists() and dest_file.stat().st_size >= MIN_DOC_SIZE:
        if verbose:
            print(f"  skip — already {dest_file.stat().st_size}B")
        return "skipped"

    # Scan source
    models = scan_module_models(module_name)
    if not models:
        if verbose:
            print(f"  fail — no models found in source")
        return "failed"

    if verbose:
        print(
            f"  {len(models)} models, "
            f"{sum(m['field_count'] for m in models)} fields, "
            f"{sum(m['method_count'] for m in models)} methods"
        )

    content = generate_module_doc(module_name, models)

    if dry_run:
        if verbose:
            print(f"  dry-run — would write {len(content)} chars")
        return "done"

    dest_file.write_text(content, encoding="utf-8")
    if verbose:
        print(f"  done — wrote {len(content)} chars → {dest_file.name}")
    return "done"


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Odoo 19 Vault Orchestrator")
    ap.add_argument("--module", "-m", help="Process specific module only")
    ap.add_argument(
        "--stubs-only", action="store_true",
        help="Only fill non-l10n stub files",
    )
    ap.add_argument(
        "--list", action="store_true",
        help="Show gaps and exit",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing",
    )
    ap.add_argument(
        "--verbose", "-v", action="store_true",
        help="Verbose output",
    )
    args = ap.parse_args()

    print("=" * 65)
    print("  ODOO 19 VAULT ORCHESTRATOR")
    print("=" * 65)

    # ── LIST mode ────────────────────────────────────────────────────────────
    if args.list:
        stubs = scan_stub_modules()
        all_modules = scan_source_modules()

        print(f"\nSource modules: {len(all_modules)}")
        print(f"Non-l10n stubs:  {len(stubs)}")
        print()

        if stubs:
            print("Stub files:")
            for s in sorted(stubs):
                f = VAULT_MODULES / f"{s}.md"
                sz = f.stat().st_size if f.exists() else 0
                wc = len(f.read_text(errors="ignore").split()) if f.exists() else 0
                print(f"  {sz:5d}B {wc:4d}w  {s}")
        else:
            print("No stubs found. All modules appear documented.")
        return

    # ── Build target list ────────────────────────────────────────────────────
    checkpoint = load_checkpoint()
    done = set(checkpoint["done"])
    failed = set(checkpoint["failed"])

    if args.module:
        targets = [args.module]
    elif args.stubs_only:
        targets = [
            s for s in scan_stub_modules()
            if s not in done and s not in failed
        ]
        print(f"\nStub modules to fill: {len(targets)}")
    else:
        # All modules not well-documented
        targets = []
        for mod in scan_source_modules():
            if mod in done or mod in failed:
                continue
            if mod.startswith(SKIP_PREFIXES):
                continue
            f = VAULT_MODULES / f"{mod}.md"
            if not f.exists() or f.stat().st_size < MIN_DOC_SIZE:
                targets.append(mod)
        print(f"\nModules to process: {len(targets)}")

    if not targets:
        print("Nothing to do.")
        return

    # ── Run pipeline ──────────────────────────────────────────────────────────
    print(f"\nRunning pipeline on {len(targets)} module(s)...\n")
    results = defaultdict(int)

    for i, module_name in enumerate(targets):
        status = process_module(module_name, dry_run=args.dry_run, verbose=args.verbose)
        results[status] += 1

        if status == "done":
            done.add(module_name)
        elif status == "failed":
            failed.add(module_name)

        # Checkpoint every 10 modules
        if (i + 1) % 10 == 0:
            save_checkpoint({"done": list(done), "failed": list(failed)})
            print(f"  [checkpoint] done={len(done)}, failed={len(failed)}")

    save_checkpoint({"done": list(done), "failed": list(failed)})

    print(f"\n{'=' * 65}")
    print(f"  FINISHED")
    print(f"  done:     {results['done']}")
    print(f"  skipped:  {results['skipped']}")
    print(f"  failed:   {results['failed']}")
    print(f"  checkpoint: {CHECKPOINT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()