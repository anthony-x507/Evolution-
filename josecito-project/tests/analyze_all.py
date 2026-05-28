#!/usr/bin/env python3
"""Complete codebase analysis for improvements."""
import sys, re, os

sys.path.insert(0, '.')

# Files to analyze (excluding tests and docs)
FILES = [
    'security.py', 'transparency.py', 'bus.py', 'adoption.py',
    'digos_lib/core_engineer.py', 'digos_lib/core_gateways.py',
    'digos_lib/core_vault.py', 'digos_lib/core_centinela.py',
    'digos_lib/core_self.py', 'digos_lib/core_log.py',
    'digos_lib/core_models.py', 'digos_lib/agent_core.py',
    'digos_lib/agent_tools.py', 'digos_lib/knowledge_base.py',
    'digos_lib/intent_classifier.py', 'digos_lib/provider_api.py',
    'digos_lib/gps.py', 'digos_lib/work_tracker.py',
    'digos_lib/self_awareness.py', 'digos_lib/engine.py',
]

print("=" * 60)
print("COMPLETE CODEBASE ANALYSIS — Improvements")
print("=" * 60)

for fpath in FILES:
    if not os.path.exists(fpath):
        continue
    with open(fpath) as f:
        content = f.read()
        lines = content.split('\n')

    issues = []

    # Check for bare excepts
    bare = 0
    for i, l in enumerate(lines):
        if re.match(r'\s*except\s*:', l):
            bare += 1
    if bare:
        issues.append(f"{bare} bare except(s) — hides errors")

    # Check for hardcoded timeouts
    hardcoded = 0
    for i, l in enumerate(lines):
        if 'timeout=' in l and re.search(r'timeout=\d+', l):
            hardcoded += 1
    if hardcoded:
        issues.append(f"{hardcoded} hardcoded timeout(s)")

    # Check for magic numbers
    magic = 0
    for i, l in enumerate(lines):
        if re.search(r'(?:if|elif|return)\s+.*\d{4,}', l) and '#' not in l:
            magic += 1
    if magic:
        issues.append(f"{magic} possible magic number(s)")

    # Check for missing docstrings on functions
    nodoc = 0
    for i, l in enumerate(lines):
        if re.match(r'    def \w+', l):
            # Check next line for docstring
            if i + 1 < len(lines) and '"""' not in lines[i+1]:
                nodoc += 1
    if nodoc:
        issues.append(f"{nodoc} function(s) without docstrings")

    # Check recursion depth
    recursions = 0
    for i, l in enumerate(lines):
        m = re.match(r'\s*def (\w+)', l)
        if m:
            fname = m.group(1)
            for j in range(i+1, min(i+50, len(lines))):
                if fname in lines[j] and 'return' in lines[j]:
                    recursions += 1
                    break

    # Check for os.system or subprocess without shell=False
    shell_insecure = 0
    for i, l in enumerate(lines):
        if 'shell=True' in l:
            shell_insecure += 1
    if shell_insecure:
        issues.append(f"{shell_insecure} shell=True — security risk")

    # Summary
    print(f"\n📄 {fpath} ({len(lines)} lines)")
    if issues:
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print(f"  ✅ Clean")

print("\n" + "=" * 60)
print("GLOBAL RECOMMENDATIONS")
print("=" * 60)
print("""
1. SECURITY: Add API key patterns for Claude (sk-ant), Gemini (AIza), Mistral
2. ERROR HANDLING: Replace bare excepts with specific exceptions
3. TESTING: Add unit tests for security.py scanner patterns
4. ARCHITECTURE: TorreDeControl has 72 methods — extract GatewayManager, KnowledgeManager
5. PERFORMANCE: _next_ticket_id counts filesystem on every call — cache the count
6. ROBUSTNESS: Add reconnection logic to GatewayTelegram
7. DOCUMENTATION: Add missing function docstrings
8. MAGIC NUMBERS: Extract hardcoded timeouts and delays to constants
""")
