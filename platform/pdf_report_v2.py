"""
PDF report generation for GradeForAI AI Agent Preference Score Reports.
Uses WeasyPrint to convert styled HTML to PDF.

Design system: Bain & Company / BCG consulting report register.
All visual tokens imported from design_tokens.py.
No hardcoded colors, font sizes, or pixel values in this file.

v2.0 - April 2026: Full visual redesign.
v2.1 - April 21 2026: Cover page restructured (all normal flow, no overlap).
       High-scorer content path (>=70, no priority fixes):
         - "Maintaining Your Advantage" replaces empty Priority Action Plan
         - "Quarterly Optimization Roadmap" replaces empty Implementation Roadmap
         - Exec summary shows "3 Optimizations" instead of "0 Priority Fixes"
         - Two Paths Forward adjusted for maintenance vs implementation
       Bug fixes: masthead/footer logo lockup, competitor header truncation,
       percentile mismatch, business name normalization, DB-driven stats,
       distribution strip <2% label hiding.
"""

import json
import math
import os
import re
from datetime import datetime, timezone
from html import escape

import design_tokens as dt

# ---------------------------------------------------------------------------
# Path detection
# ---------------------------------------------------------------------------

_opt_reports = "/opt/agent-readiness/reports"
REPORTS_DIR = (
    _opt_reports
    if os.path.isdir(os.path.dirname(_opt_reports))
    else os.path.expanduser("~/agent-readiness/reports")
)

LOGO_PATH = dt.LOGO_SVG_PATH

CONTACT_EMAIL = "hello@gradeforai.com"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_db_count_label():
    """Get live business count, rounded to nearest 10K."""
    for base in ["/opt/agent-readiness", os.path.expanduser("~/agent-readiness")]:
        stats_path = os.path.join(base, "data", "db_stats.json")
        if os.path.isfile(stats_path):
            try:
                with open(stats_path) as f:
                    stats = json.load(f)
                count = stats.get("unique_businesses", 0)
                if count >= 1000:
                    rounded = math.floor(count / 10_000) * 10_000
                    return f"{rounded:,}+"
            except Exception:
                pass
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from storage import get_score_count
        count = get_score_count()
        if count >= 1000:
            rounded = math.floor(count / 10_000) * 10_000
            return f"{rounded:,}+"
    except Exception:
        pass
    return "300,000+"  # conservative floor; DB query preferred


def _get_cities_label():
    try:
        from storage import get_cities_count
        raw = get_cities_count()
        return f"{(raw // 50) * 50}+" if raw >= 50 else f"{raw}+"
    except Exception:
        return "200+"  # conservative floor; DB query preferred


def _get_verticals_label():
    try:
        from storage import get_verticals_count
        raw = get_verticals_count()
        return f"{(raw // 10) * 10}+" if raw >= 10 else str(raw)
    except Exception:
        return "150+"  # conservative floor; DB query preferred


def _normalize_business_name(name: str, domain: str = "") -> str:
    """Clean raw business name from DB for display in the PDF report.

    Handles: trailing '| City' or ' - Tagline', all-caps, domain echoes,
    'Home' or 'Homepage' suffixes, and excess whitespace.
    """
    if not name:
        return domain or ""
    # Strip trailing pipe/dash taglines  (e.g. "Acme Plumbing | Dallas TX")
    name = re.split(r"\s*[|\u2013\u2014]\s+", name, maxsplit=1)[0]
    name = re.split(r"\s+-\s+", name, maxsplit=1)[0]
    # Drop "Home", "Homepage", "Welcome to" noise
    name = re.sub(r"(?i)\s*-?\s*home\s*(?:page)?\s*$", "", name)
    name = re.sub(r"(?i)^welcome\s+to\s+", "", name)
    # If still ALL CAPS (>= 4 letters), title-case it
    alpha = re.sub(r"[^A-Za-z]", "", name)
    if len(alpha) >= 4 and alpha == alpha.upper():
        name = name.title()
    # Collapse whitespace
    name = " ".join(name.split())
    return name or domain or ""


# ---------------------------------------------------------------------------
# Dimension metadata (4 public-facing)
# ---------------------------------------------------------------------------

DIMENSIONS = [
    ("agent_accessibility", "Agent Accessibility",
     "Can AI agents physically navigate your website, interact with forms, "
     "and access content without being blocked?"),
    ("transaction_completeness", "Transaction Completeness",
     "Can AI agents complete the core transaction for your business type, "
     "whether that is booking, scheduling, or purchasing?"),
    ("data_reliability", "Data Reliability",
     "Is your operational data structured, accurate, and consistent so "
     "AI agents can extract and act on it reliably?"),
]

COMPETITIVE_POSITION = (
    "competitive_position", "Competitive Position",
    "How does your AI agent readiness compare to similar businesses "
    "in your area and industry?",
)

_INTERNAL_TO_PUBLIC = {
    "agent_compatibility": "agent_accessibility",
    "transaction_readiness": "transaction_completeness",
    "agentic_commerce": "transaction_completeness",
    "operational_data_structure": "data_reliability",
    "data_accuracy": "data_reliability",
}


# ---------------------------------------------------------------------------
# Recommendation rewriting (carried forward from v1)
# ---------------------------------------------------------------------------

_PLAIN_ENGLISH = {
    "Replace non-semantic interactive elements": "Replace non-semantic interactive elements (div onclick, span onclick) with proper HTML elements (button, a). AI agents use the accessibility tree to navigate your site, and semantic HTML is how they find and click things.",
    "Your site relies heavily on non-semantic": "Your site relies heavily on non-semantic interactive elements. AI agents parse the accessibility tree to interact with your site. Replace div onclick/span onclick patterns with proper button and anchor elements for full agent navigability.",
    "Add semantic HTML elements": "Add semantic HTML elements (nav, main, section, article, button) to your pages. These are how AI agents understand and navigate your site structure. Without them, agents cannot reliably find key content or interact with your business.",
    "Your CAPTCHA blocks AI agents": "Your challenge-based CAPTCHA blocks AI agents from completing tasks on your site. Upgrade to invisible CAPTCHA (Cloudflare Turnstile or reCAPTCHA v3) to maintain security while enabling AI agent access.",
    "Consider invisible CAPTCHA": "Consider adding invisible CAPTCHA (Cloudflare Turnstile) to prevent spam while maintaining full AI agent accessibility. Invisible CAPTCHA protects your forms without blocking legitimate agent interactions.",
    "Improve form accessibility for AI agents": "Improve form accessibility for AI agents by adding autocomplete attributes, label-for associations, specific input types (email, tel, date), and ARIA attributes on interactive elements. These help AI agents fill out and submit forms correctly.",
    "Fix heading hierarchy": "Fix your heading hierarchy to avoid skipping levels (e.g. h1 to h3). AI agents use headings to understand page structure and find relevant content sections.",
    "Add proper heading hierarchy": "Add proper heading hierarchy (h1, h2, h3) to your pages. AI agents rely on headings to comprehend page structure and locate key business information.",
    "Improve keyboard navigability": "Improve keyboard navigability by adding skip-nav links and ensuring all interactive elements are keyboard-accessible. AI agents navigate using keyboard-like interactions, so elements that require mouse-only interaction are invisible to them.",
    "Add viewport meta tag": "Add a viewport meta tag and responsive CSS to your site. Some AI agents render pages in mobile viewports, and a non-responsive site may display key content incorrectly for agent extraction.",
    "Add responsive CSS": "Add responsive CSS to ensure full mobile compatibility. Some AI agents render your site in mobile viewports for data extraction.",
    "Anti-bot platform": "Your anti-bot platform may block legitimate AI agent interactions. Consider allowlisting known AI agent user agents (GPTBot, ClaudeBot, PerplexityBot) to enable agent access while maintaining security.",
    "Integrate a transaction platform": "Connect a transaction platform (scheduling, ordering, or booking system) to your website so AI agents can complete tasks on behalf of users. This is the single highest-impact change for transaction readiness.",
    "Add a request or inquiry form": "Add a request or inquiry form with vertical-appropriate fields so AI agents can submit service requests on behalf of users.",
    "Integrate an online payment system": "Connect an online payment system (Stripe, Square, PayPal) so AI agents can facilitate payments and complete the full transaction loop.",
    "Add online payment capability": "Add online payment capability so AI agents can complete transactions. Without a payment integration, agents can only describe your services but cannot close the deal.",
    "Add clear transaction-oriented": "Add clear transaction-oriented calls to action (Book Now, Schedule, Get a Quote) for AI agent navigation. These anchor texts help agents identify and follow transaction paths.",
    "Add pricing or fee information": "Add pricing or fee information so AI agents can compare your services on behalf of users. Price transparency is a key factor in agent-driven purchase decisions.",
    "Reduce form fields": "Reduce your form fields to improve AI agent completion rate. Long forms with many required fields increase the likelihood of agent task failure.",
    "Enable guest access": "Enable guest checkout or guest access so AI agents can complete tasks without creating accounts. Login-required flows block most AI agent transaction attempts.",
    "Add /.well-known/agent.json": "Create an agent-card file (agent.json) at /.well-known/agent.json. This tells AI agents your capabilities, services, and how to interact with your business programmatically. Part of the A2A (Agent-to-Agent) protocol standard.",
    "Add /llms.txt": "Create an llms.txt file at your website root. This is a simple text file that tells AI language models what your business does, its services, and contact details. Takes 10 minutes to create.",
    "Consider implementing UCP": "Consider implementing UCP (Universal Commerce Protocol) or ACP (Agentic Commerce Protocol) for standardized AI shopping agent interaction. These emerging protocols enable direct agent-to-business transactions.",
    "Add Product or Service schema": "Add Product or Service schema with name, description, image, and pricing for AI agent comparison shopping. Complete schema enables agents to present your offerings alongside competitors.",
    "Add explicit AI bot directives": "Add explicit AI bot directives to your robots.txt file (GPTBot, ClaudeBot, PerplexityBot) to signal an intentional AI agent access policy. This tells agents whether they are welcome and what they can access.",
    "Add FAQPage schema": "Add FAQPage schema markup so AI agents can extract answers to common questions before initiating transactions. This pre-transaction information helps agents qualify your business for user requests.",
    "Add Service or Product schema with operational": "Add Service or Product schema with operational fields so AI agents know exactly what your business offers. Without structured service data, agents cannot match customer requests to your specific services.",
    "Add openingHoursSpecification": "Add openingHoursSpecification to your schema.org markup so AI agents can verify your business is open before booking or recommending. Hours data is critical for agents scheduling on behalf of users.",
    "Add geo coordinates": "Add geo coordinates (latitude/longitude) to your schema.org for precise AI agent location routing. Without coordinates, agents rely on less reliable address geocoding.",
    "Add a structured address": "Add a structured address to your schema.org markup so AI agents can reliably extract and verify your business location.",
    "Add address and geo coordinates": "Add address and geo coordinates to your schema.org markup so AI agents can route users and verify your service area.",
    "Add Offer schema with price": "Add Offer schema with price, priceCurrency, and availability so AI agents can compare your pricing with competitors in real time.",
    "Implement server-side rendering": "Implement server-side rendering (SSR) or pre-rendering so AI agents can access your content. AI crawlers do not execute JavaScript, which means client-side rendered content is invisible to them.",
    "Add areaServed": "Add areaServed to your schema.org markup with structured GeoShape or Place data for machine-readable service boundaries. This lets AI agents filter your business by geographic coverage.",
    "Add telephone and email to your schema": "Add telephone and email to your schema.org markup for programmatic contact info extraction by AI agents.",
    "Add schema.org JSON-LD with a LocalBusiness": "Add structured data markup (Schema.org LocalBusiness) to your website. This is code your web developer adds to your homepage that makes your business name, address, phone, hours, and services machine-readable for AI agents.",
    "Ensure business name, address, and phone are consistent": "Ensure your business name, address, and phone (NAP) are consistent across schema.org, page text, and footer. Inconsistent data causes AI agent task failures because agents cannot verify which information is correct.",
    "Add business name, address, and phone to schema": "Add your business name, address, and phone number to schema.org markup for consistent AI agent data extraction. Without structured NAP data, agents extract unreliably from page text.",
    "Update your copyright year": "Update your copyright year and ensure Last-Modified headers are current to signal that business hours and operational data are up to date. AI agents deprioritize sites that appear stale.",
    "Add openingHoursSpecification to schema.org for machine-readable hours": "Add openingHoursSpecification to your schema.org markup so AI agents can read your business hours in a structured format rather than parsing text.",
    "Add business hours to your site": "Add business hours to your site and schema.org markup. AI agents need to verify you are open before booking or recommending. Missing hours data is a common cause of agent recommendation failures.",
    "Add recent content": "Add recent content or update timestamps to signal active maintenance. AI agents deprioritize sites that appear stale or abandoned, as stale data leads to failed operations.",
    "Enable HTTPS": "Enable HTTPS on your website. AI agents may refuse to submit form data or complete transactions on insecure connections. HTTPS is a baseline requirement for agent trust.",
    "Ensure your SSL certificate is valid": "Ensure your SSL certificate is valid and not expired. Expired or invalid SSL certificates block AI agent task completion and trigger security warnings that prevent agent interaction.",
    "Ensure your business name is consistent": "Ensure your business name is consistent across schema.org, page title, and domain for AI agent identity verification. Mismatched names make agents unsure which entity they are interacting with.",
    "Add MCP server reference": "Add MCP (Model Context Protocol) hints to your website. This emerging standard lets AI agents interact with your business directly. Early adopters gain a significant advantage.",
}

