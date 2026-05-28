"""
MASTER Factory Superior Agent
==============================
The Superior Agent is the ONLY bridge between the Engineer
and the Internal Agents. No other communication path exists.

The Superior Agent:
- Receives tickets from the Engineer
- Distributes work to Internal Agents
- Moves skills in/out of the Sandbox
- Reports results back to the Engineer
- Has its own GPS + Self-Awareness

Philosophy: "The bridge does not judge. It connects, routes, and verifies."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import uuid

from .agent_base import AgentBase
from .internal import InternalAgent, BuilderAgent, AuditorAgent, ReviewerAgent
from .sandbox import Sandbox, SandboxedSkill
from .ticket import Ticket, TicketType, TicketStatus, TicketPriority

from skills.capability import CapabilityCard, CapabilityStatus


@dataclass
class SuperiorAgent(AgentBase):
    """
    The Superior Agent — exclusive bridge Engineer ↔ Internal Agents.

    Communication rules:
    - Engineer speaks to Superior Agent ✅
    - Superior Agent speaks to Internal Agents ✅
    - Engineer NEVER speaks to Internal Agents ❌
    - Internal Agents NEVER speak to Engineer ❌
    """

    # ── Internal agents managed by this Superior Agent ──
    internal_agents: Dict[str, InternalAgent] = field(default_factory=dict)
    _sandbox: Optional[Sandbox] = None

    # ── Transparency callback (set by FactoryManager) ───────────
    # Called at each internal agent step to show progress in Telegram
    _progress_cb: Optional[Callable[[str, dict], None]] = None

    # ── Ticket routing ──
    pending_tickets: List[Ticket] = field(default_factory=list)
    routed_tickets: Dict[str, str] = field(default_factory=dict)  # ticket_id → agent_name

    # ── Skill flow ──
    skills_in_sandbox: List[str] = field(default_factory=list)  # sandbox skill IDs
    skills_promoted: List[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        self.name = "superior_agent"
        self.role = "superior"
        self.description = "Bridge between Engineer and Internal Agents"
        self.set_mission("Route work efficiently and maintain the communication chain")

    # ── Internal Agent Management ────────────────────────────────────

    def register_internal(self, agent: InternalAgent) -> None:
        """Register an internal agent under this Superior Agent."""
        agent.set_sandbox(self._sandbox) if self._sandbox else None
        self.internal_agents[agent.name] = agent

    def create_internal(
        self,
        agent_type: str,
        mode: str = "collaborative",
        name: str = "",
        mission: str = "",
    ) -> Optional[InternalAgent]:
        """Create an internal agent with the specified mode.

        agent_type: 'builder' | 'auditor' | 'reviewer'
        mode: ☑️ 'collaborative' (conoce hermanos, usa MessageBus)
              ☑️ 'isolated'     (solo ve a SuperiorAgent + Tower)
        name: optional custom name (auto-generated if empty)
        mission: optional custom mission

        Returns the created InternalAgent or None if type unknown.
        """
        agent_map = {
            "builder": BuilderAgent,
            "auditor": AuditorAgent,
            "reviewer": ReviewerAgent,
        }
        agent_class = agent_map.get(agent_type)
        if agent_class is None:
            return None

        agent = agent_class(mode=mode)
        if name:
            agent.name = name
        if mission:
            agent.set_mission(mission)
        self.register_internal(agent)
        return agent

    def get_internal(self, name: str) -> Optional[InternalAgent]:
        """Get an internal agent by name."""
        return self.internal_agents.get(name)

    def setup_default_internals(self) -> None:
        """Create and register the three default internal agents (collaborative mode)."""
        self.create_internal("builder", mode="collaborative")
        self.create_internal("auditor", mode="collaborative")
        self.create_internal("reviewer", mode="collaborative")

    # ── Sandbox Management ───────────────────────────────────────────

    def set_sandbox(self, sandbox: Sandbox) -> None:
        """Set the sandbox and propagate to all internal agents."""
        self._sandbox = sandbox
        for agent in self.internal_agents.values():
            agent.set_sandbox(sandbox)

    def enter_skill_to_sandbox(
        self,
        skill_name: str,
        description: str,
        capabilities: List[str],
        limitations: List[str],
        ticket_id: Optional[str] = None,
    ) -> Optional[SandboxedSkill]:
        """Enter a skill into the sandbox (called by Engineer via Superior Agent)."""
        if self._sandbox is None:
            return None

        nav = self.check_course(f"Enter skill '{skill_name}' to sandbox")
        if nav.recommendation == "abort":
            self.errors.append(
                f"GPS warning while entering sandbox; proceeding under FactoryManager authority: {skill_name}"
            )

        skill = self._sandbox.enter(
            skill_name=skill_name,
            description=description,
            capabilities=capabilities,
            limitations=limitations,
            ticket_id=ticket_id,
        )
        self.skills_in_sandbox.append(skill.id)
        return skill

    def route_skill_modification(
        self,
        sandbox_skill_id: str,
        new_capabilities: List[str],
        new_limitations: List[str],
    ) -> Optional[int]:
        """
        Route a skill modification through the internal agents:
        Builder modifies → Auditor verifies → Reviewer validates.
        Returns the new revision number or None if any step fails.
        """
        if self._sandbox is None:
            return None

        def _emit(step: str, detail: str = ""):
            if self._progress_cb:
                try:
                    self._progress_cb("factory_internal", {"step": step, "detail": detail})
                except Exception:
                    pass

        skill = self._sandbox.get_skill(sandbox_skill_id)
        if skill is None:
            return None

        # STEP 1: Builder modifies
        _emit("builder_start", f"Builder modificando {skill.skill_name}")
        builder = self.internal_agents.get("internal_builder")
        if builder and builder.accept_task(f"Modify skill {skill.skill_name}"):
            rev = self._sandbox.modify_skill(
                sandbox_skill_id,
                new_capabilities,
                new_limitations,
                changed_by="internal_builder",
                reason="Routine skill upgrade",
            )
            builder.complete_task(f"Modified skill {skill.skill_name} to v{rev}")
            if rev is None:
                _emit("builder_fail", skill.skill_name)
                return None
            _emit("builder_done", f"{skill.skill_name} → v{rev}")
        else:
            _emit("error", "Builder not available")
            return None

        # STEP 2: Auditor verifies
        _emit("auditor_start", f"Auditor verificando {skill.skill_name}")
        auditor = self.internal_agents.get("internal_auditor")
        if auditor and auditor.accept_task(f"Audit skill {skill.skill_name}"):
            is_better = skill.is_better_than_original()
            self._sandbox.verify_skill(
                sandbox_skill_id,
                passed=is_better,
                findings="Skill improved" if is_better else "No improvement detected",
            )
            auditor.complete_task(f"Audited skill {skill.skill_name}: {'PASS' if is_better else 'FAIL'}")

            # Observe patterns for auto-skill generation
            auditor.observe_pattern({
                "category": "skill_audit",
                "capabilities": new_capabilities,
                "limitations": new_limitations,
                "result": "pass" if is_better else "fail",
            })
            _emit("auditor_done", f"{'✅ PASS' if is_better else '⚠️ FAIL'}")
        else:
            _emit("error", "Auditor not available")
            return None

        # STEP 3: Reviewer validates
        _emit("reviewer_start", f"Reviewer validando {skill.skill_name}")
        reviewer = self.internal_agents.get("internal_reviewer")
        if reviewer and reviewer.accept_task(f"Review skill {skill.skill_name}"):
            reviewer.complete_task(f"Reviewed skill {skill.skill_name}")

            # Observe patterns for auto-skill generation
            reviewer.observe_pattern({
                "category": "skill_review",
                "capabilities": new_capabilities,
                "limitations": new_limitations,
                "result": "pass",
            })
            _emit("reviewer_done", f"{skill.skill_name} ✅")
        else:
            _emit("error", "Reviewer not available")
            return None

        return skill.revision

    def promote_skill(self, sandbox_skill_id: str) -> bool:
        """Promote a verified skill to 'superior' status."""
        if self._sandbox is None:
            return False

        result = self._sandbox.promote_skill(sandbox_skill_id)
        if result:
            if sandbox_skill_id in self.skills_in_sandbox:
                self.skills_in_sandbox.remove(sandbox_skill_id)
                self.skills_promoted.append(sandbox_skill_id)
        return result

    # ── Ticket Routing ───────────────────────────────────────────────

    def receive_ticket(self, ticket: Ticket) -> bool:
        """Receive a ticket from the Engineer."""
        nav = self.check_course(f"Receive ticket: {ticket.title}")
        if nav.recommendation == "abort":
            return False

        self.pending_tickets.append(ticket)
        return True

    def route_ticket(self, ticket: Ticket, internal_agent_name: str) -> bool:
        """Route a ticket to a specific internal agent."""
        agent = self.internal_agents.get(internal_agent_name)
        if agent is None:
            return False

        if agent.accept_task(ticket.description, ticket):
            self.routed_tickets[ticket.id] = internal_agent_name
            if ticket in self.pending_tickets:
                self.pending_tickets.remove(ticket)
            return True
        return False

    def auto_route(self, ticket: Ticket) -> Optional[str]:
        """Auto-route a ticket based on its type."""
        routing_map = {
            TicketType.TOOL_REQUEST: "internal_builder",
            TicketType.TOOL_FIX: "internal_builder",
            TicketType.INFRASTRUCTURE: "internal_builder",
            TicketType.DEPENDENCY: "internal_auditor",
            TicketType.SKILL_REQUEST: "internal_builder",
            TicketType.SKILL_UPGRADE: "internal_builder",
            TicketType.SKILL_GENERATED: "internal_reviewer",
            TicketType.AUDIT_REQUEST: "internal_auditor",
            TicketType.CONFIG: "internal_reviewer",
            TicketType.MAINTENANCE: "internal_builder",
            # RETRIEVE_FRAGMENT handled when privacy vault is built
        }

        target = routing_map.get(ticket.ticket_type, "internal_builder")
        if self.route_ticket(ticket, target):
            return target
        self.errors.append(f"Failed to auto-route ticket {ticket.ticket_number}: {ticket.title}")
        return None

    # ── Collect auto-generated skills from internals ─────────────────

    def collect_generated_skills(self) -> List[CapabilityCard]:
        """Collect all auto-generated skills from internal agents."""
        all_skills = []
        for agent in self.internal_agents.values():
            all_skills.extend(agent.get_pending_skills())
        return all_skills

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get extended status for the Superior Agent."""
        base = super().get_status()
        internal_statuses = {
            name: agent.get_status()
            for name, agent in self.internal_agents.items()
        }
        base.update({
            "internal_agents": len(self.internal_agents),
            "internal_statuses": internal_statuses,
            "pending_tickets": len(self.pending_tickets),
            "routed_tickets": len(self.routed_tickets),
            "skills_in_sandbox": len(self.skills_in_sandbox),
            "skills_promoted": len(self.skills_promoted),
            "generated_skills_pending": len(self.collect_generated_skills()),
        })
        return base

    def summary(self) -> str:
        """Human-readable Superior Agent summary."""
        base = super().summary()
        lines = [base]
        lines.append(f"   Internals: {len(self.internal_agents)} | "
                     f"Pending tickets: {len(self.pending_tickets)} | "
                     f"Routed: {len(self.routed_tickets)}")
        lines.append(f"   Sandbox: {len(self.skills_in_sandbox)} active | "
                     f"Promoted: {len(self.skills_promoted)}")
        for name, agent in self.internal_agents.items():
            gps_status = agent.summary_gps()
            lines.append(f"   ├─ {gps_status}")
        return "\n".join(lines)
