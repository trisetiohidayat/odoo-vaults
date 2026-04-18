#!/usr/bin/env python3
"""
gap_analyzer.py — Analyze coverage gaps between Odoo 19 source and vault

Compares:
  1. Source: /Users/tri-mac/odoo/odoo19/odoo/addons/  (304 modules)
  2. Vault:  /Users/tri-mac/odoo-vaults/odoo-19/Modules/  (doc'd modules)

Outputs:
  - Missing modules (not documented in vault)
  - Partial modules (some models undocumented)
  - Priority based on core/commonly-used modules

Usage:
    python3 gap_analyzer.py [--verbose] [--format table|json|summary]
"""

import os
import re
import sys
import json
from pathlib import Path
from collections import defaultdict

# ── CONFIG ───────────────────────────────────────────────────────────────────

ODOO_SOURCE = Path("/Users/tri-mac/odoo/odoo19/odoo/addons")
VAULT_MODULES = Path("/Users/tri-mac/odoo-vaults/odoo-19/Modules")
VAULT_CORE = Path("/Users/tri-mac/odoo-vaults/odoo-19/Core")

# Core/essential modules — high priority
CORE_MODULES = {
    'base', 'web', 'rpc', 'bus', 'html_editor',
    'mail', 'sale', 'purchase', 'stock', 'mrp',
    'account', 'crm', 'project', 'hr', 'contacts',
    'uom', 'product', 'portal', 'website', 'payment',
}

# High-value modules — frequently used, should be documented
HIGH_VALUE_MODULES = {
    'sale_management', 'sale_loyalty', 'sale_rental',
    'stock_account', 'stock_landed_costs', 'stock_picking_batch',
    'mrp_subcontracting', 'mrp_repair',
    'account_payment', 'account_edi', 'account_peppol',
    'purchase_requisition', 'purchase_product_matrix',
    'crm_iap_enrich', 'crm_livechat',
    'hr_expense', 'hr_holidays', 'hr_timesheet', 'hr_skills',
    'project_timesheet', 'project_sale_subtask',
    'helpdesk', 'rating', 'survey', 'appointment',
    'pos_self_order', 'pos_restaurant',
    'website_sale', 'website_blog', 'website_forum', 'website_slides',
    'website_sale_stock', 'website_sale_wishlist',
    'mass_mailing', 'sms', 'marketing_automation',
    'spreadsheet', 'account_reports', 'account_asset',
}

# Pattern to extract model names from vault markdown
MODEL_PATTERN = re.compile(r'`([a-z][a-z0-9_.]+)`')

# Patterns that indicate model documentation sections
SECTION_PATTERNS = [
    re.compile(r'^##?\s+Model:\s*`?([a-z][a-z0-9_.]+)`?', re.MULTILINE),
    re.compile(r'^##?\s+\d+\.\s+\w+\s+\(`([a-z][a-z0-9_.]+)`\)', re.MULTILINE),
    re.compile(r'^###\s+\d+\.\s+([A-Z][a-zA-Z0-9_]+)\s+\(`([a-z][a-z0-9_.]+)`\)', re.MULTILINE),
]


# ── SCANNERS ──────────────────────────────────────────────────────────────────

def scan_source_modules(addons_path: Path):
    """Scan Odoo source for all available modules."""
    modules = {}
    for item in sorted(addons_path.iterdir()):
        if not item.is_dir():
            continue
        manifest_path = item / "__manifest__.py"
        if not manifest_path.exists():
            # Might be a python module only
            continue
        modules[item.name] = {
            'path': item,
            'manifest': manifest_path,
        }
    return modules


