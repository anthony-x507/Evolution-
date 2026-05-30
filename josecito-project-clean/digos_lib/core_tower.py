"""DIGOS Control Tower — Principal orchestrator."""
import json
import os
import select
import sys
import time
import signal
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

from digos_lib.constants import (
    VERSION, DIGOS_DIR, STATE_FILE, KEY_FILE, LOG_DIR,
    STRIKES_FILE, SELF_FILE, VAULT_FILE,
    LANGUAGES, PROVIDERS, GATEWAYS,
    SYSTEM_IDENTITY, IDENTITY_RESPONSES,
    CENTINELA_INTERVAL, STRIKE_LIMIT,
    SYSTEM_NAME, SYSTEM_VERSION,
)
from digos_lib.provider_api import _provider_api_request
from digos_lib.core_models import AgenteRecord, DigosState, Ticket
from digos_lib.core_vault import CajaSeguraInfo
from digos_lib.core_log import LogKeeper
from digos_lib.core_centinela import Centinela
from digos_lib.core_engineer import SystemEngineer
from digos_lib.core_self import SelfAwarenessCore
from digos_lib.core_gateways import BaseGateway
from digos_lib.gateway_manager import GatewayManager
from digos_lib.knowledge_base import KnowledgeBase
from digos_lib.onboarding import OnboardingFlow
from digos_lib.dream_cycle import DreamCycle
from digos_lib.factory_status import FactoryStatusStore
from digos_lib.internal_clock import InternalClock

from adoption import AdoptionEngine, TransformationEngine
from security import CajaSegura as SecurityCaja, CajaSeguraReport as SecurityReport
from bus import MessageBus

# ─────────────────────────────────────────────
# TORRE DE CONTROL — la entidad ÚNICA
# ─────────────────────────────────────────────

