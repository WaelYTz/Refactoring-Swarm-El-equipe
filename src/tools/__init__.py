# src/tools/__init__.py
"""
Tools Package for the Refactoring Swarm.

This package provides the Toolsmith's implementation of all tools that AI agents
use to analyze, validate, and modify Python code during refactoring operations.

Role: Toolsmith 🛠
Responsibilities:
    - Develops the Python functions that the agents call (the internal API)
    - Implements security: prohibits agents from writing outside the "sandbox" folder
    - Manages the interfaces to the analysis (pylint) and testing (pytest) tools

Available Tools:
    - run_pylint: Static code analysis using pylint
    - safe_read: Safely read file contents with encoding handling
    - safe_write: Safely write file contents WITH SANDBOX SECURITY
    - list_python_files: Discover Python files in a directory
    - run_pytest: Execute tests and return structured results
    - SandboxValidator: Validate code changes in isolation

SECURITY NOTE:
    The safe_write function PROHIBITS writing outside the /sandbox folder.
    This is a critical security requirement for the automated grading bot.

Usage:
    from src.tools import run_pylint, safe_read, safe_write

    # Analyze a file in sandbox
    result = run_pylint("sandbox/messy_code.py")

    # Read file contents
    content = safe_read("sandbox/messy_code.py")

    # Write with sandbox security (ONLY works inside /sandbox)
    safe_write("sandbox/messy_code.py", fixed_content)

Course: IGL Lab 2025-2026
Python Version: 3.10/3.11
"""

import fnmatch
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, TypedDict

# Configure module logger
_logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY: Define the sandbox directory (agents can ONLY write here)
# =============================================================================
# The sandbox folder is relative to the project root
# This is enforced by the course requirements for security
SANDBOX_DIR = "sandbox"


def _get_sandbox_path() -> Path:
    """
    Get the absolute path to the sandbox directory.

    Returns:
        Absolute path to the sandbox folder.
    """
    # Find project root (where main.py is located)
    current = Path(__file__).resolve()
    # Go up from src/tools/__init__.py to project root
    project_root = current.parent.parent.parent
    return project_root / SANDBOX_DIR


def _is_path_in_sandbox(filepath: str) -> bool:
    """
    Check if a file path is inside the sandbox directory.

    SECURITY: This function ensures agents cannot write outside the sandbox.

    Args:
        filepath: The path to check.

    Returns:
        True if the path is inside sandbox, False otherwise.
    """
    try:
        # Resolve to absolute path to prevent path traversal attacks
        target_path = Path(filepath).resolve()
        sandbox_path = _get_sandbox_path().resolve()

        # Check if target is inside sandbox
        # Using is_relative_to (Python 3.9+) or checking common path
        try:
            target_path.relative_to(sandbox_path)
            return True
        except ValueError:
            return False
    except Exception as e:
        _logger.error("Error checking sandbox path: %s", e)
        return False


# =============================================================================
# Import from code_analyzer module (pylint wrapper)
# =============================================================================
from src.tools.code_analyzer import (
    run_pylint,
    get_pylint_version,
    is_pylint_available,
)


# =============================================================================
# File Utilities: safe_read, safe_write (WITH SANDBOX SECURITY), list_python_files
# =============================================================================


def safe_read(filepath: str, encoding: str = "utf-8") -> Optional[str]:
    """
    Safely read the contents of a file.

    Args:
        filepath: Path to the file to read.
        encoding: File encoding (default: utf-8).

    Returns:
        File contents as a string, or None if reading fails.

    Example:
        >>> content = safe_read("sandbox/messy_code.py")
        >>> if content is not None:
        ...     print(f"Read {len(content)} characters")
    """
    try:
        with open(filepath, "r", encoding=encoding) as f:
            content = f.read()
        _logger.debug("Successfully read file: %s (%d chars)", filepath, len(content))
        return content
    except FileNotFoundError:
        _logger.error("File not found: %s", filepath)
        return None
    except PermissionError:
        _logger.error("Permission denied: %s", filepath)
        return None
    except UnicodeDecodeError as e:
        _logger.error("Encoding error reading %s: %s", filepath, e)
        return None
    except OSError as e:
        _logger.error("OS error reading %s: %s", filepath, e)
        return None


