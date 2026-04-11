"""Gap Detection Engine.

Compares Odoo code (scanned via module_scanner / model_scanner)
against the Obsidian vault documentation to identify coverage gaps:
- Missing modules (in code but not documented in vault)
- Missing models  (module documented but model not described)
"""

import os
import re
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

CORE_MODULES: set[str] = {
    'base', 'product', 'stock', 'sale', 'purchase',
    'account', 'mrp', 'crm',
}


def is_core_module(module_name: str) -> bool:
    """Return True when module_name is a core Odoo module."""
    return module_name in CORE_MODULES


# ---------------------------------------------------------------------------
# Vault introspection
# ---------------------------------------------------------------------------

def get_vault_modules(vault_path: str) -> list[str]:
    """
    Return all documented module names found in vault/Modules/.

    Each *.md file in that directory represents one documented module;
    the filename (minus .md) is normalised to lowercase to match Odoo's
    technical module naming convention.
    """
    modules_dir = os.path.join(vault_path, "Modules")
    if not os.path.isdir(modules_dir):
        return []
    return sorted(
        f.replace(".md", "").lower()
        for f in os.listdir(modules_dir)
        if f.endswith(".md") and f not in ("00 - DOC PLAN.md",)
    )


def _find_module_file(vault_path: str, module_name: str) -> str | None:
    """
    Locate a module's .md file in vault/Modules/.

    Tries the exact module_name first, then title-cased and all-lowercase
    variants to accommodate case-preserving-but-insensitive filesystems
    (e.g. macOS APFS).
    """
    modules_dir = os.path.join(vault_path, "Modules")
    candidates = [
        f"{module_name}.md",
        f"{module_name.capitalize()}.md",
    ]
    for candidate in candidates:
        filepath = os.path.join(modules_dir, candidate)
        if os.path.isfile(filepath):
            return filepath
    return None


def get_vault_models(vault_path: str, module_name: str) -> list[str]:
    """
    Return all model technical names documented inside a module's .md file.

    Recognised patterns (case-sensitive):
      ### N. Display Name (`model.name`)
      #### Display Name (`model.name`)
      ## Model: model.name

    Returns the ``model.name`` portion from each match.
    """
    filepath = _find_module_file(vault_path, module_name)
    if filepath is None:
        return []

    with open(filepath, encoding="utf-8") as fh:
        content = fh.read()

    models: list[str] = []

    # Pattern 1: ### N. Display Name (`model.name`)
    #            #### Display Name (`model.name`)
    pattern_inline = r'`([a-z][a-z0-9_]+\.[a-z][a-z0-9_.]+)`'
    for match in re.finditer(pattern_inline, content):
        candidate = match.group(1)
        if candidate not in models:
            models.append(candidate)

    # Pattern 2: ## Model: model.name
    pattern_keyword = (
        r'^##\s+Model:\s*([a-z][a-z0-9_]+\.[a-z][a-z0-9_.]+)',
        re.MULTILINE,
    )
    for match in re.finditer(pattern_keyword[0], content, pattern_keyword[1]):
        candidate = match.group(1)
        if candidate not in models:
            models.append(candidate)

    return models


# ---------------------------------------------------------------------------
# Main detection engine
# ---------------------------------------------------------------------------

