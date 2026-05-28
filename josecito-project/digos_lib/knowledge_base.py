"""
knowledge_base.py — Knowledge Base for AgentInfra-style structured knowledge
============================================================================
Loads structured markdown files from the knowledge/ directory and provides
them as context for the agent's system prompt.

Injected at agent birth alongside Self-Awareness, GPS, Work, and Kendo.
"""

import os
from pathlib import Path
from typing import Optional, Dict, List


class KnowledgeBase:
    """Loads and provides structured project knowledge for the agent.

    The knowledge directory contains markdown files that describe:
    - ARCHITECTURE.md: system architecture
    - DECISIONS.md: key decisions and rationale
    - CAPABILITIES.md: what the system can do
    - ACTIVE.md: current work in progress

    These files are loaded at agent birth and injected into the system prompt.
    """

    REQUIRED_FILES = {
        "ARCHITECTURE.md": "Architecture",
        "DECISIONS.md": "Key Decisions",
        "CAPABILITIES.md": "Capabilities",
        "ACTIVE.md": "Active Context",
    }

    def __init__(self, knowledge_dir: str = ""):
        self._knowledge_dir = Path(knowledge_dir) if knowledge_dir else Path.cwd() / "knowledge"
        self._loaded: Dict[str, str] = {}

    def load_all(self) -> Dict[str, str]:
        """Loads all knowledge files from the directory.
        Returns a dict of {filename: content}."""
        self._loaded = {}
        if not self._knowledge_dir.is_dir():
            return self._loaded

        for fname in self.REQUIRED_FILES:
            fpath = self._knowledge_dir / fname
            if fpath.exists():
                try:
                    self._loaded[fname] = fpath.read_text(encoding="utf-8")
                except Exception:
                    self._loaded[fname] = f"*Could not load {fname}*"
            else:
                self._loaded[fname] = ""

        return self._loaded

    def is_loaded(self) -> bool:
        """Returns True if knowledge files have been loaded."""
        return bool(self._loaded)

    def build_context(self) -> str:
        """Builds a formatted string of all loaded knowledge for the system prompt."""
        if not self._loaded:
            return ""

        sections = []
        for fname, title in self.REQUIRED_FILES.items():
            content = self._loaded.get(fname, "")
            if content.strip():
                sections.append(f"== {title} ==\n{content.strip()}")

        if not sections:
            return ""

        return "\n\n" + "\n\n".join(sections)

    def get_section(self, fname: str) -> str:
        """Returns the raw content of a specific knowledge file."""
        return self._loaded.get(fname, "")

    def get(self, key: str, default: str = "") -> str:
        """Returns a specific knowledge file's content by key (filename without .md)."""
        for fname in self.REQUIRED_FILES:
            if fname.startswith(key.upper()):
                return self._loaded.get(fname, default)
        return default

    @property
    def file_count(self) -> int:
        """Returns number of successfully loaded knowledge files."""
        return sum(1 for c in self._loaded.values() if c.strip())

    @property
    def file_list(self) -> List[str]:
        """Returns list of loaded filenames."""
        return [f for f, c in self._loaded.items() if c.strip()]
