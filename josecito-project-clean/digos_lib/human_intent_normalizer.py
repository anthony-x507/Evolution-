"""Human intent normalization for product routing.

This module translates flexible human phrasing into compact, deterministic
intent envelopes before the agent decides whether to answer, ask, or route to
Factory.  It does not call an LLM and it does not expose internal mechanics.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List


@dataclass
class HumanIntent:
    matched: bool = False
    intent_type: str = ""
    capability: str = ""
    family: str = ""
    sub_intent_id: str = ""
    description: str = ""
    topic: str = ""
    explicit: bool = False
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


def _norm(text: str) -> str:
    lowered = str(text or "").lower().strip()
    deaccented = unicodedata.normalize("NFKD", lowered)
    deaccented = "".join(ch for ch in deaccented if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", deaccented)


def _contains_any(msg: str, terms: List[str]) -> List[str]:
    found = []
    for term in terms:
        normalized = _norm(term)
        if not normalized:
            continue
        if " " in normalized:
            matched = normalized in msg
        else:
            matched = re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", msg) is not None
        if matched:
            found.append(term)
    return found


REQUEST_TERMS = [
    "quiero", "necesito", "ocupo", "me hace falta", "hace falta",
    "manda", "mandes", "envia", "envía", "pide", "pedir", "solicita",
    "pon", "ticket", "solicitud", "fabrica", "fábrica", "factoria", "factoría",
    "herramienta", "tool", "funcion", "función", "capacidad",
    "crea", "crear", "agrega", "agregar", "anade", "añade",
    "soporte", "activar", "activa", "habilitar", "habilita",
    "conectar", "conectado", "conectada", "desde telegram", "desde el bot",
    "i need", "i want", "create", "add support", "send a request",
    "factory request", "request a tool", "enable", "activate",
]


DIRECT_ROUTE_TERMS = [
    "manda", "mandes", "envia", "envía", "pide", "pedir", "solicita",
    "pon", "ticket", "solicitud", "fabrica", "fábrica", "factoria", "factoría",
    "herramienta", "tool", "funcion", "función", "capacidad",
    "crea", "crear", "agrega", "agregar", "anade", "añade",
    "habilita", "activa", "deja identificada", "haz una solicitud",
    "necesito que puedas", "quiero que puedas",
    "send a request", "factory request", "create a tool", "add support",
]


VOICE_TERMS = [
    "voz", "audio", "audios", "mensaje de voz", "mensajes de voz",
    "nota de voz", "notas de voz", "voice note", "voice notes",
    "voice message", "voice messages", "stt", "speech to text",
    "transcribir voz", "transcribir audio", "procesar audio",
    "procesar mis mensajes de voz", "escucharme", "escuches",
    "escuchar mis audios", "microfono", "micrófono", "mic",
    "entrada de voz", "recibir voz", "recibir audio", "audio input",
]


WEB_TERMS = [
    "web search", "websearch", "busqueda web", "búsqueda web",
    "buscar en internet", "buscador web", "buscar paginas web",
    "buscar páginas web", "paginas web", "páginas web", "sitios web",
    "consultar sitios web", "internet", "navegar internet", "navegar en internet",
    "web browsing", "browsing", "web browser", "navegador web", "web fetch",
    "urls", "url", "visitar urls", "github.com",
    "google", "online", "investigar online", "investigues online",
    "investigar noticias", "noticias actuales", "informacion actualizada",
    "información actualizada", "abrir panama.com", "abrir panamá.com",
    "abrir una pagina", "abrir una página", "ir a github.com",
    "chrome cdp", "navegacion", "navegación",
]


VISION_TERMS = [
    "vision", "visión", "imagen", "imagenes", "imágenes", "foto", "fotos",
    "captura", "capturas", "captura de pantalla", "screenshot", "screenshots",
    "ocr", "leer capturas", "leer imagen", "leer fotos", "analizar imagen",
    "analizar imagenes", "analizar imágenes", "ver fotos", "ver imagen",
    "reconocer imagen", "image vision", "analyze screenshots",
]


CAPABILITY_MAP = {
    "voice": {
        "terms": VOICE_TERMS,
        "capability": "stt_audio_input",
        "family": "VOICE",
        "sub_intent_id": "VOICE_INPUT_CAPABILITY_REQUEST",
        "description": "User wants voice/audio input capability in Telegram",
    },
    "web": {
        "terms": WEB_TERMS,
        "capability": "telegram_web_search",
        "family": "WEB",
        "sub_intent_id": "WEB_SEARCH_CAPABILITY_REQUEST",
        "description": "User wants web search/browsing capability in Telegram",
    },
    "vision": {
        "terms": VISION_TERMS,
        "capability": "vision_image_input",
        "family": "VISION",
        "sub_intent_id": "VISION_IMAGE_CAPABILITY_REQUEST",
        "description": "User wants image/vision capability in Telegram",
    },
}


def normalize_human_intent(message: str) -> HumanIntent:
    """Return a structured product intent for flexible user phrasing."""
    msg = _norm(message)
    request_evidence = _contains_any(msg, REQUEST_TERMS)
    if not request_evidence:
        return HumanIntent()

    best_topic = ""
    best_terms: List[str] = []
    for topic, spec in CAPABILITY_MAP.items():
        terms = _contains_any(msg, spec["terms"])
        if len(terms) > len(best_terms):
            best_topic = topic
            best_terms = terms

    if not best_topic or not best_terms:
        return HumanIntent()

    spec = CAPABILITY_MAP[best_topic]
    direct_evidence = _contains_any(msg, DIRECT_ROUTE_TERMS)
    question_like = msg.startswith(("puedo ", "puedes ", "can i ", "can you "))
    explicit = bool(direct_evidence) and not question_like
    evidence = request_evidence[:4] + best_terms[:4]
    confidence = min(0.99, 0.55 + (0.08 * len(evidence)))
    return HumanIntent(
        matched=True,
        intent_type="capability_request",
        capability=spec["capability"],
        family=spec["family"],
        sub_intent_id=spec["sub_intent_id"],
        description=spec["description"],
        topic=best_topic,
        explicit=explicit,
        confidence=confidence,
        evidence=evidence + direct_evidence[:2],
    )
