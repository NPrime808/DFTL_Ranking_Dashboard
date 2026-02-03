import math
import base64
import html
import random
from urllib.parse import quote

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

# --- Share URL Configuration ---
# Detect base URL dynamically from request headers (falls back to localhost for dev)
def get_share_base_url():
    """Get the base URL for shareable links from request headers."""
    try:
        headers = st.context.headers
        host = headers.get("host", headers.get("Host", "localhost:8501"))
        # Use https unless it's localhost
        protocol = "http" if "localhost" in host or "127.0.0.1" in host else "https"
        return f"{protocol}://{host}"
    except Exception:
        return "http://localhost:8501"

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


def build_url_with_params(new_params):
    """
    Build a URL query string with only params relevant to the target tab.
    Keeps URLs clean while allowing deep linking to specific views.
    """
    # Define which params are relevant to each tab
    TAB_PARAMS = {
        "rankings": ["date"],
        "duels": ["player1", "player2"],
        "tracker": ["player"],
        "dailies": ["date"],
        "hall-of-fame": [],
    }

    # Determine target tab from new_params
    target_tab = new_params.get("tab", "rankings")
    relevant_params = TAB_PARAMS.get(target_tab, [])

    # Start with tab param
    result_params = {"tab": target_tab}

    # Only include params relevant to the target tab
    for param in relevant_params:
        if param in new_params:
            result_params[param] = new_params[param]

    # Build query string
    query_parts = [f"{quote(str(k))}={quote(str(v))}" for k, v in result_params.items()]
    return "?" + "&".join(query_parts) if query_parts else ""


def player_link(name, display_text=None):
    """
    Generate an anchor link to the Tracker tab for a player.
    The link uses query params: ?tab=tracker&player=PlayerName
    Preserves other existing query params for navigation context.
    target="_self" ensures navigation stays in the same browser tab.
    """
    if display_text is None:
        display_text = name
    url = build_url_with_params({"tab": "tracker", "player": name})
    escaped_display = html.escape(display_text)
    return f'<a href="{url}" target="_self" class="player-link">{escaped_display}</a>'


def duel_link(player1, player2, display_text=None):
    """
    Generate an anchor link to the Duels tab with a specific matchup.
    The link uses query params: ?tab=duels&player1=Name1&player2=Name2
    Preserves other existing query params for navigation context.
    target="_self" ensures navigation stays in the same browser tab.
    """
    if display_text is None:
        display_text = f"{player1} vs {player2}"
    url = build_url_with_params({"tab": "duels", "player1": player1, "player2": player2})
    escaped_display = html.escape(display_text)
    return f'<a href="{url}" target="_self" class="player-link">{escaped_display}</a>'


def daily_link(date_val, display_text=None):
    """
    Generate an anchor link to the Dailies tab with a specific date selected.
    The link uses query params: ?tab=dailies&date=YYYY-MM-DD
    Preserves other existing query params for navigation context.
    target="_self" ensures navigation stays in the same browser tab.
    """
    # Handle various date formats
    if hasattr(date_val, 'strftime'):
        date_str = date_val.strftime('%Y-%m-%d')
    else:
        date_str = str(date_val)[:10]

    if display_text is None:
        display_text = date_str

    url = build_url_with_params({"tab": "dailies", "date": date_str})
    escaped_display = html.escape(str(display_text))
    return f'<a href="{url}" target="_self" class="date-link">{escaped_display}</a>'


def render_floating_share_button(current_tab_slug):
    """
    Render a floating share button that shows a copyable URL for the current view.
    Uses st.popover() with st.code() for native clipboard support.
    CSS positions this as a fixed floating button.

    Args:
        current_tab_slug: Current tab's URL slug (e.g., "rankings", "dailies")
    """
    # Widget-to-param mapping for each tab
    WIDGET_MAPS = {
        "rankings": {"elo_ranking_date": "date"},
        "dailies": {"dailies_date": "date"},
        "tracker": {"tab4_player_select": "player"},
        "duels": {"duel_player1": "player1", "duel_player2": "player2"},
        "hall-of-fame": {},
    }

    # Build share params from current widget values
    share_params = {"tab": current_tab_slug}
    widget_map = WIDGET_MAPS.get(current_tab_slug, {})
    for widget_key, param in widget_map.items():
        if widget_key in st.session_state and st.session_state[widget_key] is not None:
            value = st.session_state[widget_key]
            if hasattr(value, 'strftime'):
                value = value.strftime('%Y-%m-%d')
            share_params[param] = value

    share_path = build_url_with_params(share_params)

    # Construct full shareable URL (detect domain from request headers)
    base_url = get_share_base_url()
    share_url = f"{base_url}/{share_path.lstrip('/')}"

    # Render popover with share URL (CSS will float this)
    with st.popover("🔗", use_container_width=False, help="Share this view"):
        st.caption("Copy this link to share:")
        st.code(share_url, language=None)


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
    # Uses spacing token: --space-md (1rem) for padding
    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:1rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);"
    # Active player: coral accent gradient
    active_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.15) 100%);"
    # Inactive player (N/R): muted gray gradient to visually distinguish
    inactive_bg = "background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(128,128,128,0.12) 100%);"

    # Header now uses CSS classes for responsive layout (see CSS: .card-header, .card-rank, etc.)
    # Status label style for inactive players (blue to match N/R and rating)
    inactive_blue = "#6B9AFF"
    status_label_style = f"font-size:0.65rem;font-weight:400;margin-top:0.15rem;color:{inactive_blue};"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.8rem;text-transform:uppercase;color:var(--text-color);font-weight:500;"
    value_style = "font-size:1.4rem;font-weight:700;color:var(--text-color);"

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
        raw_name = str(row.get('player_name', 'Unknown'))
        name_link = player_link(raw_name)
        games_played = row.get('games_played', 0)
        games_count = int(games_played) if pd.notna(games_played) else 0

        if is_inactive:
            # WCAG compliant opacity (0.7 provides ~4.5:1 contrast)
            # Status label on separate line to avoid cutoff on small screens
            if games_count < 7:
                status_text = "(not enough games)"
            else:
                status_text = "(inactive)"
            name_html = f'<span class="card-name-text">{name_link}</span><span style="{status_label_style}">{status_text}</span>'
        else:
            name_html = f'<span class="card-name-text">{name_link}</span>'

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
        card = f'<div style="{card_style}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name">{name_html}</div><div class="card-rating {rating_class}"><span class="rating-label">Elo</span>{rating}</div></div><div class="stats-grid"><div style="{stat_layout}"><span style="{label_style}">Games</span><span style="{value_style}">{games}</span></div><div style="{stat_layout}"><span style="{label_style}">Wins</span><span style="{value_style}">{wins}</span></div><div style="{stat_layout}"><span style="{label_style}">Win%</span><span style="{value_style}">{win_rate}</span></div><div style="{stat_layout}"><span style="{label_style}">Top10</span><span style="{value_style}">{top10}</span></div><div style="{stat_layout}"><span style="{label_style}">Top10%</span><span style="{value_style}">{top10_rate}</span></div><div style="{stat_layout}"><span style="{label_style}">Avg Rank</span><span style="{value_style}">{avg_r}</span></div><div style="{stat_layout}"><span style="{label_style}">7-Game Avg</span><span style="{value_style}">{last7}</span></div><div style="{stat_layout}"><span style="{label_style}">Stability</span><span style="{value_style}">{consist}</span></div></div></div>'
        cards.append(card)

    return "".join(cards)


def generate_leaderboard_cards(df, has_rating=True, has_active_rank=True):
    """
    Generate HTML cards for the daily leaderboard display (Tab 4).
    Shows: Daily Rank, Player Name, Score, Rating (if available), Rating Change, Elo Rank.
    """
    if df.empty:
        return "<p>No data available</p>"

    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:1rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(255,107,107,0.15) 100%);"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.8rem;text-transform:uppercase;color:var(--text-color);font-weight:500;"
    value_style = "font-size:1.4rem;font-weight:700;color:var(--text-color);"

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

        raw_name = str(row.get('player_name', 'Unknown'))
        name_link = player_link(raw_name)
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

        card = f'<div style="{card_base}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name"><span class="card-name-text">{name_link}</span></div><div class="card-rating active">{score}</div></div><div class="stats-grid" style="grid-template-columns:repeat(4, 1fr);">{stats_html}</div></div>'
        cards.append(card)

    return "".join(cards)


def generate_game_history_cards(df, has_active_rank=True):
    """
    Generate HTML cards for player game history display (Tab 3).
    Shows: Date, Daily Rank, Score, Rating, Rating Change, cumulative stats.
    """
    if df.empty:
        return "<p>No data available</p>"

    card_base = "border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:1rem;margin-bottom:0.75rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(59,130,246,0.12) 100%);"

    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;"
    label_style = "font-size:0.8rem;text-transform:uppercase;color:var(--text-color);font-weight:500;"
    value_style = "font-size:1.4rem;font-weight:700;color:var(--text-color);"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    cards = []
    for _, row in df.iterrows():
        # Date as header (clickable link to Dailies tab)
        date_val = row.get('date')
        date_link_html = daily_link(date_val)

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

        card = f'<div style="{card_base}"><div class="card-header"><div class="card-rank">{rank_html}</div><div class="card-name"><span class="card-name-text">{date_link_html}</span></div><div class="card-rating active">{rating}</div></div><div class="stats-grid">{stats_html}</div></div>'
        cards.append(card)

    return "".join(cards)


