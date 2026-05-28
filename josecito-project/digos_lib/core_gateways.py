"""DIGOS Gateways — Plugin communication channels (CLI, Telegram)."""
import json
import os
import sys
import time
import threading
import signal
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

class BaseGateway:
    """Base gateway — communication plugin.
    Each gateway implements: start, stop, health_check, send_message.
    """

    def __init__(self, gw_id: str, name: str, gw_type: str):
        self.id = gw_id
        self.name = name
        self.type = gw_type
        self.status = "stopped"  # stopped, running, error, connecting
        self._running = False
        self._log = None

    def set_logger(self, log_keeper):
        self._log = log_keeper

    def start(self):
        raise NotImplementedError

    def stop(self):
        self._running = False
        self.status = "stopped"

    def health_check(self) -> bool:
        raise NotImplementedError

    def status_info(self) -> dict:
        return {"id": self.id, "name": self.name, "type": self.type, "status": self.status}


class GatewayCLI(BaseGateway):
    """Terminal gateway — interactive stdin/stdout."""

    def __init__(self):
        super().__init__("cli", "CLI Terminal", "terminal")

    def start(self):
        """Start the CLI gateway. Does NOT block — the interactive loop
        is handled by TorreDeControl._start_interactive()."""
        self._running = True
        self.status = "running"
        if self._log:
            self._log.info("gateway-cli", "Gateway CLI ready")

    def health_check(self) -> bool:
        return self._running

    def send_message(self, msg: str, **kw):
        print(f"\n  [Mensaje]: {msg}\n")


class GatewayTelegram(BaseGateway):
    """Telegram gateway via long-polling. stdlib only (urllib + json)."""

    def __init__(self, token: str = ""):
        super().__init__("telegram", "Telegram Bot", "telegram")
        self._token = token
        self._offset = 0
        self._base_url = f"https://api.telegram.org/bot{token}" if token else ""

    def start(self):
        if not self._token:
            self.status = "error"
            if self._log:
                self._log.error("gateway-tg", "Token vacío — no se puede iniciar")
            return
        self._running = True
        self.status = "running"
        if self._log:
            self._log.info("gateway-tg", "Gateway Telegram iniciado")
        print(f"  🤖 Telegram Gateway listo (token: ...{self._token[-6:]})")

    def health_check(self) -> bool:
        if not self._running or not self._token:
            return False
        try:
            import urllib.request
            url = self._base_url + "/getMe"
            with urllib.request.urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
                return data.get("ok", False)
        except HTTPError as e:
            if self._log:
                self._log.warn("gateway-tg", f"Health check HTTP {e.code}: {e.reason}")
            return False
        except Exception as e:
            if self._log:
                self._log.warn("gateway-tg", f"Health check failed: {e}")
            return False

    def poll_updates(self) -> list:
        """Gets new messages from Telegram."""
        if not self._running or not self._token:
            return []
        try:
            import urllib.request
            url = f"{self._base_url}/getUpdates?offset={self._offset}&timeout=10"
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
            if not data.get("ok"):
                return []
            updates = []
            for upd in data.get("result", []):
                self._offset = upd["update_id"] + 1
                if "message" in upd:
                    updates.append(upd["message"])
            return updates
        except HTTPError as e:
            if self._log:
                self._log.warn("gateway-tg", f"Poll HTTP {e.code}: {e.reason}")
            return []
        except Exception as e:
            if self._log:
                self._log.warn("gateway-tg", f"Poll failed: {e}")
            return []

    def send_message(self, msg: str, chat_id: str = "", **kw) -> str:
        """Sends a message. Returns message_id string if ok, '' if fails."""
        if not self._token or not chat_id:
            return ""
        try:
            import urllib.request
            payload = json.dumps({"chat_id": chat_id, "text": msg}).encode()
            req = urllib.request.Request(
                self._base_url + "/sendMessage",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                if data.get("ok") and data.get("result", {}).get("message_id"):
                    return str(data["result"]["message_id"])
                return ""
        except Exception:
            return ""

    def edit_message(self, chat_id: str, message_id: str, text: str) -> bool:
        """Edits an existing message. Returns True if ok."""
        if not self._token or not chat_id or not message_id:
            return False
        try:
            import urllib.request
            payload = json.dumps({
                "chat_id": chat_id,
                "message_id": int(message_id),
                "text": text,
            }).encode()
            req = urllib.request.Request(
                self._base_url + "/editMessageText",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read()).get("ok", False)
        except Exception:
            return False

    def send_chat_action(self, chat_id: str, action: str = "typing") -> bool:
        """Sends activity indicator (typing, upload_photo, etc.)."""
        if not self._token or not chat_id:
            return False
        try:
            import urllib.request
            payload = json.dumps({"chat_id": chat_id, "action": action}).encode()
            req = urllib.request.Request(
                self._base_url + "/sendChatAction",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read()).get("ok", False)
        except Exception:
            return False

    def delete_message(self, chat_id: str, message_id: str) -> bool:
        """Deletes a message from the chat. Used to clear progress before response."""
        if not self._token or not chat_id or not message_id:
            return False
        try:
            import urllib.request
            payload = json.dumps({
                "chat_id": chat_id,
                "message_id": int(message_id),
            }).encode()
            req = urllib.request.Request(
                self._base_url + "/deleteMessage",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read()).get("ok", False)
        except Exception:
            return False

    def stop(self):
        self._running = False
        self.status = "stopped"
        if self._log:
            self._log.info("gateway-tg", "Gateway Telegram detenido")
