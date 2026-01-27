import math
import base64

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from datetime import datetime, timedelta

# --- Page Configuration ---
st.set_page_config(
    page_title="DFTL Ranking Dashboard",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Design System ---
# Theme-aware color palette (works with both light and dark modes)
# Accent colors are the same in both themes, only text/background colors differ

# Static accent colors (theme-independent)
ACCENT_COLORS = {
    "primary": "#FF6B6B",       # Coral red - primary accent
    "primary_light": "#FF8E8E",
    "primary_dark": "#E55555",
    "success": "#10B981",       # Green - positive changes
    "warning": "#F59E0B",       # Amber - neutral/caution
    "danger": "#EF4444",        # Red - negative changes
    "info": "#3B82F6",          # Blue - informational
    "chart_palette": [
        "#FF6B6B", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6",
        "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#6366F1"
    ],
}

# --- Tier System ---
# Rating tiers with distinct visual identities (like chess/gaming ranks)
TIER_SYSTEM = {
    "Grandmaster": {"min": 2700, "color": "#FF6B6B", "gradient": "linear-gradient(135deg, #FF6B6B 0%, #FFD700 50%, #FF6B6B 100%)", "glow": "0 0 20px rgba(255,107,107,0.6)", "icon": "👑"},
    "Master": {"min": 2500, "color": "#9333EA", "gradient": "linear-gradient(135deg, #9333EA 0%, #C084FC 100%)", "glow": "0 0 15px rgba(147,51,234,0.5)", "icon": "💎"},
    "Diamond": {"min": 2200, "color": "#06B6D4", "gradient": "linear-gradient(135deg, #06B6D4 0%, #67E8F9 100%)", "glow": "0 0 12px rgba(6,182,212,0.4)", "icon": "💠"},
    "Platinum": {"min": 1900, "color": "#E2E8F0", "gradient": "linear-gradient(135deg, #94A3B8 0%, #E2E8F0 100%)", "glow": "0 0 10px rgba(226,232,240,0.3)", "icon": "⚪"},
    "Gold": {"min": 1600, "color": "#F59E0B", "gradient": "linear-gradient(135deg, #D97706 0%, #FCD34D 100%)", "glow": "0 0 10px rgba(245,158,11,0.3)", "icon": "🥇"},
    "Silver": {"min": 1300, "color": "#9CA3AF", "gradient": "linear-gradient(135deg, #6B7280 0%, #D1D5DB 100%)", "glow": "none", "icon": "🥈"},
    "Bronze": {"min": 0, "color": "#CD7F32", "gradient": "linear-gradient(135deg, #92400E 0%, #D97706 100%)", "glow": "none", "icon": "🥉"},
}

def get_tier(rating):
    """Get tier information for a given rating."""
    if pd.isna(rating):
        return None
    for tier_name, tier_info in TIER_SYSTEM.items():
        if rating >= tier_info["min"]:
            return {"name": tier_name, **tier_info}
    return {"name": "Bronze", **TIER_SYSTEM["Bronze"]}

def get_tier_badge_html(rating, show_icon=True, size="small"):
    """Generate HTML for a tier badge."""
    tier = get_tier(rating)
    if tier is None:
        return ""

    sizes = {
        "small": {"font": "0.7rem", "padding": "0.15rem 0.4rem", "icon_size": "0.8rem"},
        "medium": {"font": "0.8rem", "padding": "0.2rem 0.5rem", "icon_size": "1rem"},
        "large": {"font": "0.9rem", "padding": "0.25rem 0.6rem", "icon_size": "1.1rem"},
    }
    s = sizes.get(size, sizes["small"])

    icon_html = f'<span style="font-size:{s["icon_size"]};margin-right:0.2rem;">{tier["icon"]}</span>' if show_icon else ""
    badge_style = f'background:{tier["gradient"]};color:#000;font-size:{s["font"]};font-weight:600;padding:{s["padding"]};border-radius:4px;box-shadow:{tier["glow"]};text-shadow:0 1px 0 rgba(255,255,255,0.3);display:inline-flex;align-items:center;'

    return f'<span style="{badge_style}">{icon_html}{tier["name"]}</span>'

# --- Leaderboard Flourishes ---
# Icons and decorations for top players
RANK_ICONS = {
    1: {"icon": "👑", "color": "#FFD700", "label": "Champion"},
    2: {"icon": "🥈", "color": "#C0C0C0", "label": "Runner-up"},
    3: {"icon": "🥉", "color": "#CD7F32", "label": "Third Place"},
}

def get_rank_icon(rank):
    """Get the icon for a given rank (top 3 only)."""
    if pd.isna(rank):
        return ""
    rank = int(rank)
    if rank in RANK_ICONS:
        return RANK_ICONS[rank]["icon"]
    return ""

def get_rank_badge_html(rank):
    """Generate HTML for a rank badge with icon and styling."""
    if pd.isna(rank):
        return ""
    rank = int(rank)
    if rank not in RANK_ICONS:
        return f'<span style="font-weight:600;">#{rank}</span>'

    info = RANK_ICONS[rank]
    badge_style = f'display:inline-flex;align-items:center;gap:0.3rem;font-weight:700;color:{info["color"]};text-shadow:0 0 10px {info["color"]}40;'
    return f'<span style="{badge_style}"><span style="font-size:1.2rem;">{info["icon"]}</span>#{rank}</span>'


def format_player_with_tier(player_name, rating, rank=None):
    """Format player name with tier badge and optional rank icon."""
    rank_icon = get_rank_icon(rank) if rank else ""
    tier_badge = get_tier_badge_html(rating, show_icon=False, size="small")

    rank_html = f'<span style="margin-right:0.3rem;font-size:1.1rem;">{rank_icon}</span>' if rank_icon else ""

    return f'<div style="display:inline-flex;align-items:center;gap:0.5rem;">{rank_html}<span style="font-weight:600;">{player_name}</span> {tier_badge}</div>'


def create_top3_spotlight_html(df_top3):
    """Create HTML for the Top 3 Spotlight section with flourishes."""
    if len(df_top3) == 0:
        return ""

    cards_html = []
    for _, row in df_top3.iterrows():
        rank = int(row['active_rank'])
        player = row['player_name']
        rating = row['rating']
        tier = get_tier(rating)
        rank_info = RANK_ICONS.get(rank, {"icon": "", "color": "#888888"})

        # Different card sizes: #1 is larger
        if rank == 1:
            card_style = f"flex:1.4;min-width:200px;background:linear-gradient(135deg,rgba(38,39,48,0.95) 0%,rgba(14,17,23,0.95) 100%);border:1px solid {rank_info['color']}50;border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 0 30px {rank_info['color']}60,0 0 60px {rank_info['color']}30;"
            icon_size = "3rem"
            name_size = "1.3rem"
            rating_size = "1.8rem"
        elif rank == 2:
            card_style = f"flex:1.2;min-width:180px;background:linear-gradient(135deg,rgba(38,39,48,0.95) 0%,rgba(14,17,23,0.95) 100%);border:1px solid {rank_info['color']}50;border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 0 20px {rank_info['color']}50;"
            icon_size = "2.5rem"
            name_size = "1.1rem"
            rating_size = "1.5rem"
        else:
            card_style = f"flex:1;min-width:160px;background:linear-gradient(135deg,rgba(38,39,48,0.95) 0%,rgba(14,17,23,0.95) 100%);border:1px solid {rank_info['color']}50;border-radius:16px;padding:1.5rem;text-align:center;box-shadow:0 0 15px {rank_info['color']}40;"
            icon_size = "2rem"
            name_size = "1rem"
            rating_size = "1.3rem"

        tier_badge = get_tier_badge_html(rating, show_icon=True, size="medium")

        card = f'<div style="{card_style}">'
        card += f'<div style="font-size:{icon_size};margin-bottom:0.5rem;filter:drop-shadow(0 0 10px {rank_info["color"]});">{rank_info["icon"]}</div>'
        card += f'<div style="font-family:Cinzel,serif;font-size:{name_size};font-weight:700;color:#FAFAFA;margin-bottom:0.25rem;text-shadow:0 2px 4px rgba(0,0,0,0.3);">{player}</div>'
        card += f'<div style="margin-bottom:0.5rem;">{tier_badge}</div>'
        card += f'<div style="font-family:Rajdhani,sans-serif;font-size:{rating_size};font-weight:700;background:linear-gradient(135deg,#FAFAFA 0%,{tier["color"]} 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">{rating:.1f}</div>'
        card += '</div>'
        cards_html.append(card)

    container_style = "display:flex;gap:1rem;justify-content:center;align-items:flex-end;flex-wrap:wrap;margin-bottom:1.5rem;padding:1rem;"
    return f'<div style="{container_style}">{"".join(cards_html)}</div>'


# Theme-specific colors (WCAG AA compliant contrast ratios)
DARK_THEME = {
    "bg_primary": "#0E1117",
    "bg_secondary": "#262730",
    "bg_hover": "#3D3D4D",
    "text_primary": "#FAFAFA",
    "text_secondary": "#E0E0E0",  # Improved: ~11:1 contrast vs bg_primary
    "text_muted": "#A0A0A0",       # Improved: ~7:1 contrast vs bg_primary
}

LIGHT_THEME = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F0F2F6",
    "bg_hover": "#E0E2E6",
    "text_primary": "#262730",
    "text_secondary": "#404040",  # Improved: ~10:1 contrast vs bg_primary
    "text_muted": "#666666",       # Improved: ~5.7:1 contrast vs bg_primary
}


def get_theme_colors():
    """Get the current theme colors based on user's theme preference."""
    # Streamlit 1.44+ provides st.context.theme for runtime theme detection
    try:
        # Check if we're in dark mode
        # theme.base can be "dark", "light", or None (system default which is dark)
        theme_base = st.get_option("theme.base")
        is_dark = theme_base != "light"  # Default to dark unless explicitly light
    except Exception:
        # Default to dark if detection fails
        is_dark = True

    theme = DARK_THEME if is_dark else LIGHT_THEME
    return {**ACCENT_COLORS, **theme}