def generate_duel_cards(df, player1, player2, colors=None, limit=None, last_encounter_label=False):
    """
    Generate HTML cards for head-to-head comparison (Tab 2).
    Shows: Date, Winner, both players' ranks/scores/elo side-by-side.
    Styled to match Tab 1 ranking cards for consistency.

    Args:
        colors: Theme colors dict from get_theme_colors(). If None, uses defaults.
        limit: If set, only render first N cards (but use full df for cumulative win calculation).
        last_encounter_label: If True, adds "(last encounter)" after the date on the first card.
    """
    if df.empty:
        return "<p>No data available</p>"

    # Match Tab 1 typography (design system compliant)
    stat_layout = "display:flex;flex-direction:column;align-items:center;text-align:center;min-width:60px;"
    label_style = "font-size:0.8rem;text-transform:uppercase;color:var(--text-color);font-weight:500;"
    value_style = "font-size:1.4rem;font-weight:700;color:var(--text-color);"

    # Theme-adaptive player colors (Cyan + Amber)
    # Dark mode: bright cyan #22D3EE, golden amber #FBBF24
    # Light mode: muted cyan #0891B2, burnt amber #B45309
    if colors:
        p1_color = colors.get("player1", "#0891B2")
        p2_color = colors.get("player2", "#B45309")
        p1_rgb = colors.get("player1_rgb", "8, 145, 178")
        p2_rgb = colors.get("player2_rgb", "180, 83, 9")
    else:
        p1_color = "#0891B2"
        p2_color = "#B45309"
        p1_rgb = "8, 145, 178"
        p2_rgb = "180, 83, 9"
    tie_color = "#525252"
    tie_rgb = "82, 82, 82"

    def safe_str(val, fmt=None):
        if pd.isna(val):
            return "—"
        if fmt:
            return fmt.format(val)
        return str(int(val))

    # Pre-compute cumulative wins by date (chronological order)
    df_sorted_by_date = df.sort_values('Date')
    cumulative_wins = {}
    p1_wins = 0
    p2_wins = 0
    for _, row in df_sorted_by_date.iterrows():
        winner = row.get('Winner', 'Tie')
        if winner == player1:
            p1_wins += 1
        elif winner == player2:
            p2_wins += 1
        # Store cumulative wins as of this date
        date_val = row.get('Date')
        cumulative_wins[date_val] = (p1_wins, p2_wins)

    cards = []
    for idx, (_, row) in enumerate(df.iterrows()):
        # Respect limit parameter if set
        if limit is not None and idx >= limit:
            break
        date_val = row.get('Date')
        # Generate date string for display
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = str(date_val)[:10]
        # Add "(most recent)" label to first card if requested
        display_date = date_str + " (most recent)" if last_encounter_label and idx == 0 else date_str
        # Create clickable date link
        date_link_html = daily_link(date_val, display_date)

        winner = row.get('Winner', 'Tie')

        # Get cumulative wins as of this date
        p1_cumulative, p2_cumulative = cumulative_wins.get(date_val, (0, 0))

        # Determine card style based on winner (match Tab 1 gradient style)
        if winner == player1:
            card_bg = f"background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba({p1_rgb},0.15) 100%);"
            winner_color = p1_color
        elif winner == player2:
            card_bg = f"background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba({p2_rgb},0.15) 100%);"
            winner_color = p2_color
        else:
            card_bg = f"background:linear-gradient(135deg, var(--secondary-background-color) 0%, rgba({tie_rgb},0.1) 100%);"
            winner_color = tie_color

        # Match Tab 1 card base styling (compact padding for mobile)
        card_base = f"border:1px solid rgba(255,255,255,0.2);border-radius:12px;padding:0.75rem;margin-bottom:0.5rem;box-shadow:0 0 0 1px rgba(255,255,255,0.08), inset 0 1px 0 rgba(255,255,255,0.1), 0 4px 20px rgba(0,0,0,0.15);{card_bg}"

        p1_rank = safe_str(row.get(f'{player1} Daily Rank'))
        p2_rank = safe_str(row.get(f'{player2} Daily Rank'))
        p1_score = safe_str(row.get(f'{player1} Score'))
        p2_score = safe_str(row.get(f'{player2} Score'))
        p1_elo = safe_str(row.get(f'{player1} Elo'), "{:.0f}")
        p2_elo = safe_str(row.get(f'{player2} Elo'), "{:.0f}")

        # Header: Win counts on sides, Date and Winner centered
        # 3-column grid: p1 wins | date+winner | p2 wins
        # Winner link (only if not a tie)
        winner_display = player_link(winner) if winner in (player1, player2) else html.escape(winner)
        header_html = f'''
        <div class="duel-header" style="display:grid;grid-template-columns:auto 1fr auto;align-items:center;margin-bottom:0.75rem;padding:0 0.5rem 0.5rem 0.5rem;border-bottom:1px solid rgba(128,128,128,0.35);">
            <div style="display:flex;flex-direction:column;align-items:center;min-width:2.5rem;">
                <span class="duel-win-count" style="font-weight:700;font-size:1.4rem;color:{p1_color};">{p1_cumulative}</span>
                <span class="duel-win-label" style="font-size:0.7rem;text-transform:uppercase;font-weight:600;color:{p1_color};">Duel Wins</span>
            </div>
            <div style="display:flex;flex-direction:column;align-items:center;gap:0.25rem;">
                <span class="duel-date" style="font-weight:600;font-size:1rem;color:var(--text-color);">{date_link_html}</span>
                <span class="duel-winner" style="font-weight:700;color:{winner_color};">🏆 {winner_display}</span>
            </div>
            <div style="display:flex;flex-direction:column;align-items:center;min-width:2.5rem;">
                <span class="duel-win-count" style="font-weight:700;font-size:1.4rem;color:{p2_color};">{p2_cumulative}</span>
                <span class="duel-win-label" style="font-size:0.7rem;text-transform:uppercase;font-weight:600;color:{p2_color};">Duel Wins</span>
            </div>
        </div>
        '''

        # Three-column layout: Player 1 | Crossed Swords | Player 2
        # max-width prevents excessive spreading on wide screens
        p1_link = player_link(player1)
        p2_link = player_link(player2)
        stats_html = f'''
        <div class="duel-stats" style="display:grid;grid-template-columns:1fr auto 1fr;gap:0.5rem;align-items:start;max-width:700px;margin:0 auto;">
            <div style="text-align:center;">
                <div class="duel-player-name" style="font-weight:600;color:{p1_color};margin-bottom:0.5rem;font-size:1.1rem;">{p1_link} <span style="font-weight:500;">({p1_elo})</span></div>
                <div class="duel-player-stats" style="display:flex;justify-content:center;gap:0.75rem;flex-wrap:wrap;">
                    <div style="{stat_layout}"><span class="duel-stat-label" style="{label_style}">Daily Rank</span><span class="duel-stat-value" style="{value_style}">#{p1_rank}</span></div>
                    <div style="{stat_layout}"><span class="duel-stat-label" style="{label_style}">Score</span><span class="duel-stat-value" style="{value_style}">{p1_score}</span></div>
                </div>
            </div>
            <div class="duel-vs" style="display:flex;align-items:center;justify-content:center;font-size:2rem;padding-top:0.25rem;">⚔️</div>
            <div style="text-align:center;">
                <div class="duel-player-name" style="font-weight:600;color:{p2_color};margin-bottom:0.5rem;font-size:1.1rem;">{p2_link} <span style="font-weight:500;">({p2_elo})</span></div>
                <div class="duel-player-stats" style="display:flex;justify-content:center;gap:0.75rem;flex-wrap:wrap;">
                    <div style="{stat_layout}"><span class="duel-stat-label" style="{label_style}">Daily Rank</span><span class="duel-stat-value" style="{value_style}">#{p2_rank}</span></div>
                    <div style="{stat_layout}"><span class="duel-stat-label" style="{label_style}">Score</span><span class="duel-stat-value" style="{value_style}">{p2_score}</span></div>
                </div>
            </div>
        </div>
        '''

        card = f'<div class="duel-card" style="{card_base}">{header_html}{stats_html}</div>'
        cards.append(card)

    return "".join(cards)


def compute_hall_of_fame_stats(df_history):
    """
    Compute Hall of Fame statistics from history data.
    Returns dict with top 10 for each category (including all ties at 10th):
    - most_wins: Players with most rank=1 finishes
    - highest_scores: Single-game highest scores
    - most_games: Players with most games played
    - longest_streaks: Longest consecutive rank=1 win streaks
    """
    if df_history is None or df_history.empty:
        return None

    # Filter to rows where player actually played (has a rank/score)
    df_played = df_history[df_history['rank'].notna()].copy()

    if df_played.empty:
        return None

    def top_n_with_ties(df, value_col, n=10, cols=None):
        """Get top N entries including all ties at the Nth position."""
        if cols is None:
            cols = ['player_name', value_col]
        df_sorted = df.sort_values(value_col, ascending=False)
        if len(df_sorted) <= n:
            return df_sorted[cols].values.tolist()
        # Find the value at the nth position
        nth_value = df_sorted.iloc[n - 1][value_col]
        # Include all entries with value >= nth_value
        result = df_sorted[df_sorted[value_col] >= nth_value][cols]
        return result.values.tolist()

    # 1. Most Wins (total rank=1 finishes per player)
    # Get latest row per player (cumulative wins column)
    latest_per_player = df_history.sort_values('date').groupby('player_name').last().reset_index()
    if 'wins' in latest_per_player.columns:
        most_wins = top_n_with_ties(latest_per_player, 'wins', 10, ['player_name', 'wins'])
    else:
        # Fallback: count rank=1 occurrences
        win_counts = df_played[df_played['rank'] == 1].groupby('player_name').size().reset_index(name='wins')
        most_wins = top_n_with_ties(win_counts, 'wins', 10, ['player_name', 'wins'])

    # 2. Highest Scores (single-game records)
    df_with_scores = df_played[df_played['score'].notna()].copy()
    highest_scores = top_n_with_ties(df_with_scores, 'score', 10, ['player_name', 'score', 'date'])

    # 3. Most Games (total games played per player)
    if 'games_played' in latest_per_player.columns:
        most_games = top_n_with_ties(latest_per_player, 'games_played', 10, ['player_name', 'games_played'])
    else:
        # Fallback: count appearances
        game_counts = df_played.groupby('player_name').size().reset_index(name='games_played')
        most_games = top_n_with_ties(game_counts, 'games_played', 10, ['player_name', 'games_played'])

    # 4. Longest Win Streaks (consecutive rank=1 days)
    # Sort by player and date
    df_sorted = df_played.sort_values(['player_name', 'date'])

    streaks = []
    for player, group in df_sorted.groupby('player_name'):
        group = group.sort_values('date')
        current_streak = 0
        max_streak = 0
        streak_end_date = None
        current_streak_end = None

        for _, row in group.iterrows():
            if row['rank'] == 1:
                current_streak += 1
                current_streak_end = row['date']
                if current_streak > max_streak:
                    max_streak = current_streak
                    streak_end_date = current_streak_end
            else:
                current_streak = 0

        if max_streak > 0:
            streaks.append((player, max_streak, streak_end_date))

    # Sort by streak length and include all ties at 10th position
    streaks.sort(key=lambda x: x[1], reverse=True)
    if len(streaks) <= 10:
        longest_streaks = streaks
    else:
        tenth_value = streaks[9][1]  # Value at 10th position
        longest_streaks = [s for s in streaks if s[1] >= tenth_value]

    # 5. Days at Elo #1 (all players who have held active_rank=1)
    # Count days where each player was Elo #1
    if 'active_rank' in df_history.columns:
        df_elo_1 = df_history[df_history['active_rank'] == 1].copy()
        days_at_elo_1_counts = df_elo_1.groupby('player_name').size().reset_index(name='days')
        days_at_elo_1_counts = days_at_elo_1_counts.sort_values('days', ascending=False)
        days_at_elo_1 = days_at_elo_1_counts[['player_name', 'days']].values.tolist()
    else:
        days_at_elo_1 = []

    return {
        'most_wins': most_wins,
        'highest_scores': highest_scores,
        'most_games': most_games,
        'longest_streaks': longest_streaks,
        'days_at_elo_1': days_at_elo_1,
    }


