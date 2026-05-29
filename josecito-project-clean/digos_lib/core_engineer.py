"""DIGOS SystemEngineer — Ticket system with mailbox architecture."""
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from dataclasses import asdict

from digos_lib.constants import DIGOS_DIR, PROVIDERS
from digos_lib.core_models import Ticket
from digos_lib.core_log import LogKeeper
from digos_lib.core_vault import CajaSeguraInfo
from digos_lib.provider_api import _provider_api_request

class SystemEngineer:
    """Receives reports, creates tickets in mailboxes per profile.

    Each profile has its own mailbox:
      ~/.digos/profiles/{perfil}/MAILBOX/{timestamp}-{seq}.json

    Los tickets se ordenan por timestamp (FIFO).
    Each agent writes to its own mailbox — no contention.
    The Engineer reads all mailboxes in order.
    No global index: the filesystem IS the index.
    """

    def __init__(self, log_keeper: LogKeeper, profiles_dir: Optional[Path] = None):
        self.log = log_keeper
        self._profiles_dir = profiles_dir or (DIGOS_DIR / "profiles")
        self._lock = threading.Lock()  # thread-safe ticket creation

    def _mailbox_dir(self, profile: str) -> Path:
        return self._profiles_dir / self._safe_profile(profile) / "MAILBOX"

    @staticmethod
    def _safe_profile(profile: str) -> str:
        """Keep mailbox names local and predictable."""
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(profile or "system")).strip("._")
        return cleaned or "system"

    @staticmethod
    def _capability_procedure_steps() -> List[dict]:
        """Mandatory procedure attached to every capability ticket."""
        return [
            {
                "id": "1_read_full_ticket",
                "label": "Read the full ticket, original request, family, sub-intent, notes, and checklist.",
            },
            {
                "id": "2_classify_and_confirm_scope",
                "label": "Confirm whether the request is voice, web, vision, credential, agent, or another capability.",
            },
            {
                "id": "3_inspect_existing_resources",
                "label": "Check whether the adapter, skill, gateway, profile config, or provider already exists.",
            },
            {
                "id": "4_build_or_connect_missing_links",
                "label": "Build missing pieces or connect existing resources to the requested live path.",
            },
            {
                "id": "5_wire_governance_and_channel",
                "label": "Route the capability through MASTER governance and the requested channel.",
            },
            {
                "id": "6_run_fake_local_validation",
                "label": "Run fake/local validation and record evidence.",
            },
            {
                "id": "7_run_live_path_validation",
                "label": "Run live-path validation when the request is for Telegram or another live channel.",
            },
            {
                "id": "8_close_or_return_with_evidence",
                "label": "Close only if validation passes; otherwise keep open with missing link and next action.",
            },
        ]

    @staticmethod
    def _capability_pipeline_template() -> dict:
        """REGISTER -> BUILD -> VALIDATE -> ACTIVATE state machine."""
        return {
            "current": "REGISTER",
            "checkpoints": {
                "REGISTER": "pending",
                "BUILD": "pending",
                "VALIDATE": "pending",
                "ACTIVATE": "pending",
            },
            "history": [],
        }

    @staticmethod
    def _pipeline_event(stage: str, state: str, note: str = "") -> dict:
        return {
            "at": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "state": state,
            "note": note,
        }

    def _ensure_mailbox(self, profile: str):
        self._mailbox_dir(profile).mkdir(parents=True, exist_ok=True)

    def _next_ticket_id(self, profile: str) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")  # microsecond precision
        seq = 0
        mailbox = self._mailbox_dir(profile)
        if mailbox.exists():
            for f in mailbox.iterdir():
                if f.name.endswith(".json"):
                    seq += 1
        return f"{ts}-{seq:04d}"

    def _save_ticket(self, profile: str, tid: str, ticket: dict):
        self._ensure_mailbox(profile)
        tf = self._mailbox_dir(profile) / f"{tid}.json"
        tf.write_text(json.dumps(ticket, indent=2))

    def _load_ticket(self, profile: str, tid: str) -> Optional[dict]:
        tf = self._mailbox_dir(profile) / f"{tid}.json"
        if not tf.exists():
            return None
        try:
            return json.loads(tf.read_text(encoding='utf-8'))
        except Exception:
            return None

    def _iter_tickets(self, profile: str) -> List[dict]:
        mailbox = self._mailbox_dir(profile)
        if not mailbox.is_dir():
            return []
        tickets = []
        for f in sorted(mailbox.iterdir()):
            if f.name.endswith(".json"):
                try:
                    t = json.loads(f.read_text(encoding='utf-8'))
                    tickets.append(t)
                except Exception:
                    continue
        return tickets

    def receive_report(self, report: dict) -> str:
        profile = report.get("profile", "system")
        tid = self._next_ticket_id(profile)
        target = report.get("target", "")
        sev = "high" if ("api_key" in target or "telegram" in target) else "medium"
        ticket = Ticket(id=tid, profile=profile, source="centinela",
            target=target,
            problem=f"{report.get('strikes', 3)} fallos: {report.get('reason', 'desconocido')}",
            severity=sev, status="open",
            created_at=datetime.now(timezone.utc).isoformat())
        self._save_ticket(profile, tid, asdict(ticket))
        self.log.warn("engineer", f"Ticket #{tid} en buzón de '{profile}': {target}", {"severity": sev})
        self._diagnose(profile, tid)
        return tid

    def create_ticket(self, profile: str, target: str, problem: str,
                      severity: str = "medium", source: str = "manual") -> str:
        profile = self._safe_profile(profile)
        with self._lock:
            tid = self._next_ticket_id(profile)
            ticket = Ticket(id=tid, profile=profile, source=source,
                target=target, problem=problem, severity=severity,
                status="open", created_at=datetime.now(timezone.utc).isoformat(timespec='microseconds'))
            self._save_ticket(profile, tid, asdict(ticket))
        self.log.info("engineer", f"Ticket #{tid} en buzón de '{profile}': {target}")
        return tid

    def _diagnose(self, profile: str, tid: str):
        ticket = self._load_ticket(profile, tid)
        if not ticket: return
        ticket["status"] = "diagnosing"
        target = ticket["target"]
        if target.startswith("api_key:"):
            ticket["diagnosis"] = f"API key de {target.split(':')[1]} rechazada — expirada, sin saldo o revocada"
        elif target.startswith("telegram"):
            ticket["diagnosis"] = "Telegram token rejected — revocado o inválido"
        else:
            ticket["diagnosis"] = "Unknown failure — requiere revisión manual"
        ticket["needs_human"] = True
        self._save_ticket(profile, tid, ticket)
        self.log.info("engineer", f"Ticket #{tid} diagnosis: {ticket['diagnosis']}")

    def assign_ticket(self, profile: str, tid: str, assignee: str) -> bool:
        ticket = self._load_ticket(profile, tid)
        if not ticket: return False
        ticket["assignee"] = assignee; ticket["status"] = "assigned"
        self._save_ticket(profile, tid, ticket)
        self.log.info("engineer", f"Ticket #{tid} asignado a {assignee}")
        return True

    def update_status(self, profile: str, tid: str, status: str) -> bool:
        ticket = self._load_ticket(profile, tid)
        if not ticket: return False
        ticket["status"] = status
        self._save_ticket(profile, tid, ticket)
        return True

    def add_note(self, profile: str, tid: str, note: str) -> bool:
        ticket = self._load_ticket(profile, tid)
        if not ticket: return False
        ticket.setdefault("notes", []).append({"text": note, "timestamp": datetime.now(timezone.utc).isoformat()})
        self._save_ticket(profile, tid, ticket)
        return True

    def advance_capability_pipeline(
        self,
        profile: str,
        tid: str,
        stage: str,
        state: str,
        *,
        note: str = "",
        evidence: Optional[List[str]] = None,
        missing: Optional[List[str]] = None,
        next_action: str = "",
    ) -> bool:
        """Move a capability ticket through REGISTER -> BUILD -> VALIDATE -> ACTIVATE."""
        ticket = self._load_ticket(profile, tid)
        if not ticket:
            return False
        stage = str(stage).upper()
        state = str(state).lower()
        allowed = {"REGISTER", "BUILD", "VALIDATE", "ACTIVATE"}
        if stage not in allowed:
            return False
        if stage == "ACTIVATE" and state == "done" and not ticket.get("validation_passed"):
            ticket.setdefault("notes", []).append({
                "text": "Activation blocked: validation has not passed.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._save_ticket(profile, tid, ticket)
            return False

        pipeline = ticket.setdefault("capability_pipeline", self._capability_pipeline_template())
        checkpoints = pipeline.setdefault("checkpoints", {})
        for checkpoint in ("REGISTER", "BUILD", "VALIDATE", "ACTIVATE"):
            checkpoints.setdefault(checkpoint, "pending")
        checkpoints[stage] = state
        pipeline["current"] = stage
        pipeline.setdefault("history", []).append(self._pipeline_event(stage, state, note))
        pipeline["history"] = pipeline["history"][-30:]

        ticket["pipeline_stage"] = stage
        ticket["pipeline_status"] = state
        if evidence:
            ticket.setdefault("pipeline_evidence", []).extend(str(item) for item in evidence if str(item).strip())
        if missing:
            ticket["pipeline_missing"] = [str(item) for item in missing if str(item).strip()]
        if next_action:
            ticket["pipeline_next_action"] = next_action
        self._save_ticket(profile, tid, ticket)
        return True

    def mark_instructions_reviewed(self, profile: str, tid: str, instructions: List[str]) -> bool:
        """Record that the Engineer received and reviewed the full ticket instructions."""
        ticket = self._load_ticket(profile, tid)
        if not ticket:
            return False
        manifest = [str(item) for item in instructions if str(item).strip()]
        ticket["instructions_reviewed"] = True
        ticket["instructions_reviewed_at"] = datetime.now(timezone.utc).isoformat()
        ticket["instruction_manifest"] = manifest
        status = ticket.setdefault("procedure_step_status", {})
        status["1_read_full_ticket"] = "done"
        status["2_classify_and_confirm_scope"] = "done"
        ticket["current_procedure_step"] = "3_inspect_existing_resources"
        pipeline = ticket.setdefault("capability_pipeline", self._capability_pipeline_template())
        checkpoints = pipeline.setdefault("checkpoints", {})
        checkpoints["REGISTER"] = "done"
        pipeline["current"] = "BUILD"
        pipeline.setdefault("history", []).append(
            self._pipeline_event("REGISTER", "done", "Full instructions reviewed.")
        )
        ticket["pipeline_stage"] = "BUILD"
        ticket["pipeline_status"] = "ready"
        ticket.setdefault("notes", []).append({
            "text": f"Engineer reviewed full instruction manifest ({len(manifest)} item(s)).",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save_ticket(profile, tid, ticket)
        return True

    def add_validation_evidence(
        self,
        profile: str,
        tid: str,
        evidence: List[str],
        *,
        passed: bool,
    ) -> bool:
        """Attach validation evidence and decide whether a capability ticket may close."""
        ticket = self._load_ticket(profile, tid)
        if not ticket:
            return False
        clean_evidence = [str(item) for item in evidence if str(item).strip()]
        ticket["tool_tested"] = True
        ticket["validation_passed"] = bool(passed)
        ticket["closure_allowed"] = bool(passed)
        status = ticket.setdefault("procedure_step_status", {})
        status["6_run_fake_local_validation"] = "done" if passed else "failed"
        status["7_run_live_path_validation"] = "done" if passed else "failed"
        status["8_close_or_return_with_evidence"] = "ready_to_close" if passed else "return_open"
        ticket["current_procedure_step"] = "ready_to_close" if passed else "4_build_or_connect_missing_links"
        pipeline = ticket.setdefault("capability_pipeline", self._capability_pipeline_template())
        checkpoints = pipeline.setdefault("checkpoints", {})
        checkpoints["BUILD"] = "done"
        checkpoints["VALIDATE"] = "done" if passed else "failed"
        checkpoints["ACTIVATE"] = "pending" if passed else "blocked"
        pipeline["current"] = "ACTIVATE" if passed else "VALIDATE"
        pipeline.setdefault("history", []).append(
            self._pipeline_event(
                "VALIDATE",
                "done" if passed else "failed",
                "Validation passed." if passed else "Validation failed; activation blocked.",
            )
        )
        ticket["pipeline_stage"] = "ACTIVATE" if passed else "VALIDATE"
        ticket["pipeline_status"] = "validated" if passed else "pending_validation"
        ticket.setdefault("validation_evidence", []).append({
            "passed": bool(passed),
            "items": clean_evidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        ticket.setdefault("notes", []).append({
            "text": (
                "Validation passed; ticket may close."
                if passed
                else "Validation did not pass; ticket must remain open."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save_ticket(profile, tid, ticket)
        return True

    def close_ticket(self, profile: str, tid: str, resolution: str = "") -> bool:
        ticket = self._load_ticket(profile, tid)
        if not ticket: return False
        if str(ticket.get("target", "")).startswith("capability_request:"):
            missing = []
            if not ticket.get("instructions_reviewed"):
                missing.append("full instructions were not reviewed")
            if not ticket.get("tool_tested"):
                missing.append("tool was not tested")
            if not ticket.get("validation_passed"):
                missing.append("validation did not pass")
            if not ticket.get("closure_allowed"):
                missing.append("closure was not authorized")
            if missing:
                ticket.setdefault("notes", []).append({
                    "text": "Closure blocked: " + "; ".join(missing) + ".",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                self._save_ticket(profile, tid, ticket)
                self.log.warn("engineer", f"Ticket #{tid} no puede cerrar: {', '.join(missing)}")
                return False
            pipeline = ticket.setdefault("capability_pipeline", self._capability_pipeline_template())
            checkpoints = pipeline.setdefault("checkpoints", {})
            checkpoints["ACTIVATE"] = "done"
            pipeline["current"] = "ACTIVATE"
            pipeline.setdefault("history", []).append(
                self._pipeline_event("ACTIVATE", "done", "Ticket closed after validation.")
            )
            ticket["pipeline_stage"] = "ACTIVATE"
            ticket["pipeline_status"] = "active"
        ticket["status"] = "closed"; ticket["resolution"] = resolution
        ticket["closed_at"] = datetime.now(timezone.utc).isoformat()
        self._save_ticket(profile, tid, ticket)
        self.log.info("engineer", f"Ticket #{tid} cerrado: {resolution}")
        return True

    def get_profile_tickets(self, profile: str, status: str = "") -> List[dict]:
        tickets = self._iter_tickets(profile)
        if status: return [t for t in tickets if t.get("status") == status]
        return tickets

    def get_all_open(self) -> List[dict]:
        open_tickets = []
        if not self._profiles_dir.is_dir(): return []
        for p_dir in sorted(self._profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                for t in self._iter_tickets(p_dir.name):
                    if t.get("status") not in ("closed", "resolved", "cancelled"):
                        open_tickets.append(t)
        return open_tickets

    def queue(self) -> List[dict]:
        """Returns ALL open tickets across all profiles, sorted by creation time (FIFO).
        The Engineer works through this queue in order."""
        tickets = self.get_all_open()
        tickets.sort(key=lambda t: t.get("created_at", ""))
        return tickets

    def next_ticket(self) -> Optional[dict]:
        """Returns the next ticket to process (oldest open ticket)."""
        q = self.queue()
        return q[0] if q else None

    def show_queue(self, limit: int = 10) -> str:
        """Returns a formatted string of the engineer's current queue."""
        q = self.queue()
        if not q:
            return "  📬 Engineer queue: empty. No pending tickets."
        lines = [f"  📋 ENGINEER QUEUE — {len(q)} open ticket(s)"]
        lines.append(f"  {'─' * 45}")
        for i, t in enumerate(q[:limit], 1):
            created = t.get("created_at", "?")[11:19]  # HH:MM:SS
            status = t.get("status", "?")
            profile = t.get("profile", "?")
            target = t.get("target", "?").split(".")[0][:25]
            sev = t.get("severity", "?")
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
            lines.append(f"  {icon} #{i:2d} [{created}] {status:12s} {profile:10s} {target}")
        if len(q) > limit:
            lines.append(f"  ... and {len(q) - limit} more")
        return "\n".join(lines)

    def get_by_source(self, source: str) -> List[dict]:
        results = []
        if not self._profiles_dir.is_dir(): return []
        for p_dir in sorted(self._profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                for t in self._iter_tickets(p_dir.name):
                    if t.get("source") == source: results.append(t)
        return results

    def get_by_assignee(self, assignee: str) -> List[dict]:
        results = []
        if not self._profiles_dir.is_dir(): return []
        for p_dir in sorted(self._profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                for t in self._iter_tickets(p_dir.name):
                    if t.get("assignee") == assignee: results.append(t)
        return results

    def get_ticket(self, tid: str) -> Optional[dict]:
        if not self._profiles_dir.is_dir(): return None
        for p_dir in sorted(self._profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                t = self._load_ticket(p_dir.name, tid)
                if t: return t
        return None

    def get_all_tickets(self) -> List[dict]:
        all_tickets = []
        if not self._profiles_dir.is_dir(): return []
        for p_dir in sorted(self._profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                all_tickets.extend(self._iter_tickets(p_dir.name))
        return all_tickets

    def get_open(self) -> List[dict]:
        return self.get_all_open()

    def summary(self) -> str:
        all_tickets = self.get_all_tickets()
        total = len(all_tickets)
        open_count = sum(1 for t in all_tickets if t.get("status") not in ("closed", "resolved", "cancelled"))
        profiles = set(t.get("profile", "?") for t in all_tickets)
        return f"{total} tickets, {open_count} abiertos, en {len(profiles)} perfil(es)"

    def disclose_credential(self, credential_type: str, requester: str = "agente") -> dict:
        """Credential Disclosure — the user asks for THEIR credentials.

        The Tower only guards — the credentials belong to the user.
        This method:
          1. Creates a ticket documenting WHO asked and WHAT was requested
          2. Reads the credential from CajaSeguraInfo (the vault)
          3. Returns the credential to the requester
          4. Logs the disclosure for audit

        credential_type: 'api_key' | 'gateway_token' | 'provider_id' | 'all'
        Returns: {ok, credential_type, value, ticket_id, message}
        """
        vault = CajaSeguraInfo.read_slot("principal")
        if not vault:
            return {
                "ok": False,
                "credential_type": credential_type,
                "value": None,
                "ticket_id": None,
                "message": "No hay credenciales guardadas en la CajaSeguraInfo."
            }

        # Crear ticket de auditoría
        tid = self.create_ticket(
            profile="system",
            target=f"credential_disclosure:{credential_type}",
            problem=f"Usuario ({requester}) solicita ver su {credential_type}",
            severity="low",
            source="credential_disclosure"
        )
        self.add_note("system", tid, f"Disclosure solicitado por {requester} para {credential_type}")
        self.close_ticket("system", tid, f"Credencial {credential_type} entregada al usuario")

        # Leer la credencial de la caja fuerte
        if credential_type == "all":
            # Devolver todo excepto datos internos
            safe_vault = {k: v for k, v in vault.items()
                         if not k.startswith("_")}
            # Redactar parcialmente para seguridad en logs
            if "api_key" in safe_vault:
                raw = safe_vault["api_key"]
                safe_vault["api_key"] = raw  # el usuario lo ve completo
            self.log.info("engineer",
                f"Credential disclosure #{tid}: all credentials entregadas a {requester}")
            return {
                "ok": True,
                "credential_type": "all",
                "value": safe_vault,
                "ticket_id": tid,
                "message": f"Todas las credenciales entregadas. Ticket #{tid}."
            }

        if credential_type == "provider_id":
            value = vault.get("provider_id", "")
        elif credential_type in vault:
            value = vault[credential_type]
        else:
            self.log.warn("engineer",
                f"Credential disclosure #{tid}: {credential_type} no encontrado en vault")
            return {
                "ok": False,
                "credential_type": credential_type,
                "value": None,
                "ticket_id": tid,
                "message": f"No se encontró '{credential_type}' en la CajaSeguraInfo."
            }

        self.log.info("engineer",
            f"Credential disclosure #{tid}: {credential_type} entregado a {requester}")
        return {
            "ok": True,
            "credential_type": credential_type,
            "value": value,
            "ticket_id": tid,
            "message": f"Credencial '{credential_type}' entregada. Ticket #{tid}."
        }

    def rotate_credential(self, credential_type: str, new_value: str, requester: str = "agente") -> dict:
        """Credential Rotation — the user provides a NEW credential.

        The Tower is the ONLY one that stores credentials. The Agent only
        passes the key through a ticket. The Centinela only monitors.

        This method:
          1. Creates a rotation ticket for audit
          2. Validates the new credential (test connection)
          3. Stores it in CajaSeguraInfo (LA TOWER guarda)
          4. Closes the rotation ticket AND any related open tickets
          5. Resets Centinela strikes so monitoring starts fresh

        credential_type: 'api_key' | 'gateway_token'
        Returns: {ok, credential_type, ticket_id, message, provider_name}
        """
        vault = CajaSeguraInfo.read_slot("principal")
        if not vault:
            return {
                "ok": False,
                "credential_type": credential_type,
                "ticket_id": None,
                "message": "No hay CajaSeguraInfo — ejecuta el setup primero."
            }

        # Crear ticket de rotación
        tid = self.create_ticket(
            profile="system",
            target=f"credential_rotation:{credential_type}",
            problem=f"Usuario ({requester}) solicita cambiar su {credential_type}",
            severity="medium",
            source="credential_rotation"
        )
        self.add_note("system", tid, f"Rotation started por {requester}")

        # Validar la nueva credencial
        if credential_type == "api_key":
            provider_id = vault.get("provider_id", "")
            ok, msg, status = _provider_api_request(provider_id, new_value)
            if not ok:
                self.add_note("system", tid, f"Validation failed: {msg} (HTTP {status})")
                self.close_ticket("system", tid, f"Rotation cancelled — nueva API key inválida: {msg}")
                return {
                    "ok": False,
                    "credential_type": credential_type,
                    "ticket_id": tid,
                    "message": f"La nueva API key no es válida: {msg}"
                }
            self.add_note("system", tid, f"Conexión validada: {msg}")
        elif credential_type == "gateway_token":
            from urllib.request import Request, urlopen
            from urllib.error import URLError, HTTPError
            try:
                url = f"https://api.telegram.org/bot{new_value}/getMe"
                req = Request(url)
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    if not data.get("ok"):
                        self.add_note("system", tid, "Validation failed: token rejected")
                        self.close_ticket("system", tid, "Rotation cancelled — token inválido")
                        return {
                            "ok": False,
                            "credential_type": credential_type,
                            "ticket_id": tid,
                            "message": "El token de Telegram no es válido."
                        }
                    bot_name = data["result"].get("first_name", "Bot")
                    self.add_note("system", tid, f"Bot '{bot_name}' validado")
            except (HTTPError, URLError, Exception) as e:
                self.add_note("system", tid, f"Validation failed: {e}")
                self.close_ticket("system", tid, f"Rotation cancelled — error: {e}")
                return {
                    "ok": False,
                    "credential_type": credential_type,
                    "ticket_id": tid,
                    "message": f"No se pudo validar el token: {e}"
                }
        else:
            self.close_ticket("system", tid, f"Rotation cancelled — tipo desconocido: {credential_type}")
            return {
                "ok": False,
                "credential_type": credential_type,
                "ticket_id": tid,
                "message": f"Tipo de credencial no soportado: {credential_type}"
            }

        # ── GUARDAR en CajaSeguraInfo (LA TOWER guarda, nadie más) ──
        vault[credential_type] = new_value
        vault["rotated_at"] = datetime.now(timezone.utc).isoformat()
        vault["rotated_by"] = requester
        if credential_type == "api_key":
            provider_id = vault.get("provider_id", "")
            vault["provider_name"] = PROVIDERS.get(provider_id, {}).get("name", provider_id)
        ok = CajaSeguraInfo.write_slot("principal", vault)

        if not ok:
            self.add_note("system", tid, "Error al guardar en CajaSeguraInfo")
            self.close_ticket("system", tid, "Rotation failed — error al guardar")
            return {
                "ok": False,
                "credential_type": credential_type,
                "ticket_id": tid,
                "message": "Error al guardar la nueva credencial en CajaSeguraInfo."
            }

        # Cerrar ticket de rotación
        self.close_ticket("system", tid,
            f"Rotation successful: {credential_type} actualizado en CajaSeguraInfo")

        # ── Cerrar tickets RELACIONADOS abiertos por el Centinela ──
        related = self._find_related_credential_tickets(credential_type)
        for rt in related:
            rt_profile = rt.get("profile", "system")
            rt_tid = rt["id"]
            self.add_note(rt_profile, rt_tid,
                f"Resuelto por rotación de credencial (ticket #{tid})")
            self.close_ticket(rt_profile, rt_tid,
                f"Credencial {credential_type} rotada exitosamente")
            self.log.info("engineer",
                f"Ticket relacionado #{rt_tid} cerrado por rotación")

        provider_name = vault.get("provider_name", "")
        self.log.info("engineer",
            f"Credential rotation #{tid}: {credential_type} actualizado en CajaSeguraInfo")

        return {
            "ok": True,
            "credential_type": credential_type,
            "ticket_id": tid,
            "closed_related": len(related),
            "provider_name": provider_name,
            "message": f"{credential_type} actualizado correctamente en CajaSeguraInfo. "
                       f"Ticket #{tid}. Centinela continues its monitoring."
        }

    def _find_related_credential_tickets(self, credential_type: str) -> List[dict]:
        """Finds open tickets related to a credential (created by Centinela)."""
        related = []
        if credential_type == "api_key":
            search_terms = ["api_key:"]
        elif credential_type == "gateway_token":
            search_terms = ["telegram"]
        else:
            return related
        open_tickets = self.get_all_open()
        for t in open_tickets:
            target = t.get("target", "")
            if t.get("source") == "centinela" and t.get("needs_human"):
                for term in search_terms:
                    if term in target:
                        related.append(t)
                        break
        return related

    def get_credential_tickets_needing_user(self) -> List[dict]:
        """Returns open tickets from Centinela that need user input.

        These are tickets where the Centinela detected:
          - API key invalid/expired
          - Telegram token invalid/revoked
        And the ticket has needs_human=True, waiting for the user.

        The Agent receives these and asks the user for a new credential.
        """
        tickets = []
        open_tickets = self.get_all_open()
        for t in open_tickets:
            if (t.get("source") == "centinela"
                    and t.get("needs_human")
                    and t.get("status") not in ("closed", "resolved", "cancelled")):
                target = t.get("target", "")
                if "api_key" in target or "telegram" in target:
                    tickets.append(t)
        return tickets

    def create_internal_agent(
        self,
        agent_type: str,
        mode: str = "collaborative",
        name: str = "",
        mission: str = "",
        requester: str = "agente",
        factory_create_fn: callable = None,
    ) -> dict:
        """Create an internal agent through the Factory.

        This is the bridge between the DIGOS ticket system and the Factory.
        The user says "crea 2 builders en modo aislado" and the Agent routes
        the request here. The SystemEngineer creates an audit ticket, then
        delegates to the Factory (via factory_create_fn callback).

        agent_type: 'builder' | 'auditor' | 'reviewer'
        mode: ☑️ 'collaborative' | ☑️ 'isolated'
        factory_create_fn: callback that does the actual creation in the Factory

        Returns: {ok, agent_name, agent_type, mode, ticket_id, message}
        """
        if agent_type not in ("builder", "auditor", "reviewer"):
            return {
                "ok": False,
                "agent_name": None,
                "agent_type": agent_type,
                "mode": mode,
                "ticket_id": None,
                "message": f"Tipo de agente desconocido: {agent_type}. Usa builder, auditor, o reviewer."
            }

        if mode not in ("collaborative", "isolated"):
            return {
                "ok": False,
                "agent_name": None,
                "agent_type": agent_type,
                "mode": mode,
                "ticket_id": None,
                "message": f"Modo desconocido: {mode}. Usa 'collaborative' o 'isolated'."
            }

        # Crear ticket de auditoría
        tid = self.create_ticket(
            profile="system",
            target=f"internal_agent:{agent_type}",
            problem=f"Usuario ({requester}) solicita crear agente interno: {agent_type} ({mode})",
            severity="low",
            source="agent_creation"
        )

        agent_name = name or f"{agent_type}_{tid.split('-')[0]}"

        # Delegar a la Factoría (via callback)
        if factory_create_fn is None:
            self.add_note("system", tid, "Factory no disponible — callback no configurado")
            return {
                "ok": False,
                "agent_name": agent_name,
                "agent_type": agent_type,
                "mode": mode,
                "ticket_id": tid,
                "message": "La Factory is not available en este momento."
            }

        try:
            agent = factory_create_fn(agent_type, mode, agent_name, mission)
        except Exception as e:
            self.add_note("system", tid, f"Error creando agente en Factory: {e}")
            self.close_ticket("system", tid, f"Fallo — Factory no pudo crear el agente: {e}")
            return {
                "ok": False,
                "agent_name": agent_name,
                "agent_type": agent_type,
                "mode": mode,
                "ticket_id": tid,
                "message": f"Error creating el agente en la Factoría: {e}"
            }

        if agent is None:
            self.add_note("system", tid, "Factory devolvió None — tipo de agente no soportado")
            self.close_ticket("system", tid, "Fallo — tipo de agente no soportado")
            return {
                "ok": False,
                "agent_name": agent_name,
                "agent_type": agent_type,
                "mode": mode,
                "ticket_id": tid,
                "message": f"No se pudo crear el agente tipo '{agent_type}'."
            }

        # Éxito
        actual_name = agent.name
        self.add_note("system", tid,
            f"Agente '{actual_name}' ({agent_type}, {mode}) creado en la Factoría")
        self.close_ticket("system", tid,
            f"Agente '{actual_name}' ({agent_type}, {mode}) creado exitosamente")
        self.log.info("engineer",
            f"Internal agent created: {actual_name} ({agent_type}, {mode}), ticket #{tid}")

        return {
            "ok": True,
            "agent_name": actual_name,
            "agent_type": agent_type,
            "mode": mode,
            "ticket_id": tid,
            "message": f"Agente '{actual_name}' ({agent_type}) creado en modo {mode}. Ticket #{tid}."
        }

    def create_capability_request(
        self,
        capability: str,
        family: str,
        sub_intent: str,
        user_message: str,
        requester: str = "agente",
        instructions: Optional[List[str]] = None,
    ) -> dict:
        """Create a ticket for a new capability detected via intent classification.

        When the AIAgent detects a capability gap (e.g., user wants voice but we
        don't have STT), this method creates an audit ticket and records the
        request for the Factory to process.

        capability: e.g., "stt_audio_input", "web_browsing"
        family: e.g., "VOICE", "WEB", "NEW_TOOL"
        sub_intent: e.g., "VOICE_INPUT_CAPABILITY_REQUEST"
        user_message: the original user message that triggered this

        Returns: {ok, ticket_id, capability, message}
        """
        profile = self._safe_profile(requester or "agente")
        tid = self.create_ticket(
            profile=profile,
            target=f"capability_request:{capability}",
            problem=(
                f"Solicitante ({requester}) quiere una capacidad que no existe.\n"
                f"Familia: {family}\n"
                f"Sub-intención: {sub_intent}\n"
                f"Mensaje original: {user_message[:200]}"
            ),
            severity="medium",
            source="intent_classifier"
        )
        ticket = self._load_ticket(profile, tid)
        if ticket:
            ticket["closure_requirements"] = {
                "must_read_all_instructions": True,
                "must_test_tool_before_delivery": True,
                "must_keep_ticket_open_until_validation_passes": True,
            }
            ticket["capability_pipeline"] = self._capability_pipeline_template()
            ticket["capability_pipeline"]["history"].append(
                self._pipeline_event("REGISTER", "created", "Capability request ticket created.")
            )
            ticket["pipeline_stage"] = "REGISTER"
            ticket["pipeline_status"] = "created"
            ticket["required_procedure_steps"] = self._capability_procedure_steps()
            ticket["current_procedure_step"] = "1_read_full_ticket"
            ticket["procedure_step_status"] = {
                step["id"]: "pending" for step in ticket["required_procedure_steps"]
            }
            ticket["instruction_manifest"] = [
                str(item) for item in (instructions or []) if str(item).strip()
            ]
            ticket["instructions_reviewed"] = False
            ticket["tool_tested"] = False
            ticket["validation_passed"] = False
            ticket["closure_allowed"] = False
            ticket["validation_evidence"] = []
            self._save_ticket(profile, tid, ticket)
        self.add_note(profile, tid,
            f"Capability gap detectado: {capability} ({family}/{sub_intent})")
        self.log.info("engineer",
            f"Capability request #{tid}: {capability} ({family}) — {sub_intent}")

        return {
            "ok": True,
            "ticket_id": tid,
            "profile": profile,
            "capability": capability,
            "family": family,
            "sub_intent": sub_intent,
            "message": f"Solicitud de capacidad '{capability}' registrada. Ticket #{tid}."
        }

    def resolve(self, tid: str, resolution: str):
        ticket = self.get_ticket(tid)
        if ticket:
            profile = ticket.get("profile", "")
            if profile: self.close_ticket(profile, tid, resolution)
