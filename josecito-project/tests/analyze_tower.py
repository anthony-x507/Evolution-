#!/usr/bin/env python3
"""Analyze core_tower.py for issues and improvements."""
import sys, ast, re

sys.path.insert(0, '.')
with open('digos_lib/core_tower.py') as f:
    content = f.read()
    lines = content.split('\n')

print("=== CORE_TOWER.PY ANALYSIS ===")
print(f"Total lines: {len(lines)}")

# Check for duplicate docstrings
docstrings = re.findall(r'""".*?"""', content, re.DOTALL)
print(f"\nDocstrings: {len(docstrings)}")

# Check function count
funcs = re.findall(r'def \w+', content)
print(f"Methods: {len(funcs)}")

# Check for TODO/FIXME
todos = [(i+1, l.strip()) for i, l in enumerate(lines) if 'TODO' in l.upper() or 'FIXME' in l.upper()]
if todos:
    print(f"\n⚠️  TODOs/FIXMEs:")
    for n, l in todos:
        print(f"  L{n}: {l}")
else:
    print("\n✅ No TODOs/FIXMEs")

# Check for long methods (>100 lines)
print(f"\nMethod length analysis:")
current_method = ""
method_lines = 0
for i, line in enumerate(lines):
    if re.match(r'    def \w+', line):
        if current_method and method_lines > 100:
            print(f"  ⚠️  Long method: {current_method} ({method_lines} lines)")
        current_method = line.strip()
        method_lines = 0
    elif line.strip() and method_lines is not None:
        method_lines += 1

# Check for hardcoded sleep() values
sleeps = [(i+1, l.strip()) for i, l in enumerate(lines) if 'sleep(' in l]
print(f"\nsleep() calls: {len(sleeps)}")
for n, l in sleeps[:5]:
    print(f"  L{n}: {l}")

# Check error handling
excepts = [(i+1, l.strip()) for i, l in enumerate(lines) if 'except' in l]
bare_excepts = [(n, l) for n, l in excepts if 'Exception' not in l and 'Error' not in l and 'except:' in l]
if bare_excepts:
    print(f"\n⚠️  Bare excepts: {len(bare_excepts)}")
    for n, l in bare_excepts[:5]:
        print(f"  L{n}: {l}")
else:
    print("\n✅ No bare excepts")

print(f"\n=== RECOMMENDATIONS ===")
print("1. Some methods over 100 lines - consider splitting")
print("2. Review sleep() delays for hardcoded values")
print("3. Consider extracting gateway polling into separate class")
print(f"4. Class TorreDeControl has {len(funcs)} methods - consider domain separation")
