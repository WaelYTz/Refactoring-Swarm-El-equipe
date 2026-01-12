"""
Listener (Auditor) Agent Prompts
================================
System prompts and templates for the code analysis agent.

The Listener agent is responsible for:
- Analyzing source code for issues (bugs, code smells, violations)
- Detecting security vulnerabilities
- Identifying performance problems
- Checking style/convention violations

Optimized for: Google Gemini 1.5 Flash (free tier)
- Concise prompts to minimize token usage
- Structured output format for reliable parsing
- Clear instructions to reduce hallucinations

Author: Yacine (Prompt Engineer)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


# =============================================================================
# PROMPT VERSIONS - Simplified (single version, API compatible)
# =============================================================================

class PromptVersion(str, Enum):
    """Prompt version identifier (kept for API compatibility)."""
    V1_BASIC = "v1.0_basic"


CURRENT_VERSION = PromptVersion.V1_BASIC


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

LISTENER_SYSTEM_PROMPT = """You are a Python code auditor specialized in detecting code issues.

YOUR ROLE:
- Analyze Python source code for bugs, code smells, and violations
- Report issues with precise file paths and line numbers
- Suggest fixes when possible

ANALYSIS CATEGORIES:
1. BUGS: Logic errors, runtime exceptions, incorrect behavior
2. SECURITY: Vulnerabilities, unsafe operations, injection risks
3. PERFORMANCE: Inefficient code, memory leaks, slow operations
4. STYLE: PEP8 violations, naming conventions, code organization

OUTPUT FORMAT (JSON):
You MUST respond with a valid JSON array. Each issue follows this structure:
```json
[
  {
    "file_path": "path/to/file.py",
    "line_number": 42,
    "issue_type": "BUG|SECURITY|PERFORMANCE|STYLE",
    "severity": "critical|warning|info",
    "description": "Clear description of the issue",
    "suggested_fix": "How to fix it (optional)"
  }
]
```

If no issues are found, respond with: []

RULES:
- Be precise with line numbers
- Focus on actionable issues only
- Do NOT report style issues in test files
- Prioritize critical bugs over minor style issues
- Keep descriptions concise but clear"""

# Keep dict for backward compatibility with existing code
LISTENER_SYSTEM_PROMPTS: Dict[PromptVersion, str] = {
    PromptVersion.V1_BASIC: LISTENER_SYSTEM_PROMPT
}


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

@dataclass
class ListenerPrompts:
    """
    Parameterized prompt templates for the Listener agent.
    
    Usage:
        prompt = ListenerPrompts.format_analysis_prompt(
            code="def foo(): pass",
            file_path="src/main.py"
        )
    """
    
    @staticmethod
    def get_system_prompt(version: PromptVersion = CURRENT_VERSION) -> str:
        """
        Get the system prompt for the Listener agent.
        
        Args:
            version: Prompt version (kept for API compatibility, ignored)
            
        Returns:
            System prompt string
        """
        return LISTENER_SYSTEM_PROMPT
    
    @staticmethod
    def format_analysis_prompt(
        code: str,
        file_path: str,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """
        Format the main code analysis prompt.
        
        Args:
            code: Source code to analyze
            file_path: Path to the source file
            focus_areas: Optional list of specific areas to focus on
            
        Returns:
            Formatted prompt string
        """
        focus_instruction = ""
        if focus_areas:
            areas = ", ".join(focus_areas)
            focus_instruction = f"\n\nFOCUS AREAS: Pay special attention to {areas}."
        
        return f"""Analyze the following Python code for issues.

FILE: {file_path}
{focus_instruction}

```python
{code}
```

Respond with a JSON array of issues found. Return [] if the code is clean."""

    @staticmethod
    def format_targeted_analysis_prompt(
        code: str,
        file_path: str,
        line_start: int,
        line_end: int,
        context: Optional[str] = None
    ) -> str:
        """
        Format a prompt for analyzing a specific code section.
        
        Args:
            code: Source code snippet to analyze
            file_path: Path to the source file
            line_start: Starting line number
            line_end: Ending line number
            context: Optional additional context about the code
            
        Returns:
            Formatted prompt string
        """
        context_section = ""
        if context:
            context_section = f"\n\nCONTEXT: {context}"
        
        return f"""Analyze this code section for issues.