def scan_source_models(module_path: Path):
    """Scan a module for Python model files and extract model names."""
    models = {}
    models_dir = module_path / "models"
    if not models_dir.exists():
        return models

    for py_file in models_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")

        # Find class definitions that look like Odoo models
        # Pattern: class ModelName(models.Model): or class ModelName(Model):
        for match in re.finditer(r'^class\s+([A-Z][A-Za-z0-9_]+)\s*\(.*?Model', content, re.MULTILINE):
            model_name = match.group(1)
            # Convert CamelCase to snake_case for _name default, but we want the actual _name
            # Try to find _name = 'xxx' in the class body
            class_start = match.start()
            # Find the next class or end of file
            next_class = re.search(r'^class\s+', content[class_start + 1:], re.MULTILINE)
            if next_class:
                class_body = content[class_start:class_start + 1 + next_class.start()]
            else:
                class_body = content[class_start:]

            # Look for _name
            name_match = re.search(r"_name\s*=\s*['\"]([^'\"]+)['\"]", class_body)
            if name_match:
                model_name = name_match.group(1)
            else:
                # Fall back to snake_case of class name
                name_parts = re.findall(r'[A-Z][a-z0-9]*', model_name)
                model_name = '.'.join(n.lower() for n in name_parts)

            models[model_name] = {
                'file': str(py_file.relative_to(module_path)),
                'class_name': match.group(1),
            }
    return models


def scan_vault_modules(vault_modules_path: Path):
    """Scan vault for documented modules and their models.

    Normalizes filenames to lowercase for matching against source.
    Detects empty/stub files (0 bytes) as undocumented.
    """
    documented = {}
    for md_file in vault_modules_path.glob("*.md"):
        # Normalize: underscore, lowercase (matches Odoo module naming)
        module_name = md_file.stem.replace(' ', '-').replace('_', '-').lower()
        content = md_file.read_text(encoding="utf-8", errors="ignore")
        file_size = md_file.stat().st_size

        # Extract models from content
        models = set()
        for pattern in SECTION_PATTERNS:
            for m in pattern.finditer(content):
                groups = [g for g in m.groups() if g]
                models.update(groups)

        # Also scan for `model.name` patterns in the content
        for model_ref in MODEL_PATTERN.finditer(content):
            models.add(model_ref.group(1))

        documented[module_name] = {
            'file': md_file,
            'models': models,
            'size': file_size,
            'has_frontmatter': content.startswith('---'),
            'is_stub': (file_size < 2000 and len(content.split()) < 150),
            'word_count': len(content.split()),
        }
    return documented


def scan_vault_core(vault_core_path: Path):
    """Scan Core/ directory for framework docs."""
    core_docs = {}
    for md_file in vault_core_path.glob("*.md"):
        core_docs[md_file.stem] = {
            'file': md_file,
            'size': md_file.stat().st_size,
        }
    return core_docs


# ── GAP ANALYSIS ─────────────────────────────────────────────────────────────

def classify_priority(module_name: str) -> str:
    if module_name in CORE_MODULES:
        return "CRITICAL"
    if module_name in HIGH_VALUE_MODULES:
        return "HIGH"
    # Check by category (l10n, website_, etc.)
    if module_name.startswith('l10n_'):
        return "MEDIUM"
    if module_name.startswith(('website_', 'spreadsheet')):
        return "MEDIUM"
    if module_name.startswith('account'):
        return "MEDIUM"
    if module_name.startswith(('sale_', 'purchase_', 'stock_', 'mrp_')):
        return "MEDIUM"
    if module_name.startswith(('hr_', 'project_', 'helpdesk', 'rating')):
        return "MEDIUM"
    return "LOW"


