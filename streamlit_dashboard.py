import math
import base64
import html

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="DFTL Ranking Dashboard",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed"
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

# --- Leaderboard Flourishes ---
# Icons and decorations for top players
RANK_ICONS = {
    1: {"icon": "👑", "color": "#FFD700", "label": "Champion"},
    2: {"icon": "🥈", "color": "#C0C0C0", "label": "Runner-up"},
    3: {"icon": "🥉", "color": "#CD7F32", "label": "Third Place"},
}

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


def generate_ranking_cards(df):
    """
    Generate HTML cards for the rankings display.
    Responsive: 4 columns on mobile, 8 columns on desktop.
    Uses Streamlit CSS variables for automatic theme support.
    """
    if df.empty:
        return "<p>No data available</p>"

    # Theme-adaptive styles using Streamlit CSS variables
    # Base card styling (border, radius, shadow) - background varies by active status
    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:0.875rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);"
    # Active player: coral accent gradient
    active_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.15) 100%);"
    # Inactive player (N/R): muted gray gradient to visually distinguish
    inactive_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(128,128,128,0.12) 100%);"

    # Header now uses CSS classes for responsive layout (see CSS: .card-header, .card-rank, etc.)
    # Status label style for inactive players (blue to match N/R and rating)
    inactive_blue = "#6B9AFF"
    status_label_style = f"font-size:0.65rem;font-weight:400;margin-top:0.15rem;color:{inactive_blue};"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.65rem;text-transform:uppercase;opacity:0.75;color:var(--text-color);"
    value_style = "font-size:0.9rem;font-weight:600;color:var(--text-color);"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    cards = []
    for _, row in df.iterrows():
        rank = row.get('active_rank')
        is_inactive = pd.isna(rank)

        # Choose card background based on active status
        card_style = (inactive_bg if is_inactive else active_bg) + card_base

        # Rank display - centered, emojis only for podium (1-3), # for others
        if is_inactive:
            # N/R for unranked players - blue to visually distinguish from ranked players
            rank_html = f'<span style="color:{inactive_blue};">N/R</span>'
        else:
            rank_int = int(rank)
            if rank_int in RANK_ICONS:
                # Podium ranks (1-3): show only emoji, centered
                info = RANK_ICONS[rank_int]
                rank_html = f'<span style="color:{info["color"]};font-size:1.2rem;">{info["icon"]}</span>'
            else:
                # Ranks 4+: show #N in coral (same as rating for visual link)
                rank_html = f'<span style="color:#FF6B6B;">#{rank_int}</span>'

        # Player name with status indicator (stacked vertically for small viewports)
        name = html.escape(str(row.get('player_name', 'Unknown')))
        games_played = row.get('games_played', 0)
        games_count = int(games_played) if pd.notna(games_played) else 0

        if is_inactive:
            # WCAG compliant opacity (0.7 provides ~4.5:1 contrast)
            # Status label on separate line to avoid cutoff on small screens
            if games_count < 7:
                status_text = "(not enough games)"
            else:
                status_text = "(inactive)"
            name_html = f'<span class="card-name-text">{name}</span><span style="{status_label_style}">{status_text}</span>'
        else:
            name_html = f'<span class="card-name-text">{name}</span>'

        # Stats
        rating = safe_str(row.get('rating'), "{:.1f}")
        games = safe_str(row.get('games_played'))
        wins = safe_str(row.get('wins'))
        win_rate = safe_str(row.get('win_rate'), "{:.1f}") + "%" if pd.notna(row.get('win_rate')) else "—"
        top10 = safe_str(row.get('top_10s'))
        top10_rate = safe_str(row.get('top_10s_rate'), "{:.1f}") + "%" if pd.notna(row.get('top_10s_rate')) else "—"
        avg_r = safe_str(row.get('avg_daily_rank'), "{:.1f}")
        last7 = safe_str(row.get('last_7'), "{:.1f}")
        consist = safe_str(row.get('consistency'), "{:.1f}")

        # Build card with CSS-class-based responsive header
        # Rating class: 'active' (coral) for ranked, 'inactive' (muted) for unranked
        rating_class = "inactive" if is_inactive else "active"
        card = f'<div style="{card_style}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name">{name_html}</div><div class="card-rating {rating_class}">{rating}</div></div><div class="stats-grid"><div style="{stat_layout}"><span style="{label_style}">Games</span><span style="{value_style}">{games}</span></div><div style="{stat_layout}"><span style="{label_style}">Wins</span><span style="{value_style}">{wins}</span></div><div style="{stat_layout}"><span style="{label_style}">Win%</span><span style="{value_style}">{win_rate}</span></div><div style="{stat_layout}"><span style="{label_style}">Top10</span><span style="{value_style}">{top10}</span></div><div style="{stat_layout}"><span style="{label_style}">Top10%</span><span style="{value_style}">{top10_rate}</span></div><div style="{stat_layout}"><span style="{label_style}">Avg Rank</span><span style="{value_style}">{avg_r}</span></div><div style="{stat_layout}"><span style="{label_style}">7-Game Avg</span><span style="{value_style}">{last7}</span></div><div style="{stat_layout}"><span style="{label_style}">Stability</span><span style="{value_style}">{consist}</span></div></div></div>'
        cards.append(card)

    return "".join(cards)


