#!/usr/bin/env python
# src/agents/corrector_agent.py
"""
Corrector Agent (The Fixer) for The Refactoring Swarm.

This agent is responsible for transforming buggy Python code into clean,
functional, and well-documented code. It participates in the Self-Healing
Loop with the Judge agent, iteratively fixing code until all tests pass.

Role: The Fixer 🔧
Project: The Refactoring Swarm
Course: IGL Lab 2025-2026 - ESI Algiers

Author: Toolsmith Team
Version: 1.0.0
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any

import google.generativeai as genai
from dotenv import load_dotenv

from src.utils.logger import log_experiment, ActionType
from src.prompts.corrector_prompts import (
    CorrectorPrompts,
    CorrectorPromptVersion,
    CURRENT_VERSION,
    validate_python_syntax,
    extract_code_from_response,
)
from src.tools import (
    SandboxValidator,
    SecurityError,
    safe_read,
    safe_write,
)
from src.tools.code_analyzer import run_pylint, PylintResultDict

# Load environment variables from .env file
load_dotenv()

# Get API configuration from environment


class CorrectorAgent:
    """
    The Corrector Agent (The Fixer) that transforms buggy code into clean code.

    This agent:
    - Reads refactoring plans from the Auditor agent
    - Modifies code file by file to correct errors
    - Participates in Self-Healing Loop with Judge agent
    - Logs all interactions for scientific analysis

    Attributes:
        api_key: Google Gemini API key for LLM access.
        model_name: Name of the Gemini model to use.
        model: Configured Gemini generative model instance.
        max_iterations: Maximum fix attempts before giving up.
        iteration_count: Current iteration in self-healing loop.

    Example:
        >>> corrector = CorrectorAgent(
        ...     api_key="your-api-key",
        ...     model_name="gemini-2.0-flash-exp"
        ... )
        >>> fixed_code = corrector.fix_code(
        ...     file_path="calculator.py",
        ...     original_code="def add(a,b): return a-b",
        ...     audit_findings={"issues": ["Wrong operator"]}
        ... )
    """

    # Generation configuration for consistent, high-quality output
    GENERATION_CONFIG = {
        "temperature": 0.2,  # Low temperature for deterministic fixes
        "top_p": 0.8,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    # Safety settings - allow code generation
    SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_iterations: Optional[int] = None,
        sandbox_dir: Optional[str] = None
    ) -> None:
        """
        Initialize the Corrector Agent with Gemini API configuration.

        Args:
            api_key: Google Gemini API key. If None, reads from GEMINI_API_KEY env var.
            model_name: Name of the Gemini model to use. If None, reads from GEMINI_MODEL env var.
                Default: "gemini-2.5-flash"
            max_iterations: Maximum iterations for self-healing loop. If None, reads from MAX_ITERATIONS env var.
                Default: 10
            sandbox_dir: Directory for safe file operations. If None, uses current directory.

        Raises:
            ValueError: If API key is not provided and not in environment.
        """
        # Load API key from environment or parameter
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key is required. Provide it as parameter or set GEMINI_API_KEY in .env file"
            )

        # Load model name from environment or parameter
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Load max iterations from environment or parameter
        max_iter_env = os.getenv("MAX_ITERATIONS")
        if max_iterations is not None:
            self.max_iterations = max_iterations
        elif max_iter_env:
            self.max_iterations = int(max_iter_env)
        else:
            self.max_iterations = 10

        # Initialize sandbox for secure file operations
        self.sandbox = SandboxValidator(sandbox_dir or os.getcwd()) if sandbox_dir else None
        self.iteration_count = 0

        # Configure Gemini API
        genai.configure(api_key=self.api_key)

        # Initialize the model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.GENERATION_CONFIG,
            safety_settings=self.SAFETY_SETTINGS,
        )

        # Log agent initialization
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": "Agent initialization",
                "output_response": f"CorrectorAgent initialized with model {self.model_name}",
                "event": "agent_init",
                "model": self.model_name,
                "max_iterations": self.max_iterations,
            },
            status="SUCCESS"
        )

    def get_system_prompt(
        self,
        version: CorrectorPromptVersion = CURRENT_VERSION
    ) -> str:
        """
        Get the system prompt from corrector_prompts.py.

        Args:
            version: Prompt version for A/B testing.

        Returns:
            System prompt string from the prompts module.
        """
        return CorrectorPrompts.get_system_prompt(version)

    def build_correction_prompt(
        self,
        file_path: str,
        original_code: str,
        audit_findings: Dict[str, Any],
        error_logs: Optional[str] = None
    ) -> str:
        """
        Build the correction prompt using templates from corrector_prompts.py.

        Uses the professionally designed prompts from the Prompt Engineer (Yacine)
        to minimize hallucinations and optimize token usage.

        Args:
            file_path: Path to the file being corrected.
            original_code: The buggy source code to fix.
            audit_findings: Dictionary containing audit results from Auditor.
                Expected keys: "issues", "score", "recommendations"
            error_logs: Optional traceback/error logs from failed tests.
                Provided during self-healing iterations.

        Returns:
            A carefully crafted prompt string for the LLM.
        """
        # Extract issues from audit findings
        issues = audit_findings.get("issues", [])

        # Use prompts from corrector_prompts.py
        if error_logs:
            # Self-healing mode: use self-healing prompt
            error_logs_list = [error_logs] if isinstance(error_logs, str) else error_logs
            return CorrectorPrompts.format_self_healing_prompt(
                code=original_code,
                issues=issues,
                error_logs=error_logs_list,
                file_path=file_path,
                attempt_number=self.iteration_count
            )

        # Normal correction mode
        return CorrectorPrompts.format_correction_prompt(
            code=original_code,
            issues=issues,
            file_path=file_path
        )

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from LLM.

        Args:
            response_text: Raw response text from LLM.

        Returns:
            Parsed JSON dictionary.

        Raises:
            ValueError: If JSON parsing fails.
        """
        # Try to find JSON in the response
        text = response_text.strip()

        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*\n(.*?)```',
            r'```\s*\n(\{.*?\})```',
            r'(\{[\s\S]*\})'
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        # Try parsing the whole response as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            raise ValueError(f"Failed to parse JSON response: {err}") from err

    def _extract_code_from_response(self, response: str) -> str:
        """
        Extract Python code from LLM response.

        Uses extract_code_from_response from corrector_prompts.py for JSON responses,
        with fallback to direct code extraction.

        Args:
            response: Raw response from the LLM.

        Returns:
            Extracted Python code.
        """
        if not response or not response.strip():
            return ""

        text = response.strip()

        # First, try to parse as JSON (expected format from prompts)
        try:
            parsed = self._parse_json_response(text)
            code = extract_code_from_response(parsed)
            if code:
                return code
        except (ValueError, TypeError):
            pass

        # Fallback: Try to extract from markdown code blocks
        pattern_python = r'```python\s*\n(.*?)```'
        match = re.search(pattern_python, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        pattern_generic = r'```\s*\n(.*?)```'
        match = re.search(pattern_generic, text, re.DOTALL)
        if match:
            return match.group(1).strip()

        # Last resort: return as-is if it looks like Python code
        if text.startswith(('import ', 'from ', 'def ', 'class ', '#', '"""')):
            return text

        return text

    def _validate_python_syntax(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python syntax using validate_python_syntax from corrector_prompts.py.

        Args:
            code: Python code string to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        return validate_python_syntax(code)

    def fix_code(
        self,
        file_path: str,
        original_code: str,
        audit_findings: Dict[str, Any],
        error_logs: Optional[str] = None
    ) -> str:
        """
        Main method to fix buggy code using LLM.

        This method:
        1. Builds an optimized correction prompt
        2. Sends request to Gemini API
        3. Extracts and validates the fixed code
        4. Logs the interaction for scientific analysis

        Args:
            file_path: Path to the file being corrected.
            original_code: The buggy source code to fix.
            audit_findings: Dictionary containing audit results.
            error_logs: Optional error logs from failed tests
                (provided during self-healing iterations).

        Returns:
            The corrected Python code as a string.

        Raises:
            RuntimeError: If LLM fails to generate valid code after retries.
            ValueError: If original_code is empty.
        """
        if not original_code or not original_code.strip():
            raise ValueError("Original code cannot be empty")

        # Track iteration for self-healing loop
        if error_logs:
            self.iteration_count += 1
            if self.iteration_count > self.max_iterations:
                log_experiment(
                    agent_name="Corrector",
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "input_prompt": "Max iterations reached",
                        "output_response": "Stopping self-healing loop",
                        "event": "max_iterations_exceeded",
                        "file_path": file_path,
                        "iteration": self.iteration_count,
                    },
                    status="FAILED"
                )
                raise RuntimeError(
                    f"Max iterations ({self.max_iterations}) exceeded in self-healing loop"
                )
        else:
            # Reset iteration count for new file
            self.iteration_count = 0

        # Get system prompt from corrector_prompts.py
        system_prompt = self.get_system_prompt()

        # Build the correction prompt using templates from corrector_prompts.py
        correction_prompt = self.build_correction_prompt(
            file_path=file_path,
            original_code=original_code,
            audit_findings=audit_findings,
            error_logs=error_logs
        )

        # Combine system prompt with user prompt
        full_prompt = f"{system_prompt}\n\n{correction_prompt}"

        # Log the prompt (REQUIRED for experiment data)
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": full_prompt,
                "output_response": "pending",
                "event": "correction_request",
                "file_path": file_path,
                "iteration": self.iteration_count,
                "has_error_logs": error_logs is not None,
                "prompt_version": str(CURRENT_VERSION),
            },
            status="PENDING"
        )

        # Call Gemini API with retry logic
        fixed_code = self._call_llm_with_retry(full_prompt, file_path)

        return fixed_code

    def _call_llm_with_retry(
        self,
        llm_prompt: str,
        file_path: str,
        max_retries: int = 3
    ) -> str:
        """
        Call the LLM with retry logic for robustness.

        Args:
            llm_prompt: The prompt to send to the LLM.
            file_path: Path to file being fixed (for logging).
            max_retries: Maximum number of retry attempts.

        Returns:
            Extracted and validated Python code.

        Raises:
            RuntimeError: If all retries fail.
        """
        last_error: Optional[BaseException] = None

        for attempt in range(max_retries):
            try:
                # Call Gemini API
                response = self.model.generate_content(llm_prompt)

                # Extract text from response
                if not response.text:
                    raise ValueError("Empty response from LLM")

                raw_response = response.text

                # Extract code from response
                fixed_code = self._extract_code_from_response(raw_response)

                if not fixed_code:
                    raise ValueError("No code extracted from response")

                # Validate syntax
                is_valid, error_msg = self._validate_python_syntax(fixed_code)

                if not is_valid:
                    raise ValueError(f"Invalid Python syntax: {error_msg}")

                # Log successful response (REQUIRED for experiment data)
                truncated_prompt = (
                    llm_prompt[:500] + "..." if len(llm_prompt) > 500 else llm_prompt
                )
                truncated_code = (
                    fixed_code[:500] + "..." if len(fixed_code) > 500 else fixed_code
                )
                log_experiment(
                    agent_name="Corrector",
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "input_prompt": truncated_prompt,
                        "output_response": truncated_code,
                        "event": "correction_success",
                        "file_path": file_path,
                        "attempt": attempt + 1,
                        "code_length": len(fixed_code),
                    },
                    status="SUCCESS"
                )

                return fixed_code

            except (ValueError, RuntimeError) as err:
                last_error = err

                # Log retry attempt
                log_experiment(
                    agent_name="Corrector",
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "input_prompt": f"Retry attempt {attempt + 1}",
                        "output_response": f"Error: {str(err)}",
                        "event": "correction_retry",
                        "file_path": file_path,
                        "attempt": attempt + 1,
                        "error": str(err),
                    },
                    status="RETRY"
                )

                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        # All retries failed
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": "All retries exhausted",
                "output_response": f"Final error: {str(last_error)}",
                "event": "correction_failed",
                "file_path": file_path,
                "error": str(last_error),
            },
            status="FAILED"
        )

        raise RuntimeError(
            f"Failed to fix code after {max_retries} attempts: {last_error}"
        )

    def reset_iteration_count(self) -> None:
        """
        Reset the iteration counter for a new self-healing loop.

        Call this when starting to process a new file to ensure
        the iteration limit is properly enforced per file.
        """
        self.iteration_count = 0

        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": "Reset iteration count",
                "output_response": "Iteration count reset to 0",
                "event": "iteration_reset",
            },
            status="SUCCESS"
        )


def create_corrector_agent(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    max_iterations: Optional[int] = None,
    sandbox_dir: Optional[str] = None
) -> CorrectorAgent:
    """
    Factory function to create a CorrectorAgent instance.

    Args:
        api_key: Google Gemini API key. If None, reads from GEMINI_API_KEY env var.
        model_name: Name of the Gemini model. If None, reads from GEMINI_MODEL env var.
        max_iterations: Max iterations for self-healing. If None, reads from MAX_ITERATIONS env var.
        sandbox_dir: Directory for safe file operations.

    Returns:
        Configured CorrectorAgent instance.

    Example:
        >>> # Using environment variables from .env
        >>> corrector = create_corrector_agent()
        >>> 
        >>> # Override with custom values
        >>> corrector = create_corrector_agent(
        ...     model_name="gemini-2.5-pro",
        ...     sandbox_dir="./sandbox"
        ... )
    """
    return CorrectorAgent(
        api_key=api_key,
        model_name=model_name,
        max_iterations=max_iterations,
        sandbox_dir=sandbox_dir
    )
