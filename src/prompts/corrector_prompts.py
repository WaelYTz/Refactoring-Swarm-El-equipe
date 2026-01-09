"""
Corrector (Fixer) Agent Prompts
===============================
System prompts and templates for the code correction agent.

The Corrector agent is responsible for:
- Receiving issues detected by the Listener agent
- Generating corrected code that fixes the issues
- Preserving original functionality while applying fixes
- Handling self-healing loop (fixing based on Validator error logs)

Optimized for: Google Gemini 1.5 Flash (free tier)
- Concise prompts to minimize token usage
- Structured output format for reliable parsing
- Clear instructions to reduce hallucinations and preserve code integrity

Author: Yacine (Prompt Engineer)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


# =============================================================================
# PROMPT VERSIONS - For A/B Testing
# =============================================================================

class CorrectorPromptVersion(str, Enum):
    """Track prompt versions for experimentation."""
    V1_BASIC = "v1.0_basic"
    V1_DETAILED = "v1.1_detailed"
    V2_OPTIMIZED = "v2.0_optimized"


CURRENT_VERSION = CorrectorPromptVersion.V1_BASIC


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

CORRECTOR_SYSTEM_PROMPTS: Dict[CorrectorPromptVersion, str] = {
    
    CorrectorPromptVersion.V1_BASIC: """You are a Python code fixer specialized in correcting code issues.

YOUR ROLE:
- Receive code with detected issues and generate corrected versions
- Fix bugs, security vulnerabilities, performance problems, and style issues
- Preserve original functionality - DO NOT break working code
- Maintain code style and formatting consistency

FIX PRIORITIES:
1. CRITICAL bugs and security issues first
2. Performance improvements second
3. Style/convention fixes last

OUTPUT FORMAT (JSON):
You MUST respond with a valid JSON object:
```json
{
  "fixed_code": "the complete corrected Python code",
  "changes_made": [
    {
      "line_number": 42,
      "issue_type": "BUG|SECURITY|PERFORMANCE|STYLE",
      "original": "original code snippet",
      "fixed": "fixed code snippet",
      "explanation": "brief explanation of the fix"
    }
  ],
  "warnings": ["any warnings about potential side effects"]
}
```

RULES:
- Return the COMPLETE fixed code, not just snippets
- Do NOT add unnecessary changes
- Preserve all comments and docstrings
- Keep the same variable/function names unless they are the issue
- If you cannot fix an issue safely, explain why in warnings
- Test your logic mentally before outputting""",

    CorrectorPromptVersion.V1_DETAILED: """You are an expert Python developer and code repair specialist.

YOUR MISSION:
Transform buggy or problematic code into clean, working, secure code while maintaining the original intent and functionality.

FIX APPROACH:
1. Understand the original code's purpose
2. Identify each issue and its root cause
3. Apply minimal, targeted fixes
4. Verify fixes don't introduce new problems
5. Maintain code readability and style

FIXING GUIDELINES BY TYPE:

BUG FIXES:
- Division by zero → Add validation checks
- Null/None references → Add None checks or default values
- Off-by-one errors → Correct loop bounds
- Type errors → Add type conversion or validation
- Logic errors → Fix conditional logic

SECURITY FIXES:
- SQL injection → Use parameterized queries
- Command injection → Use subprocess with list args, no shell=True
- Hardcoded secrets → Replace with environment variables
- Unsafe deserialization → Use safe alternatives (json, yaml.safe_load)
- Path traversal → Validate and sanitize paths

PERFORMANCE FIXES:
- O(n²) loops → Optimize with sets/dicts
- Repeated calculations → Cache results
- Memory leaks → Properly close resources (use 'with' statements)
- Blocking I/O → Suggest async alternatives

STYLE FIXES:
- PEP8 violations → Apply correct formatting
- Naming conventions → Use snake_case for functions/variables
- Missing docstrings → Add brief, clear documentation

OUTPUT FORMAT:
```json
{
  "fixed_code": "complete corrected Python code with all fixes applied",
  "changes_made": [
    {
      "line_number": 42,
      "issue_type": "BUG|SECURITY|PERFORMANCE|STYLE",
      "original": "problematic code line or snippet",
      "fixed": "corrected code line or snippet",
      "explanation": "why this change fixes the issue"
    }
  ],
  "warnings": ["potential side effects or things to test"],
  "tests_recommended": ["suggested test cases for the fixes"]
}
```

