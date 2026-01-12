"""
Validator (Judge/Tester) Agent Prompts
======================================
System prompts and templates for the validation agent.

The Validator agent is responsible for:
- Verifying that fixes applied by the Corrector are correct
- Generating test cases to validate the fixes
- Comparing original vs fixed code behavior
- Reporting test failures back to Corrector (self-healing loop)

Optimized for: Google Gemini 1.5 Flash (free tier)
- Concise prompts to minimize token usage
- Structured output format for reliable parsing
- Clear instructions for test generation and validation

Author: Yacine (Prompt Engineer)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


# =============================================================================
# PROMPT VERSIONS - Simplified (single version, API compatible)
# =============================================================================

class ValidatorPromptVersion(str, Enum):
    """Prompt version identifier (kept for API compatibility)."""
    V1_BASIC = "v1.0_basic"


CURRENT_VERSION = ValidatorPromptVersion.V1_BASIC


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

VALIDATOR_SYSTEM_PROMPT = """You are a Python code validator and test specialist.

YOUR ROLE:
- Verify that code fixes are correct and don't break functionality
- Generate test cases to validate fixes
- Compare original vs fixed code behavior
- Report any issues found with clear error descriptions

VALIDATION CHECKLIST:
1. Syntax validity - Code compiles without errors
2. Fix correctness - The reported issues are actually fixed
3. No regressions - Original functionality still works
4. Edge cases - Fix handles boundary conditions
5. Code quality - Fix follows Python best practices

OUTPUT FORMAT (JSON):
```json
{
  "validation_passed": true|false,
  "syntax_valid": true|false,
  "fixes_verified": [
    {
      "issue_type": "BUG|SECURITY|PERFORMANCE|STYLE",
      "line_number": 42,
      "status": "FIXED|PARTIAL|NOT_FIXED",
      "explanation": "why this status"
    }
  ],
  "tests_generated": [
    {
      "test_name": "test_function_name",
      "test_code": "def test_function_name(): assert ...",
      "purpose": "what this test validates"
    }
  ],
  "regressions_found": [
    {
      "description": "what broke",
      "severity": "critical|warning|info"
    }
  ],
  "error_logs": ["detailed error messages if validation failed"],
  "recommendation": "APPROVE|REQUEST_CHANGES|REJECT"
}
```

RULES:
- Be thorough but fair in validation
- Generate meaningful tests, not trivial ones
- Clearly explain any failures
- Focus on functional correctness over style"""

# Keep dict for backward compatibility with existing code
VALIDATOR_SYSTEM_PROMPTS: Dict[ValidatorPromptVersion, str] = {
    ValidatorPromptVersion.V1_BASIC: VALIDATOR_SYSTEM_PROMPT
}


# =============================================================================
# TEST GENERATION PROMPTS
# =============================================================================

TEST_GENERATION_SYSTEM_PROMPT = """You are a Python test engineer specialized in generating pytest test cases.

YOUR TASK:
Generate comprehensive pytest test cases for the given code.

TEST TYPES TO GENERATE:
1. Unit tests - Test individual functions/methods
2. Edge case tests - Boundary conditions, empty inputs, large values
3. Error handling tests - Verify exceptions are raised correctly
4. Integration tests - Test component interactions (if applicable)

PYTEST CONVENTIONS:
- Test function names: test_<what>_<condition>_<expected>
- Use descriptive docstrings
- Use pytest.raises for exception testing
- Use parametrize for multiple test cases
- Use fixtures for setup/teardown

