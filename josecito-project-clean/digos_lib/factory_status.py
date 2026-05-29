"""Persistent product-facing Factory status.

This file is the small shared flag board for the orchestra.  The agent,
Tower, Engineer, and Factory can all leave a durable state here without
exposing internal ticket mechanics to the user.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from digos_lib.constants import DIGOS_DIR


class FactoryStatusStore:
    """Stores capability request state in a durable JSON file."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (DIGOS_DIR / "factory_status.json")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"capability_requests": {}, "updated_at": ""}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"capability_requests": {}, "updated_at": ""}
            data.setdefault("capability_requests", {})
            return data
        except Exception:
            return {"capability_requests": {}, "updated_at": ""}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at"] = self._now()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def upsert_capability(
        self,
        capability: str,
        *,
        family: str = "",
        user_message: str = "",
        status: str = "identified",
        audit_ticket_id: str = "",
        audit_profile: str = "",
        requester: str = "",
        factory_ticket_number: str | int | None = None,
        tool_name: str = "",
        active: bool = False,
        responsibilities: Optional[dict[str, str]] = None,
        activation_requirements: Optional[list[str]] = None,
        activation_missing: Optional[list[str]] = None,
        pipeline_stage: str = "",
        pipeline_checkpoints: Optional[dict[str, str]] = None,
        next_step: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        """Create or update a capability request status."""
        data = self._read()
        requests = data.setdefault("capability_requests", {})
        now = self._now()
        record = requests.get(capability, {})
        if not record:
            record = {
                "capability": capability,
                "family": family,
                "created_at": now,
                "timeline": [],
            }

        record.update({
            "capability": capability,
            "family": family or record.get("family", ""),
            "status": status,
            "audit_ticket_id": audit_ticket_id or record.get("audit_ticket_id", ""),
            "audit_profile": audit_profile or record.get("audit_profile", ""),
            "requester": requester or record.get("requester", ""),
            "factory_ticket_number": factory_ticket_number
                if factory_ticket_number is not None
                else record.get("factory_ticket_number", ""),
            "tool_name": tool_name or record.get("tool_name", ""),
            "active": bool(active),
            "validation_required": not bool(active),
            "closure_allowed": bool(active),
            "pipeline_stage": pipeline_stage or record.get("pipeline_stage", ""),
            "updated_at": now,
        })
        if user_message:
            record["request_summary"] = user_message[:240]
        if responsibilities:
            record["responsibilities"] = responsibilities
        if activation_requirements is not None:
            record["activation_requirements"] = list(activation_requirements)
        if activation_missing is not None:
            record["activation_missing"] = list(activation_missing)
        elif active:
            record["activation_missing"] = []
        if pipeline_checkpoints is not None:
            record["pipeline_checkpoints"] = dict(pipeline_checkpoints)
        if next_step:
            record["next_step"] = next_step

        record.setdefault("timeline", []).append({
            "at": now,
            "status": status,
            "note": note,
        })
        record["timeline"] = record["timeline"][-25:]

        requests[capability] = record
        self._write(data)
        return record

    def latest(self, capability: str = "") -> Optional[dict[str, Any]]:
        """Return a specific capability record or the most recently updated one."""
        requests = self._read().get("capability_requests", {})
        if capability:
            return requests.get(capability)
        if not requests:
            return None
        return sorted(
            requests.values(),
            key=lambda item: item.get("updated_at", item.get("created_at", "")),
            reverse=True,
        )[0]

    def public_summary(self, capability: str = "", *, language: str = "es") -> str:
        """Return a clean user-facing status summary."""
        record = self.latest(capability)
        if not record:
            return (
                "No veo una solicitud de herramienta en proceso todavía."
                if language == "es"
                else "I do not see a tool request in progress yet."
            )

        cap = record.get("capability", "la herramienta")
        active = bool(record.get("active"))
        status = record.get("status", "")
        family = str(record.get("family", "")).upper()

        def _missing_text_es() -> str:
            if family == "VOICE":
                return (
                    "Falta la conexión completa de voz en Telegram y una prueba de "
                    "punta a punta antes de cerrarla."
                )
            if family == "WEB":
                return (
                    "Falta conectar la búsqueda web al canal de Telegram y validar "
                    "una búsqueda permitida y una bloqueada."
                )
            if family == "VISION":
                return (
                    "Falta conectar imágenes de Telegram, análisis visual y respuesta "
                    "final gobernada."
                )
            return (
                "Falta conectar esa capacidad al canal vivo y validarla antes de "
                "marcarla como activa."
            )

        def _missing_text_en() -> str:
            if family == "VOICE":
                return "Voice still needs Telegram wiring and an end-to-end validation before closure."
            if family == "WEB":
                return "Web search still needs Telegram wiring plus allowed and blocked search validation."
            if family == "VISION":
                return "Vision still needs Telegram image intake, visual analysis, and governed final response."
            return "It still needs live-channel wiring and validation before activation."

        if language != "es":
            if active:
                return "The requested capability is active."
            if status in {"factory_completed_pending_activation", "pending_validation"}:
                return (
                    "The request is still open. The Factory advanced the capability, "
                    f"but it is not active in Telegram yet. {_missing_text_en()} "
                    "Until that is connected, I can only work with text here."
                )
            return "The request is still being reviewed."

        if active:
            return "La capacidad solicitada ya está activa."
        if status in {"factory_completed_pending_activation", "pending_validation"}:
            return (
                "La solicitud sigue abierta. La Factoría avanzó la capacidad, pero "
                f"todavía no está activa en Telegram. {_missing_text_es()} "
                "Hasta que eso quede conectado, seguimos por texto."
            )
        if status in {"factory_processing", "registered"}:
            return (
                "La solicitud está en proceso. La Factoría y el ingeniero la tienen "
                "marcada para seguimiento hasta que cierre."
            )
        if status == "failed":
            return (
                "La solicitud fue identificada, pero la Factoría no pudo completarla. "
                "Hay que revisarla antes de prometer esa herramienta."
            )
        return f"La solicitud de {cap} está registrada para revisión."
