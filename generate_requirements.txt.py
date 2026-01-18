"""
Python Project Release Builder (Simplified)

This script scans Python files in the current directory (excluding itself),
detects top-level third-party imports (non-stdlib), and generates a
requirements.txt file listing them.
"""

import ast
import json
import os
import sys
from pathlib import Path

__version__ = "1.0.0"


def find_third_party_imports(file_path: str | Path) -> set[str]:
    """
    Return top-level third-party (non-stdlib) imports from a Python file.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    stdlib = sys.stdlib_module_names
    third_party: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.partition(".")[0]
                if name not in stdlib:
                    third_party.add(name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            name = node.module.partition(".")[0]
            if name not in stdlib:
                third_party.add(name)

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
    python_files = [
        Path(f) for f in os.listdir(".")
        if f.endswith((".py", ".pyw")) and f != current_file and f != "generate_requirements.txt.pyw"
    ]

    if not python_files:
        print("No Python files found in current directory.")
        return

    non_std_modules = set()
    for f in python_files:
        print(f"Scanning: {json.dumps(str(f))}...")
        non_std_modules.update(find_third_party_imports(f))

    if len(non_std_modules) == 0:
        print("No non-standard modules detected.")
        if os.path.exists("requirements.txt"):
            os.remove("requirements.txt")
            print(f"Deleted existing requirements file: {json.dumps('requirements.txt')}")
        return

    print(f"Detected non-standard modules: {json.dumps(list(non_std_modules))}")

    write_requirements(non_std_modules)


if __name__ == "__main__":
    sys.exit(main())