def generate_hall_of_fame_cards(stats):
    """
    Generate HTML cards for Hall of Fame leaderboards.
    Each card shows top 5 players for a category.
    """
    if stats is None:
        return ""

    def format_number(val):
        """Format large numbers with commas."""
        if pd.isna(val):
            return "-"
        try:
            return f"{int(val):,}"
        except (ValueError, TypeError):
            return str(val)

    # Card styling (matches existing card styles)
    card_style = """
        background: var(--secondary-background-color);
        border: 1px solid rgba(255,255,255,0.15);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    """

    title_style = """
        font-size: 1rem;
        font-weight: 700;
        margin: 0 0 0.75rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid rgba(128,128,128,0.35);
        display: flex;
        align-items: center;
        gap: 0.5rem;
    """

    row_style = """
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.375rem 0;
        border-bottom: 1px solid rgba(128,128,128,0.15);
    """

    rank_style = """
        font-weight: 700;
        font-size: 0.9rem;
        min-width: 1.5rem;
        color-scheme: inherit;
        color: light-dark(#666666, #999999);
    """

    name_style = """
        flex: 1;
        font-weight: 500;
        margin: 0 0.5rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    """

    value_style = """
        font-weight: 700;
        font-size: 1rem;
        color-scheme: inherit;
        color: light-dark(#D93636, #FF6B6B);
    """

    def build_card(title, icon, items, value_formatter=format_number):
        """Build a single Hall of Fame card with proper tie handling."""
        rows_html = ""
        current_rank = 0
        prev_value = None

        for i, item in enumerate(items):
            player = item[0]
            value = item[1]

            # Only increment rank if value is different from previous
            if value != prev_value:
                current_rank = i + 1
                prev_value = value

            # Special medal styling for top 3
            if current_rank == 1:
                rank_display = "🥇"
            elif current_rank == 2:
                rank_display = "🥈"
            elif current_rank == 3:
                rank_display = "🥉"
            else:
                rank_display = f"{current_rank}."

            # Create player link
            player_url = build_url_with_params({"tab": "tracker", "player": player})
            player_link_html = f'<a href="{player_url}" target="_self" class="player-link" style="color: inherit; text-decoration: none;">{html.escape(player)}</a>'

            rows_html += f'''
                <div style="{row_style}">
                    <span style="{rank_style}">{rank_display}</span>
                    <span style="{name_style}">{player_link_html}</span>
                    <span style="{value_style}">{value_formatter(value)}</span>
                </div>
            '''

        return f'''
            <div style="{card_style}">
                <div style="{title_style}">
                    <span style="font-size: 1.2rem;">{icon}</span>
                    <span>{title}</span>
                </div>
                {rows_html}
            </div>
        '''

    cards_html = '<div class="hof-cards-grid">'

    # Most Wins card
    if stats.get('most_wins'):
        cards_html += build_card("Most Wins", "🏆", stats['most_wins'])

    # Highest Scores card
    if stats.get('highest_scores'):
        cards_html += build_card("Highest Scores", "💯", stats['highest_scores'])

    # Most Games card
    if stats.get('most_games'):
        cards_html += build_card("Most Games", "🎮", stats['most_games'])

    # Longest Win Streaks card
    if stats.get('longest_streaks'):
        cards_html += build_card("Longest Win Streaks", "🔥", stats['longest_streaks'])

    # Days at Elo #1 card (shows ALL players who have held #1, not just top 5)
    if stats.get('days_at_elo_1'):
        cards_html += build_card("Days at Elo #1", "👑", stats['days_at_elo_1'])

    cards_html += '</div>'

    return cards_html


# Theme-specific colors (WCAG AA compliant contrast ratios)
DARK_THEME = {
    "bg_primary": "#0E1117",
    "bg_secondary": "#262730",
    "bg_hover": "#3D3D4D",
    "text_primary": "#FAFAFA",
    "text_secondary": "#E0E0E0",  # Improved: ~11:1 contrast vs bg_primary
    "text_muted": "#A0A0A0",       # Improved: ~7:1 contrast vs bg_primary
    # Player colors - Cyan + Amber (vibrant for dark backgrounds)
    "player1": "#22D3EE",         # Cyan 400 - 11.4:1 contrast
    "player2": "#FBBF24",         # Amber 400 - 12.4:1 contrast
    "player1_rgb": "34, 211, 238",  # For rgba() backgrounds
    "player2_rgb": "251, 191, 36",
}