def get_theme_css():
    """Generate theme-specific CSS for elements that need dynamic colors."""
    colors = get_theme_colors()
    is_dark = colors["bg_primary"] == "#0E1117"

    if is_dark:
        return """
        <style>
        /* Dark theme overrides */
        [data-testid="stExpander"] {
            background: rgba(38, 39, 48, 0.8) !important;
        }
        .dashboard-header {
            background: linear-gradient(135deg, rgba(38, 39, 48, 0.9) 0%, rgba(14, 17, 23, 0.95) 100%) !important;
        }

        /* Sidebar - Dark mode: high contrast white text */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1a1c23 0%, #0E1117 100%) !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2 {
            color: #FFFFFF !important;
        }
        /* Text elements - exclude Material icons by not targeting bare spans */
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown span,
        [data-testid="stSidebar"] .stSelectbox span {
            color: #E0E0E0 !important;
        }
        [data-testid="stSidebar"] .stCaption p {
            color: #CCCCCC !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.15) !important;
        }
        </style>
        """
    else:
        return """
        <style>
        /* Light theme overrides */
        [data-testid="stExpander"] {
            background: rgba(240, 242, 246, 0.95) !important;
        }
        .dashboard-header {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(240, 242, 246, 0.98) 100%) !important;
            border-color: rgba(0, 0, 0, 0.1) !important;
        }
        .dashboard-title {
            background: linear-gradient(135deg, #262730 0%, #404040 100%) !important;
            -webkit-background-clip: text !important;
            -webkit-text-fill-color: transparent !important;
        }
        .dashboard-subtitle {
            color: #555555 !important;
        }

        /* Sidebar - Light mode: high contrast dark text */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #FFFFFF 0%, #F0F2F6 100%) !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] .stMarkdown h1,
        [data-testid="stSidebar"] .stMarkdown h2 {
            color: #1a1c23 !important;
        }
        /* Text elements - exclude Material icons by not targeting bare spans */
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown span,
        [data-testid="stSidebar"] .stSelectbox span {
            color: #333333 !important;
        }
        [data-testid="stSidebar"] .stCaption p {
            color: #555555 !important;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(0, 0, 0, 0.1) !important;
        }

        /* Sidebar expand button (when collapsed) - make visible in light mode */
        /* Use filter to darken the icon since color overrides don't work */
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarNavCollapseButton"] {
            filter: brightness(0.2) !important;
        }
        [data-testid="collapsedControl"]:hover,
        [data-testid="stSidebarCollapsedControl"]:hover,
        [data-testid="stSidebarNavCollapseButton"]:hover {
            filter: brightness(0) !important;
        }
        /* Also try targeting via position - the expand control is fixed position */
        .stApp > div:first-child > [data-testid="collapsedControl"],
        section[data-testid="stSidebar"] ~ [data-testid="collapsedControl"] {
            filter: brightness(0.2) !important;
        }
        </style>
        """


# For backwards compatibility, create a COLORS alias
# This is evaluated once at module load, so charts use consistent colors
COLORS = {**ACCENT_COLORS, **DARK_THEME}  # Default to dark theme for static references

def create_download_link(data: str, filename: str, label: str, is_dark: bool = True) -> str:
    """
    Create a styled HTML download link with full CSS control.

    Args:
        data: The CSV string data to download
        filename: The filename for the download
        label: The button label text
        is_dark: Whether we're in dark mode (affects text color)

    Returns:
        HTML string with styled download link
    """
    b64 = base64.b64encode(data.encode()).decode()

    # Theme-aware colors
    if is_dark:
        text_color = "#FAFAFA"
        bg_color = "rgba(38,39,48,0.8)"
        border_color = "rgba(255,255,255,0.2)"
        hover_bg = "rgba(58,59,68,0.9)"
    else:
        text_color = "#1a1c23"
        bg_color = "rgba(255,255,255,0.95)"
        border_color = "rgba(0,0,0,0.2)"
        hover_bg = "rgba(240,240,240,1)"

    # Compact single-line HTML for reliable Streamlit rendering
    style = f"display:inline-block;padding:0.5rem 1rem;background:{bg_color};color:{text_color};text-decoration:none;border:1px solid {border_color};border-radius:0.5rem;font-family:Rajdhani,sans-serif;font-weight:600;font-size:0.9rem;cursor:pointer;width:100%;text-align:center;box-sizing:border-box;"

    return f'<a href="data:text/csv;base64,{b64}" download="{filename}" style="{style}">{label}</a>'


# Custom CSS for visual hierarchy and spacing
# Includes: Gothic fonts, glassmorphism, animations, gradient effects
CUSTOM_CSS = """
<style>
/* ===== Google Fonts - Gothic/Fantasy Theme ===== */
@import url('https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Rajdhani:wght@400;500;600;700&display=swap');

/* ===== CSS Variables ===== */
:root {
    --font-display: 'Cinzel', serif;
    --font-body: 'Rajdhani', sans-serif;
    --primary-glow: 0 0 20px rgba(255, 107, 107, 0.4);
    --glass-bg: rgba(38, 39, 48, 0.7);
    --glass-border: rgba(255, 107, 107, 0.2);
}

/* ===== Typography Hierarchy ===== */
.main h1, .main h2, .main h3 {
    font-family: var(--font-display) !important;
}

.main h1 {
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 0.5rem !important;
}

.main h2 {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    margin-top: 1.5rem !important;
    margin-bottom: 1rem !important;
    letter-spacing: 0.03em !important;
}

.main h3 {
    font-size: 1.25rem !important;
    font-weight: 600 !important;
}

/* Body text uses Rajdhani for readability */
.main p, .main span, .main label, .main div {
    font-family: var(--font-body), sans-serif;
}

/* ===== Section Containers ===== */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem;
}

/* ===== Glassmorphism Metric Cards (optimized - no blur for performance) ===== */
[data-testid="stMetric"] {
    background: rgba(38, 39, 48, 0.85) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3), var(--primary-glow), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
    border-color: rgba(255, 107, 107, 0.4) !important;
}

[data-testid="stMetric"] label {
    font-family: var(--font-body) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    opacity: 0.8;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: var(--font-display) !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
    background: linear-gradient(135deg, #FAFAFA 0%, #FF6B6B 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* ===== Number Counter Effect (static for performance) ===== */
/* Animation removed - was causing re-renders on every state change */

/* ===== Data Tables with Glass Effect ===== */
.stDataFrame {
    border-radius: 12px !important;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
}

.stDataFrame thead th {
    font-family: var(--font-body) !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    font-size: 0.7rem !important;
    letter-spacing: 0.08em !important;
    background: rgba(255, 107, 107, 0.1) !important;
}

/* ===== Sidebar Styling ===== */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(14, 17, 23, 0.95) 0%, rgba(38, 39, 48, 0.95) 100%) !important;
}

[data-testid="stSidebar"] .stMarkdown hr {
    border-color: rgba(255, 107, 107, 0.3);
    margin: 1.5rem 0;
    box-shadow: 0 1px 0 rgba(255, 107, 107, 0.1);
}

/* Sidebar collapse button (inside sidebar) - always light (sidebar is always dark) */
/* Use CSS filter as fallback - inverts dark icon to light */
/* IMPORTANT: Only target elements INSIDE [data-testid="stSidebar"] */
[data-testid="stSidebar"] button[data-testid="stBaseButton-headerNoPadding"],
[data-testid="stSidebar"] [data-testid="stSidebarNav"] button,
[data-testid="stSidebar"] button[kind="headerNoPadding"],
[data-testid="stSidebar"] > div > button,
[data-testid="stSidebar"] header button {
    color: #FFFFFF !important;
    filter: brightness(0) invert(1) !important;
}
[data-testid="stSidebar"] button[data-testid="stBaseButton-headerNoPadding"] svg,
[data-testid="stSidebar"] [data-testid="stSidebarNav"] svg,
[data-testid="stSidebar"] > div > button svg,
[data-testid="stSidebar"] header button svg {
    fill: #FFFFFF !important;
    stroke: #FFFFFF !important;
}

/* ===== Tab Styling - Subtle ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.25rem;
    background: transparent;
    padding: 0.25rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 0;
    /* Enable horizontal scrolling on narrow screens */
    overflow-x: auto;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
}

/* Hide the animated highlight bar */
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}

.stTabs [data-baseweb="tab"] {
    font-family: var(--font-body) !important;
    border-radius: 0 !important;
    padding: 0.6rem 1rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em;
    border-bottom: 2px solid transparent !important;
    background: transparent !important;
    opacity: 0.7;
    transition: opacity 0.15s ease !important;
    /* Prevent tabs from shrinking on narrow screens */
    flex-shrink: 0 !important;
    white-space: nowrap !important;
}

.stTabs [data-baseweb="tab"]:hover {
    opacity: 0.9;
    background: transparent !important;
    color: inherit !important;
}

.stTabs [aria-selected="true"] {
    opacity: 1 !important;
    border-bottom: 2px solid var(--text-color, currentColor) !important;
    background: transparent !important;
    color: inherit !important;
}

/* ===== Buttons with Glow Effect ===== */
.stButton > button {
    font-family: var(--font-body) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    border: 1px solid rgba(255, 107, 107, 0.3) !important;
}

.stButton > button:hover {
    border-color: #FF6B6B !important;
    box-shadow: var(--primary-glow) !important;
    transform: translateY(-1px);
}

/* ===== Toggle with Animation ===== */
[data-testid="stToggle"] label span {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
}

/* ===== Expander with Glass Effect ===== */
.streamlit-expanderHeader {
    font-family: var(--font-display) !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
}

[data-testid="stExpander"] {
    border: 1px solid var(--glass-border) !important;
    border-radius: 12px !important;
    /* Background set dynamically via get_theme_css() */
}

/* ===== Form Labels ===== */
[data-testid="stSelectbox"] label,
[data-testid="stDateInput"] label {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
}

/* ===== Spacing ===== */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.element-container {
    margin-bottom: 0.5rem;
}

/* ===== Dividers with Gradient ===== */
.main hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(255, 107, 107, 0.5) 50%, transparent 100%);
    margin: 1.5rem 0;
}

/* ===== Leaderboard Row Highlights ===== */
.rank-1-row {
    background: linear-gradient(90deg, rgba(255, 215, 0, 0.15) 0%, transparent 100%) !important;
    box-shadow: inset 3px 0 0 #FFD700;
}

.rank-2-row {
    background: linear-gradient(90deg, rgba(192, 192, 192, 0.1) 0%, transparent 100%) !important;
    box-shadow: inset 3px 0 0 #C0C0C0;
}

.rank-3-row {
    background: linear-gradient(90deg, rgba(205, 127, 50, 0.1) 0%, transparent 100%) !important;
    box-shadow: inset 3px 0 0 #CD7F32;
}

/* ===== Animation Keyframes (removed for performance) ===== */
/* Infinite animations removed - they cause continuous repaints */

/* ===== Custom Scrollbar ===== */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: rgba(38, 39, 48, 0.5);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, #FF6B6B 0%, #E55555 100%);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: linear-gradient(180deg, #FF8E8E 0%, #FF6B6B 100%);
}

/* ===== Tooltip Styling ===== */
[data-testid="stTooltipIcon"] {
    color: rgba(255, 107, 107, 0.7) !important;
}

/* ===== Selection Highlight ===== */
::selection {
    background: rgba(255, 107, 107, 0.3);
    color: #FAFAFA;
}

/* ===== Top 3 Spotlight ===== */
/* Static styling - animations removed for performance */

/* ===== Sidebar Styling ===== */
/* Sidebar text styling handled dynamically via get_theme_css() */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: var(--font-body) !important;  /* Rajdhani - more conventional than gothic */
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}

/* Text elements - exclude Material icons by not targeting bare spans */
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown span,
[data-testid="stSidebar"] .stSelectbox span {
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
}

/* Sidebar dividers - color handled dynamically via get_theme_css() */
[data-testid="stSidebar"] hr {
    margin: 1rem 0 !important;
}
</style>
"""


