import math

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
# Color Palette (consistent with config.toml theme)
COLORS = {
    # Primary brand colors
    "primary": "#FF6B6B",       # Coral red - primary accent
    "primary_light": "#FF8E8E",
    "primary_dark": "#E55555",
    # Background colors (from config.toml)
    "bg_dark": "#0E1117",
    "bg_card": "#262730",
    "bg_hover": "#3D3D4D",
    # Text colors
    "text_primary": "#FAFAFA",
    "text_secondary": "#B0B0B0",
    "text_muted": "#808080",
    # Semantic colors
    "success": "#10B981",       # Green - positive changes
    "warning": "#F59E0B",       # Amber - neutral/caution
    "danger": "#EF4444",        # Red - negative changes
    "info": "#3B82F6",          # Blue - informational
    # Chart colors (ordered for visual distinction)
    "chart_palette": [
        "#FF6B6B", "#3B82F6", "#10B981", "#F59E0B", "#8B5CF6",
        "#EC4899", "#06B6D4", "#84CC16", "#F97316", "#6366F1"
    ],
}

# Plotly chart template for consistency
PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text_primary"], "family": "sans-serif"},
        "title": {"font": {"size": 16, "color": COLORS["text_primary"]}},
        "xaxis": {
            "gridcolor": "rgba(128,128,128,0.2)",
            "linecolor": "rgba(128,128,128,0.3)",
            "tickfont": {"color": COLORS["text_secondary"]},
        },
        "yaxis": {
            "gridcolor": "rgba(128,128,128,0.2)",
            "linecolor": "rgba(128,128,128,0.3)",
            "tickfont": {"color": COLORS["text_secondary"]},
        },
        "legend": {"font": {"color": COLORS["text_secondary"]}},
        "colorway": COLORS["chart_palette"],
    }
}

# Custom CSS for visual hierarchy and spacing (theme-aware)
CUSTOM_CSS = """
<style>
/* ===== Typography Hierarchy ===== */
.main h1 {
    font-size: 2.25rem !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
    margin-bottom: 0.5rem !important;
}

.main h2 {
    font-size: 1.5rem !important;
    font-weight: 600 !important;
    margin-top: 1.5rem !important;
    margin-bottom: 1rem !important;
}

.main h3 {
    font-size: 1.25rem !important;
    font-weight: 600 !important;
}

/* ===== Section Containers ===== */
.stTabs [data-baseweb="tab-panel"] {
    padding-top: 1.5rem;
}

/* Metric card improvements - theme aware */
[data-testid="stMetric"] {
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(255, 107, 107, 0.25);
    border-radius: 8px;
    padding: 1rem;
}

[data-testid="stMetric"] label {
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    opacity: 0.7;
}

[data-testid="stMetric"] [data-testid="stMetricValue"] {
    font-size: 1.75rem !important;
    font-weight: 700 !important;
}

/* ===== Data Tables ===== */
.stDataFrame {
    border-radius: 8px;
    overflow: hidden;
}

/* Table header styling - theme aware */
.stDataFrame thead th {
    font-weight: 600 !important;
    text-transform: uppercase !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.05em !important;
    padding: 0.75rem 1rem !important;
}

/* ===== Sidebar Styling ===== */
[data-testid="stSidebar"] .stMarkdown hr {
    border-color: rgba(255, 107, 107, 0.2);
    margin: 1.5rem 0;
}

/* ===== Tab Styling ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background-color: transparent;
}

.stTabs [data-baseweb="tab"] {
    background-color: transparent;
    border-radius: 6px 6px 0 0;
    padding: 0.75rem 1rem;
    font-weight: 500;
}

.stTabs [aria-selected="true"] {
    background-color: rgba(255, 107, 107, 0.15) !important;
    border-bottom: 2px solid #FF6B6B !important;
}

/* ===== Buttons ===== */
.stButton > button {
    border-radius: 6px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border-color: #FF6B6B;
    color: #FF6B6B;
}

/* ===== Toggle Styling ===== */
[data-testid="stToggle"] label span {
    font-weight: 500 !important;
}

/* ===== Expander Styling ===== */
.streamlit-expanderHeader {
    font-weight: 600 !important;
}

/* ===== Select boxes ===== */
[data-testid="stSelectbox"] label {
    font-weight: 500 !important;
    opacity: 0.8;
}

/* ===== Date input ===== */
[data-testid="stDateInput"] label {
    font-weight: 500 !important;
    opacity: 0.8;
}

/* ===== Spacing utilities ===== */
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

/* Reduce spacing between elements */
.element-container {
    margin-bottom: 0.5rem;
}

/* ===== Divider styling ===== */
.main hr {
    border-color: rgba(255, 107, 107, 0.2);
    margin: 1.5rem 0;
}

/* ===== Caption styling ===== */
.stCaption {
    opacity: 0.6;
}
</style>
"""


