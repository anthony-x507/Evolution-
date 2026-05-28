"""DIGOS Agent Tools — Available tools, dangerous tools, and tool executors."""
import io
import os
import contextlib
import subprocess
import urllib.parse
from urllib.request import Request, urlopen


# ─────────────────────────────────────────────
# AVAILABLE TOOLS FOR THE LLM
# ─────────────────────────────────────────────

AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for updated information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Término de búsqueda"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Leer el contenido de un archivo",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribir contenido en un archivo",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta del archivo"},
                    "content": {"type": "string", "description": "Contenido a escribir"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Ejecutar código Python",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Código Python a ejecutar"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Ejecutar un comando en la terminal",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando a ejecutar"}
                },
                "required": ["command"]
            }
        }
    },
]

# Tools que requieren aprobacion humana antes de ejecutarse
DANGEROUS_TOOLS = {"write_file", "execute_code", "terminal"}


# ─────────────────────────────────────────────
# EJECUTOR DE TOOLS
# ─────────────────────────────────────────────

def _execute_tool(name: str, args: dict) -> str:
    """Executes a tool and returns the result as a string."""
    try:
        if name == "web_search":
            return _web_search(args.get("query", ""))
        elif name == "read_file":
            return _read_file(args.get("path", ""))
        elif name == "write_file":
            return _write_file(args.get("path", ""), args.get("content", ""))
        elif name == "execute_code":
            return _execute_code(args.get("code", ""))
        elif name == "terminal":
            return _run_terminal(args.get("command", ""))
        else:
            return f"Error: tool '{name}' no soportado"
    except Exception as e:
        return f"Error ejecutando {name}: {e}"


def _web_search(query: str) -> str:
    """Búsqueda web simple vía DuckDuckGo (sin API key)."""
    encoded = urllib.parse.quote(query)
    url = f"https://lite.duckduckgo.com/lite/?q={encoded}"
    try:
        req = Request(url, headers={"User-Agent": "DIGOS/0.2"})
        with urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
            # Extraer texto relevante (resultados en tags <a>)
            lines = []
            in_result = False
            for line in html.split("\n"):
                if 'class="result-link"' in line or 'class="result-snippet"' in line:
                    in_result = True
                if in_result:
                    # Limpiar tags HTML
                    clean = line.replace("<b>", "").replace("</b>", "")
                    clean = clean.replace("<br>", "\n")
                    lines.append(clean)
                    if len(lines) >= 20:
                        break
            return "\n".join(lines)[:2000] if lines else "Sin resultados"
    except Exception as e:
        return f"Error en búsqueda: {e}"


def _read_file(path: str) -> str:
    """Reads a file from the system."""
    try:
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            return f"Error: archivo no encontrado: {path}"
        with open(path, "r", errors="replace") as f:
            content = f.read(3000)
        return content
    except Exception as e:
        return f"Error leyendo archivo: {e}"


def _write_file(path: str, content: str) -> str:
    """Escribe contenido en un archivo."""
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Archivo escrito: {path} ({len(content)} bytes)"
    except Exception as e:
        return f"Error escribiendo archivo: {e}"


def _execute_code(code: str) -> str:
    """Ejecuta código Python en un entorno aislado."""
    try:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec_globals = {"__builtins__": __builtins__}
            exec(code, exec_globals)
        result = output.getvalue()
        return result if result else "Código ejecutado (sin salida)"
    except Exception as e:
        return f"Error ejecutando código: {e}"


def _run_terminal(command: str) -> str:
    """Executes a command in the terminal."""
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout or ""
        error = result.stderr or ""
        if error:
            output += f"\n[stderr]\n{error}"
        return output[:2000] if output else "Comando ejecutado (sin salida)"
    except subprocess.TimeoutExpired:
        return "Error: comando timeout (30s)"
    except Exception as e:
        return f"Error en terminal: {e}"
