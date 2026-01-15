"""
Listener Agent (Auditor)
========================
The Listener agent analyzes Python code for issues and produces a refactoring plan.

Role in the Swarm:
1. Reads code from target directory
2. Runs static analysis (pylint) 
3. Uses LLM to detect additional issues
4. Produces a list of Issue objects for the Corrector

This agent is the first in the pipeline:
    LISTENER → CORRECTOR → VALIDATOR

Author: Lead Dev (Orchestrateur)
"""

import json
import os
import logging
from typing import List, Optional, TYPE_CHECKING

# LangChain for LLM integration
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# Local imports
from src.agents.base_agent import BaseAgent
from src.tools import (
    SandboxValidator,
    safe_read,
    list_python_files,
    run_pylint,
)
from src.prompts.listener_prompts import (
    ListenerPrompts,
    PromptVersion,
    validate_issue_response,
)
from src.prompts.context_manager import optimize_context
from src.utils.logger import log_experiment, ActionType

if TYPE_CHECKING:
    from main import SwarmContext, AgentRole, Issue, SwarmState

# Configure module logger
logger = logging.getLogger(__name__)


class ListenerAgent(BaseAgent):
    """
    The Auditor agent - analyzes code and detects issues.
    
    This agent:
    1. Scans the target directory for Python files
    2. Runs pylint for static analysis
    3. Uses Gemini LLM to detect additional issues
    4. Combines and deduplicates findings
    5. Updates SwarmContext with detected_issues
    
    Usage:
        from src.agents.listener_agent import ListenerAgent
        
        listener = ListenerAgent()
        context = listener.run(context)
        print(f"Found {len(context.detected_issues)} issues")
    """
    
    def __init__(
        self,
        name: str = "Listener_Agent",
        model: str = "gemini-2.5-flash",
        prompt_version: PromptVersion = PromptVersion.V1_BASIC,
        use_llm: bool = True,
        use_pylint: bool = True,
        verbose: bool = True
    ):
        """
        Initialize the Listener agent.
        
        Args:
            name: Agent identifier for logging
            model: LLM model to use (default: gemini-2.5-flash)
            prompt_version: Which prompt version to use (for A/B testing)
            use_llm: Whether to use LLM analysis (can disable for testing)
            use_pylint: Whether to run pylint analysis
            verbose: Whether to print progress messages
        """
        super().__init__(name=name, model=model)
        self.prompt_version = prompt_version
        self.use_llm = use_llm
        self.use_pylint = use_pylint
        self.verbose = verbose
        
        # Initialize LLM if enabled
        self._llm: Optional[ChatGoogleGenerativeAI] = None
        if self.use_llm:
            self._init_llm()
    
    def _init_llm(self) -> None:
        """Initialize the Google Gemini LLM."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not found - LLM analysis disabled")
            self.use_llm = False
            return
        
        try:
            self._llm = ChatGoogleGenerativeAI(
                model=self.model,
                google_api_key=api_key,
                temperature=0.1,  # Low temperature for consistent analysis
                convert_system_message_to_human=True,
            )
            logger.info("LLM initialized: %s", self.model)
        except Exception as e:
            logger.error("Failed to initialize LLM: %s", e)
            self.use_llm = False
    
    @property
    def role(self) -> "AgentRole":
        """Return the agent's role."""
        from main import AgentRole
        return AgentRole.LISTENER
    
    def _log(self, message: str) -> None:
        """Print message if verbose mode is on."""
        if self.verbose:
            print(f"🔍 [{self.name}] {message}")
    
    def run(self, context: "SwarmContext") -> "SwarmContext":
        """
        Execute the Listener agent's main task.
        
        Steps:
        1. Initialize sandbox for target directory
        2. Discover Python files
        3. Run pylint analysis on each file
        4. Run LLM analysis on each file
        5. Combine and deduplicate issues
        6. Update context with detected_issues
        7. Transition state based on findings
        
        Args:
            context: The shared SwarmContext
            
        Returns:
            Updated SwarmContext with detected_issues populated
        """
        from main import Issue, SwarmState
        
        self._log(f"Starting analysis of: {context.target_dir}")
        
        # Initialize sandbox for security
        try:
            sandbox = SandboxValidator(context.target_dir)
        except Exception as e:
            self._log(f"❌ Failed to initialize sandbox: {e}")
            context.error_log.append(f"Sandbox init failed: {e}")
            context.current_state = SwarmState.ABORTED
            return context
        
        # Discover Python files - use "." since sandbox is already set to target_dir
        try:
            python_files = list_python_files(".", sandbox)
            self._log(f"Found {len(python_files)} Python files to analyze")
        except Exception as e:
            self._log(f"❌ Failed to list files: {e}")
            context.error_log.append(f"File discovery failed: {e}")
            context.current_state = SwarmState.ABORTED
            return context
        
        if not python_files:
            self._log("⚠️ No Python files found in target directory")
            context.current_state = SwarmState.COMPLETED
            return context
        
        all_issues: List["Issue"] = []
        
        # Analyze each file
        for file_path in python_files:
            self._log(f"Analyzing: {file_path}")
            
            # Get relative path for cleaner output
            rel_path = os.path.relpath(file_path, context.target_dir)
            
            # Run pylint analysis
            if self.use_pylint:
                pylint_issues = self._run_pylint_analysis(file_path, rel_path)
                all_issues.extend(pylint_issues)
                self._log(f"  └─ Pylint found {len(pylint_issues)} issues")
            
            # Run LLM analysis
            if self.use_llm and self._llm:
                llm_issues = self._run_llm_analysis(file_path, rel_path, sandbox)
                all_issues.extend(llm_issues)
                self._log(f"  └─ LLM found {len(llm_issues)} issues")
        
        # Deduplicate issues (same file + line + type)
        unique_issues = self._deduplicate_issues(all_issues)
        self._log(f"Total unique issues: {len(unique_issues)}")
        
        # Update context
        context.detected_issues = unique_issues
        
        # Transition state based on findings
        if unique_issues:
            context.current_state = SwarmState.ISSUES_DETECTED
            self._log(f"🔴 Found {len(unique_issues)} issues - handing over to Corrector")
        else:
            context.current_state = SwarmState.COMPLETED
            self._log("✅ No issues found - code is clean!")
        
        return context
    
    def _run_pylint_analysis(self, file_path: str, rel_path: str) -> List["Issue"]:
        """
        Run pylint on a file and convert results to Issue objects.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path for reporting
            
        Returns:
            List of Issue objects from pylint findings
        """
        from main import Issue
        
        issues = []
        try:
            result = run_pylint(file_path)
            
            if result.get("error"):
                logger.warning("Pylint error for %s: %s", file_path, result["error"])
                return issues
            
            for pylint_issue in result.get("issues", []):
                # Map pylint types to our types
                issue_type = self._map_pylint_type(pylint_issue.get("type", "convention"))
                severity = self._map_pylint_severity(pylint_issue.get("type", "convention"))
                
                issue = Issue(
                    file_path=rel_path,
                    line_number=pylint_issue.get("line", 0),
                    issue_type=issue_type,
                    description=f"[{pylint_issue.get('symbol', 'unknown')}] {pylint_issue.get('message', '')}",
                    severity=severity,
                    suggested_fix=None
                )
                issues.append(issue)
                
        except Exception as e:
            logger.error("Pylint analysis failed for %s: %s", file_path, e)
        
        return issues
    
    def _map_pylint_type(self, pylint_type: str) -> str:
        """Map pylint message type to our issue types."""
        mapping = {
            "error": "BUG",
            "warning": "BUG",
            "convention": "STYLE",
            "refactor": "PERFORMANCE",
        }
        return mapping.get(pylint_type.lower(), "STYLE")
    
    def _map_pylint_severity(self, pylint_type: str) -> str:
        """Map pylint message type to severity."""
        mapping = {
            "error": "critical",
            "warning": "warning",
            "convention": "info",
            "refactor": "info",
        }
        return mapping.get(pylint_type.lower(), "info")
    
    def _run_llm_analysis(
        self,
        file_path: str,
        rel_path: str,
        sandbox: SandboxValidator
    ) -> List["Issue"]:
        """
        Run LLM analysis on a file.
        
        Args:
            file_path: Absolute path to the file
            rel_path: Relative path for reporting
            sandbox: SandboxValidator for secure file reading
            
        Returns:
            List of Issue objects from LLM analysis
        """
        from main import Issue
        
        issues = []
        
        try:
            # Read file content securely
            code = safe_read(file_path, sandbox)
            
            # Optimize code for LLM (remove comments/docstrings to save tokens)
            optimized_code = optimize_context(code)
            
            # Get prompts
            system_prompt = ListenerPrompts.get_system_prompt(self.prompt_version)
            user_prompt = ListenerPrompts.format_analysis_prompt(
                code=optimized_code,
                file_path=rel_path
            )
            
            # Call LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            response = self._llm.invoke(messages)
            response_text = response.content
            
            # Log the interaction for data collection
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.ANALYSIS,
                details={
                    "file_analyzed": rel_path,
                    "input_prompt": f"{system_prompt}\n\n{user_prompt}",
                    "output_response": response_text,
                    "prompt_version": self.prompt_version.value,
                },
                status="SUCCESS"
            )
            
            # Parse LLM response
            issues = self._parse_llm_response(response_text, rel_path)
            
        except Exception as e:
            logger.error("LLM analysis failed for %s: %s", file_path, e)
            # Log failure
            try:
                log_experiment(
                    agent_name=self.name,
                    model_used=self.model,
                    action=ActionType.ANALYSIS,
                    details={
                        "file_analyzed": rel_path,
                        "input_prompt": f"Analysis of {rel_path}",
                        "output_response": f"Error: {str(e)}",
                        "error": str(e),
                    },
                    status="FAILURE"
                )
            except Exception:
                pass  # Don't fail on logging errors
        
        return issues
    
    def _parse_llm_response(self, response_text: str, default_file: str) -> List["Issue"]:
        """
        Parse LLM JSON response into Issue objects.
        
        Args:
            response_text: Raw LLM response
            default_file: Default file path if not specified in issue
            
        Returns:
            List of validated Issue objects
        """
        from main import Issue
        
        issues = []
        
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            parsed = json.loads(json_str.strip())
            
            if not isinstance(parsed, list):
                logger.warning("LLM response is not a list: %s", type(parsed))
                return issues
            
            # Validate and convert each issue
            for item in parsed:
                is_valid, error = validate_issue_response(item)
                if not is_valid:
                    logger.warning("Invalid issue from LLM: %s - %s", item, error)
                    continue
                
                issue = Issue(
                    file_path=item.get("file_path", default_file),
                    line_number=item.get("line_number"),
                    issue_type=item.get("issue_type", "BUG"),
                    description=item.get("description", ""),
                    severity=item.get("severity", "warning"),
                    suggested_fix=item.get("suggested_fix"),
                )
                issues.append(issue)
                
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)
        except Exception as e:
            logger.error("Error parsing LLM response: %s", e)
        
        return issues
    
    def _deduplicate_issues(self, issues: List["Issue"]) -> List["Issue"]:
        """
        Remove duplicate issues based on file, line, and type.
        
        Prioritizes issues with suggested_fix and higher severity.
        
        Args:
            issues: List of potentially duplicate issues
            
        Returns:
            Deduplicated list of issues
        """
        seen = {}
        severity_rank = {"critical": 3, "warning": 2, "info": 1}
        
        for issue in issues:
            key = (issue.file_path, issue.line_number, issue.issue_type)
            
            if key not in seen:
                seen[key] = issue
            else:
                # Keep the one with higher severity or with suggested_fix
                existing = seen[key]
                existing_rank = severity_rank.get(existing.severity, 0)
                new_rank = severity_rank.get(issue.severity, 0)
                
                if new_rank > existing_rank:
                    seen[key] = issue
                elif new_rank == existing_rank and issue.suggested_fix and not existing.suggested_fix:
                    seen[key] = issue
        
        return list(seen.values())
