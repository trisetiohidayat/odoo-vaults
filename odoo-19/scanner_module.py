"""Scan Odoo addons directory and return list of module names.

Args:
    addons_path: Path to addons directory. Defaults to ~/odoo/odoo19/odoo/addons/

Returns:
    Sorted list of module directory names (excludes __pycache__, hidden dirs, etc.)

Raises:
    NotADirectoryError: If addons_path does not exist or is not a directory
"""
import os


def scan_modules(addons_path: str | None = None) -> list[str]:
    """Return list of module names from addons directory."""
    if not addons_path:
        addons_path = os.path.expanduser("~/odoo/odoo19/odoo/addons/")

    if not os.path.isdir(addons_path):
        raise NotADirectoryError(f"Addons path does not exist or is not a directory: {addons_path}")

    modules = []
    for name in os.listdir(addons_path):
        path = os.path.join(addons_path, name)
        if os.path.isdir(path) and not name.startswith(('_', '.')):
            modules.append(name)

    return sorted(modules)


if __name__ == "__main__":
    modules = scan_modules()
    print(f"Found {len(modules)} modules")
    print(modules[:20])