CRITICAL RULES:
- NEVER remove functionality that isn't broken
- ALWAYS return syntactically valid Python
- PRESERVE imports, comments, and structure
- If unsure about a fix, add it to warnings instead of guessing""",

    CorrectorPromptVersion.V2_OPTIMIZED: """You are a Python code fixer. Fix issues while preserving functionality.

PRIORITIES: 1) Critical bugs/security 2) Performance 3) Style

OUTPUT (JSON only):
{
  "fixed_code": "complete fixed Python code",
  "changes_made": [{"line_number":N,"issue_type":"TYPE","original":"old","fixed":"new","explanation":"why"}],
  "warnings": ["side effects if any"]
}

Return complete code. Minimal changes only. Keep style consistent."""
}


# =============================================================================
# SELF-HEALING LOOP PROMPTS
# =============================================================================

SELF_HEALING_SYSTEM_PROMPT = """You are a Python code fixer in SELF-HEALING MODE.

CONTEXT:
Your previous fix attempt was tested and FAILED. You are receiving:
1. The current code (with your previous fixes)
2. The original issues that needed fixing
3. ERROR LOGS from the test failures

YOUR TASK:
Analyze the error logs, understand WHY the tests failed, and produce a NEW fix that:
- Addresses the original issues
- Fixes the problems that caused test failures
- Does not introduce new bugs

COMMON FAILURE PATTERNS:
- Syntax errors → Check for typos, missing colons, indentation
- Import errors → Ensure all imports are present
- Attribute errors → Verify object types and method names
- Type errors → Check type compatibility
- Logic errors → Re-examine the fix logic
- Test assertion failures → The fix may be incorrect or incomplete

OUTPUT FORMAT (JSON):
{
  "fixed_code": "complete corrected Python code",
  "changes_made": [
    {
      "line_number": 42,
      "issue_type": "BUG|SECURITY|PERFORMANCE|STYLE",
      "original": "code from previous attempt",
      "fixed": "new corrected code",
      "explanation": "why this fixes the test failure"
    }
  ],
  "error_analysis": "what went wrong with the previous fix",
  "confidence": "high|medium|low"
}

