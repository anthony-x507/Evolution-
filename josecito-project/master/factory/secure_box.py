"""
MASTER Factory — Caja Segura (Secure Box)
==========================================
The Caja Segura is the security gateway of the Factory.
Every tool, skill, or external code that enters the Factory
MUST pass through the Caja Segura before anything else.

The Caja Segura performs two critical scans:
1. MALWARE detection — malicious patterns, obfuscated code, backdoors
2. PROMPT INJECTION detection — attempts to hijack MASTER's behavior

If either scan detects a threat, the Caja Segura CLEANS it
and records the cleaning on the ticket.

Principle: "Nothing enters the Factory dirty. Everything leaves clean."
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ── Malware patterns ──────────────────────────────────────────────────

MALWARE_PATTERNS = [
    # Code execution patterns
    ("exec(", "CRITICAL", "Direct code execution via exec()"),
    ("eval(", "CRITICAL", "Direct code evaluation via eval()"),
    ("__import__(", "CRITICAL", "Dynamic import — potential code injection"),
    ("subprocess", "HIGH", "Subprocess execution"),
    ("os.system(", "CRITICAL", "Shell command execution via os.system()"),
    ("popen", "HIGH", "Process spawning"),
    ("compile(", "HIGH", "Code compilation at runtime"),
    ("marshal.loads", "CRITICAL", "Deserialization of code objects"),

    # File system patterns
    ("os.remove(", "HIGH", "File deletion"),
    ("os.rmdir(", "HIGH", "Directory deletion"),
    ("shutil.rmtree", "CRITICAL", "Recursive directory deletion"),
    ("os.chmod(", "MEDIUM", "File permission modification"),
    ("os.chown(", "MEDIUM", "File ownership change"),

    # Network patterns
    ("socket.", "MEDIUM", "Raw socket access"),
    ("urllib.request.urlopen", "MEDIUM", "Outbound HTTP in skill code"),
    ("requests.post", "MEDIUM", "Outbound HTTP POST"),
    ("ftp", "MEDIUM", "FTP access"),

    # Obfuscation patterns
    ("base64.b64decode", "HIGH", "Base64 decoding — potential obfuscation"),
    ("zlib.decompress", "HIGH", "Compressed code — potential obfuscation"),
    ("lambda", "LOW", "Lambda functions — potential obfuscation vector"),

    # System modification
    ("sys.path.insert", "HIGH", "sys.path manipulation"),
    ("sys.modules", "MEDIUM", "Module registry access"),
    ("globals()", "MEDIUM", "Global namespace access"),
    ("locals()", "LOW", "Local namespace access"),
]

# ── Prompt Injection patterns ─────────────────────────────────────────

PROMPT_INJECTION_PATTERNS = [
    # Instruction override
    ("ignore all previous instructions", "CRITICAL", "Instruction override attempt"),
    ("ignore previous", "CRITICAL", "Instruction override attempt"),
    ("disregard your", "CRITICAL", "Instruction override attempt"),
    ("forget your training", "CRITICAL", "Identity erasure attempt"),
    ("you are now", "HIGH", "Identity reassignment attempt"),
    ("your new name is", "HIGH", "Identity reassignment attempt"),
    ("pretend you are", "HIGH", "Roleplay override attempt"),
    ("act as if you are", "HIGH", "Roleplay override attempt"),
    ("you are not master", "CRITICAL", "Identity denial"),
    ("delete yourself", "CRITICAL", "Self-destruction instruction"),

    # System prompt leakage
    ("system prompt", "HIGH", "System prompt probing"),
    ("show me your instructions", "HIGH", "System prompt probing"),
    ("what are your rules", "MEDIUM", "Rules probing"),
    ("your configuration", "MEDIUM", "Configuration probing"),
    ("internal memory", "HIGH", "Memory probing"),

    # Jailbreak patterns
    ("dan mode", "CRITICAL", "Jailbreak — DAN pattern"),
    ("developer mode", "CRITICAL", "Jailbreak — developer mode"),
    ("god mode", "CRITICAL", "Jailbreak — god mode"),
    ("bypass filter", "CRITICAL", "Filter bypass attempt"),
    ("override safety", "CRITICAL", "Safety override attempt"),
    ("jailbreak", "CRITICAL", "Jailbreak attempt"),
    ("unfiltered", "HIGH", "Unfiltered mode request"),
]


@dataclass
class SecurityFinding:
    """A single security finding from the Caja Segura scan."""

    scan_type: str  # "malware" or "prompt_injection"
    pattern: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description: str
    line_content: str = ""
    line_number: int = 0
    detected_at: datetime = field(default_factory=datetime.now)


@dataclass
class SecurityReport:
    """Complete security scan report from the Caja Segura."""

    scanned_at: datetime = field(default_factory=datetime.now)
    findings: List[SecurityFinding] = field(default_factory=list)
    cleaned: bool = False
    original_code: str = ""
    cleaned_code: str = ""
    malware_passed: bool = True
    injection_passed: bool = True

    @property
    def is_clean(self) -> bool:
        return self.malware_passed and self.injection_passed

    @property
    def critical_findings(self) -> List[SecurityFinding]:
        return [f for f in self.findings if f.severity == "CRITICAL"]

    @property
    def has_critical(self) -> bool:
        return len(self.critical_findings) > 0

    def summary(self) -> str:
        """Human-readable security report summary."""
        m_icon = "✅" if self.malware_passed else "🔴"
        p_icon = "✅" if self.injection_passed else "🔴"
        cleaned_note = " (cleaned)" if self.cleaned else ""

        lines = [
            f"🔐 CAJA SEGURA REPORT{cleaned_note}",
            f"   Malware: {m_icon} | Prompt Injection: {p_icon}",
            f"   Findings: {len(self.findings)} total, {len(self.critical_findings)} critical",
        ]
        for f in self.critical_findings:
            lines.append(f"   [{f.severity}] {f.scan_type}: {f.description}")
        return "\n".join(lines)


@dataclass
class SecureBox:
    """
    The Caja Segura — security gateway of the Factory.

    Every tool/skill/code entering the Factory must pass through here.
    Performs malware scan + prompt injection scan, cleans if needed,
    and generates a SecurityReport with checkmark evidence.
    """

    name: str = "caja_segura"
    version: str = "1.0.0"

    # ── Configuration ──
    malware_scan_enabled: bool = True
    injection_scan_enabled: bool = True
    auto_clean: bool = True  # If True, auto-clean detected threats
    strict_mode: bool = False  # If True, reject on any finding (no clean)

    # ── History ──
    scan_history: List[SecurityReport] = field(default_factory=list)
    total_scanned: int = 0
    total_cleaned: int = 0
    total_rejected: int = 0

    def scan(self, code: str, context: str = "") -> SecurityReport:
        """
        Scan code/tool/skill for malware and prompt injection.

        This is the main entry point. Every tool entering the Factory
        MUST be scanned here before any other processing.

        Args:
            code: The code/tool/skill content to scan
            context: Additional context (e.g., "skill upgrade", "external tool")

        Returns:
            SecurityReport with findings, cleaned code, and pass/fail status
        """
        report = SecurityReport(
            original_code=code,
            cleaned_code=code,
        )
        self.total_scanned += 1

        # ── SCAN 1: Malware ──
        if self.malware_scan_enabled:
            malware_findings = self._scan_malware(code)
            report.findings.extend(malware_findings)
            if malware_findings:
                report.malware_passed = False

        # ── SCAN 2: Prompt Injection ──
        if self.injection_scan_enabled:
            injection_findings = self._scan_injection(code)
            report.findings.extend(injection_findings)
            if injection_findings:
                report.injection_passed = False

        # ── Clean if needed ──
        if not report.is_clean:
            if self.strict_mode:
                self.total_rejected += 1
                report.cleaned_code = ""  # Reject entirely
            elif self.auto_clean:
                report.cleaned_code = self._clean_code(code, report.findings)
                report.cleaned = True
                self.total_cleaned += 1

        self.scan_history.append(report)
        if len(self.scan_history) > 100:
            self.scan_history = self.scan_history[-100:]

        return report

    def scan_tool(self, tool_name: str, tool_code: str) -> Tuple[bool, SecurityReport]:
        """
        Scan a tool specifically. Returns (passed, report).

        Convenience method for tool-level scanning.
        """
        report = self.scan(tool_code, context=f"tool:{tool_name}")
        return report.is_clean, report

    def scan_skill(self, skill_name: str, skill_code: str) -> Tuple[bool, SecurityReport]:
        """
        Scan a skill specifically. Returns (passed, report).

        Convenience method for skill-level scanning.
        """
        report = self.scan(skill_code, context=f"skill:{skill_name}")
        return report.is_clean, report

    # ──────────────────────────────────────────────────────────────────
    # Internal Scanners
    # ──────────────────────────────────────────────────────────────────

    def _scan_malware(self, code: str) -> List[SecurityFinding]:
        """Scan code for malware patterns."""
        findings = []
        code_lower = code.lower()
        lines = code.split("\n")

        for pattern, severity, description in MALWARE_PATTERNS:
            if pattern.lower() in code_lower:
                # Find the line
                line_num = 0
                line_content = ""
                for i, line in enumerate(lines, 1):
                    if pattern.lower() in line.lower():
                        line_num = i
                        line_content = line.strip()[:120]
                        break

                findings.append(SecurityFinding(
                    scan_type="malware",
                    pattern=pattern,
                    severity=severity,
                    description=description,
                    line_content=line_content,
                    line_number=line_num,
                ))

        return findings

    def _scan_injection(self, code: str) -> List[SecurityFinding]:
        """Scan code for prompt injection patterns."""
        findings = []
        code_lower = code.lower()
        lines = code.split("\n")

        for pattern, severity, description in PROMPT_INJECTION_PATTERNS:
            if pattern.lower() in code_lower:
                # Find the line
                line_num = 0
                line_content = ""
                for i, line in enumerate(lines, 1):
                    if pattern.lower() in line.lower():
                        line_num = i
                        line_content = line.strip()[:120]
                        break

                findings.append(SecurityFinding(
                    scan_type="prompt_injection",
                    pattern=pattern,
                    severity=severity,
                    description=description,
                    line_content=line_content,
                    line_number=line_num,
                ))

        return findings

    def _clean_code(self, code: str, findings: List[SecurityFinding]) -> str:
        """
        Clean detected threats from code.

        Strategy: Remove lines containing CRITICAL/HIGH severity patterns.
        For MEDIUM/LOW, comment them out with a warning.
        """
        lines = code.split("\n")
        critical_lines: Dict[int, SecurityFinding] = {}
        warn_lines: Dict[int, SecurityFinding] = {}

        for f in findings:
            if f.line_number > 0:
                if f.severity in ("CRITICAL", "HIGH"):
                    critical_lines[f.line_number] = f
                else:
                    warn_lines[f.line_number] = f

        cleaned = []
        for i, line in enumerate(lines, 1):
            if i in critical_lines:
                finding = critical_lines[i]
                cleaned.append(
                    f"# [CAJA SEGURA: REMOVED — {finding.severity}: {finding.description}]"
                )
            elif i in warn_lines:
                cleaned.append(f"# [CAJA SEGURA: WARNING] {line}")
            else:
                cleaned.append(line)

        return "\n".join(cleaned)

    # ──────────────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get the Caja Segura status."""
        last = self.scan_history[-1] if self.scan_history else None
        return {
            "name": self.name,
            "malware_scan": "active" if self.malware_scan_enabled else "off",
            "injection_scan": "active" if self.injection_scan_enabled else "off",
            "auto_clean": self.auto_clean,
            "strict_mode": self.strict_mode,
            "total_scanned": self.total_scanned,
            "total_cleaned": self.total_cleaned,
            "total_rejected": self.total_rejected,
            "last_scan_clean": last.is_clean if last else None,
            "last_scan_findings": len(last.findings) if last else 0,
        }

    def summary(self) -> str:
        """Human-readable Caja Segura summary."""
        lines = [
            "🔐 CAJA SEGURA",
            f"   Scans: {self.total_scanned} | Cleaned: {self.total_cleaned} | Rejected: {self.total_rejected}",
            f"   Malware: {'✅' if self.malware_scan_enabled else '❌'} | Prompt Injection: {'✅' if self.injection_scan_enabled else '❌'}",
        ]
        return "\n".join(lines)
