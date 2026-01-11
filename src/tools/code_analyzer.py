# src/tools/code_analyzer.py
"""
Code Analysis Tools for the Refactoring Swarm.

This module provides the Toolsmith's implementation of static code analysis 
using pylint. AI agents use these tools to analyze Python code before 
performing refactoring operations.

Role: Toolsmith 🛠
Project: The Refactoring Swarm
Course: IGL Lab 2025-2026
Python Version: 3.10/3.11
"""

import json
import logging
import os
import re
import subprocess
import sys
from typing import Optional, TypedDict

# Configure module logger
logger = logging.getLogger(__name__)


class IssueDict(TypedDict):
    """Type definition for a single pylint issue."""

    type: str
    line: int
    column: int
    message: str
    symbol: str
    message_id: str


class StatsDict(TypedDict):
    """Type definition for issue statistics."""

    error_count: int
    warning_count: int
    convention_count: int
    refactor_count: int


class PylintResultDict(TypedDict, total=False):
    """Type definition for the complete pylint analysis result."""

    filepath: str
    score: float
    issues: list[IssueDict]
    stats: StatsDict
    error: Optional[str]


# Mapping from pylint message types to our standardized types
PYLINT_TYPE_MAP: dict[str, str] = {
    "fatal": "error",
    "error": "error",
    "warning": "warning",
    "convention": "convention",
    "refactor": "refactor",
    "information": "convention",
}


def _create_error_result(filepath: str, error_message: str) -> PylintResultDict:
    """
    Create a standardized error result dictionary.

    Args:
        filepath: The file path that was being analyzed.
        error_message: Description of what went wrong.

    Returns:
        A PylintResultDict with error information and zeroed stats.
    """
    logger.error("Pylint analysis failed for %s: %s", filepath, error_message)
    return {
        "filepath": filepath,
        "score": 0.0,
        "issues": [],
        "error": error_message,
        "stats": {
            "error_count": 0,
            "warning_count": 0,
            "convention_count": 0,
            "refactor_count": 0,
        },
    }


def _parse_score_from_output(stderr_output: str, stdout_output: str) -> float:
    """
    Extract the pylint score from command output.

    Pylint outputs the score in format:
    "Your code has been rated at X.XX/10" or similar patterns.

    Args:
        stderr_output: The stderr output from pylint.
        stdout_output: The stdout output from pylint.

    Returns:
        The extracted score as a float, or 0.0 if not found.
    """
    combined_output = stderr_output + "\n" + stdout_output

    # Pattern matches: "rated at 7.50/10" or "rated at -5.00/10"
    score_pattern = r"rated at (-?\d+\.?\d*)/10"
    match = re.search(score_pattern, combined_output)

    if match:
        try:
            score = float(match.group(1))
            return max(0.0, min(10.0, score))
        except ValueError:
            logger.warning("Could not parse score value: %s", match.group(1))
            return 0.0

    logger.debug("No score found in pylint output")
    return 0.0


def _categorize_issue(issue_type: str) -> str:
    """
    Map pylint's issue type to our standardized categories.

    Args:
        issue_type: The type string from pylint (e.g., 'error', 'warning').

    Returns:
        Standardized type: 'error', 'warning', 'convention', or 'refactor'.
    """
    return PYLINT_TYPE_MAP.get(issue_type.lower(), "convention")


def _parse_pylint_json(
    json_output: str, filepath: str
) -> tuple[list[IssueDict], StatsDict]:
    """
    Parse pylint's JSON output into structured issues and statistics.

    Args:
        json_output: The JSON string output from pylint.
        filepath: The filepath being analyzed (for logging).

    Returns:
        A tuple of (issues_list, stats_dict).

    Raises:
        json.JSONDecodeError: If the JSON output is malformed.
    """
    issues: list[IssueDict] = []
    stats: StatsDict = {
        "error_count": 0,
        "warning_count": 0,
        "convention_count": 0,
        "refactor_count": 0,
    }

    if not json_output.strip():
        logger.debug("Empty JSON output for %s - no issues found", filepath)
        return issues, stats

    raw_issues = json.loads(json_output)

    if not isinstance(raw_issues, list):
        logger.warning("Unexpected pylint output format for %s", filepath)
        return issues, stats

    for raw_issue in raw_issues:
        issue_type = _categorize_issue(raw_issue.get("type", "convention"))

        issue: IssueDict = {
            "type": issue_type,
            "line": raw_issue.get("line", 0),
            "column": raw_issue.get("column", 0),
            "message": raw_issue.get("message", "Unknown issue"),
            "symbol": raw_issue.get("symbol", "unknown"),
            "message_id": raw_issue.get(
                "message-id", raw_issue.get("messageId", "XXXXX")
            ),
        }
        issues.append(issue)

        if issue_type == "error":
            stats["error_count"] += 1
        elif issue_type == "warning":
            stats["warning_count"] += 1
        elif issue_type == "convention":
            stats["convention_count"] += 1
        elif issue_type == "refactor":
            stats["refactor_count"] += 1

    logger.debug("Parsed %d issues from %s", len(issues), filepath)
    return issues, stats


