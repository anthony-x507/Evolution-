"""
onboarding.py — Onboarding Flow
================================
Guides the user through first-time setup:
language → adoption → API key → gateway → vault → finalize → handoff

Extracted from TorreDeControl to keep each class focused on ONE job.
"""

import json
import os
import sys
import time
import getpass
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Tuple

from digos_lib.constants import (
    VERSION, DIGOS_DIR, LANGUAGES, PROVIDERS, GATEWAYS,
    SYSTEM_IDENTITY, IDENTITY_RESPONSES,
)
from digos_lib.core_vault import CajaSeguraInfo
from digos_lib.terminal_presentation import print_startup_banner


class OnboardingFlow:
    """Guides the user through first-time system setup.

    Each step is a method. The tower calls start() and gets back
    the configured state. Onboarding does NOT orchestrate — it guides.
    """

    def __init__(self, tower_ref):
        """tower_ref: reference to TorreDeControl for state save and agent birth."""
        self._tower = tower_ref
        self.lang = "en"
        self.state = tower_ref.state if hasattr(tower_ref, 'state') else {}
        self.log = tower_ref._log if hasattr(tower_ref, '_log') else None

    _COPY = {
        "en": {
            "select_language": "Select your language -> ",
            "invalid_option": "  Invalid option. Try again.",
            "existing_systems": "🔄 ADOPTION — EXISTING SYSTEMS DETECTED",
            "detected": "  📡 Detected: {label}",
            "see_imports": "Do you want to see what can be imported?",
            "skip_adoption": "  Skipping adoption. You can migrate later manually.",
            "exploring": "\n  ── Exploring {label} ──",
            "nothing_found": "  📭 Nothing found to import from {label}",
            "proceed_migration": "\n  Proceed with migration?",
            "migration_cancelled": "  Migration of {label} cancelled.",
            "blocked_files": "  ⚠️  Detected {count} blocked file(s) in the source.",
            "continue_migration": "Continue with migration? (some files may be skipped)",
            "migration_cancelled_security": "  Migration cancelled for security.",
            "cleaned_files": "  ⚠️  {count} file(s) will be cleaned during migration.",
            "source_clean": "  ✅ Source clean — no findings.",
            "migrating": "\n  ⏳ Migrating {label}...",
            "migrated": "  ✅ {count} item(s) migrated",
            "scanning_profiles": "\n  🔍 Scanning adopted profiles...",
            "transforming_profiles": "  🔄 Transforming profiles...",
            "adoption_complete": "\n  ✅ Adoption of {label} completed.",
            "provider_title": "🔑 AI PROVIDER",
            "choose_provider": "  Choose the provider for your principal agent:",
            "imported_api": "  🔑 Using imported API Key: {provider}",
            "provider_prompt": "Provider -> ",
            "back_language": "  Returning to language selection...",
            "invalid_back": "  Invalid option. Type a number, or 'back' to go back.",
            "provider_selected": "\n  -> Provider: {provider}",
            "api_key_prompt": "  Enter your {provider} API Key:\n  -> ",
            "api_key_empty": "  The API Key cannot be empty.",
            "testing_provider": "\n  🔍 Testing connection to {provider}...",
            "continue_anyway": "  Continue anyway? (y/N): ",
            "try_key_again": "  Try again with a different API Key, or type 'back' to change provider.",
            "try_again_prompt": "  Try again? (y/back): ",
            "provider_success": "Connection successful.",
            "invalid_api_key": "Invalid API Key (HTTP {status}).",
            "provider_connect_error": "Could not connect: {msg}",
            "agent_born": "\n  🎯 PRINCIPAL AGENT HAS BEEN BORN!",
            "agent_label": "Agent",
            "provider_label": "Provider",
            "kendo_label": "Kendo",
            "active": "Active",
            "inactive": "Inactive",
            "using_imported_gateway": "  📡 Using imported gateway: {gateway}",
            "gateway_title": "📡 GATEWAY / COMMUNICATION CHANNEL",
            "choose_gateway": "  Choose how your agent will communicate:",
            "gateway_prompt": "Gateway -> ",
            "back_api": "  Returning to API key setup...",
            "gateway_selected": "\n  -> Gateway: {gateway}",
            "manual_setup": "  ⏳ {gateway} requires manual setup.",
            "mark_later": "  Mark as configured later? (y/N): ",
            "telegram_token_title": "  🤖 Telegram Bot Token",
            "telegram_hint": "  (Get it from @BotFather on Telegram)",
            "bot_token_prompt": "  Bot Token -> ",
            "token_empty": "  The token cannot be empty.",
            "testing_telegram": "\n  🔍 Testing Telegram connection...",
            "telegram_success": "Bot '{bot_name}' (@{username}) connected.",
            "invalid_token": "Invalid token.",
            "token_rejected": "Token rejected (HTTP {code}).",
            "telegram_connect_error": "Could not connect: {msg}",
            "handoff_title": "  ║     🚀  HANDOFF COMPLETED             ║",
            "handoff_line_1": "  ║  Control Tower hands control          ║",
            "handoff_line_2": "  ║  to the Principal Agent.             ║",
            "handoff_line_3": "  ║  TOWER: Sentinel + Engineer active    ║",
            "gateway_label": "Gateway",
            "status_label": "Status",
            "agent_ready": "  The agent is ready to receive instructions.",
            "tower_monitors": "  TOWER monitors in the background.",
            "start_daemon": "  Start DIGOS in 24/7 mode?",
            "starting_daemon": "\n  🚀 Starting daemon mode...",
            "use_daemon": "  Use: digos --daemon to start 24/7 mode",
        },
        "es": {
            "select_language": "Elige tu idioma -> ",
            "invalid_option": "  Opción inválida. Intenta otra vez.",
            "existing_systems": "🔄 ADOPCIÓN — SISTEMAS EXISTENTES DETECTADOS",
            "detected": "  📡 Detectado: {label}",
            "see_imports": "¿Quieres ver qué se puede importar?",
            "skip_adoption": "  Omitiendo adopción. Puedes migrar después manualmente.",
            "exploring": "\n  ── Explorando {label} ──",
            "nothing_found": "  📭 No encontré nada para importar desde {label}",
            "proceed_migration": "\n  ¿Continuar con la migración?",
            "migration_cancelled": "  Migración de {label} cancelada.",
            "blocked_files": "  ⚠️  Detecté {count} archivo(s) bloqueado(s) en el origen.",
            "continue_migration": "¿Continuar con la migración? (algunos archivos pueden omitirse)",
            "migration_cancelled_security": "  Migración cancelada por seguridad.",
            "cleaned_files": "  ⚠️  {count} archivo(s) se limpiarán durante la migración.",
            "source_clean": "  ✅ Origen limpio — sin hallazgos.",
            "migrating": "\n  ⏳ Migrando {label}...",
            "migrated": "  ✅ {count} elemento(s) migrado(s)",
            "scanning_profiles": "\n  🔍 Revisando perfiles adoptados...",
            "transforming_profiles": "  🔄 Transformando perfiles...",
            "adoption_complete": "\n  ✅ Adopción de {label} completada.",
            "provider_title": "🔑 PROVEEDOR DE IA",
            "choose_provider": "  Elige el proveedor para tu agente principal:",
            "imported_api": "  🔑 Usando API Key importada: {provider}",
            "provider_prompt": "Proveedor -> ",
            "back_language": "  Volviendo a selección de idioma...",
            "invalid_back": "  Opción inválida. Escribe un número o 'atrás' para volver.",
            "provider_selected": "\n  -> Proveedor: {provider}",
            "api_key_prompt": "  Introduce tu API Key de {provider}:\n  -> ",
            "api_key_empty": "  La API Key no puede estar vacía.",
            "testing_provider": "\n  🔍 Probando conexión con {provider}...",
            "continue_anyway": "  ¿Continuar de todos modos? (s/N): ",
            "try_key_again": "  Puedes intentar con otra API Key o escribir 'atrás' para cambiar proveedor.",
            "try_again_prompt": "  ¿Intentar otra vez? (s/atrás): ",
            "provider_success": "Conexión correcta.",
            "invalid_api_key": "API Key inválida (HTTP {status}).",
            "provider_connect_error": "No pude conectar: {msg}",
            "agent_born": "\n  🎯 EL AGENTE PRINCIPAL QUEDÓ CREADO",
            "agent_label": "Agente",
            "provider_label": "Proveedor",
            "kendo_label": "Kendo",
            "active": "Activo",
            "inactive": "Inactivo",
            "using_imported_gateway": "  📡 Usando canal importado: {gateway}",
            "gateway_title": "📡 CANAL DE COMUNICACIÓN",
            "choose_gateway": "  Elige cómo se comunicará tu agente:",
            "gateway_prompt": "Canal -> ",
            "back_api": "  Volviendo a configuración de API Key...",
            "gateway_selected": "\n  -> Canal: {gateway}",
            "manual_setup": "  ⏳ {gateway} requiere configuración manual.",
            "mark_later": "  ¿Marcar como configurado después? (s/N): ",
            "telegram_token_title": "  🤖 Token del bot de Telegram",
            "telegram_hint": "  (Consíguelo en @BotFather en Telegram)",
            "bot_token_prompt": "  Token del bot -> ",
            "token_empty": "  El token no puede estar vacío.",
            "testing_telegram": "\n  🔍 Probando conexión con Telegram...",
            "telegram_success": "Bot '{bot_name}' (@{username}) conectado.",
            "invalid_token": "Token inválido.",
            "token_rejected": "Token rechazado (HTTP {code}).",
            "telegram_connect_error": "No pude conectar: {msg}",
            "handoff_title": "  ║     🚀  ENTREGA COMPLETADA             ║",
            "handoff_line_1": "  ║  La Torre de Control entrega           ║",
            "handoff_line_2": "  ║  al agente principal.                 ║",
            "handoff_line_3": "  ║  TORRE: Centinela + Ingeniero activos  ║",
            "gateway_label": "Canal",
            "status_label": "Estado",
            "agent_ready": "  El agente está listo para recibir instrucciones.",
            "tower_monitors": "  La Torre monitorea en segundo plano.",
            "start_daemon": "  ¿Iniciar DIGOS en modo 24/7?",
            "starting_daemon": "\n  🚀 Iniciando modo 24/7...",
            "use_daemon": "  Usa: digos --daemon para iniciar el modo 24/7",
        },
    }

    def _copy(self) -> dict:
        return self._COPY.get(self.lang, self._COPY["en"])

    def _txt(self, key: str, **kwargs) -> str:
        text = self._copy().get(key, self._COPY["en"][key])
        return text.format(**kwargs)

    def _yes(self, raw: str) -> bool:
        return raw.strip().lower() in ("y", "yes", "s", "si", "sí")

    def _back(self, raw: str) -> bool:
        return raw.strip().lower() in ("back", "atrás", "atras")

    # ── ENTRY POINT ──────────────────────────────

    def start(self):
        """Run the complete onboarding flow."""
        self._show_banner()
        self._step_language()
        self._step_adoption()
        self._step_api_key_with_provider()
        self._step_gateway_with_token()
        self._step_vault()
        self._finalize_setup()
        # Note: _handoff() is called by TorreDeControl.run() — not here.

    # ── BANNER ───────────────────────────────────

    def _show_banner(self):
        print_startup_banner(
            system_name="MASTER",
            tagline="Organized Home for Useful Intelligence",
            welcome="Bienvenido. Vamos a configurar MASTER.",
        )

    # ── STEP 1: LANGUAGE ──────────────────────────

    def _step_language(self):
        print("🌐 LANGUAGE / IDIOMA")
        print("─" * 40)
        for k, v in LANGUAGES.items():
            print(f"  [{k}] {v['name']}")
        print()
        while True:
            choice = input(self._txt("select_language")).strip()
            if choice in LANGUAGES:
                self.lang = LANGUAGES[choice]["code"]
                if hasattr(self._tower, 'lang'):
                    self._tower.lang = self.lang
                self.state["language"] = self.lang
                self._tower._save_state()
                print()
                print(f"  {LANGUAGES[choice]['welcome']}")
                print()
                return
            print(self._txt("invalid_option"))

    # ── STEP 2: ADOPTION ──────────────────────────

    def _step_adoption(self):
        """Detect and migrate from Hermes/OpenClaw."""
        from adoption import AdoptionEngine, TransformationEngine
        from security import CajaSegura as SecurityCaja

        engine = AdoptionEngine()
        transformer = TransformationEngine()
        sources = engine.detect_sources()

        if not sources:
            return

        print()
        print(self._txt("existing_systems"))
        print("━" * 45)
        source_labels = {"hermes": "Hermes Agent", "openclaw": "Open Cloud"}
        for s in sources:
            label = source_labels.get(s, s)
            print(self._txt("detected", label=label))
        print()

        if not self._confirm(self._txt("see_imports")):
            print(self._txt("skip_adoption"))
            return

        for source in sources:
            label = source_labels.get(source, source)
            print(self._txt("exploring", label=label))
            engine.discover(source)
            if not engine._report.items_migrated:
                print(self._txt("nothing_found", label=label))
                continue
            engine.print_preview(engine._report)

            if not self._confirm(self._txt("proceed_migration")):
                print(self._txt("migration_cancelled", label=label))
                continue

            self._run_migration(source, engine, transformer, label)

    def _run_migration(self, source, engine, transformer, label):
        """Run migration for a single source."""
        from security import CajaSegura as SecurityCaja
        caja_pre = SecurityCaja()
        source_paths = {
            "hermes": Path.home() / ".hermes",
            "openclaw": Path.home() / ".openclaw",
        }
        src = source_paths.get(source)

        if src and src.exists():
            pre_report = caja_pre.scan_profile(src)
            if pre_report.items_blocked > 0:
                print(self._txt("blocked_files", count=pre_report.items_blocked))
                caja_pre.print_scan_report(pre_report)
                if not self._confirm(self._txt("continue_migration")):
                    print(self._txt("migration_cancelled_security"))
                    return
            elif pre_report.items_cleaned > 0:
                print(self._txt("cleaned_files", count=pre_report.items_cleaned))
            else:
                print(self._txt("source_clean"))

        # Phase 1: Migrate files
        print(self._txt("migrating", label=label))
        migrated = engine.migrate(source)
        print(self._txt("migrated", count=len(migrated)))

        # Phase 2: Scan adopted profiles for injection
        print(self._txt("scanning_profiles"))
        for profile_dir in Path(DIGOS_DIR / "profiles").iterdir():
            if profile_dir.is_dir():
                caja_pre.scan_profile(profile_dir)

        # Phase 3: Transform
        print(self._txt("transforming_profiles"))
        transformer.transform_all(Path(DIGOS_DIR / "profiles"))

        print(self._txt("adoption_complete", label=label))

    def _confirm(self, question: str, default: bool = True) -> bool:
        """Asks the user for Yes/No confirmation."""
        if self.lang == "es":
            prompt = " (S/n): " if default else " (s/N): "
        else:
            prompt = " (Y/n): " if default else " (y/N): "
        raw = input(question + prompt).strip().lower()
        if not raw:
            return default
        return self._yes(raw)

    @staticmethod
    def _extract_adopted_env(item, var_name: str) -> str:
        """Extracts the value of a .env variable from migrated items."""
        from adoption import TRANSFORMED_DATA
        data = TRANSFORMED_DATA
        for d in data:
            if d.get("item_type") == "env_var" and d.get("var_name") == var_name and d.get("value"):
                return d["value"]
        return ""

    # ── STEP 3: API KEY ───────────────────────────

    def _step_api_key_with_provider(self):
        """Choose provider and enter API key."""
        print(self._txt("provider_title"))
        print("─" * 40)
        print(self._txt("choose_provider"))
        print()
        for k, v in PROVIDERS.items():
            print(f"  [{k}] {v['name']}  ({v['key_hint']})")
        print()

        # Check if credentials already exist in vault
        imported = CajaSeguraInfo.read_slot("principal") or {}
        imported_key = imported.get("api_key", "")
        imported_provider = imported.get("provider_id", "")
        if imported_key and imported_provider:
            provider = PROVIDERS.get(imported_provider, {})
            print(self._txt("imported_api", provider=provider.get('name', imported_provider)))
            print()
            self._provider_id = imported_provider
            self._api_key = imported_key
            self._birth_agent(imported_provider)
            return

        provider_id = None
        while provider_id is None:
            choice = input(self._txt("provider_prompt")).strip().lower()
            if choice in PROVIDERS:
                provider_id = choice
            elif self._back(choice):
                print(self._txt("back_language"))
                self._step_language()
                return self._step_api_key_with_provider()
            else:
                print(self._txt("invalid_back"))

        provider = PROVIDERS[provider_id]
        print(self._txt("provider_selected", provider=provider["name"]))
        print()

        api_key = None
        while api_key is None:
            raw = getpass.getpass(self._txt("api_key_prompt", provider=provider["name"]))
            if raw:
                api_key = raw
            else:
                print(self._txt("api_key_empty"))

        # Connection test
        print(self._txt("testing_provider", provider=provider["name"]))
        ok, msg = self._test_provider(provider_id, api_key)
        if ok:
            print(f"  ✅ {msg}")
        else:
            print(f"  ⚠️  {msg}")
            cont = input(self._txt("continue_anyway")).strip().lower()
            if not self._yes(cont):
                print(self._txt("try_key_again"))
                again = input(self._txt("try_again_prompt")).strip().lower()
                if self._back(again):
                    return self._step_api_key_with_provider()
                return self._step_api_key_with_provider()

        print()
        self._provider_id = provider_id
        self._api_key = api_key
        self._birth_agent(provider_id)

    def _test_provider(self, provider_id: str, api_key: str) -> Tuple[bool, str]:
        from digos_lib.provider_api import _provider_api_request
        ok, msg, status = _provider_api_request(provider_id, api_key)
        if ok:
            return True, self._txt("provider_success")
        if status in (401, 403):
            return False, self._txt("invalid_api_key", status=status)
        return False, self._txt("provider_connect_error", msg=msg)

    def _birth_agent(self, provider_id: str):
        """Creates the agent record (born in state)."""
        provider = PROVIDERS[provider_id]
        agente = {
            "name": "Principal Agent",
            "born_at": datetime.now(timezone.utc).isoformat(),
            "version": VERSION,
            "provider_id": provider_id,
            "provider_name": provider["name"],
            "language": self.lang,
            "self_awareness": {
                "identity": "MASTER Product Agent",
                "version": VERSION,
                "born": datetime.now(timezone.utc).isoformat(),
                "purpose": "Serve the user as an intelligent agent."
            },
            "gps": {
                "origin": "Control Tower",
                "home": str(DIGOS_DIR),
                "state": "being-born"
            },
            "work_destination": {"mode": "onboarding"},
            "kendo": {
                "type": "safety_candle",
                "rules": [
                    "Protect user credentials",
                    "Never execute commands without authorization",
                    "Report suspicious activity",
                    "Maintain system integrity"
                ],
                "active": True
            }
        }
        self.state["agente"] = agente
        self._tower._save_state()
        print(self._txt("agent_born"))
        agent_name = "Agente Principal" if self.lang == "es" else agente["name"]
        print(f"     {self._txt('agent_label')}:    {agent_name}")
        print(f"     {self._txt('provider_label')}: {provider['name']}")
        kendo_status = self._txt("active") if agente["kendo"]["active"] else self._txt("inactive")
        print(f"     {self._txt('kendo_label')}:    {'✅' if agente['kendo']['active'] else '❌'} {kendo_status}")
        print()

    # ── STEP 4: GATEWAY ───────────────────────────

    def _step_gateway_with_token(self):
        """Choose gateway and enter token if needed."""
        # Check if already in vault
        imported = CajaSeguraInfo.read_slot("principal") or {}
        imported_gw_token = imported.get("gateway_token", "")
        imported_gw_type = imported.get("gateway_type", "")

        if imported_gw_token and imported_gw_type:
            print(self._txt("using_imported_gateway", gateway=imported_gw_type))
            print()
            self._gateway_id = imported_gw_type
            self._gateway_token = imported_gw_token
            return

        print(self._txt("gateway_title"))
        print("─" * 40)
        print(self._txt("choose_gateway"))
        print()
        for k, v in GATEWAYS.items():
            name = v["name"]
            note = v.get("note", "")
            note_str = f" — {note}" if note else ""
            print(f"  [{k}] {name}{note_str}")
        print()

        gateway_id = None
        while gateway_id is None:
            choice = input(self._txt("gateway_prompt")).strip().lower()
            if choice in GATEWAYS:
                gateway_id = choice
            elif self._back(choice):
                print(self._txt("back_api"))
                return self._step_api_key_with_provider()
            else:
                print(self._txt("invalid_back"))

        gateway = GATEWAYS[gateway_id]
        print(self._txt("gateway_selected", gateway=gateway["name"]))
        print()

        token = ""
        if gateway["type"] == "telegram":
            token = self._setup_telegram()
        else:
            print(self._txt("manual_setup", gateway=gateway["name"]))
            print(f"     {gateway.get('note', '')}")
            cont = input(self._txt("mark_later")).strip().lower()
            if not self._yes(cont):
                return self._step_gateway_with_token()

        print()
        self._gateway_id = gateway_id
        self._gateway_token = token

    def _setup_telegram(self) -> str:
        print(self._txt("telegram_token_title"))
        print(self._txt("telegram_hint"))
        print()

        token = None
        while token is None:
            import getpass
            raw = getpass.getpass(self._txt("bot_token_prompt")).strip()
            if raw:
                token = raw
            else:
                print(self._txt("token_empty"))

        print(self._txt("testing_telegram"))
        ok, msg = self._test_telegram(token)
        if ok:
            print(f"  ✅ {msg}")
            return token
        else:
            print(f"  ⚠️  {msg}")
            cont = input(self._txt("continue_anyway")).strip().lower()
            if self._yes(cont):
                return token
            return self._setup_telegram()

    def _test_telegram(self, token: str) -> Tuple[bool, str]:
        from urllib.request import urlopen
        from urllib.error import HTTPError, URLError
        import json as _json
        url = f"https://api.telegram.org/bot{token}/getMe"
        try:
            with urlopen(url, timeout=10) as resp:
                data = _json.loads(resp.read().decode())
                if data.get("ok") and "result" in data:
                    bot_name = data["result"].get("first_name", "Bot")
                    username = data["result"].get("username", "?")
                    return True, self._txt("telegram_success", bot_name=bot_name, username=username)
                return False, self._txt("invalid_token")
        except HTTPError as e:
            return False, self._txt("token_rejected", code=e.code)
        except Exception as e:
            return False, self._txt("telegram_connect_error", msg=e)

    # ── STEP 5: VAULT ─────────────────────────────

    def _step_vault(self):
        """Save credentials to encrypted vault."""
        api_key = getattr(self, '_api_key', '')
        gateway_token = getattr(self, '_gateway_token', '')
        provider_id = getattr(self, '_provider_id', '')
        gateway_id = getattr(self, '_gateway_id', '')

        slot = {"api_key": api_key, "gateway_token": gateway_token,
                "provider_id": provider_id, "gateway_type": gateway_id}
        ok = CajaSeguraInfo.write_slot("principal", slot)
        if ok:
            self._tower._log.info("onboarding", "Credentials saved to encrypted vault")
        else:
            self._tower._log.warn("onboarding", "Failed to save credentials to vault")

    # ── STEP 6: FINALIZE ──────────────────────────

    def _finalize_setup(self):
        """Complete the setup and hand off to the agent."""
        self.state["setup_complete"] = True
        self.state["language"] = self.lang
        if hasattr(self._tower, '_save_state'):
            self._tower._save_state()
        self._tower._log.info("onboarding", "Setup complete, agent ready")

    # ── HANDOFF ───────────────────────────────────

    def _handoff(self):
        """Hands control to the principal agent via the tower."""
        agente = self.state.get("agente", {})
        print("  ╔══════════════════════════════════════╗")
        print(self._txt("handoff_title"))
        print("  ║                                      ║")
        print(self._txt("handoff_line_1"))
        print(self._txt("handoff_line_2"))
        print(self._txt("handoff_line_3"))
        print("  ╚══════════════════════════════════════╝")
        print()
        agent_name = "Agente Principal" if self.lang == "es" else agente.get("name", "Principal")
        print(f"     {self._txt('agent_label')}:    {agent_name}")
        print(f"     {self._txt('provider_label')}: {agente.get('provider_name', '?')}")
        print(f"     {self._txt('gateway_label')}:  {agente.get('gateway_type', '?')}")
        print(f"     {self._txt('status_label')}:   ✅ {self._txt('active')}")
        print()
        print(self._txt("agent_ready"))
        print(self._txt("tower_monitors"))
        print()

        # Prompt to start daemon mode
        if sys.stdin.isatty():
            if self._confirm(self._txt("start_daemon")):
                print(self._txt("starting_daemon"))
                self._tower._running = True
                self._tower._daemon_mode = True
                self._tower._self_awareness.activate()
                self._tower._init_agent()
                self._tower._schedule_nightly_cycle()
                self._tower._run_daemon()
            else:
                print(self._txt("use_daemon"))
                print()