_DIFFICULTY = {
    "llms.txt": ("Easy", "10 min", "+3-5"),
    "agent.json": ("Easy", "15 min", "+3-5"),
    "schema.org": ("Medium", "1-2 hours", "+10-20"),
    "structured data": ("Medium", "1-2 hours", "+5-15"),
    "semantic HTML": ("Medium", "1-3 hours", "+5-15"),
    "non-semantic": ("Medium", "1-3 hours", "+5-15"),
    "CAPTCHA": ("Medium", "30 min - 1 hour", "+5-10"),
    "invisible CAPTCHA": ("Medium", "30 min - 1 hour", "+5-10"),
    "form accessibility": ("Medium", "1-2 hours", "+5-10"),
    "autocomplete": ("Easy", "30 min", "+3-5"),
    "heading hierarchy": ("Easy", "30 min", "+3-5"),
    "keyboard": ("Medium", "1-2 hours", "+3-5"),
    "skip-nav": ("Easy", "15 min", "+2-3"),
    "viewport": ("Easy", "10 min", "+3-5"),
    "responsive CSS": ("Medium", "1-2 hours", "+3-5"),
    "anti-bot": ("Hard", "1-2 hours", "+3-5"),
    "transaction platform": ("Medium", "1-2 hours", "+15-25"),
    "scheduling": ("Medium", "1-2 hours", "+15-25"),
    "booking": ("Medium", "1-2 hours", "+15-25"),
    "request": ("Easy", "30 min", "+8-12"),
    "inquiry form": ("Easy", "30 min", "+8-12"),
    "payment system": ("Medium", "1-3 hours", "+10-15"),
    "payment capability": ("Medium", "1-3 hours", "+10-15"),
    "transaction-oriented": ("Easy", "15 min", "+3-5"),
    "pricing": ("Medium", "1-2 hours", "+5-10"),
    "fee information": ("Medium", "1-2 hours", "+5-10"),
    "form fields": ("Easy", "30 min", "+3-5"),
    "guest access": ("Easy", "30 min", "+3-5"),
    "guest checkout": ("Easy", "30 min", "+3-5"),
    "UCP": ("Hard", "2-4 hours", "+3-5"),
    "ACP": ("Hard", "2-4 hours", "+3-5"),
    "Product or Service schema": ("Medium", "1-2 hours", "+5-10"),
    "AI bot directives": ("Easy", "15 min", "+3-5"),
    "robots.txt": ("Easy", "15 min", "+3-5"),
    "FAQPage schema": ("Medium", "1 hour", "+3-5"),
    "Service or Product schema": ("Medium", "1-2 hours", "+10-15"),
    "openingHoursSpecification": ("Easy", "15 min", "+5-10"),
    "openingHours": ("Easy", "15 min", "+5-10"),
    "geo coordinates": ("Easy", "15 min", "+3-5"),
    "address": ("Easy", "15 min", "+3-5"),
    "areaServed": ("Easy", "15 min", "+3-5"),
    "Offer schema": ("Medium", "1 hour", "+5-10"),
    "server-side rendering": ("Hard", "4-8 hours", "+8-15"),
    "SSR": ("Hard", "4-8 hours", "+8-15"),
    "pre-rendering": ("Hard", "4-8 hours", "+8-15"),
    "telephone": ("Easy", "15 min", "+3-5"),
    "NAP": ("Easy", "30 min", "+5-10"),
    "business name": ("Easy", "15 min", "+3-5"),
    "copyright year": ("Easy", "5 min", "+2-3"),
    "Last-Modified": ("Easy", "15 min", "+2-3"),
    "business hours": ("Easy", "30 min", "+5-10"),
    "HTTPS": ("Medium", "1-2 hours", "+5-10"),
    "SSL": ("Easy", "30 min", "+3-5"),
    "identity": ("Easy", "30 min", "+3-5"),
    "MCP": ("Hard", "2-4 hours", "+3-5"),
    "recent content": ("Easy", "30 min", "+2-3"),
}

_CODE_SNIPPETS = {
    "llms.txt": '''# {business_name}

> {business_name} - [YOUR BUSINESS DESCRIPTION]

## Services
- [List your main services here]

## Contact
- Website: {url}
- Phone: [YOUR PHONE]
- Email: [YOUR EMAIL]
- Address: [YOUR ADDRESS]

## Hours
[YOUR BUSINESS HOURS]''',
    "schema.org": '''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "{business_name}",
  "url": "{url}",
  "telephone": "[YOUR PHONE]",
  "email": "[YOUR EMAIL]",
  "address": {{
    "@type": "PostalAddress",
    "streetAddress": "[YOUR ADDRESS]",
    "addressLocality": "[CITY]",
    "addressRegion": "[STATE]",
    "postalCode": "[ZIP]"
  }},
  "geo": {{
    "@type": "GeoCoordinates",
    "latitude": "[LATITUDE]",
    "longitude": "[LONGITUDE]"
  }},
  "openingHoursSpecification": [
    {{
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday","Tuesday","Wednesday","Thursday","Friday"],
      "opens": "08:00",
      "closes": "17:00"
    }}
  ],
  "priceRange": "$$",
  "description": "[YOUR BUSINESS DESCRIPTION]"
}}
</script>''',
    "agent.json": '''{{
  "name": "{business_name}",
  "description": "[YOUR BUSINESS DESCRIPTION]",
  "url": "{url}",
  "capabilities": ["booking", "quotes", "payments"],
  "contact": {{
    "phone": "[YOUR PHONE]",
    "email": "[YOUR EMAIL]"
  }}
}}''',
}

_SNIPPET_MATCH = {
    "llms.txt": ["llms.txt"],
    "schema.org": ["schema.org", "structured data", "LocalBusiness", "openingHoursSpecification", "areaServed", "Offer schema"],
    "agent.json": ["agent.json", "agent-card", "A2A"],
}


def _match_snippet_key(text):
    lower = text.lower()
    for snippet_key, keywords in _SNIPPET_MATCH.items():
        for kw in keywords:
            if kw.lower() in lower:
                return snippet_key
    return None


def _rewrite_rec(original):
    snippet_key = _match_snippet_key(original)
    for key, plain in _PLAIN_ENGLISH.items():
        if key.lower() in original.lower():
            for dk, (diff, time_est, impact) in _DIFFICULTY.items():
                if dk.lower() in original.lower():
                    return plain, diff, time_est, impact, snippet_key
            return plain, "Medium", "30 min - 1 hour", "+3-5", snippet_key
    return original, "Medium", "Varies", "+3-5", snippet_key


def _build_priority_actions(dims):
    _PRIORITY_TIER = {
        "agent_accessibility": 3,
        "transaction_completeness": 3,
        "data_reliability": 2,
    }
    all_dims = list(DIMENSIONS) + [COMPETITIVE_POSITION]
    actions = []
    for key, label, desc in all_dims:
        d = dims.get(key, {})
        if isinstance(d, dict):
            score = d.get("score", 0)
            recs = d.get("recommendations", [])
        else:
            score = d or 0
            recs = []
        if score >= 70 or not recs:
            continue
        gap = 100 - score
        priority_score = gap * _PRIORITY_TIER.get(key, 1)
        for rec in recs[:2]:
            plain, diff, time_est, impact, _snip = _rewrite_rec(rec)
            actions.append({
                "dimension": label, "dim_key": key, "dim_score": score,
                "action": plain, "difficulty": diff, "time": time_est,
                "impact": impact, "priority": priority_score,
            })
    actions.sort(key=lambda x: x["priority"], reverse=True)
    return actions[:7]


def _build_roi_actions(dims):
    _ROI_TIER = {"transaction_completeness": 5, "agent_accessibility": 4, "data_reliability": 3}
    all_dims = list(DIMENSIONS) + [COMPETITIVE_POSITION]
    actions = []
    for key, label, desc in all_dims:
        d = dims.get(key, {})
        if isinstance(d, dict):
            score = d.get("score", 0)
            recs = d.get("recommendations", [])
        else:
            score = d or 0
            recs = []
        if score >= 70 or not recs:
            continue
        gap = 100 - score
        roi_score = gap * _ROI_TIER.get(key, 1)
        for rec in recs[:1]:
            plain, diff, time_est, impact, _snip = _rewrite_rec(rec)
            actions.append({
                "dimension": label, "dim_key": key, "dim_score": score,
                "action": plain, "difficulty": diff, "time": time_est,
                "impact": impact, "roi": roi_score,
            })
    actions.sort(key=lambda x: x["roi"], reverse=True)
    return actions[:5]


# ---------------------------------------------------------------------------
# HTML component builders
# ---------------------------------------------------------------------------

def _eyebrow(text):
    """Tracked-out small-caps eyebrow label."""
    return (
        f'<div style="font-family:\'{dt.FONT_BODY}\',sans-serif;font-size:{dt.TYPE_EYEBROW};'
        f'font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};'
        f'color:{dt.GRAY_400};">{text}</div>'
    )


def _section_divider(number, title, thesis):
    """Full-page section divider."""
    return f"""
    <div style="page:divider;page-break-before:always;page-break-after:always;padding-top:140pt;">
        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_SECTION_NUM};
            font-weight:400;color:{dt.BRAND_BLUE};line-height:1;margin-bottom:{dt.SPACE_SM};">{number:02d}</div>
        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:14pt;
            font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};
            color:{dt.MUTED_SOFT};margin-bottom:{dt.SPACE_LG};">{title}</div>
        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_SECTION_THESIS};
            color:{dt.INK};line-height:1.4;max-width:{dt.DIVIDER_THESIS_MEASURE};">
            {thesis}
        </div>
        <hr style="border:none;border-top:{dt.RULE_STANDARD} solid {dt.RULE_COLOR};
            margin-top:180pt;margin-bottom:0;">
    </div>"""


def _source_attr(db_count):
    """Source attribution line for beneath data elements."""
    return (
        f'<div style="font-family:\'{dt.FONT_BODY}\',sans-serif;font-size:{dt.TYPE_SOURCE};'
        f'color:{dt.GRAY_400};margin-top:{dt.SPACE_SM};line-height:{dt.LEADING_TIGHT};">'
        f'{dt.source_line(db_count)}</div>'
    )