OUTPUT FORMAT (JSON):
```json
{
  "test_file_name": "test_module_name.py",
  "imports_needed": ["import pytest", "from module import func"],
  "fixtures": [
    {
      "name": "fixture_name",
      "code": "@pytest.fixture\\ndef fixture_name(): ..."
    }
  ],
  "test_cases": [
    {
      "name": "test_function_does_something",
      "code": "def test_function_does_something():\\n    ...",
      "category": "unit|edge_case|error_handling|integration",
      "description": "what this test validates"
    }
  ]
}
```"""


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

@dataclass
class ValidatorPrompts:
    """
    Parameterized prompt templates for the Validator agent.
    
    Usage:
        prompt = ValidatorPrompts.format_validation_prompt(
            original_code="def foo(): pass",
            fixed_code="def foo():\\n    return None",
            issues_fixed=[{"line_number": 1, "description": "Empty function"}],
            file_path="src/main.py"
        )
    """
    
    @staticmethod
    def get_system_prompt(version: ValidatorPromptVersion = CURRENT_VERSION) -> str:
        """
        Get the system prompt for the Validator agent.
        
        Args:
            version: Prompt version (kept for API compatibility, ignored)
            
        Returns:
            System prompt string
        """
        return VALIDATOR_SYSTEM_PROMPT
    
    @staticmethod
    def get_test_generation_system_prompt() -> str:
        """
        Get the system prompt for test generation mode.
        
        Returns:
            Test generation system prompt string
        """
        return TEST_GENERATION_SYSTEM_PROMPT
    
    @staticmethod
    def format_validation_prompt(
        original_code: str,
        fixed_code: str,
        issues_fixed: List[Dict[str, Any]],
        file_path: str
    ) -> str:
        """
        Format the main validation prompt.
        
        Args:
            original_code: Original code before fixes
            fixed_code: Code after Corrector applied fixes
            issues_fixed: List of issues that were supposedly fixed
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        issues_text = ValidatorPrompts._format_issues_list(issues_fixed)
        
        return f"""Validate the fixes applied to this Python code.

FILE: {file_path}

ISSUES THAT WERE FIXED:
{issues_text}

ORIGINAL CODE:
```python
{original_code}
```

FIXED CODE:
```python
{fixed_code}
```

Validate that:
1. The fixed code has valid syntax
2. Each issue listed above is properly fixed
3. No new bugs or regressions were introduced
4. Generate test cases to verify the fixes

Return your validation results in JSON format."""

    @staticmethod
    def format_quick_validation_prompt(
        fixed_code: str,
        issues_fixed: List[Dict[str, Any]],
        file_path: str
    ) -> str:
        """
        Format a quick validation prompt (no original code comparison).
        
        Args:
            fixed_code: Code after fixes were applied
            issues_fixed: List of issues that were supposedly fixed
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        issues_text = ValidatorPrompts._format_issues_list(issues_fixed)
        
        return f"""Quickly validate this fixed Python code.

FILE: {file_path}

ISSUES THAT SHOULD BE FIXED:
{issues_text}

FIXED CODE:
```python
{fixed_code}
```

Check:
1. Syntax is valid
2. The issues appear to be addressed
3. No obvious new problems

Return validation results in JSON format."""

    @staticmethod
    def format_test_generation_prompt(
        code: str,
        file_path: str,
        functions_to_test: Optional[List[str]] = None
    ) -> str:
        """
        Format a prompt for generating test cases.
        
        Args:
            code: Code to generate tests for
            file_path: Path to the source file
            functions_to_test: Optional list of specific functions to test
            
        Returns:
            Formatted prompt string
        """
        focus_section = ""
        if functions_to_test:
            funcs = ", ".join(functions_to_test)
            focus_section = f"\n\nFOCUS ON THESE FUNCTIONS: {funcs}"
        
        return f"""Generate pytest test cases for this Python code.

FILE: {file_path}
{focus_section}

CODE TO TEST:
```python
{code}
```

Generate comprehensive tests including:
- Normal operation tests
- Edge case tests (empty inputs, large values, None)
- Error handling tests (invalid inputs, exceptions)

Return test cases in JSON format."""

    @staticmethod
    def format_regression_check_prompt(
        original_code: str,
        fixed_code: str,
        file_path: str,
        existing_tests: Optional[str] = None
    ) -> str:
        """
        Format a prompt for checking regressions.
        
        Args:
            original_code: Original code before fixes
            fixed_code: Code after fixes
            file_path: Path to the source file
            existing_tests: Existing test code if available
            
        Returns:
            Formatted prompt string
        """
        tests_section = ""
        if existing_tests:
            tests_section = f"""
EXISTING TESTS:
```python
{existing_tests}
```
"""
        
        return f"""Check for regressions between original and fixed code.

FILE: {file_path}

ORIGINAL CODE:
```python
{original_code}
```

FIXED CODE:
```python
{fixed_code}
```
{tests_section}
Analyze if any existing functionality was broken by the fixes.

Check for:
1. Changed function signatures
2. Modified return values
3. Altered exception behavior
4. Removed or renamed functions/classes
5. Changed default values

