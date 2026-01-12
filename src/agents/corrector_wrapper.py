"""
Corrector Agent Wrapper
========================
Wrapper to make CorrectorAgent compatible with BaseAgent interface.

The original CorrectorAgent was built with a different interface (fix_code method).
This wrapper adapts it to work with the orchestrator's BaseAgent interface (run method).

This allows the CorrectorAgent to participate in the standard agent pipeline:
    LISTENER → CORRECTOR → VALIDATOR

Author: Integration Team
"""

import logging
from typing import TYPE_CHECKING, Optional

from src.agents.base_agent import BaseAgent
from src.agents.corrector_agent import CorrectorAgent
from src.tools import (
    SandboxValidator,
    safe_read,
    safe_write,
    list_python_files,
)
from src.utils.logger import log_experiment, ActionType

if TYPE_CHECKING:
    from main import SwarmContext, AgentRole, SwarmState

# Configure module logger
logger = logging.getLogger(__name__)


class CorrectorAgentWrapper(BaseAgent):
    """
    Wrapper to make CorrectorAgent compatible with BaseAgent interface.
    
    This allows CorrectorAgent to work with the RelayOrchestrator while
    preserving its original functionality.
    
    Usage:
        from src.agents.corrector_wrapper import CorrectorAgentWrapper
        
        corrector = CorrectorAgentWrapper()
        context = corrector.run(context)
    """
    
    def __init__(
        self,
        name: str = "Corrector_Agent",
        model: str = "gemini-2.5-flash",
        verbose: bool = True
    ):
        """
        Initialize the Corrector wrapper.
        
        Args:
            name: Agent identifier for logging
            model: LLM model to use
            verbose: Whether to print progress messages
        """
        super().__init__(name=name, model=model)
        self.verbose = verbose
        
        # Initialize the actual CorrectorAgent
        self._corrector = CorrectorAgent(
            model_name=model,
            max_iterations=10
        )
        logger.info("CorrectorAgentWrapper initialized with model: %s", model)
    
    @property
    def role(self) -> "AgentRole":
        """Return the agent's role in the swarm."""
        from main import AgentRole
        return AgentRole.CORRECTOR
    
    def run(self, context: "SwarmContext") -> "SwarmContext":
        """
        Execute the correction phase.
        
        This is the main entry point called by the Orchestrator.
        
        Args:
            context: The shared SwarmContext with all pipeline state
            
        Returns:
            The modified SwarmContext after corrections
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
                print(f"   Found {len(python_files)} Python files to fix")
            
            # Check if we have error logs from self-healing loop
            error_logs = None
            if context.test_error_logs:
                error_logs = "\n".join(context.test_error_logs)
                if self.verbose:
                    print(f"   📝 Self-healing mode: Processing {len(context.test_error_logs)} error logs")
            
            # Process each file
            fixed_count = 0
            for file_path in python_files:
                try:
                    # Read current code
                    original_code = safe_read(file_path, sandbox)
                    
                    if not original_code or len(original_code.strip()) < 10:
                        logger.debug("Skipping empty or trivial file: %s", file_path)
                        continue
                    
                    # Prepare audit findings from detected issues
                    # Convert Issue objects to dict format expected by CorrectorAgent
                    file_issues = [
                        issue for issue in context.detected_issues 
                        if issue.file_path == file_path
                    ]
                    
                    if not file_issues and not error_logs:
                        # No issues for this file and no test errors, skip it
                        continue
                    
                    audit_findings = {
                        "issues": [
                            {
                                "line_number": issue.line_number,
                                "issue_type": issue.issue_type,
                                "description": issue.description,
                                "severity": issue.severity,
                                "suggested_fix": issue.suggested_fix
                            }
                            for issue in file_issues
                        ],
                        "score": 5.0,  # Default low score
                        "recommendations": [issue.description for issue in file_issues]
                    }
                    
                    if self.verbose:
                        print(f"   🔧 Fixing: {file_path} ({len(file_issues)} issues)")
                    
                    # Call the corrector
                    fixed_code = self._corrector.fix_code(
                        file_path=file_path,
                        original_code=original_code,
                        audit_findings=audit_findings,
                        error_logs=error_logs
                    )
                    
                    # Write fixed code back
                    safe_write(file_path, fixed_code, sandbox)
                    
                    # Record the fix
                    context.applied_fixes.append({
                        "iteration": context.iteration,
                        "file_path": file_path,
                        "issues_fixed": len(file_issues),
                        "agent": self.name,
                        "had_error_logs": error_logs is not None
                    })
                    
                    fixed_count += 1
                    
                    if self.verbose:
                        print(f"      ✓ Fixed and saved")
                    
                    logger.info("Successfully fixed: %s", file_path)
                    
                except Exception as e:
                    logger.error("Failed to fix %s: %s", file_path, e)
                    context.error_log.append(f"Fix failed for {file_path}: {str(e)}")
            
            # Update state based on results
            if fixed_count > 0:
                if self.verbose:
                    print(f"   ✅ Successfully fixed {fixed_count} files")
                # Clear test error logs after processing them
                context.test_error_logs = []
                context.current_state = SwarmState.VALIDATING  # Move to validation
            else:
                logger.warning("No files were fixed")
                if context.detected_issues:
                    context.current_state = SwarmState.FIX_FAILED
                else:
                    context.current_state = SwarmState.COMPLETED
            
            return context
            
        except Exception as e:
            logger.exception("Corrector agent failed: %s", e)
            context.error_log.append(f"Corrector error: {str(e)}")
            context.current_state = SwarmState.FIX_FAILED
            
            # Log failure
            log_experiment(
                agent_name=self.name,
                model_used=self.model,
                action=ActionType.FIX,
                details={
                    "input_prompt": "Corrector execution failed",
                    "output_response": f"Error: {str(e)}",
                    "error": str(e),
                    "iteration": context.iteration
                },
                status="FAILURE"
            )
            
            return context
    
    def __repr__(self) -> str:
        return f"<CorrectorAgentWrapper name='{self.name}' model='{self.model}'>"
