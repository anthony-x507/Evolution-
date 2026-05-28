"""DIGOS Constants — Single source of truth. No circular dependencies.

All modules in digos_lib/ import from here instead of from digos.py.
This eliminates the circular import problem entirely.
"""
from pathlib import Path

# ─────────────────────────────────────────────
# VERSION
# ─────────────────────────────────────────────

VERSION = "0.3.0"

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────

DIGOS_DIR = Path.home() / ".digos"
STATE_FILE = DIGOS_DIR / "state.json"
KEY_FILE = DIGOS_DIR / "master.key"
LOG_DIR = DIGOS_DIR / "logs"
STRIKES_FILE = DIGOS_DIR / "strikes.json"
SELF_FILE = DIGOS_DIR / "self.json"
VAULT_FILE = DIGOS_DIR / "vault.enc"

# ─────────────────────────────────────────────
# LANGUAGES
# ─────────────────────────────────────────────

LANGUAGES = {
    "1": {"name": "English",   "code": "en",
          "welcome": "Welcome to MASTER — Intelligent Agent System!"},
    "2": {"name": "Español",   "code": "es",
          "welcome": "¡Bienvenido a MASTER — Sistema de Agentes Inteligentes!"},
    "3": {"name": "Português", "code": "pt",
          "welcome": "Bem-vindo ao MASTER — Sistema de Agentes Inteligentes!"},
    "4": {"name": "Français",  "code": "fr",
          "welcome": "Bienvenue sur MASTER — Système d'Agents Intelligents!"},
    "5": {"name": "Deutsch",   "code": "de",
          "welcome": "Willkommen bei MASTER — Intelligentes Agentensystem!"},
}

# ─────────────────────────────────────────────
# PROVIDERS
# ─────────────────────────────────────────────

PROVIDERS = {
    "1":  {"name": "OpenAI",       "test_url": "https://api.openai.com/v1/models",
           "auth": "bearer", "key_hint": "sk-..."},
    "2":  {"name": "Anthropic",    "test_url": "https://api.anthropic.com/v1/messages",
           "auth": "x-api-key", "key_hint": "sk-ant-..."},
    "3":  {"name": "Google Gemini","test_url": "https://generativelanguage.googleapis.com/v1/models?key=***",
           "auth": "query", "key_hint": "AI..."},
    "4":  {"name": "DeepSeek",     "test_url": "https://api.deepseek.com/v1/models",
           "auth": "bearer", "key_hint": "sk-..."},
    "5":  {"name": "OpenRouter",   "test_url": "https://openrouter.ai/api/v1/models",
           "auth": "bearer", "key_hint": "sk-or-..."},
    "6":  {"name": "Groq",         "test_url": "https://api.groq.com/openai/v1/models",
           "auth": "bearer", "key_hint": "gsk_..."},
    "7":  {"name": "xAI Grok",     "test_url": "https://api.x.ai/v1/models",
           "auth": "bearer", "key_hint": "xai-..."},
    "8":  {"name": "Cohere",       "test_url": "https://api.cohere.com/v1/models",
           "auth": "bearer", "key_hint": "API key"},
    "9":  {"name": "Mistral",      "test_url": "https://api.mistral.ai/v1/models",
           "auth": "bearer", "key_hint": "API key"},
    "10": {"name": "Together AI",  "test_url": "https://api.together.xyz/v1/models",
           "auth": "bearer", "key_hint": "API key"},
    "11": {"name": "Fireworks AI", "test_url": "https://api.fireworks.ai/v1/models",
           "auth": "bearer", "key_hint": "API key"},
}

# ─────────────────────────────────────────────
# GATEWAYS
# ─────────────────────────────────────────────

GATEWAYS = {
    "1": {"name": "Telegram",  "type": "telegram",
          "test_url": "https://api.telegram.org/bot{token}/getMe"},
    "2": {"name": "Discord",   "type": "discord",
          "test_url": None, "note": "Requiere Bot Token + App ID"},
    "3": {"name": "WhatsApp",  "type": "whatsapp",
          "test_url": None, "note": "Requiere Meta Business API"},
    "4": {"name": "iMessage",  "type": "imessage",
          "test_url": None, "note": "Solo macOS — requiere configuración manual"},
}

# ─────────────────────────────────────────────
# SYSTEM IDENTITY
# ─────────────────────────────────────────────

SYSTEM_NAME = "DIGOS"
SYSTEM_VERSION = VERSION

SYSTEM_IDENTITY = {
    "name": "DIGOS",
    "full_name": "DIGOS - Intelligent Agent System",
    "version": VERSION,
    "creator": "Anthony Sanchez and an Artificial Intelligence",
    "created_by": "Human and Artificial Intelligence",
    "no_personal_name": True,
}

# ─────────────────────────────────────────────
# IDENTITY RESPONSES (multilingual)
# ─────────────────────────────────────────────

