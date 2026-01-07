# src/tools/file_operations.py
"""
Secure File Operations for the Refactoring Swarm.

This module provides secure file operations that AI agents use to read,
write, and manipulate Python files during the refactoring process.
All operations are validated through the SandboxValidator to prevent
unauthorized file access.

Role: Toolsmith 🛠
Project: The Refactoring Swarm
Course: IGL Lab 2025-2026
Python Version: 3.10/3.11

Available Functions:
    - safe_read: Read file content with security validation
    - safe_write: Write content to file with security validation
    - list_python_files: Find all Python files in a directory
    - safe_delete: Delete a file safely
    - create_backup: Create a timestamped backup of a file

Security:
    All functions require a SandboxValidator instance and will raise
    SecurityError if attempting to access files outside the sandbox.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Union

from src.tools.sandbox import SandboxValidator, SecurityError

# Configure module logger
logger = logging.getLogger(__name__)

# Directories to exclude when listing Python files
EXCLUDED_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    ".tox",
    "build",
    "dist",
    "*.egg-info",
}


def safe_read(filepath: Union[str, Path], sandbox: SandboxValidator) -> str:
    """
    Safely read the contents of a file within the sandbox.

    This function reads file content with UTF-8 encoding after validating
    that the file path is within the allowed sandbox directory.

    Args:
        filepath: Path to the file to read (relative or absolute).
        sandbox: SandboxValidator instance for security validation.

    Returns:
        The file contents as a string.

    Raises:
        SecurityError: If the file is outside the sandbox.
        FileNotFoundError: If the file doesn't exist.
        PermissionError: If the file can't be read.
        UnicodeDecodeError: If the file isn't valid UTF-8.

    Example:
        >>> from src.tools.sandbox import SandboxValidator
        >>> from src.tools.file_operations import safe_read
        >>>
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>> code = safe_read("calculator.py", sandbox)
        >>> print(code[:50])
        'def add(a, b):\\n    return a + b\\n'

        >>> # Files outside sandbox are blocked
        >>> safe_read("/etc/passwd", sandbox)
        SecurityError: Path outside sandbox: '/etc/passwd' is outside sandbox '/tmp/target_code'
    """
    # Validate path is within sandbox
    safe_path = sandbox.get_safe_path(filepath)

    # Check file exists
    if not safe_path.exists():
        logger.error("File not found: %s", safe_path)
        raise FileNotFoundError(f"File not found: {safe_path}")

    if not safe_path.is_file():
        logger.error("Path is not a file: %s", safe_path)
        raise IsADirectoryError(f"Path is not a file: {safe_path}")

    try:
        content = safe_path.read_text(encoding="utf-8")
        logger.debug("Read %d characters from: %s", len(content), safe_path)
        return content

    except UnicodeDecodeError as e:
        logger.error("Encoding error reading %s: %s", safe_path, e)
        raise

    except PermissionError as e:
        logger.error("Permission denied reading %s: %s", safe_path, e)
        raise


def safe_write(
    filepath: Union[str, Path],
    content: str,
    sandbox: SandboxValidator
) -> bool:
    """
    Safely write content to a file within the sandbox.

    This function writes content with UTF-8 encoding after validating
    that the file path is within the allowed sandbox directory.
    Parent directories are created automatically if they don't exist.

    Args:
        filepath: Path to the file to write (relative or absolute).
        content: The content to write to the file.
        sandbox: SandboxValidator instance for security validation.

    Returns:
        True if the write was successful.

    Raises:
        SecurityError: If the file is outside the sandbox.
        PermissionError: If the file can't be written.
        OSError: If there's an I/O error during writing.

    Example:
        >>> from src.tools.sandbox import SandboxValidator
        >>> from src.tools.file_operations import safe_write
        >>>
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>>
        >>> # Write new content
        >>> fixed_code = "def add(a: int, b: int) -> int:\\n    return a + b\\n"
        >>> safe_write("calculator.py", fixed_code, sandbox)
        True
        >>>
        >>> # Subdirectories are created automatically
        >>> safe_write("src/utils/helpers.py", "# New file", sandbox)
        True
        >>>
        >>> # Files outside sandbox are blocked
        >>> safe_write("/etc/malicious.py", "bad code", sandbox)
        SecurityError: Path outside sandbox
    """
    # Validate path is within sandbox
    safe_path = sandbox.get_safe_path(filepath)

    try:
        # Create parent directories if they don't exist
        safe_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the content
        safe_path.write_text(content, encoding="utf-8")

        logger.info(
            "✅ Wrote %d characters to: %s",
            len(content),
            safe_path
        )
        return True

    except PermissionError as e:
        logger.error("Permission denied writing to %s: %s", safe_path, e)
        raise

    except OSError as e:
        logger.error("Error writing to %s: %s", safe_path, e)
        raise


def list_python_files(
    directory: Union[str, Path],
    sandbox: SandboxValidator
) -> List[str]:
    """
    List all Python files in a directory recursively.

    This function finds all .py files within the specified directory,
    excluding common non-source directories like __pycache__, .venv, etc.

    Args:
        directory: Path to the directory to search (relative or absolute).
        sandbox: SandboxValidator instance for security validation.

    Returns:
        List of absolute paths to Python files as strings.

    Raises:
        SecurityError: If the directory is outside the sandbox.
        NotADirectoryError: If the path is not a directory.

    Excluded Directories:
        - __pycache__
        - .venv, venv
        - .git
        - .pytest_cache
        - .mypy_cache
        - node_modules
        - build, dist

    Example:
        >>> from src.tools.sandbox import SandboxValidator
        >>> from src.tools.file_operations import list_python_files
        >>>
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>> files = list_python_files(".", sandbox)
        >>> print(files)
        ['/tmp/target_code/calculator.py', '/tmp/target_code/src/utils.py']
        >>>
        >>> # Search subdirectory
        >>> files = list_python_files("src", sandbox)
        >>> print(len(files))
        5
    """
    # Validate directory is within sandbox
    safe_dir = sandbox.get_safe_path(directory)

    if not safe_dir.exists():
        logger.warning("Directory does not exist: %s", safe_dir)
        return []

    if not safe_dir.is_dir():
        logger.error("Path is not a directory: %s", safe_dir)
        raise NotADirectoryError(f"Path is not a directory: {safe_dir}")

    python_files: List[str] = []

    try:
        # Walk through directory recursively
        for py_file in safe_dir.rglob("*.py"):
            # Check if any parent directory is in excluded list
            parts = py_file.relative_to(safe_dir).parts
            excluded = False

            for part in parts[:-1]:  # Check all parent directories
                if part in EXCLUDED_DIRS:
                    excluded = True
                    break
                # Handle wildcard patterns like *.egg-info
                for pattern in EXCLUDED_DIRS:
                    if "*" in pattern and part.endswith(pattern.replace("*", "")):
                        excluded = True
                        break

            if not excluded:
                python_files.append(str(py_file))

        logger.debug(
            "Found %d Python files in %s",
            len(python_files),
            safe_dir
        )
        return sorted(python_files)

    except PermissionError as e:
        logger.error("Permission denied accessing %s: %s", safe_dir, e)
        return []

    except OSError as e:
        logger.error("Error listing files in %s: %s", safe_dir, e)
        return []


def safe_delete(
    filepath: Union[str, Path],
    sandbox: SandboxValidator
) -> bool:
    """
    Safely delete a file within the sandbox.

    This function deletes a file after validating that the path
    is within the allowed sandbox directory.

    Args:
        filepath: Path to the file to delete (relative or absolute).
        sandbox: SandboxValidator instance for security validation.

    Returns:
        True if the file was deleted, False if it didn't exist.

    Raises:
        SecurityError: If the file is outside the sandbox.
        PermissionError: If the file can't be deleted.
        IsADirectoryError: If the path is a directory (use shutil.rmtree).

    Example:
        >>> from src.tools.sandbox import SandboxValidator
        >>> from src.tools.file_operations import safe_delete
        >>>
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>>
        >>> # Delete a file
        >>> safe_delete("old_code.py", sandbox)
        True
        >>>
        >>> # File doesn't exist
        >>> safe_delete("nonexistent.py", sandbox)
        False
        >>>
        >>> # Files outside sandbox are blocked
        >>> safe_delete("/etc/important.conf", sandbox)
        SecurityError: Path outside sandbox
    """
    # Validate path is within sandbox
    safe_path = sandbox.get_safe_path(filepath)

    # Check if file exists
    if not safe_path.exists():
        logger.debug("File does not exist, nothing to delete: %s", safe_path)
        return False

    if safe_path.is_dir():
        logger.error("Cannot delete directory with safe_delete: %s", safe_path)
        raise IsADirectoryError(
            f"Cannot delete directory: {safe_path}. Use shutil.rmtree for directories."
        )

    try:
        safe_path.unlink()
        logger.info("🗑️ Deleted file: %s", safe_path)
        return True

    except PermissionError as e:
        logger.error("Permission denied deleting %s: %s", safe_path, e)
        raise

    except OSError as e:
        logger.error("Error deleting %s: %s", safe_path, e)
        raise


def create_backup(
    filepath: Union[str, Path],
    sandbox: SandboxValidator
) -> str:
    """
    Create a timestamped backup of a file within the sandbox.

    This function creates a backup copy of the specified file with
    a timestamp appended to the filename. The backup is created
    in the same directory as the original file.

    Backup format: `filename.backup.YYYYMMDD_HHMMSS.ext`

    Args:
        filepath: Path to the file to backup (relative or absolute).
        sandbox: SandboxValidator instance for security validation.

    Returns:
        The absolute path to the backup file as a string.

    Raises:
        SecurityError: If the file is outside the sandbox.
        FileNotFoundError: If the source file doesn't exist.
        PermissionError: If the backup can't be created.

    Example:
        >>> from src.tools.sandbox import SandboxValidator
        >>> from src.tools.file_operations import create_backup
        >>>
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>>
        >>> # Create backup before making changes
        >>> backup_path = create_backup("calculator.py", sandbox)
        >>> print(backup_path)
        '/tmp/target_code/calculator.backup.20260108_143022.py'
        >>>
        >>> # Now safe to modify the original
        >>> safe_write("calculator.py", fixed_code, sandbox)
    """
    # Validate path is within sandbox
    safe_path = sandbox.get_safe_path(filepath)

    # Check file exists
    if not safe_path.exists():
        logger.error("Cannot backup non-existent file: %s", safe_path)
        raise FileNotFoundError(f"File not found: {safe_path}")

    if not safe_path.is_file():
        logger.error("Cannot backup non-file: %s", safe_path)
        raise IsADirectoryError(f"Path is not a file: {safe_path}")

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = safe_path.stem  # filename without extension
    suffix = safe_path.suffix  # extension including dot

    backup_name = f"{stem}.backup.{timestamp}{suffix}"
    backup_path = safe_path.parent / backup_name

    try:
        # Copy file to backup location
        shutil.copy2(safe_path, backup_path)

        logger.info(
            "💾 Created backup: %s -> %s",
            safe_path.name,
            backup_name
        )
        return str(backup_path)

    except PermissionError as e:
        logger.error("Permission denied creating backup: %s", e)
        raise

    except OSError as e:
        logger.error("Error creating backup: %s", e)
        raise
