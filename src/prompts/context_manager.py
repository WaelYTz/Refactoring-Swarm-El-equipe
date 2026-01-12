"""
Context Manager
===============
Simple utility to optimize code context before sending to LLM.

Purpose:
- Reduce token count by removing unnecessary content
- Prevent overloading the AI's context window
- Ensure agents send clean, relevant code only

Optimization Technique:
- Remove # comments (except important ones like TODO, FIXME)
- Remove docstrings (triple quotes)
- Remove excessive empty lines
- Remove trailing whitespace

Target Model: Google Gemini 2.5 Flash

Usage:
    from src.prompts.context_manager import optimize_context, count_tokens
    
    # Before sending to AI:
    clean_code = optimize_context(original_code)
    
    # Check token count:
    tokens = count_tokens(clean_code)

Author: Yacine (Prompt Engineer)
"""

import re
from typing import Optional


# =============================================================================
# CONSTANTS
# =============================================================================

# Gemini 2.5 Flash - safe limits
MAX_RECOMMENDED_TOKENS = 8000   # Safe limit per request
CHARS_PER_TOKEN = 4             # ~4 characters per token for code


# =============================================================================
# MAIN FUNCTIONS
# =============================================================================

def count_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Simple estimation: ~4 characters = 1 token for code.
    
    Args:
        text: The text to count
        
    Returns:
        Estimated token count
        
    Example:
        >>> count_tokens("def hello(): pass")
        5
    """
    if not text:
        return 0
    return len(text) // CHARS_PER_TOKEN + 1


def optimize_context(
    code: str,
    remove_comments: bool = True,
    remove_docstrings: bool = True,
    remove_empty_lines: bool = True,
    keep_important_comments: bool = True
) -> str:
    """
    Optimize code for LLM context by removing unnecessary content.
    
    This is THE main function that all agents should use before 
    sending code to Gemini. It reduces token count while keeping
    the code functional and analyzable.
    
    Args:
        code: Original source code
        remove_comments: Remove # comments (default: True)
        remove_docstrings: Remove triple-quoted strings (default: True)
        remove_empty_lines: Remove blank lines (default: True)
        keep_important_comments: Keep TODO, FIXME, BUG, HACK comments (default: True)
        
    Returns:
        Optimized code with reduced token count
        
    Example:
        >>> code = '''
        ... # This is a comment
        ... def foo():
        ...     \"\"\"This is a docstring\"\"\"
        ...     pass
        ... '''
        >>> clean = optimize_context(code)
        >>> print(clean)
        def foo():
            pass
    """
    if not code:
        return ""
    
    result = code
    
    # Step 1: Remove docstrings (triple quotes)
    if remove_docstrings:
        result = _remove_docstrings(result)
    
    # Step 2: Remove comments
    if remove_comments:
        result = _remove_comments(result, keep_important=keep_important_comments)
    
    # Step 3: Remove empty lines and clean up
    if remove_empty_lines:
        result = _remove_empty_lines(result)
    
    # Step 4: Remove trailing whitespace from each line
    result = _clean_whitespace(result)
    
    return result


def is_context_too_large(code: str, max_tokens: int = MAX_RECOMMENDED_TOKENS) -> bool:
    """
    Check if code is too large for the AI context.
    
    Use this to decide if you need to optimize or warn the user.
    
    Args:
        code: The code to check
        max_tokens: Maximum recommended tokens (default: 8000)
        
    Returns:
        True if code exceeds limit, False otherwise
        
    Example:
        >>> is_context_too_large("short code")
        False
    """
    return count_tokens(code) > max_tokens


def get_optimization_stats(original: str, optimized: str) -> dict:
    """
    Get statistics about the optimization.
    
    Useful for logging and debugging.
    
    Args:
        original: Original code
        optimized: Optimized code
        
    Returns:
        Dict with token counts and savings
        
    Example:
        >>> stats = get_optimization_stats(original_code, clean_code)
        >>> print(f"Saved {stats['tokens_saved']} tokens ({stats['percentage_saved']}%)")
    """
    original_tokens = count_tokens(original)
    optimized_tokens = count_tokens(optimized)
    tokens_saved = original_tokens - optimized_tokens
    
    percentage = 0
    if original_tokens > 0:
        percentage = round((tokens_saved / original_tokens) * 100, 1)
    
    return {
        "original_tokens": original_tokens,
        "optimized_tokens": optimized_tokens,
        "tokens_saved": tokens_saved,
        "percentage_saved": percentage,
        "original_lines": len(original.split('\n')),
        "optimized_lines": len(optimized.split('\n'))
    }


# =============================================================================
# HELPER FUNCTIONS (Internal)
# =============================================================================

def _remove_docstrings(code: str) -> str:
    """
    Remove triple-quoted docstrings from code.
    
    Handles both ''' and \"\"\" docstrings.
    """
    # Remove """ docstrings
    result = re.sub(r'"""[\s\S]*?"""', '', code)
    # Remove ''' docstrings
    result = re.sub(r"'''[\s\S]*?'''", '', result)
    return result