def _signal_label(signal_type):
    """Render OPERATIONAL or INFORMATIONAL inline label."""
    if signal_type == "OPERATIONAL":
        glyph = dt.SIGNAL_OPERATIONAL_GLYPH
    else:
        glyph = dt.SIGNAL_INFORMATIONAL_GLYPH
    return (
        f'<span style="font-family:\'{dt.FONT_BODY}\',sans-serif;font-size:{dt.TYPE_SIGNAL_LABEL};'
        f'font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};'
        f'padding:{dt.SIGNAL_PADDING_V} {dt.SIGNAL_PADDING_H};'
        f'border:{dt.RULE_STANDARD} solid {dt.ACCENT};display:inline-block;'
        f'line-height:1;margin-right:6pt;color:{dt.ACCENT};">'
        f'{glyph} {signal_type}</span>'
    )


def _render_finding(finding_text):
    """Render a finding with signal labels."""
    f = str(finding_text)
    if "[OPERATIONAL]" in f:
        clean = f.replace("[OPERATIONAL] ", "").replace("[OPERATIONAL]", "")
        return (
            f'<li style="margin-bottom:8pt;font-size:{dt.TYPE_BODY_SMALL};'
            f'line-height:{dt.LEADING_BODY};color:{dt.INK};">'
            f'{_signal_label("OPERATIONAL")}'
            f'{escape(clean)}</li>'
        )
    elif "[INFORMATIONAL]" in f:
        clean = f.replace("[INFORMATIONAL] ", "").replace("[INFORMATIONAL]", "")
        return (
            f'<li style="margin-bottom:8pt;font-size:{dt.TYPE_BODY_SMALL};'
            f'line-height:{dt.LEADING_BODY};color:{dt.INK};">'
            f'{_signal_label("INFORMATIONAL")}'
            f'{escape(clean)}</li>'
        )
    else:
        return (
            f'<li style="margin-bottom:6pt;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};'
            f'line-height:{dt.LEADING_BODY};">{escape(f)}</li>'
        )


def _code_block(filename, code, label="COPY INTO YOUR SITE"):
    """Deliverable-grade code block with header bar."""
    lines = code.strip().split("\n")
    numbered = ""
    for i, line in enumerate(lines, 1):
        # Escape HTML entities explicitly — use &#60; and &#62; for angle brackets
        # to prevent any HTML parser interference with <script> tags
        safe_line = line.replace("&", "&#38;").replace("<", "&#60;").replace(">", "&#62;").replace('"', "&#34;")
        numbered += (
            f'<span style="display:inline-block;width:24pt;color:{dt.GRAY_400};'
            f'font-size:{dt.TYPE_CODE_LINENUM};text-align:right;margin-right:12pt;'
            f'user-select:none;">{i}</span>{safe_line}\n'
        )
    return f"""
    <div style="margin:{dt.SPACE_MD} 0;page-break-inside:avoid;">
        {_eyebrow(label)}
        <div style="margin-top:{dt.SPACE_XS};border:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};overflow:hidden;">
            <div style="background:{dt.CODE_HEADER_BG};padding:6pt 12pt;
                font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_EYEBROW};
                font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};
                color:{dt.GRAY_500};">Template &middot; {escape(filename)}</div>
            <pre style="background:{dt.CODE_BG};margin:0;padding:12pt;
                font-family:'{dt.FONT_MONO}',monospace;font-size:{dt.TYPE_CODE};
                line-height:{dt.LEADING_CODE};color:{dt.INK};
                white-space:pre-wrap;overflow-x:auto;">{numbered}</pre>
        </div>
    </div>"""


def _callout_rule(text):
    """Pull-quote callout with 2pt accent rule on left edge."""
    return (
        f'<div style="border-left:{dt.RULE_EMPHASIS} solid {dt.ACCENT};'
        f'padding-left:{dt.GUTTER};margin:{dt.SPACE_MD} 0;">'
        f'<div style="font-family:\'{dt.FONT_DISPLAY}\',Georgia,serif;'
        f'font-size:{dt.TYPE_BODY};font-style:italic;color:{dt.INK};'
        f'line-height:{dt.LEADING_BODY};">{text}</div></div>'
    )


def _callout_box(text):
    """Warm off-white callout with hairline border."""
    return (
        f'<div style="background:{dt.CALLOUT_FILL};border:{dt.RULE_HAIRLINE} solid {dt.CALLOUT_BORDER};'
        f'padding:{dt.SPACE_MD};margin:{dt.SPACE_MD} 0;">'
        f'<div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};'
        f'line-height:{dt.LEADING_BODY};">{text}</div></div>'
    )


# ---------------------------------------------------------------------------
# MAIN REPORT GENERATOR
# ---------------------------------------------------------------------------