LIGHT_THEME = {
    "bg_primary": "#FFFFFF",
    "bg_secondary": "#F0F2F6",
    "bg_hover": "#E0E2E6",
    "text_primary": "#262730",
    "text_secondary": "#404040",  # Improved: ~10:1 contrast vs bg_primary
    "text_muted": "#666666",       # Improved: ~5.7:1 contrast vs bg_primary
    # Player colors - Cyan + Amber (muted for light backgrounds)
    "player1": "#0891B2",         # Cyan 600 - 4.5:1 contrast
    "player2": "#B45309",         # Amber 700 - 4.8:1 contrast
    "player1_rgb": "8, 145, 178",   # For rgba() backgrounds
    "player2_rgb": "180, 83, 9",
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
        /* Sidebar spacing */
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }
        /* Section headings */
        [data-testid="stSidebar"] h2 {
            margin-top: 0 !important;
            margin-bottom: 0.25rem !important;
        }
        /* Captions stack tightly together */
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            margin-bottom: 0 !important;
        }
        /* Caption containers stack tightly */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {
            margin-bottom: 0 !important;
        }
        /* Dividers: symmetrical spacing to center content between them */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(hr) {
            margin-top: var(--space-md) !important;
            margin-bottom: var(--space-md) !important;
        }
        /* Selectbox container - reduce default margin for tighter layout */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stSelectbox"]) {
            margin-bottom: var(--space-sm) !important;
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
        /* Sidebar spacing */
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: 0.5rem !important;
        }
        [data-testid="stSidebar"] h2 {
            margin-top: 0 !important;
            margin-bottom: 0.25rem !important;
        }
        /* Captions stack tightly together */
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
            margin-bottom: 0 !important;
        }
        /* Caption containers stack tightly */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) {
            margin-bottom: 0 !important;
        }
        /* Dividers: symmetrical spacing to center content between them */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has(hr) {
            margin-top: var(--space-md) !important;
            margin-bottom: var(--space-md) !important;
        }
        /* Selectbox container - reduce default margin for tighter layout */
        [data-testid="stSidebar"] [data-testid="stElementContainer"]:has([data-testid="stSelectbox"]) {
            margin-bottom: var(--space-sm) !important;
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
    style = f"display:inline-block;padding:0.5rem 1rem;background:{bg_color};color:{text_color};text-decoration:none;border:1px solid {border_color};border-radius:0.5rem;font-family:'Source Sans',sans-serif;font-weight:600;font-size:0.9rem;cursor:pointer;width:100%;text-align:center;box-sizing:border-box;"

    return f'<a href="data:text/csv;base64,{b64}" download="{filename}" style="{style}">{label}</a>'


# Custom CSS for visual hierarchy and spacing
# Includes: Gothic fonts, glassmorphism, animations, gradient effects
CUSTOM_CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous">
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --font-display: 'Source Sans', sans-serif;
    --font-body: 'Source Sans', sans-serif;
    --primary-glow: 0 0 20px rgba(255, 107, 107, 0.4);
    --glass-bg: rgba(38, 39, 48, 0.7);
    --glass-border: rgba(255, 107, 107, 0.2);
    /* Spacing tokens */
    --space-xs: 0.25rem;
    --space-sm: 0.5rem;
    --space-md: 1rem;
    --space-lg: 1.5rem;
    --space-xl: 2rem;
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

/* ===== Player Links (click to view in Tracker) ===== */
.player-link {
    color: inherit !important;
    text-decoration: none !important;
    transition: color 0.15s ease;
}
.player-link:hover {
    color: #FF6B6B !important;
    text-decoration: underline !important;
}

/* ===== Date Links (click to view in Dailies) ===== */
.date-link {
    color: inherit !important;
    text-decoration: none !important;
    transition: color 0.15s ease;
}
.date-link:hover {
    color: #3B82F6 !important;
    text-decoration: underline !important;
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
    color-scheme: inherit;
    color: light-dark(#6B7280, #9CA3AF) !important;
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
    opacity: 0.85;
    transition: opacity 0.15s ease !important;
    /* Prevent tabs from shrinking on narrow screens */
    flex-shrink: 0 !important;
    white-space: nowrap !important;
}

.stTabs [data-baseweb="tab"]:hover {
    opacity: 0.95;
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
    padding-top: 3rem;
    padding-bottom: 2rem;
}

.element-container {
    margin-bottom: 0.5rem;
}

/* Tighter vertical spacing - use --space-xs (4px) for related controls */
[data-testid="stVerticalBlock"] {
    gap: 0.25rem !important;
}
/* Horizontal blocks: allow wrapping by default for charts to stack on mobile */
[data-testid="stHorizontalBlock"] {
    gap: 0.5rem !important;
}
/* Tab 1 controls (with date input): keep side-by-side even on mobile */
[data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]) {
    flex-wrap: nowrap !important;
}
/* Only remove min-width for Tab 1 control columns, not chart columns */
[data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]) [data-testid="stColumn"] {
    min-width: 0 !important;
}
/* Tab 2 duel pickers: keep side-by-side even on mobile */
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) {
    flex-wrap: nowrap !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-testid="stColumn"] {
    min-width: 0 !important;
}
/* Remove margin between player label and selectbox in duel pickers */
[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) [data-testid="stElementContainer"]:has([data-testid="stHtml"]) {
    margin-bottom: 0 !important;
}
/* Reduce vertical spacing in Tab 2 (duel pickers, cards, charts) */
[data-testid="stVerticalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="stElementContainer"] {
    margin-bottom: 0.5rem !important;
}
/* Vertical divider between side-by-side chart columns */
[data-testid="stHorizontalBlock"]:has(.stPlotlyChart) {
    color-scheme: inherit;
    gap: 1.5rem !important;
}
[data-testid="stHorizontalBlock"]:has(.stPlotlyChart) > [data-testid="stColumn"]:first-child {
    color-scheme: inherit;
    border-right: 1px solid light-dark(#C0C0C0, #404040);
    padding-right: 1rem;
}
/* Mobile (sm): fully disable chart interaction to prevent scroll hijacking */
@media (max-width: 600px) {
    .stPlotlyChart {
        pointer-events: none !important;
    }
}

/* ===== Radio-as-Tabs Styling ===== */
/* Style horizontal radio buttons to look like native Streamlit tabs */
/* Center the tab bar by making container full-width and centering content */
[data-testid="stElementContainer"]:has([data-testid="stRadio"]) {
    width: 100% !important;
    display: flex !important;
    justify-content: center !important;
    position: relative !important;
}
/* Full-width divider line below tabs */
[data-testid="stElementContainer"]:has([data-testid="stRadio"])::after {
    content: "" !important;
    position: absolute !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 1px !important;
    background: rgba(128, 128, 128, 0.3) !important;
}
[data-testid="stRadio"] [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 0 !important;
    justify-content: center !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label {
    display: flex !important;
    align-items: center !important;
    padding: 0.5rem 0.6rem !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    cursor: pointer !important;
    font-weight: 500 !important;
    font-size: 0.75rem !important;
    color: var(--text-color) !important;
    opacity: 0.6 !important;
    border-bottom: 2px solid transparent !important;
    transition: opacity 0.2s, border-color 0.2s !important;
    white-space: nowrap !important;
}
[data-testid="stRadio"] [role="radiogroup"] > label:hover {
    opacity: 1 !important;
}
/* Selected tab styling - use :has(input:checked) */
[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) {
    opacity: 1 !important;
    border-bottom-color: #FF6B6B !important;
    font-weight: 600 !important;
}
/* Hide the actual radio circle */
[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child {
    display: none !important;
}
/* Mobile sm (≤600px): compact tabs to fit on one row */
@media (max-width: 600px) {
    [data-testid="stRadio"] [role="radiogroup"] > label {
        padding: 0.3rem 0 !important;
        font-size: 0.6rem !important;
        transform: scale(0.85) !important;
        transform-origin: center !important;
        margin: 0 -6px !important;
    }
}
/* Mobile xs (≤450px): extra compact tabs for narrow screens */
@media (max-width: 450px) {
    [data-testid="stRadio"] [role="radiogroup"] > label {
        transform: scale(0.78) !important;
        margin: 0 -10px !important;
    }
}

/* ===== Player Tracker Summary Card ===== */
.tracker-summary {
    background: var(--secondary-background-color);
    border-radius: 12px;
    padding: 1rem;
    border-left: 4px solid #FF6B6B;
}
.tracker-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
}
.tracker-name {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-color);
}
.tracker-rank-badge {
    font-size: 0.875rem;
    font-weight: 700;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    color: white;
}
.tracker-rating {
    font-size: 2.2rem;
    font-weight: 700;
    color-scheme: inherit;
    color: light-dark(#D93636, #FF6B6B);
    line-height: 1.1;
}
.tracker-rating-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color-scheme: inherit;
    color: light-dark(#666666, #999999);
    margin-bottom: 0.75rem;
}
.tracker-stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}
.tracker-stat {
    text-align: center;
    padding: 0.4rem;
    background: rgba(128, 128, 128, 0.1);
    border-radius: 6px;
}
.tracker-stat-value {
    display: block;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-color);
}
.tracker-stat-label {
    display: block;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color-scheme: inherit;
    color: light-dark(#666666, #999999);
}
.tracker-timeline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(128, 128, 128, 0.2);
}
.tracker-timeline-item {
    flex: 1;
    text-align: center;
    padding: 0.4rem;
    border-radius: 6px;
}
.tracker-timeline-item.tracker-first {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
}
.tracker-timeline-item.tracker-last {
    background: rgba(255, 107, 107, 0.15);
    border: 1px solid rgba(255, 107, 107, 0.3);
}
.tracker-timeline-label {
    font-size: 0.6rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color-scheme: inherit;
    color: light-dark(#666666, #999999);
}
.tracker-timeline-date {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--text-color);
}
.tracker-timeline-detail {
    font-size: 0.7rem;
    color-scheme: inherit;
    color: light-dark(#666666, #999999);
}
.tracker-timeline-arrow {
    font-size: 1rem;
    color-scheme: inherit;
    color: light-dark(#999999, #666666);
}
.tracker-chart-label {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
    margin: 0.75rem 0 0.25rem 0;
    padding: 0;
}
@media (max-width: 400px) {
    .tracker-stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .tracker-rating {
        font-size: 1.8rem;
    }
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
/* Typography uses design system scale: Card heading (1.1/1/0.95rem), Label (0.8/0.75/0.7rem) */
[data-testid="stSidebar"] {
    padding: var(--space-sm) !important;  /* Compact: --space-sm instead of --space-md */
    max-width: 360px !important;
}

/* Only set min-width when sidebar is expanded */
[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 320px !important;
}

/* Collapse sidebar properly when closed */
[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
}

[data-testid="stSidebar"] > div:first-child {
    width: 100% !important;
    max-width: 360px !important;
}

/* Sidebar headers - Card heading scale with consistent vertical rhythm */
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-size: 1rem !important;  /* Card heading sm size */
    margin-top: 0 !important;
    margin-bottom: var(--space-sm) !important;
    padding-top: 0 !important;
}

/* Sidebar metadata text - Label scale */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown span {
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;  /* Label lg size */
}

/* Sidebar selectbox value - Body xs scale (fits on one line) */
[data-testid="stSidebar"] .stSelectbox span {
    font-family: var(--font-body) !important;
    font-weight: 400 !important;
    font-size: 0.9rem !important;  /* Body xs size */
}

/* Sidebar captions - Label sm scale with WCAG-compliant contrast */
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
    font-family: var(--font-body) !important;
    font-weight: 500 !important;
    font-size: 0.75rem !important;  /* Label sm size */
    opacity: 1 !important;  /* Full opacity for accessibility - overrides Streamlit's 0.6 */
    margin-top: 0 !important;
    margin-bottom: 0 !important;  /* No gap - let elements stack tightly */
}

/* Consecutive captions - even tighter */
[data-testid="stSidebar"] .stCaption + .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] + [data-testid="stCaptionContainer"] {
    margin-top: calc(-1 * var(--space-xs)) !important;
}

/* Sidebar dividers - accent gradient, container handles spacing */
[data-testid="stSidebar"] hr {
    margin: 0 !important;  /* Container provides balanced spacing */
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent 0%, rgba(255, 107, 107, 0.4) 50%, transparent 100%) !important;
}

/* Sidebar selectbox - consistent spacing and no truncation */
[data-testid="stSidebar"] [data-testid="stSelectbox"] {
    margin-bottom: var(--space-sm) !important;
}

/* Sidebar download button - Label scale with card styling */
[data-testid="stSidebar"] .stDownloadButton button,
[data-testid="stSidebar"] a.download-link {
    font-family: var(--font-body) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;  /* Label lg size */
    letter-spacing: 0.02em;
    border-radius: 8px !important;
    padding: var(--space-sm) var(--space-md) !important;
    transition: all 0.2s ease !important;
}

/* Responsive sidebar typography */
@media (max-width: 400px) {
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        font-size: 0.95rem !important;  /* Card heading xs size */
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown span {
        font-size: 0.75rem !important;  /* Label sm size */
    }
    [data-testid="stSidebar"] .stSelectbox span {
        font-size: 0.9rem !important;  /* Body xs size */
    }
    [data-testid="stSidebar"] .stCaption {
        font-size: 0.7rem !important;  /* Label xs size */
    }
    [data-testid="stSidebar"] .stDownloadButton button,
    [data-testid="stSidebar"] a.download-link {
        font-size: 0.75rem !important;  /* Label sm size */
        padding: var(--space-xs) var(--space-sm) !important;
    }
}

/* ===== Ranking Cards ===== */
.ranking-cards {
    display: block;
    container-type: inline-size;
    container-name: cards;
}

