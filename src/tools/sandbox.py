# src/tools/sandbox.py
"""
Sandbox Security Module for the Refactoring Swarm.

This module provides secure path validation to ensure AI agents can only
read/write files within the allowed target directory. This is critical
for preventing agents from accessing or modifying system files.

Role: Toolsmith 🛠
Project: The Refactoring Swarm
Course: IGL Lab 2025-2026
Python Version: 3.10/3.11

Security Features:
    - Blocks path traversal attacks (../../escape)
    - Blocks absolute paths outside sandbox (/etc/passwd)
    - Blocks home directory access (~/home)
    - Blocks symlinks pointing outside sandbox
    - Uses pathlib.Path.resolve() for secure path resolution
"""

import logging
import os
from pathlib import Path
from typing import Union

# Configure module logger
logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """
    Exception raised when a security violation is detected.

    This exception is raised when an agent attempts to access a file
    or directory outside the allowed sandbox directory.

    Attributes:
        message: Explanation of the security violation.
        path: The path that caused the violation.
        sandbox: The allowed sandbox directory.

    Example:
        >>> raise SecurityError("Path escape attempt", "/etc/passwd", "/tmp/sandbox")
        SecurityError: Path escape attempt: '/etc/passwd' is outside sandbox '/tmp/sandbox'
    """

    def __init__(
        self,
        message: str,
        path: Union[str, Path, None] = None,
        sandbox: Union[str, Path, None] = None
    ) -> None:
        """
        Initialize SecurityError with details about the violation.

        Args:
            message: Description of the security violation.
            path: The path that caused the violation (optional).
            sandbox: The allowed sandbox directory (optional).
        """
        self.message = message
        self.path = str(path) if path else None
        self.sandbox = str(sandbox) if sandbox else None

        if path and sandbox:
            full_message = f"{message}: '{path}' is outside sandbox '{sandbox}'"
        elif path:
            full_message = f"{message}: '{path}'"
        else:
            full_message = message

        super().__init__(full_message)