def generate_pdf_report(score_result, benchmarks=None, competitors=None, percentile=None, metro_benchmarks=None):
    """Generate the full consulting-grade PDF report. Returns file path."""

    # ---- Extract data ----
    domain = score_result.get("domain", "unknown")
    url = score_result.get("url", "")
    business_name = _normalize_business_name(
        score_result.get("business_name", ""), domain
    )
    composite = score_result.get("composite_score", 0)
    band = dt.band_name(composite)
    color = dt.band_color(composite)

    ai_pref_dims = score_result.get("ai_preference_dimensions") or {}
    internal_dims = score_result.get("dimension_scores", score_result.get("dimensions", {}))
    # If internal_dims is the full raw_json (fallback path), extract nested dimension_scores
    if isinstance(internal_dims, dict) and "dimension_scores" in internal_dims:
        internal_dims = internal_dims["dimension_scores"]

    if ai_pref_dims:
        dims = {}
        for key in ("agent_accessibility", "transaction_completeness", "data_reliability", "competitive_position"):
            val = ai_pref_dims.get(key)
            if val is not None:
                dims[key] = {"score": val, "findings": [], "recommendations": []}
        for int_key, pub_key in _INTERNAL_TO_PUBLIC.items():
            int_dim = internal_dims.get(int_key) or {}
            if isinstance(int_dim, dict) and pub_key in dims:
                dims[pub_key]["findings"].extend(int_dim.get("findings", []))
                dims[pub_key]["recommendations"].extend(int_dim.get("recommendations", []))
    else:
        def _ls(key):
            d = internal_dims.get(key) or {}
            return d.get("score", 0) if isinstance(d, dict) else (d or 0)
        dims = {
            "agent_accessibility": {
                "score": _ls("agent_compatibility"),
                "findings": (internal_dims.get("agent_compatibility") or {}).get("findings", []),
                "recommendations": (internal_dims.get("agent_compatibility") or {}).get("recommendations", []),
            },
            "transaction_completeness": {
                "score": (_ls("transaction_readiness") + _ls("agentic_commerce")) / 2,
                "findings": (internal_dims.get("transaction_readiness") or {}).get("findings", [])
                    + (internal_dims.get("agentic_commerce") or {}).get("findings", []),
                "recommendations": (internal_dims.get("transaction_readiness") or {}).get("recommendations", [])
                    + (internal_dims.get("agentic_commerce") or {}).get("recommendations", []),
            },
            "data_reliability": {
                "score": (_ls("operational_data_structure") + _ls("data_accuracy")) / 2,
                "findings": (internal_dims.get("operational_data_structure") or {}).get("findings", [])
                    + (internal_dims.get("data_accuracy") or {}).get("findings", []),
                "recommendations": (internal_dims.get("operational_data_structure") or {}).get("recommendations", [])
                    + (internal_dims.get("data_accuracy") or {}).get("recommendations", []),
            },
        }
        cp = internal_dims.get("competitive_position") or {}
        if isinstance(cp, dict) and cp.get("score", 0) > 0:
            dims["competitive_position"] = cp

    # Also grab competitive position findings from ai_pref path
    if "competitive_position" in dims:
        cp_internal = internal_dims.get("competitive_position") or {}
        if isinstance(cp_internal, dict):
            if not dims["competitive_position"].get("findings"):
                dims["competitive_position"]["findings"] = cp_internal.get("findings", [])
            if not dims["competitive_position"].get("recommendations"):
                dims["competitive_position"]["recommendations"] = cp_internal.get("recommendations", [])

    now = datetime.now(timezone.utc)
    now_display = now.strftime("%d %B %Y").upper()
    now_readable = now.strftime("%B %d, %Y")
    vertical = (benchmarks.get("vertical", "") if benchmarks else "") or score_result.get("vertical", "")
    city = (benchmarks.get("city", "") if benchmarks else "") or score_result.get("city", "")
    vertical_category = score_result.get("vertical_category", "") or vertical or "general"
    vertical_category_label = score_result.get("vertical_category_label", "") or vertical_category.replace("_", " ").title() or "General"

    has_competitive = "competitive_position" in dims
    all_dimensions = list(DIMENSIONS) + [COMPETITIVE_POSITION]
    num_dimensions = 4
    dims_scored = num_dimensions if has_competitive else 3

    db_count = _get_db_count_label()
    cities_label = _get_cities_label()
    verticals_label = _get_verticals_label()

    priority_actions = _build_priority_actions(dims)
    is_high_scorer = composite >= 70 and len(priority_actions) == 0
    roi_actions = _build_roi_actions(dims)

    # Sanity check: if any dimension has recommendations and scores below 70,
    # priority_actions must not be empty
    _total_recs = sum(len(d.get("recommendations", []) if isinstance(d, dict) else []) for d in dims.values())
    _any_below_70 = any((d.get("score", 0) if isinstance(d, dict) else (d or 0)) < 70 for d in dims.values())
    if _total_recs > 0 and _any_below_70 and len(priority_actions) == 0:
        raise AssertionError(
            f"priority_actions is empty but dims have {_total_recs} recommendations "
            f"with scores below 70. Data flow is broken."
        )

    scored_dims = [(k, d.get("score", 0) if isinstance(d, dict) else (d or 0)) for k, d in dims.items()]
    weakest = min(scored_dims, key=lambda x: x[1], default=("", 0))
    strongest = max(scored_dims, key=lambda x: x[1], default=("", 0))
    key_to_label = {k: l for k, l, _ in all_dimensions}
    weakest_label = key_to_label.get(weakest[0], weakest[0])
    strongest_label = key_to_label.get(strongest[0], strongest[0])

    # Industry avg
    industry_avg = None
    if benchmarks:
        bd = benchmarks.get("benchmarks", {})
        ca = bd.get("composite_score", {})
        industry_avg = ca.get("mean") if isinstance(ca, dict) else None

    # Band distribution
    try:
        from storage import get_band_distribution
        bdist = get_band_distribution()
    except Exception:
        bdist = {
            "Agent Incompatible": 12, "Agent Detected": 35, "Agent Functional": 30,
            "Agent Ready": 15, "Agent Optimized": 6, "Agent Preferred": 2,
        }

    # Tech stack - check score_result directly and also raw_data sub-dict
    _raw_data = score_result.get("raw_data", {}) or {}
    cms_detected = score_result.get("cms_detected") or _raw_data.get("cms_detected")
    payment_platforms = score_result.get("payment_platforms") or _raw_data.get("payment_platforms", []) or []
    chat_platforms = score_result.get("chat_platforms") or _raw_data.get("chat_platforms", []) or []
    review_platforms = score_result.get("review_platforms") or _raw_data.get("review_platforms", []) or []
    analytics_platforms = score_result.get("analytics_platforms") or _raw_data.get("analytics_platforms", []) or []
    form_platforms = score_result.get("form_platforms") or _raw_data.get("form_platforms", []) or []

    # Band definition
    band_def = {
        "Agent Preferred": "AI agents can fully navigate, transact with, and confidently recommend your business.",
        "Agent Optimized": "Strong foundation with minor gaps. AI agents can work with your business effectively.",
        "Agent Ready": "AI agents can handle basic tasks but gaps limit what they accomplish.",
        "Agent Functional": "AI agents find your business but struggle to complete transactions.",
        "Agent Detected": "AI agents have trouble interacting with your business meaningfully.",
        "Agent Incompatible": "AI agents cannot effectively navigate or transact with your business.",
    }.get(band, "")

    # ==================================================================
    # PAGE ASSEMBLY
    # ==================================================================

    # ---- Severity strip builder (reused on cover + glance page) ----
    def _severity_strip(active_band, composite_score):
        """Render 6-segment severity scale strip with active band elevated."""
        segs = ""
        ticks = ""
        x_pos = 0
        band_widths = {
            "Agent Incompatible": 10, "Agent Detected": 20, "Agent Functional": 20,
            "Agent Ready": 20, "Agent Optimized": 20, "Agent Preferred": 10,
        }
        for b in dt.BAND_ORDER:
            w = band_widths[b]
            bc = dt.BAND_COLORS[b]
            is_active = (b == active_band)
            h = dt.STRIP_SEGMENT_HEIGHT_ACTIVE if is_active else dt.STRIP_SEGMENT_HEIGHT_INACTIVE
            opacity = "1" if is_active else dt.STRIP_INACTIVE_OPACITY
            top_offset = "0" if is_active else "3px"
            segs += (
                f'<div style="position:absolute;left:{x_pos}%;width:{w}%;height:{h};'
                f'top:{top_offset};background:{bc};opacity:{opacity};"></div>'
            )
            x_pos += w
        # Tick marks at band boundaries
        x_pos = 0
        for i, b in enumerate(dt.BAND_ORDER):
            w = band_widths[b]
            tick_val = dt.BAND_TICK_POSITIONS[i]
            is_active_tick = (b == active_band)
            tc = dt.BAND_COLORS[b] if is_active_tick else dt.MUTED_SOFT
            fw = "700" if is_active_tick else "400"
            ticks += (
                f'<div style="position:absolute;left:{x_pos}%;font-size:{dt.TYPE_STRIP_TICK};'
                f'color:{tc};font-weight:{fw};font-feature-settings:{dt.TABULAR_FIGURES};'
                f'transform:translateX(-50%);">{tick_val}</div>'
            )
            x_pos += w
        # Final 100 tick
        ticks += (
            f'<div style="position:absolute;left:100%;font-size:{dt.TYPE_STRIP_TICK};'
            f'color:{dt.MUTED_SOFT};font-weight:400;font-feature-settings:{dt.TABULAR_FIGURES};'
            f'transform:translateX(-100%);">100</div>'
        )
        return f"""
        <div style="position:relative;height:14px;margin-top:12px;">
            {segs}
        </div>
        <div style="position:relative;height:14px;margin-top:2px;">
            {ticks}
        </div>"""

    # ---- Band pill builder ----
    def _band_pill(band_name_str, band_color_str):
        """Render a filled pill with band name in white text."""
        return (
            f'<span style="display:inline-block;background:{band_color_str};color:#FFFFFF;'
            f'font-family:\'{dt.FONT_BODY}\',sans-serif;font-size:{dt.COVER_PILL_PADDING and dt.TYPE_COVER_PILL};'
            f'font-weight:700;text-transform:uppercase;letter-spacing:0.12em;'
            f'padding:{dt.COVER_PILL_PADDING};border-radius:{dt.COVER_PILL_RADIUS};'
            f'line-height:1;">'
            f'<span style="display:inline-block;width:{dt.COVER_PILL_DOT_SIZE};height:{dt.COVER_PILL_DOT_SIZE};'
            f'background:#FFFFFF;border-radius:50%;vertical-align:middle;margin-right:6px;"></span>'
            f'{escape(band_name_str)}</span>'
        )

    # ---- COVER PAGE ----
    # All content in normal flow except the left band stripe.
    # This prevents overlap regardless of verdict text length.
    cover_html = f"""
    <div style="page:cover;position:relative;height:684pt;overflow:hidden;">
        <!-- Left-edge band stripe -->
        <div style="position:absolute;top:-54pt;left:-72pt;width:{dt.COVER_STRIPE_WIDTH};
            height:calc(100% + 108pt);background:{color};"></div>

        <!-- MASTHEAD -->
        <div style="padding-top:0;margin-bottom:0;">
            <table style="width:100%;border-collapse:collapse;">
                <tr>
                    <td style="vertical-align:middle;padding:0;">
                        <img src="file://{LOGO_PATH}" style="width:160px;height:auto;vertical-align:middle;" alt="GradeForAI">
                    </td>
                    <td style="vertical-align:middle;text-align:right;padding:0;">
                        <span style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_MASTHEAD_LABEL};
                            font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                            color:{dt.MUTED};">AI AGENT PREFERENCE REPORT</span>
                    </td>
                </tr>
            </table>
            <hr style="border:none;border-top:1px solid {dt.RULE_COLOR};margin:{dt.SPACE_SM} 0 0 0;">
        </div>

        <!-- PREPARED FOR -->
        <div style="margin-top:24px;">
            <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_MASTHEAD_LABEL};
                font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                color:{dt.BRAND_BLUE};margin-bottom:6px;">PREPARED FOR</div>
            <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;
                font-size:{'56pt' if len(domain) <= 18 else '44pt' if len(domain) <= 24 else '36pt' if len(domain) <= 32 else '30pt'};
                font-weight:500;color:{dt.INK};line-height:1.05;letter-spacing:-0.03em;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {escape(domain)}</div>
            <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:13pt;
                color:{dt.MUTED};margin-top:4px;">
                {escape(url or domain)}</div>
        </div>

        <!-- SCORE + PILL -->
        <div style="border-top:1px solid {dt.RULE_COLOR};
            padding:16px 0 0 0;margin-top:20px;">
            <div style="display:inline;vertical-align:baseline;">
                <span style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:120pt;
                    font-weight:600;color:{color};line-height:0.85;letter-spacing:-0.045em;
                    font-feature-settings:{dt.TABULAR_FIGURES};">{composite:.0f}</span>
                <span style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:36pt;
                    font-weight:400;color:{dt.MUTED_SOFT};">/100</span>
            </div>
            <div style="margin-top:8px;">
                {_band_pill(band, color)}
            </div>
        </div>

        <!-- VERDICT -->
        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:18pt;
            font-style:italic;font-weight:400;color:{dt.INK};line-height:1.32;
            max-width:420px;margin-top:14px;">{band_def}</div>

        <!-- SEVERITY STRIP -->
        <div style="margin-top:14px;">
            {_severity_strip(band, composite)}
        </div>

        <!-- METADATA ROW -->
        <div style="margin-top:14px;">
            <hr style="border:none;border-top:1px solid {dt.RULE_COLOR};margin:0 0 10px 0;">
            <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                <colgroup>
                    <col style="width:25%;"><col style="width:25%;">
                    <col style="width:25%;"><col style="width:25%;">
                </colgroup>
                <tr>
                    <td style="vertical-align:top;padding-right:12px;">
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_LABEL};
                            font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                            color:{dt.MUTED_SOFT};margin-bottom:4px;">SCAN DATE</div>
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_VALUE};
                            font-weight:500;color:{dt.INK};">{now_readable}</div>
                    </td>
                    <td style="vertical-align:top;padding-right:12px;">
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_LABEL};
                            font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                            color:{dt.MUTED_SOFT};margin-bottom:4px;">METHODOLOGY</div>
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_VALUE};
                            font-weight:500;color:{dt.INK};">v6.2</div>
                    </td>
                    <td style="vertical-align:top;padding-right:12px;">
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_LABEL};
                            font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                            color:{dt.MUTED_SOFT};margin-bottom:4px;">INDUSTRY</div>
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_VALUE};
                            font-weight:500;color:{dt.INK};">{escape(vertical_category_label)}</div>
                    </td>
                    <td style="vertical-align:top;">
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_LABEL};
                            font-weight:600;text-transform:uppercase;letter-spacing:0.16em;
                            color:{dt.MUTED_SOFT};margin-bottom:4px;">CLASSIFICATION</div>
                        <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_META_VALUE};
                            font-weight:500;color:{dt.INK};">Confidential</div>
                    </td>
                </tr>
            </table>
        </div>

        <!-- FOOTER -->
        <div style="margin-top:12px;">
            <hr style="border:none;border-top:1px solid {dt.RULE_COLOR};margin:0 0 10px 0;">
            <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                <colgroup>
                    <col style="width:auto;">
                    <col style="width:60%;">
                </colgroup>
                <tr>
                    <td style="vertical-align:middle;padding:0;white-space:nowrap;">
                        <img src="file://{LOGO_PATH}" style="width:90px;height:auto;vertical-align:middle;" alt="GradeForAI">
                    </td>
                    <td style="vertical-align:middle;text-align:right;padding:0;">
                        <span style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:8pt;
                            text-transform:uppercase;letter-spacing:0.1em;
                            color:{dt.MUTED};">THE SCORING STANDARD FOR AI AGENT PREFERENCE&trade;</span>
                    </td>
                </tr>
            </table>
        </div>
    </div>"""

    # ---- TABLE OF CONTENTS ----
    toc_sections = [
        ("01", "Executive Summary"),
        ("02", "AI Agent Preference and Why It Matters"),
        ("03", "Scoring Methodology"),
        ("04", "Your Score at a Glance"),
    ]
    if has_competitive:
        toc_sections.append(("05", "Competitive Position"))
    toc_sections.append(("06" if has_competitive else "05",
                         "Maintaining Your Advantage" if is_high_scorer else "Priority Action Plan"))
    toc_sections.append(("07" if has_competitive else "06", "Detailed Findings"))
    if competitors:
        toc_sections.append(("08", "Competitor Comparison"))
    toc_sections.extend([
        ("09", "Optimization Roadmap" if is_high_scorer else "Implementation Roadmap"),
        ("10", "Two Paths Forward"),
        ("11", "About GradeForAI"),
    ])

    toc_rows = ""
    for num, title in toc_sections:
        toc_rows += (
            f'<tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">'
            f'<td style="padding:10pt 0;font-family:\'{dt.FONT_BODY}\',sans-serif;'
            f'font-size:{dt.TYPE_BODY_SMALL};color:{dt.ACCENT};font-weight:600;width:36pt;'
            f'font-feature-settings:{dt.TABULAR_FIGURES};">{num}</td>'
            f'<td style="padding:10pt 0;font-family:\'{dt.FONT_BODY}\',sans-serif;'
            f'font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">{title}</td></tr>'
        )

    toc_html = f"""
    <div style="page-break-before:always;padding-top:{dt.SPACE_XL};">
        <h1>Contents</h1>
        <table style="width:60%;border-collapse:collapse;margin-top:{dt.SPACE_MD};">
            <tbody>{toc_rows}</tbody>
        </table>
    </div>"""

    # ---- EXECUTIVE SUMMARY ----
    exec_divider = _section_divider(1, "Executive Summary",
        "The essential findings from your AI agent readiness assessment.")

    _vrt = vertical or vertical_category_label or "service provider"
    _city_name = city or ""
    _will_not = "will not" if composite < 50 else "may" if composite < 70 else "will likely"
    _bottom_line = (
        f'Right now, if a customer asks an AI agent to find a {_vrt} '
        f'{"in " + _city_name if _city_name else "in your area"}, '
        f'your business <strong>{_will_not}</strong> be among the options presented.'
    )

    exec_html = f"""
    <div style="page-break-before:always;">
        <h1>Executive Summary</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <!-- Three-column at-a-glance strip -->
        <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_LG};">
            <tr>
                <td style="width:33%;vertical-align:top;padding-right:{dt.GUTTER};">
                    {_eyebrow("Strongest Dimension")}
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                        {strongest[1]:.0f}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-top:2pt;">
                        {strongest_label}</div>
                </td>
                <td style="width:33%;vertical-align:top;padding-right:{dt.GUTTER};">
                    {_eyebrow("Weakest Dimension")}
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                        {weakest[1]:.0f}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-top:2pt;">
                        {weakest_label}</div>
                </td>
                <td style="width:33%;vertical-align:top;">
                    {_eyebrow("Optimizations" if is_high_scorer else "Priority Fixes")}
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                        {"3" if is_high_scorer else str(len(priority_actions))}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-top:2pt;">
                        {"Advanced" if is_high_scorer else "Identified"}</div>
                </td>
            </tr>
        </table>

        <!-- Bottom-line statement -->
        <div style="border-left:{dt.RULE_EMPHASIS} solid {dt.ACCENT};padding-left:{dt.GUTTER};
            margin-bottom:{dt.SPACE_LG};">
            <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_BODY};
                color:{dt.INK};line-height:{dt.LEADING_BODY};">
                {_bottom_line}
            </div>
        </div>

        <!-- Narrative -->
        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
            margin-bottom:{dt.SPACE_MD};">
            <strong>{escape(business_name)}</strong> scored
            <strong>{composite:.0f}/100 ({band})</strong> on AI Agent Preference.
            Your strongest dimension is <strong>{strongest_label}</strong> ({strongest[1]:.0f}/100)
            and your biggest gap is <strong>{weakest_label}</strong> ({weakest[1]:.0f}/100).
            {f'Compared to {vertical} businesses in our database, you score higher than {percentile:.0f}%.' if percentile else ''}
        </div>

        {f'<div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">This report identifies <strong>{len(priority_actions)} priority fixes</strong> that can meaningfully improve your score. The highest-impact change is improving your <strong>{priority_actions[0]["dimension"]}</strong> (currently {priority_actions[0]["dim_score"]:.0f}/100).</div>' if priority_actions else (f'<div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">Your site is already well-optimized for AI agents. This report identifies <strong>3 advanced optimizations</strong> to extend your lead and ensure you stay ahead as the AI agent ecosystem evolves.</div>' if is_high_scorer else '')}

        {_callout_box(f'<strong>The math:</strong> This report costs $199. The fixes it identifies typically cost $1,500 to $5,000 to implement. The revenue they protect is ongoing: every customer an AI agent routes to a competitor instead of you is a customer lost permanently.')}

        {_source_attr(db_count)}
    </div>"""

    # ---- WHAT IS AI AGENT PREFERENCE ----
    aao_divider = _section_divider(2, "AI Agent Preference",
        "Why AI agents are becoming the primary interface between consumers and businesses.")

    aao_html = f"""
    <div style="page-break-before:always;">
        <h1>AI Agent Preference and Why It Matters</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
            margin-bottom:{dt.SPACE_MD};">
            AI agents are software that acts on behalf of users to accomplish tasks: scheduling
            appointments, comparing services, making purchases. Examples include ChatGPT, Google Gemini,
            Apple Intelligence, and Claude. These agents do not browse the internet the way humans do.
            They parse structured data, navigate accessibility trees, and interact with forms programmatically.
        </div>

        {_callout_rule('"Every company needs an agentic system strategy. This is the new computer." -- Jensen Huang, CEO of NVIDIA, GTC Conference March 2026')}

        <h2>The Four Dimensions</h2>
        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
            margin-bottom:{dt.SPACE_SM};">
            GradeForAI measures AI agent readiness across four dimensions:
        </div>

        <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_MD};">
            <tr style="border-top:{dt.RULE_STANDARD} solid {dt.GRAY_300};
                border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                <td style="padding:8pt 12pt 8pt 0;font-weight:600;color:{dt.INK};
                    font-size:{dt.TYPE_BODY_SMALL};width:35%;">Agent Accessibility</td>
                <td style="padding:8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};
                    line-height:{dt.LEADING_BODY};">Can AI agents physically navigate your site?
                    Semantic HTML, form accessibility, CAPTCHA impact, keyboard navigability.</td>
            </tr>
            <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                <td style="padding:8pt 12pt 8pt 0;font-weight:600;color:{dt.INK};
                    font-size:{dt.TYPE_BODY_SMALL};">Transaction Completeness</td>
                <td style="padding:8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};
                    line-height:{dt.LEADING_BODY};">Can AI agents complete the core transaction?
                    Booking, scheduling, ordering, quoting, or purchasing.</td>
            </tr>
            <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                <td style="padding:8pt 12pt 8pt 0;font-weight:600;color:{dt.INK};
                    font-size:{dt.TYPE_BODY_SMALL};">Data Reliability</td>
                <td style="padding:8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};
                    line-height:{dt.LEADING_BODY};">Is operational data structured, accurate,
                    and consistent for reliable agent extraction?</td>
            </tr>
            <tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                <td style="padding:8pt 12pt 8pt 0;font-weight:600;color:{dt.INK};
                    font-size:{dt.TYPE_BODY_SMALL};">Competitive Position</td>
                <td style="padding:8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};
                    line-height:{dt.LEADING_BODY};">How does your readiness compare to businesses
                    in your area and industry?</td>
            </tr>
        </table>

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};page-break-before:avoid;">
            The businesses that achieve AI agent readiness first will capture the customers that
            AI sends. The ones that wait will lose transactions to competitors whose sites agents
            can actually use.
        </div>
    </div>"""

    # ---- METHODOLOGY ----
    meth_divider = _section_divider(3, "Scoring Methodology",
        "How we measure AI agent readiness across four dimensions.")

    methodology_html = f"""
    <div style="page-break-before:always;">
        <h1>Our Scoring Methodology</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
            margin-bottom:{dt.SPACE_MD};">
            GradeForAI's AI Agent Preference Score evaluates your business across {num_dimensions}
            dimensions of AI agent readiness. Each dimension measures a distinct capability that
            AI agents need to physically use your website and act on behalf of your customers.
            Scores are industry-calibrated to ensure fair evaluation for your business category.
        </div>

        <h2>Capability Bands</h2>
        <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_MD};">
            <thead>
                <tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};
                        font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};
                        color:{dt.GRAY_400};">Band</th>
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};
                        font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};
                        color:{dt.GRAY_400};">Score</th>
                    <th style="padding:6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};
                        font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};
                        color:{dt.GRAY_400};">Meaning</th>
                </tr>
            </thead>
            <tbody>
                <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Preferred']};margin-right:6px;vertical-align:middle;"></span>Agent Preferred</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">90-100</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Fully operational for AI agents</td>
                </tr>
                <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Optimized']};margin-right:6px;vertical-align:middle;"></span>Agent Optimized</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">70-89</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Strong with minor gaps</td>
                </tr>
                <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Ready']};margin-right:6px;vertical-align:middle;"></span>Agent Ready</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">50-69</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Basic tasks possible, gaps limit capability</td>
                </tr>
                <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Functional']};margin-right:6px;vertical-align:middle;"></span>Agent Functional</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">30-49</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Agents find you but cannot transact</td>
                </tr>
                <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Detected']};margin-right:6px;vertical-align:middle;"></span>Agent Detected</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">10-29</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Minimal agent interaction possible</td>
                </tr>
                <tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.RULE_COLOR};">
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dt.BAND_COLORS['Agent Incompatible']};margin-right:6px;vertical-align:middle;"></span>Agent Incompatible</td>
                    <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.MUTED};font-feature-settings:{dt.TABULAR_FIGURES};">0-9</td>
                    <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">Agents cannot use your site</td>
                </tr>
            </tbody>
        </table>

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};">
            Industry category for this report: <strong>{escape(vertical_category_label)}</strong>.
            Vertical-specific calibration ensures that a {escape(vertical or 'business')} is evaluated
            against the standards of its own industry, not against unrelated business types.
        </div>

        {_source_attr(db_count)}
    </div>"""

    # ---- SCORE AT A GLANCE ----
    glance_divider = _section_divider(4, "Your Score at a Glance",
        "Four dimensions of AI agent readiness, industry-calibrated for your vertical.")

    # Build dimension rows
    dim_rows_html = ""
    for key, label, description in all_dimensions:
        if key == "competitive_position" and not has_competitive:
            dim_rows_html += f"""
            <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                <td style="padding:10pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};">{label}</td>
                <td style="padding:10pt 0;text-align:right;font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_400};
                    font-feature-settings:{dt.TABULAR_FIGURES};">N/A</td>
                <td style="padding:10pt 12pt;width:50%;">
                    <div style="height:{dt.BAR_HEIGHT};background:{dt.GRAY_300};"></div>
                </td>
            </tr>"""
            continue
        d = dims.get(key, {})
        s = d.get("score", 0) if isinstance(d, dict) else (d or 0)
        dim_bar_color = dt.band_color(s)
        dim_rows_html += f"""
        <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.RULE_COLOR};">
            <td style="padding:10pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:600;color:{dt.INK};">{label}</td>
            <td style="padding:10pt 0;text-align:right;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};
                font-weight:600;font-feature-settings:{dt.TABULAR_FIGURES};">{s:.0f}</td>
            <td style="padding:10pt 12pt;width:50%;">
                <div style="position:relative;height:{dt.BAR_HEIGHT};background:{dt.RULE_COLOR};">
                    <div style="position:absolute;top:0;left:0;height:{dt.BAR_HEIGHT};
                        width:{max(1, s)}%;background:{dim_bar_color};"></div>
                    {f'<div style="position:absolute;top:-4pt;left:{industry_avg}%;width:1.5pt;height:{dt.BAR_TICK_HEIGHT};background:{dt.INK_SOFT};"></div><div style="position:absolute;top:-14pt;left:{industry_avg}%;font-size:{dt.TYPE_STRIP_TICK};color:{dt.INK_SOFT};font-weight:600;font-feature-settings:{dt.TABULAR_FIGURES};transform:translateX(-50%);">{industry_avg:.0f}</div>' if industry_avg else ''}
                </div>
            </td>
        </tr>"""

    # Band strip - always show all 6 bands, even at 0%
    band_order = dt.BAND_ORDER
    cumulative = 0
    marker_pos = 50
    for b in band_order:
        pct = bdist.get(b, 0)
        if b == band:
            marker_pos = cumulative + (pct / 2)
            break
        cumulative += pct

    strip_segments = ""
    strip_labels = ""
    for b in band_order:
        pct = bdist.get(b, 0)
        bc = dt.BAND_COLORS[b]
        is_user_band = (b == band)
        opacity = "1" if is_user_band else "0.4"
        display_pct = max(pct, 2)  # ensure even 0% bands get a sliver
        strip_segments += f'<td style="width:{display_pct}%;height:{dt.BAND_STRIP_HEIGHT};background:{bc};opacity:{opacity};padding:0;border:none;"></td>'
        short = b.replace("Agent ", "")
        label_color = dt.INK if is_user_band else dt.MUTED_SOFT
        label_weight = "700" if is_user_band else "400"
        # Hide labels entirely for very narrow segments (<2%), abbreviate for <5%
        if is_user_band:
            label_text = f"{short}<br>{pct}%"
        elif pct < 2:
            label_text = ""
        elif pct < 5:
            label_text = f"{pct}%"
        else:
            label_text = f"{short}<br>{pct}%"
        strip_labels += f'<td style="width:{display_pct}%;padding:4pt 0 0 0;text-align:center;font-size:6.5pt;color:{label_color};font-weight:{label_weight};border:none;line-height:1.2;">{label_text}</td>'

    glance_html = f"""
    <div style="page-break-before:always;">
        <table style="width:100%;border-collapse:collapse;">
        <tr>
        <td style="width:66%;vertical-align:top;padding-right:{dt.GUTTER};">

        <h1>Your Score at a Glance</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <div style="margin-bottom:{dt.SPACE_MD};">
            <span style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:48pt;
                font-weight:700;color:{dt.INK};font-feature-settings:{dt.TABULAR_FIGURES};
                line-height:1;">{composite:.0f}</span>
            <span style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_500};margin-left:6pt;">/100</span>
            <div style="font-size:{dt.TYPE_EYEBROW};font-weight:600;text-transform:uppercase;
                letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};margin-top:{dt.SPACE_XS};">{band}</div>
        </div>

        <table style="width:100%;border-collapse:collapse;">
            <thead><tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                <th style="padding:6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                    text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Dimension</th>
                <th style="padding:6pt 0;text-align:right;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                    text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Score</th>
                <th style="padding:6pt 12pt;width:50%;"></th>
            </tr></thead>
            <tbody>{dim_rows_html}</tbody>
            <tfoot><tr style="border-top:{dt.RULE_STANDARD} solid {dt.RULE_COLOR};">
                <td style="padding:10pt 0;font-size:{dt.TYPE_BODY_SMALL};font-weight:700;color:{dt.INK};">Composite</td>
                <td style="padding:10pt 0;text-align:right;font-size:{dt.TYPE_BODY_SMALL};font-weight:700;color:{dt.INK};
                    font-feature-settings:{dt.TABULAR_FIGURES};">{composite:.0f}</td>
                <td style="padding:10pt 12pt;width:50%;"><div style="position:relative;height:{dt.BAR_HEIGHT};background:{dt.RULE_COLOR};">
                    <div style="position:absolute;top:0;left:0;height:{dt.BAR_HEIGHT};width:{max(1,composite)}%;background:{color};"></div>
                </div></td>
            </tr></tfoot>
        </table>

        {_source_attr(db_count)}

        <!-- Band distribution -->
        <div style="margin-top:{dt.SPACE_LG};">
            {_eyebrow("Score Distribution")}
            <div style="position:relative;margin-top:{dt.SPACE_SM};">
                <div style="position:absolute;top:-10pt;left:{marker_pos}%;margin-left:-5pt;
                    width:0;height:0;border-left:5pt solid transparent;border-right:5pt solid transparent;
                    border-top:6pt solid {dt.INK};"></div>
                <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                    <tr>{strip_segments}</tr>
                </table>
                <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                    <tr>{strip_labels}</tr>
                </table>
            </div>
            <div style="font-size:{dt.TYPE_SOURCE};color:{dt.GRAY_400};margin-top:{dt.SPACE_XS};">
                Your band: <strong style="color:{dt.INK};">{band}</strong>. Marker shows position among {db_count} scored businesses.
            </div>
        </div>

        </td>
        <td style="width:34%;vertical-align:top;padding-top:80pt;">
            <div style="padding-left:{dt.SPACE_SM};border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                {_eyebrow("How to Read")}
                <p style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};
                    margin:{dt.SPACE_SM} 0;">Each bar shows your score (0-100). The ink-blue fill is your score.
                    {f'The amber tick marks the industry average ({industry_avg:.0f}).' if industry_avg else ''}</p>
                <p style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};
                    margin:0 0 {dt.SPACE_SM} 0;">Scores are industry-calibrated: a 60 in dental means something
                    different than a 60 in legal services.</p>
                <p style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};
                    margin:0;">The strip below shows where you fall among all {db_count} businesses in our database.</p>
            </div>
        </td>
        </tr>
        </table>
    </div>"""

    # ---- COMPETITIVE POSITION ----
    competitive_html = ""
    if has_competitive:
        cp = dims.get("competitive_position", {})
        cp_score = cp.get("score", 0) if isinstance(cp, dict) else 0
        cp_findings = cp.get("findings", []) if isinstance(cp, dict) else []
        cp_meta = cp.get("_competitive_meta", {}) if isinstance(cp, dict) else {}
        _cp_cohort = cp_meta.get("cohort_size", 0)
        if not _cp_cohort and competitors:
            _cp_cohort = len([c for c in competitors if c.get("composite_score", 0) > 0])
        _cp_percentile = percentile or cp_meta.get("percentile", 0) or cp_score

        cp_findings_html = ""
        if cp_findings:
            items = "".join(_render_finding(f) for f in cp_findings)
            cp_findings_html = f'<ul style="margin:0;padding-left:16pt;">{items}</ul>'
        elif _cp_cohort > 0:
            _cp_location = f" in {escape(city)}" if city else ""
            _cp_vert = f" {escape(vertical)}" if vertical else ""
            cp_findings_html = f'<div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};">Ranked in the {dt.ordinal(int(_cp_percentile))} percentile among {_cp_cohort}{_cp_vert} businesses{_cp_location}.</div>'

        competitive_html = f"""
        <div style="page-break-before:always;">
            <h1>Competitive Position</h1>
            <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

            <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_LG};">
                <tr>
                    <td style="width:33%;vertical-align:top;">
                        {_eyebrow("Percentile Rank")}
                        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H1};
                            color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                            {dt.ordinal(int(_cp_percentile))}</div>
                    </td>
                    <td style="width:33%;vertical-align:top;">
                        {_eyebrow("Businesses Compared")}
                        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H1};
                            color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                            {_cp_cohort if _cp_cohort else 'N/A'}</div>
                    </td>
                    <td style="width:33%;vertical-align:top;">
                        {_eyebrow("Competitive Score")}
                        <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H1};
                            color:{dt.INK};margin-top:{dt.SPACE_XS};font-feature-settings:{dt.TABULAR_FIGURES};">
                            {cp_score:.0f}/100</div>
                    </td>
                </tr>
            </table>

            {cp_findings_html}
            {_source_attr(db_count)}
        </div>"""
    else:
        competitive_html = f"""
        <div style="page-break-before:always;">
            <h1>Competitive Position</h1>
            <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">
            {_callout_box(f'Competitive Position compares your AI agent readiness against businesses in the same industry and geographic area. There is not yet enough data in your vertical and location to generate a valid comparison (minimum 15 businesses required). This dimension has been excluded from your composite score. Your score reflects the remaining 3 dimensions only.')}
            <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_500};margin-top:{dt.SPACE_SM};line-height:{dt.LEADING_BODY};">
                As our database grows, competitive positioning data may become available for your market.
            </div>
        </div>"""

    # ---- PRIORITY ACTION PLAN / MAINTAINING YOUR ADVANTAGE ----
    _pap_section_num = 5 if not has_competitive else 6

    if is_high_scorer:
        priority_divider = _section_divider(_pap_section_num, "Maintaining Your Advantage",
            "Advanced optimizations to extend your lead.")

        # Build list of remaining gaps even above 70
        _gap_items = []
        for key, label, _desc in DIMENSIONS:
            d = dims.get(key, {})
            s = d.get("score", 0) if isinstance(d, dict) else (d or 0)
            if s < 100:
                _gap_items.append((label, s, 100 - s))
        _gap_items.sort(key=lambda x: x[2], reverse=True)

        _gap_rows = ""
        for label, score, gap in _gap_items[:3]:
            _gap_rows += f"""
            <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                <td style="padding:8pt 12pt 8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};
                    font-weight:600;">{escape(label)}</td>
                <td style="padding:8pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.ACCENT};
                    font-feature-settings:{dt.TABULAR_FIGURES};text-align:right;">{score:.0f}/100</td>
                <td style="padding:8pt 0 8pt 12pt;font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_500};
                    font-feature-settings:{dt.TABULAR_FIGURES};text-align:right;">+{gap:.0f} possible</td>
            </tr>"""

        priority_html = f"""
        <div style="page-break-before:always;">
            <h1>Maintaining Your Advantage</h1>
            <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

            <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
                margin-bottom:{dt.SPACE_MD};">
                Your score of {composite:.0f}/100 puts you in the <strong>{band}</strong> tier. You have no
                critical gaps. The optimizations below are about extending your lead as the AI agent
                ecosystem matures.</div>

            <div style="margin-bottom:{dt.SPACE_LG};">
                {_eyebrow("Remaining Score Gaps")}
                <table style="width:100%;border-collapse:collapse;margin-top:{dt.SPACE_SM};">
                    <thead><tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                        <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                            text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Dimension</th>
                        <th style="padding:6pt 0;text-align:right;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                            text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Score</th>
                        <th style="padding:6pt 0 6pt 12pt;text-align:right;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                            text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Headroom</th>
                    </tr></thead>
                    <tbody>{_gap_rows}</tbody>
                </table>
            </div>

            <div style="margin-bottom:{dt.SPACE_LG};">
                {_eyebrow("Advanced Optimizations")}
                <div style="margin-top:{dt.SPACE_SM};">
                    <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                        margin-bottom:10pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                        <strong>1. Adopt agent discovery protocols.</strong> Add an agent.json file at
                        /.well-known/agent.json and an llms.txt at your site root. These tell AI agents
                        exactly what your business does and how to interact with it programmatically.
                        Most competitors have not adopted these yet.
                        <span style="color:{dt.SEMANTIC_GREEN};font-weight:600;"> [Easy | 25 min]</span></div>
                    <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                        margin-bottom:10pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                        <strong>2. Monitor competitive position monthly.</strong> Your {percentile:.0f}th percentile
                        ranking can shift as competitors improve. Schedule a monthly rescan to track movement
                        and respond to competitive changes before they affect your AI visibility.
                        <span style="color:{dt.SEMANTIC_GREEN};font-weight:600;"> [Easy | Ongoing]</span></div>
                    <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                        margin-bottom:10pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                        <strong>3. Explore emerging commerce protocols.</strong> UCP (Universal Commerce Protocol)
                        and ACP (Agentic Commerce Protocol) are emerging standards for direct agent-to-business
                        transactions. Early adoption positions you for the next wave of AI agent capabilities.
                        <span style="color:{dt.SEMANTIC_AMBER};font-weight:600;"> [Medium | 2-4 hours]</span></div>
                </div>
            </div>

            {_callout_box(f"<strong>Your competitive advantage is real but perishable.</strong> You are currently ahead of {percentile:.0f}% of businesses in your market. As AI agent optimization becomes mainstream, the bar will rise. The optimizations above help you stay ahead of that curve.")}

            {_source_attr(db_count)}
        </div>"""
    else:
        priority_divider = _section_divider(_pap_section_num, "Priority Action Plan",
            "The highest-impact fixes, ranked by potential score improvement.")

        priority_rows = ""
        for i, act in enumerate(priority_actions, 1):
            diff_color = {"Easy": dt.SEMANTIC_GREEN, "Medium": dt.SEMANTIC_AMBER, "Hard": dt.SEMANTIC_RED}.get(act["difficulty"], dt.INK)
            priority_rows += f"""
            <tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};page-break-inside:avoid;">
                <td style="padding:10pt 12pt 10pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_400};
                    font-feature-settings:{dt.TABULAR_FIGURES};font-weight:600;vertical-align:top;">{i:02d}</td>
                <td style="padding:10pt 12pt 10pt 0;font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};
                    line-height:{dt.LEADING_BODY};overflow-wrap:break-word;vertical-align:top;">{escape(act['action'])}</td>
                <td style="padding:10pt 12pt 10pt 0;font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};vertical-align:top;">
                    {act['dimension']}<br><span style="font-feature-settings:{dt.TABULAR_FIGURES};">{act['dim_score']:.0f}/100</span></td>
                <td style="padding:10pt 0;font-size:{dt.TYPE_CAPTION};vertical-align:top;">
                    <span style="color:{diff_color};font-weight:600;">{act['difficulty']}</span><br>
                    <span style="color:{dt.GRAY_500};">{act['time']}</span></td>
            </tr>"""

        priority_html = f"""
        <div style="page-break-before:always;">
            <h1>Priority Action Plan</h1>
            <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

            <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
                margin-bottom:{dt.SPACE_MD};">
                The {len(priority_actions)} highest-impact fixes for your business, ranked by
                potential score improvement.
            </div>

            <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                <colgroup>
                    <col style="width:28pt;">
                    <col style="width:auto;">
                    <col style="width:100pt;">
                    <col style="width:74pt;">
                </colgroup>
                <thead><tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">#</th>
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Action</th>
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Dimension</th>
                    <th style="padding:6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Effort</th>
                </tr></thead>
                <tbody>{priority_rows}</tbody>
            </table>

            {_source_attr(db_count)}
        </div>""" if priority_actions else ""

    # ---- DETAILED FINDINGS ----
    findings_divider = _section_divider(6 if not has_competitive else 7, "Detailed Findings",
        "What AI agents found on your website, and exactly what to fix.")

    dim_details = ""
    for idx, (key, label, description) in enumerate(all_dimensions):
        if key == "competitive_position":
            continue
        d = dims.get(key, {})
        if isinstance(d, dict):
            s = d.get("score", 0)
            findings = d.get("findings", [])
            recs = d.get("recommendations", [])
        else:
            s = d or 0
            findings = []
            recs = []

        findings_html = ""
        if findings:
            items = "".join(_render_finding(f) for f in findings)
            findings_html = f"""
            <div style="margin-bottom:{dt.SPACE_MD};">
                {_eyebrow("What AI Agents Found")}
                <ul style="margin:{dt.SPACE_SM} 0 0 0;padding-left:16pt;">{items}</ul>
            </div>"""

        recs_html = ""
        if recs:
            rec_items = ""
            snippet_shown = False
            for r in recs:
                plain, diff, time_est, impact, snippet_key = _rewrite_rec(r)
                diff_color = {"Easy": dt.SEMANTIC_GREEN, "Medium": dt.SEMANTIC_AMBER, "Hard": dt.SEMANTIC_RED}.get(diff, dt.INK)
                rec_items += (
                    f'<li style="margin-bottom:10pt;font-size:{dt.TYPE_BODY_SMALL};'
                    f'line-height:{dt.LEADING_BODY};color:{dt.INK};">'
                    f'{escape(plain)} '
                    f'<span style="font-size:{dt.TYPE_SOURCE};color:{diff_color};font-weight:600;">'
                    f'[{diff} | {time_est}]</span></li>'
                )
                if snippet_key and not snippet_shown and snippet_key in _CODE_SNIPPETS:
                    snippet_shown = True
                    snippet_code = _CODE_SNIPPETS[snippet_key].format(
                        business_name=business_name, url=url
                    )
                    filename = {"llms.txt": "/llms.txt", "schema.org": "homepage <head>",
                                "agent.json": "/.well-known/agent.json"}.get(snippet_key, snippet_key)
                    rec_items += f'<li style="list-style:none;margin-left:-16pt;">{_code_block(filename, snippet_code)}</li>'

            recs_html = f"""
            <div style="margin-bottom:{dt.SPACE_MD};">
                {_eyebrow("What to Fix")}
                <ul style="margin:{dt.SPACE_SM} 0 0 0;padding-left:16pt;">{rec_items}</ul>
            </div>"""

        page_break = "page-break-before:always;" if idx == 0 else f"margin-top:{dt.SPACE_XL};border-top:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};padding-top:{dt.SPACE_LG};"

        dim_details += f"""
        <div style="{page_break}">
            <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_SM};">
                <tr>
                    <td><h2 style="margin:0;">{label}</h2></td>
                    <td style="text-align:right;font-family:'{dt.FONT_DISPLAY}',Georgia,serif;
                        font-size:{dt.TYPE_H1};font-weight:700;color:{dt.INK};
                        font-feature-settings:{dt.TABULAR_FIGURES};">{s:.0f}</td>
                </tr>
            </table>
            <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};
                line-height:{dt.LEADING_BODY};">{description}</div>
            <div style="position:relative;height:{dt.BAR_HEIGHT};background:{dt.GRAY_300};margin-bottom:{dt.SPACE_MD};">
                <div style="position:absolute;top:0;left:0;height:{dt.BAR_HEIGHT};width:{max(1,s)}%;background:{dt.ACCENT};"></div>
            </div>
            {findings_html}
            {recs_html}
        </div>"""

    # ---- TECH STACK ----
    tech_html = ""
    tech_rows_data = []
    if cms_detected:
        tech_rows_data.append(("CMS / Website Platform", cms_detected))
    if payment_platforms:
        tech_rows_data.append(("Payment Platforms", ", ".join(payment_platforms)))
    if chat_platforms:
        tech_rows_data.append(("Chat / Messaging", ", ".join(chat_platforms)))
    if review_platforms:
        tech_rows_data.append(("Review Platforms", ", ".join(review_platforms)))
    if analytics_platforms:
        tech_rows_data.append(("Analytics", ", ".join(analytics_platforms)))
    if form_platforms:
        tech_rows_data.append(("Form / Scheduling", ", ".join(form_platforms)))

    if tech_rows_data:
        tr_html = ""
        for cat, val in tech_rows_data:
            tr_html += f'<tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};"><td style="padding:8pt 12pt 8pt 0;font-weight:600;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};">{cat}</td><td style="padding:8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};">{escape(val)}</td></tr>'

        tech_html = f"""
        <div style="margin-top:{dt.SPACE_XL};border-top:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};padding-top:{dt.SPACE_LG};">
            <h2>What We Detected</h2>
            <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};
                line-height:{dt.LEADING_BODY};">Technology platforms identified during our scan.</div>
            <table style="width:100%;border-collapse:collapse;">
                <thead><tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                    <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Category</th>
                    <th style="padding:6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;
                        text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Detected</th>
                </tr></thead>
                <tbody>{tr_html}</tbody>
            </table>
            <div style="font-size:{dt.TYPE_SOURCE};color:{dt.GRAY_400};margin-top:{dt.SPACE_SM};">
                Detected from HTML, scripts, and metadata. Actual stack may include additional tools not visible externally.</div>
        </div>"""

    # ---- COMPETITOR COMPARISON ----
    comp_html = ""
    if competitors:
        # Filter out competitors with zero scores
        # Deduplicate by domain, keeping first occurrence (highest composite)
        seen_domains = set()
        deduped = []
        for c in competitors:
            cd = (c.get("domain") or "").lower().strip()
            if cd and cd not in seen_domains:
                seen_domains.add(cd)
                deduped.append(c)
        # Filter out zero-composite and competitors whose dimension scores are all zero
        real_comps = []
        for c in deduped[:8]:
            if c.get("composite_score", 0) <= 0:
                continue
            dim_cols = ["agent_compatibility_score", "transaction_readiness_score", "operational_data_structure_score"]
            dim_sum = sum(c.get(col, 0) or 0 for col in dim_cols)
            if dim_sum == 0:
                continue  # skip competitors with 0/0/0 dimension breakdown
            real_comps.append(c)
            if len(real_comps) >= 5:
                break
        if len(real_comps) >= 3:
            comp_header = f'<th style="padding:6pt 4pt;text-align:right;font-size:7pt;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:{dt.ACCENT};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:0;">{escape(domain.upper())}</th>'
            for c in real_comps[:3]:
                cname = _normalize_business_name(c.get("business_name", ""), c.get("domain", ""))
                comp_header += f'<th style="padding:6pt 4pt;text-align:right;font-size:7pt;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;color:{dt.GRAY_400};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:0;">{escape(cname)}</th>'

            comp_body = f'<tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};font-weight:700;"><td style="padding:8pt 12pt 8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};">Overall</td><td style="padding:8pt 0;text-align:right;color:{dt.ACCENT};font-size:{dt.TYPE_BODY_SMALL};font-feature-settings:{dt.TABULAR_FIGURES};">{composite:.0f}</td>'
            for c in real_comps[:3]:
                cs = c.get("composite_score", 0)
                dc = dt.SEMANTIC_GREEN if composite >= cs else dt.SEMANTIC_RED
                comp_body += f'<td style="padding:8pt 0;text-align:right;color:{dc};font-size:{dt.TYPE_BODY_SMALL};font-feature-settings:{dt.TABULAR_FIGURES};">{cs:.0f}</td>'
            comp_body += "</tr>"

            dim_col_map = {"agent_accessibility": "agent_compatibility_score", "transaction_completeness": "transaction_readiness_score", "data_reliability": "operational_data_structure_score"}
            for key, label, _ in DIMENSIONS:
                d_val = dims.get(key, {})
                s_val = d_val.get("score", 0) if isinstance(d_val, dict) else (d_val or 0)
                col = dim_col_map.get(key, "")
                comp_body += f'<tr style="border-bottom:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};"><td style="padding:8pt 12pt 8pt 0;color:{dt.INK};font-size:{dt.TYPE_BODY_SMALL};">{label}</td><td style="padding:8pt 0;text-align:right;color:{dt.ACCENT};font-size:{dt.TYPE_BODY_SMALL};font-feature-settings:{dt.TABULAR_FIGURES};">{s_val:.0f}</td>'
                for c in real_comps[:3]:
                    cv = c.get(col, 0) or 0
                    dc = dt.SEMANTIC_GREEN if s_val >= cv else dt.SEMANTIC_RED
                    comp_body += f'<td style="padding:8pt 0;text-align:right;color:{dc};font-size:{dt.TYPE_BODY_SMALL};font-feature-settings:{dt.TABULAR_FIGURES};">{cv:.0f}</td>'
                comp_body += "</tr>"

            comp_html = f"""
            <div style="page-break-before:always;">
                <h1>Local Competitor Comparison</h1>
                <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">
                <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
                    How you compare against the top-scoring {escape(vertical)} businesses in your area.</div>
                <table style="width:100%;border-collapse:collapse;table-layout:fixed;">
                    <colgroup>
                        <col style="width:35%;">
                        <col style="width:{65 // (len(real_comps[:3]) + 1)}%;">
                        {''.join(f'<col style="width:{65 // (len(real_comps[:3]) + 1)}%;">' for _ in real_comps[:3])}
                    </colgroup>
                    <thead><tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                        <th style="padding:6pt 12pt 6pt 0;text-align:left;font-size:{dt.TYPE_EYEBROW};font-weight:600;text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">Dimension</th>
                        {comp_header}
                    </tr></thead>
                    <tbody>{comp_body}</tbody>
                </table>
                <div style="font-size:{dt.TYPE_SOURCE};color:{dt.GRAY_400};margin-top:{dt.SPACE_SM};line-height:{dt.LEADING_BODY};">
                    Green indicates you match or exceed the competitor. Red means they are better positioned for AI agents in that area.</div>
                {_source_attr(db_count)}
            </div>"""
        elif len(real_comps) >= 1:
            c = real_comps[0]
            cname = c.get("business_name") or c.get("domain", "")
            cs = c.get("composite_score", 0)
            comp_html = f"""
            <div style="page-break-before:always;">
                <h1>Local Competitor Comparison</h1>
                <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">
                <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
                    One comparable business found: <strong>{escape(cname)}</strong> (score: {cs:.0f}/100, vs your {composite:.0f}/100).
                </div>
                <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};
                    padding-left:{dt.SPACE_SM};border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Competitive density insufficient for full peer cohort. Additional competitors will be
                    added as the GradeForAI dataset expands in your market.</div>
            </div>"""

    # ---- ROADMAP ----
    if is_high_scorer:
        roadmap_divider = _section_divider(9, "Optimization Roadmap",
            "A quarterly cadence to maintain and extend your advantage.")

        roadmap_html = f"""
        <div style="page-break-before:always;">
            <h1>Quarterly Optimization Roadmap</h1>
            <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

            <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};
                margin-bottom:{dt.SPACE_MD};">
                With a score of {composite:.0f}/100, your priority shifts from fixing gaps to maintaining
                your position and adopting emerging standards before competitors.</div>

            <div style="margin-bottom:{dt.SPACE_LG};">
                {_eyebrow("This Month -- Protocol Adoption")}
                <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">
                    Quick wins that signal advanced AI readiness.</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                    Add llms.txt to your site root describing your business for AI language models</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                    Create /.well-known/agent.json with your capabilities and transaction endpoints</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.ACCENT};">
                    Review and expand schema.org markup for any missing operational fields</div>
            </div>

            <div style="margin-bottom:{dt.SPACE_LG};">
                {_eyebrow("Next Quarter -- Competitive Monitoring")}
                <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">
                    Track your position and respond to market shifts.</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Schedule monthly rescans to track score changes and competitor movement</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Monitor for new AI agent protocols and standards as they emerge</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Test your transaction flow from an AI agent perspective quarterly</div>
            </div>

            <div style="margin-bottom:{dt.SPACE_LG};">
                {_eyebrow("Ongoing -- Emerging Standards")}
                <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">
                    Longer-term investments in the agentic commerce ecosystem.</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Evaluate UCP/ACP protocol integration for direct agent-to-business transactions</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Consider MCP (Model Context Protocol) server for programmatic business interactions</div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    Build internal AI agent testing into your QA process for website changes</div>
            </div>
        </div>"""
    else:
        roadmap_divider = _section_divider(9, "Implementation Roadmap",
            "A phased approach to improving your AI agent readiness.")

        roadmap_html = ""
        if priority_actions:
            easy = [a for a in priority_actions if a["difficulty"] == "Easy"]
            medium = [a for a in priority_actions if a["difficulty"] == "Medium"]
            hard = [a for a in priority_actions if a["difficulty"] == "Hard"]

            def _phase_list(items, limit=3):
                if not items:
                    return f'<div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};">No items in this phase.</div>'
                out = ""
                for a in items[:limit]:
                    out += f'<div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:6pt;padding-left:12pt;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">{escape(a["action"])}</div>'
                return out

            roadmap_html = f"""
            <div style="page-break-before:always;">
                <h1>30-Day Implementation Roadmap</h1>
                <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

                <div style="margin-bottom:{dt.SPACE_LG};">
                    {_eyebrow("Week 1 -- Quick Wins")}
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">Easy fixes, under an hour each.</div>
                    {_phase_list(easy)}
                </div>

                <div style="margin-bottom:{dt.SPACE_LG};">
                    {_eyebrow("Week 2 -- Core Infrastructure")}
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">Medium-effort structural improvements.</div>
                    {_phase_list(medium)}
                </div>

                <div style="margin-bottom:{dt.SPACE_LG};">
                    {_eyebrow("Weeks 3-4 -- Advanced")}
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-bottom:{dt.SPACE_SM};">Harder changes requiring development time.</div>
                    {_phase_list(hard + medium[3:] + easy[3:])}
                </div>
            </div>"""

    # ---- TWO PATHS FORWARD ----
    paths_divider = _section_divider(10, "Two Paths Forward",
        "Choose DIY implementation or let us handle it.")

    if is_high_scorer:
        _path1_title = "Path 1 -- Self-Managed"
        _path1_body = f"""Use the optimization roadmap in this report to maintain your advantage.
                    The protocol adoption steps (llms.txt, agent.json) take under 30 minutes and
                    keep you ahead of competitors."""
        _path1_items = """-- Optimization roadmap with timelines<br>
                    -- Ready-to-paste protocol files<br>
                    -- Competitive monitoring guidance<br>
                    -- Emerging standards briefing"""
        _path1_cost = "Cost: Your time (minimal)"
        _path2_title = "Path 2 -- Managed Optimization"
        _path2_body = f"""We implement the advanced optimizations, set up competitive monitoring,
                    and keep your AI agent readiness at the leading edge. Ideal if you want
                    to stay ahead without tracking protocol changes yourself."""
        _path2_items = """-- All protocol files configured<br>
                    -- Schema.org optimization audit<br>
                    -- Monthly competitive position monitoring<br>
                    -- Quarterly rescan and adjustment<br>
                    -- Priority support for AI agent issues"""
        _path2_cost = "Starting at $500/quarter"
    else:
        _path1_title = "Path 1 -- DIY Implementation"
        _path1_body = """Use the roadmaps and code templates in this report to implement the fixes yourself
                    or hand them to your web developer. Everything you need is in these pages."""
        _path1_items = """-- All recommendations in plain English<br>
                    -- Ready-to-paste code templates<br>
                    -- Difficulty and time estimates<br>
                    -- Two roadmaps to guide order of operations"""
        _path1_cost = "Cost: Your time (or your developer's)"
        _path2_title = "Path 2 -- Managed Implementation"
        _path2_body = """We implement every recommendation in this report for you. Structured data,
                    agent compatibility fixes, transaction platform integrations, and everything
                    AI agents need to operate on your site."""
        _path2_items = """-- All fixes in this report implemented<br>
                    -- Schema.org markup configured<br>
                    -- Agent compatibility and accessibility fixes<br>
                    -- Post-implementation rescan to verify<br>
                    -- 30-day support window"""
        _path2_cost = "Starting at $1,500 -- scoped to your specific findings"

    cta_html = f"""
    <div style="page-break-before:always;">
        <h1>Two Paths Forward</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <table style="width:100%;border-collapse:collapse;">
            <tr>
            <td style="width:48%;vertical-align:top;padding-right:{dt.GUTTER};">
                <h2 style="font-size:{dt.TYPE_BODY};font-weight:700;">{_path1_title}</h2>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:{dt.SPACE_SM};">
                    {_path1_body}
                </div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:2;">
                    {_path1_items}
                </div>
                <div style="margin-top:{dt.SPACE_SM};font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};">
                    {_path1_cost}
                </div>
            </td>
            <td style="width:4%;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};"></td>
            <td style="width:48%;vertical-align:top;padding-left:{dt.GUTTER};">
                <h2 style="font-size:{dt.TYPE_BODY};font-weight:700;">{_path2_title}</h2>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:{dt.LEADING_BODY};
                    margin-bottom:{dt.SPACE_SM};">
                    {_path2_body}
                </div>
                <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};line-height:2;">
                    {_path2_items}
                </div>
                <div style="margin-top:{dt.SPACE_SM};font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};">
                    {_path2_cost}
                </div>
            </td>
            </tr>
        </table>

        <div style="margin-top:{dt.SPACE_XL};">
            <div style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_BODY};
                color:{dt.ACCENT};font-weight:600;">{CONTACT_EMAIL}</div>
            <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_500};margin-top:{dt.SPACE_XS};">
                Or reply directly to the email that delivered this report.</div>
        </div>
    </div>"""

    # ---- ABOUT GRADEFORAI ----
    about_html = f"""
    <div style="page-break-before:always;">
        <h1>About GradeForAI</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
            GradeForAI operates the largest AI Agent Preference scoring database in the world.
            We have scored over {db_count} businesses across {verticals_label} verticals and
            {cities_label} cities, measuring how ready each business is for the AI agent economy.
        </div>

        <table style="width:100%;border-collapse:collapse;margin-bottom:{dt.SPACE_LG};">
            <tr style="border-bottom:{dt.RULE_STANDARD} solid {dt.GRAY_300};border-top:{dt.RULE_STANDARD} solid {dt.GRAY_300};">
                <td style="padding:16pt 24pt 16pt 0;text-align:center;">
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};font-feature-settings:{dt.TABULAR_FIGURES};">{db_count}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_400};margin-top:4pt;">Businesses Scored</div>
                </td>
                <td style="padding:16pt 24pt;text-align:center;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};font-feature-settings:{dt.TABULAR_FIGURES};">{num_dimensions}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_400};margin-top:4pt;">Scoring Dimensions</div>
                </td>
                <td style="padding:16pt 0 16pt 24pt;text-align:center;border-left:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};">
                    <div style="font-family:'{dt.FONT_DISPLAY}',Georgia,serif;font-size:{dt.TYPE_H2};
                        color:{dt.INK};font-feature-settings:{dt.TABULAR_FIGURES};">{cities_label}</div>
                    <div style="font-size:{dt.TYPE_CAPTION};color:{dt.GRAY_400};margin-top:4pt;">Cities Covered</div>
                </td>
            </tr>
        </table>

        <div style="font-size:{dt.TYPE_BODY};color:{dt.INK};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
            AI Agent Preference is a category we created because existing frameworks (SEO, AEO)
            do not address whether AI agents can physically use a website -- navigate it, extract
            data, and complete transactions. As AI agents become the primary interface between
            consumers and businesses, agent readiness determines which businesses get customers.
        </div>

        <div style="border-top:{dt.RULE_HAIRLINE} solid {dt.GRAY_300};padding-top:{dt.SPACE_SM};">
            <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.INK};">
                Questions about this report? Email <strong style="color:{dt.ACCENT};">{CONTACT_EMAIL}</strong>
                or visit <strong>gradeforai.com</strong>.</div>
        </div>
    </div>"""

    # ---- DISCLAIMER ----
    disclaimer_html = f"""
    <div style="page-break-before:always;">
        <h1>Disclaimer</h1>
        <hr class="rule-hairline" style="margin-bottom:{dt.SPACE_MD};">

        <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
            This report represents a point-in-time assessment based on publicly available information
            and automated analysis. Scores may change as your website evolves, as AI agent technology
            advances, and as our methodology improves. This report does not constitute legal, financial,
            or technical advice. Consult qualified professionals as appropriate.</div>
        <div style="font-size:{dt.TYPE_BODY_SMALL};color:{dt.GRAY_500};line-height:{dt.LEADING_BODY};margin-bottom:{dt.SPACE_MD};">
            This report is confidential and prepared exclusively for <strong style="color:{dt.INK};">{escape(business_name)}</strong>.
            Redistribution or publication without written consent from GradeForAI is prohibited.</div>
        <div style="font-size:{dt.TYPE_SOURCE};color:{dt.GRAY_400};">
            &copy; {now.year} Layered Media LLC. All rights reserved. GradeForAI&trade; and AI Agent Preference&trade; are property of Layered Media LLC.</div>
    </div>"""

    # ==================================================================
    # ASSEMBLE FULL HTML
    # ==================================================================
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{dt.font_face_css()}
{dt.page_css()}
{dt.base_css()}
</style>
</head>
<body>