def safe_write(
    filepath: str,
    content: str,
    encoding: str = "utf-8",
    create_backup: bool = True,
) -> bool:
    """
    Safely write content to a file WITH SANDBOX SECURITY.

    ⚠️ SECURITY: This function ONLY allows writing to files inside the /sandbox folder.
    Any attempt to write outside the sandbox will be REJECTED.

    Args:
        filepath: Path to the file to write (MUST be inside /sandbox).
        content: Content to write.
        encoding: File encoding (default: utf-8).
        create_backup: Whether to create a .bak backup file before overwriting.

    Returns:
        True if write succeeded, False otherwise.

    Raises:
        PermissionError: If attempting to write outside the sandbox.

    Example:
        >>> # This works (inside sandbox)
        >>> safe_write("sandbox/fixed_code.py", "print('hello')")
        True

        >>> # This FAILS (outside sandbox - SECURITY VIOLATION)
        >>> safe_write("src/agents/base_agent.py", "malicious_code")
        False  # Rejected!
    """
    # =========================================================================
    # SECURITY CHECK: Verify file is inside sandbox
    # =========================================================================
    if not _is_path_in_sandbox(filepath):
        _logger.error(
            "🚫 SECURITY VIOLATION: Attempted to write outside sandbox: %s",
            filepath
        )
        _logger.error("   Agents can ONLY write to files inside the /sandbox folder!")
        return False

    try:
        path = Path(filepath)

        # Create backup if file exists and backup requested
        if create_backup and path.exists():
            backup_path = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(filepath, backup_path)
            _logger.debug("Created backup: %s", backup_path)

        # Ensure parent directory exists (inside sandbox)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write the content
        with open(filepath, "w", encoding=encoding) as f:
            f.write(content)

        _logger.info("✅ Successfully wrote to: %s (%d chars)", filepath, len(content))
        return True

    except PermissionError:
        _logger.error("Permission denied writing to: %s", filepath)
        return False
    except OSError as e:
        _logger.error("OS error writing to %s: %s", filepath, e)
        return False


def list_python_files(
    directory: str,
    recursive: bool = True,
    exclude_patterns: Optional[list[str]] = None,
) -> list[str]:
    """
    List all Python files in a directory.

    Args:
        directory: Path to the directory to search.
        recursive: Whether to search subdirectories (default: True).
        exclude_patterns: Glob patterns to exclude (e.g., ['test_*', '*_test.py']).

    Returns:
        List of absolute paths to Python files.

    Example:
        >>> files = list_python_files("sandbox/dataset_buggy")
        >>> print(f"Found {len(files)} Python files to refactor")
    """
    exclude_patterns = exclude_patterns or []
    python_files: list[str] = []

    try:
        base_path = Path(directory)

        if not base_path.exists():
            _logger.error("Directory not found: %s", directory)
            return []

        if not base_path.is_dir():
            _logger.error("Path is not a directory: %s", directory)
            return []

        pattern = "**/*.py" if recursive else "*.py"

        for py_file in base_path.glob(pattern):
            filename = py_file.name

            # Check if file matches any exclude pattern
            excluded = any(
                fnmatch.fnmatch(filename, pat) for pat in exclude_patterns
            )

            if not excluded:
                python_files.append(str(py_file.absolute()))

        _logger.debug("Found %d Python files in %s", len(python_files), directory)
        return sorted(python_files)

    except PermissionError:
        _logger.error("Permission denied accessing: %s", directory)
        return []
    except OSError as e:
        _logger.error("OS error accessing %s: %s", directory, e)
        return []


# =============================================================================
# Test Runner: run_pytest (for the Judge agent)
# =============================================================================


class TestResultDict(TypedDict, total=False):
    """Type definition for test results."""

    success: bool
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    output: str
    error: Optional[str]


