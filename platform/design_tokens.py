"""
Design tokens for GradeForAI PDF report system.

Every color, type size, rule weight, spacing value, and margin lives here.
No hex values, font sizes, or pixel values may appear in pdf_report.py or
any other report-rendering code. Import from this module exclusively.

Visual register: GradeForAI brand identity + consulting report lineage.
Rendering engine: WeasyPrint (CSS Paged Media).
Page format: US Letter (8.5 x 11 in / 216 x 279 mm).
"""

import os

# ---------------------------------------------------------------------------
# FONT PATHS
# ---------------------------------------------------------------------------

_opt_fonts = "/opt/agent-readiness/website/assets/fonts"
_local_fonts = os.path.expanduser("~/agent-readiness/website/assets/fonts")
FONTS_DIR = _opt_fonts if os.path.isdir(_opt_fonts) else _local_fonts

# Display serif: Fraunces (Google Fonts, OFL license)
# Soft serif with optical size axis. Cover numerals, domain, pull quotes.
FONT_DISPLAY = "Fraunces"
FONT_DISPLAY_FILES = {
    "regular": "Fraunces-Regular.ttf",
    "medium": "Fraunces-Medium.ttf",
    "semibold": "Fraunces-SemiBold.ttf",
    "bold": "Fraunces-Bold.ttf",
    "italic": "Fraunces-Italic.ttf",
}

# Body sans: Inter (already available in project)
FONT_BODY = "Inter"
FONT_BODY_FILES = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
}

# Monospace: JetBrains Mono (OFL license)
FONT_MONO = "JetBrains Mono"
FONT_MONO_FILES = {
    "regular": "JetBrainsMono-Regular.ttf",
}

# Font feature settings for numeric contexts
TABULAR_FIGURES = '"tnum"'
SMALL_CAPS_TRACKING = "0.08em"

# ---------------------------------------------------------------------------
# COLOR PALETTE (from gradeforai.com brand)
# ---------------------------------------------------------------------------

# Brand palette
BRAND_BLUE = "#4353FE"       # Primary brand blue
BRAND_BLUE_TINT = "#6B78FE"  # Lighter tint

# Ink / text
INK = "#0E1629"              # Primary ink (near-black navy)
INK_SOFT = "#222222"         # Slightly lighter ink

# Paper / background
PAPER = "#F9F9FB"            # Light page background tint

# Rules / borders
RULE_COLOR = "#D8D9E3"       # Default rule/border color

# Muted text
MUTED = "#6B6E7A"            # Secondary text
MUTED_SOFT = "#A3A6B0"       # Tertiary text, labels

# Semantic colors (used sparingly, for difficulty labels only)
SEMANTIC_RED = "#9B1C1C"
SEMANTIC_AMBER = "#92400E"
SEMANTIC_GREEN = "#166534"

# --- Legacy aliases (map old names to new palette) ---
ACCENT = BRAND_BLUE
GRAY_300 = RULE_COLOR
GRAY_400 = MUTED_SOFT
GRAY_500 = MUTED
GRAY_600 = INK_SOFT
WARM = "#F5F1EA"
WARM_DARK = "#EDE8DF"
PAGE_BG = "#FFFFFF"

# ---------------------------------------------------------------------------
# SEVERITY BAND COLORS (brand-native, blue-to-red)
# ---------------------------------------------------------------------------

BAND_COLORS = {
    "Agent Preferred":    "#4353FE",  # 90-100 brand blue
    "Agent Optimized":    "#6B78FE",  # 70-89  tint
    "Agent Ready":        "#E59F26",  # 50-69  amber
    "Agent Functional":   "#D17A2E",  # 30-49  orange
    "Agent Detected":     "#DB4850",  # 10-29  red
    "Agent Incompatible": "#A8323A",  # 0-9    dark red
}

BAND_THRESHOLDS = [
    (90, "Agent Preferred"),
    (70, "Agent Optimized"),
    (50, "Agent Ready"),
    (30, "Agent Functional"),
    (10, "Agent Detected"),
    (0, "Agent Incompatible"),
]

# Ordered list for rendering severity strips
BAND_ORDER = [
    "Agent Incompatible", "Agent Detected", "Agent Functional",
    "Agent Ready", "Agent Optimized", "Agent Preferred",
]

# Tick positions on the severity scale (score boundaries)
BAND_TICK_POSITIONS = [0, 10, 30, 50, 70, 90]

