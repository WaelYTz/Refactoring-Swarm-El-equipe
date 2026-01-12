"""
Prompts Module
==============
Contains all system prompts, templates, and context management for the swarm agents.

This module provides:
- System prompts for each agent (Listener, Corrector, Validator)
- Parameterized prompt templates with {code}, {issues}, {file_path} placeholders
- Context optimization (remove comments/docstrings to save tokens)
- Prompt versioning for A/B testing

Module Structure:
- listener_prompts.py:  Auditor analysis prompts for code issue detection
- corrector_prompts.py: Fixer prompts with issue context for code correction
- validator_prompts.py: Test validation prompts for verifying fixes
- context_manager.py:   Code optimization and token management utilities

Usage:
    from src.prompts import (
        ListenerPrompts,
        CorrectorPrompts, 
        ValidatorPrompts,
        optimize_context,
        prepare_code_for_ai
    )
    
    # Get system prompt for listener agent
    system_prompt = ListenerPrompts.get_system_prompt()
    
    # Format a template with code context
    prompt = ListenerPrompts.format_analysis_prompt(
        code="def foo(): pass",
        file_path="src/main.py"
    )
    
    # Optimize code before sending to AI (removes comments/docstrings)
    clean_code = optimize_context(large_code)
    
    # Or use the all-in-one function
    result = prepare_code_for_ai(code, file_path="src/main.py")
    if result['fits_in_context']:
        send_to_gemini(result['optimized_code'])

Author: Yacine (Prompt Engineer)
"""

# Imports will be added as modules are implemented
from src.prompts.listener_prompts import ListenerPrompts, PromptVersion, validate_issue_response
from src.prompts.corrector_prompts import (
    CorrectorPrompts, 
    CorrectorPromptVersion,
    validate_correction_response,
    validate_python_syntax,
    extract_code_from_response
)
from src.prompts.validator_prompts import (
    ValidatorPrompts,
    ValidatorPromptVersion,
    validate_validation_response,
    extract_error_logs,
    extract_generated_tests,
    should_trigger_self_healing
)
from src.prompts.context_manager import (
    optimize_context,
    count_tokens,
    is_context_too_large,
    prepare_code_for_ai,
    get_optimization_stats
)

__all__ = [
    "ListenerPrompts",
    "PromptVersion",
    "validate_issue_response",
    "CorrectorPrompts",
    "CorrectorPromptVersion",
    "validate_correction_response",
    "validate_python_syntax",
    "extract_code_from_response",
    "ValidatorPrompts",
    "ValidatorPromptVersion",
    "validate_validation_response",
    "extract_error_logs",
    "extract_generated_tests",
    "should_trigger_self_healing",
    "optimize_context",
    "count_tokens",
    "is_context_too_large",
    "prepare_code_for_ai",
    "get_optimization_stats",
]

# Prompt version tracking for A/B testing
PROMPT_VERSION = "1.0.0"
