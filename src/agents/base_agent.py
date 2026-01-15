"""
Base Agent Interface
====================
Defines the contract that all swarm agents must follow.
Team members will inherit from this to implement their agents.

This file is managed by the Lead Dev (Orchestrateur).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports - main.py imports this, we reference its types
    from main import SwarmContext, AgentRole


class BaseAgent(ABC):
    """
    Abstract base class for all swarm agents.
    
    Each agent receives the SwarmContext (the "baton"), 
    performs its work, and returns the modified context.
    
    Implementers:
        - ListenerAgent (Auditor) - analyzes code
        - CorrectorAgent (Fixer) - applies fixes
        - ValidatorAgent (Tester) - validates fixes
    """
    
    def __init__(self, name: str, model: str = "gemini-2.5-flash"):
        """
        Initialize the agent.
        
        Args:
            name: Human-readable agent name
            model: LLM model to use for this agent
        """
        self.name = name
        self.model = model
    
    @property
    @abstractmethod
    def role(self) -> "AgentRole":
        """Return the agent's role in the swarm."""
        pass
    
    @abstractmethod
    def run(self, context: "SwarmContext") -> "SwarmContext":
        """
        Execute the agent's main task.
        
        This is called by the Orchestrator during handover.
        The agent should:
        1. Read necessary data from context
        2. Perform its task
        3. Update context with results
        4. Return the modified context
        
        Args:
            context: The shared SwarmContext with all pipeline state
            
        Returns:
            The modified SwarmContext after agent execution
            
        Raises:
            Exception: If the agent encounters an unrecoverable error
        """
        pass
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' model='{self.model}'>"
