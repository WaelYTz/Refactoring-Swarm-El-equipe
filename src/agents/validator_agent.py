"""
Validator Agent (Judge/Tester)
===============================
The Validator agent is responsible for verifying fixes and running tests.

Role in the Swarm:
1. Receives fixed code from the Corrector agent
2. Generates functional tests using LLM with semantic understanding
3. Executes tests using pytest
4. Analyzes test results
5. Sends feedback to Corrector for self-healing loop if tests fail

This agent is the third in the pipeline:
    LISTENER → CORRECTOR → VALIDATOR

The Validator must:
- Generate tests that validate FUNCTIONAL CORRECTNESS, not just crash testing
- Understand semantic intent from function names (e.g., "calculate_average" should test averages)
- Create assertions that verify business logic
- Provide clear error messages for the self-healing loop

Author: Judge/Tester Team
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING

# LangChain for LLM integration
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# Local imports
from src.agents.base_agent import BaseAgent
from src.tools import (
    SandboxValidator,
    safe_read,
    safe_write,
    list_python_files,
    run_pytest,
    discover_tests,
)
from src.prompts.validator_prompts import (
    ValidatorPrompts,
    ValidatorPromptVersion,
    validate_validation_response,
    extract_error_logs,
    extract_generated_tests,
    should_trigger_self_healing,
)
from src.utils.logger import log_experiment, ActionType

if TYPE_CHECKING:
    from main import SwarmContext, AgentRole, SwarmState

# Configure module logger
logger = logging.getLogger(__name__)


class ValidatorAgent(BaseAgent):
    """
    The Judge/Tester agent - validates fixes and runs tests.
    
    This agent:
    1. Analyzes code that has been fixed by Corrector
    2. Generates functional tests using LLM (understanding semantic intent)
    3. Executes tests using pytest
    4. Validates that fixes are correct and functional
    5. Provides feedback for self-healing loop if needed
    
    Key Features:
    - Semantic understanding: Generates tests based on function purpose, not just syntax
    - Functional correctness: Tests business logic, not just crash testing
    - Self-healing loop: Sends detailed error logs back to Corrector for retry
    
    Usage:
        from src.agents.validator_agent import ValidatorAgent
        
        validator = ValidatorAgent()
        context = validator.run(context)
        if context.current_state == SwarmState.FIX_SUCCESS:
            print("All tests passed!")
        else:
            print("Tests failed, triggering self-healing loop")
    """
    
    def __init__(
        self,
        name: str = "Validator_Agent",
        model: str = "gemini-1.5-flash",
        prompt_version: ValidatorPromptVersion = ValidatorPromptVersion.V1_BASIC,
        generate_tests: bool = True,
        run_existing_tests: bool = True,
        verbose: bool = True,
        test_timeout: int = 120
    ):
        """
        Initialize the Validator agent.
        
        Args:
            name: Agent identifier for logging
            model: LLM model to use (default: gemini-1.5-flash for free tier)
            prompt_version: Which prompt version to use (for A/B testing)
            generate_tests: Whether to generate new tests with LLM
            run_existing_tests: Whether to run existing pytest tests
            verbose: Whether to print progress messages
            test_timeout: Maximum time for test execution in seconds
        """
        super().__init__(name=name, model=model)
        self.prompt_version = prompt_version
        self.generate_tests = generate_tests
        self.run_existing_tests = run_existing_tests
        self.verbose = verbose
        self.test_timeout = test_timeout
        
        # Initialize LLM
        self._llm: Optional[ChatGoogleGenerativeAI] = None
        self._init_llm()
    
    def _init_llm(self) -> None:
        """Initialize the Google Gemini LLM."""
        try:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("GOOGLE_API_KEY not found in environment")
                raise ValueError("GOOGLE_API_KEY is required for Validator agent")
            
            self._llm = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=api_key,
                temperature=0.2,  # Low temperature for consistent test generation
                max_output_tokens=4096
            )
            logger.info("Validator LLM initialized: model=%s", self.model)
        except Exception as e:
            logger.exception("Failed to initialize LLM: %s", e)
            raise
    
    @property
    def role(self) -> "AgentRole":
        """Return the agent's role in the swarm."""
        from main import AgentRole
        return AgentRole.VALIDATOR
    
    def run(self, context: "SwarmContext") -> "SwarmContext":
        """
        Execute the validation phase.
        
        This is the main entry point called by the Orchestrator.
        
        Args:
            context: The shared SwarmContext with all pipeline state
            
        Returns:
            The modified SwarmContext after validation
        """
        from main import SwarmState
        
        logger.info("=" * 80)
        logger.info("VALIDATOR AGENT STARTING - Iteration %d", context.iteration)
        logger.info("=" * 80)
        
        if self.verbose:
            print(f"\n🧪 Validator Agent (Judge) starting - Iteration {context.iteration}")
        
        # Update context state
        context.current_state = SwarmState.VALIDATING
        context.current_agent = self.role
        
        # Initialize sandbox
        sandbox = SandboxValidator(context.target_dir)
        
        try:
            # Get all Python files in target directory
            python_files = list_python_files(context.target_dir, sandbox)
            
            if not python_files:
                logger.warning("No Python files found in target directory")
                context.current_state = SwarmState.COMPLETED
                return context
            
            if self.verbose:
                print(f"   Found {len(python_files)} Python files to validate")
            
            # Step 1: Generate tests for each file (if enabled)
            if self.generate_tests:
                self._generate_and_write_tests(python_files, sandbox, context)
            
            # Step 2: Run all tests (both generated and existing)
            test_results = self._run_all_tests(context.target_dir, sandbox, context)
            
            # Step 3: Analyze results and determine next action
            self._analyze_test_results(test_results, context)
            
            # Log final status
            if context.current_state == SwarmState.FIX_SUCCESS:
                logger.info("✅ VALIDATION SUCCESSFUL - All tests passed")
                if self.verbose:
                    print(f"   ✅ All tests passed! Validation successful.")
            else:
                logger.warning("❌ VALIDATION FAILED - Tests failed, triggering self-healing")
                if self.verbose:
                    print(f"   ❌ Tests failed. Sending feedback to Corrector for retry.")
            
            return context
            
        except Exception as e:
            logger.exception("Validator agent failed: %s", e)
            context.error_log.append(f"Validator error: {str(e)}")
            context.current_state = SwarmState.FIX_FAILED
            
            # Log failure
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.DEBUG,
                details={
                    "input_prompt": "Validator execution failed",
                    "output_response": f"Error: {str(e)}",
                    "error": str(e),
                    "iteration": context.iteration
                },
                status="FAILURE"
            )
            
            return context
    
    def _generate_and_write_tests(
        self,
        python_files: List[str],
        sandbox: SandboxValidator,
        context: "SwarmContext"
    ) -> None:
        """
        Generate tests for Python files using LLM with semantic understanding.
        
        This is the key feature: the LLM analyzes function names and purposes
        to generate tests that validate functional correctness, not just syntax.
        
        Args:
            python_files: List of Python file paths
            sandbox: Sandbox validator for security
            context: Swarm context
        """
        if self.verbose:
            print(f"   📝 Generating functional tests with semantic understanding...")
        
        for file_path in python_files:
            try:
                # Read the code
                code = safe_read(file_path, sandbox)
                
                if not code or len(code.strip()) < 10:
                    logger.debug("Skipping empty or trivial file: %s", file_path)
                    continue
                
                # Generate test using LLM
                test_code = self._generate_tests_for_file(file_path, code, context)
                
                if test_code:
                    # Write test file next to source file
                    test_file_path = self._get_test_file_path(file_path)
                    safe_write(test_file_path, test_code, sandbox)
                    
                    if self.verbose:
                        print(f"      ✓ Generated tests: {test_file_path}")
                    
                    logger.info("Generated test file: %s", test_file_path)
                
            except Exception as e:
                logger.error("Failed to generate tests for %s: %s", file_path, e)
                context.error_log.append(f"Test generation failed for {file_path}: {str(e)}")
    
    def _generate_tests_for_file(
        self,
        file_path: str,
        code: str,
        context: "SwarmContext"
    ) -> Optional[str]:
        """
        Generate pytest tests for a file using LLM with semantic understanding.
        
        The LLM analyzes:
        - Function names to understand intent (e.g., "calculate_average" should compute averages)
        - Parameters and return types
        - Business logic and edge cases
        
        This generates tests for FUNCTIONAL CORRECTNESS, not just crash testing.
        
        Args:
            file_path: Path to source file
            code: Source code content
            context: Swarm context
            
        Returns:
            Generated test code as string, or None if generation failed
        """
        try:
            # Get system prompt
            system_prompt = ValidatorPrompts.get_test_generation_system_prompt()
            
            # Format user prompt with emphasis on functional correctness
            user_prompt = f"""Generate comprehensive pytest test cases for this Python code.

CRITICAL REQUIREMENT - FUNCTIONAL CORRECTNESS:
You MUST analyze function names semantically and generate tests that validate the INTENDED BEHAVIOR, not just syntax.

Example: If a function is named "calculate_average", you must:
1. Understand that it should compute the mathematical average
2. Generate a test like: assert calculate_average([10, 20]) == 15
3. NOT just test that it runs without crashing

FILE: {file_path}

CODE TO TEST:
```python
{code}
```

For EACH function, you must:
1. Analyze the function name to understand its semantic intent
2. Generate assertions that verify the function does what its name suggests
3. Test edge cases (empty inputs, None, large values, zero, negative numbers)
4. Test error handling (invalid inputs should raise appropriate exceptions)

Generate complete, runnable pytest code with:
- All necessary imports (pytest, the module being tested)
- Descriptive test function names: test_<function>_<scenario>_<expected>
- Docstrings explaining what each test validates
- Multiple test cases per function (normal case, edge cases, error cases)

OUTPUT: Complete pytest file ready to run (no JSON, just Python code)."""

            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            logger.debug("Calling LLM to generate tests for: %s", file_path)
            response = self._llm.invoke(messages)
            
            test_code = response.content.strip()
            
            # Log the interaction
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.GENERATION,
                details={
                    "input_prompt": user_prompt,
                    "output_response": test_code,
                    "file_tested": file_path,
                    "code_length": len(code),
                    "test_length": len(test_code),
                    "iteration": context.iteration
                },
                status="SUCCESS"
            )
            
            # Clean up the response (remove markdown code blocks if present)
            test_code = self._clean_code_response(test_code)
            
            return test_code
            
        except Exception as e:
            logger.error("LLM test generation failed for %s: %s", file_path, e)
            
            # Log failure
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.GENERATION,
                details={
                    "input_prompt": f"Generate tests for {file_path}",
                    "output_response": f"Error: {str(e)}",
                    "file_tested": file_path,
                    "error": str(e),
                    "iteration": context.iteration
                },
                status="FAILURE"
            )
            
            return None
    
    def _clean_code_response(self, code: str) -> str:
        """
        Clean LLM response to extract pure Python code.
        
        Removes markdown code blocks and other formatting.
        
        Args:
            code: Raw LLM response
            
        Returns:
            Cleaned Python code
        """
        # Remove markdown code blocks
        if "```python" in code:
            parts = code.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
        elif "```" in code:
            parts = code.split("```")
            if len(parts) >= 2:
                code = parts[1].split("```")[0] if len(parts) > 2 else parts[1]
        
        return code.strip()
    
    def _get_test_file_path(self, source_file: str) -> str:
        """
        Get the path for the test file corresponding to a source file.
        
        Follows pytest convention: test_<filename>.py
        
        Args:
            source_file: Path to source file
            
        Returns:
            Path to test file
        """
        source_path = Path(source_file)
        test_filename = f"test_{source_path.stem}.py"
        test_path = source_path.parent / test_filename
        return str(test_path)
    
    def _run_all_tests(
        self,
        target_dir: str,
        sandbox: SandboxValidator,
        context: "SwarmContext"
    ) -> Dict[str, Any]:
        """
        Run all tests in the target directory using pytest.
        
        Args:
            target_dir: Directory containing code and tests
            sandbox: Sandbox validator
            context: Swarm context
            
        Returns:
            Test results dictionary from run_pytest
        """
        if self.verbose:
            print(f"   🧪 Running pytest on all tests...")
        
        try:
            # Discover tests
            test_files = discover_tests(target_dir, sandbox)
            
            if not test_files and not self.generate_tests:
                logger.warning("No test files found in: %s", target_dir)
                return {
                    'success': True,  # No tests = no failures
                    'passed': 0,
                    'failed': 0,
                    'total': 0,
                    'error_messages': [],
                    'output': 'No tests found'
                }
            
            if self.verbose and test_files:
                print(f"      Found {len(test_files)} test files")
            
            # Run pytest
            result = run_pytest(
                directory=target_dir,
                sandbox=sandbox,
                timeout=self.test_timeout,
                verbose=self.verbose
            )
            
            # Log test execution
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.DEBUG,  # Testing is debugging
                details={
                    "input_prompt": f"Run pytest on {target_dir}",
                    "output_response": result['output'],
                    "passed": result['passed'],
                    "failed": result['failed'],
                    "total": result['total'],
                    "success": result['success'],
                    "duration": result['duration'],
                    "test_files_count": len(test_files),
                    "iteration": context.iteration
                },
                status="SUCCESS" if result['success'] else "FAILURE"
            )
            
            if self.verbose:
                print(f"      ✓ Tests completed: {result['passed']} passed, {result['failed']} failed")
            
            return result
            
        except Exception as e:
            logger.error("Failed to run tests: %s", e)
            
            # Log failure
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.DEBUG,
                details={
                    "input_prompt": f"Run pytest on {target_dir}",
                    "output_response": f"Error: {str(e)}",
                    "error": str(e),
                    "iteration": context.iteration
                },
                status="FAILURE"
            )
            
            return {
                'success': False,
                'passed': 0,
                'failed': 1,
                'total': 1,
                'error_messages': [str(e)],
                'output': str(e)
            }
    
    def _analyze_test_results(
        self,
        test_results: Dict[str, Any],
        context: "SwarmContext"
    ) -> None:
        """
        Analyze test results and update context accordingly.
        
        If tests passed: Mark as FIX_SUCCESS (mission complete)
        If tests failed: Prepare error logs and trigger self-healing loop
        
        Args:
            test_results: Results from run_pytest
            context: Swarm context to update
        """
        from main import SwarmState
        
        # Store results in context
        context.validation_results.append({
            "iteration": context.iteration,
            "test_results": test_results,
            "agent": self.name
        })
        
        if test_results['success']:
            # All tests passed!
            context.current_state = SwarmState.FIX_SUCCESS
            logger.info("All tests passed. Marking as FIX_SUCCESS")
            
        else:
            # Tests failed - prepare for self-healing loop
            context.current_state = SwarmState.FIX_FAILED
            
            # Extract error messages for Corrector
            error_messages = test_results.get('error_messages', [])
            
            # Add detailed failure information
            detailed_errors = []
            detailed_errors.append(f"Test run failed: {test_results['failed']} of {test_results['total']} tests failed")
            
            # Add specific error messages
            for i, error in enumerate(error_messages, 1):
                detailed_errors.append(f"Error {i}: {error}")
            
            # Add test output summary
            if 'output' in test_results and test_results['output']:
                # Extract relevant failure sections from pytest output
                output = test_results['output']
                if 'FAILED' in output:
                    detailed_errors.append("\nFailed tests details:")
                    # Extract lines containing FAILED
                    for line in output.split('\n'):
                        if 'FAILED' in line or 'AssertionError' in line or 'Error:' in line:
                            detailed_errors.append(line.strip())
            
            # Store error logs for Corrector to use in self-healing
            context.test_error_logs = detailed_errors
            
            # Track which tests failed (for targeted fixes)
            failed_tests = []
            for test_result in test_results.get('test_results', []):
                if test_result.get('status') in ('failed', 'error'):
                    failed_tests.append(test_result.get('name', 'unknown'))
            
            context.last_failed_tests = failed_tests
            
            # Increment healing counter
            context.healing_attempts += 1
            
            logger.warning(
                "Tests failed. Healing attempt %d/%d. Failed tests: %s",
                context.healing_attempts,
                context.max_iterations,
                ", ".join(failed_tests) if failed_tests else "unknown"
            )
            
            # Add to error log
            context.error_log.append(
                f"Validation failed at iteration {context.iteration}: "
                f"{test_results['failed']} tests failed"
            )
    
    def __repr__(self) -> str:
        return f"<ValidatorAgent name='{self.name}' model='{self.model}' generate_tests={self.generate_tests}>"