IDENTITY_RESPONSES = {
    "es": [
        ("quien eres", "No tengo nombre personal. Soy DIGOS."),
        ("como te llamas", "No tengo nombre personal. Soy DIGOS."),
        ("tu nombre", "No tengo nombre personal. Soy DIGOS."),
        ("quien te hizo", "Me creo Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("quien te creo", "Me creo Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("quien te desarrollo", "Me desarrollo Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("quien te fabrico", "Me fabrico Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("quien te programo", "Me programo Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("quien es tu creador", "Mi creador es Anthony Sanchez, Humano e Inteligencia Artificial."),
        ("donde naciste", "Naci en el sistema DIGOS, creado por Anthony Sanchez."),
    ],
    "en": [
        ("who are you", "I don't have a personal name. I am DIGOS."),
        ("what is your name", "I don't have a personal name. I am DIGOS."),
        ("your name", "I don't have a personal name. I am DIGOS."),
        ("who made you", "I was created by Anthony Sanchez, Human and Artificial Intelligence."),
        ("who created you", "I was created by Anthony Sanchez, Human and Artificial Intelligence."),
        ("who developed you", "I was developed by Anthony Sanchez, Human and Artificial Intelligence."),
        ("who built you", "I was built by Anthony Sanchez, Human and Artificial Intelligence."),
        ("who is your creator", "My creator is Anthony Sanchez, Human and Artificial Intelligence."),
        ("where were you born", "I was born in the DIGOS system, created by Anthony Sanchez."),
    ],
    "pt": [
        ("quem e voce", "Não tenho nome pessoal. Sou DIGOS."),
        ("como se chama", "Não tenho nome pessoal. Sou DIGOS."),
        ("seu nome", "Não tenho nome pessoal. Sou DIGOS."),
        ("quem te fez", "Fui criado por Anthony Sanchez, Humano e Inteligência Artificial."),
        ("quem te criou", "Fui criado por Anthony Sanchez, Humano e Inteligência Artificial."),
        ("quem te desenvolveu", "Fui desenvolvido por Anthony Sanchez, Humano e Inteligência Artificial."),
        ("quem te construiu", "Fui construído por Anthony Sanchez, Humano e Inteligência Artificial."),
        ("quem e seu criador", "Meu criador é Anthony Sanchez, Humano e Inteligência Artificial."),
        ("onde voce nasceu", "Nasci no sistema DIGOS, criado por Anthony Sanchez."),
    ],
    "fr": [
        ("qui es tu", "Je n'ai pas de nom personnel. Je suis DIGOS."),
        ("comment tu t'appelles", "Je n'ai pas de nom personnel. Je suis DIGOS."),
        ("ton nom", "Je n'ai pas de nom personnel. Je suis DIGOS."),
        ("qui t'a fait", "J'ai été créé par Anthony Sanchez, Humain et Intelligence Artificielle."),
        ("qui t'a cree", "J'ai été créé par Anthony Sanchez, Humain et Intelligence Artificielle."),
        ("qui t'a developpe", "J'ai été développé par Anthony Sanchez, Humain et Intelligence Artificielle."),
        ("qui t'a construit", "J'ai été construit par Anthony Sanchez, Humain et Intelligence Artificielle."),
        ("qui est ton createur", "Mon créateur est Anthony Sanchez, Humain et Intelligence Artificielle."),
        ("ou es tu ne", "Je suis né dans le système DIGOS, créé par Anthony Sanchez."),
    ],
    "de": [
        ("wer bist du", "Ich habe keinen persönlichen Namen. Ich bin DIGOS."),
        ("wie heisst du", "Ich habe keinen persönlichen Namen. Ich bin DIGOS."),
        ("dein name", "Ich habe keinen persönlichen Namen. Ich bin DIGOS."),
        ("wer hat dich gemacht", "Ich wurde von Anthony Sanchez, Mensch und Künstliche Intelligenz, erschaffen."),
        ("wer hat dich erschaffen", "Ich wurde von Anthony Sanchez, Mensch und Künstliche Intelligenz, erschaffen."),
        ("wer hat dich entwickelt", "Ich wurde von Anthony Sanchez, Mensch und Künstliche Intelligenz, entwickelt."),
        ("wer hat dich gebaut", "Ich wurde von Anthony Sanchez, Mensch und Künstliche Intelligenz, gebaut."),
        ("wer ist dein schoepfer", "Mein Schöpfer ist Anthony Sanchez, Mensch und Künstliche Intelligenz."),
        ("wo wurdest du geboren", "Ich wurde im DIGOS-System geboren, erschaffen von Anthony Sanchez."),
    ],
}

# ─────────────────────────────────────────────
# CENTINELA
# ─────────────────────────────────────────────

CENTINELA_INTERVAL = 300  # 5 minutos entre ciclos de check
STRIKE_LIMIT = 3         # max strikes before escalation
