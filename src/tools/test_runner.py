# src/tools/test_runner.py
"""
Test Runner Module for the Refactoring Swarm.

This module provides a wrapper around pytest that AI agents use to run
unit tests and validate code fixes. Used by the Judge agent to determine
if the Fixer agent's corrections work correctly.

Role: Toolsmith 🛠
Project: The Refactoring Swarm
Course: IGL Lab 2025-2026
Python Version: 3.10/3.11

Usage:
    from src.tools.test_runner import run_pytest
    from src.tools.sandbox import SandboxValidator
    
    sandbox = SandboxValidator("./sandbox/target_code")
    result = run_pytest("./sandbox/target_code", sandbox)
    
    if result['success']:
        print(f"All {result['passed']} tests passed!")
    else:
        print(f"{result['failed']} tests failed")
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from src.tools.sandbox import SandboxValidator

# Configure module logger
logger = logging.getLogger(__name__)


def run_pytest(
    directory: Union[str, Path],
    sandbox: Optional["SandboxValidator"] = None,
    timeout: int = 120,
    verbose: bool = False
) -> Dict:
    """
    Run pytest on a directory and return structured results.

    Used by the Judge agent to validate if Fixer's code corrections work.
    Parses pytest output to extract pass/fail counts and error messages.

    Args:
        directory: Path to directory containing test files (test_*.py or *_test.py).
        sandbox: Optional SandboxValidator for security validation.
                 If provided, validates directory is inside sandbox.
        timeout: Maximum time in seconds for test execution (default: 120).
        verbose: If True, include more detailed output.

    Returns:
        dict: {
            'success': bool,              # True if all tests passed
            'passed': int,                # Number of passed tests
            'failed': int,                # Number of failed tests
            'errors': int,                # Number of error tests
            'skipped': int,               # Number of skipped tests
            'total': int,                 # Total number of tests
            'error_messages': List[str],  # List of error messages
            'duration': float,            # Test execution time in seconds
            'output': str,                # Full pytest output
            'test_results': List[dict]    # Detailed results per test
        }

    Raises:
        SecurityError: If sandbox is provided and directory is outside sandbox.

    Example:
        >>> from src.tools.test_runner import run_pytest
        >>> result = run_pytest("sandbox/tests/")
        >>> if result['success']:
        ...     print(f"✅ All {result['passed']} tests passed!")
        ... else:
        ...     print(f"❌ {result['failed']} tests failed")
        ...     for err in result['error_messages']:
        ...         print(f"  - {err}")
    """
    # Security validation if sandbox provided
    if sandbox is not None:
        try:
            safe_dir = sandbox.get_safe_path(directory)
            directory = str(safe_dir)
            logger.debug("Validated test directory in sandbox: %s", directory)
        except Exception as e:
            logger.error("Security violation: %s", e)
            raise

    # Convert to Path and validate
    dir_path = Path(directory)
    
    if not dir_path.exists():
        logger.error("Test directory does not exist: %s", directory)
        return _create_error_result(f"Directory not found: {directory}")

    if not dir_path.is_dir():
        logger.error("Path is not a directory: %s", directory)
        return _create_error_result(f"Path is not a directory: {directory}")

    # Build pytest command
    # Use -v for verbose output with test names
    # Use --tb=short for shorter tracebacks
    # Use -q for quieter output when not verbose
    cmd = [
        "pytest",
        str(dir_path),
        "--tb=short",
        "-v" if verbose else "-q",
    ]

    logger.info("Running pytest: %s", " ".join(cmd))
    start_time = time.time()

    try:
        # Run pytest
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(dir_path.parent) if dir_path.is_absolute() else None,
        )

        duration = time.time() - start_time
        output = result.stdout + result.stderr

        # Parse the output
        parsed = _parse_pytest_output(output, result.returncode)
        parsed['duration'] = round(duration, 2)
        parsed['output'] = output

        logger.info(
            "Pytest complete: success=%s, passed=%d, failed=%d, duration=%.2fs",
            parsed['success'],
            parsed['passed'],
            parsed['failed'],
            duration
        )

        return parsed

    except FileNotFoundError:
        logger.error("pytest not found. Is it installed?")
        return _create_error_result(
            "pytest is not installed. Run: pip install pytest"
        )

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error("pytest timed out after %d seconds", timeout)
        return _create_error_result(
            f"pytest timed out after {timeout} seconds",
            duration=duration
        )

    except Exception as e:
        logger.exception("Unexpected error running pytest: %s", e)
        return _create_error_result(f"Unexpected error: {str(e)}")


def _create_error_result(error_message: str, duration: float = 0.0) -> Dict:
    """
    Create an error result dictionary.

    Args:
        error_message: The error message to include.
        duration: Optional duration value.

    Returns:
        Error result dictionary.
    """
    return {
        'success': False,
        'passed': 0,
        'failed': 0,
        'errors': 0,
        'skipped': 0,
        'total': 0,
        'error_messages': [error_message],
        'duration': duration,
        'output': '',
        'test_results': []
    }


def _parse_pytest_output(output: str, return_code: int) -> Dict:
    """
    Parse pytest output to extract test results.

    Args:
        output: Combined stdout and stderr from pytest.
        return_code: pytest exit code.

    Returns:
        Parsed results dictionary.
    """
    passed = 0
    failed = 0
    errors = 0
    skipped = 0
    error_messages: List[str] = []
    test_results: List[Dict] = []

    # Parse summary line (e.g., "5 passed, 2 failed, 1 error in 1.23s")
    # Pattern matches various formats:
    # "5 passed"
    # "2 failed"
    # "1 error"
    # "3 skipped"
    passed_match = re.search(r"(\d+)\s+passed", output)
    if passed_match:
        passed = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", output)
    if failed_match:
        failed = int(failed_match.group(1))

    error_match = re.search(r"(\d+)\s+error", output)
    if error_match:
        errors = int(error_match.group(1))

    skipped_match = re.search(r"(\d+)\s+skipped", output)
    if skipped_match:
        skipped = int(skipped_match.group(1))

    # Parse individual test results from verbose output
    # Pattern: "test_file.py::test_name PASSED" or "FAILED" or "ERROR"
    test_pattern = re.compile(
        r"([\w/\\]+\.py)::(\w+)\s+(PASSED|FAILED|ERROR|SKIPPED)"
    )
    for match in test_pattern.finditer(output):
        test_results.append({
            'file': match.group(1),
            'name': match.group(2),
            'status': match.group(3).lower()
        })

    # Extract error messages from FAILURES section
    if "FAILURES" in output:
        # Find all assertion errors or exception messages
        error_pattern = re.compile(r"(?:AssertionError|Error|Exception):\s*(.+?)(?:\n|$)")
        for match in error_pattern.finditer(output):
            error_messages.append(match.group(1).strip())

    # Also check for collection errors
    if "ERROR" in output and "collecting" in output.lower():
        collection_error = re.search(r"ERROR\s+(.+?)(?:\n|$)", output)
        if collection_error:
            error_messages.append(f"Collection error: {collection_error.group(1)}")

    # If no tests found
    if "no tests ran" in output.lower() or "collected 0 items" in output.lower():
        error_messages.append("No tests found in directory")

    total = passed + failed + errors + skipped
    success = return_code == 0 and failed == 0 and errors == 0

    return {
        'success': success,
        'passed': passed,
        'failed': failed,
        'errors': errors,
        'skipped': skipped,
        'total': total,
        'error_messages': error_messages,
        'duration': 0.0,  # Will be set by caller
        'output': '',     # Will be set by caller
        'test_results': test_results
    }


def discover_tests(
    directory: Union[str, Path],
    sandbox: Optional["SandboxValidator"] = None
) -> List[str]:
    """
    Discover test files in a directory.

    Args:
        directory: Path to search for test files.
        sandbox: Optional SandboxValidator for security.

    Returns:
        List of paths to test files.

    Example:
        >>> tests = discover_tests("sandbox/project")
        >>> print(f"Found {len(tests)} test files")
    """
    # Security validation if sandbox provided
    if sandbox is not None:
        try:
            safe_dir = sandbox.get_safe_path(directory)
            directory = str(safe_dir)
        except Exception as e:
            logger.error("Security violation: %s", e)
            raise

    dir_path = Path(directory)
    
    if not dir_path.exists() or not dir_path.is_dir():
        return []

    test_files: List[str] = []

    # Find test_*.py and *_test.py files
    for pattern in ["test_*.py", "*_test.py"]:
        for test_file in dir_path.rglob(pattern):
            # Exclude __pycache__ and venv directories
            parts = test_file.parts
            if "__pycache__" not in parts and "venv" not in parts:
                test_files.append(str(test_file))

    logger.debug("Discovered %d test files in %s", len(test_files), directory)
    return sorted(test_files)
