#!/usr/bin/env python3
"""
cross_vault_sync.py — Sync content from odoo-minimal to odoo-19 vault

Usage:
    python3 cross_vault_sync.py [--dry-run] [--verbose]

Syncs unique platform-infrastructure content from odoo-minimal wiki
into the odoo-19 vault, adding sync metadata frontmatter.
"""

import os
import re
import sys
from datetime import datetime, date
from pathlib import Path

# ── CONFIG ───────────────────────────────────────────────────────────────────

SRC_ROOT  = Path("/Users/tri-mac/odoo-minimal/wiki")
DST_ROOT  = Path("/Users/tri-mac/odoo-vaults/odoo-19")

IMPORTS = [
    # (source_path_relative_to_SRC/wiki/, dest_path_relative_to_DST/, category)
    # Core synthesis
    ("synthesis/odoo-minimal-complete-guide.md",
     "Core/Odoo-Minimal-Complete-Guide.md",
     "synthesis"),

    # Core concepts
    ("concepts/auto-install-mechanism.md",
     "Core/Auto-Install-Mechanism.md",
     "concept"),
    ("concepts/module-dependency-system.md",
     "Core/Module-Dependency-System.md",
     "concept"),
    ("concepts/manifest-schema.md",
     "Snippets/Manifest-Schema.md",
     "concept"),
    ("concepts/startup-sequence.md",
     "Core/Startup-Sequence.md",
     "concept"),
    ("concepts/odoo-cli-commands.md",
     "Snippets/CLI-Commands.md",
     "concept"),
    ("concepts/server-wide-modules.md",
     "Core/Server-Wide-Modules.md",
     "concept"),
]

# Files that link back to other odoo-minimal wiki pages via [[...]]
# We convert these to relative markdown links pointing to the same vault
WIKI_LINK_RE = re.compile(r'\[\[([^\]]+)\]\]')


def convert_wiki_links(content: str) -> str:
    """Convert [[page-name]] to relative markdown links."""
    def replacer(m):
        title = m.group(1)
        # Convert spaces to hyphens, lowercase for filename
        filename = title.lower().replace(" ", "-") + ".md"
        return f"[{title}]({filename})"
    return WIKI_LINK_RE.sub(replacer, content)


def add_sync_frontmatter(content: str, src_path: str) -> str:
    """Prepend or merge sync metadata into frontmatter."""
    today = date.today().isoformat()

    sync_fields = [
        "synced_from: odoo-minimal",
        f"sync_date: {today}",
        f"source_path: wiki/{src_path}",
        "type: synced",
    ]

    # Detect existing frontmatter
    lines = content.split('\n')
    if not (lines and lines[0].strip() == '---'):
        # No frontmatter — prepend one
        frontmatter_lines = ["---"] + sync_fields + ["---"]
        return '\n'.join(frontmatter_lines) + '\n\n' + content

    # Has frontmatter — find the closing ---
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break

    if end_idx is None:
        # Malformed frontmatter, just prepend
        frontmatter_lines = ["---"] + sync_fields + ["---"]
        return '\n'.join(frontmatter_lines) + '\n\n' + content

    # Existing frontmatter lines (before our sync fields)
    existing = lines[1:end_idx]

    # Merge: add sync fields, avoiding duplicates
    all_keys = set()
    merged = []
    for line in existing:
        key = line.split(':')[0].strip() if ':' in line else ''
        if key:
            all_keys.add(key)
        merged.append(line)

    for field in sync_fields:
        key = field.split(':')[0].strip()
        if key not in all_keys:
            merged.append(field)

    # Reconstruct
    new_frontmatter = '\n'.join(["---"] + merged + ["---"])
    return new_frontmatter + '\n\n' + '\n'.join(lines[end_idx + 1:])


def sync_file(src_path: Path, dst_path: Path, verbose: bool = False) -> bool:
    """Sync a single file. Returns True if changed."""
    if not src_path.exists():
        print(f"  [SKIP] Source not found: {src_path}")
        return False

    # Read source
    content = src_path.read_text(encoding="utf-8")

    # Convert wiki links → relative markdown links
    content = convert_wiki_links(content)

    # Add sync frontmatter
    content = add_sync_frontmatter(content, str(src_path.relative_to(SRC_ROOT)))

    # Ensure destination directory exists
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if destination exists and is identical
    if dst_path.exists() and dst_path.read_text(encoding="utf-8") == content:
        if verbose:
            print(f"  [OK]   {dst_path} (unchanged)")
        return False

    # Write
    dst_path.write_text(content, encoding="utf-8")
    if verbose:
        print(f"  [SYNC] {src_path} → {dst_path}")
    return True


def main(dry_run: bool = False, verbose: bool = False):
    print(f"Source:      {SRC_ROOT}")
    print(f"Destination: {DST_ROOT}")
    print(f"Mode:        {'DRY RUN' if dry_run else 'LIVE'}")
    print()

    if not SRC_ROOT.exists():
        print(f"ERROR: Source root not found: {SRC_ROOT}")
        sys.exit(1)

    if not DST_ROOT.exists():
        print(f"ERROR: Destination root not found: {DST_ROOT}")
        sys.exit(1)

    changed = 0
    skipped = 0

    for src_rel, dst_rel, category in IMPORTS:
        src_path = SRC_ROOT / src_rel
        dst_path = DST_ROOT / dst_rel

        print(f"Importing: {src_rel}")
        print(f"  → {dst_rel}")

        if src_path.exists():
            if not dry_run:
                synced = sync_file(src_path, dst_path, verbose)
                if synced:
                    changed += 1
                else:
                    skipped += 1
            else:
                print(f"  [DRY] Would sync: {src_rel} → {dst_rel}")
                changed += 1
        else:
            print(f"  [ERROR] Source not found: {src_path}")
            skipped += 1

    print()
    print(f"Done. changed={changed}, skipped={skipped}")

    if dry_run:
        print("(DRY RUN — no files written)")


if __name__ == "__main__":
    dry_run   = "--dry-run" in sys.argv
    verbose   = "--verbose" in sys.argv or "-v" in sys.argv

    main(dry_run=dry_run, verbose=verbose)