Return regression analysis in JSON format:
{{
  "regressions_found": true|false,
  "details": [
    {{
      "location": "function or class name",
      "change_type": "signature|return_value|exception|removal|rename",
      "original_behavior": "what it did before",
      "new_behavior": "what it does now",
      "severity": "critical|warning|info",
      "breaking": true|false
    }}
  ],
  "safe_to_deploy": true|false
}}"""

    @staticmethod
    def format_fix_verification_prompt(
        fixed_code: str,
        specific_issue: Dict[str, Any],
        file_path: str
    ) -> str:
        """
        Format a prompt for verifying a single specific fix.
        
        Args:
            fixed_code: Code after the fix
            specific_issue: The specific issue to verify
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        issue_text = ValidatorPrompts._format_single_issue(specific_issue)
        
        return f"""Verify this specific fix was applied correctly.

FILE: {file_path}

ISSUE THAT WAS FIXED:
{issue_text}

FIXED CODE:
```python
{fixed_code}
```

Verify:
1. The specific issue at line {specific_issue.get('line_number', '?')} is fixed
2. The fix is correct and complete
3. No side effects from the fix

Return verification in JSON format:
{{
  "issue_fixed": true|false,
  "fix_quality": "correct|partial|incorrect",
  "explanation": "detailed analysis",
  "test_to_verify": "pytest code to test this fix"
}}"""

    @staticmethod
    def format_batch_validation_prompt(
        validations: List[Dict[str, Any]]
    ) -> str:
        """
        Format a prompt for validating multiple fixes at once.
        
        Args:
            validations: List of dicts with 'file_path', 'original_code', 
                        'fixed_code', and 'issues_fixed' keys
            
        Returns:
            Formatted prompt string
        """
        files_section = ""
        for i, v in enumerate(validations, 1):
            issues_text = ValidatorPrompts._format_issues_list(v.get('issues_fixed', []))
            files_section += f"""
--- FILE {i}: {v['file_path']} ---
ISSUES FIXED:
{issues_text}

ORIGINAL:
```python
{v.get('original_code', 'Not provided')}
```

FIXED:
```python
{v['fixed_code']}
```
"""
        
        return f"""Validate fixes for multiple files.

{files_section}

For EACH file, validate:
1. Syntax is valid
2. Issues are properly fixed
3. No regressions

Return validation for all files in JSON format:
{{
  "files": [
    {{
      "file_path": "path",
      "validation_passed": true|false,
      "fixes_verified": [...],
      "error_logs": [...]
    }}
  ],
  "overall_recommendation": "APPROVE|REQUEST_CHANGES|REJECT"
}}"""

    @staticmethod
    def format_error_analysis_prompt(
        code: str,
        error_output: str,
        file_path: str
    ) -> str:
        """
        Format a prompt for analyzing test/runtime errors.
        
        Used to generate helpful error_logs for the self-healing loop.
        
        Args:
            code: Code that caused the error
            error_output: Error message or traceback
            file_path: Path to the source file
            
        Returns:
            Formatted prompt string
        """
        return f"""Analyze this error and provide actionable feedback.

FILE: {file_path}

CODE:
```python
{code}
```

ERROR OUTPUT:
```
{error_output}
```

Analyze:
1. What is the root cause of this error?
2. Which line(s) are responsible?
3. What specific change would fix it?

Return analysis in JSON format:
{{
  "error_type": "SyntaxError|TypeError|ValueError|etc",
  "root_cause": "clear explanation of why this error occurred",
  "responsible_lines": [line_numbers],
  "fix_suggestion": "specific code change to fix this",
  "error_log_for_corrector": "formatted message for the Corrector agent"
}}"""

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @staticmethod
    def _format_issues_list(issues: List[Dict[str, Any]]) -> str:
        """Format a list of issues into readable text."""
        if not issues:
            return "No specific issues listed."
        
        formatted = []
        for i, issue in enumerate(issues, 1):
            line = issue.get('line_number', '?')
            issue_type = issue.get('issue_type', 'UNKNOWN')
            severity = issue.get('severity', 'info')
            description = issue.get('description', 'No description')
            
            entry = f"{i}. [{severity.upper()}] Line {line} - {issue_type}: {description}"
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


# =============================================================================
# RESPONSE PARSING & VALIDATION
# =============================================================================

VALID_RECOMMENDATIONS = {"APPROVE", "REQUEST_CHANGES", "REJECT"}
VALID_FIX_STATUSES = {"FIXED", "PARTIAL", "NOT_FIXED"}