def apply_plotly_style(fig):
    """Apply consistent styling to Plotly figures."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_primary"], family="sans-serif"),
        xaxis=dict(
            gridcolor="rgba(128,128,128,0.2)",
            linecolor="rgba(128,128,128,0.3)",
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
        yaxis=dict(
            gridcolor="rgba(128,128,128,0.2)",
            linecolor="rgba(128,128,128,0.3)",
            tickfont=dict(color=COLORS["text_secondary"]),
        ),
        legend=dict(font=dict(color=COLORS["text_secondary"])),
    )
    return fig


def format_rating_change(value):
    """Format rating change with color indicator."""
    if pd.isna(value):
        return ""
    if value > 0:
        return f"<span style='color: {COLORS['success']}'>+{value:.1f}</span>"
    elif value < 0:
        return f"<span style='color: {COLORS['danger']}'>{value:.1f}</span>"
    else:
        return f"<span style='color: {COLORS['text_muted']}'>{value:.1f}</span>"


def format_trend(trend):
    """Format trend indicator with color."""
    if trend == "↑":
        return f"<span style='color: {COLORS['success']}; font-size: 1.25rem;'>↑</span>"
    elif trend == "↓":
        return f"<span style='color: {COLORS['danger']}; font-size: 1.25rem;'>↓</span>"
    else:
        return f"<span style='color: {COLORS['text_muted']}; font-size: 1.25rem;'>→</span>"


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
    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # Title with subtitle
    st.title("🎮 DFTL Ranking Dashboard")
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

        # Dataset selector
        dataset_label = st.selectbox(
            "Dataset",
            options=list(available_datasets.keys()),
            index=0
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
            st.download_button(
                label="Download Leaderboard CSV",
                data=csv_leaderboard,
                file_name="full_leaderboard.csv",
                mime="text/csv",
                help="Download the complete daily leaderboard data (all dates)"
            )

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

            # Compact header: date picker + metrics on same row
            col_date, col1, col2, col3, col4, col5 = st.columns([1.2, 1, 1, 1, 1, 1])
            with col_date:
                selected_ranking_date = st.date_input(
                    "Date",
                    value=available_dates[0],
                    min_value=available_dates[-1],
                    max_value=available_dates[0],
                    key="elo_ranking_date"
                )

            # Load data for selected date and compute metrics
            df_date_history = df_history[df_history['date'].dt.date == selected_ranking_date].copy()

            if not df_date_history.empty:
                df_ranked = df_date_history[df_date_history['active_rank'].notna()].copy()
                df_unranked = df_date_history[df_date_history['active_rank'].isna()].copy()
                ranked_count = len(df_ranked)
                unranked_count = len(df_unranked)
                if 'games_played' in df_unranked.columns:
                    too_few_games = len(df_unranked[df_unranked['games_played'] < 7])
                    inactive_players = unranked_count - too_few_games
                else:
                    too_few_games = 0
                    inactive_players = unranked_count
                highest_rating = f"{df_ranked['rating'].max():.1f}" if not df_ranked.empty else "N/A"
                avg_rating = f"{df_ranked['rating'].mean():.1f}" if not df_ranked.empty else "N/A"
                median_rating = f"{df_ranked['rating'].median():.1f}" if not df_ranked.empty else "N/A"
            else:
                ranked_count = 0
                unranked_count = 0
                too_few_games = 0
                inactive_players = 0
                highest_rating = "N/A"
                avg_rating = "N/A"
                median_rating = "N/A"

            # Display metrics (computed after date selection)
            with col1:
                st.metric("Ranked", ranked_count)
            with col2:
                st.metric("Unranked", unranked_count, help=f"<7 games: {too_few_games} | Inactive: {inactive_players}")
            with col3:
                st.metric("Top Rating", highest_rating)
            with col4:
                st.metric("Average", avg_rating)
            with col5:
                st.metric("Median", median_rating)

            if df_date_history.empty:
                st.info(f"No ranking data for {selected_ranking_date}. Try another date.")
            else:
                # Leaderboard section
                st.subheader("Elo Ranking Leaderboard")

                # Toggle to show unranked players
                show_unranked = st.toggle("Show Unranked Players", value=True, help="Players with <7 games or inactive >7 days")

                # Columns to display (defined once, reused)
                display_cols = ['active_rank', 'player_name', 'rating', 'trend', 'games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency']
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
                    "trend": st.column_config.TextColumn("Trend", help="Performance trend: ↑ improving, ↓ declining, → stable"),
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

                # Quick navigation to Player Tracker
                st.markdown("---")
                col_select, col_button = st.columns([3, 1])
                with col_select:
                    # Use pre-sorted player list (df_date_history is already filtered for this date)
                    quick_select_player = st.selectbox(
                        "Quick jump to player history",
                        options=df_date_history.sort_values('rating', ascending=False)['player_name'].tolist(),
                        index=None,
                        placeholder="Select a player...",
                        key="tab1_player_select"
                    )
                with col_button:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("View History", key="tab1_view_history", disabled=quick_select_player is None):
                        # Directly set the Player Tracker selectbox value
                        st.session_state.tab4_player_select = quick_select_player
                        st.info(f"Click the **Player Tracker** tab above to see {quick_select_player}'s history.")
        elif df_ratings is not None:
            # Fallback if no history data with active_rank
            st.warning("Historical rankings not available. Showing current rankings only.")

            # Activity gating info
            ranked_count = len(df_ratings)
            total_count = len(df_ratings_all) if df_ratings_all is not None else ranked_count
            unranked_count = total_count - ranked_count

            # Break down unranked players by reason
            if df_ratings_all is not None and 'games_played' in df_ratings_all.columns:
                df_unranked_all = df_ratings_all[df_ratings_all['active_rank'].isna()]
                too_few_games = len(df_unranked_all[df_unranked_all['games_played'] < 7])
                inactive_players = unranked_count - too_few_games
            else:
                too_few_games = 0
                inactive_players = unranked_count

            # Summary metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Ranked Players", ranked_count)
            with col2:
                st.metric("Unranked Players", unranked_count, help=f"<7 games: {too_few_games} | Inactive: {inactive_players}")
            with col3:
                st.metric("Highest Rating", f"{df_ratings['rating'].max():.1f}")
            with col4:
                st.metric("Average Rating", f"{df_ratings['rating'].mean():.1f}")
            with col5:
                st.metric("Median Rating", f"{df_ratings['rating'].median():.1f}")

            # Rating Distribution Chart
            with st.expander("📊 Rating Distribution", expanded=False):
                fig_dist = px.histogram(
                    df_ratings,
                    x='rating',
                    nbins=20,
                    labels={'rating': 'Elo Rating', 'count': 'Players'},
                    color_discrete_sequence=[COLORS["primary"]]
                )
                apply_plotly_style(fig_dist)
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
                    line_color=COLORS["warning"],
                    annotation_text=f"Median: {df_ratings['rating'].median():.0f}",
                    annotation_font_color=COLORS["warning"]
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

            # Quick navigation to Player Tracker
            st.markdown("---")
            col_select, col_button = st.columns([3, 1])
            with col_select:
                # Always show all players (ranked + unranked) sorted by rating
                all_players_sorted = df_ratings_all.sort_values('rating', ascending=False)['player_name'].tolist() if df_ratings_all is not None else df_ratings_display['player_name'].tolist()
                quick_select_player2 = st.selectbox(
                    "Quick jump to player history",
                    options=all_players_sorted,
                    index=None,
                    placeholder="Select a player...",
                    key="tab1_player_select_fallback"
                )
            with col_button:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("View History", key="tab1_view_history_fallback", disabled=quick_select_player2 is None):
                    # Directly set the Player Tracker selectbox value
                    st.session_state.tab4_player_select = quick_select_player2
                    st.info(f"Click the **Player Tracker** tab above to see {quick_select_player2}'s history.")
        else:
            st.warning("Ratings data not available.")

    # --- Tab 3: Player Tracker ---
    with tab3:

        if df_history is not None:
            # Player selector (single selection)
            # Note: Value can be pre-set from Elo Rankings tab via session state key
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
                    # All stats are pre-computed in the history CSV - no runtime computation needed!
                    # Just filter to days where the player actually played (score is not null)
                    df_player_display = df_player_history[df_player_history['score'].notna()].copy()

                    # Determine if active_rank column exists
                    has_active_rank = 'active_rank' in df_player_display.columns

                    # Select columns for display (aligned with Tab 1)
                    display_cols = ['date', 'rank', 'score', 'rating', 'rating_change']
                    if has_active_rank:
                        display_cols.append('active_rank')
                    display_cols.extend(['games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency'])

                    # Sort by date descending (most recent first)
                    df_player_display = df_player_display.sort_values('date', ascending=False)

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
                        "last_7": st.column_config.NumberColumn("Recent", format="%.1f", help="Average daily rank over last 7 games"),
                        "consistency": st.column_config.NumberColumn("Consistency", format="%.1f", help="Standard deviation of daily ranks over last 14 games (lower = more consistent)")
                    }
                    if has_active_rank:
                        column_config["active_rank"] = st.column_config.NumberColumn("Elo Rank", format="%d")

                    # Table first
                    st.dataframe(
                        df_player_display[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config=column_config
                    )

                    # Rating trajectory chart below table
                    df_chart = df_player_display.sort_values('date')  # Ascending for chart
                    fig_rating = px.line(
                        df_chart,
                        x='date',
                        y='rating',
                        markers=True,
                        labels={'date': 'Date', 'rating': 'Elo Rating'},
                        color_discrete_sequence=[COLORS["primary"]]
                    )
                    apply_plotly_style(fig_rating)
                    fig_rating.update_layout(
                        height=250,
                        margin=dict(l=20, r=20, t=30, b=20),
                        showlegend=False
                    )
                    fig_rating.add_hline(
                        y=1500,
                        line_dash="dash",
                        line_color=COLORS["text_muted"],
                        annotation_text="Baseline",
                        annotation_font_color=COLORS["text_muted"]
                    )
                    # Add peak rating marker
                    peak_idx = df_chart['rating'].idxmax()
                    peak_row = df_chart.loc[peak_idx]
                    fig_rating.add_scatter(
                        x=[peak_row['date']],
                        y=[peak_row['rating']],
                        mode='markers',
                        marker=dict(size=12, color=COLORS["warning"], symbol='star'),
                        name='Peak',
                        hovertemplate=f"Peak: {peak_row['rating']:.0f}<extra></extra>"
                    )
                    st.plotly_chart(fig_rating, use_container_width=True)
                else:
                    st.info(f"No history data available for {selected_player}.")
            else:
                st.info("Select a player to view their history.")
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
                    color_discrete_sequence=[COLORS["primary"]]
                )
                fig_rank1.update_traces(
                    line=dict(shape='hv', color=COLORS["primary"]),  # Step line
                    marker=dict(size=8, color=COLORS["primary"]),
                    hovertemplate='%{y}<br>%{x|%Y-%m-%d}<extra></extra>'
                )
                apply_plotly_style(fig_rank1)
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
                        tickfont=dict(color=COLORS["text_secondary"])
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

                        # Display encounter badges
                        col_first, col_last = st.columns(2)
                        with col_first:
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, {COLORS['bg_card']} 0%, rgba(59,130,246,0.2) 100%);
                                        border: 1px solid {COLORS['info']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: {COLORS['text_secondary']}; margin-bottom: 0.25rem;">First Encounter</div>
                                <div style="font-size: 1.25rem; font-weight: 700; color: {COLORS['text_primary']};">{first_date.strftime('%Y-%m-%d')}</div>
                                <div style="font-size: 0.875rem; color: {COLORS['info']};">Winner: {first_winner}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_last:
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, {COLORS['bg_card']} 0%, rgba(255,107,107,0.2) 100%);
                                        border: 1px solid {COLORS['primary']}; border-radius: 8px; padding: 1rem; text-align: center;">
                                <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; color: {COLORS['text_secondary']}; margin-bottom: 0.25rem;">Last Encounter</div>
                                <div style="font-size: 1.25rem; font-weight: 700; color: {COLORS['text_primary']};">{last_date.strftime('%Y-%m-%d')}</div>
                                <div style="font-size: 0.875rem; color: {COLORS['primary']};">Winner: {last_winner}</div>
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
                            color_discrete_map={player1: COLORS["info"], player2: COLORS["warning"]}
                        )
                        fig_elo.update_traces(
                            hovertemplate='%{fullData.name}: %{y:.0f}<extra></extra>'
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
                                font=dict(color=COLORS["text_secondary"])
                            ),
                            margin=dict(l=20, r=20, t=40, b=20)
                        )
                        fig_elo.add_hline(
                            y=1500,
                            line_dash="dash",
                            line_color=COLORS["text_muted"],
                            annotation_text="Baseline",
                            annotation_font_color=COLORS["text_muted"]
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
                            color_discrete_map={player1: COLORS["info"], player2: COLORS["warning"]}
                        )
                        fig_score.update_traces(
                            hovertemplate='%{fullData.name}: %{y:,.0f}<extra></extra>'
                        )
                        apply_plotly_style(fig_score)
                        fig_score.update_layout(
                            hovermode='x unified',
                            height=300,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="center",
                                x=0.5,
                                font=dict(color=COLORS["text_secondary"])
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
                                color_discrete_sequence=[COLORS["info"], COLORS["warning"], COLORS["success"]]
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
                                margin=dict(l=20, r=20, t=20, b=20),
                                showlegend=True,
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=-0.1,
                                    xanchor="center",
                                    x=0.5,
                                    font=dict(size=12, color=COLORS["text_secondary"])
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