class SandboxValidator:
    """
    Validates file paths to ensure they are within an allowed directory.

    This class provides security validation for file operations, ensuring
    that AI agents can only access files within the specified target directory
    (passed via CLI --target_dir argument).

    Attributes:
        allowed_dir: The absolute path to the allowed sandbox directory.

    Security Checks:
        - Path traversal (../) detection
        - Absolute path validation
        - Symlink resolution and validation
        - Home directory (~) blocking

    Example:
        >>> from src.tools.sandbox import SandboxValidator, SecurityError
        >>>
        >>> # Initialize with CLI --target_dir argument
        >>> sandbox = SandboxValidator("/tmp/target_code")
        >>>
        >>> # Check if path is safe
        >>> sandbox.is_safe_path("calculator.py")
        True
        >>>
        >>> # Get validated absolute path
        >>> safe_path = sandbox.get_safe_path("calculator.py")
        >>> print(safe_path)
        /tmp/target_code/calculator.py
        >>>
        >>> # Unsafe paths are blocked
        >>> sandbox.is_safe_path("../../etc/passwd")
        False
        >>>
        >>> # SecurityError raised for unsafe paths
        >>> sandbox.get_safe_path("/etc/passwd")
        SecurityError: Path outside sandbox: '/etc/passwd' is outside sandbox '/tmp/target_code'
    """

    def __init__(self, allowed_dir: Union[str, Path]) -> None:
        """
        Initialize the SandboxValidator with an allowed directory.

        Args:
            allowed_dir: The directory where file operations are allowed.
                         This is typically the --target_dir from CLI.

        Raises:
            ValueError: If allowed_dir is empty or None.
            SecurityError: If allowed_dir doesn't exist or isn't a directory.

        Example:
            >>> sandbox = SandboxValidator("./sandbox/target_code")
        """
        if not allowed_dir:
            raise ValueError("allowed_dir cannot be empty or None")

        # Convert to Path and resolve to absolute path
        self._allowed_dir = Path(allowed_dir).resolve()

        # Validate the sandbox directory exists
        if not self._allowed_dir.exists():
            logger.warning(
                "Sandbox directory does not exist, creating: %s",
                self._allowed_dir
            )
            self._allowed_dir.mkdir(parents=True, exist_ok=True)

        if not self._allowed_dir.is_dir():
            raise SecurityError(
                "Sandbox path is not a directory",
                path=self._allowed_dir
            )

        logger.info("SandboxValidator initialized with: %s", self._allowed_dir)

    @property
    def allowed_dir(self) -> Path:
        """
        Get the allowed sandbox directory.

        Returns:
            The absolute Path to the sandbox directory.
        """
        return self._allowed_dir

    def is_safe_path(self, path: Union[str, Path]) -> bool:
        """
        Check if a path is safely within the sandbox directory.

        This method performs comprehensive security checks:
        1. Resolves the path to its absolute form
        2. Follows and validates symlinks
        3. Checks if resolved path is within sandbox
        4. Blocks home directory expansion (~)

        Args:
            path: The path to validate (relative or absolute).

        Returns:
            True if the path is safe (inside sandbox), False otherwise.

        Example:
            >>> sandbox = SandboxValidator("/tmp/sandbox")
            >>> sandbox.is_safe_path("code.py")
            True
            >>> sandbox.is_safe_path("subdir/code.py")
            True
            >>> sandbox.is_safe_path("../../etc/passwd")
            False
            >>> sandbox.is_safe_path("/etc/passwd")
            False
        """
        try:
            # Block home directory expansion
            path_str = str(path)
            if path_str.startswith("~"):
                logger.warning("Blocked home directory access: %s", path)
                return False

            # Convert to Path object
            target_path = Path(path)

            # If relative, make it relative to sandbox
            if not target_path.is_absolute():
                target_path = self._allowed_dir / target_path

            # Resolve to absolute path (follows symlinks, resolves ..)
            resolved_path = target_path.resolve()

            # Check if resolved path is within sandbox
            try:
                resolved_path.relative_to(self._allowed_dir)
                return True
            except ValueError:
                logger.warning(
                    "Path outside sandbox: %s -> %s",
                    path,
                    resolved_path
                )
                return False

        except Exception as e:
            logger.error("Error validating path '%s': %s", path, e)
            return False

    def get_safe_path(self, path: Union[str, Path]) -> Path:
        """
        Get a validated absolute path within the sandbox.

        This method validates the path and returns its absolute form.
        If the path is unsafe, it raises a SecurityError.

        Args:
            path: The path to validate and resolve.

        Returns:
            The validated absolute Path object.

        Raises:
            SecurityError: If the path is outside the sandbox.

        Example:
            >>> sandbox = SandboxValidator("/tmp/sandbox")
            >>>
            >>> # Relative paths are resolved within sandbox
            >>> sandbox.get_safe_path("code.py")
            PosixPath('/tmp/sandbox/code.py')
            >>>
            >>> # Subdirectories work too
            >>> sandbox.get_safe_path("src/utils.py")
            PosixPath('/tmp/sandbox/src/utils.py')
            >>>
            >>> # Unsafe paths raise SecurityError
            >>> sandbox.get_safe_path("../../etc/passwd")
            SecurityError: Path outside sandbox: '../../etc/passwd' is outside sandbox '/tmp/sandbox'
        """
        # Block home directory expansion
        path_str = str(path)
        if path_str.startswith("~"):
            raise SecurityError(
                "Home directory access blocked",
                path=path,
                sandbox=self._allowed_dir
            )

        # Convert to Path object
        target_path = Path(path)

        # If relative, make it relative to sandbox
        if not target_path.is_absolute():
            target_path = self._allowed_dir / target_path

        # Resolve to absolute path (follows symlinks, resolves ..)
        resolved_path = target_path.resolve()

        # Validate path is within sandbox
        try:
            resolved_path.relative_to(self._allowed_dir)
        except ValueError:
            raise SecurityError(
                "Path outside sandbox",
                path=path,
                sandbox=self._allowed_dir
            )

        # Additional check: if path exists and is symlink, verify target
        if resolved_path.exists() and resolved_path.is_symlink():
            symlink_target = resolved_path.resolve()
            try:
                symlink_target.relative_to(self._allowed_dir)
            except ValueError:
                raise SecurityError(
                    "Symlink points outside sandbox",
                    path=path,
                    sandbox=self._allowed_dir
                )

        logger.debug("Validated safe path: %s -> %s", path, resolved_path)
        return resolved_path

    def __repr__(self) -> str:
        """Return string representation of SandboxValidator."""
        return f"SandboxValidator(allowed_dir='{self._allowed_dir}')"

    def __str__(self) -> str:
        """Return human-readable string of SandboxValidator."""
        return f"Sandbox: {self._allowed_dir}"