# ---------------------------------------------------------------------------
# TYPE SCALE
# ---------------------------------------------------------------------------

TYPE_COVER_DOMAIN = "56pt"   # Cover page domain name (Fraunces)
TYPE_COVER_SCORE = "160pt"   # Cover page score numeral
TYPE_COVER_DENOM = "42pt"    # /100 denominator
TYPE_COVER_VERDICT = "23pt"  # Band verdict line
TYPE_COVER_PILL = "11pt"     # Band pill label
TYPE_SECTION_NUM = "120pt"   # Section divider page number
TYPE_H1 = "28pt"             # Page titles
TYPE_H2 = "20pt"             # Section subtitles
TYPE_BODY = "14pt"           # Body text
TYPE_BODY_SMALL = "11pt"     # Body text in dense contexts
TYPE_CAPTION = "11pt"        # Captions, sidebar text
TYPE_SOURCE = "9pt"          # Source lines, footnotes, page numbers
TYPE_EYEBROW = "9pt"         # Tracked-out small-caps labels
TYPE_CODE = "9pt"            # Code blocks
TYPE_CODE_LINENUM = "7pt"    # Line numbers in code blocks
TYPE_SIGNAL_LABEL = "8pt"    # OPERATIONAL / INFORMATIONAL pills
TYPE_COLOPHON = "9pt"        # Cover colophon
TYPE_SECTION_THESIS = "18pt" # Section divider thesis statement
TYPE_MASTHEAD_WORDMARK = "18pt"  # Cover masthead wordmark
TYPE_MASTHEAD_LABEL = "10pt"     # Cover masthead right label
TYPE_META_LABEL = "9pt"      # Cover metadata labels
TYPE_META_VALUE = "12pt"     # Cover metadata values
TYPE_STRIP_TICK = "9pt"      # Severity strip tick labels

# Line heights
LEADING_DISPLAY = "1.1"
LEADING_BODY = "1.6"
LEADING_CODE = "1.3"
LEADING_TIGHT = "1.2"

# ---------------------------------------------------------------------------
# RULE WEIGHTS
# ---------------------------------------------------------------------------

RULE_HAIRLINE = "0.5pt"
RULE_STANDARD = "1pt"
RULE_EMPHASIS = "2pt"

# ---------------------------------------------------------------------------
# SPACING
# ---------------------------------------------------------------------------

BASELINE = "12pt"
GUTTER = "24pt"
SPACE_XS = "6pt"
SPACE_SM = "12pt"
SPACE_MD = "24pt"
SPACE_LG = "36pt"
SPACE_XL = "48pt"
SPACE_XXL = "72pt"

# ---------------------------------------------------------------------------
# PAGE LAYOUT (US Letter)
# ---------------------------------------------------------------------------

PAGE_SIZE = "letter"
PAGE_WIDTH_PT = 612
PAGE_HEIGHT_PT = 792

MARGIN_TOP = "54pt"
MARGIN_BOTTOM = "54pt"
MARGIN_INNER = "72pt"
MARGIN_OUTER = "54pt"

CONTENT_WIDTH_PT = 612 - 72 - 54  # 486pt
CONTENT_WIDTH = "486pt"

SIDENOTE_WIDTH = "54pt"
SIDENOTE_GUTTER = "12pt"
BODY_COLUMN_WIDTH = "408pt"

HEADER_HEIGHT = "36pt"
FOOTER_HEIGHT = "36pt"

BAR_HEIGHT = "4pt"
BAR_TICK_HEIGHT = "12pt"
BAND_STRIP_HEIGHT = "16pt"

# ---------------------------------------------------------------------------
# COMPONENT TOKENS
# ---------------------------------------------------------------------------

TABLE_HEADER_BG = "transparent"
TABLE_ROW_HEIGHT = "14pt"
TABLE_RULE_COLOR = RULE_COLOR

CODE_BG = WARM
CODE_BORDER = RULE_COLOR
CODE_HEADER_BG = WARM_DARK

CALLOUT_RULE_COLOR = BRAND_BLUE
CALLOUT_FILL = WARM
CALLOUT_BORDER = RULE_COLOR

SIGNAL_OPERATIONAL_GLYPH = "\u25AA"
SIGNAL_INFORMATIONAL_GLYPH = "\u25AB"
SIGNAL_BORDER = BRAND_BLUE
SIGNAL_PADDING_V = "2pt"
SIGNAL_PADDING_H = "6pt"

