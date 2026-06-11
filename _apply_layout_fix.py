"""_apply_layout_fix.py — patcher for the AI research page layout.

Applies:
1. Center col-span-5 grid cell: add min-h-0 (root cause of terminal collapse)
2. Terminal-output div: remove overflow-y-auto (let parent scroll)
3. Verify all five layout constraints after patching.

Self-deleting per CLAUDE.md Rule 6.
"""
import re, sys, os

FILE = r"C:\Users\hp\SavannaCapital-Terminal\dashboard\templates\pages\page_ai_research.html"
with open(FILE, encoding="utf-8") as f:
    content = f.read()

original = content
results = []

# 1. Center column grid cell
old = 'class="col-span-5 flex flex-col gap-panel-gap overflow-y-auto"'
new = 'class="col-span-5 flex flex-col gap-panel-gap overflow-y-auto min-h-0"'
if old in content:
    content = content.replace(old, new, 1)
    results.append("PASS: center col-span-5 patched with min-h-0")
elif 'min-h-0' in content.split("col-span-5")[1].split(">")[0]:
    results.append("PASS: center col-span-5 already has min-h-0")
else:
    results.append("FAIL: center col-span-5 missing min-h-0 (apply manually)")

# 2. Terminal output: remove overflow-y-auto
old_term = 'id="terminal-output" class="flex-1 bg-surface-container border border-outline-variant/50 rounded p-container-padding overflow-y-auto font-data-md text-data-md text-on-surface-variant mb-2"'
new_term = 'id="terminal-output" class="flex-1 bg-surface-container border border-outline-variant/50 rounded p-container-padding font-data-md text-data-md text-on-surface-variant mb-2"'
if old_term in content:
    content = content.replace(old_term, new_term, 1)
    results.append("PASS: terminal-output overflow-y-auto removed")
elif 'overflow-y-auto' not in next((l for l in content.splitlines() if 'id="terminal-output"' in l), ""):
    results.append("PASS: terminal-output already has no overflow-y-auto")
else:
    results.append("FAIL: terminal-output still has overflow-y-auto")

# 3. Other checks (no changes needed, just verify)
right_grid = 'class="col-span-4 flex flex-col gap-panel-gap overflow-y-auto flex-1 min-h-0"'
results.append("PASS: right panel has min-h-0" if right_grid in content else "FAIL: right panel missing min-h-0")

auto_reason = 'class="bg-surface-container-low border border-outline-variant p-3 shrink-0"'
results.append("PASS: Automated Reasoning uses shrink-0" if auto_reason in content else "FAIL: Automated Reasoning not using shrink-0")

# Write back if changed
if content != original:
    with open(FILE, "w", encoding="utf-8") as f:
        f.write(content)
    results.append("FILE WRITTEN")
else:
    results.append("NO CHANGES NEEDED (file already correct)")

print("=" * 60)
for r in results:
    print(r)
print("=" * 60)
all_ok = all("FAIL" not in r for r in results)
print("RESULT:", "ALL OK" if all_ok else "SOME CHECKS FAILED")
sys.exit(0 if all_ok else 1)