def run_pylint(filepath: str) -> PylintResultDict:
    """
    Analyze a Python file using pylint and return structured results.

    This function wraps pylint to provide static code analysis for Python files.
    It runs pylint with JSON output format and transforms the results into a
    structured dictionary that AI agents can easily process.

    Args:
        filepath: Absolute or relative path to the Python file to analyze.
                  The file must exist and be a valid Python file.

    Returns:
        A dictionary containing:
        - filepath (str): The file that was analyzed
        - score (float): Pylint score from 0.0 to 10.0
        - issues (list): List of issue dictionaries, each containing:
            - type (str): 'error', 'warning', 'convention', or 'refactor'
            - line (int): Line number where the issue occurs
            - column (int): Column number where the issue occurs
            - message (str): Human-readable issue description
            - symbol (str): Pylint symbol code (e.g., 'undefined-variable')
            - message_id (str): Pylint message ID (e.g., 'E0602')
        - stats (dict): Summary statistics with counts for each issue type
        - error (str, optional): Only present if analysis failed

    Examples:
        >>> from src.tools.code_analyzer import run_pylint
        >>> result = run_pylint("sandbox/messy_code.py")
        >>> print(f"Score: {result['score']}/10")
        Score: 4.50/10

        >>> # The Auditor agent uses this to create refactoring plans
        >>> for issue in result['issues']:
        ...     if issue['type'] == 'error':
        ...         print(f"Line {issue['line']}: {issue['message']}")

    Note:
        - Requires pylint to be installed (included in requirements.txt)
        - Does not execute the analyzed code, only performs static analysis
        - Used by the Auditor agent for CODE_ANALYSIS actions
    """
    logger.info("Starting pylint analysis for: %s", filepath)

    # Validate the filepath
    filepath = os.path.abspath(filepath)

    if not os.path.exists(filepath):
        return _create_error_result(filepath, f"File not found: {filepath}")

    if not os.path.isfile(filepath):
        return _create_error_result(filepath, f"Path is not a file: {filepath}")

    if not filepath.endswith(".py"):
        return _create_error_result(
            filepath, f"Not a Python file (expected .py extension): {filepath}"
        )

    # Command for JSON output (issues)
    # Use sys.executable -m pylint for proper venv support on Windows
    json_command = [
        sys.executable,
        "-m",
        "pylint",
        "--output-format=json",
        "--exit-zero",
        filepath,
    ]

    # Command for text output (score extraction)
    score_command = [
        sys.executable,
        "-m",
        "pylint",
        "--output-format=text",
        "--score=y",
        "--exit-zero",
        filepath,
    ]

    try:
        logger.debug("Running JSON command: %s", " ".join(json_command))

        # Run pylint for JSON output (issues)
        json_result = subprocess.run(
            json_command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(filepath) or ".",
        )

        # Run pylint for text output (score)
        logger.debug("Running score command: %s", " ".join(score_command))
        score_result = subprocess.run(
            score_command,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(filepath) or ".",
        )

        # Parse JSON output
        try:
            issues, stats = _parse_pylint_json(json_result.stdout, filepath)
        except json.JSONDecodeError as e:
            if json_result.stderr and "error" in json_result.stderr.lower():
                return _create_error_result(
                    filepath, f"Pylint error: {json_result.stderr.strip()}"
                )
            return _create_error_result(
                filepath, f"Failed to parse pylint output: {str(e)}"
            )

        # Extract score from text output
        score = _parse_score_from_output(score_result.stdout, score_result.stderr)

        # Build successful result
        analysis_result: PylintResultDict = {
            "filepath": filepath,
            "score": score,
            "issues": issues,
            "stats": stats,
        }

        logger.info(
            "Pylint analysis complete for %s: score=%.2f/10, issues=%d",
            filepath,
            score,
            len(issues),
        )

        return analysis_result

    except FileNotFoundError:
        return _create_error_result(
            filepath,
            "Pylint is not installed or not in PATH. Run: pip install -r requirements.txt",
        )

    except subprocess.TimeoutExpired:
        return _create_error_result(
            filepath, f"Pylint analysis timed out after 60 seconds for: {filepath}"
        )

    except PermissionError:
        return _create_error_result(
            filepath, f"Permission denied when accessing: {filepath}"
        )

    except Exception as e:
        logger.exception("Unexpected error during pylint analysis: %s", e)
        return _create_error_result(
            filepath, f"Unexpected error during analysis: {str(e)}"
        )


def get_pylint_version() -> Optional[str]:
    """
    Get the installed pylint version.

    Returns:
        Version string (e.g., "3.0.3") or None if pylint is not installed.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pylint", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        match = re.search(r"pylint (\d+\.\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def is_pylint_available() -> bool:
    """
    Check if pylint is installed and available.

    Returns:
        True if pylint is available, False otherwise.
    """
    return get_pylint_version() is not None


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = __file__

    print(f"Analyzing: {test_file}")
    print("-" * 50)

    result = run_pylint(test_file)

    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Score: {result['score']}/10")
        print(f"Total issues: {len(result['issues'])}")
        print(f"Stats: {result['stats']}")
        print()

        for issue in result["issues"][:5]:
            print(f"  [{issue['type'].upper()}] Line {issue['line']}: {issue['message']}")

        if len(result["issues"]) > 5:
            print(f"  ... and {len(result['issues']) - 5} more issues")