DIVIDER_THESIS_MEASURE = "300pt"

# Cover-specific tokens
COVER_STRIPE_WIDTH = "6px"       # Left-edge band stripe
COVER_PILL_PADDING = "7px 14px"  # Band pill padding
COVER_PILL_RADIUS = "3px"        # Band pill border-radius
COVER_PILL_DOT_SIZE = "6px"      # White dot before pill text
COVER_SCORE_RULE_PADDING = "24px"  # Padding inside score bordered block

# Severity strip tokens
STRIP_SEGMENT_HEIGHT_ACTIVE = "10px"
STRIP_SEGMENT_HEIGHT_INACTIVE = "7px"
STRIP_INACTIVE_OPACITY = "0.35"


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def band_color(score):
    """Return the band color for a given score."""
    for threshold, name in BAND_THRESHOLDS:
        if score >= threshold:
            return BAND_COLORS[name]
    return BAND_COLORS["Agent Incompatible"]


def band_name(score):
    """Return capability band name for a given score."""
    for threshold, name in BAND_THRESHOLDS:
        if score >= threshold:
            return name
    return "Agent Incompatible"


def ordinal(n):
    """Return ordinal suffix for an integer: 1st, 2nd, 3rd, 4th, etc."""
    n = int(n)
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def font_path(filename):
    """Return full path to a font file."""
    return os.path.join(FONTS_DIR, filename)


# ---------------------------------------------------------------------------
# SOURCE ATTRIBUTION
# ---------------------------------------------------------------------------

def source_line(n_businesses="470,000+", methodology="v6.2"):
    return (
        f"Source: GradeForAI Benchmark Database, "
        f"n={n_businesses} businesses scored. "
        f"Methodology {methodology}."
    )


# ---------------------------------------------------------------------------
# LOGO PATH
# ---------------------------------------------------------------------------

_opt_logo_svg = "/opt/agent-readiness/website/assets/gradeforai-logo.svg"
_local_logo_svg = os.path.expanduser("~/agent-readiness/website/assets/gradeforai-logo.svg")
LOGO_SVG_PATH = _opt_logo_svg if os.path.isfile(_opt_logo_svg) else _local_logo_svg

_opt_logo_old = "/opt/agent-readiness/website/assets/GradeForAI logo.svg"
_local_logo_old = os.path.expanduser("~/agent-readiness/website/assets/GradeForAI logo.svg")
LOGO_PATH = _opt_logo_old if os.path.isfile(_opt_logo_old) else _local_logo_old


# ---------------------------------------------------------------------------
# CSS GENERATION HELPERS
# ---------------------------------------------------------------------------

def font_face_css():
    """Generate @font-face declarations for all report fonts."""
    faces = []

    # Fraunces
    weight_map = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700, "italic": 400}
    for style, filename in FONT_DISPLAY_FILES.items():
        weight = weight_map[style]
        font_style = "italic" if style == "italic" else "normal"
        path = font_path(filename)
        faces.append(
            f"@font-face {{\n"
            f"  font-family: '{FONT_DISPLAY}';\n"
            f"  font-style: {font_style};\n"
            f"  font-weight: {weight};\n"
            f"  src: url('file://{path}') format('truetype');\n"
            f"}}"
        )

    # Inter
    inter_weights = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700}
    for style, filename in FONT_BODY_FILES.items():
        weight = inter_weights[style]
        path = font_path(filename)
        faces.append(
            f"@font-face {{\n"
            f"  font-family: '{FONT_BODY}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: {weight};\n"
            f"  src: url('file://{path}') format('truetype');\n"
            f"}}"
        )

    # JetBrains Mono
    for style, filename in FONT_MONO_FILES.items():
        path = font_path(filename)
        faces.append(
            f"@font-face {{\n"
            f"  font-family: '{FONT_MONO}';\n"
            f"  font-style: normal;\n"
            f"  font-weight: 400;\n"
            f"  src: url('file://{path}') format('truetype');\n"
            f"}}"
        )

    return "\n".join(faces)