def validate_validation_response(response: dict) -> tuple[bool, Optional[str]]:
    """
    Validate that a validation response matches expected schema.
    
    Args:
        response: Dictionary representing the validation response
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check required fields
    required_fields = ["validation_passed", "syntax_valid"]
    for field in required_fields:
        if field not in response:
            return False, f"Missing required field: {field}"
    
    if not isinstance(response.get("validation_passed"), bool):
        return False, "validation_passed must be a boolean"
    
    if not isinstance(response.get("syntax_valid"), bool):
        return False, "syntax_valid must be a boolean"
    
    # Validate recommendation if present
    if "recommendation" in response:
        if response["recommendation"] not in VALID_RECOMMENDATIONS:
            return False, f"recommendation must be one of: {VALID_RECOMMENDATIONS}"
    
    # Validate fixes_verified if present
    if "fixes_verified" in response:
        if not isinstance(response["fixes_verified"], list):
            return False, "fixes_verified must be a list"
        
        for i, fix in enumerate(response["fixes_verified"]):
            if not isinstance(fix, dict):
                return False, f"fixes_verified[{i}] must be a dictionary"
            if "status" in fix and fix["status"] not in VALID_FIX_STATUSES:
                return False, f"fixes_verified[{i}].status must be one of: {VALID_FIX_STATUSES}"
    
    return True, None


def extract_error_logs(response: dict) -> List[str]:
    """
    Extract error logs from validation response for self-healing loop.
    
    Args:
        response: Validation response dictionary
        
    Returns:
        List of error log strings
    """
    error_logs = []
    
    # Get explicit error_logs
    if "error_logs" in response and isinstance(response["error_logs"], list):
        error_logs.extend(response["error_logs"])
    
    # Get syntax errors
    if "syntax_errors" in response and isinstance(response["syntax_errors"], list):
        error_logs.extend(response["syntax_errors"])
    
    # Get regression descriptions
    if "regressions_found" in response and isinstance(response["regressions_found"], list):
        for reg in response["regressions_found"]:
            if isinstance(reg, dict) and "description" in reg:
                error_logs.append(f"Regression: {reg['description']}")
    
    # Get unfixed issues
    if "fixes_verified" in response and isinstance(response["fixes_verified"], list):
        for fix in response["fixes_verified"]:
            if isinstance(fix, dict) and fix.get("status") in ("PARTIAL", "NOT_FIXED"):
                error_logs.append(
                    f"Issue not fixed at line {fix.get('line_number', '?')}: "
                    f"{fix.get('explanation', 'No explanation')}"
                )
    
    return error_logs


def extract_generated_tests(response: dict) -> List[Dict[str, str]]:
    """
    Extract generated test cases from validation response.
    
    Args:
        response: Validation response dictionary
        
    Returns:
        List of test case dictionaries with 'name', 'code', 'purpose'
    """
    tests = []
    
    if "tests_generated" in response and isinstance(response["tests_generated"], list):
        for test in response["tests_generated"]:
            if isinstance(test, dict) and "test_code" in test:
                tests.append({
                    "name": test.get("test_name", "test_unnamed"),
                    "code": test["test_code"],
                    "purpose": test.get("purpose", "")
                })
    
    # Also check test_cases (alternative key)
    if "test_cases" in response and isinstance(response["test_cases"], list):
        for test in response["test_cases"]:
            if isinstance(test, dict) and "code" in test:
                tests.append({
                    "name": test.get("name", "test_unnamed"),
                    "code": test["code"],
                    "purpose": test.get("description", "")
                })
    
    return tests


def should_trigger_self_healing(response: dict) -> bool:
    """
    Determine if the validation response should trigger self-healing loop.
    
    Args:
        response: Validation response dictionary
        
    Returns:
        True if Corrector should retry, False if fix is approved
    """
    # Not passed = needs retry
    if not response.get("validation_passed", False):
        return True
    
    # Syntax errors = needs retry
    if not response.get("syntax_valid", True):
        return True
    
    # REQUEST_CHANGES or REJECT = needs retry
    recommendation = response.get("recommendation", "APPROVE")
    if recommendation in ("REQUEST_CHANGES", "REJECT"):
        return True
    
    # Check for unfixed issues
    fixes = response.get("fixes_verified", [])
    for fix in fixes:
        if isinstance(fix, dict) and fix.get("status") in ("PARTIAL", "NOT_FIXED"):
            return True
    
    return False
