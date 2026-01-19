"""
Python Project Release Builder (Simplified)

This script scans Python files in the current directory (excluding itself),
detects top-level third-party imports (non-stdlib), and generates a
requirements.txt file listing them.
"""

import ast
import importlib.metadata
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Sequence

__version__ = "1.0.1"


def resolve_distribution(import_name: str, import_to_dist: Mapping[str, Sequence[str]]) -> str:
    """
    Resolve a top-level import name to its PyPI distribution name.
    Falls back to the import name if unresolved.
    """
    dists = import_to_dist.get(import_name)
    if dists and dists[0] != import_name:
        print(f"Resolved {import_name} to {dists[0]}")
        return dists[0]
    return import_name


def find_third_party_imports(file_path: str | Path) -> set[str]:
    """
    Return PyPI distribution names for top-level third-party imports
    using installed package metadata.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    stdlib = sys.stdlib_module_names
    import_to_dist = importlib.metadata.packages_distributions()
    third_party: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = (node.module,)
        else:
            continue

        for full_name in names:
            name = full_name.partition(".")[0]
            if name in stdlib:
                continue

            print(f"Found non-stdlib import: {name}")
            third_party.add(resolve_distribution(name, import_to_dist))

    return third_party


def write_requirements(non_std_modules: set[str], output_path: str | Path = "requirements.txt") -> None:
    """
    Write a requirements.txt file listing third-party modules.
    """
    path = Path(output_path)
    if not non_std_modules:
        print(f"No non-standard modules detected; {json.dumps(str(path))} not generated")
        return

    with path.open("w", encoding="utf-8", newline="\n") as f:
        for module in sorted(non_std_modules):
            f.write(f"{module}\n")

    print(f"Generated requirements file: {json.dumps(str(path))}")


def main():
    """Scan Python files and generate requirements.txt for third-party imports."""
    current_file = Path(__file__).name
    print("Scanning current directory for Python files...")
    python_files = [
        Path(f) for f in os.listdir(".")
        if f.endswith((".py", ".pyw")) and f != current_file and f != "generate_requirements.txt.pyw"
    ]

    if not python_files:
        print("No Python files found in current directory.")
        return

    print(f"Found {len(python_files)} Python files:"
          f" {', '.join([json.dumps(str(f)) for f in python_files])}")

    non_std_modules = set()
    for f in python_files:
        print(f"Scanning: {json.dumps(str(f))}...")
        non_std_modules.update(find_third_party_imports(f))
    print("Done scanning Python files.")

    if len(non_std_modules) == 0:
        print("No non-standard modules detected.")
        if os.path.exists("requirements.txt"):
            os.remove("requirements.txt")
            print(f"Deleted existing requirements file: {json.dumps('requirements.txt')}")
        return

    print(f"All detected non-standard modules: {json.dumps(list(non_std_modules))}")

    write_requirements(non_std_modules)


if __name__ == "__main__":
    sys.exit(main())
