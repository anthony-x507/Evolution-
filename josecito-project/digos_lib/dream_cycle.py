"""
dream_cycle.py — Nightly Self-Improvement Cycle
================================================
Inspired by Deep-Claw's Dream Cycle: the agent scans its own skills,
reflects on performance, and proposes improvements — once per night.

Two triggers:
1. Nightly alarm (2:00 AM) — full scan and improvement proposal
2. Skill audit (every 10 new skills) — lightweight focus on skill health
"""

import time
from pathlib import Path


class DreamCycle:
    """Nightly self-improvement cycle. Scans skills, checks knowledge,
    schedules next cycle, and reports via Engineer tickets.

    Called by Centinela alarm handler and skill audit trigger."""

    def __init__(self, log_keeper, centinela, engineer, knowledge=None):
        self._log = log_keeper
        self._centinela = centinela
        self._engineer = engineer
        self._knowledge = knowledge
        self._skill_count = 0
        self._skill_audit_threshold = 10

    # ── SKILL AUDIT (every 10 skills) ────────────

    def register_skill(self, skill_name: str = "") -> None:
        """Registers a new skill. Every 10 skills, triggers a full audit alarm."""
        self._skill_count += 1
        count = self._skill_count
        threshold = self._skill_audit_threshold

        self._log.info("dream", f"Skill registered ({count}/{threshold} until next audit)")

        if count >= threshold:
            alarm_time = time.time() + 60
            title = f"Skill audit: {count} skills registered"
            desc = (
                f"Auto-triggered skill audit. {count} skills accumulated "
                f"since the last audit. Review for duplicates, merges, relevance."
            )
            aid = self._centinela.schedule_alarm(alarm_time, title, desc)
            self._log.info("dream", f"Skill audit alarm scheduled: {aid}")
            self._skill_count = 0

    def run_skill_audit(self) -> str:
        """Runs the skill audit scan. Returns a formatted report string."""
        skills_dir = Path.home() / ".hermes" / "profiles" / "josecito" / "skills"
        if not skills_dir.is_dir():
            return "No skills directory found."

        categories = {}
        total = 0
        for cat_dir in sorted(skills_dir.iterdir()):
            if cat_dir.is_dir():
                count = len(list(cat_dir.glob("SKILL.md")))
                if count > 0:
                    categories[cat_dir.name] = count
                    total += count

        lines = [
            f"🔍 SKILL AUDIT — {total} skills, {len(categories)} categories",
            f"{'─' * 50}",
        ]
        for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 20)
            lines.append(f"  {bar} {count:3d}  {cat}")
        lines.append("")
        lines.append("Suggestions:")
        lines.append("  • Small categories (1-2 skills): consider merging")
        lines.append("  • Similar names: check for duplicates")
        lines.append("  • Unused skills: archive or delete")
        lines.append("")
        lines.append(f"Next audit in: {self._skill_audit_threshold} new skills")

        if self._engineer:
            self._engineer.create_ticket(
                "system", "skill_audit",
                f"Skill audit: {total} skills, {len(categories)} categories",
                "low", source="centinela"
            )

        return "\n".join(lines)

    # ── NIGHTLY DREAM CYCLE (2:00 AM) ────────────

    def schedule_nightly(self):
        """Schedules the next Dream Cycle at 2:00 AM UTC if not already pending."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        next_2am = tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)
        alarm_ts = next_2am.timestamp()

        # Check if already scheduled
        for al in self._centinela._alarms:
            if "dream-cycle" in al.get("id", ""):
                return  # already scheduled

        aid = self._centinela.schedule_alarm(
            alarm_ts,
            "Dream Cycle: knowledge scan and self-improvement",
            "Nightly self-improvement. Scans skills, checks for duplicates, "
            "updates knowledge base, and proposes improvements.",
        )
        self._log.info("dream", f"Nightly Dream Cycle scheduled: {aid}")

    def run_nightly(self) -> str:
        """Runs the full Dream Cycle. Called by Centinela alarm at 2:00 AM."""
        lines = ["🌙 DREAM CYCLE — Nightly self-improvement", f"{'─' * 50}"]

        # 1. Scan skills
        skills_dir = Path.home() / ".hermes" / "profiles" / "josecito" / "skills"
        if skills_dir.is_dir():
            total_skills = 0
            categories = {}
            for cat_dir in sorted(skills_dir.iterdir()):
                if cat_dir.is_dir():
                    count = len(list(cat_dir.glob("SKILL.md")))
                    if count > 0:
                        categories[cat_dir.name] = count
                        total_skills += count
            lines.append(f"\n📚 Skills: {total_skills} in {len(categories)} categories")

            small = [(c, n) for c, n in categories.items() if n <= 2]
            if small:
                lines.append(f"  ⚠️  {len(small)} small categories — merge candidates")
                for c, n in small[:5]:
                    lines.append(f"     • {c} ({n} skill(s))")

        # 2. Check knowledge base health
        if self._knowledge and self._knowledge.is_loaded():
            lines.append(f"\n🧠 Knowledge Base: {self._knowledge.file_count} files loaded")
            lines.append(f"   Files: {', '.join(self._knowledge.file_list)}")
        else:
            lines.append("\n🧠 Knowledge Base: not loaded")

        # 3. Schedule next cycle
        self.schedule_nightly()
        lines.append(f"\n🔄 Next cycle: tomorrow at 2:00 AM UTC")

        # 4. Log results
        report = "\n".join(lines)
        if self._engineer:
            self._engineer.create_ticket(
                "system", "dream_cycle",
                "Nightly Dream Cycle completed: skills review + knowledge check",
                "low", source="centinela"
            )
        return report
