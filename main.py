"""
Refactoring Swarm - Main Orchestrator
======================================
Lead Dev: Orchestrateur responsible for:
- Execution graph design (LangGraph/CrewAI/AutoGen ready)
- Relay handover logic between agents
- CLI argument handling and configuration

EXECUTION GRAPH DESIGN (To be implemented with LangGraph):
----------------------------------------------------------
                    ┌─────────────────┐
                    │     START       │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    LISTENER     │ ◄──── Analyzes code, detects issues
                    │   (Auditor)     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
              ┌─────│   DECISION      │─────┐
              │     │    NODE         │     │
              │     └─────────────────┘     │
              │                             │
        issues_found              no_issues_found
              │                             │
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │   CORRECTOR     │           │      END        │
    │    (Fixer)      │           │   (Success)     │
    └────────┬────────┘           └─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │   VALIDATOR     │ ◄──── Runs tests (Judge), checks fixes
    │    (Judge)      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │  LOOP DECISION  │
    └────────┬────────┘
             │
    ┌────────┴────────┐
    │                 │
 tests_pass       tests_fail
    │                 │
    ▼                 ▼
┌────────┐    ┌─────────────────────────────────────┐
│  END   │    │      SELF-HEALING LOOP              │
│SUCCESS │    │  Judge sends error_logs back to     │
└────────┘    │  Corrector for retry                │
              └─────────────────┬───────────────────┘
                                │
                      max_iterations reached? 
                           │         │
                          YES       NO 
                           │         │
                           ▼         ▼
                      ┌────────┐  ┌──────────────────┐
                      │  END   │  │ Back to CORRECTOR│
                      │FAILURE │  │ (with error logs)│
                      └────────┘  └──────────────────┘
"""

import argparse
import sys
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from dotenv import load_dotenv

# Import agents
from src.agents import ListenerAgent, CorrectorAgent, ValidatorAgent

load_dotenv()


# =============================================================================
# ORCHESTRATION STATE & TYPES
# =============================================================================

class AgentRole(str, Enum):
    """Available agent roles in the swarm."""
    LISTENER = "listener"       # Auditor - analyzes code
    CORRECTOR = "corrector"     # Fixer - applies fixes
    VALIDATOR = "validator"     # Tester - validates fixes
    ORCHESTRATOR = "orchestrator"


class SwarmState(str, Enum):
    """Possible states of the execution pipeline."""
    IDLE = "idle"
    LISTENING = "listening"           # Listener is analyzing
    ISSUES_DETECTED = "issues_detected"
    CORRECTING = "correcting"         # Corrector is fixing
    VALIDATING = "validating"         # Validator is testing
    FIX_SUCCESS = "fix_success"
    FIX_FAILED = "fix_failed"
    COMPLETED = "completed"
    ABORTED = "aborted"


@dataclass
class Issue:
    """Represents a detected code issue."""
    file_path: str
    line_number: Optional[int]
    issue_type: str
    description: str
    severity: str  # "critical", "warning", "info"
    suggested_fix: Optional[str] = None


@dataclass
class SwarmContext:
    """
    Shared state passed between agents during execution.
    This is the "baton" in the relay handover.
    """
    target_dir: str
    current_state: SwarmState = SwarmState.IDLE
    current_agent: Optional[AgentRole] = None
    iteration: int = 0
    max_iterations: int = 3
    
    # Data passed between agents
    detected_issues: List[Issue] = field(default_factory=list)
    applied_fixes: List[Dict[str, Any]] = field(default_factory=list)
    validation_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Self-Healing Loop: Error context passed from Judge to Corrector
    test_error_logs: List[str] = field(default_factory=list)  # pytest failures
    last_failed_tests: List[str] = field(default_factory=list)  # test names that failed
    healing_attempts: int = 0  # track how many self-healing iterations
    
    # Execution tracking
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_log: List[str] = field(default_factory=list)
    
    def should_continue(self) -> bool:
        """Determine if the loop should continue."""
        if self.current_state == SwarmState.COMPLETED:
            return False
        if self.current_state == SwarmState.ABORTED:
            return False
        if self.iteration >= self.max_iterations:
            return False
        return True
    
    def has_unresolved_issues(self) -> bool:
        """Check if there are still issues to fix."""
        return len(self.detected_issues) > 0


# =============================================================================
# RELAY HANDOVER LOGIC
# =============================================================================