def _remove_comments(code: str, keep_important: bool = True) -> str:
    """
    Remove # comments from code.
    
    Optionally keeps important comments (TODO, FIXME, BUG, HACK, NOTE).
    """
    lines = code.split('\n')
    result_lines = []
    
    # Important comment patterns to keep
    important_patterns = ['TODO', 'FIXME', 'BUG', 'HACK', 'NOTE', 'XXX', 'WARNING']
    
    for line in lines:
        # Find comment position (ignore # inside strings)
        comment_pos = _find_comment_position(line)
        
        if comment_pos == -1:
            # No comment, keep line as is
            result_lines.append(line)
        elif comment_pos == 0:
            # Line is only a comment
            if keep_important and any(p in line.upper() for p in important_patterns):
                result_lines.append(line)
            # else: skip the line entirely
        else:
            # Line has code + comment
            code_part = line[:comment_pos].rstrip()
            comment_part = line[comment_pos:]
            
            if keep_important and any(p in comment_part.upper() for p in important_patterns):
                # Keep important comment
                result_lines.append(line)
            else:
                # Remove comment, keep code
                result_lines.append(code_part)
    
    return '\n'.join(result_lines)


def _find_comment_position(line: str) -> int:
    """
    Find the position of # comment, ignoring # inside strings.
    
    Returns -1 if no comment found.
    """
    in_single_quote = False
    in_double_quote = False
    
    i = 0
    while i < len(line):
        char = line[i]
        
        # Handle escape characters
        if i > 0 and line[i-1] == '\\':
            i += 1
            continue
        
        # Toggle string states
        if char == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        elif char == '#' and not in_single_quote and not in_double_quote:
            return i
        
        i += 1
    
    return -1


def _remove_empty_lines(code: str) -> str:
    """
    Remove excessive empty lines (keep max 1 consecutive).
    """
    lines = code.split('\n')
    result_lines = []
    prev_empty = False
    
    for line in lines:
        is_empty = line.strip() == ''
        
        if is_empty:
            if not prev_empty:
                # Keep first empty line (for readability)
                result_lines.append('')
            prev_empty = True
        else:
            result_lines.append(line)
            prev_empty = False
    
    # Remove leading/trailing empty lines
    while result_lines and result_lines[0] == '':
        result_lines.pop(0)
    while result_lines and result_lines[-1] == '':
        result_lines.pop()
    
    return '\n'.join(result_lines)


def _clean_whitespace(code: str) -> str:
    """
    Remove trailing whitespace from each line.
    """
    lines = code.split('\n')
    return '\n'.join(line.rstrip() for line in lines)


# =============================================================================
# CONVENIENCE FUNCTION FOR AGENTS
# =============================================================================

def prepare_code_for_ai(
    code: str,
    file_path: Optional[str] = None,
    max_tokens: int = MAX_RECOMMENDED_TOKENS
) -> dict:
    """
    Prepare code for sending to AI agent.
    
    This is the ONE function agents should call. It:
    1. Optimizes the code (removes comments/docstrings)
    2. Checks if it fits in context
    3. Returns ready-to-use data
    
    Args:
        code: Original source code
        file_path: Optional file path for context
        max_tokens: Maximum tokens allowed
        
    Returns:
        Dict with optimized code and metadata
        
    Example:
        >>> result = prepare_code_for_ai(code, "src/main.py")
        >>> if result['fits_in_context']:
        ...     send_to_gemini(result['optimized_code'])
        ... else:
        ...     print(f"Warning: Code has {result['token_count']} tokens!")
    """
    optimized = optimize_context(code)
    token_count = count_tokens(optimized)
    fits = token_count <= max_tokens
    stats = get_optimization_stats(code, optimized)
    
    return {
        "optimized_code": optimized,
        "original_code": code,
        "token_count": token_count,
        "fits_in_context": fits,
        "file_path": file_path,
        "stats": stats
    }
