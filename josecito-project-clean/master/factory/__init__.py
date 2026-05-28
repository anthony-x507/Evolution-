"""
MASTER Factory
=============
The operational backbone that manages tickets, routes work,
evolves skills, and handles infrastructure.

The Factory has three agent levels:
1. Engineer — monitors, resets, modifies skills (only talks to Superior)
2. Superior Agent — exclusive bridge Engineer ↔ Internal Agents
3. Internal Agents — Builder, Auditor, Reviewer (workers)

Every agent has its own GPS + Self-Awareness.
Internal agents auto-generate skills from successful patterns.
Skills enter the Sandbox, get modified, and emerge "superior".

The FactoryManager is the top-level orchestrator. Main Agent and
Internal Agents interact with the Factory ONLY through the FactoryManager.
"""

from .ticket import Ticket, TicketStatus, TicketPriority, TicketType
from .router import TicketRouter, RoutingRule
from .engineer import FactoryEngineer
from .agent_base import AgentBase
from .superior import SuperiorAgent
from .internal import InternalAgent, BuilderAgent, AuditorAgent, ReviewerAgent
from .sandbox import Sandbox, SandboxedSkill
from .secure_box import SecureBox, SecurityReport, SecurityFinding
from .manager import FactoryManager

__all__ = [
    # Tickets
    "Ticket",
    "TicketStatus",
    "TicketPriority",
    "TicketType",
    # Routing
    "TicketRouter",
    "RoutingRule",
    # Agents
    "AgentBase",
    "FactoryEngineer",
    "SuperiorAgent",
    "InternalAgent",
    "BuilderAgent",
    "AuditorAgent",
    "ReviewerAgent",
    # Sandbox
    "Sandbox",
    "SandboxedSkill",
    # Security
    "SecureBox",
    "SecurityReport",
    "SecurityFinding",
    # Manager
    "FactoryManager",
]
