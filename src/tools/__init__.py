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
    - SandboxValidator: Security validation for file paths
    - SecurityError: Exception for security violations
    - safe_read: Safely read file contents with security validation
    - safe_write: Safely write file contents with security validation
    - list_python_files: Discover Python files in a directory
    - safe_delete: Safely delete files
    - create_backup: Create timestamped backups
    - run_pylint: Static code analysis using pylint
    - run_pytest: Execute tests and return structured results

Usage:
    from src.tools import SandboxValidator, safe_read, safe_write, run_pylint

    # Initialize sandbox with --target_dir
    sandbox = SandboxValidator("./sandbox/target_code")

    # Read file contents (secure)
    content = safe_read("calculator.py", sandbox)

    # Analyze code
    result = run_pylint("calculator.py")

    # Write fixed code (secure)
    safe_write("calculator.py", fixed_content, sandbox)

Course: IGL Lab 2025-2026
Python Version: 3.10/3.11
"""

# =============================================================================
# Import from sandbox module (security)
# =============================================================================
from src.tools.sandbox import (
    SandboxValidator,
    SecurityError,
)

# =============================================================================
# Import from file_operations module
# =============================================================================
from src.tools.file_operations import (
    safe_read,
    safe_write,
    list_python_files,
    safe_delete,
    create_backup,
)

# =============================================================================
# Import from code_analyzer module (pylint wrapper)
# =============================================================================
from src.tools.code_analyzer import (
    run_pylint,
    get_pylint_version,
    is_pylint_available,
)

# =============================================================================
# Import from test_runner module (pytest wrapper)
# =============================================================================
from src.tools.test_runner import (
    run_pytest,
    discover_tests,
)

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Security (sandbox.py)
    "SandboxValidator",
    "SecurityError",
    # File operations (file_operations.py)
    "safe_read",
    "safe_write",
    "list_python_files",
    "safe_delete",
    "create_backup",
    # Code analysis (code_analyzer.py)
    "run_pylint",
    "get_pylint_version",
    "is_pylint_available",
    # Test running (test_runner.py)
    "run_pytest",
    "discover_tests",
]

__version__ = "1.0.0"
