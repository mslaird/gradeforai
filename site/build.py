#!/usr/bin/env python3
"""
Simple static site builder for GradeForAI.
Assembles pages from partials to eliminate nav/footer drift.

Usage:
    python build.py              # Build all pages
    python build.py --watch      # Build and watch for changes
"""

import json
import os
import re
import sys
import time
import glob
import urllib.request

SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
OUT_DIR = os.path.dirname(__file__)  # Output to website/ root
PARTIALS_DIR = os.path.join(SRC_DIR, "partials")
PAGES_DIR = os.path.join(SRC_DIR, "pages")

# Pattern: <!-- PARTIAL:name --> or {{PARTIAL:name}}
PARTIAL_PATTERN = re.compile(r'(?:<!--\s*PARTIAL:(\w+)\s*-->|{{PARTIAL:(\w+)}})')

# Pattern: <!-- VAR:name:value -->
VAR_SET_PATTERN = re.compile(r'<!--\s*VAR:(\w+):(.+?)\s*-->')
VAR_USE_PATTERN = re.compile(r'{{VAR:(\w+)}}')

def load_industry_data():
    """Load industry_data.json and flatten into template variables."""
    json_path = os.path.join(os.path.dirname(__file__), "industry_data.json")
    if not os.path.exists(json_path):
        print(f"  Warning: {json_path} not found, skipping data injection")
        return {}

    with open(json_path) as f:
        data = json.load(f)

    v = {}

    # Top-level keys: {{BUSINESS_COUNT}}, {{BUSINESS_COUNT_RAW}}
    if "business_count" in data:
        v["BUSINESS_COUNT"] = str(data["business_count"])
    if "business_count_raw" in data:
        v["BUSINESS_COUNT_RAW"] = str(data["business_count_raw"])
    if "city_count" in data:
        v["CITY_COUNT"] = str(data["city_count"])
    if "vertical_count" in data:
        v["VERTICAL_COUNT"] = str(data["vertical_count"])

    # National averages: {{NATL_AVG}}, {{NATL_INCOMPATIBLE_PCT}}, {{NATL_AGENT_COMPAT}}, etc.
    for key, val in data.get("national", {}).items():
        v[f"NATL_{key.upper()}"] = str(val)

    # Industry reference (all-industries column on industry pages):
    # {{INDREF_AGENT_COMPAT}}, {{INDREF_TRANSACTION}}, etc.
    for key, val in data.get("industry_ref", {}).items():
        if key.startswith("_"):
            continue
        v[f"INDREF_{key.upper()}"] = str(val)

    # Per-industry: {{PLUMBING_AVG}}, {{PLUMBING_AGENT_COMPAT}}, etc.
    for ind, scores in data.get("industries", {}).items():
        prefix = ind.upper()
        for key, val in scores.items():
            v[f"{prefix}_{key.upper()}"] = str(val)

    # Benchmark verticals: {{BENCH_MEDICAL_COUNT}}, {{BENCH_MEDICAL_AVG}}, {{BENCH_MEDICAL_F_PCT}}
    for vert, scores in data.get("benchmark_verticals", {}).items():
        prefix = f"BENCH_{vert.upper()}"
        for key, val in scores.items():
            v[f"{prefix}_{key.upper()}"] = str(val)

    # Cities: {{DALLAS_AVG}}, {{DALLAS_F_PCT}}, {{DALLAS_PLUMBING_AVG}}, etc.
    for city, cdata in data.get("cities", {}).items():
        cpfx = city.upper()
        v[f"{cpfx}_AVG"] = str(cdata.get("avg", ""))
        v[f"{cpfx}_F_PCT"] = str(cdata.get("f_pct", ""))
        for vert, vdata in cdata.get("verticals", {}).items():
            vpfx = f"{cpfx}_{vert.upper()}"
            for key, val in vdata.items():
                v[f"{vpfx}_{key.upper()}"] = str(val)

    return v


def get_global_vars():
    """Build global template variables."""
    v = {}
    v.update(load_industry_data())
    # BUSINESS_COUNT from industry_data.json if available, else fallback
    if "BUSINESS_COUNT" not in v:
        v["BUSINESS_COUNT"] = "300,000+"
    if "BUSINESS_COUNT_RAW" not in v:
        v["BUSINESS_COUNT_RAW"] = "300000"
    return v


def load_partials():
    """Load all partial files into a dict."""
    partials = {}
    for f in glob.glob(os.path.join(PARTIALS_DIR, "*.html")):
        name = os.path.splitext(os.path.basename(f))[0]
        with open(f, "r") as fh:
            partials[name] = fh.read()
    return partials


def build_page(page_path, partials, global_vars):
    """Assemble a single page from its template and partials."""
    with open(page_path, "r") as f:
        content = f.read()

    # Extract page-level variables
    variables = {}
    for match in VAR_SET_PATTERN.finditer(content):
        variables[match.group(1)] = match.group(2)

    # Remove VAR declarations from output
    content = VAR_SET_PATTERN.sub("", content)

    # Replace partials
    def replace_partial(match):
        name = match.group(1) or match.group(2)
        partial = partials.get(name, f"<!-- MISSING PARTIAL: {name} -->")
        # Replace variables within partials too
        for var_name, var_value in variables.items():
            partial = partial.replace(f"{{{{VAR:{var_name}}}}}", var_value)
        return partial

    content = PARTIAL_PATTERN.sub(replace_partial, content)

    # Replace any remaining variables in the page itself
    for var_name, var_value in variables.items():
        content = content.replace(f"{{{{VAR:{var_name}}}}}", var_value)

    # Replace global variables
    for var_name, var_value in global_vars.items():
        content = content.replace(f"{{{{{var_name}}}}}", var_value)

    return content


def build_all():
    """Build all pages."""
    partials = load_partials()
    global_vars = get_global_vars()
    built = 0

    for root, dirs, files in os.walk(PAGES_DIR):
        for f in files:
            if not f.endswith(".html"):
                continue
            page_path = os.path.join(root, f)
            rel_path = os.path.relpath(page_path, PAGES_DIR)
            out_path = os.path.join(OUT_DIR, rel_path)

            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            result = build_page(page_path, partials, global_vars)
            with open(out_path, "w") as fh:
                fh.write(result)
            built += 1
            print(f"  Built: {rel_path}")

    print(f"\nDone. {built} pages built.")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        print("Watching for changes... (Ctrl+C to stop)")
        last_build = 0
        while True:
            latest = 0
            for root, dirs, files in os.walk(SRC_DIR):
                for f in files:
                    mtime = os.path.getmtime(os.path.join(root, f))
                    if mtime > latest:
                        latest = mtime
            if latest > last_build:
                print(f"\n[{time.strftime('%H:%M:%S')}] Changes detected, rebuilding...")
                build_all()
                last_build = time.time()
            time.sleep(1)
    else:
        build_all()