/* Responsive stats grid: 8 columns on desktop, 4 on mobile */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 0.5rem;
    margin-top: 0.5rem;
}

/* Align stat values to bottom when labels wrap */
.stats-grid > div {
    display: flex !important;
    flex-direction: column !important;
    justify-content: flex-start !important;
    align-items: center !important;
    min-height: 3.5rem;
}
.stats-grid > div span:last-child {
    margin-top: auto;
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
    display: flex;
    flex-direction: column;
    align-items: center;
}
.card-rating .rating-label {
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    /* No opacity - inherits color from parent for WCAG compliance */
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
    margin-bottom: 0.5rem;
}

/* Tab 1 controls compression - related controls use --space-sm */
[data-testid="stDateInput"] {
    margin-bottom: 0.5rem !important;
}
[data-testid="stDateInput"] + div [data-testid="stHorizontalBlock"] {
    margin-top: 0 !important;
}
.sort-controls + div [data-testid="stToggle"] {
    margin-top: 0.25rem !important;
    margin-bottom: 0.5rem !important;
}

/* Removed: Hidden table CSS - tables now fully removed from code */

/* Back to top anchor - hide container spacing */
#top {
    scroll-margin-top: 100vh;
}
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.back-to-top) {
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
    overflow: visible;
}
[data-testid="stMarkdownContainer"]:has(.back-to-top) p {
    margin: 0 !important;
    line-height: 0 !important;
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

/* Floating share button - position the popover container */
[data-testid="stMain"] [data-testid="stPopover"] {
    position: fixed !important;
    bottom: 2rem !important;
    left: 2rem !important;
    width: 48px !important;
    height: 48px !important;
    z-index: 1000 !important;
}
/* Style the button as a circle */
[data-testid="stMain"] [data-testid="stPopover"] button {
    width: 48px !important;
    height: 48px !important;
    min-width: 48px !important;
    min-height: 48px !important;
    max-width: 48px !important;
    max-height: 48px !important;
    border-radius: 50% !important;
    background: #3B82F6 !important;
    color: white !important;
    padding: 0 !important;
    border: none !important;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4) !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
    overflow: hidden !important;
}
[data-testid="stMain"] [data-testid="stPopover"] button:hover {
    transform: scale(1.1) !important;
    box-shadow: 0 6px 16px rgba(59, 130, 246, 0.5) !important;
    background: #2563EB !important;
}
[data-testid="stMain"] [data-testid="stPopover"] button:active {
    transform: scale(0.95) !important;
}
/* Hide the dropdown arrow - target by material icon testid */
[data-testid="stMain"] [data-testid="stPopover"] [data-testid="stIconMaterial"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
    height: 0 !important;
}
/* Also hide the parent container of the arrow */
[data-testid="stMain"] [data-testid="stPopover"] button > div > div:last-child {
    display: none !important;
}
/* Center the emoji and make it bright */
[data-testid="stMain"] [data-testid="stPopover"] button > div {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
    text-align: center !important;
    margin: 0 !important;  /* Remove -5px right margin Streamlit adds for arrow */
}
[data-testid="stMain"] [data-testid="stPopover"] button > div > div:first-child {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
}
[data-testid="stMain"] [data-testid="stPopover"] [data-testid="stMarkdownContainer"] {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
}
[data-testid="stMain"] [data-testid="stPopover"] [data-testid="stMarkdownContainer"] p {
    margin: 0 !important;
    padding: 0 !important;
    font-size: 1.2rem !important;
    line-height: 1 !important;
    text-align: center !important;
    filter: brightness(1.3) saturate(1.2) !important;
    text-shadow: 0 0 2px rgba(255,255,255,0.5) !important;
}
/* Hide the element container for the floating button */
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has([data-testid="stPopover"]) {
    margin: 0 !important;
    padding: 0 !important;
    height: 0 !important;
    overflow: visible !important;
    width: 0 !important;
}
/* Share popover content - mobile responsive */
[data-testid="stPopoverBody"] {
    max-width: calc(100vw - 4rem) !important;
    width: auto !important;
    min-width: 200px !important;
}
[data-testid="stPopoverBody"] [data-testid="stCode"] {
    max-width: 100% !important;
}
[data-testid="stPopoverBody"] [data-testid="stCode"] code {
    white-space: pre-wrap !important;
    word-break: break-all !important;
    font-size: 0.8rem !important;
}
/* Make copy button always visible (parent has opacity:0 by default) */
[data-testid="stPopoverBody"] div:has(> [data-testid="stCodeCopyButton"]) {
    opacity: 1 !important;
}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] {
    font-size: 0.85rem !important;
}

/* Container-responsive: 4-column grid when container ≤600px */
@container cards (max-width: 600px) {
    /* Tab 1 ranking cards */
    .stats-grid {
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 0.375rem !important;
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
        font-size: 0.95rem !important;
    }
    .card-rating {
        grid-column: 4 !important;
        justify-self: center !important;
        text-align: center !important;
        font-size: 1rem !important;
    }
    /* Design system: sm breakpoint typography */
    .stats-grid > div span:first-child {
        font-size: 0.75rem !important;
    }
    .stats-grid > div span:last-child {
        font-size: 1.2rem !important;
    }
    /* Design system: sm breakpoint padding (0.75rem) */
    .ranking-cards > div {
        padding: 0.75rem !important;
    }
    /* Tab 2 duel cards - sm breakpoint */
    .duel-player-name {
        font-size: 0.95rem !important;
    }
    .duel-stat-label {
        font-size: 0.75rem !important;
    }
    .duel-stat-value {
        font-size: 1.2rem !important;
    }
    .duel-win-count {
        font-size: 1.2rem !important;
    }
    .duel-win-label {
        font-size: 0.65rem !important;
    }
    .duel-date {
        font-size: 0.9rem !important;
    }
    .duel-vs {
        font-size: 1.5rem !important;
    }
    .duel-player-stats {
        gap: 0.5rem !important;
    }
}

/* Container-responsive: extra compact when container ≤400px */
@container cards (max-width: 400px) {
    /* Tab 1 ranking cards */
    .card-name-text {
        font-size: 0.9rem !important;
    }
    .card-rating {
        font-size: 0.95rem !important;
    }
    /* Design system: xs breakpoint typography */
    .stats-grid > div span:first-child {
        font-size: 0.7rem !important;
    }
    .stats-grid > div span:last-child {
        font-size: 1.1rem !important;
    }
    /* Design system: xs breakpoint padding (0.5rem) */
    .ranking-cards > div {
        padding: 0.5rem !important;
    }
    .stats-grid {
        gap: 0.25rem !important;
    }
    /* Tab 2 duel cards - xs breakpoint */
    .duel-player-name {
        font-size: 0.9rem !important;
    }
    .duel-stat-label {
        font-size: 0.7rem !important;
    }
    .duel-stat-value {
        font-size: 1.1rem !important;
    }
    .duel-win-count {
        font-size: 1.1rem !important;
    }
    .duel-win-label {
        font-size: 0.6rem !important;
    }
    .duel-date {
        font-size: 0.85rem !important;
    }
    .duel-vs {
        font-size: 1.25rem !important;
    }
    .duel-player-stats {
        gap: 0.35rem !important;
    }
}

/* Large viewport (lg breakpoint >900px) */
@media (min-width: 900px) {
    /* Tab 1 ranking cards */
    .card-name-text {
        font-size: 1.1rem !important;
    }
    .card-rating {
        font-size: 1.25rem !important;
    }
    .card-rank {
        font-size: 1.1rem !important;
    }
    /* Data values already 1.4rem via inline styles - no override needed */
    /* Tab 2 duel cards - lg breakpoint */
    .duel-player-name {
        font-size: 1.1rem !important;
    }
    .duel-stat-value {
        font-size: 1.4rem !important;
    }
    .duel-win-count {
        font-size: 1.4rem !important;
    }
}

/* Hall of Fame cards grid */
.hof-cards-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}

@media (max-width: 700px) {
    .hof-cards-grid {
        grid-template-columns: 1fr;
    }
}

.hof-cards-grid a.player-link:hover {
    color: #FF6B6B !important;
    text-decoration: underline !important;
}

/* Hall of Fame chart card */
.hof-chart-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px 12px 0 0;
    padding: 1rem 1rem 0 1rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    margin-top: 0.5rem;
}

