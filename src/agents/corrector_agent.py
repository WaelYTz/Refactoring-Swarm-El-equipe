#!/usr/bin/env python
# -*- coding: utf-8 -*-
# src/agents/corrector_agent.py
"""
Corrector Agent (The Fixer) - The Refactoring Swarm
=====================================================
IGL Lab 2025-2026 - Multi-Agent Refactoring System

This agent is responsible for fixing buggy Python code using Google's Gemini API
via LangChain (consistent with ListenerAgent and ValidatorAgent).

It operates as "The Fixer" in the swarm, receiving flagged code from The Auditor
and returning corrected code to The Judge for validation.

Key Features:
- Uses LangChain for LLM integration (langchain-google-genai)
- Uses prompts from src/prompts/corrector_prompts.py (designed by Prompt Engineer Yacine)
- Self-healing loop with configurable max iterations
- Structured JSON response parsing
- Scientific logging for A/B testing and analysis
- Environment variable support for configuration
- Inherits from BaseAgent interface for orchestrator compatibility

Architecture (Execution Graph):
    LISTENER (Auditor) → CORRECTOR (this agent) → VALIDATOR (Judge)
                              ↑_________|
                         Self-Healing Loop
                    (error_logs from Judge back to Corrector)

IMPORTANT - LOGGING PROTOCOL (MANDATORY per course requirements):
    Every LLM interaction MUST be logged using log_experiment with:
    - input_prompt: The exact prompt sent to the LLM (minimum 10 characters)
    - output_response: The exact response from the LLM (minimum 5 characters)

    ActionType values to use:
    - ActionType.ANALYSIS for code analysis
    - ActionType.FIX for code corrections
    - ActionType.DEBUG for debugging
    - ActionType.GENERATION for code generation

Constructor Parameters:
    - name: Agent identifier for logging
    - model_name: Gemini model to use (default from GEMINI_MODEL env var)
    - max_iterations: Max self-healing iterations (default from MAX_ITERATIONS env var)
    - sandbox_dir: Optional directory for sandbox file operations
    - api_key: Optional override (reads from GOOGLE_API_KEY env var if not provided)
    - verbose: Whether to print progress messages

Author: Corrector Agent Team Member
Course: IGL Lab 2025-2026 - ESI Algiers
Version: 2.2.0 (BaseAgent inheritance version)
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

from dotenv import load_dotenv

# LangChain for LLM integration (consistent with other agents)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# Import base agent interface (Lead Dev's interface)
from src.agents.base_agent import BaseAgent

# Import prompts from corrector_prompts.py (by Prompt Engineer Yacine)
from src.prompts.corrector_prompts import (
    CorrectorPrompts,
    CorrectorPromptVersion,
    CURRENT_VERSION,
    validate_python_syntax,
    extract_code_from_response,
)
from src.prompts.context_manager import optimize_context

# Import logging utilities (MANDATORY per course requirements)
from src.utils.logger import log_experiment, ActionType

# Import tools for sandbox operations
from src.tools import (
    SandboxValidator,
    SecurityError,
    safe_read,
    safe_write,
    list_python_files,
)
from src.tools.code_analyzer import run_pylint, PylintResultDict

if TYPE_CHECKING:
    from main import SwarmContext, AgentRole, SwarmState

# Load environment variables from .env file at module load
load_dotenv()

# Configure module logger
logger = logging.getLogger(__name__)


class CorrectorAgent(BaseAgent):
    """
    The Corrector Agent (The Fixer) transforms buggy code into clean code.

    This agent uses LangChain for LLM integration, consistent with
    ListenerAgent and ValidatorAgent.

    This agent:
    - Receives refactoring plans from the Listener (Auditor) agent
    - Modifies code file by file to correct errors using Gemini LLM
    - Participates in Self-Healing Loop with Validator (Judge) agent
    - Logs ALL interactions for scientific analysis (MANDATORY)

    The agent reads configuration from environment variables:
    - GOOGLE_API_KEY: Google Gemini API key (REQUIRED per course requirements)
    - GEMINI_MODEL: Model name (default: "gemini-2.5-flash")
    - MAX_ITERATIONS: Max self-healing iterations (default: 10)

    Attributes:
        model_name (str): Gemini model identifier
        max_iterations (int): Maximum self-healing loop iterations
        iteration_count (int): Current iteration counter
        sandbox (SandboxValidator): Optional sandbox for file operations
    
    Example Usage:
        # Standard initialization (reads API key from environment)
        corrector = CorrectorAgent(model_name="gemini-2.5-flash", max_iterations=10)
        
        # Fix code
        fixed_code = corrector.fix_code(
            file_path="src/buggy.py",
            original_code="def add(a, b):\\n    return a - b  # Bug here",
            audit_findings={"issues": [{"type": "logic_error", "description": "Wrong operator"}]}
        )
    """

    def __init__(
        self,
        name: str = "Corrector_Agent",
        model_name: Optional[str] = None,
        max_iterations: Optional[int] = None,
        sandbox_dir: Optional[str] = None,
        api_key: Optional[str] = None,
        verbose: bool = True,
    ) -> None:
        """
        Initialize the Corrector Agent.

        IMPORTANT: This constructor is designed to work without api_key parameter.
        The API key is read from environment variables (GOOGLE_API_KEY per course requirements).
        This is compatible with BaseAgent interface.

        Args:
            name: Human-readable agent name for identification and logging.
            model_name: Gemini model to use. Default reads from GEMINI_MODEL env var
                       or falls back to "gemini-2.5-flash".
            max_iterations: Maximum self-healing loop iterations. Default reads from
                           MAX_ITERATIONS env var or falls back to 10.
            sandbox_dir: Optional directory for sandbox file operations.
            api_key: Optional API key override. If None, reads from GOOGLE_API_KEY
                    (per course requirements) or GEMINI_API_KEY (fallback).
            verbose: Whether to print progress messages (default: True).

        Raises:
            ValueError: If no API key is available (not in env and not provided).
        """
        # Load model name from parameter or environment
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        # Call parent constructor with name and model
        super().__init__(name=name, model=self.model_name)
        
        # Store verbose flag
        self.verbose = verbose
        
        # Load API key from environment (primary) or parameter (fallback)
        # Course requirements specify GOOGLE_API_KEY
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key is required. Set GOOGLE_API_KEY in .env file or provide as parameter."
            )

        # Load model name from parameter or environment
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Load max iterations from parameter or environment
        if max_iterations is not None:
            self.max_iterations = max_iterations
        else:
            env_max_iter = os.getenv("MAX_ITERATIONS")
            self.max_iterations = int(env_max_iter) if env_max_iter else 10

        # Initialize iteration counter
        self.iteration_count = 0

        # Initialize sandbox for secure file operations (optional)
        self.sandbox = SandboxValidator(sandbox_dir) if sandbox_dir else None

        # Initialize LangChain LLM (consistent with ListenerAgent and ValidatorAgent)
        self._llm: Optional[ChatGoogleGenerativeAI] = None
        self._init_llm()

        # Log agent initialization (MANDATORY per course requirements)
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": f"Initialize CorrectorAgent with model {self.model_name}",
                "output_response": f"Agent initialized successfully. Max iterations: {self.max_iterations}",
                "event": "agent_initialization",
                "model": self.model_name,
                "max_iterations": self.max_iterations,
                "has_sandbox": self.sandbox is not None,
            },
            status="SUCCESS"
        )

    def _init_llm(self) -> None:
        """
        Initialize the Google Gemini LLM via LangChain.
        
        Uses the same pattern as ListenerAgent and ValidatorAgent for consistency.
        """
        try:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=self.api_key,
                temperature=0.2,  # Low temperature for deterministic code fixes
                max_output_tokens=16384,  # Increased for larger code outputs
                convert_system_message_to_human=True,
            )
            logger.info("Corrector LLM initialized: model=%s", self.model_name)
        except Exception as e:
            logger.exception("Failed to initialize LLM: %s", e)
            raise ValueError(f"Failed to initialize Gemini LLM: {e}") from e

    @property
    def role(self) -> "AgentRole":
        """Return the agent's role in the swarm."""
        from main import AgentRole
        return AgentRole.CORRECTOR

    def run(self, context: "SwarmContext") -> "SwarmContext":
        """
        Execute the correction phase.
        
        This is the main entry point called by the Orchestrator.
        Implements the BaseAgent interface.
        
        Args:
            context: The shared SwarmContext with all pipeline state
            
        Returns:
            The modified SwarmContext after correction
        """
        from main import SwarmState
        
        logger.info("=" * 80)
        logger.info("CORRECTOR AGENT STARTING - Iteration %d", context.iteration)
        logger.info("=" * 80)
        
        if self.verbose:
            print(f"\n🔧 Corrector Agent (Fixer) starting - Iteration {context.iteration}")
        
        # Update context state
        context.current_state = SwarmState.CORRECTING
        context.current_agent = self.role
        
        # Reset iteration count for new correction phase
        self.reset_iteration_count()
        
        # Initialize sandbox if not already set
        if self.sandbox is None:
            self.sandbox = SandboxValidator(context.target_dir)
        
        try:
            # Get all Python files in target directory
            python_files = list_python_files(context.target_dir, self.sandbox)
            
            if not python_files:
                logger.warning("No Python files found in target directory")
                context.current_state = SwarmState.FIX_SUCCESS
                return context
            
            if self.verbose:
                print(f"   Found {len(python_files)} Python files to process")
            
            # Process each file with detected issues
            files_fixed = 0
            for file_path in python_files:
                # Read the original code
                original_code = safe_read(file_path, self.sandbox)
                if original_code is None:
                    logger.warning("Could not read file: %s", file_path)
                    continue
                
                # Get issues for this file from context
                # Use Path for proper path comparison across platforms
                file_path_obj = Path(file_path)
                
                # Skip test files on first iteration - they're generated by validator
                if file_path_obj.name.startswith("test_") or file_path_obj.name.endswith("_test.py"):
                    if context.iteration == 0:
                        logger.debug("Skipping test file on first iteration: %s", file_path)
                        continue
                
                file_issues = [
                    issue for issue in context.detected_issues
                    if (
                        Path(issue.get("file", "")).resolve() == file_path_obj.resolve() or
                        Path(issue.get("path", "")).resolve() == file_path_obj.resolve() or
                        issue.get("file_path", "") == file_path or
                        Path(issue.get("file_path", "")).name == file_path_obj.name
                    )
                ]
                
                if not file_issues and not context.test_error_logs:
                    logger.debug("No issues detected for file: %s", file_path)
                    continue
                
                # Build audit findings from detected issues
                audit_findings = {
                    "issues": file_issues,
                    "file_path": file_path,
                }
                
                # Get error logs from previous validator run (for self-healing loop)
                error_logs = "\n".join(context.test_error_logs) if context.test_error_logs else None
                
                if self.verbose:
                    print(f"   🔧 Fixing: {Path(file_path).name} ({len(file_issues)} issues)")
                
                try:
                    # Call the fix_code method to perform the actual correction
                    fixed_code = self.fix_code(
                        file_path=file_path,
                        original_code=original_code,
                        audit_findings=audit_findings,
                        error_logs=error_logs
                    )
                    
                    # Write the fixed code back to the file
                    if fixed_code and fixed_code != original_code:
                        safe_write(file_path, fixed_code, self.sandbox)
                        files_fixed += 1
                        
                        # Record the applied fix
                        context.applied_fixes.append({
                            "file": file_path,
                            "issues_fixed": len(file_issues),
                            "iteration": context.iteration,
                        })
                        
                        if self.verbose:
                            print(f"      ✅ Fixed {len(file_issues)} issues")
                    else:
                        if self.verbose:
                            print(f"      ℹ️ No changes needed")
                            
                except Exception as fix_error:
                    logger.error("Error fixing file %s: %s", file_path, fix_error)
                    context.error_log.append(f"Corrector error on {file_path}: {str(fix_error)}")
            
            # Update state based on results
            if files_fixed > 0:
                context.current_state = SwarmState.VALIDATING  # Ready for validator
                if self.verbose:
                    print(f"   ✅ Fixed {files_fixed} files. Ready for validation.")
            else:
                context.current_state = SwarmState.FIX_SUCCESS  # No fixes needed
                if self.verbose:
                    print(f"   ℹ️ No files needed fixing.")
            
            # Clear test error logs after processing (consumed by this iteration)
            context.test_error_logs.clear()
            
            return context
            
        except Exception as e:
            logger.exception("Corrector agent failed: %s", e)
            context.error_log.append(f"Corrector error: {str(e)}")
            context.current_state = SwarmState.FIX_FAILED
            
            # Log failure
            log_experiment(
                agent_name=self.name,
                model_used=self.model_name,
                action=ActionType.FIX,
                details={
                    "input_prompt": f"Correction phase for {context.target_dir}",
                    "output_response": f"Error: {str(e)}",
                    "event": "correction_phase_failed",
                    "error": str(e),
                },
                status="FAILURE"
            )
            
            return context

    def get_system_prompt(
        self,
        version: CorrectorPromptVersion = CURRENT_VERSION
    ) -> str:
        """
        Get the system prompt from corrector_prompts.py.

        Uses prompts designed by Prompt Engineer Yacine for optimal
        LLM performance and minimal hallucination.

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

        Uses professionally designed prompts from the Prompt Engineer (Yacine)
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

        # Optimize code for LLM (remove comments/docstrings to save tokens)
        optimized_code = optimize_context(original_code)

        # Use prompts from corrector_prompts.py
        if error_logs:
            # Self-healing mode: use self-healing prompt
            error_logs_list = [error_logs] if isinstance(error_logs, str) else error_logs
            return CorrectorPrompts.format_self_healing_prompt(
                code=optimized_code,
                issues=issues,
                error_logs=error_logs_list,
                file_path=file_path,
                attempt_number=self.iteration_count
            )

        # Normal correction mode
        return CorrectorPrompts.format_correction_prompt(
            code=optimized_code,
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
            ValueError: If JSON parsing fails after all attempts.
        """
        text = response_text.strip()

        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*\n?(.*?)```',
            r'```\s*\n?(\{.*?\})```',
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
        with fallback to direct code extraction from markdown blocks.

        Args:
            response: Raw response from the LLM.

        Returns:
            Extracted Python code string.
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
        if text.startswith(('import ', 'from ', 'def ', 'class ', '#', '"""', "'''")):
            return text

        return text

    def _validate_python_syntax(self, code: str) -> Tuple[bool, Optional[str]]:
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
        1. Builds an optimized correction prompt using corrector_prompts.py
        2. Sends request to Gemini API via LangChain with retry logic
        3. Extracts and validates the fixed code
        4. Logs all interactions for scientific analysis (MANDATORY)

        Args:
            file_path: Path to the file being corrected.
            original_code: The buggy source code to fix.
            audit_findings: Dictionary containing audit results from Auditor.
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
                # Log max iterations exceeded (MANDATORY)
                log_experiment(
                    agent_name="Corrector",
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "input_prompt": f"Self-healing attempt {self.iteration_count} for {file_path}",
                        "output_response": f"STOPPED: Max iterations ({self.max_iterations}) exceeded",
                        "event": "max_iterations_exceeded",
                        "file_path": file_path,
                        "iteration": self.iteration_count,
                    },
                    status="FAILURE"
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

        # Full prompt for logging
        full_prompt = f"{system_prompt}\n\n{correction_prompt}"

        # Log the prompt being sent (MANDATORY per course requirements)
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": full_prompt[:2000] + "..." if len(full_prompt) > 2000 else full_prompt,
                "output_response": "[PENDING - Awaiting LLM response]",
                "event": "correction_request_sent",
                "file_path": file_path,
                "iteration": self.iteration_count,
                "has_error_logs": error_logs is not None,
                "prompt_version": str(CURRENT_VERSION),
            },
            status="PENDING"
        )

        # Call Gemini API via LangChain with retry logic
        fixed_code = self._call_llm_with_retry(system_prompt, correction_prompt, file_path)

        return fixed_code

    def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        file_path: str,
        max_retries: int = 3
    ) -> str:
        """
        Call the LLM via LangChain with retry logic for robustness.

        Uses the same LangChain pattern as ListenerAgent and ValidatorAgent.

        Args:
            system_prompt: The system prompt for the LLM.
            user_prompt: The user prompt with code and issues.
            file_path: Path to file being fixed (for logging).
            max_retries: Maximum number of retry attempts.

        Returns:
            Extracted and validated Python code.

        Raises:
            RuntimeError: If all retries fail.
        """
        last_error: Optional[BaseException] = None
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        for attempt in range(max_retries):
            try:
                # Build LangChain messages (same pattern as other agents)
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]

                # Call LLM via LangChain
                response = self._llm.invoke(messages)

                # Extract text from response
                raw_response = response.content
                if not raw_response:
                    raise ValueError("Empty response from LLM")

                # Extract code from response
                fixed_code = self._extract_code_from_response(raw_response)

                if not fixed_code:
                    raise ValueError("No code extracted from LLM response")

                # Validate Python syntax
                is_valid, error_msg = self._validate_python_syntax(fixed_code)

                if not is_valid:
                    raise ValueError(f"Invalid Python syntax: {error_msg}")

                # Log successful response (MANDATORY per course requirements)
                truncated_prompt = full_prompt[:500] + "..." if len(full_prompt) > 500 else full_prompt
                truncated_code = fixed_code[:500] + "..." if len(fixed_code) > 500 else fixed_code

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
                        "raw_response_length": len(raw_response),
                    },
                    status="SUCCESS"
                )

                return fixed_code

            except Exception as err:
                last_error = err
                logger.warning("LLM call attempt %d failed: %s", attempt + 1, err)

                # Log retry attempt (MANDATORY per course requirements)
                log_experiment(
                    agent_name="Corrector",
                    model_used=self.model_name,
                    action=ActionType.FIX,
                    details={
                        "input_prompt": f"Retry attempt {attempt + 1}/{max_retries} for {file_path}",
                        "output_response": f"Error encountered: {str(err)}",
                        "event": "correction_retry",
                        "file_path": file_path,
                        "attempt": attempt + 1,
                        "error_type": type(err).__name__,
                        "error_message": str(err),
                    },
                    status="RETRY"
                )

                # Wait before retry (exponential backoff)
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)

        # All retries failed - log failure (MANDATORY per course requirements)
        log_experiment(
            agent_name="Corrector",
            model_used=self.model_name,
            action=ActionType.FIX,
            details={
                "input_prompt": f"All {max_retries} retry attempts exhausted for {file_path}",
                "output_response": f"Final error: {str(last_error)}",
                "event": "correction_failed",
                "file_path": file_path,
                "total_attempts": max_retries,
                "final_error_type": type(last_error).__name__ if last_error else "Unknown",
                "final_error_message": str(last_error),
            },
            status="FAILURE"
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
                "input_prompt": "Reset iteration counter for new file",
                "output_response": "Iteration count reset to 0 successfully",
                "event": "iteration_reset",
            },
            status="SUCCESS"
        )


def create_corrector_agent(
    model_name: Optional[str] = None,
    max_iterations: Optional[int] = None,
    sandbox_dir: Optional[str] = None,
    api_key: Optional[str] = None,
) -> CorrectorAgent:
    """
    Factory function to create a CorrectorAgent instance.

    This is the recommended way to create a CorrectorAgent as it handles
    all configuration from environment variables automatically.

    Args:
        model_name: Gemini model name. If None, reads from GEMINI_MODEL env var.
        max_iterations: Max self-healing iterations. If None, reads from MAX_ITERATIONS env var.
        sandbox_dir: Directory for sandbox file operations.
        api_key: API key override. If None, reads from GOOGLE_API_KEY env var.

    Returns:
        Configured CorrectorAgent instance.

    Example:
        >>> # Using environment variables from .env
        >>> corrector = create_corrector_agent()
        >>>
        >>> # Override with custom values
        >>> corrector = create_corrector_agent(
        ...     model_name="gemini-2.5-pro",
        ...     max_iterations=5
        ... )
    """
    return CorrectorAgent(
        model_name=model_name,
        max_iterations=max_iterations,
        sandbox_dir=sandbox_dir,
        api_key=api_key,
    )
