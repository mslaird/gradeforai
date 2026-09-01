#!/usr/bin/env python3
"""Run the unit tests without requiring pytest."""
import sys, pathlib
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root)); sys.path.insert(0, str(root / "tests"))
import test_bands as m
p = f = 0
for n in sorted(x for x in dir(m) if x.startswith("test_")):
    try:
        getattr(m, n)(); print(f"PASS  {n}"); p += 1
    except Exception as e:
        print(f"FAIL  {n}: {e}"); f += 1
print(f"\n{p} passed, {f} failed")
raise SystemExit(1 if f else 0)