.hof-chart-header {
    font-size: 1rem;
    font-weight: 700;
    margin: 0;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(128,128,128,0.35);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Style the Plotly chart container that follows the card header */
[data-testid="stElementContainer"]:has(.hof-chart-card) + [data-testid="stElementContainer"] {
    background: var(--secondary-background-color);
    border: 1px solid rgba(255,255,255,0.15);
    border-top: none;
    border-radius: 0 0 12px 12px;
    padding: 0.75rem 1rem 1rem 1rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
    margin-top: -1rem !important;
}
</style>
"""


def apply_plotly_style(fig, add_gradient_fill=False):
    """Apply consistent styling to Plotly figures following the design system.

    Typography (from CLAUDE.md design system):
    - Font: System font stack (matches "System" in design system)
    - Label: 0.8rem (~13px), weight 500
    - Data value: 1.4rem (~22px), weight 700

    Text colors are NOT explicitly set, allowing Streamlit to inject theme-aware
    colors automatically. Only structural elements (grids, backgrounds) use
    explicit neutral colors.
    """
    # System font stack (design system "System" font)
    system_font = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

    # Structural colors that work on both light and dark backgrounds
    grid_color = "rgba(128, 128, 128, 0.4)"  # Neutral gray grid
    line_color = "rgba(128, 128, 128, 0.3)"  # Neutral gray lines
    legend_bg = "rgba(128, 128, 128, 0.15)"  # Semi-transparent neutral
    hover_bg = "rgba(50, 50, 50, 0.9)"  # Dark hover for readability
    hover_text = "#FFFFFF"  # White text on dark hover background

    # Design system font weights
    label_weight = 500   # Label style
    heading_weight = 600  # Card heading style

    # Design system font sizes (converted from rem, assuming 16px base)
    label_size = 13      # 0.8rem ≈ 13px
    body_size = 16       # 1rem = 16px

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=system_font, size=body_size, weight=label_weight),
        xaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(family=system_font, size=label_size, weight=label_weight),
            title_font=dict(family=system_font, size=label_size, weight=heading_weight),
            showgrid=True,
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=grid_color,
            linecolor=line_color,
            tickfont=dict(family=system_font, size=label_size, weight=label_weight),
            title_font=dict(family=system_font, size=label_size, weight=heading_weight),
            showgrid=True,
            zeroline=False,
        ),
        legend=dict(
            title_text="",  # Remove "Player" title
            font=dict(family=system_font, size=label_size, weight=heading_weight),
            bgcolor="rgba(0,0,0,0)",  # Transparent background
            borderwidth=0,  # No border
        ),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor="rgba(0,0,0,0)",  # No border
            font=dict(color=hover_text, family=system_font, size=14, weight=heading_weight),
        ),
        dragmode=False,  # Disable pan/zoom to prevent scroll hijacking on mobile
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
    # Inject custom CSS (static) - use st.html() to avoid markdown parsing of CSS comments
    st.html(CUSTOM_CSS)

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
            /* Banner header - compact, full-width, always horizontal, centered */
            .dashboard-banner {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 0.75rem;
                padding: 0;
                margin: 0 0 var(--space-md) 0;  /* 16px bottom margin per design system */
            }}
            .dashboard-banner-link,
            .dashboard-banner-link:hover,
            .dashboard-banner-link:visited {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: inherit;
                text-decoration: none !important;
                color: inherit;
                cursor: pointer;
            }}
            .dashboard-banner-link *,
            .dashboard-banner-link:hover * {{
                text-decoration: none !important;
            }}
            .dashboard-banner-link:hover {{
                opacity: 0.85;
            }}
            [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.dashboard-banner) {{
                margin: 0 !important;  /* Override Streamlit default - spacing controlled via .dashboard-banner */
            }}
            .dashboard-logo {{
                width: 50px;
                height: auto;
                filter: drop-shadow(0 0 8px rgba(255, 107, 107, 0.3));
                flex-shrink: 0;
            }}
            .dashboard-title-group {{
                display: flex;
                flex-direction: column;
                align-items: flex-start;
                gap: 0;
            }}
            .dashboard-title {{
                font-family: 'Source Sans', sans-serif !important;
                font-size: 1.25rem !important;
                font-weight: 700 !important;
                line-height: 1.1 !important;
                margin: 0 !important;
                padding: 0 !important;
                color-scheme: inherit;
                --gradient-start: light-dark(#8B2942, #FAFAFA);
                --gradient-mid: light-dark(#C53030, #FF6B6B);
                --gradient-end: light-dark(#92400E, #FFD700);
                background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-mid) 50%, var(--gradient-end) 100%) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                background-clip: text !important;
                letter-spacing: 0.02em;
            }}
            .dashboard-subtitle {{
                font-size: 0.55rem;
                font-weight: 400;
                line-height: 1.2;
                color-scheme: inherit;
                color: light-dark(#6B7280, #9CA3AF);
                margin: 0 !important;
                padding: 0 !important;
                letter-spacing: 0.04em;
            }}
            /* Scale up banner on wider viewports (sm breakpoint = 600px) */
            @media (min-width: 600px) {{
                .dashboard-banner {{
                    gap: 1rem;  /* --space-md */
                }}
                .dashboard-logo {{
                    width: 60px;
                }}
                .dashboard-title {{
                    font-size: 1.5rem !important;
                }}
                .dashboard-subtitle {{
                    font-size: 0.7rem;
                }}
            }}
            /* Hide the anchor link inside the title */
            .dashboard-title [data-testid="stHeaderActionElements"] {{
                display: none !important;
            }}
            /* Hide Streamlit header action elements on mobile (sm) */
            @media (max-width: 600px) {{
                [data-testid="stHeaderActionElements"] {{
                    display: none !important;
                }}
            }}
        </style>
        <div class="dashboard-banner">
            <a href="?" class="dashboard-banner-link" target="_self" title="Clear filters and return to Rankings">
                <img src="data:image/png;base64,{logo_b64}" class="dashboard-logo">
                <div class="dashboard-title-group">
                    <h1 class="dashboard-title">DFTL Rankings</h1>
                    <p class="dashboard-subtitle">Elo-based leaderboard</p>
                </div>
            </a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.title("DFTL Rankings")

    # Back-to-top anchor and button (always rendered)
    st.markdown('<a id="top"></a><a href="#top" class="back-to-top" title="Back to top">↑</a>', unsafe_allow_html=True)

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

        st.caption(f"Data range: {min_date} to {max_date}")
        st.caption(f"Players in Dataset: {len(all_players)}")

        # Export Data section
        st.markdown("---")
        st.markdown('<div style="padding-top: 0.3rem;"></div>', unsafe_allow_html=True)
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

        # Help link
        st.markdown("---")
        st.markdown(
            '<div style="padding: 0.5rem 0;">'
            '<a href="https://github.com/NPrime808/DFTL_Ranking_Dashboard#faq" target="_blank">📖 FAQ & Glossary</a>'
            '</div>',
            unsafe_allow_html=True
        )

        # Attribution
        st.markdown("---")
        st.caption("Made with 🫶 by N Prime")

    # Use full date range
    df_filtered = df_leaderboard.copy()

    # --- Main Content ---
    # Tab options (radio-as-tabs for persistence)
    TAB_OPTIONS = [
        "🏅 Rankings",
        "⚔️ Duels",
        "👤 Tracker",
        "📊 Dailies",
        "🏆 Hall of Fame"
    ]

    # Tab name to URL slug mapping (for cleaner URLs)
    TAB_SLUGS = {
        "🏅 Rankings": "rankings",
        "⚔️ Duels": "duels",
        "👤 Tracker": "tracker",
        "📊 Dailies": "dailies",
        "🏆 Hall of Fame": "hall-of-fame"
    }
    SLUG_TO_TAB = {v: k for k, v in TAB_SLUGS.items()}

    # Define which query params are relevant to each tab
    TAB_PARAMS = {
        "rankings": ["date"],
        "duels": ["player1", "player2"],
        "tracker": ["player"],
        "dailies": ["date"],
        "hall-of-fame": [],
    }
    ALL_TAB_PARAMS = set(p for params in TAB_PARAMS.values() for p in params)

    # Read tab from URL query params (persists across reloads)
    url_tab = st.query_params.get("tab", "rankings")
    default_tab = SLUG_TO_TAB.get(url_tab, TAB_OPTIONS[0])

    # Radio buttons styled as tabs (CSS makes them look like native tabs)
    active_tab = st.radio(
        "Navigation",
        TAB_OPTIONS,
        index=TAB_OPTIONS.index(default_tab),
        horizontal=True,
        label_visibility="collapsed",
        key="tab_selector"
    )

    # Map widget session state keys to their corresponding URL param names
    # This allows saving widget values when switching tabs (without URL auto-sync)
    WIDGET_TO_PARAM = {
        "rankings": {"elo_ranking_date": "date"},
        "dailies": {"dailies_date": "date"},
        "tracker": {"tab4_player_select": "player"},
        "duels": {"duel_player1": "player1", "duel_player2": "player2"},
    }

    # Smart tab switching: save/restore params per tab, keep URLs clean
    new_slug = TAB_SLUGS.get(active_tab, "rankings")
    if url_tab != new_slug:
        # Save current tab's widget values to session state before switching
        widget_map = WIDGET_TO_PARAM.get(url_tab, {})
        for widget_key, param in widget_map.items():
            if widget_key in st.session_state and st.session_state[widget_key] is not None:
                value = st.session_state[widget_key]
                # Format dates as strings
                if hasattr(value, 'strftime'):
                    value = value.strftime('%Y-%m-%d')
                st.session_state[f"saved_param_{url_tab}_{param}"] = value

        # Clear all tab-specific params from URL
        for param in ALL_TAB_PARAMS:
            if param in st.query_params:
                del st.query_params[param]

        # Restore saved params for the new tab (to URL for deep linking)
        for param in TAB_PARAMS.get(new_slug, []):
            saved_key = f"saved_param_{new_slug}_{param}"
            if saved_key in st.session_state:
                st.query_params[param] = st.session_state[saved_key]

        # Update tab param
        st.query_params["tab"] = new_slug

    # --- Tab 4: Steam Leaderboards ---
    if active_tab == "📊 Dailies":
        # Date selector for specific day
        available_dates = sorted(df_filtered['date'].dt.date.unique(), reverse=True)
        if available_dates:
            # Check for date in URL query params (e.g., ?tab=dailies&date=2024-01-15)
            url_date = st.query_params.get("date", None)
            default_date = available_dates[0]  # Most recent by default

            if url_date:
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(url_date, '%Y-%m-%d').date()
                    if parsed_date in available_dates:
                        default_date = parsed_date
                except ValueError:
                    pass  # Invalid date format, use default

            # Calendar date picker
            selected_date = st.date_input(
                "Select date",
                value=default_date,
                min_value=available_dates[-1],
                max_value=available_dates[0],
                key="dailies_date"
            )

            # Note: Date is saved to session state on tab switch, not synced to URL on every change
            # This prevents browser history pollution while still enabling deep linking via date clicks

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

                # Sort by daily rank (natural order for leaderboard)
                df_day_sorted = df_day.sort_values('rank', ascending=True, na_position='last')

                # Display as cards
                has_rating = 'rating' in df_day.columns
                has_active_rank = 'active_rank' in df_day.columns
                cards_html = generate_leaderboard_cards(df_day_sorted, has_rating=has_rating, has_active_rank=has_active_rank)
                st.markdown(f'<div class="ranking-cards">{cards_html}</div>', unsafe_allow_html=True)
        else:
            st.warning("No data available for the selected date range.")

    # --- Tab 1: Elo Rankings ---
    if active_tab == "🏅 Rankings":
        if df_history is not None and 'active_rank' in df_history.columns:
            # Date picker and sort on same row
            available_dates = sorted(df_history['date'].dt.date.unique(), reverse=True)

            # Check for date in URL query params (shared with Dailies tab)
            url_date = st.query_params.get("date", None)
            default_ranking_date = available_dates[0]  # Most recent by default

            if url_date:
                try:
                    from datetime import datetime
                    parsed_date = datetime.strptime(url_date, '%Y-%m-%d').date()
                    if parsed_date in available_dates:
                        default_ranking_date = parsed_date
                except ValueError:
                    pass  # Invalid date format, use default

            # Sort options: display name -> (column, default_ascending)
            sort_options = {
                "Elo": ("rating", False),
                "Games": ("games_played", False),
                "Wins": ("wins", False),
                "Win %": ("win_rate", False),
                "Top 10": ("top_10s", False),
                "Top 10 %": ("top_10s_rate", False),
                "Avg Rank": ("avg_daily_rank", True),
                "7-Game Avg": ("last_7", True),
                "Stability": ("consistency", True),
            }

            col_date, col_sort = st.columns([2, 3])
            with col_date:
                selected_ranking_date = st.date_input(
                    "Date",
                    value=default_ranking_date,
                    min_value=available_dates[-1],
                    max_value=available_dates[0],
                    key="elo_ranking_date"
                )
                # Note: Date saved to session state on tab switch, not synced to URL on every change
            with col_sort:
                selected_sort = st.selectbox(
                    "Sort by",
                    options=list(sort_options.keys()),
                    index=0,
                    key="card_sort"
                )

            # Load data for selected date
            df_date_history = df_history[df_history['date'].dt.date == selected_ranking_date].copy()

            if df_date_history.empty:
                st.info(f"No ranking data for {selected_ranking_date}. Try another date.")
            else:
                # Toggle to show unranked players
                show_unranked = st.toggle("Show Unranked Players", value=True, help="Players with <7 games or inactive >7 days")

                # Use "Best" sort direction (defined in sort_options)
                sort_column, sort_ascending = sort_options[selected_sort]

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
                st.plotly_chart(fig_dist, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

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
    if active_tab == "👤 Tracker":
        if df_history is not None:
            # Check for player in URL query params (e.g., ?tab=tracker&player=Bidderlyn)
            url_player = st.query_params.get("player", None)
            player_index = None

            if url_player and url_player in players_by_rating:
                player_index = players_by_rating.index(url_player)
            elif 'tracker_default_player' not in st.session_state:
                # Pre-select random player from top 10 on first load (persists during session)
                top_n = min(10, len(players_by_rating))
                if top_n >= 1:
                    player_index = random.randint(0, top_n - 1)
                    st.session_state.tracker_default_player = player_index

            # Use URL player, session state, or None
            if player_index is None:
                player_index = st.session_state.get('tracker_default_player', None)

            # Player selector (single selection)
            selected_player = st.selectbox(
                "Select a player",
                options=players_by_rating,
                index=player_index,
                placeholder="Choose a player...",
                key="tab4_player_select"
            )
            # Note: Player saved to session state on tab switch, not synced to URL on every change

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

                        # Get current Elo rank
                        current_player_rating = df_ratings[df_ratings['player_name'] == selected_player]
                        if not current_player_rating.empty and pd.notna(current_player_rating.iloc[0]['active_rank']):
                            elo_rank = int(current_player_rating.iloc[0]['active_rank'])
                            elo_rank_str = f"#{elo_rank}"
                        else:
                            elo_rank_str = "—"

                        # Prepare metric values
                        current_rating = latest['rating']
                        games = int(latest['games_played'])
                        wins = int(latest['wins'])
                        win_rate = latest['win_rate']
                        top_10s = int(latest['top_10s'])
                        top_10_rate = latest['top_10s_rate']
                        avg_rank = latest['avg_daily_rank']
                        last_7 = latest['last_7']
                        consistency = latest['consistency']

                        # Pre-format optional values for f-string
                        avg_rank_str = f"{avg_rank:.1f}" if pd.notna(avg_rank) else "N/A"
                        last_7_str = f"{last_7:.1f}" if pd.notna(last_7) else "N/A"
                        consistency_str = f"{consistency:.1f}" if pd.notna(consistency) else "N/A"

                        # First/Last game data
                        sorted_games = df_player_played.sort_values('date')
                        first_game = sorted_games.iloc[0]
                        last_game = sorted_games.iloc[-1]

                        first_date = first_game['date']
                        first_date_link = daily_link(first_date)
                        first_rank = int(first_game['rank'])
                        first_rating = first_game['rating']

                        last_date = last_game['date']
                        last_date_link = daily_link(last_date)
                        last_rank = int(last_game['rank'])
                        last_rating = last_game['rating']

                        # --- Compact Player Summary Card ---
                        summary_html = f"""
                        <div class="tracker-summary">
                            <div class="tracker-header">
                                <div class="tracker-name">{selected_player}</div>
                                <div class="tracker-rank-badge" style="background: {ACCENT_COLORS['primary']};">{elo_rank_str}</div>
                            </div>
                            <div class="tracker-rating">{current_rating:.0f}</div>
                            <div class="tracker-rating-label">Elo Rating</div>
                            <div class="tracker-stats-grid">
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{games}</span>
                                    <span class="tracker-stat-label">Games</span>
                                </div>
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{wins}</span>
                                    <span class="tracker-stat-label">Wins ({win_rate:.0f}%)</span>
                                </div>
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{top_10s}</span>
                                    <span class="tracker-stat-label">Top 10 ({top_10_rate:.0f}%)</span>
                                </div>
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{avg_rank_str}</span>
                                    <span class="tracker-stat-label">Avg Rank</span>
                                </div>
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{last_7_str}</span>
                                    <span class="tracker-stat-label">7-Game Avg</span>
                                </div>
                                <div class="tracker-stat">
                                    <span class="tracker-stat-value">{consistency_str}</span>
                                    <span class="tracker-stat-label">Stability</span>
                                </div>
                            </div>
                            <div class="tracker-timeline">
                                <div class="tracker-timeline-item tracker-first">
                                    <div class="tracker-timeline-label">First</div>
                                    <div class="tracker-timeline-date">{first_date_link}</div>
                                    <div class="tracker-timeline-detail">#{first_rank} • {first_rating:.0f}</div>
                                </div>
                                <div class="tracker-timeline-arrow">→</div>
                                <div class="tracker-timeline-item tracker-last">
                                    <div class="tracker-timeline-label">Last</div>
                                    <div class="tracker-timeline-date">{last_date_link}</div>
                                    <div class="tracker-timeline-detail">#{last_rank} • {last_rating:.0f}</div>
                                </div>
                            </div>
                        </div>
                        """
                        st.html(summary_html)

                        # --- Rating Trajectory Chart ---
                        st.html('<p class="tracker-chart-label">Elo Rating History</p>')
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
                        st.plotly_chart(fig_rating, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

                        # --- Daily Rank History Chart (Bar Chart) ---
                        st.html('<p class="tracker-chart-label">Daily Rank History</p>')

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
                        st.plotly_chart(fig_rank, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

                        # --- Game History Cards ---
                        # Sort controls - column and direction combined
                        sort_options = {
                            "Recent": ("date", False),
                            "Oldest": ("date", True),
                            "Daily Rank": ("rank", True),
                            "Score": ("score", False),
                        }

                        col_label, col_sort = st.columns([1, 2])
                        with col_label:
                            st.html('<p class="tracker-chart-label" style="margin-top: 0.5rem;">Game History</p>')
                        with col_sort:
                            selected_sort = st.selectbox(
                                "Sort",
                                options=list(sort_options.keys()),
                                index=0,
                                key="history_sort",
                                label_visibility="collapsed"
                            )

                        sort_column, sort_ascending = sort_options[selected_sort]
                        # Daily Rank: secondary sort by score (highest first within same rank)
                        if selected_sort == "Daily Rank":
                            df_table = df_player_played.sort_values(
                                ['rank', 'score'],
                                ascending=[True, False],
                                na_position='last'
                            )
                        else:
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
    if active_tab == "🏆 Hall of Fame":
        if df_history is not None and 'active_rank' in df_history.columns:
            # Hall of Fame leaderboard cards
            hof_stats = compute_hall_of_fame_stats(df_history)
            if hof_stats:
                hof_cards_html = generate_hall_of_fame_cards(hof_stats)
                st.html(hof_cards_html)

            # Use pre-computed active_rank from history data
            # Filter to players with an active_rank (only active players have ranks)
            df_history_active = df_history[df_history['active_rank'].notna()].copy()

            # Filter to top 10 active ranks only
            df_top10 = df_history_active[df_history_active['active_rank'] <= 10].copy()

            # Elo #1 evolution chart - shows who held #1 over time (all history)
            df_rank1 = df_top10[df_top10['active_rank'] == 1].copy()
            df_rank1 = df_rank1.sort_values('date')

            # Card header for the chart
            st.html('''
                <div class="hof-chart-card">
                    <div class="hof-chart-header">
                        <span style="font-size: 1.2rem;">📈</span>
                        <span>Elo #1 Timeline</span>
                    </div>
                </div>
            ''')

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
                st.plotly_chart(fig_rank1, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
        else:
            st.warning("Active rank history data not available.")

    # --- Tab 2: Daily Duels ---
    if active_tab == "⚔️ Duels":
        if df_history is not None:
            # Check for players in URL query params (e.g., ?tab=duels&player1=Bidderlyn&player2=Siker_7)
            url_player1 = st.query_params.get("player1", None)
            url_player2 = st.query_params.get("player2", None)

            p1_index = None
            p2_index = None

            # If query params provided, use them
            if url_player1 and url_player1 in players_by_rating:
                p1_index = players_by_rating.index(url_player1)
            if url_player2 and url_player2 in players_by_rating:
                p2_index = players_by_rating.index(url_player2)

            # If no query params (or invalid), use session state or random selection
            if p1_index is None or p2_index is None:
                if 'duel_default_p1' not in st.session_state:
                    top_n = min(10, len(players_by_rating))
                    if top_n >= 2:
                        idx1, idx2 = random.sample(range(top_n), 2)
                        st.session_state.duel_default_p1 = idx1
                        st.session_state.duel_default_p2 = idx2
                    else:
                        st.session_state.duel_default_p1 = None
                        st.session_state.duel_default_p2 = None

                if p1_index is None:
                    p1_index = st.session_state.get('duel_default_p1', None)
                if p2_index is None:
                    p2_index = st.session_state.get('duel_default_p2', None)

            # Get theme colors (same source as duel cards for consistency)
            duel_colors = get_theme_colors()
            p1_label_color = duel_colors.get("player1", "#0891B2")
            p2_label_color = duel_colors.get("player2", "#B45309")

            col_p1, col_p2 = st.columns([1, 1])

            with col_p1:
                st.html(f'<p style="font-size: 0.875rem; font-weight: 600; margin: 0; color: {p1_label_color};">Player 1</p>')
                player1 = st.selectbox(
                    "Player 1",
                    options=players_by_rating,
                    index=p1_index,
                    placeholder="Choose player...",
                    key="duel_player1",
                    label_visibility="collapsed"
                )

            with col_p2:
                st.html(f'<p style="font-size: 0.875rem; font-weight: 600; margin: 0; color: {p2_label_color};">Player 2</p>')
                player2 = st.selectbox(
                    "Player 2",
                    options=players_by_rating,
                    index=p2_index,
                    placeholder="Choose player...",
                    key="duel_player2",
                    label_visibility="collapsed"
                )
            # Note: Players saved to session state on tab switch, not synced to URL on every change

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

                        # Last Encounter section - show most recent duel card with full win tally
                        df_duel_recent_first = df_duel.sort_values('Date', ascending=False)
                        theme_colors = get_theme_colors()
                        last_card_html = generate_duel_cards(df_duel_recent_first, player1, player2, colors=theme_colors, limit=1, last_encounter_label=True)
                        st.html(f'<div class="ranking-cards">{last_card_html}</div>')

                        # --- Prepare both charts data first, then display side-by-side ---

                        # Elo chart data
                        df_p1_chart = df_p1_played[['date', 'rating']].copy()
                        df_p1_chart['player'] = player1
                        df_p2_chart = df_p2_played[['date', 'rating']].copy()
                        df_p2_chart['player'] = player2
                        df_elo_compare = pd.concat([df_p1_chart, df_p2_chart]).sort_values('date')

                        elo_colors = get_theme_colors()
                        fig_elo = px.line(
                            df_elo_compare,
                            x='date',
                            y='rating',
                            color='player',
                            markers=True,
                            labels={'date': 'Date', 'rating': 'Elo Rating', 'player': 'Player'},
                            color_discrete_map={player1: elo_colors["player1"], player2: elo_colors["player2"]}
                        )
                        fig_elo.update_traces(
                            hovertemplate='%{fullData.name}: %{y:.0f}<extra></extra>',
                            marker=dict(size=8, line=dict(width=1, color='rgba(255, 255, 255, 0.3)')),
                            line=dict(width=2),
                        )
                        apply_plotly_style(fig_elo)
                        fig_elo.update_layout(
                            hovermode='x unified',
                            height=280,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(weight=600)),
                            margin=dict(l=20, r=60, t=30, b=20)
                        )
                        # X-axis shows one tick per month; hover shows full date
                        fig_elo.update_xaxes(title="", tickformat="%b", hoverformat="%b %d, %Y", tickangle=0, dtick="M1")
                        fig_elo.update_yaxes(title="")
                        fig_elo.add_hline(y=1500, line_dash="dash", line_color="rgba(128, 128, 128, 0.5)", annotation_text="Baseline", annotation_font=dict(weight=600))

                        # Score chart data
                        score_colors = get_theme_colors()
                        dates_sorted = sorted(common_dates)
                        p1_scores_raw = []
                        p2_scores_raw = []

                        for date in dates_sorted:
                            p1_data = df_p1_played[df_p1_played['date'].dt.date == date].iloc[0]
                            p2_data = df_p2_played[df_p2_played['date'].dt.date == date].iloc[0]
                            p1_scores_raw.append(p1_data['score'])
                            p2_scores_raw.append(p2_data['score'])

                        all_scores = p1_scores_raw + p2_scores_raw
                        score_cap = np.percentile(all_scores, 90) * 1.5 if len(all_scores) > 0 else 50000
                        score_cap = max(score_cap, 1000)

                        p1_scores_display, p2_scores_display = [], []
                        p1_colors, p2_colors = [], []
                        p1_patterns, p2_patterns = [], []

                        for i, date in enumerate(dates_sorted):
                            p1_score, p2_score = p1_scores_raw[i], p2_scores_raw[i]
                            p1_scores_display.append(min(p1_score, score_cap))
                            p2_scores_display.append(-min(p2_score, score_cap))

                            if p1_score > p2_score:
                                p1_colors.append(score_colors["player1"])
                                p2_colors.append("rgba(128, 128, 128, 0.4)")
                            elif p2_score > p1_score:
                                p1_colors.append("rgba(128, 128, 128, 0.4)")
                                p2_colors.append(score_colors["player2"])
                            else:
                                p1_colors.append("rgba(128, 128, 128, 0.6)")
                                p2_colors.append("rgba(128, 128, 128, 0.6)")

                            p1_patterns.append("/" if p1_score > score_cap else "")
                            p2_patterns.append("/" if p2_score > score_cap else "")

                        fig_score = go.Figure()
                        fig_score.add_trace(go.Bar(name=player1, x=dates_sorted, y=p1_scores_display,
                            marker=dict(color=p1_colors, line=dict(width=1, color='rgba(255,255,255,0.3)'), pattern=dict(shape=p1_patterns, solidity=0.5)),
                            customdata=p1_scores_raw, hovertemplate=f'{player1}: %{{customdata:,.0f}}<extra></extra>', showlegend=False))
                        fig_score.add_trace(go.Bar(name=player2, x=dates_sorted, y=p2_scores_display,
                            marker=dict(color=p2_colors, line=dict(width=1, color='rgba(255,255,255,0.3)'), pattern=dict(shape=p2_patterns, solidity=0.5)),
                            customdata=p2_scores_raw, hovertemplate=f'{player2}: %{{customdata:,.0f}}<extra></extra>', showlegend=False))
                        fig_score.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=10, color=score_colors["player1"]), name=player1, showlegend=True))
                        fig_score.add_trace(go.Scatter(x=[None], y=[None], mode='markers', marker=dict(size=10, color=score_colors["player2"]), name=player2, showlegend=True))

                        apply_plotly_style(fig_score)
                        fig_score.update_layout(
                            barmode='relative', hovermode='x unified', height=280, bargap=0.15,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(weight=600)),
                            margin=dict(l=20, r=60, t=30, b=20),
                        )

                        # X-axis shows one tick per month; hover shows full date
                        fig_score.update_xaxes(title="", tickformat="%b", hoverformat="%b %d, %Y", tickangle=0, dtick="M1")

                        # Abbreviated y-axis labels (60K instead of 60,000) for narrow screens
                        def format_score_tick(val):
                            if val >= 1000:
                                return f"{int(val/1000)}K"
                            return str(int(val))

                        tick_step = 10 ** math.floor(math.log10(max(score_cap, 1000)))
                        if score_cap / tick_step < 3:
                            tick_step = tick_step / 2
                        tick_data = []
                        val = 0
                        while val <= score_cap * 1.1:
                            tick_data.append((val, format_score_tick(val)))
                            if val > 0:
                                tick_data.append((-val, format_score_tick(val)))
                            val += tick_step
                        tick_data.sort(key=lambda x: x[0])
                        fig_score.update_yaxes(title="", range=[-score_cap * 1.1, score_cap * 1.1],
                            tickvals=[t[0] for t in tick_data], ticktext=[t[1] for t in tick_data])
                        fig_score.add_hline(y=0, line_width=1, line_color="rgba(128, 128, 128, 0.5)")

                        # Display charts side-by-side
                        col_elo, col_score = st.columns(2)
                        with col_elo:
                            st.subheader("Elo Rating Comparison")
                            st.html('<p style="color-scheme: inherit; color: light-dark(#555555, #A0A0A0); font-size: 0.75rem; font-weight: 500; margin: -0.5rem 0 0.5rem 0;">1500 = starting rating</p>')
                            st.plotly_chart(fig_elo, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})
                        with col_score:
                            st.subheader("Score Comparison")
                            st.html('<p style="color-scheme: inherit; color: light-dark(#555555, #A0A0A0); font-size: 0.75rem; font-weight: 500; margin: -0.5rem 0 0.5rem 0;">Color = duel winner</p>')
                            st.plotly_chart(fig_score, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': False})

                        # Display the duel cards
                        st.subheader("Game-by-Game Comparison")

                        # Sort control - just Recent/Oldest by date
                        sort_direction = st.selectbox(
                            "Sort by",
                            options=["Recent", "Oldest"],
                            index=0,
                            key="duel_sort"
                        )
                        sort_ascending = sort_direction == "Oldest"
                        df_duel_sorted = df_duel.sort_values("Date", ascending=sort_ascending, na_position='last')

                        # Display as cards (with theme-adaptive player colors)
                        theme_colors = get_theme_colors()
                        cards_html = generate_duel_cards(df_duel_sorted, player1, player2, colors=theme_colors)
                        st.html(f'<div class="ranking-cards">{cards_html}</div>')
            else:
                st.info("Select two players to compare their head-to-head performance.")
        else:
            st.warning("History data not available.")

    # Floating share button (rendered last so CSS :last-of-type targets it)
    render_floating_share_button(new_slug)

if __name__ == "__main__":
    main()
