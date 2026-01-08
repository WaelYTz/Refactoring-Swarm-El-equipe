"""
Prompts Module
==============
Contains all system prompts, templates, and context management for the swarm agents.

This module provides:
- System prompts for each agent (Listener, Corrector, Validator)
- Parameterized prompt templates with {code}, {issues}, {file_path} placeholders
- Context management utilities (chunking, token counting)
- Prompt versioning for A/B testing

Module Structure:
- listener_prompts.py:  Auditor analysis prompts for code issue detection
- corrector_prompts.py: Fixer prompts with issue context for code correction
- validator_prompts.py: Test validation prompts for verifying fixes
- context_manager.py:   Code chunking and token management utilities

Usage:
    from src.prompts import (
        ListenerPrompts,
        CorrectorPrompts, 
        ValidatorPrompts,
        ContextManager
    )
    
    # Get system prompt for listener agent
    system_prompt = ListenerPrompts.get_system_prompt()
    
    # Format a template with code context
    prompt = ListenerPrompts.format_analysis_prompt(
        code="def foo(): pass",
        file_path="src/main.py"
    )
    
    # Manage context for large codebases
    chunks = ContextManager.chunk_code(large_code, max_tokens=4000)

Author: Yacine (Prompt Engineer)
"""

# Imports will be added as modules are implemented
from src.prompts.listener_prompts import ListenerPrompts, PromptVersion, validate_issue_response
# from src.prompts.corrector_prompts import CorrectorPrompts
# from src.prompts.validator_prompts import ValidatorPrompts
# from src.prompts.context_manager import ContextManager

__all__ = [
    "ListenerPrompts",
    "PromptVersion",
    "validate_issue_response",
    # "CorrectorPrompts", 
    # "ValidatorPrompts",
    # "ContextManager",
]

# Prompt version tracking for A/B testing
PROMPT_VERSION = "1.0.0"