def build_category(module_name: str) -> str:
    if module_name in {'base', 'web', 'rpc', 'bus', 'mail', 'portal', 'contacts'}:
        return "Core Infrastructure"
    if module_name in {'account', 'account_payment', 'account_edi', 'account_asset'}:
        return "Accounting"
    if module_name.startswith('l10n'):
        return "Localization"
    if module_name.startswith('sale'):
        return "Sales"
    if module_name.startswith('purchase'):
        return "Purchase"
    if module_name.startswith('stock'):
        return "Inventory"
    if module_name.startswith('mrp'):
        return "Manufacturing"
    if module_name.startswith('crm') or module_name in {'helpdesk', 'rating', 'survey'}:
        return "CRM/Service"
    if module_name.startswith('hr'):
        return "HR"
    if module_name.startswith('project'):
        return "Project"
    if module_name.startswith('website'):
        return "Website/E-commerce"
    if module_name in {'point_of_sale', 'pos_self_order', 'pos_restaurant'}:
        return "POS"
    if module_name.startswith(('mass_mailing', 'sms', 'marketing')):
        return "Marketing"
    return "Other"


# ── OUTPUT FORMATS ────────────────────────────────────────────────────────────

def format_table(gaps, modules_by_cat, vault_modules):
    lines = []
    lines.append("=" * 80)
    lines.append("ODOO 19 VAULT GAP ANALYSIS")
    lines.append("=" * 80)
    lines.append(f"Source:   {ODOO_SOURCE}  ({ODOO_SOURCE.exists() and 'exists' or 'NOT FOUND'})")
    lines.append(f"Vault:    {VAULT_MODULES}")
    lines.append("")

    total_source = len(modules_by_cat)
    total_documented = len(gaps['documented'])
    total_missing = len(gaps['missing'])
    total_stubs = len(gaps['stubs'])
    total_vault = total_documented + total_stubs

    lines.append(f"Source modules:    {total_source}")
    lines.append(f"Vault entries:     {total_vault}  (documented: {total_documented}, stubs: {total_stubs})")
    lines.append(f"Missing:           {total_missing}")
    lines.append(f"Real coverage:     {total_documented}/{total_source} = {total_documented/total_source*100:.1f}%")
    lines.append("")

    # Stubs
    if gaps['stubs']:
        lines.append("-" * 80)
        lines.append(f"STUBS ({total_stubs} modules — empty or near-empty files)")
        lines.append("-" * 80)
        lines.append(f"{'Module':<40} {'Size':>8}  {'Action'}")
        lines.append("-" * 60)
        for stub in sorted(gaps['stubs']):
            # Find the stub entry
            info = vault_modules.get(stub, vault_modules.get(stub.replace('_','-'), {}))
            sz = info.get('size', 0) if info else 0
            lines.append(f"  {stub:<38} {sz:6d}B  → needs documentation")

    # Missing modules by priority
    lines.append("")
    lines.append("-" * 80)
    lines.append("MISSING MODULES BY PRIORITY")
    lines.append("-" * 80)

    for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        missing = [m for m in gaps['missing'] if classify_priority(m) == priority]
        if not missing:
            continue
        lines.append(f"\n[{priority}] ({len(missing)} modules)")
        lines.append(f"{'Module':<35} {'Category':<22} {'Models'}")
        lines.append("-" * 65)
        for module in sorted(missing)[:20]:
            source_path = ODOO_SOURCE / module
            model_count = 0
            if source_path.exists():
                models = scan_source_models(source_path)
                model_count = len(models)
            cat = build_category(module)
            lines.append(f"  {module:<33} {cat:<22} {model_count}")
        if len(missing) > 20:
            lines.append(f"  ... and {len(missing) - 20} more missing modules")
    lines.append("")

    # Top categories with most gaps
    lines.append("-" * 80)
    lines.append("CATEGORIES WITH MOST MISSING MODULES")
    lines.append("-" * 80)
    cat_counts = defaultdict(int)
    for m in gaps['missing']:
        cat_counts[build_category(m)] += 1
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        lines.append(f"  {cat:<25} {count:3d}  {bar}")

    return "\n".join(lines)


