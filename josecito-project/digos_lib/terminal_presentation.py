"""Terminal presentation helpers for the DIGOS first-run experience."""
from __future__ import annotations

import os
import shutil
import sys
from typing import Iterable


NINJA_ART = [
    "              .-.",
    "           __/___\\__          /",
    "          /  _   _  \\        /",
    "         |  /_\\ /_\\  |      /",
    "          \\   ___   /      /",
    "      _____`-.___.-'______/ ",
    "     /  _   _  |||  _   _ \\",
    "    /__/ \\_/ \\_|||_/ \\_/ \\__\\",
    "          /    |||    \\",
    "         /___/\\___/\\___\\",
    "        /__/       \\__\\",
]


DIGOS_TITLE = [
    r"██████╗  ██╗ ██████╗  ██████╗ ███████╗",
    r"██╔══██╗ ██║██╔════╝ ██╔═══██╗██╔════╝",
    r"██║  ██║ ██║██║  ███╗██║   ██║███████╗",
    r"██║  ██║ ██║██║   ██║██║   ██║╚════██║",
    r"██████╔╝ ██║╚██████╔╝╚██████╔╝███████║",
    r"╚═════╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝",
]


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM", "").lower() == "dumb":
        return False
    return sys.stdout.isatty()


def _terminal_width(default: int = 88) -> int:
    return shutil.get_terminal_size((default, 24)).columns


def _center(lines: Iterable[str], width: int) -> list[str]:
    return [line.center(width).rstrip() for line in lines]


def _color(text: str, code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def render_startup_banner(
    *,
    system_name: str = "DIGOS",
    tagline: str = "Organized Home for Useful Intelligence",
    welcome: str = "Welcome. Vamos a configurar DIGOS.",
    width: int | None = None,
    color: bool | None = None,
) -> str:
    """Build the static first-run terminal banner.

    The banner is presentation only: it does not inspect state, credentials,
    provider configuration, tickets, or any runtime internals.
    """
    resolved_width = max(64, min(width or _terminal_width(), 120))
    use_color = _supports_color() if color is None else color
    divider = "─" * min(42, resolved_width - 16)

    title_lines = DIGOS_TITLE if system_name.upper() == "DIGOS" else [system_name.upper()]
    title = _center(title_lines, resolved_width)
    ninja = _center(NINJA_ART, resolved_width)

    rendered: list[str] = [""]
    rendered.extend(_color(line, "38;5;220", use_color) for line in title)
    rendered.append("")
    rendered.append(_color(tagline.center(resolved_width).rstrip(), "38;5;250", use_color))
    rendered.append("")
    rendered.append(_color(divider.center(resolved_width).rstrip(), "38;5;238", use_color))
    rendered.append("")
    rendered.extend(_color(line, "38;5;245", use_color) for line in ninja)
    rendered.append("")
    rendered.append(_color(divider.center(resolved_width).rstrip(), "38;5;238", use_color))
    rendered.append("")
    rendered.append(_color(welcome.center(resolved_width).rstrip(), "38;5;250", use_color))
    rendered.append("")
    return "\n".join(rendered)


def print_startup_banner(**kwargs) -> None:
    """Print the first-run terminal banner."""
    print(render_startup_banner(**kwargs))