class TorreDeControl:
    """Control Tower is born first. Guides the entire onboarding.
    Contains Safe Box and TOWER (self-preservation).
    Can live 24/7 as a daemon.

    SYSTEM POLICY — Operations protected by level:
    🔴 RED: Permanently prohibited (damages the ecosystem)
    🟡 YELLOW: Requires Engineer authorization with ticket
    🟢 GREEN: Permitted without restriction
    """

    # 🔴 RED — Operations NO ONE can do, not even the user
    FORBIDDEN_OPERATIONS = {
        "delete_provider": "Cannot delete system providers.",
        "change_provider": "Cannot change active providers.",
        "disconnect_gateway": "Cannot disconnect communication gateways.",
        "delete_gateway_token": "Cannot delete gateway tokens.",
        "delete_gps": "Cannot delete GPS from the system.",
        "delete_safety_candle": "Cannot delete Safety Candle.",
        "delete_self_awareness": "Cannot delete Self-Awareness.",
        "delete_work_destination": "Cannot delete Work Destination.",
        "delete_ticket_system": "Cannot delete the ticket system.",
        "delete_core_structure": "Cannot delete the core structure.",
        "delete_system_md": "Cannot delete system configuration files.",
        "delete_engineer": "Cannot delete the System Engineer.",
        "delete_caja_segura": "Cannot delete the security vault.",
        "delete_internal_operation": "Cannot delete internal Control Tower components.",
        "delete_principal_agent": "Cannot delete the Principal Agent. It is part of the ecosystem.",
    }

    FORBIDDEN_PATTERNS = [
        # Operating system files (not user-owned)
        "/etc/shadow", "/etc/passwd", "/etc/sudoers",
        "/etc/ssh/", "/proc/", "/sys/",
    ]

    ALLOWED_READ_PATHS = [
        str(DIGOS_DIR),          # ~/.digos/ — system config
        str(Path.home() / "josecito-project"),  # project root
        str(Path.home() / "Desktop"),           # Desktop files
        "/tmp",                  # temp files
    ]

    # 🟡 AMARILLO — Operaciones que requieren ticket del Engineer
    SENSITIVE_OPERATIONS = {
        "change_api_key": "Change API key. A ticket will be created explaining the procedure.",
        "change_telegram_token": "Change Telegram token. Authorization required.",
        "modify_gateway": "Modify gateway configuration. Review required.",
        "modify_profile": "Modify agent profile. Review required.",
        "delete_agent": "Delete an internal agent. Data verification required.",
        "delete_agent_data": "Delete agent data. Verification required.",
        "delete_user_data": "Delete user information. Confirmation required.",
    }

    def __init__(self, daemon_mode: bool = False):
        self._ensure_dirs()
        self.state = self._load_state()
        self.lang = self.state.get("language", "en")

        # Authorized Telegram chats (loaded from state, defaults to owner)
        self._authorized_chats: set = set(
            self.state.get("authorized_chats", ["8123240885"])
        )

        # TOWER: self-preservation components
        self._log = LogKeeper()
        self._self_awareness = SelfAwarenessCore(self._log)
        self._engineer = SystemEngineer(self._log)
        self._centinela = Centinela(self._log, engineer=self._engineer)

        # Engine: GPS + Self + Work to govern the flow
        self._engine = None

        # Phase 3: Gateways — now managed by GatewayManager
        self._gateway_mgr = GatewayManager(self._log, daemon_mode)
        self._gateway_mgr.set_state_ref(self.state)

        # Phase 4: Transparency — tracker de progreso (managed by GatewayManager)

        # Phase 4b: AIAgent — LLM + tool calling
        self._agent: Optional[AIAgent] = None

        # Phase 9: Knowledge Base — AgentInfra structured knowledge
        self._knowledge: Optional[KnowledgeBase] = None

        # Phase 10: Dream Cycle — nightly self-improvement
        self._dream: Optional[DreamCycle] = None

        # Phase 6: Message Bus — multi-agent communication
        self._bus: Optional[MessageBus] = None

        # Phase 8: Factory — internal agent creation
        self._factory_manager = None
        self._superior_agent = None
        self._factory_status = FactoryStatusStore()
        self._clock = InternalClock()

        self._daemon_mode = daemon_mode
        self._running = False
        self._cycle_count = 0

        if daemon_mode:
            self._self_awareness.activate()

    def _ensure_dirs(self):
        DIGOS_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        (DIGOS_DIR / "profiles").mkdir(parents=True, exist_ok=True)
        (DIGOS_DIR / "imported").mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, ValueError):
                pass
        return {"setup_complete": False, "version": VERSION}

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    # ── RUN ──

    def _ui_text(self, en: str, es: str) -> str:
        return es if self.state.get("language", self.lang) == "es" else en

    def _active_language(self) -> str:
        """Return the current product language and keep tower state aligned."""
        lang = self.state.get("language") or self.lang or "es"
        self.lang = lang
        return lang

    def _start_clock_session(self):
        """Start the local timeline session without using tickets or model tokens."""
        try:
            self._clock.start_session(metadata={
                "language": self._active_language(),
                "setup_complete": bool(self.state.get("setup_complete")),
            })
        except Exception as e:
            self._log.info("clock", f"Internal clock unavailable: {e}")

    def _end_clock_session(self):
        try:
            self._clock.end_session()
        except Exception as e:
            self._log.info("clock", f"Internal clock end failed: {e}")

    def _record_timeline_event(
        self,
        role: str,
        summary: str,
        bullet_points: Optional[List[str]] = None,
        event_type: str = "conversation",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        try:
            return self._clock.record(
                role=role,
                summary=summary,
                bullet_points=bullet_points or [],
                event_type=event_type,
                metadata=metadata or {},
            )
        except Exception as e:
            self._log.info("clock", f"Timeline event skipped: {e}")
            return None

    def _temporal_context_for_agent(self, message: str = "", language: str = "es") -> str:
        try:
            return self._clock.context_card(message=message, language=language or self._active_language())
        except Exception as e:
            self._log.info("clock", f"Temporal context unavailable: {e}")
            return ""

    def _capability_public_followup_note(self, capability: str, family: str) -> str:
        """Clean user-facing note when a capability needs ticket follow-up."""
        fam = str(family or "").upper()
        if fam == "VOICE" or capability == "stt_audio_input":
            return (
                "La solicitud sigue abierta. La Factoría avanzó la capacidad, pero "
                "todavía no está activa en Telegram. Falta conectar la voz al canal "
                "de Telegram y completar una prueba de punta a punta antes de cerrarla. "
                "Hasta que eso quede validado, seguimos por texto."
            )
        if fam == "WEB" or capability in {"telegram_web_search", "web_search", "web_browsing"}:
            return (
                "La solicitud sigue abierta. La Factoría avanzó la capacidad, pero "
                "todavía no está activa en Telegram. Falta conectar la búsqueda web "
                "al canal de Telegram y validar una búsqueda permitida y una bloqueada. "
                "Hasta que eso quede validado, seguimos por texto."
            )
        if fam == "VISION" or capability == "vision_image_input":
            return (
                "La solicitud sigue abierta. La Factoría avanzó la capacidad, pero "
                "todavía no está activa en Telegram. Falta conectar imágenes de Telegram, "
                "análisis visual y respuesta gobernada con una prueba de punta a punta. "
                "Hasta que eso quede validado, seguimos por texto."
            )
        return (
            "La solicitud sigue abierta. Falta completar la conexión al canal vivo "
            "y validar la capacidad antes de cerrarla."
        )

    def _open_capability_followup(
        self,
        *,
        audit_profile: str,
        audit_ticket_id: str,
        capability: str,
        family: str,
        user_message: str,
        missing: Optional[List[str]] = None,
        next_action: str = "",
        force_user_update: bool = False,
    ) -> dict:
        """Open the persistent Principal Agent ↔ Engineer follow-up for a ticket."""
        if not audit_ticket_id:
            return {}
        public_note = self._capability_public_followup_note(capability, family)
        followup = self._engineer.coordinate_capability_followup(
            audit_profile,
            audit_ticket_id,
            capability=capability,
            family=family,
            user_message=user_message,
            missing=missing or [],
            next_action=next_action,
            public_note=public_note,
            force_user_update=force_user_update,
        )
        if followup.get("ok"):
            self._record_timeline_event(
                role="factory",
                summary=f"seguimiento persistente abierto: {capability}",
                bullet_points=[
                    f"ticket: {audit_ticket_id}",
                    followup.get("thread_status", ""),
                ],
                event_type="factory.ticket.followup",
                metadata={"capability": capability, "audit_ticket_id": audit_ticket_id},
            )
        return followup

    def report_factory_followup_issue(
        self,
        user_message: str,
        capability: str = "",
        requester: str = "agente",
    ) -> dict:
        """Attach a user-reported issue to the existing Factory ticket thread."""
        record = self._factory_status.latest(capability)
        if not record:
            return {
                "ok": False,
                "needs_clarification": True,
                "user_status": (
                    "No encontré una solicitud abierta para actualizar. "
                    "Dime si es voz, búsqueda web o visión."
                ),
            }

        cap = record.get("capability", capability or "")
        family = str(record.get("family", "") or "").upper()
        audit_profile = record.get("audit_profile") or requester or "agente"
        audit_ticket_id = record.get("audit_ticket_id", "")
        if not cap or not audit_ticket_id:
            return {
                "ok": False,
                "needs_clarification": False,
                "user_status": (
                    "Veo la solicitud, pero no encontré un ticket interno válido "
                    "para actualizar. Debe revisarse antes de cerrarla."
                ),
            }

        missing = (
            record.get("activation_missing")
            or record.get("activation_requirements")
            or ["User reported live-channel validation is failing."]
        )
        next_action = (
            record.get("next_step")
            or "revisar el reporte del usuario, completar VALIDATE y activar antes de cerrar."
        )
        followup_note = (
            f"User follow-up from Telegram: {user_message}. "
            "Treat this as evidence that the live capability is not complete. "
            "Do not close the ticket until the channel connection and final validation pass."
        )
        self._engineer.add_note(audit_profile, audit_ticket_id, followup_note)
        self._engineer.update_status(audit_profile, audit_ticket_id, "pending_validation")
        engineer_followup = self._open_capability_followup(
            audit_profile=audit_profile,
            audit_ticket_id=audit_ticket_id,
            capability=cap,
            family=family,
            user_message=followup_note,
            missing=missing,
            next_action=next_action,
            force_user_update=True,
        )
        self._factory_status.upsert_capability(
            cap,
            family=family,
            user_message=user_message,
            status="pending_validation",
            audit_ticket_id=audit_ticket_id,
            audit_profile=audit_profile,
            requester=record.get("requester", requester),
            factory_ticket_number=record.get("factory_ticket_number", ""),
            tool_name=record.get("tool_name", ""),
            active=False,
            responsibilities=record.get("responsibilities", {}),
            activation_requirements=record.get("activation_requirements", []),
            activation_missing=missing,
            pipeline_stage=record.get("pipeline_stage", "VALIDATE"),
            pipeline_checkpoints=record.get("pipeline_checkpoints", {}),
            next_step=next_action,
            engineer_followup=engineer_followup or None,
            note="User reported the capability is still incomplete from Telegram.",
        )
        self._record_timeline_event(
            role="factory",
            summary=f"actualizacion de seguimiento: {cap}",
            bullet_points=[f"ticket: {audit_ticket_id}", "usuario reporto incompleto"],
            event_type="factory.ticket.followup_update",
            metadata={"capability": cap, "audit_ticket_id": audit_ticket_id},
        )
        return {
            "ok": True,
            "capability": cap,
            "ticket_id": audit_ticket_id,
            "thread_id": engineer_followup.get("thread_id", ""),
            "user_status": self._factory_status.public_summary(
                cap,
                language=self._active_language(),
            ),
        }

    def run(self):
        if self._daemon_mode:
            self._run_daemon()
            return

        if self.state.get("setup_complete"):
            print(self._ui_text(
                "\n✅ System is already configured. Starting agent...",
                "\n✅ El sistema ya está configurado. Iniciando agente...",
            ))
            self._handoff()
        else:
            # Delegate onboarding to OnboardingFlow
            flow = OnboardingFlow(self)
            flow.start()
            # After onboarding, the tower's state is updated
            self._handoff()

    # ── BANNER ──

    def _handoff(self):
        """Handoff: initializes components and starts the agent.
        Called after onboarding is complete."""
        print(self._ui_text(
            "\n  🚀 Initializing system components...",
            "\n  🚀 Iniciando componentes del sistema...",
        ))
        self._self_awareness.activate()
        self._start_clock_session()
        self._gateway_mgr.init_gateways()
        self._init_bus()
        self._init_agent()
        self._schedule_nightly_cycle()

        if not self._daemon_mode and self.state.get("setup_complete") and sys.stdin.isatty():
            question = self._ui_text("  Start 24/7 mode?", "  ¿Iniciar modo 24/7?")
            if self._confirm_yn(question):
                print(self._ui_text("\n  🚀 Starting daemon mode...", "\n  🚀 Iniciando modo 24/7..."))
                self._daemon_mode = True
                self._running = True
                self._run_daemon()
            else:
                self._start_interactive()
        else:
            print(self._ui_text(
                "  Use: digos --daemon for 24/7 mode",
                "  Usa: digos --daemon para el modo 24/7",
            ))
            print()

    def _confirm_yn(self, question: str, default: bool = True) -> bool:
        """Simple yes/no confirmation."""
        if self.state.get("language", self.lang) == "es":
            prompt = " (S/n): " if default else " (s/N): "
        else:
            prompt = " (Y/n): " if default else " (y/N): "
        raw = input(question + prompt).strip().lower()
        if not raw:
            return default
        return raw in ("y", "yes", "s", "si", "sí")

    # ── POLÍTICA DEL SISTEMA ─────────────────

    def _check_operation(self, tool_name: str, args: dict) -> dict:
        """Evaluates an operation against the system policy.
        Returns dict with level and explanation.

        🔴 ROJO: permanently prohibited — even the user cannot do it
        🟡 AMARILLO: requires Engineer ticket
        🟢 VERDE: permitted
        """
        file_path = ""
        if tool_name in ("write_file", "read_file"):
            file_path = args.get("path", "")

        # Terminal con comandos destructivos
        if tool_name == "terminal":
            cmd = args.get("command", "").lower()
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in cmd:
                    return {"level": "red", "reason":
                        f"Prohibited: affects protected files ({pattern}).",
                        "explanation": "This operation would damage the system ecosystem. "
                                       "Cannot be executed under any circumstances."}

        # Paths prohibidos en operaciones de archivo
        if file_path:
            for pattern in self.FORBIDDEN_PATTERNS:
                if pattern in file_path:
                    return {"level": "red", "reason":
                        f"Prohibited: {file_path} contains '{pattern}'.",
                        "explanation": "This file or directory is part of the system core. "
                                       "Cannot be modified or deleted."}

            # read_file allowlist — solo ciertos directorios permitidos
            if tool_name == "read_file":
                resolved_path = Path(file_path).expanduser().resolve()
                allowed = False
                for ap in self.ALLOWED_READ_PATHS:
                    allowed_path = Path(ap).expanduser().resolve()
                    if resolved_path == allowed_path or allowed_path in resolved_path.parents:
                        allowed = True
                        break
                if not allowed:
                    return {"level": "red", "reason":
                        f"read_file not allowed for: {file_path}",
                        "explanation": "Only approved user/project folders can be read."}

            # Escribir en DIGOS_DIR prohibido
            if tool_name == "write_file" and str(DIGOS_DIR) in file_path:
                return {"level": "red", "reason":
                    f"Cannot write to {DIGOS_DIR}.",
                    "explanation": "System configuration files are protected."}

        # YELLOW: sensitive operations create ticket and BLOCK
        if tool_name in ("write_file", "terminal", "execute_code"):
            tid = ""
            if hasattr(self, '_engineer') and self._engineer:
                tid = self._engineer.create_ticket(
                    "system", f"tool:{tool_name}",
                    f"Sensitive operation needs approval: {tool_name} args={str(args)[:100]}",
                    "medium", source="control_tower")
                self._log.info("torre", f"Ticket #{tid} created (PENDING) for: {tool_name}")
            return {"level": "pending", "reason":
                f"Sensitive operation: {tool_name}. Requires Engineer approval.",
                "explanation": f"Ticket #{tid} created with pending status. "
                               "When the Engineer approves it, you can try again.",
                "ticket_id": tid}

        return {"level": "green", "reason": ""}

    def _approval_callback(self, tool_name: str, args: dict) -> bool:

        result = self._check_operation(tool_name, args)
        if result["level"] == "red":
            msg = f"⛔ {result['explanation']}"

            if self._gateway_mgr:
                self._gateway_mgr.emit_assistant_message(msg)
            return False
        if result["level"] == "pending":
            msg = f"⏳ {result['explanation']}"

            if self._gateway_mgr:
                self._gateway_mgr.emit_assistant_message(msg)
            return False
        return True

    def _start_interactive(self):
        """Modo interactivo CLI — agente iniciado sin daemon.
        Inicializa el agente y entra en un loop de chat."""
        self._running = True
        self._self_awareness.activate()
        self._start_clock_session()

        # Telegram gateway (si hay token)
        vault = CajaSeguraInfo.read_slot("principal")
        if vault:
            gw_token = vault.get("gateway_token", "")
            if gw_token:
                tg = GatewayTelegram(gw_token)
                tg.set_logger(self._log)
                self.register_gateway(tg)
                tg.start()

        self._init_bus()
        self._init_agent()

        if self._agent is None:
            print("  ⚠️  No se pudo iniciar el agente. Verifica tus credenciales.")
            self._running = False
            return

        print()
        print("  🖥️  Modo interactivo iniciado.")
        print("  Escribe tus mensajes. 'exit' o 'quit' para salir.")
        print()

        while self._running:
            try:
                # Poll Telegram for incoming messages
                self._poll_gateways()

                # Show prompt before waiting for input
                sys.stdout.write("→ ")
                sys.stdout.flush()

                # Non-blocking check for stdin input (2s timeout)
                ready, _, _ = select.select([sys.stdin], [], [], 2.0)
                if not ready:
                    continue

                user_input = sys.stdin.readline().strip()
                if user_input.lower() in ("exit", "quit", "salir"):
                    self._running = False
                    break
                if not user_input:
                    continue

                response = self._agent.process_message(user_input)
                print(f"\n{response}\n")
            except (EOFError, KeyboardInterrupt):
                self._running = False
                print()

        # Cleanup
        self._gateway_mgr.stop_all()
        if self._bus:
            try:
                self._bus.stop()
            except Exception:
                pass
        self._self_awareness.pause()
        self._end_clock_session()
        print("  👋 Goodbye!")
        print()

    # ── DAEMON MODE ──

    def _run_daemon(self):
        """Modo daemon: Torre de Control vive 24/7 con TORRE activa."""
        self._running = True
        self._self_awareness.activate()
        self._start_clock_session()

        # Initialize Phase 3 gateways (only if not already initialized)
        self._gateway_mgr.init_gateways()

        # Initialize Phase 6 Message Bus (only if not already initialized)
        if self._bus is None:
            self._init_bus()

        # Initialize Phase 4b: AIAgent (only if not already initialized)
        if self._agent is None:
            self._init_agent()

        # Schedule nightly Dream Cycle
        self._schedule_nightly_cycle()

        # Handle SIGTERM/SIGINT for clean shutdown
        # (ANTES de _ensure_launchd para capturar interrupciones)
        def _handle_signal(sig, frame):
            self._running = False

            # Detener gateways
            self._gateway_mgr.stop_all()
            # Detener Message Bus
            if self._bus:
                try:
                    self._bus.stop()
                except Exception:
                    pass
            self._self_awareness.pause()
            self._end_clock_session()

        signal.signal(signal.SIGTERM, _handle_signal)
        signal.signal(signal.SIGINT, _handle_signal)

        # Auto-launch: ensure DIGOS lives 24/7 (after signal handlers)
        self._ensure_launchd()

        print(f"\n  🏗️  TORRE DAEMON — v{VERSION}")
        print("  ─────────────────────────────")
        print(f"  Centinela: cada {CENTINELA_INTERVAL}s")
        print(f"  Logs:      {LOG_DIR}")
        print(f"  Estado:    {self._self_awareness.state}")
        print()


        self._log.info("torre", {"interval": CENTINELA_INTERVAL})

        while self._running:
            try:
                self._cycle_count += 1
                self._log.info("torre", f"Ciclo #{self._cycle_count}")

                # 1. Centinela: revisa API keys y tokens
                self._centinela_cycle()

                # 2. Gateway health check
                self._gateway_health_check()

                # 3. Engineer: processes pending reports
                self._engineer_cycle()

                # 4. Poll gateways for incoming messages (every 2s)
                for _ in range(CENTINELA_INTERVAL // 2):
                    if not self._running:
                        break
                    self._poll_gateways()
                    time.sleep(2)

            except Exception as e:

                self._self_awareness.set_error()
                time.sleep(10)

        self._self_awareness.pause()
        self._end_clock_session()


    def _centinela_cycle(self):
        """One cycle of Centinela checks. Also triggers nightly Dream Cycle."""
        factory_reports = self._centinela.review_factory_orchestra(
            self._factory_status._read()
        )
        for report in factory_reports:
            self._log.warn(
                "centinela",
                f"Factory orchestra watch: {report['capability']} — {report['reason']}",
                {"ticket": report.get("ticket_id", "")},
            )

        vault = CajaSeguraInfo.read_slot("principal")
        if not vault:
            self._log.info("centinela", "No hay slot principal — saltando checks")
            return

        api_key = vault.get("api_key", "")
        provider_id = vault.get("provider_id", "")
        gateway_token = vault.get("gateway_token", "")

        # Check API key
        api_ok = self._centinela.check_api_key(provider_id, api_key)
        self._log.info("centinela", f"API key check: {'OK' if api_ok else 'FALLO'}")

        # Check Telegram token
        if gateway_token:
            tg_ok = self._centinela.check_telegram_token(gateway_token)
            self._log.info("centinela", f"Telegram token: {'OK' if tg_ok else 'FALLO'}")

        # Check alarmas y recordatorios pendientes
        fired = self._centinela._check_alarms()
        if fired:
            self._log.info("centinela", f"{len(fired)} alarm(s)/reminder(s) fired")
            for fid in fired:
                # Search for more alarm details
                for al in self._centinela._alarms + self._centinela._reminders:
                    if al.get("id") == fid:
                        atype = "🔔" if al["type"] == "alarm" else "📌"
                        print(f"\n  {atype} {al['type'].upper()}: {al['title']}")
                        if al.get("description"):
                            print(f"     {al['description']}")

                        # ── Skill audit alarm: run full audit ──
                        if "skill audit" in al.get("title", "").lower():
                            print(f"\n  🔍 Running auto skill audit...")
                            report = self._run_skill_audit()
                            print(report)
                            print()
                            # Create ticket with audit results
                            self._engineer.create_ticket(
                                "system",
                                "skill_audit",
                                f"Skill audit completed: skills reviewed, duplicates checked",
                                "low", source="centinela"
                            )

                        # ── Dream Cycle alarm: nightly self-improvement ──
                        if "dream cycle" in al.get("title", "").lower():
                            print(f"\n  🌙 Running nightly Dream Cycle...")
                            report = self._run_dream_cycle()
                            print(report)
                            print()
                        break

        # Process reports
        reports = self._centinela.get_reports()
        for report in reports:
            tid = self._engineer.receive_report(report)

            ticket_data = self._engineer.get_ticket(tid) or {}
            print(f"\n  ⚠️  CENTINELA DETECTÓ DEFECTO: {report['target']}")
            print(f"     → Ticket #{tid} creado con System Engineer")
            print(f"     → Diagnosis: {ticket_data.get('diagnosis', 'pending')}")
            print()

        # ── Push credential notifications to user via gateways ──
        notification = self.inject_credential_ticket_notification()
        if notification:
            print(f"\n{notification}\n")
            # Push through Telegram gateway if available
            tg_gw = self._gateway_mgr.telegram
            if tg_gw and tg_gw.status == "running":
                try:
                    chat_id = self.state.get("active_chat_id", "")
                    if chat_id:
                        tg_gw.send_message(notification, chat_id=chat_id)
                        self._log.info("torre", "Credential notification sent to user via Telegram")
                except Exception as e:
                    self._log.warn("torre", f"Error notifying credentials via Telegram: {e}")

    def _engineer_cycle(self):
        """Processes open tickets and shows the Engineer queue.
        Notifies when new tickets arrive."""
        open_tickets = self._engineer.get_all_open()

        # Track new tickets since last cycle for notification
        now_count = len(open_tickets)
        if hasattr(self, '_last_ticket_count'):
            new_count = now_count - self._last_ticket_count
            if new_count > 0:
                # New tickets arrived — show queue
                print(f"\n  🚨 {new_count} NEW TICKET(S) — Engineer queue updated")
                print(self._engineer.show_queue(5))
                print()
                # Push notification via Telegram if available
                tg_gw = self._gateway_mgr.telegram
                if tg_gw and tg_gw.status == "running":
                    chat_id = self.state.get("active_chat_id", "")
                    if chat_id:
                        try:
                            next_t = self._engineer.next_ticket()
                            if next_t:
                                msg = (f"🚨 New ticket: {next_t.get('profile','?')} — "
                                       f"{next_t.get('target','?')}")
                                tg_gw.send_message(msg, chat_id=chat_id)
                        except Exception:
                            pass
        self._last_ticket_count = now_count

        # Check each open ticket for human intervention
        for ticket in open_tickets:
            if ticket.get("needs_human"):
                self._log.warn("engineer",
                    f"Ticket #{ticket['id']} needs user: {ticket.get('diagnosis','?')}")

    # ── DREAM CYCLE — delegated to DreamCycle ──

    def register_skill(self, skill_name: str = "") -> None:
        """Registers a new skill via DreamCycle."""
        if self._dream is not None:
            self._dream.register_skill(skill_name)

    def _run_skill_audit(self) -> str:
        """Runs skill audit via DreamCycle."""
        if self._dream is not None:
            return self._dream.run_skill_audit()
        return "Dream Cycle not initialized"

    def _schedule_nightly_cycle(self):
        """Schedules nightly Dream Cycle."""
        if self._dream is not None:
            self._dream.schedule_nightly()

    def _run_dream_cycle(self) -> str:
        """Runs nightly Dream Cycle."""
        if self._dream is not None:
            return self._dream.run_nightly()
        return "Dream Cycle not initialized"

    # ── ESTADO ──

    def status(self) -> dict:
        """Complete system status — including TOWER."""
        agente = self.state.get("agente", {})

        print()
        print("📊 ESTADO DE DIGOS v" + VERSION)
        print("━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"  Setup:       {'✅ Completo' if self.state.get('setup_complete') else '⏳ Pendiente'}")
        print(f"  Idioma:      {self.state.get('language', '?')}")
        if agente:
            print(f"  Agente:      {agente.get('name', '?')}")
            print(f"  Proveedor:   {agente.get('provider_name', '?')}")
            print(f"  Gateway:     {agente.get('gateway_type', '?')}")
            print(f"  Kendo:       {'✅ Activo' if agente.get('kendo', {}).get('active') else '❌ Inactivo'}")
        print()
        print("  ── TOWER (Self-Preservation) ──")
        sa = self._self_awareness.status()
        print(f"  Self-Awareness: {sa['state']}")
        print(f"  Identidad:      {sa['identity']['name']} v{sa['identity']['version']}")
        print()

        # Centinela strikes
        strikes = self._centinela.get_all_strikes()
        if strikes:
            print(f"  ⚠️  Centinela — Strikes activos:")
            for k, v in strikes.items():
                print(f"     {k}: {v['count']}/{STRIKE_LIMIT} — {v.get('reason', '')}")
        else:
            print("  ✅ Centinela — Sin defectos detectados")
        print()

        # Engineer tickets
        open_tickets = self._engineer.get_open()
        if open_tickets:
            print(f"  ⚠️  System Engineer — Tickets abiertos: {len(open_tickets)}")
            for t in open_tickets[:3]:
                print(f"     #{t['id']} [{t['severity']}] {t['target']}: {t['diagnosis'] or t['problem']}")
        else:
            print("  ✅ System Engineer — Sin tickets abiertos")
        print()

        total_tickets = len(self._engineer.get_all_tickets())
        print(f"  Total tickets creados: {total_tickets}")
        print()

        # Internal clock
        clock_now = self._clock.now()
        recent_timeline = len(self._clock.recent_events(limit=25))
        print(f"  🕰️  Reloj interno: {clock_now['date']} {clock_now['time']} ({clock_now['timezone']})")
        print(f"  Línea temporal: {recent_timeline} evento(s) recientes")
        print()

        # Gateways
        self.gateway_show_status()

    # ── COMANDOS DE TORRE ──

    def centinela_run_once(self):
        """Runs one Centinela check cycle (CLI mode)."""
        print("\n  🔍 CENTINELA — Ejecutando checks...")
        print("  ─────────────────────────────")
        self._centinela_cycle()
        print("  ✅ Ciclo completado.")
        print()

    def engineer_show_tickets(self, status: str = None):
        """Muestra tickets del Engineer."""
        if status:
            tickets = self._engineer.get_open() if status == "open" else self._engineer.get_all_tickets()
        else:
            tickets = self._engineer.get_all_tickets()

        if not tickets:
            print("\n  📋 No hay tickets.\n")
            return

        print(f"\n  📋 TICKETS ({len(tickets)})")
        print("  ────────────────")
        for t in tickets:
            sev_icon = "🔴" if t["severity"] == "high" else "🟡" if t["severity"] == "medium" else "🟢"
            status_icon = "🔧" if t["status"] == "diagnosing" else "📌" if t["status"] == "open" else "✅"
            print(f"  {sev_icon} {status_icon} #{t['id']:>4} [{t['status']:>10}] {t['target']:25s} {t.get('diagnosis', t['problem'])[:50]}")
        print()

    def logs_show(self, level: str = None, source: str = None, limit: int = 20):
        """Shows system logs."""
        logs = self._log.get_logs(level=level, source=source, limit=limit)
        if not logs:
            print("\n  📝 No hay logs.\n")
            return
        print(f"\n  📝 LOGS ({len(logs)} entries)")
        print("  ────────────────")
        for entry in logs:
            ts = entry.get("ts", "?")[11:19]
            lvl = entry.get("level", "?")
            src = entry.get("source", "?")
            msg = entry.get("msg", "")
            print(f"  {ts} [{lvl:5s}] [{src:10s}] {msg}")
        print()

    # ── GATEWAYS — delegated to GatewayManager ──

    def _init_gateways(self):
        """Initializes gateways via GatewayManager."""
        self._gateway_mgr.init_gateways()

    def register_gateway(self, gateway: 'BaseGateway'):
        """Registers a gateway via GatewayManager."""
        self._gateway_mgr.register(gateway)

    # ── TRANSPARENCY — delegated to GatewayManager ──

    def _init_transparency(self):
        """Initializes transparency via GatewayManager."""
        pass  # handled by GatewayManager internally

    def emit_tool_progress(self, tool_name: str, args: Optional[Dict] = None):
        """Calls the tracker when the agent starts a tool."""
        self._gateway_mgr.emit_tool_progress(tool_name, args)

    def emit_tool_end(self, tool_name: str):
        """Calls the tracker when the agent finishes a tool."""
        self._gateway_mgr.emit_tool_end(tool_name)

    def emit_assistant_message(self, text: str):
        """Calls the tracker when the model generates text between tools."""
        self._gateway_mgr.emit_assistant_message(text)

    def set_active_chat(self, chat_id: str):
        """Updates the active chat in state and tracker. Only for authorized chats."""
        if chat_id not in self._authorized_chats:
            self._log.info("torre", f"Ignored set_active_chat for unauthorized: {chat_id}")
            return
        self.state["active_chat_id"] = chat_id
        self._save_state()
        if self._gateway_mgr is not None:
            self._gateway_mgr.set_active_chat(chat_id)

    def authorize_chat(self, chat_id: str) -> bool:
        """Authorizes a new chat ID and persists it. Returns True if added."""
        chat_str = str(chat_id)
        if chat_str in self._authorized_chats:
            return False
        self._authorized_chats.add(chat_str)
        self.state["authorized_chats"] = list(self._authorized_chats)
        self._save_state()
        self._log.info("torre", f"Chat authorized: {chat_str}")
        return True


    # ── FASE 9: KNOWLEDGE BASE (AgentInfra) ─────

    def _init_knowledge(self):
        """Initializes the knowledge base. Loads structured markdown files."""
        if self._knowledge is not None:
            return
        try:
            kb = KnowledgeBase(str(Path(__file__).resolve().parent.parent / "knowledge"))
            kb.load_all()
            if kb.is_loaded():
                self._knowledge = kb
                self._log.info("torre", f"Knowledge Base loaded ({kb.file_count} files)")
            else:
                self._log.info("torre", "Knowledge Base: no files found")
        except Exception as e:
            self._log.warn("torre", f"Knowledge Base init failed: {e}")
            self._knowledge = None
        # Initialize Dream Cycle alongside knowledge
        self._init_dream()

    def _init_dream(self):
        """Initializes the Dream Cycle for nightly self-improvement."""
        if self._dream is not None:
            return
        self._dream = DreamCycle(self._log, self._centinela, self._engineer, self._knowledge)

    # ── FASE 4b: AIAGENT ──────────────────────

    # ── FASE 8: INTERNAL AGENT CREATION ────────

    def _init_factory(self):
        """Initializes the Factory (FactoryManager + SuperiorAgent).

        Looks for the Factory code in the project root or a master/ directory.
        If not found, Factory is unavailable — no silent failures.
        """
        if self._factory_manager is not None:
            return
        try:
            # Look for Factory in project root or master/
            _project_root = Path(__file__).resolve().parent.parent
            _factory_paths = [
                _project_root / "master",          # ../master/
                _project_root.parent / "master",   # ../../master/
                _project_root / "factory",          # ../factory/
            ]
            _master_dir = None
            for p in _factory_paths:
                if p.is_dir() and (p / "factory" / "manager.py").exists():
                    _master_dir = str(p)
                    break
                elif p.is_dir() and (p / "manager.py").exists():
                    _master_dir = str(p)
                    break

            if _master_dir is None:
                self._log.info("torre", "Factory code not found in any expected location")
                self._factory_manager = None
                self._superior_agent = None
                return

            import sys
            if _master_dir not in sys.path:
                sys.path.insert(0, _master_dir)
            from factory.manager import FactoryManager
            from factory.superior import SuperiorAgent

            self._factory_manager = FactoryManager()
            self._factory_manager.setup()
            self._factory_manager._progress_cb = self.emit_tool_progress
            self._superior_agent = self._factory_manager._superior
            self._log.info("torre", "Factory initialized — internal agents available (with transparency)")
        except Exception as e:
            self._log.warn("torre", f"Factory not available: {e}")
            self._factory_manager = None
            self._superior_agent = None

    def request_internal_agent_creation(
        self,
        agent_type: str,
        mode: str = "collaborative",
        name: str = "",
        mission: str = "",
        requester: str = "agente",
    ) -> dict:
        """Creates an internal agent through the Factory.

        This is called by the AIAgent when the user says "crea 2 builders".
        The flow:
          1. SystemEngineer creates audit ticket
          2. TorreDeControl initializes Factory if needed
          3. SuperiorAgent creates the agent with the chosen mode
          4. If collaborative → registers on MessageBus
          5. If isolated → only sees SuperiorAgent + Tower
          6. Torre inyecta SelfAwareness + GPS + Work + Kendo via AgentBase

        agent_type: 'builder' | 'auditor' | 'reviewer'
        mode: ☑️ 'collaborative' | ☑️ 'isolated'
        """
        # Ensure Factory is initialized
        self._init_factory()

        # Build the factory_create callback for SystemEngineer
        def _factory_create(atype, amode, aname, amission):
            if self._superior_agent is None:
                return None
            return self._superior_agent.create_internal(
                agent_type=atype,
                mode=amode,
                name=aname,
                mission=amission,
            )

        # Route through SystemEngineer (creates ticket + delegates)
        result = self._engineer.create_internal_agent(
            agent_type=agent_type,
            mode=mode,
            name=name,
            mission=mission,
            requester=requester,
            factory_create_fn=_factory_create,
        )

        # Register on MessageBus if collaborative
        if result.get("ok") and mode == "collaborative" and self._bus is not None:
            agent_name = result.get("agent_name", "")
            if agent_name:
                self._bus.register_agent(agent_name, mode=mode)
                self._log.info("torre", f"Agent '{agent_name}' registrado en MessageBus ({mode})")

        return result

    def list_internal_agents(self) -> list:
        """Lists all internal agents from the Factory."""
        if self._superior_agent is None:
            self._init_factory()
        if self._superior_agent is None:
            return []
        return [
            {
                "name": name,
                "type": agent.internal_type,
                "mode": agent.mode,
                "status": agent.status,
                "mission": agent.mission[:80],
                "capabilities": len(agent.get_capabilities()),
            }
            for name, agent in self._superior_agent.internal_agents.items()
        ]

    def request_capability(
        self,
        capability: str,
        family: str,
        sub_intent: str,
        user_message: str,
        requester: str = "agente",
    ) -> dict:
        """Request a new capability detected via intent classification.

        When the AIAgent detects a capability gap (Camino B) and user confirms,
        this method routes the request through the FULL Factory pipeline:
          1. Looks up CapabilitySkillDefinition from intent_classifier
          2. Initializes Factory if needed
          3. Calls FactoryManager.request_new_capability() →
             Builder→Auditor→Reviewer→Release pipeline
          4. Also creates an audit ticket via SystemEngineer for traceability

        This is the bridge between the Intent Classifier and the Factory.
        """
        # ── 1. Look up skill definition ──
        from digos_lib.intent_classifier import get_skill_for_capability, AVAILABLE_CAPABILITIES

        responsibilities = {
            "router": "MASTER",
            "engineer": "System Engineer",
            "factory": "Factory Manager",
            "agent_delivery": "Principal Agent",
            "activation_owner": "Runtime Integration",
        }

        skill_def = get_skill_for_capability(capability)
        activation_requirements = (
            list(skill_def.activation_requirements)
            if skill_def is not None
            else []
        )
        activation_next_step = (
            "conectar la capacidad al canal de Telegram y validarla con una prueba completa."
            if activation_requirements
            else ""
        )
        if skill_def is None:
            # No skill definition — just create an audit ticket
            result = self._engineer.create_capability_request(
                capability=capability,
                family=family,
                sub_intent=sub_intent,
                user_message=user_message,
                requester=requester,
                instructions=[
                    "No automatic Factory definition exists for this request.",
                    "Do not close this ticket until a reviewer defines the missing capability and validates the live path.",
                ],
            )
            audit_profile = result.get("profile", requester or "agente")
            audit_ticket_id = result.get("ticket_id", "")
            engineer_followup = self._open_capability_followup(
                audit_profile=audit_profile,
                audit_ticket_id=audit_ticket_id,
                capability=capability,
                family=family,
                user_message=user_message,
                missing=[
                    "No automatic Factory definition exists for this request.",
                    "A reviewer must define the missing capability and validation path.",
                ],
                next_action="definir la capacidad y validarla antes de cerrarla.",
            )
            self._factory_status.upsert_capability(
                capability,
                family=family,
                user_message=user_message,
                status="registered",
                audit_ticket_id=audit_ticket_id,
                audit_profile=audit_profile,
                requester=requester,
                responsibilities=responsibilities,
                activation_requirements=[],
                activation_missing=[],
                pipeline_stage="REGISTER",
                engineer_followup=engineer_followup or None,
                note="Capability identified without an automatic Factory definition.",
            )
            self._record_timeline_event(
                role="factory",
                summary=f"solicitud identificada sin definicion automatica: {capability}",
                bullet_points=[family, "requiere revision manual"],
                event_type="factory.ticket.registered",
                metadata={"capability": capability, "audit_ticket_id": audit_ticket_id},
            )
            result["user_status"] = self._factory_status.public_summary(capability, language=self._active_language())
            return result

        # ── 2. Also create audit ticket in SystemEngineer for traceability ──
        audit_result = self._engineer.create_capability_request(
            capability=capability,
            family=family,
            sub_intent=sub_intent,
            user_message=user_message,
            requester=requester,
            instructions=activation_requirements,
        )
        audit_profile = audit_result.get("profile", requester or "agente")
        audit_ticket_id = audit_result.get("ticket_id", "")
        if audit_ticket_id:
            self._engineer.mark_instructions_reviewed(
                audit_profile,
                audit_ticket_id,
                activation_requirements or [
                    "No activation checklist was provided. Keep this ticket open until manual validation passes."
                ],
            )
            self._engineer.advance_capability_pipeline(
                audit_profile,
                audit_ticket_id,
                "BUILD",
                "pending",
                note="Waiting for Factory build stage.",
            )
        self._factory_status.upsert_capability(
            capability,
            family=family,
            user_message=user_message,
            status="registered",
            audit_ticket_id=audit_ticket_id,
            audit_profile=audit_profile,
            requester=requester,
            responsibilities=responsibilities,
            activation_requirements=activation_requirements,
            activation_missing=activation_requirements,
            pipeline_stage="REGISTER",
            pipeline_checkpoints={
                "REGISTER": "done",
                "BUILD": "pending",
                "VALIDATE": "pending",
                "ACTIVATE": "pending",
            },
            next_step=activation_next_step,
            note="Capability request registered by the engineer.",
        )
        self._record_timeline_event(
            role="factory",
            summary=f"solicitud registrada: {capability}",
            bullet_points=[family, "REGISTER completado"],
            event_type="factory.ticket.registered",
            metadata={"capability": capability, "audit_ticket_id": audit_ticket_id},
        )

        # ── 3. Initialize Factory if needed ──
        self._init_factory()

        if self._factory_manager is None:
            ticket_id = audit_result.get("ticket_id", "")
            engineer_followup = {}
            if ticket_id:
                self._engineer.add_note(audit_profile, ticket_id,
                    "Factory not available — request logged for awareness")
                self._engineer.update_status(audit_profile, ticket_id, "open")
                self._engineer.add_note(audit_profile, ticket_id,
                    "Ticket remains open until Factory processing becomes available.")
                engineer_followup = self._open_capability_followup(
                    audit_profile=audit_profile,
                    audit_ticket_id=ticket_id,
                    capability=capability,
                    family=family,
                    user_message=user_message,
                    missing=["Factory is not available in this runtime."],
                    next_action="inicializar la Factoría y continuar este mismo ticket.",
                )
            self._factory_status.upsert_capability(
                capability,
                family=family,
                user_message=user_message,
                status="failed",
                audit_ticket_id=ticket_id,
                audit_profile=audit_profile,
                requester=requester,
                responsibilities=responsibilities,
                activation_requirements=activation_requirements,
                activation_missing=activation_requirements,
                pipeline_stage="REGISTER",
                next_step=activation_next_step,
                engineer_followup=engineer_followup or None,
                note="Factory unavailable.",
            )
            return {
                "ok": False,
                "ticket_id": ticket_id,
                "user_status": self._factory_status.public_summary(capability, language=self._active_language()),
                "message": (
                    "Request identified but Factory is not available. "
                    "An audit ticket was created for awareness. "
                    "No automatic processing is queued."
                ),
            }

        # ── 4. Route through FULL Factory pipeline ──
        self._factory_status.upsert_capability(
            capability,
            family=family,
            user_message=user_message,
            status="factory_processing",
            audit_ticket_id=audit_result.get("ticket_id", ""),
            audit_profile=audit_profile,
            requester=requester,
            responsibilities=responsibilities,
            activation_requirements=activation_requirements,
            activation_missing=activation_requirements,
            pipeline_stage="BUILD",
            pipeline_checkpoints={
                "REGISTER": "done",
                "BUILD": "in_progress",
                "VALIDATE": "pending",
                "ACTIVATE": "pending",
            },
            next_step=activation_next_step,
            note="Factory is processing the request.",
        )
        try:
            factory_result = self._factory_manager.request_new_capability(
                capability_id=capability,
                family=family,
                description=skill_def.description,
                target_capabilities=skill_def.target_capabilities,
                target_limitations=skill_def.target_limitations,
                activation_requirements=activation_requirements,
                tool_name=skill_def.tool_name,
                requested_by=requester,
            )
        except Exception as e:
            ticket_id = audit_result.get("ticket_id", "")
            engineer_followup = {}
            if ticket_id:
                self._engineer.add_note(audit_profile, ticket_id,
                    f"Factory error: {e}")
                self._engineer.update_status(audit_profile, ticket_id, "open")
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "BUILD",
                    "failed",
                    note=f"Factory error: {e}",
                    missing=[str(e)],
                    next_action="Fix Factory build failure and retry this same ticket.",
                )
                self._engineer.add_note(audit_profile, ticket_id,
                    "Ticket remains open with failure evidence for another pass.")
                engineer_followup = self._open_capability_followup(
                    audit_profile=audit_profile,
                    audit_ticket_id=ticket_id,
                    capability=capability,
                    family=family,
                    user_message=user_message,
                    missing=[str(e)],
                    next_action="corregir el fallo de Factoría y reintentar este mismo ticket.",
                )
            self._factory_status.upsert_capability(
                capability,
                family=family,
                user_message=user_message,
                status="failed",
                audit_ticket_id=ticket_id,
                audit_profile=audit_profile,
                requester=requester,
                responsibilities=responsibilities,
                activation_requirements=activation_requirements,
                activation_missing=activation_requirements,
                pipeline_stage="BUILD",
                next_step=activation_next_step,
                engineer_followup=engineer_followup or None,
                note=f"Factory error: {e}",
            )
            return {
                "ok": False,
                "ticket_id": ticket_id,
                "user_status": self._factory_status.public_summary(capability, language=self._active_language()),
                "message": f"Factory error: {e}",
            }

        if factory_result is None:
            ticket_id = audit_result.get("ticket_id", "")
            engineer_followup = {}
            if ticket_id:
                self._engineer.add_note(audit_profile, ticket_id,
                    "Factory returned None — no handler for this request")
                self._engineer.update_status(audit_profile, ticket_id, "open")
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "BUILD",
                    "failed",
                    note="Factory returned no handler.",
                    missing=["Factory returned no result for this capability."],
                    next_action="Define a Factory handler or capability skill definition, then retry this same ticket.",
                )
                self._engineer.add_note(audit_profile, ticket_id,
                    "Ticket remains open because no Factory handler completed it.")
                engineer_followup = self._open_capability_followup(
                    audit_profile=audit_profile,
                    audit_ticket_id=ticket_id,
                    capability=capability,
                    family=family,
                    user_message=user_message,
                    missing=["Factory returned no result for this capability."],
                    next_action="definir un handler de Factoría y reintentar este mismo ticket.",
                )
            self._factory_status.upsert_capability(
                capability,
                family=family,
                user_message=user_message,
                status="failed",
                audit_ticket_id=ticket_id,
                audit_profile=audit_profile,
                requester=requester,
                responsibilities=responsibilities,
                activation_requirements=activation_requirements,
                activation_missing=activation_requirements,
                pipeline_stage="BUILD",
                next_step=activation_next_step,
                engineer_followup=engineer_followup or None,
                note="Factory returned no result.",
            )
            return {
                "ok": False,
                "ticket_id": ticket_id,
                "user_status": self._factory_status.public_summary(capability, language=self._active_language()),
                "message": "Factory could not process the request.",
            }

        # ── 5. Enrich result with audit ticket info ──
        ticket_id = audit_ticket_id
        factory_result["audit_ticket_id"] = ticket_id
        factory_result["audit_profile"] = audit_profile
        tool_name = factory_result.get("tool_name", skill_def.tool_name)
        factory_ok = bool(factory_result.get("ok", False))
        is_active = factory_ok and (tool_name in AVAILABLE_CAPABILITIES or capability in AVAILABLE_CAPABILITIES)
        status = "active" if is_active else (
            "pending_validation" if factory_ok else "failed"
        )
        responsibilities = dict(responsibilities)
        if factory_result.get("agent_name"):
            responsibilities["builder"] = factory_result["agent_name"]
        engineer_followup = {}

        if ticket_id:
            if factory_ok and is_active:
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "BUILD",
                    "done",
                    note="Factory build completed.",
                )
                self._engineer.add_validation_evidence(
                    audit_profile,
                    ticket_id,
                    [
                        f"Capability '{capability}' exists in the active capability registry.",
                        "Live-path validation was required before closure.",
                    ],
                    passed=True,
                )
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "ACTIVATE",
                    "done",
                    note="Capability active in the requested runtime path.",
                )
                self._engineer.add_note(audit_profile, ticket_id,
                    f"Factory processed and validated active capability: {capability}")
                self._engineer.close_ticket(audit_profile, ticket_id,
                    f"Capability '{capability}' processed, validated, and active. "
                    f"Result: {factory_result.get('message', 'processed')}")
                self._log.info("torre",
                    f"Ticket #{ticket_id} closed: Factory validated {capability}")
            elif factory_ok:
                self._engineer.update_status(audit_profile, ticket_id, "pending_validation")
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "BUILD",
                    "done",
                    note="Factory build completed; validation gate is next.",
                )
                self._engineer.add_validation_evidence(
                    audit_profile,
                    ticket_id,
                    [
                        "Factory accepted the request but the live channel is not active yet.",
                        *activation_requirements,
                    ],
                    passed=False,
                )
                self._engineer.add_note(audit_profile, ticket_id,
                    "Factory processed the request, but VALIDATE did not pass. "
                    "Runtime activation and end-to-end validation are still pending. "
                    "Ticket remains open at pending_validation.")
                engineer_followup = self._open_capability_followup(
                    audit_profile=audit_profile,
                    audit_ticket_id=ticket_id,
                    capability=capability,
                    family=family,
                    user_message=user_message,
                    missing=activation_requirements,
                    next_action=activation_next_step,
                )
                self._log.info("torre",
                    f"Ticket #{ticket_id} remains open: {capability} pending validation")
            else:
                self._engineer.add_note(audit_profile, ticket_id,
                    f"Factory failed: {factory_result.get('message', 'unknown error')}")
                self._engineer.update_status(audit_profile, ticket_id, "open")
                self._engineer.advance_capability_pipeline(
                    audit_profile,
                    ticket_id,
                    "BUILD",
                    "failed",
                    note=f"Factory failed: {factory_result.get('message', 'unknown error')}",
                    missing=[factory_result.get("message", "unknown error")],
                    next_action="Fix Factory build failure and retry this same ticket.",
                )
                self._engineer.add_note(audit_profile, ticket_id,
                    "Returned to the mailbox with failure details. Validation did not run "
                    "because BUILD failed; the ticket stays open.")
                engineer_followup = self._open_capability_followup(
                    audit_profile=audit_profile,
                    audit_ticket_id=ticket_id,
                    capability=capability,
                    family=family,
                    user_message=user_message,
                    missing=[factory_result.get("message", "unknown error")],
                    next_action="corregir el fallo de build y reintentar este mismo ticket.",
                )
                self._log.warn("torre",
                    f"Ticket #{ticket_id} returned open with failure: {capability}")

        # ── 6. Persist live ticket status for the agent and Factory ──
        self._factory_status.upsert_capability(
            capability,
            family=family,
            user_message=user_message,
            status=status,
            audit_ticket_id=ticket_id,
            audit_profile=audit_profile,
            requester=requester,
            factory_ticket_number=factory_result.get("ticket_number", ""),
            tool_name=tool_name,
            active=is_active,
            responsibilities=responsibilities,
            activation_requirements=activation_requirements,
            activation_missing=[] if is_active else activation_requirements,
            pipeline_stage="ACTIVATE" if is_active else ("VALIDATE" if factory_ok else "BUILD"),
            pipeline_checkpoints={
                "REGISTER": "done",
                "BUILD": "done" if factory_ok else "failed",
                "VALIDATE": "done" if is_active else ("failed" if factory_ok else "pending"),
                "ACTIVATE": "done" if is_active else ("blocked" if factory_ok else "pending"),
            },
            next_step="" if is_active else activation_next_step,
            engineer_followup=engineer_followup or None,
            note=(
                "Factory completed and capability is active."
                if is_active
                else "Factory completed its part; VALIDATE did not pass and runtime activation is still pending."
            ),
        )
        self._record_timeline_event(
            role="factory",
            summary=f"estado de capacidad: {capability}",
            bullet_points=[
                f"estado: {status}",
                f"etapa: {'ACTIVATE' if is_active else ('VALIDATE' if factory_ok else 'BUILD')}",
                "ticket sigue abierto" if not is_active else "ticket cerrado",
            ],
            event_type="factory.ticket.status",
            metadata={"capability": capability, "audit_ticket_id": ticket_id},
        )
        factory_result["active"] = is_active
        factory_result["status"] = status
        factory_result["audit_ticket_status"] = "closed" if is_active else ("pending_validation" if factory_ok else "open")
        factory_result["pipeline_stage"] = "ACTIVATE" if is_active else ("VALIDATE" if factory_ok else "BUILD")
        factory_result["pipeline_checkpoints"] = {
            "REGISTER": "done",
            "BUILD": "done" if factory_ok else "failed",
            "VALIDATE": "done" if is_active else ("failed" if factory_ok else "pending"),
            "ACTIVATE": "done" if is_active else ("blocked" if factory_ok else "pending"),
        }
        factory_result["validation_required"] = not is_active
        factory_result["closure_allowed"] = bool(is_active)
        factory_result["responsibilities"] = responsibilities
        factory_result["activation_requirements"] = activation_requirements
        factory_result["activation_missing"] = [] if is_active else activation_requirements
        factory_result["user_status"] = self._factory_status.public_summary(capability, language=self._active_language())
        return factory_result

    def get_factory_user_status(self, capability: str = "") -> str:
        """Return clean user-facing Factory status for the latest request."""
        return self._factory_status.public_summary(capability, language=self._active_language())

    def request_credential_disclosure(self, credential_type: str, requester: str = "agente") -> dict:
        """
        If the user asks to see their token/API key, the Agent calls here,
        the Engineer creates an audit ticket, reads CajaSeguraInfo,
        and returns the credential.

        credential_type: 'api_key' | 'gateway_token' | 'provider_id' | 'all'
        """
        return self._engineer.disclose_credential(credential_type, requester)

    def request_credential_rotation(self, credential_type: str, new_value: str, requester: str = "agente") -> dict:
        """
        El Centinela solo monitorea.

        1. Engineer validates the new key (connection test)
        2. Tower guarda en CajaSeguraInfo
        3. Cierra tickets relacionados del Centinela
        4. Resetea strikes del Centinela para monitoreo fresco

        credential_type: 'api_key' | 'gateway_token'
        """
        result = self._engineer.rotate_credential(credential_type, new_value, requester)

        # Reset Centinela strikes para el tipo rotado
        if result.get("ok"):
            strike_key = f"api_key:{self.state.get('agente', {}).get('provider_id', '')}" if credential_type == "api_key" else "telegram:bot"
            self._centinela.reset_strikes(strike_key)


            # Si es API key, reiniciar el agente con la nueva key
            if credential_type == "api_key" and self._agent is not None:
                vault = CajaSeguraInfo.read_slot("principal")
                if vault and vault.get("api_key"):
                    self._agent._api_key = vault["api_key"]
                    self._log.info("torre", "AIAgent reiniciado con nueva API key")

        return result

    def get_pending_credential_tickets(self) -> List[dict]:
        """Returns Centinela tickets that need user input (invalid API key/token).

        These tickets were detected by Centinela and diagnosed by the Engineer.
        El Agente debe notificar al usuario para que proporcione una nueva credencial.
        """
        return self._engineer.get_credential_tickets_needing_user()

    def inject_credential_ticket_notification(self) -> str:
        """If there are pending Centinela tickets about credentials,
        builds a notification message for the Agent to present to the user.

        Returns empty string if no pending tickets."""
        tickets = self.get_pending_credential_tickets()
        if not tickets:
            return ""

        lines = ["⚠️  EL CENTINELA DETECTÓ PROBLEMAS CON TUS CREDENCIALES", ""]
        for t in tickets[:3]:  # max 3
            tid = t.get("id", "?")
            target = t.get("target", "")
            diagnosis = t.get("diagnosis", t.get("problem", ""))
            if "api_key" in target:
                lines.append(f"  🔑 Ticket #{tid}: Tu API key ha fallado.")
                lines.append(f"     {diagnosis}")
                lines.append(f"     Usa: 'cambia mi API key a [nueva key]' para rotarla.")
            elif "telegram" in target:
                lines.append(f"  📡 Ticket #{tid}: Tu token de Telegram ha fallado.")
                lines.append(f"     {diagnosis}")
                lines.append(f"     Usa: 'cambia mi token a [nuevo token]' para rotarlo.")
            lines.append("")
        lines.append("El System Engineer ya tiene los tickets. Proporciona la nueva credencial para resolverlos.")
        return "\n".join(lines)

    def _init_engine(self):
        """Inicializa el Engine (GPS + Self + Work) si hay destino configurado."""
        if self._engine is not None:
            return
        try:
            from digos_lib.engine import Engine
            rocket_path = str(DIGOS_DIR / "rocket")
            self._engine = Engine(rocket_path)
            self._log.info("torre", "Engine (GPS/SELF/WORK) inicializado")
        except Exception as e:
            self._log.info("torre", f"Engine no disponible: {e}")
            self._engine = None

    def _check_with_engine(self, text: str) -> dict:
        """Runs the message through the Engine to validate GPS.
        Returns dict with routing decision."""
        if self._engine is None:
            return {"action": "process_normally", "reason": "Engine no disponible"}

        try:
            decision = self._engine.process_message(text)
            return decision
        except Exception as e:

            return {"action": "process_normally", "reason": f"Error: {e}"}

    def _init_agent(self):
        """Inicializa el AIAgent con credenciales de CajaSeguraInfo."""
        if self._agent is not None:
            return

        vault = CajaSeguraInfo.read_slot("principal")
        if not vault:
            self._log.info("torre", "No hay slot principal — AIAgent no iniciado (esperando setup)")
            return

        api_key = vault.get("api_key", "")
        provider_id = vault.get("provider_id", "")
        model = vault.get("model", self._provider_default_model(provider_id))
        base_url = self._provider_base_url(provider_id)

        if not api_key:
            self._log.info("torre", "Empty API key in vault — AIAgent not started (waiting for setup)")
            return

        # Ensure engine is initialized before building prompt (GPS + Self + Work)
        self._init_engine()

        # Ensure transparency tracker is initialized (part of agent birth)
        self._init_transparency()

        # Ensure knowledge base is initialized (project context)
        self._init_knowledge()

        system_prompt = self._build_agent_prompt()

        from agent import AIAgent  # lazy import to avoid circular dep
        self._agent = AIAgent(
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            progress_cb=self.emit_tool_progress,
            assistant_cb=self.emit_assistant_message,
            approval_cb=self._approval_callback,
            disclosure_cb=self.request_credential_disclosure,
            rotation_cb=self.request_credential_rotation,
            creation_cb=self.request_internal_agent_creation,
            capability_cb=self.request_capability,
            factory_status_cb=self.get_factory_user_status,
            factory_followup_cb=self.report_factory_followup_issue,
            timeline_cb=self._record_timeline_event,
            temporal_context_cb=self._temporal_context_for_agent,
            language=self._active_language(),
        )
        self._log.info("torre",
            f"AIAgent iniciado: {provider_id}/{model} → {base_url}")

    PROVIDER_DEFAULT_MODELS = {
        "1": "gpt-4o",
        "2": "claude-sonnet-4-20250514",
        "3": "gemini-2.0-flash",
        "4": "deepseek-chat",
        "5": "openrouter/auto",
        "6": "llama-3.3-70b-versatile",
        "7": "grok-2-latest",
        "8": "command-r-plus",
        "9": "mistral-large-latest",
        "10": "mistralai/Mixtral-8x22B-Instruct-v0.1",
        "11": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    }

    @staticmethod
    def _provider_default_model(provider_id: str) -> str:
        """Returns the default model for a provider."""
        return TorreDeControl.PROVIDER_DEFAULT_MODELS.get(provider_id, "gpt-4o")

    @staticmethod
    def _provider_base_url(provider_id: str) -> str:
        """Resolves the base API URL for the provider."""
        urls = {
            "1": "https://api.openai.com/v1",
            "2": "https://api.anthropic.com/v1",
            "3": "https://generativelanguage.googleapis.com/v1beta/openai",
            "4": "https://api.deepseek.com/v1",
            "5": "https://openrouter.ai/api/v1",
            "6": "https://api.groq.com/openai/v1",
            "7": "https://api.x.ai/v1",
            "8": "https://api.cohere.com/v1",
            "9": "https://api.mistral.ai/v1",
            "10": "https://api.together.xyz/v1",
            "11": "https://api.fireworks.ai/v1",
        }
        return urls.get(provider_id, "https://api.openai.com/v1")

    def _build_agent_prompt(self) -> str:
        """Builds the product-facing agent prompt for MASTER.

        Internal operating notes stay internal. The public agent receives only
        enough context to answer safely and route work through the orchestra.
        """
        lang = self._active_language()
        agente = self.state.get("agente", {})

        # ── 1. Base identity (multilingual) ──
        base_prompts = {
            "en": (
                "You are MASTER, an intelligent agent system.\n"
                "You have access to tools. Use them when needed.\n"
                "Be concise, direct, and helpful.\n"
                "Your public identity is MASTER.\n"
                "Answer in English unless the user confirms a language change.\n"
            ),
            "es": (
                "Eres MASTER, un sistema de agente inteligente.\n"
                "Tienes acceso a herramientas. Úsalas cuando sea necesario.\n"
                "Sé conciso, directo y útil.\n"
                "Tu identidad pública es MASTER.\n"
                "Responde en español salvo que el usuario confirme cambiar idioma.\n"
            ),
            "pt": (
                "Você é MASTER, um sistema de agente inteligente.\n"
                "Você tem acesso a ferramentas. Use-as quando necessário.\n"
                "Seja conciso, direto e útil.\n"
                "Sua identidade pública é MASTER.\n"
            ),
            "fr": (
                "Vous êtes MASTER, un système d'agent intelligent.\n"
                "Vous avez accès à des outils. Utilisez-les si nécessaire.\n"
                "Soyez concis, direct et utile.\n"
                "Votre identité publique est MASTER.\n"
            ),
            "de": (
                "Du bist MASTER, ein intelligentes Agentensystem.\n"
                "Du hast Zugriff auf Werkzeuge. Nutze sie bei Bedarf.\n"
                "Sei prägnant, direkt und hilfreich.\n"
                "Deine öffentliche Identität ist MASTER.\n"
            ),
        }
        base = base_prompts.get(lang, base_prompts["en"])

        product_boundaries = (
            "\n== PUBLIC PRODUCT BOUNDARIES ==\n"
            "- Do not expose internal architecture, file paths, folders, build names, "
            "project history, safety labels, ticket internals, builders, sandboxes, or logs.\n"
            "- Do not mention legacy project names, internal status systems, internal "
            "color policies, internal documents, or source-code module names to the user.\n"
            "- If asked how the system works, explain it simply: receive message, check "
            "whether MASTER can help, use available tools when appropriate, and answer.\n"
            "- For voice, say it is not active yet if asked to process audio.\n"
            "- For web search, say it is not active from Telegram unless a real tool is available.\n"
            "- For tool requests, report the clean user-facing Factory status only.\n"
        )

        # ── 2. System info ──
        system_info = (
            f"\nSystem: MASTER v{VERSION}\n"
            f"Creator: Anthony Sanchez and an Artificial Intelligence\n"
            f"Agent: {agente.get('name', 'Principal')}\n"
            f"Provider: {agente.get('provider_name', '?')}\n"
        )

        # ── 3. Product-safe knowledge summary ──
        knowledge_context = ""
        if self._knowledge is not None and self._knowledge.is_loaded():
            try:
                kb_text = self._knowledge.build_context()
                if kb_text.strip():
                    knowledge_context = kb_text.strip()
            except Exception:
                knowledge_context = ""

        safety_guidance = (
            "\n== SAFETY GUIDANCE ==\n"
            "If a user message includes an internal safety review note, analyze intent "
            "carefully. If harmful, refuse briefly. If harmless, answer normally. "
            "Never repeat the note.\n"
        )

        return base + product_boundaries + knowledge_context + system_info + safety_guidance

    # ── FASE 6: MESSAGE BUS ─────────────────────

    def _init_bus(self):
        """Initializes the Message Bus for multi-agent communication."""
        if self._bus is not None:
            return
        self._bus = MessageBus()
        self._bus.set_message_callback(
            lambda msg: self._log.info("bus", msg)
        )

        # Register principal agent
        agente = self.state.get("agente", {})
        name = agente.get("name", "principal").lower().replace(" ", "-")
        self._bus.register_agent(name, mode="collaborative")

        # Register adopted profiles
        profiles_dir = DIGOS_DIR / "profiles"
        if profiles_dir.is_dir():
            for p_dir in sorted(profiles_dir.iterdir()):
                if p_dir.is_dir() and not p_dir.name.startswith("."):
                    self._bus.register_agent(p_dir.name, mode="isolated")

        self._bus.start()
        count = len(self._bus.list_agents())


    def _register_agent_bus(self, name: str, mode: str = "isolated"):
        """Registers an agent in the Message Bus."""
        if self._bus is None:
            return
        self._bus.register_agent(name, mode=mode)
        self._log.info("torre", f"Agente '{name}' registrado en MessageBus ({mode})")


    def _agent_set_mode(self, name: str, mode: str) -> bool:
        """Changes an agent's mode in the bus (by user order)."""
        if self._bus is None:
            return False
        ok = self._bus.switch_mode(name, mode)
        if ok:
            icons = {"isolated": "🔒", "collaborative": "🤝"}
            icon = icons.get(mode, "❓")
            self._log.info("torre", f"Agente '{name}' cambiado a modo {mode}")
            print(f"  {icon} Agente '{name}' ahora en modo {mode}")
        return ok

    def _bus_status(self):
        """Muestra estado del Message Bus."""
        if self._bus is None:
            print("  📡 Message Bus: No iniciado")
            return
        self._bus.print_status()

    # ── FASE 7: AUTO-LAUNCH (launchd) ──────────

    LAUNCHD_LABEL = "com.digos.torredecontrol"
    LAUNCHD_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"

    def _launchd_entrypoint(self) -> Path:
        return Path(__file__).resolve().parent.parent / "digos.py"

    def _launchd_install_block_reason(self) -> str:
        entrypoint = self._launchd_entrypoint()
        restricted_roots = [
            Path.home() / "Desktop",
            Path.home() / "Downloads",
        ]
        for root in restricted_roots:
            try:
                if entrypoint == root or root in entrypoint.parents:
                    return (
                        "MASTER esta corriendo desde una carpeta que macOS puede "
                        "bloquear para servicios en segundo plano. Mueve la carpeta "
                        "a una ruta permanente fuera de Desktop/Downloads antes de "
                        "instalar inicio automatico."
                    )
            except Exception:
                continue
        return ""

    def _install_launchd(self) -> bool:
        """Installs DIGOS as a launchd service so it starts at login."""
        try:
            block_reason = self._launchd_install_block_reason()
            if block_reason:
                self._log.warn("torre", f"Launchd install blocked: {block_reason}")
                return False
            entrypoint = self._launchd_entrypoint()
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.LAUNCHD_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{entrypoint}</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{DIGOS_DIR / 'logs' / 'launchd.stdout.log'}</string>
    <key>StandardErrorPath</key>
    <string>{DIGOS_DIR / 'logs' / 'launchd.stderr.log'}</string>
    <key>WorkingDirectory</key>
    <string>{DIGOS_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>'''
            self.LAUNCHD_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.LAUNCHD_PATH.write_text(plist_content)
            self.LAUNCHD_PATH.chmod(0o644)
            import subprocess
            subprocess.run(["launchctl", "load", str(self.LAUNCHD_PATH)],
                          capture_output=True, timeout=10)
            self._log.info("torre", "Launchd installed — DIGOS will start at login")
            return True
        except Exception as e:
            self._log.error("torre", f"Error instalando launchd: {e}")
            return False

    def _uninstall_launchd(self) -> bool:
        """Desinstala el servicio launchd."""
        try:
            if self.LAUNCHD_PATH.exists():
                import subprocess
                subprocess.run(["launchctl", "unload", str(self.LAUNCHD_PATH)],
                              capture_output=True, timeout=10)
                self.LAUNCHD_PATH.unlink()
                self._log.info("torre", "Launchd desinstalado")
                return True
            self._log.info("torre", "Launchd no estaba instalado")
            return False
        except Exception as e:
            self._log.error("torre", f"Error desinstalando launchd: {e}")
            return False

    def _launchd_status(self) -> dict:
        """Verifica el estado del servicio launchd."""
        try:
            import subprocess
            # Verificar si el plist existe
            installed = self.LAUNCHD_PATH.exists()
            # Verify if the process is actually running
            pid_result = subprocess.run(
                ["launchctl", "list", self.LAUNCHD_LABEL],
                capture_output=True, text=True, timeout=5,
            )
            running = False
            if pid_result.returncode == 0 and pid_result.stdout.strip():
                try:
                    parts = pid_result.stdout.strip().split("\t")
                    if len(parts) >= 3 and parts[0] != "-":
                        running = True
                except Exception:
                    pass
            return {"installed": installed, "running": running}
        except Exception:
            return {"installed": self.LAUNCHD_PATH.exists(), "running": False}

    def _ensure_launchd(self):
        """In daemon mode, checks that launchd is configured.
        If not, asks the user if they want to install it."""
        if not self._daemon_mode:
            return
        status = self._launchd_status()
        if status.get("installed"):
            self._log.info("torre", "Launchd ya instalado — MASTER vive 24/7")
            return
        print()
        print("  🚀 AUTO-LAUNCH")
        print("  ────────────────")
        print(self._ui_text(
            "  MASTER can start automatically when you turn on",
            "  MASTER puede iniciar automaticamente cuando enciendas",
        ))
        print(self._ui_text(
            "  your computer. So you never have to start it manually.",
            "  esta computadora. Asi no tienes que abrirlo manualmente.",
        ))
        print()
        question = self._ui_text("  Install auto-start?", "  ¿Instalar inicio automatico?")
        if self._confirm_yn(question):
            block_reason = self._launchd_install_block_reason()
            if block_reason:
                print(f"  ⚠️ {block_reason}")
                print(self._ui_text(
                    "  Start MASTER manually for now, then install auto-start from the permanent folder.",
                    "  Inicia MASTER manualmente por ahora y luego instala inicio automatico desde la carpeta permanente.",
                ))
            elif self._install_launchd():
                print(self._ui_text(
                    "  ✅ Auto-start installed. MASTER will stay available.",
                    "  ✅ Inicio automatico instalado. MASTER quedara disponible.",
                ))
            else:
                print(self._ui_text(
                    "  ❌ Could not install auto-start.",
                    "  ❌ No pude instalar el inicio automatico.",
                ))
        else:
            print(self._ui_text(
                "  You can install it later with: ./digos --install",
                "  Puedes instalarlo despues con: ./digos --install",
            ))
        print()

    def print_launchd_status(self):
        """Muestra estado del servicio launchd."""
        status = self._launchd_status()
        print()
        print("  🚀 AUTO-LAUNCH")
        print("  ────────────────")
        if status["installed"]:
            icon = "🟢" if status["running"] else "🟡"
            print(f"  {icon} Servicio: {'Activo' if status['running'] else 'Instalado pero no corriendo'}")
        else:
            print("  ⚫ No instalado. Usa --install para activar.")
        print()

    def print_identity(self):
        """Shows DIGOS system identity."""
        ident = SYSTEM_IDENTITY
        print()
        print(f"  ╔══════════════════════════════════════╗")
        print(f"  ║     {ident['name']} — Identity           ║")
        print(f"  ╚══════════════════════════════════════╝")
        print()
        print(f"  System:    {ident['full_name']}")
        print(f"  Version:   {ident['version']}")
        print(f"  Creator:   {ident['creator']}")
        print(f"  Made by:   {ident['created_by']}")
        print(f"  Name:      {'I have no personal name' if ident['no_personal_name'] else 'DIGOS'}")
        print()
        print(f"  {'─' * 40}")
        print(f"  FAQ:")
        print(f"    Who are you?       → I have no personal name. I am DIGOS.")
        print(f"    Who created you?  → {ident['creator']}, {ident['created_by']}.")
        print(f"    Who made you?     → {ident['creator']}, {ident['created_by']}.")
        print(f"    Who built you?    → {ident['creator']}, {ident['created_by']}.")
        print()

    def gateway_show_status(self):
        """Muestra el estado de todos los gateways."""
        self._gateway_mgr.show_status()

    def _gateway_health_check(self):
        """Health check de todos los gateways registrados."""
        self._gateway_mgr.health_check()

    def _poll_gateways(self):
        """Poll mensajes entrantes de gateways con transparencia."""
        tg_gw = self._gateway_mgr.telegram
        if not tg_gw or tg_gw.status != "running":
            return

        messages = tg_gw.poll_updates()
        for msg in messages:
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "").strip()

            if not chat_id:
                continue

            # Chat authorization — reject unauthorized users
            if chat_id not in self._authorized_chats:
                tg_gw.send_message(
                    "⛔ You are not authorized to talk to this agent.",
                    chat_id=chat_id,
                )
                self._log.info("torre", f"Rejected message from unauthorized chat: {chat_id}")
                continue

            if not text:
                tg_gw.send_message(
                    "Por ahora solo puedo procesar mensajes de texto. "
                    "La función de voz todavía no está activa.",
                    chat_id=chat_id,
                )
                continue

            # Update active chat for transparency tracker
            self.set_active_chat(chat_id)

            # Process through agent
            if self._agent is not None:
                try:
                    tg_gw.send_chat_action(chat_id, "typing")
                    response = self._agent.process_message(text)
                    # Clear progress window before sending final answer
                    if self._gateway_mgr is not None:
                        self._gateway_mgr.clear_progress()
                    tg_gw.send_message(response, chat_id=chat_id)
                except Exception as e:
                    self._log.warn("torre",
                        f"Error procesando mensaje de Telegram: {e}")
                    tg_gw.send_message(
                        "⚠️ Error procesando tu mensaje. Intenta de nuevo.",
                        chat_id=chat_id,
                    )
            else:
                tg_gw.send_message(
                    "⚠️ Agente no disponible. Inicia el setup primero.",
                    chat_id=chat_id,
                )