def format_json(gaps, modules_by_cat):
    return json.dumps({
        "source_modules": len(modules_by_cat),
        "documented_modules": len(gaps['documented']),
        "stub_modules": len(gaps['stubs']),
        "missing_modules": sorted(gaps['missing']),
        "stub_list": sorted(gaps['stubs']),
        "coverage_pct": round(len(gaps['documented']) / len(modules_by_cat) * 100, 1),
        "missing_by_priority": {
            p: sorted([m for m in gaps['missing'] if classify_priority(m) == p])
            for p in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        }
    }, indent=2)


def format_summary(gaps, modules_by_cat, vault_modules):
    total = len(modules_by_cat)
    documented = len(gaps['documented'])
    missing = len(gaps['missing'])
    stubs = len(gaps['stubs'])

    lines = []
    lines.append("=" * 65)
    lines.append(f"  GAP SUMMARY: Odoo 19 Vault vs Source")
    lines.append("=" * 65)
    lines.append(f"  Source total modules:       {total}")
    lines.append(f"  Already documented:         {documented} ({documented/total*100:.1f}%)")
    lines.append(f"  Stub files (needs content): {stubs}")
    lines.append(f"  Missing (not in vault):     {missing} ({missing/total*100:.1f}%)")
    lines.append("=" * 65)

    if stubs:
        lines.append("")
        lines.append("  STUB FILES (empty / minimal content):")
        for s in sorted(gaps['stubs']):
            info = vault_modules.get(s, vault_modules.get(s.replace('_','-'), {}))
            sz = info.get('size', 0) if info else 0
            lines.append(f"    ⚠️  {s}  ({sz}B)")

    if missing:
        lines.append("")
        lines.append("  MISSING MODULES:")
        for p in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            mods = sorted([m for m in missing if classify_priority(m) == p])
            if not mods:
                continue
            lines.append(f"  [{p}] ({len(mods)})")
            for m in mods[:8]:
                lines.append(f"    - {m}")
            if len(mods) > 8:
                lines.append(f"    ... +{len(mods)-8} more")

    return "\n".join(lines)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main(fmt: str = "summary", verbose: bool = False):
    print("Scanning Odoo 19 source...", file=sys.stderr)
    source_modules = scan_source_modules(ODOO_SOURCE)
    print(f"  Found {len(source_modules)} modules in source", file=sys.stderr)

    print("Scanning vault...", file=sys.stderr)
    vault_modules = scan_vault_modules(VAULT_MODULES)
    print(f"  Found {len(vault_modules)} modules documented in vault", file=sys.stderr)

    vault_core = scan_vault_core(VAULT_CORE)

    # Categorize: documented vs missing
    # Also detect stubs (empty or near-empty files treated as undocumented)
    missing = []
    documented = []
    stubs = []

    for module_name in sorted(source_modules.keys()):
        # Normalize for matching: Odoo uses underscores, vault may have hyphens
        # Try: exact, underscore->hyphen, hyphen->underscore, lowercase
        candidates = [
            module_name,
            module_name.replace('_', '-'),
            module_name.replace('-', '_'),
            module_name.lower(),
        ]
        matched_key = None
        for c in candidates:
            if c in vault_modules:
                matched_key = c
                break

        if matched_key is None:
            missing.append(module_name)
        else:
            info = vault_modules[matched_key]
            if info['is_stub']:
                stubs.append(module_name)
            else:
                documented.append(module_name)

    gaps = {
        "missing": missing,        # Not in vault at all
        "documented": documented,  # Has real content
        "stubs": stubs,            # In vault but empty/stub
    }

    # Print results
    if fmt == "table":
        print(format_table(gaps, source_modules, vault_modules))
    elif fmt == "json":
        print(format_json(gaps, source_modules))
    else:
        print(format_summary(gaps, source_modules, vault_modules))

    return gaps


if __name__ == "__main__":
    fmt = "summary"
    verbose = False

    for arg in sys.argv[1:]:
        if arg in ("-v", "--verbose"):
            verbose = True
        elif arg in ("--format=table", "--format=json", "--format=summary"):
            fmt = arg.split("=")[1]

    gaps = main(fmt, verbose)