def generate_leaderboard_cards(df, has_rating=True, has_active_rank=True):
    """
    Generate HTML cards for the daily leaderboard display (Tab 4).
    Shows: Daily Rank, Player Name, Score, Rating (if available), Rating Change, Elo Rank.
    """
    if df.empty:
        return "<p>No data available</p>"

    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:0.875rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.15) 100%);"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.65rem;text-transform:uppercase;opacity:0.75;color:var(--text-color);"
    value_style = "font-size:0.9rem;font-weight:600;color:var(--text-color);"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    cards = []
    for _, row in df.iterrows():
        rank = row.get('rank')
        rank_int = int(rank) if pd.notna(rank) else 0

        # Rank display with podium icons
        if rank_int in RANK_ICONS:
            info = RANK_ICONS[rank_int]
            rank_html = f'<span style="color:{info["color"]};font-size:1.2rem;">{info["icon"]}</span>'
        else:
            rank_html = f'<span style="color:#FF6B6B;">#{rank_int}</span>'

        name = html.escape(str(row.get('player_name', 'Unknown')))
        score = safe_str(row.get('score'))

        # Build stats grid based on available columns
        stats_html = f'<div style="{stat_layout}"><span style="{label_style}">Score</span><span style="{value_style}">{score}</span></div>'

        if has_rating and 'rating' in row.index:
            rating = safe_str(row.get('rating'), "{:.1f}")
            stats_html += f'<div style="{stat_layout}"><span style="{label_style}">Rating</span><span style="{value_style}">{rating}</span></div>'

            if 'rating_change' in row.index:
                change = row.get('rating_change')
                if pd.notna(change):
                    change_color = "#10B981" if change >= 0 else "#EF4444"
                    change_str = f"+{change:.1f}" if change >= 0 else f"{change:.1f}"
                    stats_html += f'<div style="{stat_layout}"><span style="{label_style}">Change</span><span style="{value_style};color:{change_color};">{change_str}</span></div>'

        if has_active_rank and 'active_rank' in row.index:
            elo_rank = row.get('active_rank')
            elo_rank_str = f"#{int(elo_rank)}" if pd.notna(elo_rank) else "N/R"
            elo_color = "#FF6B6B" if pd.notna(elo_rank) else "#6B9AFF"
            stats_html += f'<div style="{stat_layout}"><span style="{label_style}">Elo Rank</span><span style="{value_style};color:{elo_color};">{elo_rank_str}</span></div>'

        card = f'<div style="{card_base}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name"><span class="card-name-text">{name}</span></div><div class="card-rating active">{score}</div></div><div class="stats-grid" style="grid-template-columns:repeat(4, 1fr);">{stats_html}</div></div>'
        cards.append(card)

    return "".join(cards)


def generate_game_history_cards(df, has_active_rank=True):
    """
    Generate HTML cards for player game history display (Tab 3).
    Shows: Date, Daily Rank, Score, Rating, Rating Change, cumulative stats.
    """
    if df.empty:
        return "<p>No data available</p>"

    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:0.875rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(59,130,246,0.12) 100%);"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.65rem;text-transform:uppercase;opacity:0.75;color:var(--text-color);"
    value_style = "font-size:0.9rem;font-weight:600;color:var(--text-color);"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    cards = []
    for _, row in df.iterrows():
        # Date as header
        date_val = row.get('date')
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)[:10]

        rank = row.get('rank')
        rank_int = int(rank) if pd.notna(rank) else 0

        # Rank display
        if rank_int in RANK_ICONS:
            info = RANK_ICONS[rank_int]
            rank_html = f'<span style="color:{info["color"]};font-size:1.1rem;">{info["icon"]} #{rank_int}</span>'
        else:
            rank_html = f'<span style="color:#3B82F6;">#{rank_int}</span>'

        score = safe_str(row.get('score'))
        rating = safe_str(row.get('rating'), "{:.1f}")

        # Rating change with color
        change = row.get('rating_change')
        if pd.notna(change):
            change_color = "#10B981" if change >= 0 else "#EF4444"
            change_str = f"+{change:.1f}" if change >= 0 else f"{change:.1f}"
        else:
            change_color = "var(--text-color)"
            change_str = "—"

        # Build stats
        stats_html = f'''
        <div style="{stat_layout}"><span style="{label_style}">Score</span><span style="{value_style}">{score}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Rating</span><span style="{value_style}">{rating}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Change</span><span style="{value_style};color:{change_color};">{change_str}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Games</span><span style="{value_style}">{safe_str(row.get('games_played'))}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Wins</span><span style="{value_style}">{safe_str(row.get('wins'))}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Win%</span><span style="{value_style}">{safe_str(row.get('win_rate'), "{:.1f}")}%</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Avg Rank</span><span style="{value_style}">{safe_str(row.get('avg_daily_rank'), "{:.1f}")}</span></div>
        <div style="{stat_layout}"><span style="{label_style}">Stability</span><span style="{value_style}">{safe_str(row.get('consistency'), "{:.1f}")}</span></div>
        '''

        card = f'<div style="{card_base}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name"><span class="card-name-text">{date_str}</span></div><div class="card-rating active">{rating}</div></div><div class="stats-grid">{stats_html}</div></div>'
        cards.append(card)

    return "".join(cards)