<!-- Running header/footer elements -->
<div class="page-header-left"></div>
<div class="page-header-right" style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_EYEBROW};
    text-transform:uppercase;letter-spacing:{dt.SMALL_CAPS_TRACKING};color:{dt.GRAY_400};">
    {escape(domain).upper()}</div>
<div class="page-footer-left" style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_SOURCE};
    color:{dt.GRAY_400};">GradeForAI &middot; AI Agent Preference Report</div>
<div class="page-footer-right" style="font-family:'{dt.FONT_BODY}',sans-serif;font-size:{dt.TYPE_SOURCE};
    color:{dt.GRAY_400};font-feature-settings:{dt.TABULAR_FIGURES};"></div>

{cover_html}
{toc_html}
{exec_divider}
{exec_html}
{aao_divider}
{aao_html}
{meth_divider}
{methodology_html}
{glance_divider}
{glance_html}
{competitive_html}
{priority_divider}
{priority_html}
{findings_divider}
{dim_details}
{tech_html}
{comp_html}
{roadmap_divider}
{roadmap_html}
{paths_divider}
{cta_html}
{about_html}
{disclaimer_html}

</body>
</html>"""

    # ---- Generate PDF ----
    os.makedirs(REPORTS_DIR, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    clean_domain = domain.replace("https://", "").replace("http://", "").replace("/", "_").strip("_")
    pdf_path = os.path.join(REPORTS_DIR, f"{clean_domain}-{date_str}.pdf")
    html_path = os.path.join(REPORTS_DIR, f"{clean_domain}-{date_str}.html")

    with open(html_path, "w") as f:
        f.write(html)

    from weasyprint import HTML
    HTML(string=html, base_url=os.path.dirname(LOGO_PATH)).write_pdf(pdf_path)

    return pdf_path


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    if len(sys.argv) > 1:
        domain_arg = sys.argv[1]
    else:
        domain_arg = None

    from storage import _get_conn, get_vertical_benchmarks, get_local_competitors

    conn = _get_conn()
    if domain_arg:
        row = conn.execute(
            "SELECT b.domain, b.vertical, b.city, s.raw_json FROM scores s "
            "JOIN businesses b ON s.business_id = b.id WHERE b.domain = ? "
            "ORDER BY s.timestamp DESC LIMIT 1", (domain_arg,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT b.domain, b.vertical, b.city, s.raw_json FROM scores s "
            "JOIN businesses b ON s.business_id = b.id "
            "WHERE s.methodology_version >= 5.4 AND s.composite_score > 40 "
            "ORDER BY RANDOM() LIMIT 1"
        ).fetchone()
    conn.close()

    score_result = json.loads(row["raw_json"])
    benchmarks = get_vertical_benchmarks(row["vertical"], row["city"])
    competitors = get_local_competitors(row["vertical"], row["city"], exclude_domain=row["domain"])

    print(f"Domain: {row['domain']} | Vertical: {row['vertical']} | City: {row['city']}")
    pdf = generate_pdf_report(score_result, benchmarks=benchmarks, competitors=competitors)
    print(f"Generated: {pdf}")
