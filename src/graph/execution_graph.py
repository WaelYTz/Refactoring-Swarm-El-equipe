"""
Execution Graph - LangGraph Implementation
==========================================
Lead Dev: Orchestrateur responsible for execution graph design.

This module implements the Refactoring Swarm pipeline using LangGraph,
providing a declarative, visual execution flow.

EXECUTION GRAPH:
----------------
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
    │   VALIDATOR     │ ◄──── Runs tests (Judge)
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
    ▼                 │
┌────────┐           │
│  END   │           ▼
│SUCCESS │    ┌──────────────────┐
└────────┘    │ SELF-HEALING     │
              │ (back to CORRECTOR)
              └──────────────────┘

Course: IGL Lab 2025-2026 - ESI Algiers
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END


# =============================================================================
# GRAPH STATE DEFINITION
# =============================================================================

class AgentRole(str, Enum):
    """Available agent roles in the swarm."""
    LISTENER = "listener"
    CORRECTOR = "corrector"
    VALIDATOR = "validator"


class SwarmState(str, Enum):
    """Possible states of the execution pipeline."""
    IDLE = "idle"
    LISTENING = "listening"
    ISSUES_DETECTED = "issues_detected"
    FIXING = "fixing"
    VALIDATING = "validating"
    FIX_SUCCESS = "fix_success"
    FIX_FAILED = "fix_failed"
    COMPLETED = "completed"
    ABORTED = "aborted"


class GraphState(TypedDict):
    """
    State that flows through the LangGraph execution.
    This is the "baton" passed between nodes.
    """
    # Target configuration
    target_dir: str
    max_iterations: int
    verbose: bool
    
    # Current execution state
    current_state: str
    current_agent: str
    iteration: int
    
    # Data passed between agents
    detected_issues: List[Dict[str, Any]]
    applied_fixes: List[Dict[str, Any]]
    validation_results: List[Dict[str, Any]]
    
    # Self-Healing Loop data
    test_error_logs: List[str]
    last_failed_tests: List[str]
    healing_attempts: int
    
    # Execution tracking
    started_at: str
    ended_at: str
    error_log: List[str]
    
    # Agent instances (injected)
    agents: Dict[str, Any]


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

def listener_node(state: GraphState) -> GraphState:
    """
    LISTENER NODE: Analyzes code and detects issues.
    
    The Auditor agent scans the target directory for code issues.
    """
    if state.get("verbose", True):
        print(f"\n🔍 [LISTENER NODE] Analyzing code in {state['target_dir']}...")
    
    state["current_state"] = SwarmState.LISTENING.value
    state["current_agent"] = AgentRole.LISTENER.value
    
    # Get the listener agent
    agents = state.get("agents", {})
    listener = agents.get("listener")
    
    if listener is None:
        state["error_log"].append("Listener agent not registered")
        state["current_state"] = SwarmState.ABORTED.value
        return state
    
    try:
        # Create a context-like object for the agent
        from main import SwarmContext
        context = SwarmContext(
            target_dir=state["target_dir"],
            max_iterations=state["max_iterations"],
            iteration=state["iteration"],
            detected_issues=[],
            applied_fixes=state.get("applied_fixes", []),
            test_error_logs=state.get("test_error_logs", []),
        )
        
        # Run the listener agent
        result_context = listener.run(context)
        
        # Update state with results
        state["detected_issues"] = [
            issue if isinstance(issue, dict) else {
                "file_path": getattr(issue, "file_path", ""),
                "line_number": getattr(issue, "line_number", None),
                "issue_type": getattr(issue, "issue_type", ""),
                "description": getattr(issue, "description", ""),
                "severity": getattr(issue, "severity", ""),
            }
            for issue in result_context.detected_issues
        ]
        
        if state["detected_issues"]:
            state["current_state"] = SwarmState.ISSUES_DETECTED.value
            if state.get("verbose", True):
                print(f"   Found {len(state['detected_issues'])} issues")
        else:
            state["current_state"] = SwarmState.COMPLETED.value
            if state.get("verbose", True):
                print("   ✅ No issues found - code is clean!")
                
    except Exception as e:
        state["error_log"].append(f"Listener error: {str(e)}")
        state["current_state"] = SwarmState.ABORTED.value
        if state.get("verbose", True):
            print(f"   ❌ Error: {e}")
    
    return state


def corrector_node(state: GraphState) -> GraphState:
    """
    CORRECTOR NODE: Applies fixes to detected issues.
    
    The Fixer agent modifies code to correct errors.
    """
    if state.get("verbose", True):
        print(f"\n🔧 [CORRECTOR NODE] Fixing issues (Iteration {state['iteration']})...")
    
    state["current_state"] = SwarmState.FIXING.value
    state["current_agent"] = AgentRole.CORRECTOR.value
    
    # Get the corrector agent
    agents = state.get("agents", {})
    corrector = agents.get("corrector")
    
    if corrector is None:
        state["error_log"].append("Corrector agent not registered")
        state["current_state"] = SwarmState.ABORTED.value
        return state
    
    try:
        # Create context for the agent
        from main import SwarmContext
        context = SwarmContext(
            target_dir=state["target_dir"],
            max_iterations=state["max_iterations"],
            iteration=state["iteration"],
            detected_issues=state.get("detected_issues", []),
            applied_fixes=state.get("applied_fixes", []),
            test_error_logs=state.get("test_error_logs", []),
        )
        
        # Run the corrector agent
        result_context = corrector.run(context)
        
        # Update state with results
        state["applied_fixes"] = result_context.applied_fixes
        state["current_state"] = SwarmState.VALIDATING.value
        
        if state.get("verbose", True):
            print(f"   Applied {len(result_context.applied_fixes)} fixes")
            
    except Exception as e:
        state["error_log"].append(f"Corrector error: {str(e)}")
        state["current_state"] = SwarmState.ABORTED.value
        if state.get("verbose", True):
            print(f"   ❌ Error: {e}")
    
    return state


def validator_node(state: GraphState) -> GraphState:
    """
    VALIDATOR NODE: Validates fixes by running tests.
    
    The Judge agent generates and runs tests to verify fixes.
    """
    if state.get("verbose", True):
        print(f"\n🧪 [VALIDATOR NODE] Running tests...")
    
    state["current_state"] = SwarmState.VALIDATING.value
    state["current_agent"] = AgentRole.VALIDATOR.value
    
    # Get the validator agent
    agents = state.get("agents", {})
    validator = agents.get("validator")
    
    if validator is None:
        state["error_log"].append("Validator agent not registered")
        state["current_state"] = SwarmState.ABORTED.value
        return state
    
    try:
        # Create context for the agent
        from main import SwarmContext
        context = SwarmContext(
            target_dir=state["target_dir"],
            max_iterations=state["max_iterations"],
            iteration=state["iteration"],
            detected_issues=state.get("detected_issues", []),
            applied_fixes=state.get("applied_fixes", []),
            test_error_logs=[],
        )
        
        # Run the validator agent
        result_context = validator.run(context)
        
        # Update state with results
        state["test_error_logs"] = result_context.test_error_logs
        state["validation_results"] = result_context.validation_results
        
        # Determine success or failure
        if result_context.current_state.value == "fix_success":
            state["current_state"] = SwarmState.FIX_SUCCESS.value
            if state.get("verbose", True):
                print("   ✅ All tests passed!")
        else:
            state["current_state"] = SwarmState.FIX_FAILED.value
            state["healing_attempts"] = state.get("healing_attempts", 0) + 1
            if state.get("verbose", True):
                print(f"   ❌ Tests failed - triggering self-healing loop")
                
    except Exception as e:
        state["error_log"].append(f"Validator error: {str(e)}")
        state["current_state"] = SwarmState.ABORTED.value
        if state.get("verbose", True):
            print(f"   ❌ Error: {e}")
    
    return state


# =============================================================================
# CONDITIONAL EDGES (DECISION NODES)
# =============================================================================

def should_fix(state: GraphState) -> str:
    """
    DECISION NODE after LISTENER:
    - If issues found → go to CORRECTOR
    - If no issues → END (success)
    """
    if state["current_state"] == SwarmState.ABORTED.value:
        return "end"
    
    if state["current_state"] == SwarmState.ISSUES_DETECTED.value:
        return "corrector"
    
    # No issues found - code is clean
    return "end"


def should_continue_healing(state: GraphState) -> str:
    """
    DECISION NODE after VALIDATOR (Self-Healing Loop):
    - If tests pass → END (success)
    - If tests fail AND iterations left → back to CORRECTOR
    - If max iterations reached → END (failure)
    """
    if state["current_state"] == SwarmState.ABORTED.value:
        return "end"
    
    if state["current_state"] == SwarmState.FIX_SUCCESS.value:
        return "end"
    
    if state["current_state"] == SwarmState.FIX_FAILED.value:
        # Check if we can retry
        state["iteration"] = state.get("iteration", 0) + 1
        if state["iteration"] < state["max_iterations"]:
            if state.get("verbose", True):
                print(f"\n🔄 [SELF-HEALING LOOP] Iteration {state['iteration'] + 1}/{state['max_iterations']}")
            return "corrector"  # Retry with error logs
        else:
            if state.get("verbose", True):
                print(f"\n🛑 Max iterations reached ({state['max_iterations']})")
            return "end"
    
    return "end"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def build_execution_graph() -> StateGraph:
    """
    Build the LangGraph execution graph.
    
    Returns:
        Compiled StateGraph ready for execution.
    """
    # Create the graph with our state schema
    workflow = StateGraph(GraphState)
    
    # Add nodes (agents)
    workflow.add_node("listener", listener_node)
    workflow.add_node("corrector", corrector_node)
    workflow.add_node("validator", validator_node)
    
    # Set entry point
    workflow.set_entry_point("listener")
    
    # Add conditional edge after LISTENER (Decision Node 1)
    workflow.add_conditional_edges(
        "listener",
        should_fix,
        {
            "corrector": "corrector",
            "end": END,
        }
    )
    
    # Add edge from CORRECTOR to VALIDATOR
    workflow.add_edge("corrector", "validator")
    
    # Add conditional edge after VALIDATOR (Self-Healing Loop Decision)
    workflow.add_conditional_edges(
        "validator",
        should_continue_healing,
        {
            "corrector": "corrector",  # Self-healing: back to corrector
            "end": END,
        }
    )
    
    # Compile the graph
    return workflow.compile()


# =============================================================================
# GRAPH RUNNER
# =============================================================================

class LangGraphOrchestrator:
    """
    Orchestrator that runs the LangGraph execution pipeline.
    
    This replaces the manual RelayOrchestrator with a declarative graph.
    """
    
    def __init__(self, target_dir: str, max_iterations: int = 10, verbose: bool = True):
        self.target_dir = target_dir
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.agents: Dict[str, Any] = {}
        self.graph = build_execution_graph()
    
    def register_agent(self, role: str, agent: Any) -> None:
        """Register an agent for a given role."""
        self.agents[role] = agent
        if self.verbose:
            print(f"📝 Registered agent: {role}")
    
    def run(self) -> GraphState:
        """
        Execute the LangGraph pipeline.
        
        Returns:
            Final state after execution.
        """
        # Initialize state
        initial_state: GraphState = {
            "target_dir": self.target_dir,
            "max_iterations": self.max_iterations,
            "verbose": self.verbose,
            "current_state": SwarmState.IDLE.value,
            "current_agent": "",
            "iteration": 0,
            "detected_issues": [],
            "applied_fixes": [],
            "validation_results": [],
            "test_error_logs": [],
            "last_failed_tests": [],
            "healing_attempts": 0,
            "started_at": datetime.now().isoformat(),
            "ended_at": "",
            "error_log": [],
            "agents": self.agents,
        }
        
        if self.verbose:
            print("\n🚀 Starting LangGraph Pipeline...")
            print(f"   Target: {self.target_dir}")
            print(f"   Max Iterations: {self.max_iterations}")
        
        # Run the graph
        final_state = self.graph.invoke(initial_state)
        
        # Set end time
        final_state["ended_at"] = datetime.now().isoformat()
        
        return final_state


def get_graph_visualization() -> str:
    """
    Get ASCII visualization of the execution graph.
    
    Returns:
        ASCII diagram of the graph.
    """
    return """
    ┌─────────────────────────────────────────────────────────┐
    │              LANGGRAPH EXECUTION FLOW                   │
    └─────────────────────────────────────────────────────────┘
    
                         ┌───────────┐
                         │   START   │
                         └─────┬─────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      LISTENER       │
                    │   (Auditor Node)    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   should_fix()?     │ ◄── Decision Node
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
         issues_found                    no_issues_found
              │                                 │
              ▼                                 ▼
    ┌─────────────────────┐           ┌─────────────┐
    │     CORRECTOR       │           │     END     │
    │   (Fixer Node)      │           │  (Success)  │
    └──────────┬──────────┘           └─────────────┘
               │
               ▼
    ┌─────────────────────┐
    │     VALIDATOR       │
    │   (Judge Node)      │
    └──────────┬──────────┘
               │
    ┌──────────▼──────────┐
    │ should_continue_    │ ◄── Self-Healing Decision
    │    healing()?       │
    └──────────┬──────────┘
               │
    ┌──────────┴──────────┐
    │                     │
 tests_pass           tests_fail
    │                     │
    ▼                     │
┌─────────┐              │
│   END   │              ▼
│ SUCCESS │    ┌───────────────────┐
└─────────┘    │  iterations < max │
               └─────────┬─────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
             YES                   NO
              │                     │
              ▼                     ▼
    ┌─────────────────┐     ┌─────────────┐
    │ Back to         │     │    END      │
    │ CORRECTOR       │     │  (Failure)  │
    │ (with errors)   │     └─────────────┘
    └─────────────────┘
    """