class RelayOrchestrator:
    """
    Manages the handover between agents.
    Decides WHEN to switch and WHO gets control next.
    """
    
    def __init__(self, context: SwarmContext, verbose: bool = True):
        self.context = context
        self.verbose = verbose
        # Agent instances will be injected by team members
        self._agents: Dict[AgentRole, Any] = {}
    
    def register_agent(self, role: AgentRole, agent_instance: Any) -> None:
        """Register an agent instance for a given role."""
        self._agents[role] = agent_instance
        if self.verbose:
            print(f"📝 Registered agent: {role.value}")
    
    def _log(self, message: str) -> None:
        """Internal logging."""
        if self.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{timestamp}] 🧠 Orchestrator: {message}")
    
    def determine_next_agent(self) -> Optional[AgentRole]:
        """
        HANDOVER LOGIC: Determines which agent should run next.
        
        Returns:
            The next agent role, or None if the pipeline should stop.
        """
        state = self.context.current_state
        
        # State machine transitions
        if state == SwarmState.IDLE:
            return AgentRole.LISTENER
        
        elif state == SwarmState.LISTENING:
            # Listener finished → check results
            return None  # Wait for listener to complete
        
        elif state == SwarmState.ISSUES_DETECTED:
            # Issues found → hand over to Corrector
            return AgentRole.CORRECTOR
        
        elif state == SwarmState.CORRECTING:
            # Corrector finished → validate
            return None  # Wait for corrector to complete
        
        elif state == SwarmState.VALIDATING:
            return None  # Wait for validator
        
        elif state == SwarmState.FIX_SUCCESS:
            # Check if more issues remain
            if self.context.has_unresolved_issues():
                return AgentRole.CORRECTOR
            return None  # Done!
        
        elif state == SwarmState.FIX_FAILED:
            # SELF-HEALING LOOP: Judge detected test failures
            # Send back to Corrector WITH error logs (as per lab requirements)
            self.context.healing_attempts += 1
            if self.context.iteration < self.context.max_iterations:
                self._log(f"🔄 Self-Healing Loop #{self.context.healing_attempts}: "
                         f"Sending {len(self.context.test_error_logs)} error(s) back to Corrector")
                return AgentRole.CORRECTOR
            return None  # Max retries reached
        
        elif state in (SwarmState.COMPLETED, SwarmState.ABORTED):
            return None
        
        return None
    
    def should_stop_loop(self) -> tuple[bool, str]:
        """
        STOP CONDITIONS: Determines if the execution loop should terminate.
        
        Returns:
            Tuple of (should_stop: bool, reason: str)
        """
        # Condition 1: Max iterations reached
        if self.context.iteration >= self.context.max_iterations:
            return True, f"Max iterations reached ({self.context.max_iterations})"
        
        # Condition 2: No more issues
        if self.context.current_state == SwarmState.COMPLETED:
            return True, "All issues resolved successfully"
        
        # Condition 3: Pipeline aborted
        if self.context.current_state == SwarmState.ABORTED:
            reason = self.context.error_log[-1] if self.context.error_log else "Unknown error"
            return True, f"Pipeline aborted: {reason}"
        
        # Condition 4: No issues detected from start
        if (self.context.current_state == SwarmState.LISTENING and 
            not self.context.has_unresolved_issues() and 
            self.context.iteration > 0):
            return True, "No issues detected - code is clean"
        
        return False, ""
    
    def transition_state(self, new_state: SwarmState) -> None:
        """Transition to a new state with logging."""
        old_state = self.context.current_state
        self.context.current_state = new_state
        self._log(f"State transition: {old_state.value} → {new_state.value}")
    
    def handover_to(self, agent_role: AgentRole) -> None:
        """
        Perform the relay handover to the specified agent.
        """
        self.context.current_agent = agent_role
        self._log(f"🔄 Handover to: {agent_role.value.upper()}")
        
        # Update state based on which agent is taking over
        state_map = {
            AgentRole.LISTENER: SwarmState.LISTENING,
            AgentRole.CORRECTOR: SwarmState.CORRECTING,
            AgentRole.VALIDATOR: SwarmState.VALIDATING,
        }
        if agent_role in state_map:
            self.transition_state(state_map[agent_role])
    
    def run_pipeline(self) -> SwarmContext:
        """
        Main execution loop - runs the agent pipeline.
        
        NOTE: Agent execution (agent.run()) will be implemented by team members.
        This method handles the orchestration logic only.
        """
        self.context.started_at = datetime.now()
        self._log(f"🚀 Starting pipeline on: {self.context.target_dir}")
        
        while self.context.should_continue():
            self.context.iteration += 1
            self._log(f"━━━ Iteration {self.context.iteration}/{self.context.max_iterations} ━━━")
            
            # Determine next agent
            next_agent = self.determine_next_agent()
            
            if next_agent is None:
                should_stop, reason = self.should_stop_loop()
                if should_stop:
                    self._log(f"🛑 Stopping: {reason}")
                    break
                continue
            
            # Perform handover
            self.handover_to(next_agent)
            
            # Execute agent (placeholder - agents will implement their logic)
            if next_agent in self._agents:
                agent = self._agents[next_agent]
                try:
                    # Agent execution interface: agent.run(context) -> context
                    self.context = agent.run(self.context)
                except Exception as e:
                    self.context.error_log.append(str(e))
                    self.transition_state(SwarmState.ABORTED)
                    self._log(f"❌ Agent {next_agent.value} failed: {e}")
                    break
            else:
                # No agent registered - placeholder for development
                self._log(f"⚠️ No agent registered for {next_agent.value} - skipping")
                # Simulate progression for testing
                if next_agent == AgentRole.LISTENER:
                    self.transition_state(SwarmState.COMPLETED)
        
        # Finalize
        self.context.ended_at = datetime.now()
        if self.context.current_state not in (SwarmState.COMPLETED, SwarmState.ABORTED):
            self.transition_state(SwarmState.COMPLETED)
        
        return self.context


