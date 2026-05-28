"""
gateway_manager.py — Gateway Manager
=====================================
Manages all communication gateways (Telegram, CLI) and the
transparency tracker (ToolProgressTracker).

Responsibilities:
- Register and start gateways
- Poll incoming messages from gateways
- Health check all gateways
- Transparency (tool progress + typing indicators)
- Gateway status display

Part of the orchestra — does ONE thing and does it well.
"""

import time
import sys
from typing import Optional, Dict

from digos_lib.core_gateways import BaseGateway, GatewayCLI, GatewayTelegram
from digos_lib.core_vault import CajaSeguraInfo
from transparency import ToolProgressTracker


class GatewayManager:
    """Manages gateways and transparency for the system."""

    MAX_RETRIES = 3
    RETRY_DELAY = 30  # seconds between retry attempts

    def __init__(self, log_keeper, daemon_mode: bool = False):
        self._log = log_keeper
        self._daemon_mode = daemon_mode
        self._gateways: Dict[str, BaseGateway] = {}
        self._tracker: Optional[ToolProgressTracker] = None
        self._state_ref = None  # reference to tower's state (for chat_id)
        self._retry_count: Dict[str, int] = {}
        self._last_retry: Dict[str, float] = {}

    def set_state_ref(self, state_ref: dict):
        """Sets a reference to the tower's state for reading active_chat_id."""
        self._state_ref = state_ref

    # ── INIT ────────────────────────────────────────

    def init_gateways(self):
        """Initializes gateways from CajaSeguraInfo vault.
        In daemon mode CLI does NOT start (would block the loop)."""
        vault = CajaSeguraInfo.read_slot("principal")
        if not vault:
            return

        gw_token = vault.get("gateway_token", "")

        # CLI gateway: register but do NOT start in daemon mode
        cli = GatewayCLI()
        cli.set_logger(self._log)
        self.register(cli)
        if not self._daemon_mode:
            cli.start()

        # Telegram if token available
        if gw_token:
            tg = GatewayTelegram(gw_token)
            tg.set_logger(self._log)
            self.register(tg)
            tg.start()

    def register(self, gateway: BaseGateway):
        """Registers a gateway. Connects transparency if Telegram."""
        self._gateways[gateway.id] = gateway
        self._init_transparency()

    # ── TRANSPARENCY ─────────────────────────────────

    def _init_transparency(self):
        """Initializes the progress tracker. Connects to Telegram gateway if available."""
        if self._tracker is not None:
            return

        tg_gw = self._gateways.get("telegram")
        if not tg_gw or not tg_gw._token:
            return

        chat_id = ""
        if self._state_ref:
            chat_id = self._state_ref.get("active_chat_id", "")

        self._tracker = ToolProgressTracker(
            send_fn=tg_gw.send_message,
            edit_fn=tg_gw.edit_message,
            delete_fn=tg_gw.delete_message,
            action_fn=tg_gw.send_chat_action,
            chat_id=chat_id,
            mode="new",
        )

    def emit_tool_progress(self, tool_name: str, args: Optional[Dict] = None):
        """Called when the agent starts a tool."""
        if self._tracker is not None:
            self._tracker.on_tool_start(tool_name, args or {})

    def emit_tool_end(self, tool_name: str):
        """Called when the agent finishes a tool."""
        if self._tracker is not None:
            self._tracker.on_tool_end(tool_name)

    def emit_assistant_message(self, text: str):
        """Called when the model generates text between tools."""
        if self._tracker is not None:
            self._tracker.on_assistant_message(text)

    def set_active_chat(self, chat_id: str):
        """Updates the active chat for the tracker."""
        if self._state_ref is not None:
            self._state_ref["active_chat_id"] = chat_id
        if self._tracker is not None:
            self._tracker._chat_id = chat_id

    def clear_progress(self):
        """Clears the progress message before sending the final answer."""
        if self._tracker is not None:
            self._tracker.clear()

    # ── POLLING ──────────────────────────────────────

    def poll_messages(self, process_fn=None):
        """Polls all gateways for incoming messages.
        
        Args:
            process_fn: callable(chat_id, text) — called for each message.
                        If None, returns list of (chat_id, text) tuples.
        Returns:
            List of (chat_id, text) tuples if process_fn is None.
        """
        tg_gw = self._gateways.get("telegram")
        if not tg_gw or tg_gw.status != "running":
            return []

        messages = tg_gw.poll_updates()
        results = []

        for msg in messages:
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = msg.get("text", "").strip()

            if not chat_id:
                continue

            if not text:
                tg_gw.send_message(
                    "Por ahora solo puedo procesar mensajes de texto. "
                    "La función de voz todavía no está activa.",
                    chat_id=chat_id,
                )
                continue

            results.append((chat_id, text))

            if process_fn:
                process_fn(chat_id, text)

        return results

    # ── HEALTH ───────────────────────────────────────

    def health_check(self):
        """Checks health of all registered gateways. Auto-reconnects failed ones."""
        failed = []
        for gw_id, gw in self._gateways.items():
            try:
                ok = gw.health_check()
                if not ok:
                    self._log.warn("gateway", f"Gateway {gw_id} — health check failed")
                    failed.append(gw_id)
                    gw.status = "error"
                    self._auto_reconnect(gw_id)
                else:
                    # Reset retry count on success
                    self._retry_count[gw_id] = 0
                    if gw.status == "error":
                        gw.status = "running"
                        self._log.info("gateway", f"Gateway {gw_id} — recovered")
            except Exception as e:
                self._log.warn("gateway", f"Gateway {gw_id} — health check error: {e}")
                failed.append(gw_id)
                gw.status = "error"
                self._auto_reconnect(gw_id)
        return failed

    def _auto_reconnect(self, gw_id: str):
        """Attempts to reconnect a failed gateway with retry limit and delay."""
        now = time.time()
        retries = self._retry_count.get(gw_id, 0)
        last_retry = self._last_retry.get(gw_id, 0)

        # Check retry limit
        if retries >= self.MAX_RETRIES:
            self._log.error("gateway", f"Gateway {gw_id} — max retries ({self.MAX_RETRIES}) reached")
            return

        # Check delay since last attempt
        if now - last_retry < self.RETRY_DELAY:
            return  # too soon, wait

        self._retry_count[gw_id] = retries + 1
        self._last_retry[gw_id] = now

        gw = self._gateways.get(gw_id)
        if not gw:
            return

        self._log.info("gateway", f"Gateway {gw_id} — reconnecting (attempt {retries + 1}/{self.MAX_RETRIES})")

        try:
            if gw.type == "telegram" and hasattr(gw, '_token'):
                # Re-initialize and restart
                gw._running = False
                gw.status = "stopped"
                gw.start()
                ok = gw.health_check()
                if ok:
                    gw.status = "running"
                    self._retry_count[gw_id] = 0
                    self._log.info("gateway", f"Gateway {gw_id} — reconnected successfully")
                else:
                    self._log.warn("gateway", f"Gateway {gw_id} — reconnection failed")
            else:
                gw.start()
                gw.status = "running"
        except Exception as e:
            self._log.warn("gateway", f"Gateway {gw_id} — reconnection error: {e}")

    # ── STATUS ───────────────────────────────────────

    def show_status(self):
        """Prints status of all gateways."""
        if not self._gateways:
            print("\n  📡 GATEWAYS — None registered\n")
            return
        print("\n  📡 GATEWAYS")
        print("  " + "─" * 45)
        for gw in self._gateways.values():
            icon = "✅" if gw.status == "running" else ("⏹️" if gw.status == "stopped" else "🔴")
            print(f"  {icon} {gw.name} ({gw.id}): {gw.status}")
        print()

    @property
    def has_telegram(self) -> bool:
        """Returns True if Telegram gateway is available and running."""
        tg = self._gateways.get("telegram")
        return tg is not None and tg.status == "running"

    @property
    def telegram(self):
        """Returns the Telegram gateway if available."""
        return self._gateways.get("telegram")

    def stop_all(self):
        """Stops all gateways."""
        for gw in self._gateways.values():
            try:
                gw.stop()
            except Exception:
                pass