def apply_plotly_style(fig, add_gradient_fill=False):
    """Apply consistent styling to Plotly figures (theme-aware) with optional gradient fill."""
    colors = get_theme_colors()

    # Theme-aware background colors for overlays
    is_dark = colors["bg_primary"] == "#0E1117"
    if is_dark:
        legend_bg = "rgba(38, 39, 48, 0.9)"
        hover_bg = "rgba(38, 39, 48, 0.95)"
        grid_color = "rgba(255, 255, 255, 0.08)"
        line_color = "rgba(255, 255, 255, 0.15)"
    else:
        legend_bg = "rgba(255, 255, 255, 0.95)"
        hover_bg = "rgba(255, 255, 255, 0.98)"
        grid_color = "rgba(0, 0, 0, 0.08)"
        line_color = "rgba(0, 0, 0, 0.15)"

    # Bold font weight for better readability
    bold_weight = 600

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=colors["text_primary"], family="Rajdhani, sans-serif", weight=bold_weight),
        xaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(color=colors["text_secondary"], family="Rajdhani", size=12, weight=bold_weight),
            title_font=dict(weight=bold_weight),
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(color=colors["text_secondary"], family="Rajdhani", size=12, weight=bold_weight),
            title_font=dict(weight=bold_weight),
            showgrid=True,
            zeroline=False,
        ),
        legend=dict(
            font=dict(color=colors["text_primary"], family="Rajdhani", weight=bold_weight),
            bgcolor=legend_bg,
            bordercolor=line_color,
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor=colors["primary"],
            font=dict(color=colors["text_primary"], family="Rajdhani", weight=bold_weight),
        ),
    )

    # Add gradient fill under line charts if requested
    if add_gradient_fill:
        fig.update_traces(
            fill='tozeroy',
            fillcolor='rgba(255, 107, 107, 0.15)',
            line=dict(width=3),
        )

    return fig

def apply_plotly_style_enhanced(fig):
    """Apply enhanced styling with gradient fills and glowing markers."""
    apply_plotly_style(fig)
    fig.update_traces(
        marker=dict(
            size=8,
            line=dict(width=2, color='rgba(255, 107, 107, 0.8)'),
        ),
        line=dict(width=3),
    )
    return fig


def format_rating_change(value):
    """Format rating change with color indicator (uses accent colors - theme-independent)."""
    if pd.isna(value):
        return ""
    if value > 0:
        return f"<span style='color: {ACCENT_COLORS['success']}'>+{value:.1f}</span>"
    elif value < 0:
        return f"<span style='color: {ACCENT_COLORS['danger']}'>{value:.1f}</span>"
    else:
        return f"<span style='color: #767676'>{value:.1f}</span>"  # WCAG AA compliant in both themes


def format_trend(trend):
    """Format trend indicator with color (uses accent colors - theme-independent)."""
    if trend == "↑":
        return f"<span style='color: {ACCENT_COLORS['success']}; font-size: 1.25rem;'>↑</span>"
    elif trend == "↓":
        return f"<span style='color: {ACCENT_COLORS['danger']}; font-size: 1.25rem;'>↓</span>"
    else:
        return f"<span style='color: #767676; font-size: 1.25rem;'>→</span>"  # WCAG AA compliant in both themes


# --- Constants ---
OUTPUT_FOLDER = Path(__file__).parent / "output"
DATASET_OPTIONS = {
    "Steam Demo+Early Access": "full",
    "Early Access Only": "early_access"
}


# --- Data Loading Functions ---
@st.cache_data(ttl=3600)
def load_leaderboard_data(dataset_prefix):
    """Load the most recent leaderboard CSV for the given dataset."""
    pattern = f"{dataset_prefix}_leaderboard_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))
    if not files:
        return None
    df = pd.read_csv(files[-1], parse_dates=['date'])
    return df


@st.cache_data(ttl=3600)
def load_ratings_data(dataset_prefix):
    """Load the most recent Elo ratings CSV for the given dataset (active players only)."""
    pattern = f"{dataset_prefix}_elo_ratings_*.csv"
    # Exclude _all_ files
    files = sorted([f for f in OUTPUT_FOLDER.glob(pattern) if '_all_' not in f.name])
    if not files:
        return None
    df = pd.read_csv(files[-1], parse_dates=['last_seen'])
    return df


@st.cache_data(ttl=3600)
def load_all_ratings_data(dataset_prefix):
    """Load the most recent Elo ratings CSV including inactive players."""
    pattern = f"{dataset_prefix}_elo_ratings_all_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))
    if not files:
        return None
    df = pd.read_csv(files[-1], parse_dates=['last_seen'])
    return df


@st.cache_data(ttl=3600)
def load_history_data(dataset_prefix):
    """Load the most recent Elo history CSV for the given dataset."""
    pattern = f"{dataset_prefix}_elo_history_*.csv"
    files = sorted(OUTPUT_FOLDER.glob(pattern))
    if not files:
        return None
    df = pd.read_csv(files[-1], parse_dates=['date'])
    return df


def get_available_datasets():
    """Check which datasets are available."""
    available = {}
    for label, prefix in DATASET_OPTIONS.items():
        if list(OUTPUT_FOLDER.glob(f"{prefix}_leaderboard_*.csv")):
            available[label] = prefix
    return available


