"""
MASTER Factory Manager
======================
The FactoryManager is the top-level orchestrator of the Factory.
It initializes all Factory components, starts the monitoring loop,
and exposes the API that Main Agent and Internal Agents use to interact
with the Factory.

The FactoryManager:
- Creates and wires: Engineer → Superior → Internals + SecureBox + Sandbox
- Runs the monitoring loop (health checks, auto-resets)
- Exposes: request_tool(), get_status(), get_tickets(), get_ticket()
- Handles notifications from Engineer back to the requesting agent

Communication rules (enforced by the FactoryManager):
- Main Agent → FactoryManager.request_tool() → Engineer
- Nobody talks to Internal Agents directly — only through the Engineer
- Engineer reports → FactoryManager → notifies Main Agent

Philosophy: "The factory floor is dangerous. Only the foreman has the keys."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import threading
import time

from .engineer import FactoryEngineer
from .superior import SuperiorAgent
from .sandbox import Sandbox
from .secure_box import SecureBox
from .ticket import Ticket, TicketStatus, TicketType, TicketPriority
from .router import TicketRouter


@dataclass
class FactoryManager:
    """
    Top-level Factory orchestrator.

    Usage:
        manager = FactoryManager()
        manager.start()
        ticket = manager.request_tool("my_tool", tool_code, requested_by="main_agent")
        status = manager.get_status()
        manager.stop()
    """

    name: str = "factory_manager"

    # ── Core components ──────────────────────────────────────────
    _engineer: Optional[FactoryEngineer] = None
    _superior: Optional[SuperiorAgent] = None
    _sandbox: Optional[Sandbox] = None
    _secure_box: Optional[SecureBox] = None
    _router: Optional[TicketRouter] = None

    # ── Transparency callback (set by TorreDeControl) ─────────────
    # Called at each pipeline step to show progress in Telegram
    _progress_cb: Optional[Callable[[str, dict], None]] = None

    # ── State ────────────────────────────────────────────────────
    started_at: Optional[datetime] = None
    running: bool = False

    # ── Monitoring ───────────────────────────────────────────────
    _monitor_thread: Optional[threading.Thread] = None
    monitor_interval: float = 5.0  # seconds between health checks

    # ── Notification callbacks ───────────────────────────────────
    # Called when a tool is released: callback(tool_name, ticket)
    on_tool_released: Optional[Callable[[str, Ticket], None]] = None
    # Called when a ticket is completed: callback(ticket)
    on_ticket_complete: Optional[Callable[[Ticket], None]] = None

    # ── History ──────────────────────────────────────────────────
    monitor_reports: List[Dict[str, Any]] = field(default_factory=list)
    notifications: List[Dict[str, Any]] = field(default_factory=list)

    # ────────────────────────────────────────────────────────────────
    # Setup
    # ────────────────────────────────────────────────────────────────

    def setup(self) -> None:
        """
        Initialize all Factory components and wire them together.

        Architecture:
            FactoryManager
                └── FactoryEngineer (the foreman)
                        ├── SecureBox (Caja Segura — security gateway)
                        ├── Sandbox (skill testing environment)
                        └── SuperiorAgent (bridge)
                                ├── BuilderAgent (internal — tools/code)
                                ├── AuditorAgent (internal — verification)
                                └── ReviewerAgent (internal — validation)
        """
        # ── Create the Caja Segura (security FIRST) ──
        self._secure_box = SecureBox(
            auto_clean=True,
            strict_mode=False,  # Clean by default, not reject
        )

        # ── Create the Sandbox ──
        self._sandbox = Sandbox()

        # ── Create the Superior Agent with its internal workers ──
        self._superior = SuperiorAgent()
        self._superior.set_sandbox(self._sandbox)
        self._superior.setup_default_internals()
        # Propagate transparency callback
        if self._progress_cb:
            self._superior._progress_cb = self._progress_cb

        # ── Create the Engineer — the foreman ──
        self._engineer = FactoryEngineer()
        self._engineer.set_superior(self._superior)
        self._engineer.set_sandbox(self._sandbox)
        self._engineer.set_secure_box(self._secure_box)

        # ── Wire notification callbacks ──
        self._engineer.set_notification_handler(
            on_tool_released=self._on_engineer_tool_released,
            on_ticket_complete=self._on_engineer_ticket_complete,
        )

        # ── Create the Ticket Router ──
        self._router = TicketRouter()

    def start(self, monitor: bool = True) -> None:
        """
        Start the Factory.

        Args:
            monitor: If True, start the background monitoring loop
        """
        if self._engineer is None:
            self.setup()

        self.running = True
        self.started_at = datetime.now()

        if monitor:
            self._start_monitoring()

    def stop(self) -> None:
        """Stop the Factory and the monitoring loop."""
        self.running = False
        if self._engineer:
            self._engineer.stop_monitoring()
        self._stop_monitoring()

    def is_healthy(self) -> bool:
        """Quick health check — is the Factory operational?"""
        if self._engineer is None:
            return False
        report = self._engineer.monitor()
        return report.get("engineer_health") != "critical"

    # ────────────────────────────────────────────────────────────────
    # API for Main Agent (the ONLY way to interact with the Factory)
    # ────────────────────────────────────────────────────────────────

    def request_tool(
        self,
        tool_name: str,
        tool_code: str,
        requested_by: str = "main_agent",
        description: str = "",
    ) -> Optional[Ticket]:
        """
        Main Agent requests a tool to be processed by the Factory.

        This is the primary API for Main Agent. The tool goes through:
        Caja Segura → Efficiency → Evolution → Agent Work → Release

        Returns the completed Ticket (the "Bible") or None if rejected.
        """
        if self._engineer is None:
            self.setup()

        if self._engineer is None:
            return None

        return self._engineer.process_tool(
            tool_name=tool_name,
            tool_code=tool_code,
            requested_by=requested_by,
            description=description,
        )

    def request_new_capability(
        self,
        capability_id: str,
        family: str,
        description: str = "",
        target_capabilities: Optional[List[str]] = None,
        target_limitations: Optional[List[str]] = None,
        activation_requirements: Optional[List[str]] = None,
        tool_name: str = "",
        requested_by: str = "agente",
    ) -> Optional[dict]:
        """
        Request a NEW capability to be built from scratch by the Factory.

        Unlike request_skill_upgrade (which modifies an existing skill),
        this creates a brand-new skill pipeline:
        1. Creates a specialized Builder agent for this capability
        2. Enters a new skill into the Sandbox with empty initial capabilities
        3. Routes through Builder→Auditor→Reviewer→Release
        4. Returns the Factory ticket + sandbox info

        capability_id: e.g., "stt_audio_input", "web_browsing"
        family: e.g., "VOICE", "WEB", "NEW_TOOL"
        description: human-readable description of the capability
        target_capabilities: list of capabilities the skill should have
        target_limitations: list of known limitations
        tool_name: name for the resulting tool
        requested_by: who requested this capability

        Returns: {ok, ticket_id, ticket_number, sandbox_id, agent_name, message}
        """
        if self._engineer is None:
            self.setup()

        if self._engineer is None or self._superior is None or self._sandbox is None:
            return {
                "ok": False,
                "ticket_id": None,
                "message": "Factory not initialized — setup failed.",
            }

        target_capabilities = target_capabilities or ["to_be_defined"]
        target_limitations = target_limitations or ["to_be_defined"]
        activation_requirements = activation_requirements or []
        requires_live_activation = bool(activation_requirements)
        factory_limitations = list(target_limitations)
        factory_limitations.extend(
            f"activation required: {item}"
            for item in activation_requirements
        )
        tool_name = tool_name or capability_id

        def _emit(step: str, detail: str = ""):
            """Emit progress to the transparency layer (Telegram)."""
            if self._progress_cb:
                try:
                    self._progress_cb("factory", {"step": step, "detail": detail})
                except Exception:
                    pass

        _emit("factory_start", f"Creando capacidad {family}: {capability_id}")

        # ── 1. Create a specialized Builder agent for this capability ──
        agent_name = f"{capability_id}_builder"
        _emit("creating_builder", agent_name)
        builder = self._superior.create_internal(
            agent_type="builder",
            mode="collaborative",
            name=agent_name,
            mission=f"Desarrollar capacidad {family}: {capability_id} — {description}",
        )
        if builder is None:
            _emit("error", f"No se pudo crear Builder '{agent_name}'")
            return {
                "ok": False,
                "ticket_id": None,
                "message": f"No se pudo crear el Builder '{agent_name}'.",
            }
        _emit("builder_created", agent_name)

        # ── 2. Create a Factory ticket for this new capability ──
        ticket = self._engineer.create_ticket(
            title=f"New capability: {capability_id}",
            description=description or f"Build new {family} capability: {capability_id}",
            ticket_type=TicketType.SKILL_REQUEST,
            priority=TicketPriority.MEDIUM,
            payload={
                "capability_id": capability_id,
                "family": family,
                "requested_by": requested_by,
                "target_capabilities": target_capabilities,
                "target_limitations": factory_limitations,
                "activation_requirements": activation_requirements,
                "activation_missing": list(activation_requirements),
                "requires_live_activation": requires_live_activation,
                "validation_required": True,
                "validation_passed": False,
                "closure_allowed": False,
                "pipeline_stage": "REGISTER",
                "pipeline_checkpoints": {
                    "REGISTER": "done",
                    "BUILD": "pending",
                    "VALIDATE": "pending",
                    "ACTIVATE": "pending",
                },
                "tool_name": tool_name,
                "builder_agent": agent_name,
            },
        )

        _emit("ticket_created", f"Ticket #{ticket.ticket_number}")

        # ── 3. Enter skill into Sandbox ──
        _emit("entering_sandbox", tool_name)
        sandboxed = self._superior.enter_skill_to_sandbox(
            skill_name=tool_name,
            description=description,
            capabilities=[],  # Start empty — Builder will fill in
            limitations=["not_implemented_yet"] + factory_limitations,
            ticket_id=ticket.id,
        )

        if sandboxed is None:
            _emit("error", "Failed to enter sandbox")
            ticket.payload["pipeline_stage"] = "BUILD"
            ticket.payload["pipeline_checkpoints"]["BUILD"] = "failed"
            ticket.block("Failed to enter sandbox")
            return {
                "ok": False,
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "sandbox_id": None,
                "agent_name": agent_name,
                "message": "Skill entered Sandbox but modification pipeline failed.",
            }

        _emit("sandbox_entered", f"Sandbox #{sandboxed.id}")

        # ── 4. Route modification through internal agents ──
        _emit("agent_pipeline", "Builder → Auditor → Reviewer")
        revision = self._superior.route_skill_modification(
            sandboxed.id,
            target_capabilities,
            factory_limitations,
        )

        if revision is None:
            _emit("error", "Agent pipeline failed")
            ticket.payload["pipeline_stage"] = "BUILD"
            ticket.payload["pipeline_checkpoints"]["BUILD"] = "failed"
            ticket.block("Skill modification pipeline failed")
            self._sandbox.reject_skill(sandboxed.id, "Could not modify — no agents available")
            return {
                "ok": False,
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "sandbox_id": sandboxed.id,
                "agent_name": agent_name,
                "message": f"Skill entered Sandbox (#{sandboxed.id}) but no agents could process it.",
            }

        _emit("pipeline_complete", f"Skill v{revision}")

        # ── 5. Promote the skill to "superior" + Release ──
        _emit("promoting", tool_name)
        if self._superior.promote_skill(sandboxed.id):
            ticket.checkmark_agent_work(
                True,
                agent_name,
                f"Builder/Auditor/Reviewer advanced '{tool_name}' to v{revision}.",
            )
            ticket.payload["pipeline_checkpoints"]["BUILD"] = "done"

            if requires_live_activation:
                ticket.mark_pending_activation(
                    "Factory build finished, but live-channel validation and activation are still required.",
                    missing=activation_requirements,
                )
                _emit("pending_activation", f"{tool_name} v{revision} — requiere validacion viva")
                return {
                    "ok": True,
                    "active": False,
                    "status": "pending_activation",
                    "ticket_id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "sandbox_id": sandboxed.id,
                    "agent_name": agent_name,
                    "revision": revision,
                    "tool_name": tool_name,
                    "activation_requirements": activation_requirements,
                    "activation_missing": activation_requirements,
                    "validation_required": True,
                    "closure_allowed": False,
                    "pipeline_stage": "ACTIVATE",
                    "pipeline_checkpoints": dict(ticket.payload["pipeline_checkpoints"]),
                    "message": (
                        f"Capacidad '{capability_id}' ({family}) avanzada por la Factoría, "
                        "pero el ticket sigue abierto. Falta conectar, validar y activar "
                        "la capacidad en el canal vivo antes de cerrarla."
                    ),
                }

            ticket.mark_active([f"Skill '{tool_name}' promoted to superior"])
            ticket.checkmark_released(True, f"Skill '{tool_name}' promoted to superior")
            ticket.resolve(f"New capability '{capability_id}' ({family}) built, validated, and promoted (v{revision})")
            ticket.close()
            self._engineer._record_completed_ticket(ticket)
            self._engineer.total_released += 1

            _emit("released", f"{tool_name} v{revision} — ✅")
            return {
                "ok": True,
                "active": True,
                "status": "active",
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "sandbox_id": sandboxed.id,
                "agent_name": agent_name,
                "revision": revision,
                "tool_name": tool_name,
                "activation_requirements": activation_requirements,
                "activation_missing": [],
                "validation_required": False,
                "closure_allowed": True,
                "pipeline_stage": "ACTIVATE",
                "pipeline_checkpoints": dict(ticket.payload["pipeline_checkpoints"]),
                "message": (
                    f"Capacidad '{capability_id}' ({family}) creada en la Factoría. "
                    f"Builder '{agent_name}' la procesó. "
                    f"Skill '{tool_name}' promovida (v{revision}). "
                    f"Ticket #{ticket.ticket_number}."
                ),
            }
        else:
            _emit("error", "Promotion failed")
            ticket.payload["pipeline_stage"] = "BUILD"
            ticket.payload["pipeline_checkpoints"]["BUILD"] = "done"
            ticket.payload["pipeline_checkpoints"]["VALIDATE"] = "failed"
            ticket.payload["pipeline_checkpoints"]["ACTIVATE"] = "blocked"
            ticket.block("Promotion failed — skill not verified")
            return {
                "ok": False,
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "sandbox_id": sandboxed.id,
                "agent_name": agent_name,
                "revision": revision,
                "message": f"Skill modificada (v{revision}) pero no se pudo promover.",
            }

    def request_skill_upgrade(
        self,
        skill_name: str,
        description: str,
        current_capabilities: List[str],
        current_limitations: List[str],
        new_capabilities: List[str],
        new_limitations: List[str],
    ) -> Optional[Ticket]:
        """
        Request a skill upgrade through the Factory.

        Goes through: Caja Segura → Sandbox → Agent modification → Release.
        Returns the associated Ticket or None if rejected.
        """
        if self._engineer is None:
            self.setup()

        if self._engineer is None:
            return None

        sandboxed = self._engineer.upgrade_skill(
            skill_name=skill_name,
            description=description,
            current_capabilities=current_capabilities,
            current_limitations=current_limitations,
            new_capabilities=new_capabilities,
            new_limitations=new_limitations,
        )

        # Find the ticket associated with this upgrade
        for ticket in reversed(self._engineer.all_tickets):
            if ticket.payload.get("skill_name") == skill_name:
                return ticket

        return None

    # ────────────────────────────────────────────────────────────────
    # Status & Reporting
    # ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get the full Factory status for Main Agent or CLI display."""
        if self._engineer is None:
            return {
                "factory": "not_initialized",
                "running": False,
                "tickets": 0,
            }

        engineer_status = self._engineer.get_status()
        return {
            "factory": "operational" if self.running else "stopped",
            "running": self.running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "engineer": engineer_status,
            "tickets": {
                "total_created": self._engineer._ticket_counter,
                "active": engineer_status.get("active_tickets", 0),
                "completed": engineer_status.get("completed", 0),
                "rejected": engineer_status.get("rejected", 0),
                "released": engineer_status.get("released", 0),
            },
            "security": self._secure_box.status() if self._secure_box else {},
            "monitoring": {
                "active": self._engineer._monitoring_active,
                "interval": self.monitor_interval,
                "reports": len(self.monitor_reports),
                "last_poll": engineer_status.get("last_poll"),
            },
        }

    def get_tickets(
        self,
        status: Optional[TicketStatus] = None,
        limit: int = 20,
    ) -> List[Ticket]:
        """
        Get tickets, optionally filtered by status.

        This is the API for Main Agent to query Factory activity.
        """
        if self._engineer is None:
            return []

        tickets = self._engineer.all_tickets

        if status:
            tickets = [t for t in tickets if t.status == status]

        # Most recent first
        sorted_tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)
        return sorted_tickets[:limit]

    def get_ticket(self, ticket_id: str) -> Optional[Ticket]:
        """Get a specific ticket by ID."""
        if self._engineer is None:
            return None
        for t in self._engineer.all_tickets:
            if t.id == ticket_id or (t.ticket_number and str(t.ticket_number) == ticket_id):
                return t
        return None

    def get_tickets_summary(self) -> str:
        """Human-readable tickets summary for CLI display."""
        if self._engineer is None:
            return "Factory not initialized."

        active = self.get_tickets(status=TicketStatus.OPEN) + \
                 self.get_tickets(status=TicketStatus.IN_PROGRESS) + \
                 self.get_tickets(status=TicketStatus.ASSIGNED) + \
                 self.get_tickets(status=TicketStatus.PENDING_VALIDATION) + \
                 self.get_tickets(status=TicketStatus.PENDING_ACTIVATION)
        completed = self.get_tickets(status=TicketStatus.CLOSED)

        lines = [f"🎫 Factory Tickets ({self._engineer._ticket_counter} total)"]
        lines.append(f"   Active: {len(active)} | Completed: {len(completed)}")

        for ticket in active[:5]:
            lines.append(f"   {ticket.summary()}")

        for ticket in completed[:3]:
            lines.append(f"   {ticket.summary()}")

        return "\n".join(lines)

    def summary(self) -> str:
        """Full human-readable Factory summary."""
        if self._engineer is None:
            return "🏭 Factory: not initialized"

        status = self.get_status()
        tickets = status["tickets"]

        lines = [
            "=" * 60,
            "🏭 MASTER FACTORY",
            "=" * 60,
            f"   Status: {'🟢 RUNNING' if self.running else '🔴 STOPPED'}",
            f"   Started: {status['started_at'] or 'N/A'}",
            "",
            "   📊 TICKETS:",
            f"      Created: {tickets['total_created']} | "
            f"Active: {tickets['active']} | "
            f"Completed: {tickets['completed']}",
            f"      Rejected: {tickets['rejected']} | "
            f"Released: {tickets['released']}",
            "",
        ]

        if self._engineer:
            lines.append(self._engineer.summary())

        if self._secure_box:
            lines.append("")
            lines.append(self._secure_box.summary())

        lines.append("=" * 60)
        return "\n".join(lines)

    # ────────────────────────────────────────────────────────────────
    # Notification handlers (internal)
    # ────────────────────────────────────────────────────────────────

    def _on_engineer_tool_released(self, tool_name: str, ticket: Ticket) -> None:
        """Called by the Engineer when a tool is released."""
        notification = {
            "type": "tool_released",
            "tool_name": tool_name,
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "timestamp": datetime.now().isoformat(),
        }
        self.notifications.append(notification)

        # Forward to external callback if set
        if self.on_tool_released:
            self.on_tool_released(tool_name, ticket)

        # Trim notifications
        if len(self.notifications) > 200:
            self.notifications = self.notifications[-200:]

    def _on_engineer_ticket_complete(self, ticket: Ticket) -> None:
        """Called by the Engineer when a ticket is fully completed."""
        notification = {
            "type": "ticket_complete",
            "ticket_id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "timestamp": datetime.now().isoformat(),
        }
        self.notifications.append(notification)

        if self.on_ticket_complete:
            self.on_ticket_complete(ticket)

    # ────────────────────────────────────────────────────────────────
    # Monitoring loop (background thread)
    # ────────────────────────────────────────────────────────────────

    def _start_monitoring(self) -> None:
        """Start the background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        if self._engineer:
            self._engineer.start_monitoring(int(self.monitor_interval))

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="factory-monitor",
        )
        self._monitor_thread.start()

    def _stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=self.monitor_interval * 2)

    def _monitor_loop(self) -> None:
        """Background loop: periodically check Factory health and auto-reset."""
        while self.running:
            try:
                if self._engineer:
                    report = self._engineer.monitor()
                    self.monitor_reports.append(report)

                    # Trim reports
                    if len(self.monitor_reports) > 200:
                        self.monitor_reports = self.monitor_reports[-200:]

                    # If Engineer itself is critical, log and attempt recovery
                    if report.get("engineer_health") == "critical":
                        self._attempt_engineer_recovery()

            except Exception as e:
                if self._engineer:
                    self._engineer.errors.append(f"Monitor error: {str(e)[:200]}")

            time.sleep(self.monitor_interval)

    def _attempt_engineer_recovery(self) -> None:
        """
        Attempt to recover a critical Engineer.
        Uses reset_critical_agents() for controlled recovery.
        """
        if self._engineer is None:
            return

        # Use the controlled reset method instead of manual clearing
        original_mission = self._engineer.mission
        self._engineer.reset_critical_agents()
        self._engineer.set_mission(original_mission)