def page_css():
    """Generate @page rules for the report."""
    return f"""
@page {{
    size: {PAGE_SIZE};
    margin: {MARGIN_TOP} {MARGIN_OUTER} {MARGIN_BOTTOM} {MARGIN_INNER};
    @top-left {{
        content: element(page-header-left);
        font-family: '{FONT_BODY}', sans-serif;
        font-size: {TYPE_EYEBROW};
        color: {MUTED_SOFT};
        text-transform: uppercase;
        letter-spacing: {SMALL_CAPS_TRACKING};
    }}
    @top-right {{
        content: element(page-header-right);
        font-family: '{FONT_BODY}', sans-serif;
        font-size: {TYPE_EYEBROW};
        color: {MUTED_SOFT};
        text-transform: uppercase;
        letter-spacing: {SMALL_CAPS_TRACKING};
    }}
    @bottom-left {{
        content: element(page-footer-left);
        font-family: '{FONT_BODY}', sans-serif;
        font-size: {TYPE_SOURCE};
        color: {MUTED_SOFT};
    }}
    @bottom-right {{
        content: element(page-footer-right);
        font-family: '{FONT_BODY}', sans-serif;
        font-size: {TYPE_SOURCE};
        color: {MUTED_SOFT};
        font-feature-settings: {TABULAR_FIGURES};
    }}
}}

@page cover {{
    margin: {MARGIN_TOP} {MARGIN_OUTER} {MARGIN_BOTTOM} {MARGIN_INNER};
    @top-left {{ content: none; }}
    @top-right {{ content: none; }}
    @bottom-left {{ content: none; }}
    @bottom-right {{ content: none; }}
}}

@page divider {{
    @top-left {{ content: none; }}
    @top-right {{ content: none; }}
    @bottom-left {{ content: none; }}
    @bottom-right {{ content: none; }}
}}
"""


def base_css():
    """Generate base body/element styles."""
    return f"""
body {{
    font-family: '{FONT_BODY}', -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: {TYPE_BODY};
    line-height: {LEADING_BODY};
    color: {INK};
    -webkit-font-smoothing: antialiased;
    font-feature-settings: {TABULAR_FIGURES};
}}

h1 {{
    font-family: '{FONT_DISPLAY}', Georgia, serif;
    font-size: {TYPE_H1};
    font-weight: 600;
    line-height: {LEADING_DISPLAY};
    color: {INK};
    margin: 0 0 {SPACE_MD} 0;
}}

h2 {{
    font-family: '{FONT_DISPLAY}', Georgia, serif;
    font-size: {TYPE_H2};
    font-weight: 600;
    line-height: {LEADING_DISPLAY};
    color: {INK};
    margin: 0 0 {SPACE_SM} 0;
}}

p {{
    margin: 0 0 {SPACE_SM} 0;
}}

table {{
    font-size: {TYPE_BODY_SMALL};
    border-collapse: collapse;
    width: 100%;
}}

.eyebrow {{
    font-family: '{FONT_BODY}', sans-serif;
    font-size: {TYPE_EYEBROW};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: {SMALL_CAPS_TRACKING};
    color: {MUTED_SOFT};
}}

.source {{
    font-family: '{FONT_BODY}', sans-serif;
    font-size: {TYPE_SOURCE};
    color: {MUTED_SOFT};
    margin-top: {SPACE_SM};
    line-height: {LEADING_TIGHT};
}}

.signal-label {{
    font-family: '{FONT_BODY}', sans-serif;
    font-size: {TYPE_SIGNAL_LABEL};
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: {SMALL_CAPS_TRACKING};
    padding: {SIGNAL_PADDING_V} {SIGNAL_PADDING_H};
    border: {RULE_STANDARD} solid {SIGNAL_BORDER};
    display: inline-block;
    line-height: 1;
}}

.page-header-left {{
    position: running(page-header-left);
}}
.page-header-right {{
    position: running(page-header-right);
}}
.page-footer-left {{
    position: running(page-footer-left);
}}
.page-footer-right {{
    position: running(page-footer-right);
}}

.rule-hairline {{
    border: none;
    border-top: {RULE_HAIRLINE} solid {RULE_COLOR};
    margin: 0;
}}

.rule-standard {{
    border: none;
    border-top: {RULE_STANDARD} solid {RULE_COLOR};
    margin: 0;
}}

.rule-emphasis {{
    border: none;
    border-top: {RULE_EMPHASIS} solid {BRAND_BLUE};
    margin: 0;
}}

/* Widow/orphan control */
p, li, div {{
    widows: 2;
    orphans: 2;
}}

tr {{
    page-break-inside: avoid;
}}

thead {{
    display: table-header-group;
}}
"""