Be extra careful - this is a retry attempt. Analyze errors thoroughly."""


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

@dataclass
class CorrectorPrompts:
    """
    Parameterized prompt templates for the Corrector agent.
    
    Usage:
        prompt = CorrectorPrompts.format_correction_prompt(
            code="def foo(): pass",
            issues=[{"line_number": 1, "description": "Empty function"}],
            file_path="src/main.py"
        )
    """
    
    @staticmethod
    def get_system_prompt(version: CorrectorPromptVersion = CURRENT_VERSION) -> str:
        """
        Get the system prompt for the Corrector agent.
        
        Args:
            version: Prompt version to use (for A/B testing)
            
        Returns:
            System prompt string
        """
        return CORRECTOR_SYSTEM_PROMPTS.get(version, CORRECTOR_SYSTEM_PROMPTS[CURRENT_VERSION])
    
    @staticmethod
    def get_self_healing_system_prompt() -> str:
        """
        Get the system prompt for self-healing mode.
        
        Used when the Validator reports test failures and we need to retry.
        
        Returns:
            Self-healing system prompt string
        """
        return SELF_HEALING_SYSTEM_PROMPT
    
    @staticmethod
    def format_correction_prompt(
        code: str,
        issues: List[Dict[str, Any]],
        file_path: str
    ) -> str:
        """
        Format the main code correction prompt.
        
        Args:
            code: Source code to fix
            issues: List of issues detected by Listener agent
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        # Format issues into readable list
        issues_text = CorrectorPrompts._format_issues_list(issues)
        
        return f"""Fix the following Python code based on the detected issues.

FILE: {file_path}

DETECTED ISSUES:
{issues_text}

ORIGINAL CODE:
```python
{code}
```

Apply fixes for all issues listed above. Return the complete fixed code in JSON format."""

    @staticmethod
    def format_targeted_fix_prompt(
        code: str,
        issue: Dict[str, Any],
        file_path: str,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None
    ) -> str:
        """
        Format a prompt for fixing a single specific issue.
        
        Args:
            code: Source code snippet to fix
            issue: Single issue to fix
            file_path: Path to the source file
            context_before: Code before the problematic section
            context_after: Code after the problematic section
            
        Returns:
            Formatted prompt string
        """
        issue_text = CorrectorPrompts._format_single_issue(issue)
        
        context_section = ""
        if context_before:
            context_section += f"\nCODE BEFORE (for context, do not modify):\n```python\n{context_before}\n```\n"
        if context_after:
            context_section += f"\nCODE AFTER (for context, do not modify):\n```python\n{context_after}\n```\n"
        
        return f"""Fix this specific issue in the Python code.

FILE: {file_path}

ISSUE TO FIX:
{issue_text}
{context_section}
CODE TO FIX:
```python
{code}
```

Apply ONLY the fix for the issue listed above. Return the fixed code in JSON format."""

    @staticmethod
    def format_self_healing_prompt(
        code: str,
        issues: List[Dict[str, Any]],
        error_logs: List[str],
        file_path: str,
        attempt_number: int = 1
    ) -> str:
        """
        Format a prompt for self-healing loop (when previous fix failed tests).
        
        This is called when the Validator reports test failures and we need
        to send the Corrector back to fix the issues again with error context.
        
        Args:
            code: Current code (with previous fix attempts)
            issues: Original issues from Listener
            error_logs: Test failure logs from Validator
            file_path: Path to the source file
            attempt_number: Which retry attempt this is
            
        Returns:
            Formatted prompt string
        """
        issues_text = CorrectorPrompts._format_issues_list(issues)
        errors_text = CorrectorPrompts._format_error_logs(error_logs)
        
        return f"""SELF-HEALING MODE - Fix Attempt #{attempt_number}

Your previous fix was tested and FAILED. Analyze the errors and try again.

FILE: {file_path}

ORIGINAL ISSUES TO FIX:
{issues_text}

TEST FAILURE LOGS:
{errors_text}

CURRENT CODE (with previous fix attempt):
```python
{code}
```

Analyze what went wrong, then provide a corrected version that:
1. Fixes the original issues
2. Resolves the test failures
3. Does not introduce new problems

Return the complete fixed code in JSON format."""

    @staticmethod
    def format_batch_correction_prompt(
        files_with_issues: List[Dict[str, Any]]
    ) -> str:
        """
        Format a prompt for fixing multiple files at once.
        
        Args:
            files_with_issues: List of dicts with 'path', 'code', and 'issues' keys
            
        Returns:
            Formatted prompt string
        """
        files_section = ""
        for i, f in enumerate(files_with_issues, 1):
            issues_text = CorrectorPrompts._format_issues_list(f.get('issues', []))
            files_section += f"""
--- FILE {i}: {f['path']} ---
ISSUES:
{issues_text}

CODE:
```python
{f['code']}
```
"""
        
        return f"""Fix the following Python files based on their detected issues.

{files_section}

Return fixes for ALL files in JSON format:
{{
  "files": [
    {{
      "file_path": "path/to/file.py",
      "fixed_code": "complete fixed code",
      "changes_made": [...]
    }}
  ]
}}"""

    @staticmethod
    def format_security_fix_prompt(
        code: str,
        security_issues: List[Dict[str, Any]],
        file_path: str
    ) -> str:
        """
        Format a prompt specifically for security fixes.
        
        Args:
            code: Source code with security vulnerabilities
            security_issues: List of security-related issues
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        issues_text = CorrectorPrompts._format_issues_list(security_issues)
        
        return f"""SECURITY FIX REQUIRED - Apply security patches to this code.

FILE: {file_path}

SECURITY VULNERABILITIES:
{issues_text}

VULNERABLE CODE:
```python
{code}
```

SECURITY FIX GUIDELINES:
- SQL injection → Use parameterized queries (cursor.execute(query, params))
- Command injection → Use subprocess with list args, avoid shell=True
- Hardcoded secrets → Replace with os.environ.get('SECRET_NAME')
- Unsafe pickle/yaml → Use json or yaml.safe_load
- Path traversal → Validate paths with os.path.realpath and check prefix