def detect_gaps(
    module_scanner: Callable[[], Iterable[str]],
    model_scanner: Callable[[str], list[dict]],
    vault_path: str,
) -> list[dict]:
    """
    Compare live code against vault documentation and return a list of gaps.

    Parameters
    ----------
    module_scanner
        Callable returning an iterable of module technical names from the
        Odoo codebase (e.g. ``scanner_module.scan_modules``).
    model_scanner
        Callable taking a module name and returning a list of model dicts,
        each with at least a ``'name'`` key (e.g. ``scanner_model.scan_models``).
    vault_path
        Absolute path to the Obsidian vault root.

    Returns
    -------
    list[dict]
        Each dict has the shape::

            {
                'type':      'missing_module' | 'missing_model',
                'module':    str,           # module technical name
                'model':     str | None,     # only for 'missing_model'
                'priority':  'critical' | 'high' | 'medium' | 'low',
                'description': str,
            }

    Gaps are ordered: critical first, then high, medium, low, then
    alphabetically by module / model name within each priority band.
    """
    gaps: list[dict] = []

    # 1. Collect code modules
    code_modules = set(module_scanner())
    vault_modules = set(get_vault_modules(vault_path))

    # ------------------------------------------------------------------
    # Category 1 – modules that exist in code but have no vault entry
    # ------------------------------------------------------------------
    missing_modules = code_modules - vault_modules
    for mod in sorted(missing_modules):
        priority = "critical" if is_core_module(mod) else "high"
        gaps.append({
            "type": "missing_module",
            "module": mod,
            "model": None,
            "priority": priority,
            "description": f"Module '{mod}' exists in Odoo code but has no "
                           f"vault documentation entry.",
        })

    # ------------------------------------------------------------------
    # Category 2 – modules that are documented; check for missing models
    # ------------------------------------------------------------------
    documented_modules = code_modules & vault_modules
    for mod in sorted(documented_modules):
        code_models = {m["name"] for m in model_scanner(mod)}
        vault_models = set(get_vault_models(vault_path, mod))

        missing_models = code_models - vault_models
        for model in sorted(missing_models):
            gaps.append({
                "type": "missing_model",
                "module": mod,
                "model": model,
                "priority": "high",
                "description": f"Model '{model}' exists in module '{mod}' "
                               f"but is not documented in the vault.",
            })

    # ------------------------------------------------------------------
    # Sort: critical → high → medium → low, then alphabetically
    # ------------------------------------------------------------------
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def sort_key(gap: dict) -> tuple:
        secondary = (
            (gap["module"], gap.get("model") or "")
            if gap["type"] == "missing_model"
            else (gap["module"], "")
        )
        return (priority_order.get(gap["priority"], 99), secondary)

    gaps.sort(key=sort_key)
    return gaps


# ---------------------------------------------------------------------------
# Pretty-print utilities
# ---------------------------------------------------------------------------

def summarize(gaps: list[dict]) -> str:
    """Return a human-readable summary of the gap list."""
    if not gaps:
        return "No gaps found — vault documentation is complete!"

    counts: dict[str, dict[str, int]] = {}
    for g in gaps:
        p = g["priority"]
        counts.setdefault(p, {})
        counts[p][g["type"]] = counts[p].get(g["type"], 0) + 1

    lines = [
        f"Gap Detection Summary",
        f"{'=' * 50}",
        f"Total gaps: {len(gaps)}",
        "",
    ]
    for priority in ("critical", "high", "medium", "low"):
        if priority in counts:
            lines.append(f"  [{priority.upper()}]")
            for kind, cnt in sorted(counts[priority].items()):
                lines.append(f"    {kind}: {cnt}")
            lines.append("")

    lines.append("Detailed listing:")
    lines.append("-" * 50)
    for g in gaps:
        if g["type"] == "missing_module":
            lines.append(
                f"  [{g['priority']:8s}] missing_module  {g['module']}"
            )
        else:
            lines.append(
                f"  [{g['priority']:8s}] missing_model   {g['module']}.{g['model']}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    vault_path = os.path.dirname(os.path.abspath(__file__))  # vault root (gap_detector.py lives here)

    # Import scanners from the vault root
    try:
        sys.path.insert(0, vault_path)
        from scanner_module import scan_modules
        from scanner_model import scan_models
    except ImportError as exc:
        sys.stderr.write(
            f"ERROR: Could not import scanners from vault root: {exc}\n"
        )
        sys.exit(1)

    gaps = detect_gaps(scan_modules, scan_models, vault_path)
    print(summarize(gaps))