def generate_duel_cards(df, player1, player2):
    """
    Generate HTML cards for head-to-head comparison (Tab 2).
    Shows: Date, Winner, both players' ranks/scores/elo side-by-side.
    """
    if df.empty:
        return "<p>No data available</p>"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;min-width:60px;"
    label_style = "font-size:0.6rem;text-transform:uppercase;opacity:0.75;color:var(--text-color);"
    value_style = "font-size:0.85rem;font-weight:600;color:var(--text-color);"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    cards = []
    for _, row in df.iterrows():
        date_val = row.get('Date')
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)[:10]

        winner = row.get('Winner', 'Tie')

        # Determine card style based on winner
        if winner == player1:
            card_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(59,130,246,0.2) 100%);"
            winner_color = "#3B82F6"
        elif winner == player2:
            card_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(245,158,11,0.2) 100%);"
            winner_color = "#F59E0B"
        else:
            card_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(128,128,128,0.15) 100%);"
            winner_color = "#888888"

        card_base = f"border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:0.875rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);{card_bg}"

        p1_rank = safe_str(row.get(f'{player1} Daily Rank'))
        p2_rank = safe_str(row.get(f'{player2} Daily Rank'))
        p1_score = safe_str(row.get(f'{player1} Score'))
        p2_score = safe_str(row.get(f'{player2} Score'))
        p1_elo = safe_str(row.get(f'{player1} Elo'), "{:.0f}")
        p2_elo = safe_str(row.get(f'{player2} Elo'), "{:.0f}")

        # Header: Date and Winner
        header_html = f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;padding-bottom:0.5rem;border-bottom:1px solid rgba(128,128,128,0.35);">
            <span style="font-weight:600;font-size:1rem;color:var(--text-color);">{date_str}</span>
            <span style="font-weight:700;color:{winner_color};">🏆 {winner}</span>
        </div>
        '''

        # Two-column layout for players
        p1_color = "#3B82F6"
        p2_color = "#F59E0B"

        stats_html = f'''
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;">
            <div style="text-align:center;">
                <div style="font-weight:600;color:{p1_color};margin-bottom:0.5rem;font-size:0.85rem;">{html.escape(player1)}</div>
                <div style="display:flex;justify-content:center;gap:0.75rem;flex-wrap:wrap;">
                    <div style="{stat_layout}"><span style="{label_style}">Rank</span><span style="{value_style}">#{p1_rank}</span></div>
                    <div style="{stat_layout}"><span style="{label_style}">Score</span><span style="{value_style}">{p1_score}</span></div>
                    <div style="{stat_layout}"><span style="{label_style}">Elo</span><span style="{value_style}">{p1_elo}</span></div>
                </div>
            </div>
            <div style="text-align:center;">
                <div style="font-weight:600;color:{p2_color};margin-bottom:0.5rem;font-size:0.85rem;">{html.escape(player2)}</div>
                <div style="display:flex;justify-content:center;gap:0.75rem;flex-wrap:wrap;">
                    <div style="{stat_layout}"><span style="{label_style}">Rank</span><span style="{value_style}">#{p2_rank}</span></div>
                    <div style="{stat_layout}"><span style="{label_style}">Score</span><span style="{value_style}">{p2_score}</span></div>
                    <div style="{stat_layout}"><span style="{label_style}">Elo</span><span style="{value_style}">{p2_elo}</span></div>
                </div>
            </div>
        </div>
        '''

        card = f'<div style="{card_base}">{header_html}{stats_html}</div>'
        cards.append(card)

    return "".join(cards)


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
    is_dark = True  # Default to dark

    try:
        # Method 1: st.context (Streamlit 1.37+) - most reliable for runtime detection
        if hasattr(st, 'context') and hasattr(st.context, 'theme'):
            theme_info = st.context.theme
            if theme_info:
                # Check backgroundColor - light themes have high RGB values
                bg_color = getattr(theme_info, 'backgroundColor', None)
                if bg_color:
                    # Parse hex color to check luminance
                    bg_hex = bg_color.lstrip('#')
                    if len(bg_hex) == 6:
                        r, g, b = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
                        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
                        is_dark = luminance < 128
    except Exception:
        pass

    # Method 2: Fallback to theme.base option
    if is_dark:
        try:
            theme_base = st.get_option("theme.base")
            if theme_base == "light":
                is_dark = False
        except Exception:
            pass

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
        /* Expander content text - ensure light text in dark mode */
        [data-testid="stExpander"] p,
        [data-testid="stExpander"] li,
        [data-testid="stExpander"] td,
        [data-testid="stExpander"] th {
            color: #FAFAFA !important;
        }
        [data-testid="stExpander"] strong {
            color: #FFFFFF !important;
        }
        /* Expander header - force light text in dark mode with multiple methods */
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] details > summary,
        [data-testid="stExpander"] details > summary *,
        [data-testid="stExpander"] details[open] > summary,
        [data-testid="stExpander"] details[open] > summary *,
        .streamlit-expanderHeader,
        .streamlit-expanderHeader *,
        details[open] > summary,
        details[open] > summary * {
            color: #FAFAFA !important;
            -webkit-text-fill-color: #FAFAFA !important;
            opacity: 1 !important;
            visibility: visible !important;
            background-clip: unset !important;
            -webkit-background-clip: unset !important;
        }
        /* Ensure expanded header has visible background */
        [data-testid="stExpander"] details[open] > summary {
            background-color: rgba(38, 39, 48, 0.95) !important;
        }
        [data-testid="stExpander"] summary svg,
        [data-testid="stExpander"] details > summary svg,
        [data-testid="stExpander"] details[open] > summary svg {
            fill: #FAFAFA !important;
            stroke: #FAFAFA !important;
            opacity: 1 !important;
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
        /* Expander content text - ensure dark text in light mode */
        [data-testid="stExpander"] p,
        [data-testid="stExpander"] li,
        [data-testid="stExpander"] td,
        [data-testid="stExpander"] th {
            color: #262730 !important;
        }
        [data-testid="stExpander"] strong {
            color: #1a1c23 !important;
        }
        /* Expander header - force dark text in light mode with multiple methods */
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] summary *,
        [data-testid="stExpander"] details > summary,
        [data-testid="stExpander"] details > summary *,
        [data-testid="stExpander"] details[open] > summary,
        [data-testid="stExpander"] details[open] > summary *,
        .streamlit-expanderHeader,
        .streamlit-expanderHeader *,
        details[open] > summary,
        details[open] > summary * {
            color: #262730 !important;
            -webkit-text-fill-color: #262730 !important;
            opacity: 1 !important;
            visibility: visible !important;
            background-clip: unset !important;
            -webkit-background-clip: unset !important;
        }
        /* Ensure expanded header has visible background */
        [data-testid="stExpander"] details[open] > summary {
            background-color: rgba(240, 242, 246, 0.95) !important;
        }
        [data-testid="stExpander"] summary svg,
        [data-testid="stExpander"] details > summary svg,
        [data-testid="stExpander"] details[open] > summary svg {
            fill: #262730 !important;
            stroke: #262730 !important;
            opacity: 1 !important;
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

/* ===== Metric Cards (theme-adaptive using Streamlit CSS variables) ===== */
[data-testid="stMetric"] {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15) !important;
    border-color: rgba(255, 107, 107, 0.4) !important;
}

[data-testid="stMetric"] label {
    font-family: var(--font-body) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--text-color) !important;
    opacity: 0.7 !important;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-family: var(--font-display) !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: var(--text-color) !important;
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
/* Background set dynamically via get_theme_css() for theme support */

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

/* ===== Ranking Cards ===== */
.ranking-cards {
    display: block;
}

/* Responsive stats grid: 8 columns on desktop, 4 on mobile */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 0.5rem;
    margin-top: 0.5rem;
}

/* Responsive card header: matches stats grid columns */
.card-header {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.625rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(128,128,128,0.35);
}
.card-rank {
    grid-column: 1;
    font-weight: 700;
    font-size: 1rem;
    text-align: center;
}
.card-name {
    grid-column: 2 / 8;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    overflow: hidden;
}
.card-name-text {
    font-weight: 600;
    font-size: 1rem;
    color: var(--text-color);
    word-break: break-word;
    overflow-wrap: break-word;
    line-height: 1.2;
}
.card-rating {
    grid-column: 8;
    font-weight: 700;
    font-size: 1.1rem;
    text-align: center;
}
.card-rating.active {
    color: #FF6B6B;
}
.card-rating.inactive {
    color: #6B9AFF;
}

/* Sort controls */
.sort-controls {
    display: block;
    margin-bottom: 1rem;
}

/* Removed: Hidden table CSS - tables now fully removed from code */

/* Back to top anchor */
#top {
    scroll-margin-top: 100vh;
}

/* Back to top button */
.back-to-top {
    display: flex;
    align-items: center;
    justify-content: center;
    position: fixed;
    bottom: 2rem;
    right: 1.5rem;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #FF6B6B 0%, #ee5a5a 100%);
    border: none;
    color: white !important;
    font-size: 1.5rem;
    font-weight: bold;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(255,107,107,0.4);
    z-index: 1000;
    transition: transform 0.2s, box-shadow 0.2s;
    text-decoration: none !important;
}
.back-to-top:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 16px rgba(255,107,107,0.5);
}
.back-to-top:active {
    transform: scale(0.95);
}

/* Mobile responsive: 4-column grid */
@media (max-width: 768px) {
    .stats-grid {
        grid-template-columns: repeat(4, 1fr) !important;
    }
    .card-header {
        grid-template-columns: repeat(4, 1fr) !important;
    }
    .card-rank {
        grid-column: 1 !important;
        justify-self: center !important;
        text-align: center !important;
    }
    .card-name {
        grid-column: 2 / 4 !important;
        justify-self: center !important;
        text-align: center !important;
    }
    .card-name-text {
        font-size: 0.875rem !important;
    }
    .card-rating {
        grid-column: 4 !important;
        justify-self: center !important;
        text-align: center !important;
        font-size: 1rem !important;
    }
}

/* Large viewport: bigger card content */
@media (min-width: 1200px) {
    .card-name-text {
        font-size: 1.15rem !important;
    }
    .card-rating {
        font-size: 1.25rem !important;
    }
    .card-rank {
        font-size: 1.1rem !important;
    }
    .stats-grid > div span:last-child {
        font-size: 1rem !important;
    }
}
</style>
"""


def apply_plotly_style(fig, add_gradient_fill=False):
    """Apply consistent styling to Plotly figures with theme-adaptive text colors.

    Text colors are NOT explicitly set, allowing Streamlit to inject theme-aware
    colors automatically. Only structural elements (grids, backgrounds) use
    explicit neutral colors.
    """
    # Structural colors that work on both light and dark backgrounds
    grid_color = "rgba(128, 128, 128, 0.4)"  # Neutral gray grid
    line_color = "rgba(128, 128, 128, 0.3)"  # Neutral gray lines
    legend_bg = "rgba(128, 128, 128, 0.15)"  # Semi-transparent neutral
    hover_bg = "rgba(50, 50, 50, 0.9)"  # Dark hover for readability
    hover_text = "#FFFFFF"  # White text on dark hover background

    # Bold font weight for better readability
    bold_weight = 600

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Rajdhani, sans-serif", weight=bold_weight),
        xaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(family="Rajdhani", size=12, weight=bold_weight),
            title_font=dict(weight=bold_weight),
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(family="Rajdhani", size=12, weight=bold_weight),
            title_font=dict(weight=bold_weight),
            showgrid=True,
            zeroline=False,
        ),
        legend=dict(
            font=dict(family="Rajdhani", weight=bold_weight),
            bgcolor=legend_bg,
            bordercolor=line_color,
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor=ACCENT_COLORS["primary"],
            font=dict(color=hover_text, family="Rajdhani", weight=bold_weight),
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


# --- Constants ---
OUTPUT_FOLDER = Path(__file__).parent / "data" / "processed"
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
    logo_path = Path(__file__).parent / "images" / "dftl_logo.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
            /* Container query context */
            .header-container {{
                container-type: inline-size;
                container-name: header;
            }}
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
                flex-shrink: 0;
            }}
            .dashboard-title {{
                font-family: 'Cinzel', serif;
                font-size: clamp(1.4rem, 5cqw, 2.8rem) !important;
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
                font-size: clamp(0.7rem, 1.8cqw, 1.1rem);
                color: #B0B0B0;
                letter-spacing: 0.1em;
                text-transform: uppercase;
                font-weight: 500;
            }}
            /* Container query: stacked layout when container is narrow */
            @container header (max-width: 600px) {{
                .dashboard-header {{
                    flex-direction: column;
                    align-items: center;
                    text-align: center;
                    gap: 1rem;
                    padding: 1rem;
                }}
                .dashboard-logo {{
                    width: 100px;
                }}
                .dashboard-text {{
                    width: 100%;
                    text-align: center;
                }}
                .dashboard-title {{
                    text-align: center;
                    font-size: 1.5rem !important;
                }}
                .dashboard-subtitle {{
                    letter-spacing: 0.05em;
                    text-align: center;
                }}
            }}
            /* Container query: small container fixed sizes */
            @container header (max-width: 400px) {{
                .dashboard-title {{
                    font-size: 1.3rem !important;
                }}
                .dashboard-subtitle {{
                    font-size: 0.75rem;
                }}
            }}
            /* Fallback media query for hiding anchor on narrow viewports */
            @media (max-width: 768px) {{
                [data-testid="stHeaderActionElements"] {{
                    display: none !important;
                }}
            }}
        </style>
        <div class="header-container">
            <div class="dashboard-header">
                <img src="data:image/png;base64,{logo_b64}" class="dashboard-logo">
                <div class="dashboard-text">
                    <h1 class="dashboard-title">DFTL Ranking Dashboard</h1>
                    <p class="dashboard-subtitle">Track Elo ratings, compare players, and analyze performance trends</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("DFTL Ranking Dashboard")
        st.caption("Track Elo ratings, compare players, and analyze performance trends")

    # Back-to-top anchor and button (always rendered)
    st.markdown('<a id="top"></a><a href="#top" class="back-to-top" title="Back to top">↑</a>', unsafe_allow_html=True)
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

                # Sort controls
                sort_options = {
                    "Daily Rank": ("rank", True),
                    "Score": ("score", False),
                    "Elo Rating": ("rating", False),
                    "Rating Change": ("rating_change", False),
                }
                if 'active_rank' in df_day.columns:
                    sort_options["Elo Rank"] = ("active_rank", True)

                sort_col1, sort_col2 = st.columns([3, 1])
                with sort_col1:
                    selected_sort = st.selectbox(
                        "Sort by",
                        options=list(sort_options.keys()),
                        index=0,
                        key="leaderboard_sort"
                    )
                with sort_col2:
                    sort_column, default_asc = sort_options[selected_sort]
                    sort_direction = st.selectbox(
                        "Order",
                        options=["Best", "Worst"],
                        index=0,
                        key="leaderboard_sort_dir"
                    )

                sort_ascending = default_asc if sort_direction == "Best" else not default_asc
                df_day_sorted = df_day.sort_values(sort_column, ascending=sort_ascending, na_position='last')

                # Display as cards
                has_rating = 'rating' in df_day.columns
                has_active_rank = 'active_rank' in df_day.columns
                cards_html = generate_leaderboard_cards(df_day_sorted, has_rating=has_rating, has_active_rank=has_active_rank)
                st.markdown(f'<div class="ranking-cards">{cards_html}</div>', unsafe_allow_html=True)
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

                # Toggle to show unranked players (sticky via CSS targeting aria-label)
                show_unranked = st.toggle("Show Unranked Players", value=True, help="Players with <7 games or inactive >7 days")

                # Sort controls for card view
                # Sort options: display name -> (column, default_ascending)
                # ascending=True means lower values first (good for ranks)
                # ascending=False means higher values first (good for ratings, counts)
                sort_options = {
                    "Rating": ("rating", False),
                    "Games": ("games_played", False),
                    "Wins": ("wins", False),
                    "Win %": ("win_rate", False),
                    "Top 10": ("top_10s", False),
                    "Top 10 %": ("top_10s_rate", False),
                    "Avg Rank": ("avg_daily_rank", True),
                    "7-Game Avg": ("last_7", True),
                    "Stability": ("consistency", True),
                }

                st.markdown('<div class="sort-controls">', unsafe_allow_html=True)
                sort_col1, sort_col2 = st.columns([3, 1])
                with sort_col1:
                    selected_sort = st.selectbox(
                        "Sort by",
                        options=list(sort_options.keys()),
                        index=0,  # Default to Rating
                        key="card_sort"
                    )
                with sort_col2:
                    sort_column, default_asc = sort_options[selected_sort]
                    sort_direction = st.selectbox(
                        "Order",
                        options=["Best", "Worst"],
                        index=0,
                        key="card_sort_dir"
                    )
                st.markdown('</div>', unsafe_allow_html=True)

                # Determine sort direction based on selection
                sort_ascending = default_asc if sort_direction == "Best" else not default_asc

                # Columns to display (defined once, reused)
                display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency']
                if 'days_inactive' in df_date_history.columns:
                    display_cols.append('days_inactive')

                # Filter data based on unranked toggle
                if show_unranked:
                    df_filtered = df_date_history[display_cols].copy()
                else:
                    df_filtered = df_date_history[df_date_history['active_rank'].notna()][display_cols].copy()

                # Sort cards by selected option
                df_cards_display = df_filtered.sort_values(sort_column, ascending=sort_ascending, na_position='last')

                # Card layout (responsive: 8 stats on desktop, 4x2 on mobile)
                # Uses Streamlit CSS variables for automatic theme adaptation
                cards_html = generate_ranking_cards(df_cards_display)
                st.markdown(f'<div class="ranking-cards">{cards_html}</div>', unsafe_allow_html=True)
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
                st.plotly_chart(fig_dist, width='stretch')

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
                "games_played": st.column_config.NumberColumn("Games", format="%d", help="Top 30 Daily Runs"),
                "wins": st.column_config.NumberColumn("Wins", format="%d"),
                "win_rate": st.column_config.NumberColumn("Win %", format="%.1f"),
                "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                "top_10s_rate": st.column_config.NumberColumn("Top 10 %", format="%.1f"),
                "avg_daily_rank": st.column_config.NumberColumn("Avg Rank", format="%.1f", help="Average Daily Rank over all games"),
                "last_7": st.column_config.NumberColumn("7-Game Avg", format="%.1f", help="Average Daily Rank over last 7 games"),
                "last_seen": st.column_config.DateColumn("Last Seen", format="YYYY-MM-DD")
            }
            if has_days_inactive:
                column_config["days_inactive"] = st.column_config.NumberColumn("Inactive", format="%d")
            if has_uncertainty:
                column_config["uncertainty"] = st.column_config.NumberColumn("Uncertainty", format="%.2f")

            st.dataframe(
                df_ratings_display[display_cols],
                width='stretch',
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
                            st.metric("Current Rating", f"{current_rating:.0f}")
                        with col2:
                            games = int(latest['games_played'])
                            st.metric("Games Played", games, help="Top 30 Daily Runs")
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
                            st.metric("Avg Rank", f"{avg_rank:.1f}" if pd.notna(avg_rank) else "N/A", help="Average Daily Rank over all games")
                        with col6:
                            last_7 = latest['last_7']
                            st.metric("7-Game Avg", f"{last_7:.1f}" if pd.notna(last_7) else "N/A", help="Average Daily Rank over last 7 games")
                        with col7:
                            consistency = latest['consistency']
                            st.metric("Stability", f"{consistency:.1f}" if pd.notna(consistency) else "N/A", help="Rank variation over last 14 games (lower = more stable)")
                        with col8:
                            # Get CURRENT Elo rank from current ratings (not from last game history)
                            current_player_rating = df_ratings[df_ratings['player_name'] == selected_player]
                            if not current_player_rating.empty and pd.notna(current_player_rating.iloc[0]['active_rank']):
                                current_rank = int(current_player_rating.iloc[0]['active_rank'])
                                st.metric("Elo Rank", f"#{current_rank}")
                            else:
                                st.metric("Elo Rank", "Inactive", help="Not ranked (inactive >7 days or <7 games)")

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
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['info']};">Daily Rank #{first_rank} | Rating: {first_rating:.0f}</div>
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
                                <div style="font-size: 0.875rem; color: {ACCENT_COLORS['primary']};">Daily Rank #{last_rank} | Rating: {last_rating:.0f}</div>
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
                        st.plotly_chart(fig_rating, width='stretch')

                        # --- Daily Rank History Chart (Bar Chart) ---
                        st.subheader("Daily Rank History")

                        # Bars grow from bottom (rank 31) UPWARD toward rank 1
                        # Better ranks (closer to 1) = taller bars
                        base_rank = 31  # Base of all bars (bottom of chart)
                        fig_rank = go.Figure()

                        # Calculate bar heights: negative values so bars grow upward on reversed y-axis
                        # height = rank - base_rank (e.g., rank 1 -> height -30, rank 30 -> height -1)
                        ranks = df_chart['rank'].tolist()
                        bar_heights = [r - base_rank for r in ranks]  # All negative

                        # Determine colors: green for best rank (rank 1), blue for others
                        best_rank = df_chart['rank'].min()
                        bar_colors = [ACCENT_COLORS["success"] if r == best_rank else ACCENT_COLORS["info"] for r in ranks]

                        fig_rank.add_trace(go.Bar(
                            x=df_chart['date'],
                            y=bar_heights,  # Negative heights = bars grow upward
                            base=[base_rank] * len(df_chart),  # All bars start from rank 31
                            marker=dict(
                                color=bar_colors,
                                line=dict(width=1, color='rgba(255,255,255,0.3)')
                            ),
                            customdata=ranks,  # Store actual ranks for hover
                            hovertemplate='%{x|%b %d, %Y}<br>Rank #%{customdata}<extra></extra>',
                        ))

                        apply_plotly_style(fig_rank)
                        fig_rank.update_layout(
                            height=280,
                            margin=dict(l=20, r=70, t=30, b=20),  # Extra right margin for annotation
                            showlegend=False,
                            yaxis=dict(
                                autorange="reversed",  # Rank 1 at top, rank 31 at bottom
                                range=[1, base_rank],  # With reversed: 1 at top, 31 at bottom
                                title="Daily Rank",
                                tickmode='array',
                                tickvals=[1, 5, 10, 15, 20, 25, 30],
                            ),
                            xaxis=dict(title="Date"),
                            bargap=0.15,
                        )
                        # Add average rank line with annotation at right edge
                        avg_rank_val = df_chart['rank'].mean()
                        fig_rank.add_hline(
                            y=avg_rank_val,
                            line_dash="dash",
                            line_color="rgba(59, 130, 246, 0.8)",
                            annotation_text=f"Avg: {avg_rank_val:.1f}",
                            annotation_position="right",
                            annotation_font=dict(color="rgba(59, 130, 246, 1)", weight=600),
                            annotation_xshift=5,  # Small shift to ensure text is in margin area
                        )
                        st.plotly_chart(fig_rank, width='stretch')

                        # --- Game History Cards ---
                        st.subheader("Game History")

                        # Sort controls
                        sort_options = {
                            "Date": ("date", False),
                            "Daily Rank": ("rank", True),
                            "Score": ("score", False),
                            "Rating": ("rating", False),
                            "Rating Change": ("rating_change", False),
                        }

                        sort_col1, sort_col2 = st.columns([3, 1])
                        with sort_col1:
                            selected_sort = st.selectbox(
                                "Sort by",
                                options=list(sort_options.keys()),
                                index=0,
                                key="history_sort"
                            )
                        with sort_col2:
                            sort_column, default_asc = sort_options[selected_sort]
                            sort_direction = st.selectbox(
                                "Order",
                                options=["Best", "Worst"] if selected_sort != "Date" else ["Recent", "Oldest"],
                                index=0,
                                key="history_sort_dir"
                            )

                        sort_ascending = default_asc if sort_direction in ["Best", "Oldest"] else not default_asc
                        df_table = df_player_played.sort_values(sort_column, ascending=sort_ascending, na_position='last')

                        # Display as cards
                        cards_html = generate_game_history_cards(df_table, has_active_rank=has_active_rank)
                        st.markdown(f'<div class="ranking-cards">{cards_html}</div>', unsafe_allow_html=True)
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
                        tickfont=dict(weight=600)
                    )
                )
                st.plotly_chart(fig_rank1, width='stretch')

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
                width='stretch',
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

                        # Win distribution pie chart (below encounter badges)
                        if len(common_dates) > 0:
                            pie_data = pd.DataFrame({
                                'Result': [player1, player2, 'Tie'],
                                'Count': [p1_wins, p2_wins, ties]
                            })
                            pie_data = pie_data[pie_data['Count'] > 0]

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
                            fig_pie.update_layout(
                                height=250,
                                margin=dict(l=20, r=20, t=20, b=40),
                                showlegend=True,
                                legend=dict(
                                    orientation="h",
                                    yanchor="top",
                                    y=-0.05,
                                    xanchor="center",
                                    x=0.5,
                                    font=dict(size=12, weight=600)
                                )
                            )
                            st.plotly_chart(fig_pie, width='stretch')

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
                        fig_elo.update_layout(
                            hovermode='x unified',
                            height=350,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(weight=600),
                            ),
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        fig_elo.add_hline(
                            y=1500,
                            line_dash="dash",
                            line_color="rgba(128, 128, 128, 0.5)",
                            annotation_text="Baseline",
                            annotation_font=dict(weight=600)
                        )
                        st.plotly_chart(fig_elo, width='stretch')

                        # Score Comparison (Diverging Bar Chart with Winner Highlighting)
                        st.subheader("Score Comparison")

                        # Build diverging score data: P1 positive, P2 negative
                        dates_sorted = sorted(common_dates)
                        p1_scores_raw = []
                        p2_scores_raw = []

                        for date in dates_sorted:
                            p1_data = df_p1_played[df_p1_played['date'].dt.date == date].iloc[0]
                            p2_data = df_p2_played[df_p2_played['date'].dt.date == date].iloc[0]
                            p1_scores_raw.append(p1_data['score'])
                            p2_scores_raw.append(p2_data['score'])

                        # Calculate adaptive cap based on 90th percentile
                        all_scores = p1_scores_raw + p2_scores_raw
                        if len(all_scores) > 0:
                            score_cap = np.percentile(all_scores, 90) * 1.5  # 1.5x the 90th percentile
                            score_cap = max(score_cap, 1000)  # Minimum cap to avoid tiny charts
                        else:
                            score_cap = 50000

                        # Build display data with capping
                        p1_scores_display = []
                        p2_scores_display = []
                        p1_colors = []
                        p2_colors = []
                        p1_patterns = []
                        p2_patterns = []

                        for i, date in enumerate(dates_sorted):
                            p1_score = p1_scores_raw[i]
                            p2_score = p2_scores_raw[i]

                            # Cap scores for display (keep actual for hover)
                            p1_capped = min(p1_score, score_cap)
                            p2_capped = min(p2_score, score_cap)
                            p1_scores_display.append(p1_capped)
                            p2_scores_display.append(-p2_capped)  # Negative for diverging

                            # Determine winner and color accordingly
                            if p1_score > p2_score:
                                p1_colors.append(ACCENT_COLORS["info"])  # Winner: highlighted
                                p2_colors.append("rgba(128, 128, 128, 0.4)")  # Loser: muted
                            elif p2_score > p1_score:
                                p1_colors.append("rgba(128, 128, 128, 0.4)")  # Loser: muted
                                p2_colors.append(ACCENT_COLORS["warning"])  # Winner: highlighted
                            else:  # Tie
                                p1_colors.append("rgba(128, 128, 128, 0.6)")
                                p2_colors.append("rgba(128, 128, 128, 0.6)")

                            # Add stripe pattern for capped bars
                            p1_patterns.append("/" if p1_score > score_cap else "")
                            p2_patterns.append("/" if p2_score > score_cap else "")

                        fig_score = go.Figure()

                        # P1 bars (positive, above zero line)
                        fig_score.add_trace(go.Bar(
                            name=player1,
                            x=dates_sorted,
                            y=p1_scores_display,
                            marker=dict(
                                color=p1_colors,
                                line=dict(width=1, color='rgba(255,255,255,0.3)'),
                                pattern=dict(shape=p1_patterns, solidity=0.5),
                            ),
                            customdata=p1_scores_raw,
                            hovertemplate=f'{player1}: %{{customdata:,.0f}}<extra></extra>',
                            showlegend=False,
                        ))

                        # P2 bars (negative, below zero line)
                        fig_score.add_trace(go.Bar(
                            name=player2,
                            x=dates_sorted,
                            y=p2_scores_display,
                            marker=dict(
                                color=p2_colors,
                                line=dict(width=1, color='rgba(255,255,255,0.3)'),
                                pattern=dict(shape=p2_patterns, solidity=0.5),
                            ),
                            customdata=p2_scores_raw,
                            hovertemplate=f'{player2}: %{{customdata:,.0f}}<extra></extra>',
                            showlegend=False,
                        ))

                        # Add invisible traces for legend with consistent player colors
                        fig_score.add_trace(go.Scatter(
                            x=[None], y=[None],
                            mode='markers',
                            marker=dict(size=10, color=ACCENT_COLORS["info"]),
                            name=player1,
                            showlegend=True,
                        ))
                        fig_score.add_trace(go.Scatter(
                            x=[None], y=[None],
                            mode='markers',
                            marker=dict(size=10, color=ACCENT_COLORS["warning"]),
                            name=player2,
                            showlegend=True,
                        ))

                        apply_plotly_style(fig_score)
                        fig_score.update_layout(
                            barmode='relative',
                            hovermode='x unified',
                            height=300,
                            bargap=0.15,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(weight=600),
                            ),
                            margin=dict(l=20, r=20, t=40, b=20),
                            yaxis=dict(
                                title="Score",
                                tickformat=",d",
                                range=[-score_cap * 1.1, score_cap * 1.1],  # Symmetric range
                            ),
                            xaxis=dict(title="Date"),
                        )

                        # Add zero line for visual clarity
                        fig_score.add_hline(y=0, line_width=1, line_color="rgba(128, 128, 128, 0.5)")

                        st.plotly_chart(fig_score, width='stretch')

                        # Display the duel cards
                        st.subheader("Game-by-Game Comparison")

                        # Sort controls
                        sort_options = {
                            "Date": ("Date", False),
                            f"{player1} Daily Rank": (f"{player1} Daily Rank", True),
                            f"{player2} Daily Rank": (f"{player2} Daily Rank", True),
                            f"{player1} Score": (f"{player1} Score", False),
                            f"{player2} Score": (f"{player2} Score", False),
                        }

                        sort_col1, sort_col2 = st.columns([3, 1])
                        with sort_col1:
                            selected_sort = st.selectbox(
                                "Sort by",
                                options=list(sort_options.keys()),
                                index=0,
                                key="duel_sort"
                            )
                        with sort_col2:
                            sort_column, default_asc = sort_options[selected_sort]
                            sort_direction = st.selectbox(
                                "Order",
                                options=["Best", "Worst"] if selected_sort != "Date" else ["Recent", "Oldest"],
                                index=0,
                                key="duel_sort_dir"
                            )

                        sort_ascending = default_asc if sort_direction in ["Best", "Oldest"] else not default_asc
                        df_duel_sorted = df_duel.sort_values(sort_column, ascending=sort_ascending, na_position='last')

                        # Display as cards
                        cards_html = generate_duel_cards(df_duel_sorted, player1, player2)
                        st.markdown(f'<div class="ranking-cards">{cards_html}</div>', unsafe_allow_html=True)
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
            Ratings reflects actual skill gaps between players (the better the player the higher the rating), and roughly matches with expected performance:

            | Rating | Typical Rank |
            |--------|--------------|
            | **2800+** | Top 1 |
            | **2500-2800** | Top 5 |
            | **2000-2500** | Top 10 |
            | **1500** | ~Rank 15-20 |
            | **1200-1500** | Rank 20-25 |
            | **1000-1200** | Rank 25-30 |
            """)

        with st.expander("How are Elo Rankings calculated?"):
            st.markdown("""
            Each day, all players on the leaderboard are compared pairwise:
            1. Player A finishes 5th. They beat the 25 players below them, and lost to the 4 above
            2. Rating changes are calculated using a modified Elo formula
            3. Score is taken into account. Domination means more points, narrow wins mean less
            4. Players with more games have more stable ratings (dynamic K-factor)
            5. Uncertainty increases with inactivity, so you'll face big rating swings on return

            After 7 daily leaderboard appearances, you become Ranked.
            Your Elo rank is determined by your rating compared to the other Ranked players.

            After 7 days without a leaderboard appearance, you are considered inactive, and you become Unranked.
            Don't worry, your rating is preserved.
            At this point, a single top 30 result is enough to get you back in the rankings.
            """)

        with st.expander("Why did my rating change so much/little?"):
            st.markdown("""
            Several factors:
            - **Opponent ratings**: Beating higher-rated players = bigger gains
            - **Score margin**: Dominating performances give more weight
            - **Games played**: New players (<10 games) have larger swings to find their true rating
            - **Your rating level**: Gains shrink as you climb
            - **Number of opponents**: Placing #1 means you beat 29 opponents, #30 means you beat none
            """)

        st.markdown("---")
        st.subheader("System Design Philosophy")

        with st.expander("Why use Elo instead of other rating systems?"):
            st.markdown("""
            The true answer is that I'm a former chess player and I'll always be biased in favor of the Elo system.
            I did consider and/or try several other rating systems though:

            | System | Pros | Why I didn't use it |
            |--------|------|---------------------|
            | **Glicko/Glicko-2** | Popular, tracks rating uncertainty | Designed for 1v1 matches, not 30-player daily competitions |
            | **TrueSkill** | Robust skill-based matchmaking algorithm  | Overkill for our use case. Also it's patented by Microsoft and I don't have "Microsoft lawyer" money |
            | **Simple averages** | Easy to understand, easy to implement | "Underkill" for our use case. Doesn't account for opponent strength or improvement over time |
            | **ELO** | Battle-tested, intuitive | Not quite perfect without some tweaks |

            **Why Pairwise Elo works here:**
            - Chess proved that Elo accurately ranks players over time through repeated competition
            - My pairwise adaptation treats each daily leaderboard as 435 simultaneous "matches" (30 players = 30×29/2 pairs)
            - The system is self-correcting: beat strong players, gain more; lose to weak players, lose more
            - It's popular and intuitive: everyone understands "higher number = better"
            """)

        with st.expander("Why pairwise comparisons instead of just using daily rank?"):
            st.markdown("""
            Skill comparisons felt important to highlight
            Daily rank is simply less effective to make those evaluations:

            - Finishing 1st against 29 weak players = same as 1st against 29 strong players
            - A rank of 5th tells you nothing about who you beat or lost to
            - No way to compare across different days with different player pools

            **Why pairwise works better:**
            - Beat a 2500-rated player? Big gain.
            - Lose to a 1200-rated player? Big loss.
            - The gains and losses depend on *who* you competed against.
            """)

        with st.expander("How do you handle only seeing the top 30 each day?"):
            st.markdown("""
            That shaped the system design a lot actually.

            **The limitation:**
            Players ranked 31st or lower are invisible: I don't know their scores, their identities, or even how many of them there are.

            **Why this is actually fine for Elo:**
            The pairwise system only compares players *who both appear on the same day*. If you're in the top 30, you get compared to the other 29 players. If you're not, you simply don't participate that day.

            **Key implications:**
            - **No penalty for missing days**: If you don't appear, your rating stays untouched
            - **Appearing matters**: To gain or lose rating, you must show up in the top 30
            - **Bottom of top 30 is meaningful**: Rank 30 means you made it, but barely. There is still some road ahead

            **What I *can't* measure:**
            - Players who never crack the top 30
            - How much above the rest of the field the top 30 is
            - The "true" skill of players who rarely appear
            """)

        with st.expander("What's the deal with rating compression?"):
            st.markdown("""
            Raw Elo scores are processed and then compressed using a hybrid system:
            - Below 2700: Gentle logarithmic scaling (diminishing returns)
            - Above 2700: Hyperbolic tangent compression toward the 3000 ceiling
                        
            This allows the high end of the distribution curve to mimic chess Elo, in the sense that:
            - **2800+** is genuinely elite
            - **2900** is legendary
            - **3000** is the theoretical limits of human ability
                        
            While mostly aesthetics (compared to the raw ratings), it prevents runaway ratings while preserving meaningful differences
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
            | **Games** | Top 30 Daily Runs |
            | **Confidence** | How reliable your rating is (based on games played) |
            """)

        with col2:
            st.markdown("""
            | Term | Definition |
            |------|------------|
            | **Avg Rank** | Average Daily Rank over all games |
            | **7-Game Avg** | Average Daily Rank over last 7 games |
            | **Stability** | Rank variation over last 14 games (lower = more stable) |
            | **Daily Rank** | Your position on a specific day's leaderboard |
            | **Rating Change** | How much your Elo changed that day |
            | **Baseline** | The starting/median rating of 1500 |
            | **Compression** | System that maps raw ratings to display ratings |
            """)


if __name__ == "__main__":
    main()
