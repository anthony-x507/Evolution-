"""DIGOS SelfAwarenessCore — Agent identity + state machine."""
import json
from datetime import datetime, timezone

from digos_lib.constants import SYSTEM_IDENTITY, SELF_FILE, VERSION
from digos_lib.core_log import LogKeeper

class SelfAwarenessCore:
    """Agent identity + state machine.
    States: INITIALIZING → ACTIVE ↔ PAUSED / ERROR → ACTIVE"""

    VALID_STATES = ["INICIANDO", "ACTIVO", "EN_PAUSA", "ERROR"]

    def __init__(self, log_keeper: LogKeeper):
        self.log = log_keeper
        self._identity = {
            "name": SYSTEM_IDENTITY["name"],
            "version": VERSION,
            "purpose": "Agente inteligente con auto-preservación",
            "born": datetime.now(timezone.utc).isoformat()
        }
        self._state = "INICIANDO"
        self._load()
        self._persist()

    def _load(self):
        if SELF_FILE.exists():
            try:
                data = json.loads(SELF_FILE.read_text(encoding='utf-8'))
                self._state = data.get("state", "INICIANDO")
                if data.get("identity"):
                    self._identity.update(data["identity"])
            except (json.JSONDecodeError, ValueError):
                pass

    def _persist(self):
        data = {
            "state": self._state,
            "identity": self._identity,
            "updated": datetime.now(timezone.utc).isoformat()
        }
        SELF_FILE.write_text(json.dumps(data, indent=2))

    def _set(self, new_state: str):
        if new_state in self.VALID_STATES and new_state != self._state:
            old = self._state
            self._state = new_state
            self._persist()
            self.log.info("self", f"Estado: {old} → {new_state}")

    @property
    def state(self) -> str:
        return self._state

    @property
    def identity(self) -> dict:
        return dict(self._identity)

    def activate(self):
        self._set("ACTIVO")

    def pause(self):
        self._set("EN_PAUSA")

    def set_error(self):
        self._set("ERROR")

    def recover(self):
        self._set("ACTIVO")

    def status(self) -> dict:
        return {
            "state": self._state,
            "identity": self._identity,
            "version": VERSION
        }