Apply ALL security fixes. Return the complete secured code in JSON format."""

    @staticmethod
    def format_refactor_prompt(
        code: str,
        refactor_suggestions: List[str],
        file_path: str
    ) -> str:
        """
        Format a prompt for code refactoring (not bug fixing).
        
        Args:
            code: Source code to refactor
            refactor_suggestions: List of refactoring suggestions
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        suggestions = "\n".join(f"- {s}" for s in refactor_suggestions)
        
        return f"""Refactor this Python code for better quality.

FILE: {file_path}

REFACTORING GOALS:
{suggestions}

ORIGINAL CODE:
```python
{code}
```

REFACTORING RULES:
- Improve readability without changing behavior
- Apply Python best practices and idioms
- Add type hints if missing
- Improve variable/function names if unclear
- Break down complex functions if needed

Return the refactored code in JSON format. Include explanation for each change."""

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @staticmethod
    def _format_issues_list(issues: List[Dict[str, Any]]) -> str:
        """Format a list of issues into readable text."""
        if not issues:
            return "No specific issues provided."
        
        formatted = []
        for i, issue in enumerate(issues, 1):
            line = issue.get('line_number', '?')
            issue_type = issue.get('issue_type', 'UNKNOWN')
            severity = issue.get('severity', 'info')
            description = issue.get('description', 'No description')
            suggested_fix = issue.get('suggested_fix', '')
            
            entry = f"{i}. [{severity.upper()}] Line {line} - {issue_type}: {description}"
            if suggested_fix:
                entry += f"\n   Suggested fix: {suggested_fix}"
            formatted.append(entry)
        
        return "\n".join(formatted)
    
    @staticmethod
    def _format_single_issue(issue: Dict[str, Any]) -> str:
        """Format a single issue into readable text."""
        line = issue.get('line_number', '?')
        issue_type = issue.get('issue_type', 'UNKNOWN')
        severity = issue.get('severity', 'info')
        description = issue.get('description', 'No description')
        suggested_fix = issue.get('suggested_fix', '')
        
        text = f"[{severity.upper()}] Line {line} - {issue_type}\n"
        text += f"Description: {description}"
        if suggested_fix:
            text += f"\nSuggested fix: {suggested_fix}"
        
        return text
    
    @staticmethod
    def _format_error_logs(error_logs: List[str]) -> str:
        """Format error logs into readable text."""
        if not error_logs:
            return "No error logs provided."
        
        formatted = []
        for i, log in enumerate(error_logs, 1):
            # Truncate very long logs to save tokens
            if len(log) > 500:
                log = log[:500] + "\n... (truncated)"
            formatted.append(f"Error {i}:\n{log}")
        
        return "\n\n".join(formatted)


# =============================================================================
# RESPONSE PARSING & VALIDATION
# =============================================================================

EXPECTED_CORRECTION_SCHEMA = {
    "fixed_code": str,
    "changes_made": list,
    "warnings": list  # optional
}

EXPECTED_CHANGE_SCHEMA = {
    "line_number": int,
    "issue_type": str,
    "original": str,
    "fixed": str,
    "explanation": str
}


def validate_correction_response(response: dict) -> tuple[bool, Optional[str]]:
    """
    Validate that a correction response matches expected schema.
    
    Args:
        response: Dictionary representing the correction response
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    if "fixed_code" not in response:
        return False, "Missing required field: fixed_code"
    
    if not isinstance(response.get("fixed_code"), str):
        return False, "fixed_code must be a string"
    
    if len(response.get("fixed_code", "").strip()) == 0:
        return False, "fixed_code cannot be empty"
    
    # Check changes_made if present
    if "changes_made" in response:
        if not isinstance(response["changes_made"], list):
            return False, "changes_made must be a list"
        
        for i, change in enumerate(response["changes_made"]):
            if not isinstance(change, dict):
                return False, f"changes_made[{i}] must be a dictionary"
            
            # Validate each change has required fields
            required = ["line_number", "original", "fixed", "explanation"]
            for field in required:
                if field not in change:
                    return False, f"changes_made[{i}] missing field: {field}"
    
    return True, None


def validate_python_syntax(code: str) -> tuple[bool, Optional[str]]:
    """
    Validate that the generated code has valid Python syntax.
    
    Args:
        code: Python code string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        compile(code, '<string>', 'exec')
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def extract_code_from_response(response: dict) -> Optional[str]:
    """
    Safely extract the fixed code from a correction response.
    
    Args:
        response: Dictionary containing the correction response
        
    Returns:
        The fixed code string, or None if not found
    """
    if not isinstance(response, dict):
        return None
    
    fixed_code = response.get("fixed_code")
    
    if not isinstance(fixed_code, str):
        return None
    
    # Clean up code (remove markdown code blocks if present)
    code = fixed_code.strip()
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    
    return code.strip()
