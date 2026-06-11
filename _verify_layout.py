"""
_verify_layout.py — Verify the three key layout fixes on the AI research page.

Checks:
1. Center column grid cell has min-h-0 (the critical missing constraint)
2. Right column grid cell has min-h-0
3. Terminal output div does NOT have min-h-[200px] and has the right overflow class
4. Automated Reasoning section uses shrink-0 not flex-1
5. Right panel outer div uses overflow-y-auto not overflow-hidden

This script is a self-deleting verification helper per CLAUDE.md Rule 6.
"""
import sys

FILE = r"C:\Users\hp\SavannaCapital-Terminal\dashboard\templates\pages\page_ai_research.html"

with open(FILE, encoding="utf-8") as f:
    content = f.read()

results = []

# 1. Center column: col-span-5 must have min-h-0
center_pattern = 'class="col-span-5 flex flex-col gap-panel-gap overflow-y-auto min-h-0"'
if center_pattern in content:
    results.append("PASS: Center column has min-h-0 (verified via parent pattern)")
else:
    results.append("FAIL: Center column missing min-h-0 — this is the ROOT CAUSE of terminal collapse")

# 2. Right column grid cell: must have min-h-0
right_grid = 'class="col-span-4 flex flex-col gap-panel-gap overflow-y-auto flex-1 min-h-0"'
if right_grid in content:
    results.append("PASS: Right panel grid cell has min-h-0")
else:
    results.append("FAIL: Right panel grid cell missing min-h-0")

# 3. Terminal output: must NOT have min-h-[200px]
term_line = None
for line in content.splitlines():
    if 'id="terminal-output"' in line:
        term_line = line.strip()
        break

if term_line:
    if "min-h-[200px]" not in term_line:
        results.append("PASS: Terminal output has no min-h-[200px]")
    else:
        results.append("FAIL: Terminal output still has min-h-[200px]")
    if 'overflow-y-auto' in term_line:
        results.append("PASS: Terminal output has overflow-y-auto")
    else:
        results.append("WARN: Terminal output missing overflow-y-auto")
else:
    results.append("FAIL: terminal-output div not found")

# 4. Automated Reasoning: must use shrink-0
auto_reason = 'class="bg-surface-container-low border border-outline-variant p-3 shrink-0"'
if auto_reason in content:
    results.append("PASS: Automated Reasoning uses shrink-0")
else:
    results.append("FAIL: Automated Reasoning not using shrink-0")

# 5. Right panel outer must use overflow-y-auto
if 'overflow-y-auto flex-1 min-h-0"' in content:
    results.append("PASS: Right panel uses overflow-y-auto")
else:
    results.append("FAIL: Right panel not using overflow-y-auto")

print("=" * 60)
print("LAYOUT VERIFICATION REPORT")
print("=" * 60)
for r in results:
    print(r)

all_pass = all("PASS" in r or "WARN" in r for r in results)
print("=" * 60)
if all_pass:
    print("RESULT:", "All layout checks passed.")
    sys.exit(0)
else:
    print("RESULT:", "Some checks FAILED — fix the issues above.")
    sys.exit(1)