def run_pytest(
    target: str = ".",
    verbose: bool = False,
    timeout: int = 120,
) -> TestResultDict:
    """
    Run pytest and return structured results.

    This function is used by the Judge agent to execute unit tests
    and determine if the refactored code passes all tests.

    Args:
        target: Path to test file or directory (default: current directory).
        verbose: Whether to include verbose output.
        timeout: Maximum time in seconds for test execution (default: 120).

    Returns:
        Dictionary with test results including pass/fail counts:
        - success (bool): True if all tests passed
        - total (int): Total number of tests run
        - passed (int): Number of tests passed
        - failed (int): Number of tests failed
        - errors (int): Number of errors (not failures)
        - skipped (int): Number of tests skipped
        - output (str): Full pytest output
        - error (str, optional): Error message if pytest failed to run

    Example:
        >>> result = run_pytest("sandbox/tests/")
        >>> if result['success']:
        ...     print(f"✅ All {result['passed']} tests passed!")
        ... else:
        ...     print(f"❌ {result['failed']} tests failed")
    """
    try:
        cmd = ["pytest", target, "--tb=short", "-q"]
        if verbose:
            cmd.append("-v")

        _logger.info("Running pytest: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        output = result.stdout + result.stderr

        # Parse pytest summary line (e.g., "5 passed, 2 failed, 1 error")
        passed = failed = errors = skipped = 0

        passed_match = re.search(r"(\d+) passed", output)
        if passed_match:
            passed = int(passed_match.group(1))

        failed_match = re.search(r"(\d+) failed", output)
        if failed_match:
            failed = int(failed_match.group(1))

        error_match = re.search(r"(\d+) error", output)
        if error_match:
            errors = int(error_match.group(1))

        skipped_match = re.search(r"(\d+) skipped", output)
        if skipped_match:
            skipped = int(skipped_match.group(1))

        total = passed + failed + errors + skipped

        success = result.returncode == 0

        _logger.info(
            "Pytest complete: %s (passed=%d, failed=%d, errors=%d)",
            "SUCCESS" if success else "FAILURE",
            passed,
            failed,
            errors
        )

        return {
            "success": success,
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "output": output,
        }

    except FileNotFoundError:
        _logger.error("pytest not found. Run: pip install -r requirements.txt")
        return {
            "success": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "output": "",
            "error": "pytest is not installed. Run: pip install -r requirements.txt",
        }

    except subprocess.TimeoutExpired:
        _logger.error("pytest timed out after %d seconds", timeout)
        return {
            "success": False,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "output": "",
            "error": f"pytest timed out after {timeout} seconds",
        }


# =============================================================================
# Sandbox Validator (for testing code changes in isolation)
# =============================================================================


class SandboxValidator:
    """
    Validates code changes in an isolated sandbox environment.

    This class creates a temporary copy of files, applies changes,
    and validates them without affecting the original codebase.

    Used by agents to test fixes before committing them.

    Example:
        >>> with SandboxValidator() as sandbox:
        ...     file_path = sandbox.add_file("test.py", "print('hello')")
        ...     result = sandbox.validate()
        ...     if result['valid']:
        ...         print("Code is valid!")
    """

    def __init__(self) -> None:
        """Initialize the sandbox validator."""
        self.sandbox_dir: Optional[Path] = None
        self._original_files: dict[str, str] = {}

    def __enter__(self) -> "SandboxValidator":
        """Create the sandbox directory."""
        self.sandbox_dir = Path(tempfile.mkdtemp(prefix="refactor_sandbox_"))
        _logger.debug("Created temporary sandbox: %s", self.sandbox_dir)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Clean up the sandbox directory."""
        if self.sandbox_dir and self.sandbox_dir.exists():
            shutil.rmtree(self.sandbox_dir)
            _logger.debug("Cleaned up sandbox: %s", self.sandbox_dir)

    def add_file(self, relative_path: str, content: str) -> Path:
        """
        Add a file to the sandbox.

        Args:
            relative_path: Relative path within the sandbox.
            content: File content to write.

        Returns:
            Absolute path to the created file.

        Raises:
            RuntimeError: If sandbox is not initialized.
        """
        if not self.sandbox_dir:
            raise RuntimeError("Sandbox not initialized. Use 'with' statement.")

        file_path = self.sandbox_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        _logger.debug("Added file to sandbox: %s", relative_path)
        return file_path

    def copy_file(self, source_path: str, relative_dest: Optional[str] = None) -> Path:
        """
        Copy an existing file into the sandbox.

        Args:
            source_path: Path to the source file.
            relative_dest: Destination path in sandbox (defaults to filename).

        Returns:
            Absolute path to the copied file.

        Raises:
            RuntimeError: If sandbox is not initialized.
        """
        if not self.sandbox_dir:
            raise RuntimeError("Sandbox not initialized. Use 'with' statement.")

        source = Path(source_path)
        dest_name = relative_dest or source.name
        dest_path = self.sandbox_dir / dest_name

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)

        self._original_files[str(dest_path)] = source_path
        _logger.debug("Copied %s to sandbox as %s", source_path, dest_name)
        return dest_path

    def validate(self) -> dict:
        """
        Validate all Python files in the sandbox using pylint.

        Returns:
            Dictionary with validation results:
            - valid (bool): Whether all files are valid (no errors)
            - files (dict): Per-file validation results
            - errors (list): List of error messages
        """
        if not self.sandbox_dir:
            return {
                "valid": False,
                "files": {},
                "errors": ["Sandbox not initialized"],
            }

        results: dict = {"valid": True, "files": {}, "errors": []}

        for py_file in self.sandbox_dir.glob("**/*.py"):
            pylint_result = run_pylint(str(py_file))

            has_error = "error" in pylint_result
            error_count = pylint_result["stats"]["error_count"]
            file_valid = not has_error and error_count == 0

            results["files"][str(py_file)] = {
                "valid": file_valid,
                "score": pylint_result["score"],
                "error_count": error_count,
                "issues": len(pylint_result.get("issues", [])),
            }

            if not file_valid:
                results["valid"] = False
                if has_error:
                    results["errors"].append(pylint_result["error"])

        _logger.info(
            "Sandbox validation complete: valid=%s, files=%d",
            results["valid"],
            len(results["files"])
        )
        return results


# =============================================================================
# Module Exports
# =============================================================================

__all__ = [
    # Code analysis (Auditor agent uses these)
    "run_pylint",
    "is_pylint_available",
    "get_pylint_version",
    # File utilities (Fixer agent uses these)
    "safe_read",
    "safe_write",  # WITH SANDBOX SECURITY!
    "list_python_files",
    # Test running (Judge agent uses this)
    "run_pytest",
    # Sandbox validation
    "SandboxValidator",
    # Security utilities
    "SANDBOX_DIR",
]

__version__ = "1.0.0"
