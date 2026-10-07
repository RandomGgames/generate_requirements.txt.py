"""
Python Project Release Builder (Simplified)

This script scans Python files in the current directory (excluding itself),
detects top-level third-party imports (non-stdlib), and generates a
requirements.txt file listing them.
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Sequence
import ast
import importlib.metadata
import json
import logging
import os
import sys

__version__ = "1.1.0"

logger = logging.getLogger(__name__)


def resolve_distribution(import_name: str, import_to_dist: Mapping[str, Sequence[str]]) -> str:
    """
    Resolve a top-level import name to its PyPI distribution name.
    Falls back to the import name if unresolved.
    """
    dists = import_to_dist.get(import_name)
    if dists and dists[0] != import_name:
        logger.debug("Resolved %s to %s", import_name, dists[0])
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

            logger.debug("Found non-standard lib import: \"%s\"", name)
            third_party.add(resolve_distribution(name, import_to_dist))

    return third_party


def write_requirements(non_std_modules: set[str], output_path: str | Path = "requirements.txt") -> None:
    """
    Write a requirements.txt file listing third-party modules.
    """
    path = Path(output_path)
    if not non_std_modules:
        logger.warning("No non-standard modules detected; \"%s\" not generated", path)
        return

    with path.open("w", encoding="utf-8") as f:
        for module in sorted(non_std_modules):
            f.write(f"{module}\n")

    logger.info("Generated \"requirements.txt\" file.")


def main():
    """Scan Python files and generate requirements.txt for third-party imports."""

    working_dir = Path(os.getcwd())
    logger.debug("Working directory: \"%s\"", working_dir.as_posix())

    current_file = Path(__file__).name
    logger.info("Scanning current directory for Python files...")
    python_files = [
        Path(f) for f in os.listdir(".")
        if f.endswith((".py", ".pyw")) and f != current_file and f != "generate_requirements.txt.pyw"
    ]

    if not python_files:
        logger.info("No Python files found in current directory.")
        return

    logger.info("Found %s Python files:", len(', '.join([json.dumps(str(f)) for f in python_files])))

    non_std_modules = set()
    for f in python_files:
        logger.info("Scanning: \"%s\"...", f)
        non_std_modules.update(find_third_party_imports(f))
    logger.info("Done scanning Python files.")

    if len(non_std_modules) == 0:
        logger.debug("No non-standard modules detected.")
        if os.path.exists("requirements.txt"):
            os.remove("requirements.txt")
            logger.info("Deleted existing requirements file: \"requirements.txt\"")
        return

    logger.debug("All detected non-standard modules: %s", non_std_modules)

    write_requirements(non_std_modules)


def setup_logging(log_folder: Path = Path("Logs"), console_level: int = logging.DEBUG, enable_file_logging: bool = True, max_log_files: int = 30, file_level: int = logging.DEBUG, date_format: str = "%Y-%m-%dT%H:%M:%S", message_format: str = "%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s") -> Path | None:
    """Configures file and console logging and prunes old logs for this script."""
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(message_format, datefmt=date_format)

    # Console Handler (always active)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_path: Path | None = None

    # Optional File Handler
    if enable_file_logging:
        script_stem = Path(__file__).stem
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")

        log_dir = log_folder.expanduser().resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{timestamp}_{script_stem}.log"

        file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Prune old logs specific to this script
        if max_log_files > 0 and log_dir.exists():
            script_logs = sorted(
                [f for f in log_dir.glob("*.log") if f.name.endswith(f"_{script_stem}.log")],
                key=lambda p: p.stat().st_mtime,
            )
            while len(script_logs) > max_log_files:
                oldest = script_logs.pop(0)
                try:
                    oldest.unlink()
                except OSError:
                    pass

    return log_path


if __name__ == "__main__":
    PAUSE_ON_ERROR = True
    ALWAYS_PAUSE = False

    exit_code = 0
    try:
        setup_logging(max_log_files=5)
        main()

    except KeyboardInterrupt:
        print()
        logger.warning("Operation interrupted by user.")
        exit_code = 130

    except Exception as e:
        print()
        logger.exception("A fatal error has occurred: %s", e)
        exit_code = 1

    finally:
        # input("Press Enter to exit...")
        sys.exit(exit_code)