# --- Main App ---
def main():
    # Inject custom CSS (static)
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Inject theme-specific CSS (dynamic based on current theme)
    st.markdown(get_theme_css(), unsafe_allow_html=True)

    # Title with logo, gradient text, and glow effects
    import base64
    logo_path = Path(__file__).parent / "images" / "dftl_logo.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
            .dashboard-header {{
                display: flex;
                align-items: center;
                gap: 2rem;
                margin-bottom: 1rem;
                padding: 1.5rem;
                background: linear-gradient(135deg, rgba(38, 39, 48, 0.9) 0%, rgba(14, 17, 23, 0.95) 100%);
                border-radius: 16px;
                border: 1px solid rgba(255, 107, 107, 0.2);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
            }}
            .dashboard-logo {{
                width: 140px;
                height: auto;
                filter: drop-shadow(0 0 15px rgba(255, 107, 107, 0.4));
            }}
            .dashboard-title {{
                font-family: 'Cinzel', serif;
                font-size: 2.8rem;
                font-weight: 700;
                margin: 0;
                padding: 0;
                background: linear-gradient(135deg, #FAFAFA 0%, #FF6B6B 50%, #FFD700 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                text-shadow: 0 0 30px rgba(255, 107, 107, 0.5);
                letter-spacing: 0.05em;
            }}
            .dashboard-subtitle {{
                font-family: 'Rajdhani', sans-serif;
                margin: 0.5rem 0 0 0;
                font-size: 1.1rem;
                color: #B0B0B0;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                font-weight: 500;
            }}
        </style>
        <div class="dashboard-header">
            <img src="data:image/png;base64,{logo_b64}" class="dashboard-logo">
            <div>
                <h1 class="dashboard-title">DFTL Ranking Dashboard</h1>
                <p class="dashboard-subtitle">Track Elo ratings, compare players, and analyze performance trends</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("DFTL Ranking Dashboard")
        st.caption("Track Elo ratings, compare players, and analyze performance trends")
    st.markdown("---")

    # Check for available datasets
    available_datasets = get_available_datasets()
    if not available_datasets:
        st.error("No data files found in the output folder. Please run the data pipeline first.")
        return

    # --- Sidebar ---
    with st.sidebar:
        st.header("📊 Dataset")

        # Dataset selector (label hidden - redundant with header)
        dataset_label = st.selectbox(
            "Dataset",
            options=list(available_datasets.keys()),
            index=0,
            label_visibility="collapsed"
        )
        dataset_prefix = available_datasets[dataset_label]

        # Load data
        df_leaderboard = load_leaderboard_data(dataset_prefix)
        df_ratings = load_ratings_data(dataset_prefix)
        df_ratings_all = load_all_ratings_data(dataset_prefix)
        df_history = load_history_data(dataset_prefix)

        if df_leaderboard is None:
            st.error("Failed to load leaderboard data.")
            return

        # Get date range for the dataset
        min_date = df_leaderboard['date'].min().date()
        max_date = df_leaderboard['date'].max().date()

        all_players = sorted(df_leaderboard['player_name'].unique())

        # Create rating-sorted player list (ranked first, then unranked, both by rating desc)
        if df_ratings_all is not None:
            df_ranked_sorted = df_ratings_all[df_ratings_all['active_rank'].notna()].sort_values('rating', ascending=False)
            df_unranked_sorted = df_ratings_all[df_ratings_all['active_rank'].isna()].sort_values('rating', ascending=False)
            players_by_rating = df_ranked_sorted['player_name'].tolist() + df_unranked_sorted['player_name'].tolist()
        else:
            players_by_rating = all_players  # Fallback to alphabetical

        st.markdown("---")
        st.caption(f"Data range: {min_date} to {max_date}")
        st.caption(f"Players in Dataset: {len(all_players)}")

        # Export Data section
        st.markdown("---")
        st.header("📥 Export Data")

        # Export leaderboard data (always use full dataset for complete data)
        df_full_leaderboard = load_leaderboard_data("full")
        if df_full_leaderboard is not None:
            csv_leaderboard = df_full_leaderboard.to_csv(index=False)
            # Custom HTML download link - full CSS control for light/dark mode
            colors = get_theme_colors()
            is_dark = colors["bg_primary"] == "#0E1117"
            download_html = create_download_link(
                data=csv_leaderboard,
                filename="full_leaderboard.csv",
                label="Download Leaderboard CSV",
                is_dark=is_dark
            )
            st.markdown(download_html, unsafe_allow_html=True)

        # Attribution
        st.markdown("---")
        st.caption("Made with 🫶 by N Prime")

    # Use full date range
    df_filtered = df_leaderboard.copy()

    # --- Main Content ---
    st.markdown(f"**Active dataset:** {dataset_label}")

    # Create tabs (Elo Rankings first for main use case)
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏅 Elo Rankings",
        "⚔️ Daily Duels",
        "👤 Player Tracker",
        "📊 Steam Leaderboards",
        "🏆 Top 10 History",
        "📖 FAQ / Glossary"
    ])

    # --- Tab 4: Steam Leaderboards ---
    with tab4:

        # Date selector for specific day
        available_dates = sorted(df_filtered['date'].dt.date.unique(), reverse=True)
        if available_dates:
            # Calendar date picker
            selected_date = st.date_input(
                "Select date",
                value=available_dates[0],  # Default to most recent
                min_value=available_dates[-1],
                max_value=available_dates[0]
            )

            # Check if selected date has data
            df_day = df_filtered[df_filtered['date'].dt.date == selected_date].copy()

            if df_day.empty:
                st.info(f"No leaderboard data for {selected_date.strftime('%Y-%m-%d')}. Try another date.")
            else:
                df_day = df_day.sort_values('rank').head(30)

                # Merge with history data for rating, rating_change, and active_rank
                if df_history is not None:
                    # Get history for the selected date (active_rank is pre-computed if available)
                    history_cols = ['player_name', 'rating', 'rating_change']
                    if 'active_rank' in df_history.columns:
                        history_cols.append('active_rank')
                    df_day_history = df_history[df_history['date'].dt.date == selected_date][
                        history_cols
                    ].copy()
                    df_day = df_day.merge(df_day_history, on='player_name', how='left')
                    display_cols = ['rank', 'player_name', 'score', 'rating', 'rating_change']
                    if 'active_rank' in df_day.columns:
                        display_cols.append('active_rank')
                else:
                    display_cols = ['rank', 'player_name', 'score']

                # Display table
                column_config = {
                    "rank": st.column_config.NumberColumn("Daily Rank", format="%d"),
                    "player_name": st.column_config.TextColumn("Player"),
                    "score": st.column_config.NumberColumn("Score", format="%d"),
                    "rating": st.column_config.NumberColumn("Elo Rating", format="%.1f"),
                    "rating_change": st.column_config.NumberColumn("Rating Change", format="%+.1f")
                }
                if 'active_rank' in df_day.columns:
                    column_config["active_rank"] = st.column_config.NumberColumn("Elo Rank", format="%d")

                st.dataframe(
                    df_day[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config
                )
        else:
            st.warning("No data available for the selected date range.")

    # --- Tab 1: Elo Rankings ---
    with tab1:
        if df_history is not None and 'active_rank' in df_history.columns:
            # Date picker for historical rankings
            available_dates = sorted(df_history['date'].dt.date.unique(), reverse=True)

            selected_ranking_date = st.date_input(
                "Date",
                value=available_dates[0],
                min_value=available_dates[-1],
                max_value=available_dates[0],
                key="elo_ranking_date"
            )

            # Load data for selected date
            df_date_history = df_history[df_history['date'].dt.date == selected_ranking_date].copy()

            if df_date_history.empty:
                st.info(f"No ranking data for {selected_ranking_date}. Try another date.")
            else:
                # Leaderboard section
                date_str = selected_ranking_date.strftime("%b %d, %Y")
                st.subheader(f"Elo Ranking Leaderboard - {date_str} Ratings")

                # Toggle to show unranked players
                show_unranked = st.toggle("Show Unranked Players", value=True, help="Players with <7 games or inactive >7 days")

                # Columns to display (defined once, reused)
                display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency']
                if 'days_inactive' in df_date_history.columns:
                    display_cols.append('days_inactive')

                # Filter and sort in one operation (no unnecessary copies)
                # All stats are pre-computed in the history CSV - just filter and display
                if show_unranked:
                    df_rankings_display = df_date_history.sort_values('rating', ascending=False)[display_cols]
                else:
                    df_rankings_display = df_date_history[df_date_history['active_rank'].notna()].sort_values('rating', ascending=False)[display_cols]

                column_config = {
                    "active_rank": st.column_config.NumberColumn("Elo Rank", format="%d"),
                    "player_name": st.column_config.TextColumn("Player"),
                    "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                    "games_played": st.column_config.NumberColumn("Games", format="%d"),
                    "wins": st.column_config.NumberColumn("Wins", format="%d"),
                    "win_rate": st.column_config.NumberColumn("Win %", format="%.1f"),
                    "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                    "top_10s_rate": st.column_config.NumberColumn("Top 10 %", format="%.1f"),
                    "avg_daily_rank": st.column_config.NumberColumn("Avg Rank", format="%.1f"),
                    "last_7": st.column_config.NumberColumn("Recent", format="%.1f", help="Average daily rank over last 7 games"),
                    "consistency": st.column_config.NumberColumn("Consistency", format="%.1f", help="Standard deviation of daily ranks over last 14 games (lower = more consistent)"),
                    "days_inactive": st.column_config.NumberColumn("Inactive", format="%d")
                }

                st.dataframe(
                    df_rankings_display,
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config
                )
        elif df_ratings is not None:
            # Fallback if no history data with active_rank
            st.warning("Historical rankings not available. Showing current rankings only.")

            # Rating Distribution Chart
            with st.expander("📊 Rating Distribution", expanded=False):
                fig_dist = px.histogram(
                    df_ratings,
                    x='rating',
                    nbins=20,
                    labels={'rating': 'Elo Rating', 'count': 'Players'},
                    color_discrete_sequence=[ACCENT_COLORS["primary"]]
                )
                apply_plotly_style(fig_dist)
                # Enhanced bar styling with glow effect
                fig_dist.update_traces(
                    marker=dict(
                        line=dict(width=1, color='rgba(255, 107, 107, 0.8)'),
                        opacity=0.85,
                    ),
                )
                fig_dist.update_layout(
                    showlegend=False,
                    height=300,
                    margin=dict(l=20, r=20, t=30, b=20),
                    xaxis_title="Rating",
                    yaxis_title="Players"
                )
                fig_dist.add_vline(
                    x=df_ratings['rating'].median(),
                    line_dash="dash",
                    line_color=ACCENT_COLORS["warning"],
                    annotation_text=f"Median: {df_ratings['rating'].median():.0f}",
                    annotation_font=dict(color=ACCENT_COLORS["warning"], weight=600)
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            # Toggle to show unranked players
            show_unranked = st.toggle("Show Unranked Players", value=True, help="Players with <7 games or inactive >7 days")

            # Determine which ratings to display
            if show_unranked and df_ratings_all is not None:
                df_ratings_to_display = df_ratings_all.copy()
            else:
                df_ratings_to_display = df_ratings.copy()

            # All players table
            st.subheader("Elo Ranking Leaderboard")

            # Calculate player stats from leaderboard data
            player_stats = df_leaderboard.groupby('player_name').agg(
                wins=('rank', lambda x: (x == 1).sum()),
                top_10s=('rank', lambda x: (x <= 10).sum()),
                avg_daily_rank=('rank', 'mean'),
                total_games=('rank', 'count')
            ).reset_index()
            player_stats['avg_daily_rank'] = player_stats['avg_daily_rank'].round(1)
            player_stats['win_rate'] = (player_stats['wins'] / player_stats['total_games'] * 100).round(1)
            player_stats['top_10s_rate'] = (player_stats['top_10s'] / player_stats['total_games'] * 100).round(1)
            player_stats = player_stats.drop(columns=['total_games'])

            # Calculate Last 7: average daily rank over last 7 games
            last7_data = []
            for player in df_ratings_to_display['player_name'].unique():
                player_games = df_leaderboard[
                    df_leaderboard['player_name'] == player
                ].sort_values('date', ascending=False).head(7)

                if len(player_games) > 0:
                    avg_last7 = player_games['rank'].mean()
                    last7_data.append({
                        'player_name': player,
                        'last_7': round(avg_last7, 1)
                    })
                else:
                    last7_data.append({'player_name': player, 'last_7': None})

            df_last7 = pd.DataFrame(last7_data)
            player_stats = player_stats.merge(df_last7, on='player_name', how='left')

            # Merge stats with ratings
            df_ratings_display = df_ratings_to_display.merge(player_stats, on='player_name', how='left')

            # Determine columns based on whether we have uncertainty data
            has_uncertainty = 'uncertainty' in df_ratings_display.columns
            has_days_inactive = 'days_inactive' in df_ratings_display.columns

            # Select columns to display (use active_rank instead of rank)
            display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'last_seen']
            if has_days_inactive:
                display_cols.insert(-1, 'days_inactive')
            if has_uncertainty and show_unranked:
                display_cols.insert(-1, 'uncertainty')

            column_config = {
                "active_rank": st.column_config.NumberColumn("Elo Rank", format="%d"),
                "player_name": st.column_config.TextColumn("Player"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                "games_played": st.column_config.NumberColumn("Games", format="%d"),
                "wins": st.column_config.NumberColumn("Wins", format="%d"),
                "win_rate": st.column_config.NumberColumn("Win %", format="%.1f"),
                "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                "top_10s_rate": st.column_config.NumberColumn("Top 10 %", format="%.1f"),
                "avg_daily_rank": st.column_config.NumberColumn("Avg Rank", format="%.1f"),
                "last_7": st.column_config.NumberColumn("Recent", format="%.1f", help="Average daily rank over last 7 games"),
                "last_seen": st.column_config.DateColumn("Last Seen", format="YYYY-MM-DD")
            }
            if has_days_inactive:
                column_config["days_inactive"] = st.column_config.NumberColumn("Inactive", format="%d")
            if has_uncertainty:
                column_config["uncertainty"] = st.column_config.NumberColumn("Uncertainty", format="%.2f")

            st.dataframe(
                df_ratings_display[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
        else:
            st.warning("Ratings data not available.")

    # --- Tab 3: Player Tracker ---
    with tab3:

        if df_history is not None:
            # Player selector (single selection)
            selected_player = st.selectbox(
                "Select a player",
                options=players_by_rating,
                index=None,
                placeholder="Choose a player...",
                key="tab4_player_select"
            )

            if selected_player:
                # Filter history for selected player
                df_player_history = df_history[
                    df_history['player_name'] == selected_player
                ].copy()

                if not df_player_history.empty:
                    # Filter to days where the player actually played (score is not null)
                    df_player_played = df_player_history[df_player_history['score'].notna()].copy()

                    if not df_player_played.empty:
                        # Get latest stats from the most recent game
                        latest = df_player_played.sort_values('date', ascending=False).iloc[0]
                        has_active_rank = 'active_rank' in df_player_played.columns

                        # --- Key Metrics Section ---
                        st.subheader("Player Summary")

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            current_rating = latest['rating']
                            tier = get_tier(current_rating)
                            tier_name = tier['name'] if tier else "Unranked"
                            st.metric("Current Rating", f"{current_rating:.0f}", help=f"Tier: {tier_name}")
                        with col2:
                            games = int(latest['games_played'])
                            st.metric("Games Played", games)
                        with col3:
                            wins = int(latest['wins'])
                            win_rate = latest['win_rate']
                            st.metric("Wins", wins, help=f"Win Rate: {win_rate:.1f}%")
                        with col4:
                            top_10s = int(latest['top_10s'])
                            top_10_rate = latest['top_10s_rate']
                            st.metric("Top 10", top_10s, help=f"Top 10 Rate: {top_10_rate:.1f}%")

                        # Second row of metrics
                        col5, col6, col7, col8 = st.columns(4)

                        with col5:
                            avg_rank = latest['avg_daily_rank']
                            st.metric("Avg Rank", f"{avg_rank:.1f}" if pd.notna(avg_rank) else "N/A")
                        with col6:
                            last_7 = latest['last_7']
                            st.metric("Recent (L7)", f"{last_7:.1f}" if pd.notna(last_7) else "N/A", help="Average rank over last 7 games")
                        with col7:
                            consistency = latest['consistency']
                            st.metric("Consistency", f"{consistency:.1f}" if pd.notna(consistency) else "N/A", help="Lower is more consistent")
                        with col8:
                            if has_active_rank and pd.notna(latest['active_rank']):
                                st.metric("Elo Rank", f"#{int(latest['active_rank'])}")
                            else:
                                st.metric("Elo Rank", "Unranked", help="Inactive or <7 games")

                        st.markdown("")  # Spacer

                        # --- First and Last Game Badges ---
                        sorted_games = df_player_played.sort_values('date')
                        first_game = sorted_games.iloc[0]
                        last_game = sorted_games.iloc[-1]

                        col_first, col_last = st.columns(2)
                        with col_first:
                            first_date = first_game['date']
                            if hasattr(first_date, 'strftime'):
                                first_date_str = first_date.strftime('%Y-%m-%d')
                            else:
                                first_date_str = str(first_date)[:10]
                            first_rank = int(first_game['rank'])
                            first_rating = first_game['rating']
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(59,130,246,0.2) 100%);
                                        border: 1px solid {ACCENT_COLORS['info']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; margin-bottom: 0.25rem;">First Game</div>
                                <div style="font-size: 1.25rem; font-weight: 700;">{first_date_str}</div>
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['info']};">Rank #{first_rank} | Rating: {first_rating:.0f}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_last:
                            last_date = last_game['date']
                            if hasattr(last_date, 'strftime'):
                                last_date_str = last_date.strftime('%Y-%m-%d')
                            else:
                                last_date_str = str(last_date)[:10]
                            last_rank = int(last_game['rank'])
                            last_rating = last_game['rating']
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.2) 100%);
                                        border: 1px solid {ACCENT_COLORS['primary']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; margin-bottom: 0.25rem;">Last Game</div>
                                <div style="font-size: 1.25rem; font-weight: 700;">{last_date_str}</div>
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['primary']};">Rank #{last_rank} | Rating: {last_rating:.0f}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("")  # Spacer

                        # --- Rating Trajectory Chart ---
                        st.subheader("Elo Rating History")
                        df_chart = df_player_played.sort_values('date')

                        fig_rating = px.line(
                            df_chart,
                            x='date',
                            y='rating',
                            markers=True,
                            labels={'date': 'Date', 'rating': 'Elo Rating'},
                            color_discrete_sequence=[ACCENT_COLORS["primary"]]
                        )
                        apply_plotly_style(fig_rating)
                        fig_rating.update_traces(
                            marker=dict(size=8, line=dict(width=2, color='rgba(255,255,255,0.3)')),
                            line=dict(width=3),
                            fill='tozeroy',
                            fillcolor='rgba(255, 107, 107, 0.15)',
                        )
                        # Set Y-axis range to fit data with padding (don't show 0)
                        rating_min = df_chart['rating'].min()
                        rating_max = df_chart['rating'].max()
                        rating_padding = (rating_max - rating_min) * 0.1
                        y_min = max(rating_min - rating_padding, 1000)  # Don't go below 1000
                        y_max = rating_max + rating_padding
                        fig_rating.update_layout(
                            height=300,
                            margin=dict(l=20, r=20, t=30, b=20),
                            showlegend=False,
                            yaxis=dict(range=[y_min, y_max])
                        )
                        fig_rating.add_hline(
                            y=1500,
                            line_dash="dash",
                            line_color="rgba(255, 107, 107, 0.4)",
                            annotation_text="Baseline (1500)",
                            annotation_font=dict(color="rgba(255, 107, 107, 0.7)", weight=600)
                        )
                        # Add peak rating marker
                        peak_idx = df_chart['rating'].idxmax()
                        peak_row = df_chart.loc[peak_idx]
                        fig_rating.add_scatter(
                            x=[peak_row['date']],
                            y=[peak_row['rating']],
                            mode='markers',
                            marker=dict(
                                size=16,
                                color=ACCENT_COLORS["warning"],
                                symbol='star',
                                line=dict(width=2, color='#FFD700')
                            ),
                            name='Peak',
                            hovertemplate=f"<b>Peak Rating</b><br>{peak_row['rating']:.0f}<extra></extra>"
                        )
                        st.plotly_chart(fig_rating, use_container_width=True)

                        # --- Daily Rank History Chart ---
                        st.subheader("Daily Rank History")

                        fig_rank = px.line(
                            df_chart,
                            x='date',
                            y='rank',
                            markers=True,
                            labels={'date': 'Date', 'rank': 'Daily Rank'},
                            color_discrete_sequence=[ACCENT_COLORS["info"]]
                        )
                        apply_plotly_style(fig_rank, add_gradient_fill=True)
                        fig_rank.update_traces(
                            marker=dict(size=8, line=dict(width=2, color='rgba(255,255,255,0.3)')),
                            line=dict(width=3),
                            fillcolor='rgba(59, 130, 246, 0.15)',
                        )
                        fig_rank.update_layout(
                            height=280,
                            margin=dict(l=20, r=20, t=30, b=20),
                            showlegend=False,
                            yaxis=dict(autorange="reversed")  # Lower rank is better
                        )
                        # Add average rank line
                        avg_rank_val = df_chart['rank'].mean()
                        fig_rank.add_hline(
                            y=avg_rank_val,
                            line_dash="dash",
                            line_color="rgba(59, 130, 246, 0.6)",
                            annotation_text=f"Avg: {avg_rank_val:.1f}",
                            annotation_font=dict(color="rgba(59, 130, 246, 0.8)", weight=600)
                        )
                        # Add best rank markers for ALL occurrences of best rank
                        best_rank = df_chart['rank'].min()
                        df_best_ranks = df_chart[df_chart['rank'] == best_rank]
                        fig_rank.add_scatter(
                            x=df_best_ranks['date'],
                            y=df_best_ranks['rank'],
                            mode='markers',
                            marker=dict(
                                size=16,
                                color=ACCENT_COLORS["success"],
                                symbol='star',
                                line=dict(width=2, color='#10B981')
                            ),
                            name='Best',
                            hovertemplate=f"<b>Best Rank</b><br>#{int(best_rank)}<extra></extra>"
                        )
                        st.plotly_chart(fig_rank, use_container_width=True)

                        # --- Game History Table ---
                        st.subheader("Game History")

                        display_cols = ['date', 'rank', 'score', 'rating', 'rating_change']
                        if has_active_rank:
                            display_cols.append('active_rank')
                        display_cols.extend(['games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency'])

                        df_table = df_player_played.sort_values('date', ascending=False)

                        column_config = {
                            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                            "rank": st.column_config.NumberColumn("Daily Rank", format="%d"),
                            "score": st.column_config.NumberColumn("Score", format="%d"),
                            "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                            "rating_change": st.column_config.NumberColumn("Rating Change", format="%+.1f"),
                            "games_played": st.column_config.NumberColumn("Games", format="%d"),
                            "wins": st.column_config.NumberColumn("Wins", format="%d"),
                            "win_rate": st.column_config.NumberColumn("Win %", format="%.1f"),
                            "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                            "top_10s_rate": st.column_config.NumberColumn("Top 10 %", format="%.1f"),
                            "avg_daily_rank": st.column_config.NumberColumn("Avg Rank", format="%.1f"),
                            "last_7": st.column_config.NumberColumn("Recent", format="%.1f", help="Average rank over last 7 games"),
                            "consistency": st.column_config.NumberColumn("Consistency", format="%.1f", help="Standard deviation of ranks over last 14 games")
                        }
                        if has_active_rank:
                            column_config["active_rank"] = st.column_config.NumberColumn("Elo Rank", format="%d")

                        st.dataframe(
                            df_table[display_cols],
                            use_container_width=True,
                            hide_index=True,
                            column_config=column_config
                        )
                    else:
                        st.info(f"No game history found for {selected_player}.")
                else:
                    st.info(f"No history data available for {selected_player}.")
            else:
                st.info("Select a player to view their profile and history.")
        else:
            st.warning("History data not available.")

    # --- Tab 5: Top 10 History ---
    with tab5:

        if df_history is not None and 'active_rank' in df_history.columns:
            # Use pre-computed active_rank from history data
            # Filter to players with an active_rank (only active players have ranks)
            df_history_active = df_history[df_history['active_rank'].notna()].copy()

            # Filter to top 10 active ranks only
            df_top10 = df_history_active[df_history_active['active_rank'] <= 10].copy()

            # Elo #1 evolution chart - shows who held #1 over time (all history)
            df_rank1 = df_top10[df_top10['active_rank'] == 1].copy()
            df_rank1 = df_rank1.sort_values('date')

            st.subheader("Elo Rank #1 History")

            if not df_rank1.empty:
                # Get all unique players who held #1
                all_rank1_players = df_rank1['player_name'].unique().tolist()

                fig_rank1 = px.line(
                    df_rank1,
                    x='date',
                    y='player_name',
                    markers=True,
                    labels={'date': 'Date', 'player_name': 'Elo #1'},
                    category_orders={'player_name': all_rank1_players},
                    color_discrete_sequence=[ACCENT_COLORS["primary"]]
                )
                fig_rank1.update_traces(
                    line=dict(shape='hv', color=ACCENT_COLORS["primary"]),  # Step line
                    marker=dict(size=8, color=ACCENT_COLORS["primary"]),
                    hovertemplate='%{y}<br>%{x|%Y-%m-%d}<extra></extra>'
                )
                apply_plotly_style(fig_rank1)
                # Enhanced marker styling with glow effect
                fig_rank1.update_traces(
                    marker=dict(
                        size=10,
                        line=dict(width=2, color='rgba(255, 255, 255, 0.4)'),
                        symbol='diamond',
                    ),
                )
                colors = get_theme_colors()
                fig_rank1.update_layout(
                    height=max(200, len(all_rank1_players) * 25),  # Dynamic height based on player count
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=False,
                    yaxis_title=None,
                    xaxis_title=None,
                    yaxis=dict(
                        tickmode='array',
                        tickvals=all_rank1_players,
                        ticktext=all_rank1_players,
                        tickfont=dict(color=colors["text_secondary"], weight=600)
                    )
                )
                st.plotly_chart(fig_rank1, use_container_width=True)

            # Pivot to get ranks as columns for table
            df_pivot = df_top10.pivot(
                index='date',
                columns='active_rank',
                values='player_name'
            ).reset_index()

            # Rename columns to indicate Elo rankings
            df_pivot.columns = ['Date'] + [f'Elo #{int(i)}' for i in df_pivot.columns[1:]]

            # Sort by date descending (most recent first)
            df_pivot = df_pivot.sort_values('Date', ascending=False)

            # Build column config dynamically
            column_config = {
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD")
            }
            for i in range(1, 11):
                col_name = f'Elo #{i}'
                if col_name in df_pivot.columns:
                    column_config[col_name] = st.column_config.TextColumn(col_name)

            st.dataframe(
                df_pivot,
                use_container_width=True,
                hide_index=True,
                column_config=column_config
            )
        else:
            st.warning("Active rank history data not available.")

    # --- Tab 2: Daily Duels ---
    with tab2:

        if df_history is not None:
            col_p1, col_p2 = st.columns(2)

            with col_p1:
                player1 = st.selectbox(
                    "Select Player 1",
                    options=players_by_rating,
                    index=None,
                    placeholder="Choose Player 1...",
                    key="duel_player1"
                )

            with col_p2:
                player2 = st.selectbox(
                    "Select Player 2",
                    options=players_by_rating,
                    index=None,
                    placeholder="Choose Player 2...",
                    key="duel_player2"
                )

            if player1 and player2:
                if player1 == player2:
                    st.warning("Please select two different players.")
                else:
                    # Get history for both players
                    df_p1 = df_history[df_history['player_name'] == player1].copy()
                    df_p2 = df_history[df_history['player_name'] == player2].copy()

                    # Filter to days when both players actually played (have scores)
                    df_p1_played = df_p1[df_p1['score'].notna()].copy()
                    df_p2_played = df_p2[df_p2['score'].notna()].copy()

                    # Find common dates where both played
                    common_dates = set(df_p1_played['date'].dt.date) & set(df_p2_played['date'].dt.date)

                    if not common_dates:
                        st.info(f"No common game days found between {player1} and {player2}.")
                    else:
                        # Elo system constants (matching elo_ranking.py)
                        K_FACTOR = 180
                        K_NORMALIZED = K_FACTOR / 29  # Per pairwise comparison
                        DYNAMIC_K_NEW_GAMES = 10
                        DYNAMIC_K_ESTABLISHED_GAMES = 30
                        DYNAMIC_K_NEW_MULT = 1.5
                        DYNAMIC_K_PROV_MULT = 1.2
                        LOSS_AMP_MAX = 1.5

                        def get_dynamic_k(games_played):
                            """Calculate K-factor based on games played"""
                            if games_played < DYNAMIC_K_NEW_GAMES:
                                return K_NORMALIZED * DYNAMIC_K_NEW_MULT
                            elif games_played < DYNAMIC_K_ESTABLISHED_GAMES:
                                return K_NORMALIZED * DYNAMIC_K_PROV_MULT
                            return K_NORMALIZED

                        def calc_elo_exchange(p1_elo, p2_elo, p1_won, p1_games, p1_uncertainty, score_weight=1.0):
                            """
                            Calculate Elo exchange for P1 from a single matchup with P2.
                            Returns positive if P1 gained, negative if P1 lost.
                            """
                            # Expected score for P1
                            expected = 1 / (1 + 10 ** ((p2_elo - p1_elo) / 400))
                            actual = 1.0 if p1_won else 0.0

                            # Get P1's K-factor
                            k = get_dynamic_k(p1_games)

                            # Apply loss amplification if P1 lost
                            if not p1_won and p1_uncertainty is not None:
                                loss_amp = 1 + (LOSS_AMP_MAX - 1) * p1_uncertainty
                                k *= loss_amp

                            # Apply score weighting
                            k *= score_weight

                            return k * (actual - expected)

                        # Build comparison dataframe
                        duel_rows = []
                        p1_wins = 0
                        p2_wins = 0
                        p1_higher_elo_wins = 0
                        p2_higher_elo_wins = 0
                        total_games = 0
                        total_p1_elo = 0.0
                        total_p2_elo = 0.0

                        for date in sorted(common_dates, reverse=True):
                            p1_data = df_p1_played[df_p1_played['date'].dt.date == date].iloc[0]
                            p2_data = df_p2_played[df_p2_played['date'].dt.date == date].iloc[0]

                            # Determine winner (lower rank is better)
                            p1_rank = p1_data['rank']
                            p2_rank = p2_data['rank']
                            winner = None
                            p1_won = False
                            if p1_rank < p2_rank:
                                winner = player1
                                p1_wins += 1
                                p1_won = True
                            elif p2_rank < p1_rank:
                                winner = player2
                                p2_wins += 1

                            # Track Elo prediction accuracy
                            p1_elo = p1_data['rating']
                            p2_elo = p2_data['rating']
                            if winner:
                                total_games += 1
                                if p1_elo > p2_elo and winner == player1:
                                    p1_higher_elo_wins += 1
                                elif p2_elo > p1_elo and winner == player2:
                                    p2_higher_elo_wins += 1

                            # Calculate Elo exchange for both players
                            p1_elo_change = 0.0
                            p2_elo_change = 0.0
                            if winner:  # Only if there's a winner (not a tie)
                                p1_games = p1_data['games_played'] if 'games_played' in p1_data else 30
                                p2_games = p2_data['games_played'] if 'games_played' in p2_data else 30
                                p1_uncertainty = p1_data['uncertainty'] if 'uncertainty' in p1_data else 0.0
                                p2_uncertainty = p2_data['uncertainty'] if 'uncertainty' in p2_data else 0.0

                                # Calculate score weight (ratio-based) - winner's score / loser's score
                                p1_score = p1_data['score']
                                p2_score = p2_data['score']
                                if p1_won and p2_score > 0:
                                    ratio = p1_score / p2_score
                                    log_ratio = math.log2(max(ratio, 1.0))
                                    score_weight = 0.5 + 0.5 * min(log_ratio / math.log2(10), 1.0)
                                elif not p1_won and p1_score > 0:
                                    ratio = p2_score / p1_score
                                    log_ratio = math.log2(max(ratio, 1.0))
                                    score_weight = 0.5 + 0.5 * min(log_ratio / math.log2(10), 1.0)
                                else:
                                    score_weight = 1.0

                                # P1's perspective
                                p1_elo_change = calc_elo_exchange(
                                    p1_elo, p2_elo, p1_won, p1_games, p1_uncertainty, score_weight
                                )
                                # P2's perspective (opposite outcome)
                                p2_elo_change = calc_elo_exchange(
                                    p2_elo, p1_elo, not p1_won, p2_games, p2_uncertainty, score_weight
                                )

                                total_p1_elo += p1_elo_change
                                total_p2_elo += p2_elo_change

                            row = {
                                'Date': date,
                                'Winner': winner if winner else "Tie",
                                f'{player1} Daily Rank': int(p1_rank),
                                f'{player2} Daily Rank': int(p2_rank),
                                f'{player1} Score': int(p1_data['score']),
                                f'{player2} Score': int(p2_data['score']),
                            }

                            # Add active rank if available
                            if 'active_rank' in df_p1_played.columns:
                                p1_active = p1_data['active_rank']
                                p2_active = p2_data['active_rank']
                                row[f'{player1} Active Rank'] = int(p1_active) if pd.notna(p1_active) else None
                                row[f'{player2} Active Rank'] = int(p2_active) if pd.notna(p2_active) else None

                            row[f'{player1} Elo'] = round(p1_elo, 1)
                            row[f'{player2} Elo'] = round(p2_elo, 1)

                            duel_rows.append(row)

                        df_duel = pd.DataFrame(duel_rows)

                        # Summary statistics
                        st.subheader("Head-to-Head Summary")
                        ties = len(common_dates) - p1_wins - p2_wins

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric("Matchups", len(common_dates))
                        with col2:
                            st.metric(f"{player1} Wins", p1_wins)
                        with col3:
                            st.metric(f"{player2} Wins", p2_wins)
                        with col4:
                            st.metric("Ties", ties)

                        # First and Last Encounter
                        sorted_dates = sorted(common_dates)
                        first_date = sorted_dates[0]
                        last_date = sorted_dates[-1]

                        # Get first encounter winner
                        first_p1 = df_p1_played[df_p1_played['date'].dt.date == first_date].iloc[0]
                        first_p2 = df_p2_played[df_p2_played['date'].dt.date == first_date].iloc[0]
                        if first_p1['rank'] < first_p2['rank']:
                            first_winner = player1
                        elif first_p2['rank'] < first_p1['rank']:
                            first_winner = player2
                        else:
                            first_winner = "Tie"

                        # Get last encounter winner
                        last_p1 = df_p1_played[df_p1_played['date'].dt.date == last_date].iloc[0]
                        last_p2 = df_p2_played[df_p2_played['date'].dt.date == last_date].iloc[0]
                        if last_p1['rank'] < last_p2['rank']:
                            last_winner = player1
                        elif last_p2['rank'] < last_p1['rank']:
                            last_winner = player2
                        else:
                            last_winner = "Tie"

                        # Display encounter badges (theme-aware using CSS variables)
                        col_first, col_last = st.columns(2)
                        with col_first:
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(59,130,246,0.2) 100%);
                                        border: 1px solid {ACCENT_COLORS['info']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; margin-bottom: 0.25rem;">First Encounter</div>
                                <div style="font-size: 1.25rem; font-weight: 700;">{first_date.strftime('%Y-%m-%d')}</div>
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['info']};">Winner: {first_winner}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_last:
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.2) 100%);
                                        border: 1px solid {ACCENT_COLORS['primary']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; margin-bottom: 0.25rem;">Last Encounter</div>
                                <div style="font-size: 1.25rem; font-weight: 700;">{last_date.strftime('%Y-%m-%d')}</div>
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['primary']};">Winner: {last_winner}</div>
                            </div>
                            """, unsafe_allow_html=True)

                        st.markdown("")  # Spacer

                        # Comparative Elo Graph - both players' ratings over time
                        st.subheader("Elo Rating Comparison")

                        # Get full history for both players (all days they played, not just common)
                        df_p1_chart = df_p1_played[['date', 'rating']].copy()
                        df_p1_chart['player'] = player1
                        df_p2_chart = df_p2_played[['date', 'rating']].copy()
                        df_p2_chart['player'] = player2

                        df_elo_compare = pd.concat([df_p1_chart, df_p2_chart]).sort_values('date')

                        fig_elo = px.line(
                            df_elo_compare,
                            x='date',
                            y='rating',
                            color='player',
                            markers=True,
                            labels={'date': 'Date', 'rating': 'Elo Rating', 'player': 'Player'},
                            color_discrete_map={player1: ACCENT_COLORS["info"], player2: ACCENT_COLORS["warning"]}
                        )
                        fig_elo.update_traces(
                            hovertemplate='%{fullData.name}: %{y:.0f}<extra></extra>',
                            marker=dict(
                                size=10,
                                line=dict(width=2, color='rgba(255, 255, 255, 0.3)'),
                            ),
                            line=dict(width=3),
                        )
                        apply_plotly_style(fig_elo)
                        colors = get_theme_colors()
                        fig_elo.update_layout(
                            hovermode='x unified',
                            height=350,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(color=colors["text_primary"], weight=600),
                            ),
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        fig_elo.add_hline(
                            y=1500,
                            line_dash="dash",
                            line_color=colors["text_muted"],
                            annotation_text="Baseline",
                            annotation_font=dict(color=colors["text_muted"], weight=600)
                        )
                        st.plotly_chart(fig_elo, use_container_width=True)

                        # Score Timeline on Mutual Games
                        st.subheader("Score Timeline (Mutual Games)")

                        # Build score data for mutual games only
                        score_data = []
                        for date in sorted(common_dates):
                            p1_data = df_p1_played[df_p1_played['date'].dt.date == date].iloc[0]
                            p2_data = df_p2_played[df_p2_played['date'].dt.date == date].iloc[0]
                            score_data.append({
                                'date': date,
                                'player': player1,
                                'score': p1_data['score']
                            })
                            score_data.append({
                                'date': date,
                                'player': player2,
                                'score': p2_data['score']
                            })

                        df_score_timeline = pd.DataFrame(score_data)

                        fig_score = px.line(
                            df_score_timeline,
                            x='date',
                            y='score',
                            color='player',
                            markers=True,
                            labels={'date': 'Date', 'score': 'Score', 'player': 'Player'},
                            color_discrete_map={player1: ACCENT_COLORS["info"], player2: ACCENT_COLORS["warning"]}
                        )
                        fig_score.update_traces(
                            hovertemplate='%{fullData.name}: %{y:,.0f}<extra></extra>',
                            marker=dict(
                                size=10,
                                line=dict(width=2, color='rgba(255, 255, 255, 0.3)'),
                            ),
                            line=dict(width=3),
                        )
                        apply_plotly_style(fig_score)
                        colors = get_theme_colors()
                        fig_score.update_layout(
                            hovermode='x unified',
                            height=300,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(color=colors["text_primary"], weight=600),
                            ),
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        st.plotly_chart(fig_score, use_container_width=True)

                        # Win distribution pie chart
                        if len(common_dates) > 0:
                            pie_data = pd.DataFrame({
                                'Result': [player1, player2, 'Tie'],
                                'Count': [p1_wins, p2_wins, ties]
                            })
                            # Filter out zero values
                            pie_data = pie_data[pie_data['Count'] > 0]

                            # Use design system colors (colorblind-safe)
                            fig_pie = px.pie(
                                pie_data,
                                values='Count',
                                names='Result',
                                hole=0.4,
                                color_discrete_sequence=[ACCENT_COLORS["info"], ACCENT_COLORS["warning"], ACCENT_COLORS["success"]]
                            )
                            fig_pie.update_traces(
                                textposition='inside',
                                textinfo='percent+value',
                                textfont=dict(color='white', size=14),
                                hovertemplate='%{label}: %{value} wins<extra></extra>'
                            )
                            apply_plotly_style(fig_pie)
                            colors = get_theme_colors()
                            fig_pie.update_layout(
                                height=250,
                                margin=dict(l=20, r=20, t=20, b=20),
                                showlegend=True,
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=-0.1,
                                    xanchor="center",
                                    x=0.5,
                                    font=dict(size=12, color=colors["text_primary"], weight=600)
                                )
                            )
                            st.plotly_chart(fig_pie, use_container_width=True)

                        # Display the duel table
                        st.subheader("Game-by-Game Comparison")

                        # Build column config
                        column_config = {
                            "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                            "Winner": st.column_config.TextColumn("Winner"),
                            f"{player1} Daily Rank": st.column_config.NumberColumn(f"{player1} Daily Rank", format="%d"),
                            f"{player2} Daily Rank": st.column_config.NumberColumn(f"{player2} Daily Rank", format="%d"),
                            f"{player1} Score": st.column_config.NumberColumn(f"{player1} Score", format="%d"),
                            f"{player2} Score": st.column_config.NumberColumn(f"{player2} Score", format="%d"),
                            f"{player1} Active Rank": st.column_config.NumberColumn(f"{player1} Elo Rank", format="%d"),
                            f"{player2} Active Rank": st.column_config.NumberColumn(f"{player2} Elo Rank", format="%d"),
                            f"{player1} Elo": st.column_config.NumberColumn(f"{player1} Elo", format="%.1f"),
                            f"{player2} Elo": st.column_config.NumberColumn(f"{player2} Elo", format="%.1f"),
                        }

                        st.dataframe(
                            df_duel,
                            use_container_width=True,
                            hide_index=True,
                            column_config=column_config
                        )
            else:
                st.info("Select two players to compare their head-to-head performance.")
        else:
            st.warning("History data not available.")

    # --- Tab 6: FAQ / Glossary ---
    with tab6:
        st.subheader("Frequently Asked Questions")

        with st.expander("What is Elo rating?", expanded=True):
            st.markdown("""
            **Elo** is a rating system originally designed for chess that measures relative skill levels.
            Here, I use a modified pairwise Elo system that compares players based on their daily leaderboard performance.

            - **Starting Rating**: All players begin at **1500** (the baseline/median)
            - **Rating Range**: From **1000** (floor) to **3000** (theoretical ceiling)
            - **How it works**: When you finish higher than another player on the daily leaderboard, you "win" against them. Your rating increases, theirs decreases. The amount depends on the rating difference and score margin.
            """)

        with st.expander("What do the ratings mean?"):
            st.markdown("""
            Ratings roughly correspond to expected performance levels:

            | Rating | Tier | Typical Rank |
            |--------|------|--------------|
            | **2800+** | Elite | Top 1 |
            | **2500-2800** | Expert | Top 5 |
            | **2000-2500** | Strong | Top 10 |
            | **1500** | Average | ~Rank 15-20 |
            | **1200-1500** | Below Average | Rank 20-25 |
            | **1000-1200** | Beginner | Rank 25-30 |

            *These are approximate guidelines based on current data. The system reflects actual skill gaps, so exact thresholds may shift as the player pool evolves.*

            **Rating Milestones:**
            - **2800**: Elite tier - only 0-2 players typically reach this level
            - **2900**: Legendary - requires exceptional sustained dominance
            - **3000**: Theoretical maximum (asymptotic, effectively unreachable)
            """)

        with st.expander("How are rankings calculated?"):
            st.markdown("""
            Each day, all players on the leaderboard are compared pairwise:
            1. Player A (rank 5) vs Player B (rank 12) → Player A "wins"
            2. Rating changes are calculated using a modified Elo formula
            3. Score margins matter - dominating by 2x score gives more weight than a narrow win
            4. Players with more games have more stable ratings (dynamic K-factor)

            **Rating Compression**: Raw Elo scores are compressed using a hybrid system:
            - Below 2700: Gentle logarithmic scaling (diminishing returns)
            - Above 2700: Hyperbolic tangent compression toward the 3000 ceiling
            - This prevents runaway ratings while preserving meaningful differences

            **Activity Gating**: Only players active in the last 7 days with at least 7 games appear in the main rankings. Inactive players don't appear but their ratings are preserved.
            """)

        with st.expander("Why did my rating change so much/little?"):
            st.markdown("""
            Several factors affect rating changes:
            - **Opponent ratings**: Beating higher-rated players = bigger gains
            - **Score margin**: Dominating performances (2x, 3x score) give more weight
            - **Games played**: New players (<10 games) have larger swings to find their true rating
            - **Your rating level**: Higher ratings compress more, so gains shrink as you climb
            - **Number of opponents**: Placing #1 means you beat 29 opponents, #30 means you beat none

            **Why gains shrink at high ratings:**
            The system uses rating compression to create meaningful tiers. A player at 2700 needs to perform significantly better than average to gain points, while a player at 1500 can climb more easily with good performances.
            """)

        st.markdown("---")
        st.subheader("System Design Philosophy")

        with st.expander("Why use Elo instead of other rating systems?"):
            st.markdown("""
            I considered several rating systems before settling on a modified Elo approach:

            | System | Pros | Why I didn't use it |
            |--------|------|---------------------|
            | **Glicko/Glicko-2** | Tracks rating uncertainty | Designed for 1v1 matches, not 30-player daily competitions |
            | **TrueSkill** | Handles team games well | Overly complex for this use case; designed for Xbox matchmaking |
            | **Simple averages** | Easy to understand | Doesn't account for opponent strength or improvement over time |
            | **ELO** | Battle-tested, intuitive | Perfect fit with pairwise adaptation |

            **Why Elo works here:**
            - Chess proved that Elo accurately ranks players over time through repeated competition
            - My pairwise adaptation treats each daily leaderboard as 435 simultaneous "matches" (30 players = 30×29/2 pairs)
            - The system is self-correcting: beat strong players, gain more; lose to weak players, lose more
            - It's intuitive: everyone understands "higher number = better"

            The key insight from chess is that **relative performance over many games** reveals true skill better than any single result.
            """)

        with st.expander("How do you know the ratings are accurate?"):
            st.markdown("""
            Several indicators suggest the ratings reflect actual skill:

            **1. Predictive Power**
            Higher-rated players consistently outperform lower-rated players when they compete on the same day. If ratings were random, this wouldn't happen.

            **2. Stability with Volume**
            New players have volatile ratings that stabilize as they play more. This matches how you'd expect skill measurement to work - more data = more certainty.

            **3. Intuitive Results**
            The rankings align with community perception. Players known for consistent dominance have high ratings; casual players cluster around the median.

            **4. Natural Distribution**
            The rating distribution resembles a bell curve centered at 1500, with long tails for exceptional and struggling players - exactly what you'd expect from a skill-based metric.

            **5. Score Margin Correlation**
            Players who win by larger margins (2x, 3x score) tend to have higher ratings than those who barely edge out opponents. The system captures dominance, not just wins.

            **The chess parallel:** Chess ratings have been validated over 60+ years of competitive play. My adaptation applies the same mathematical principles to daily leaderboard competition.
            """)

        with st.expander("Why pairwise comparisons instead of just using daily rank?"):
            st.markdown("""
            Using raw daily rank (1st, 5th, 20th) would be simpler, but it misses crucial information:

            **Problem with raw ranks:**
            - Finishing 1st against 29 weak players = same as 1st against 29 strong players
            - A rank of 5th tells you nothing about who you beat or lost to
            - No way to compare across different days with different player pools

            **Why pairwise works better:**
            Each day, I ask: "Did Player A beat Player B?" This creates a web of relative comparisons:
            - Beat a 2500-rated player? Big gain.
            - Lose to a 1200-rated player? Big loss.
            - The gains and losses depend on *who* you competed against.

            **Inspiration from competitive gaming:**
            This is how chess, League of Legends, and other ranked systems work. You don't just get points for winning - you get points based on the *strength of your opponents*.

            The result: a rating that reflects not just how often you win, but *who* you beat to get there.
            """)

        with st.expander("How do you handle only seeing the top 30 each day?"):
            st.markdown("""
            This is one of the most important constraints that shaped my system design.

            **The limitation:**
            I only see the top 30 players each day. Players ranked 31st or lower are invisible - I don't know their scores, their identities, or even how many of them there are.

            **Why this is actually fine for Elo:**
            The pairwise system only compares players *who both appear on the same day*. If you're in the top 30, you get compared to the other 29 players. If you're not, you simply don't participate that day.

            **Key implications:**
            - **No penalty for missing days**: If you don't appear, your rating stays frozen - you don't lose points
            - **Appearing matters**: To gain or lose rating, you must show up in the top 30
            - **Self-selecting competition**: The leaderboard naturally captures the most active/competitive players
            - **Bottom of top 30 is meaningful**: Rank 30 means you beat no one that day and lost to 29 players

            **What I *can't* measure:**
            - Players who never crack the top 30
            - How close rank 31 was to rank 30
            - The "true" skill of players who rarely appear

            **The philosophical tradeoff:**
            I chose to measure *competitive performance* rather than *total player skill*. If you want a rating, you need to compete. This mirrors chess tournaments - you can't get a rating by staying home.

            The system rewards showing up and performing, which aligns with what a "leaderboard ranking" should capture.
            """)

        with st.expander("What's the deal with rating compression?"):
            st.markdown("""
            Without compression, ratings would diverge infinitely. A dominant player could theoretically reach 5000, 10000, or higher. This creates problems:

            **Why I compress:**
            - **Meaningful tiers**: 2800 means "elite" - not just "higher than 2700"
            - **Visual clarity**: Ratings fit on a readable 1000-3000 scale
            - **Diminishing returns**: The best player can't just run away from the field forever

            **The chess parallel:**
            Even Magnus Carlsen, the strongest chess player in history, peaked around 2882. The system naturally resists extreme outliers because:
            - There are fewer players to beat at the top
            - Beating weaker players yields smaller gains
            - Losing to anyone costs more when you're highly rated

            My compression applies similar principles mathematically, creating a world where:
            - **2800+** is genuinely elite (like 2700+ in chess)
            - **2900** is legendary (like 2800+ in chess)
            - **3000** is the asymptotic ceiling (like the theoretical limits of human chess ability)

            This makes ratings *meaningful* rather than just *big numbers*.
            """)

        st.markdown("---")
        st.subheader("Glossary of Terms")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("""
            | Term | Definition |
            |------|------------|
            | **Ranked** | Players in the main leaderboard (active + enough games) |
            | **Unranked** | Players not in main leaderboard (<7 games or inactive >7 days) |
            | **Elo Rank** | Your position among ranked players by Elo rating |
            | **Rating** | Your compressed Elo score (higher = better) |
            | **Raw Rating** | Your uncompressed Elo score (used internally) |
            | **Games** | Total days you've appeared on the leaderboard |
            | **Confidence** | How reliable your rating is (based on games played) |
            """)

        with col2:
            st.markdown("""
            | Term | Definition |
            |------|------------|
            | **Avg Rank** | Your average daily leaderboard position |
            | **Recent** | Average daily rank over your last 7 games |
            | **Consistency** | Std deviation of ranks (lower = more consistent) |
            | **Daily Rank** | Your position on a specific day's leaderboard |
            | **Rating Change** | How much your Elo changed that day |
            | **Baseline** | The starting/median rating of 1500 |
            | **Compression** | System that maps raw ratings to display ratings |
            """)

        st.markdown("---")
        st.subheader("Tips for Improving Your Rating")

        st.markdown("""
        1. **Play consistently** - Regular appearances build rating stability and keep you ranked
        2. **Aim for top placements** - Even if you can't win, beating more players helps
        3. **Dominate when you can** - Score margins matter; a 2x score gives more weight than a narrow win
        4. **Compete against strong players** - Beating high-rated players gives bigger gains
        5. **Check your trends** - Use Player Tracker to see if you're improving over time
        6. **Stay active** - Players inactive for 7+ days become unranked (but keep their rating)
        """)


if __name__ == "__main__":
    main()
