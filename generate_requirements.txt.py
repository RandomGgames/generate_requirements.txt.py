"""
Python Project Release Builder (Simplified)

This script scans Python files in the current directory (excluding itself),
detects top-level third-party imports (non-stdlib), and generates a
requirements.txt file listing them.
"""

import ast
import importlib.metadata
import json
import logging
import os
import socket
import sys
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

__version__ = "1.0.2"


def resolve_distribution(import_name: str, import_to_dist: Mapping[str, Sequence[str]]) -> str:
    """
    Resolve a top-level import name to its PyPI distribution name.
    Falls back to the import name if unresolved.
    """
    dists = import_to_dist.get(import_name)
    if dists and dists[0] != import_name:
        logger.debug(f"Resolved {import_name} to {dists[0]}")
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

            logger.debug(f"Found non-stdlib import: {name}")
            third_party.add(resolve_distribution(name, import_to_dist))

    return third_party


def write_requirements(non_std_modules: set[str], output_path: str | Path = "requirements.txt") -> None:
    """
    Write a requirements.txt file listing third-party modules.
    """
    path = Path(output_path)
    if not non_std_modules:
        logger.warning(f"No non-standard modules detected; {json.dumps(str(path))} not generated")
        return

    with path.open("w", encoding="utf-8", newline="\n") as f:
        for module in sorted(non_std_modules):
            f.write(f"{module}\n")

    logger.info(f"Generated requirements file: {json.dumps(str(path))}")


def main():
    """Scan Python files and generate requirements.txt for third-party imports."""

    working_dir = os.getcwd()
    logger.debug(f"Working directory: {json.dumps(str(working_dir))}")

    current_file = Path(__file__).name
    logger.info("Scanning current directory for Python files...")
    python_files = [
        Path(f) for f in os.listdir(".")
        if f.endswith((".py", ".pyw")) and f != current_file and f != "generate_requirements.txt.pyw"
    ]

    if not python_files:
        logger.info("No Python files found in current directory.")
        return

    logger.info(f"Found {len(python_files)} Python files:"
                f" {', '.join([json.dumps(str(f)) for f in python_files])}")

    non_std_modules = set()
    for f in python_files:
        logger.info(f"Scanning: {json.dumps(str(f))}...")
        non_std_modules.update(find_third_party_imports(f))
    logger.info("Done scanning Python files.")

    if len(non_std_modules) == 0:
        logger.debug("No non-standard modules detected.")
        if os.path.exists("requirements.txt"):
            os.remove("requirements.txt")
            logger.info(f"Deleted existing requirements file: {json.dumps('requirements.txt')}")
        return

    logger.debug(f"All detected non-standard modules: {json.dumps(list(non_std_modules))}")

    write_requirements(non_std_modules)


def format_duration_long(duration_seconds: float) -> str:
    """
    Format duration in a human-friendly way, showing only the two largest non-zero units.
    For durations >= 1s, do not show microseconds or nanoseconds.
    For durations >= 1m, do not show milliseconds.
    """
    ns = int(duration_seconds * 1_000_000_000)
    units = [
        ("y", 365 * 24 * 60 * 60 * 1_000_000_000),
        ("mo", 30 * 24 * 60 * 60 * 1_000_000_000),
        ("d", 24 * 60 * 60 * 1_000_000_000),
        ("h", 60 * 60 * 1_000_000_000),
        ("m", 60 * 1_000_000_000),
        ("s", 1_000_000_000),
        ("ms", 1_000_000),
        ("us", 1_000),
        ("ns", 1),
    ]
    parts = []
    for name, factor in units:
        value, ns = divmod(ns, factor)
        if value:
            parts.append(f"{value}{name}")
        if len(parts) == 2:
            break
    if not parts:
        return "0s"
    return "".join(parts)


def enforce_max_log_count(dir_path: Path | str, max_count: int | None, script_name: str) -> None:
    """Keep only the N most recent logs for this script."""
    if max_count is None or max_count <= 0:
        return

    dir_path = Path(dir_path)

    # Get all logs for this script, sorted by name (which is our timestamp)
    # Newest will be at the end of the list
    files = sorted([f for f in dir_path.glob(f"*{script_name}*.log") if f.is_file()])

    # If there is more than the limit, calculate how many to delete
    if len(files) > max_count:
        to_delete = files[:-max_count]  # Everything except the last N files
        for f in to_delete:
            try:
                f.unlink()
                logger.debug(f"Deleted old log: {f.name}")
            except OSError as e:
                logger.error(f"Failed to delete {f.name}: {e}")


def setup_logging(
        logger_obj: logging.Logger,
        file_path: Path | str,
        script_name: str,
        max_log_files: int | None = None,
        console_logging_level: int = logging.DEBUG,
        file_logging_level: int = logging.DEBUG,
        message_format: str = "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s",
        date_format: str = "%Y-%m-%d %H:%M:%S"
) -> None:
    """
    Set up logging for a script.

    Args:
    logger_obj (logging.Logger): The logger object to configure.
    file_path (Path | str): The file path of the log file to write.
    max_log_files (int | None, optional): The maximum total size for all logs in the folder. Defaults to None.
    console_logging_level (int, optional): The logging level for console output. Defaults to logging.DEBUG.
    file_logging_level (int, optional): The logging level for file output. Defaults to logging.DEBUG.
    message_format (str, optional): The format string for log messages. Defaults to "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s]: %(message)s".
    date_format (str, optional): The format string for log timestamps. Defaults to "%Y-%m-%d %H:%M:%S".
    """

    file_path = Path(file_path)
    dir_path = file_path.parent
    dir_path.mkdir(parents=True, exist_ok=True)

    logger_obj.handlers.clear()
    logger_obj.setLevel(file_logging_level)

    formatter = logging.Formatter(message_format, datefmt=date_format)

    # File Handler
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(file_logging_level)
    file_handler.setFormatter(formatter)
    logger_obj.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_logging_level)
    console_handler.setFormatter(formatter)
    logger_obj.addHandler(console_handler)

    if max_log_files is not None:
        enforce_max_log_count(dir_path, max_log_files, script_name)


def bootstrap():
    """
    Handles environment setup, configuration loading,
    and logging before executing the main script logic.
    """
    exit_code = 0
    try:
        script_path = Path(__file__)
        script_name = script_path.stem

        console_log_level = logging.DEBUG
        file_log_level = logging.DEBUG
        log_message_format = "%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] - %(message)s"

        logs_folder = Path("logs")
        logs_folder.mkdir(parents=True, exist_ok=True)

        pc_name = socket.gethostname()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = logs_folder / f"{timestamp}__{script_name}__{pc_name}.log"

        setup_logging(
            logger_obj=logger,
            file_path=log_path,
            script_name=script_name,
            max_log_files=10,
            console_logging_level=console_log_level,
            file_logging_level=file_log_level,
            message_format=log_message_format
        )

        start_ns = time.perf_counter_ns()
        logger.info(f"Script: {json.dumps(script_name)} | Version: {__version__} | Host: {json.dumps(pc_name)}")

        main()

        end_ns = time.perf_counter_ns()
        duration_str = format_duration_long((end_ns - start_ns) / 1e9)
        logger.info(f"Execution completed in {duration_str}.")

    except KeyboardInterrupt:
        logger.warning("Operation interrupted by user.")
        exit_code = 130
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(f"A fatal error has occurred: {e}")
        exit_code = 1
    finally:
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    input("Press Enter to exit...")

    return exit_code


if __name__ == "__main__":
    sys.exit(bootstrap())