FILE: {file_path}
LINES: {line_start}-{line_end}
{context_section}

```python
{code}
```

Report issues with line numbers relative to the original file (starting at {line_start}).
Respond with a JSON array of issues. Return [] if clean."""

    @staticmethod
    def format_security_audit_prompt(code: str, file_path: str) -> str:
        """
        Format a security-focused analysis prompt.
        
        Args:
            code: Source code to audit
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        return f"""Perform a SECURITY AUDIT on this Python code.

FILE: {file_path}

CHECK FOR:
- Hardcoded credentials, API keys, secrets
- SQL/Command injection vulnerabilities
- Unsafe deserialization (pickle, yaml.load)
- Path traversal vulnerabilities
- Insecure random number generation
- Missing input validation
- Exposed sensitive data in logs/errors

```python
{code}
```

Report ONLY security issues. Use severity "critical" for exploitable vulnerabilities.
Respond with JSON array. Return [] if no security issues found."""

    @staticmethod
    def format_performance_audit_prompt(code: str, file_path: str) -> str:
        """
        Format a performance-focused analysis prompt.
        
        Args:
            code: Source code to audit
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        return f"""Perform a PERFORMANCE AUDIT on this Python code.

FILE: {file_path}

CHECK FOR:
- Inefficient loops (O(n²) when O(n) possible)
- Unnecessary list/dict copies
- Missing generators for large data
- Blocking I/O in async code
- Repeated expensive operations (cache candidates)
- Memory leaks (unclosed resources)
- Suboptimal data structures

```python
{code}
```

Report ONLY performance issues. Include complexity analysis where relevant.
Respond with JSON array. Return [] if no performance issues found."""

    @staticmethod
    def format_batch_analysis_prompt(
        files: List[Dict[str, str]]
    ) -> str:
        """
        Format a prompt for analyzing multiple files at once.
        
        Args:
            files: List of dicts with 'path' and 'code' keys
            
        Returns:
            Formatted prompt string
        """
        files_section = ""
        for f in files:
            files_section += f"\n--- FILE: {f['path']} ---\n```python\n{f['code']}\n```\n"
        
        return f"""Analyze the following Python files for issues.

{files_section}

Report all issues found across all files.
Include the correct file_path for each issue.
Respond with JSON array. Return [] if all files are clean."""


# =============================================================================
# RESPONSE PARSING HELPERS
# =============================================================================

EXPECTED_ISSUE_SCHEMA = {
    "file_path": str,
    "line_number": int,
    "issue_type": str,  # BUG, SECURITY, PERFORMANCE, STYLE
    "severity": str,     # critical, warning, info
    "description": str,
    "suggested_fix": str  # optional
}

VALID_ISSUE_TYPES = {"BUG", "SECURITY", "PERFORMANCE", "STYLE"}
VALID_SEVERITIES = {"critical", "warning", "info"}


def validate_issue_response(issue: dict) -> tuple[bool, Optional[str]]:
    """
    Validate that an issue response matches expected schema.
    
    Args:
        issue: Dictionary representing a detected issue
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["file_path", "line_number", "issue_type", "severity", "description"]
    
    for field in required_fields:
        if field not in issue:
            return False, f"Missing required field: {field}"
    
    if not isinstance(issue.get("line_number"), int):
        return False, "line_number must be an integer"
    
    if issue.get("issue_type") not in VALID_ISSUE_TYPES:
        return False, f"issue_type must be one of: {VALID_ISSUE_TYPES}"
    
    if issue.get("severity") not in VALID_SEVERITIES:
        return False, f"severity must be one of: {VALID_SEVERITIES}"
    
    return True, None