# =============================================================================
# CLI ARGUMENT HANDLING
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse and validate CLI arguments.
    
    Usage:
        python main.py --target_dir ./my_project
        python main.py --target_dir ./src --max_iterations 5 --verbose
        python main.py --target_dir ./code --dry_run
    """
    parser = argparse.ArgumentParser(
        prog="refactoring-swarm",
        description="🤖 Multi-Agent Code Refactoring Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --target_dir ./my_project
  python main.py --target_dir ./src --max_iterations 5
  python main.py --target_dir ./code --dry_run --verbose

Agent Roles:
  LISTENER   - Analyzes code and detects issues
  CORRECTOR  - Applies fixes to detected issues  
  VALIDATOR  - Validates fixes by running tests
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--target_dir", 
        type=str, 
        required=True,
        help="Directory containing code to refactor"
    )
    
    # Optional arguments
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=3,
        help="Maximum number of fix iterations (default: 3)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="Analyze only, don't apply fixes"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to configuration file (JSON)"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save execution report"
    )
    
    return parser.parse_args()


def validate_arguments(args: argparse.Namespace) -> None:
    """Validate CLI arguments and check prerequisites."""
    
    # Check target directory exists
    if not os.path.exists(args.target_dir):
        print(f"❌ Error: Directory not found: {args.target_dir}")
        sys.exit(1)
    
    if not os.path.isdir(args.target_dir):
        print(f"❌ Error: Path is not a directory: {args.target_dir}")
        sys.exit(1)
    
    # Validate max_iterations
    if args.max_iterations < 1:
        print("❌ Error: --max_iterations must be at least 1")
        sys.exit(1)
    
    if args.max_iterations > 10:
        print("⚠️ Warning: High iteration count may be slow")
    
    # Check config file if provided
    if args.config and not os.path.exists(args.config):
        print(f"❌ Error: Config file not found: {args.config}")
        sys.exit(1)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the Refactoring Swarm."""
    
    # Parse and validate arguments
    args = parse_arguments()
    validate_arguments(args)
    
    # Display banner
    print("\n" + "=" * 60)
    print("🤖 REFACTORING SWARM - Multi-Agent Code Improvement")
    print("=" * 60)
    print(f"📁 Target: {os.path.abspath(args.target_dir)}")
    print(f"🔄 Max Iterations: {args.max_iterations}")
    print(f"📢 Verbose: {args.verbose}")
    print(f"🧪 Dry Run: {args.dry_run}")
    print("=" * 60 + "\n")
    
    # Initialize context (the "baton" for relay)
    context = SwarmContext(
        target_dir=os.path.abspath(args.target_dir),
        max_iterations=args.max_iterations
    )
    
    # Initialize orchestrator
    orchestrator = RelayOrchestrator(context, verbose=args.verbose)
    
    # Register agents
    try:
        orchestrator.register_agent(AgentRole.LISTENER, ListenerAgent(verbose=args.verbose))
        orchestrator.register_agent(AgentRole.CORRECTOR, CorrectorAgent(verbose=args.verbose))
        orchestrator.register_agent(AgentRole.VALIDATOR, ValidatorAgent(verbose=args.verbose))
        print("✅ All agents registered successfully")
    except Exception as e:
        print(f"❌ Error: Failed to register agents: {e}")
        print(f"   Make sure GOOGLE_API_KEY is set in .env file")
        sys.exit(1)
    
    # Run pipeline (unless dry_run)
    if args.dry_run:
        print("🧪 DRY RUN MODE - Analysis only, no changes will be made")
        orchestrator.handover_to(AgentRole.LISTENER)
        print("✅ Dry run complete - no agents registered yet")
    else:
        final_context = orchestrator.run_pipeline()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 EXECUTION SUMMARY")
        print("=" * 60)
        print(f"Final State: {final_context.current_state.value}")
        print(f"Iterations: {final_context.iteration}")
        print(f"Issues Detected: {len(final_context.detected_issues)}")
        print(f"Fixes Applied: {len(final_context.applied_fixes)}")
        if final_context.error_log:
            print(f"Errors: {len(final_context.error_log)}")
        print("=" * 60)
    
    print("\n✅ MISSION COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())