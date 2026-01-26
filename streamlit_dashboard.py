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
    initial_sidebar_state="collapsed"
)

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
    # Title
    st.title("🎮 DFTL Ranking Dashboard")
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

        st.markdown("---")
        st.caption(f"Data range: {min_date} to {max_date}")
        st.caption(f"Players in Dataset: {len(all_players)}")

    # Use full date range
    df_filtered = df_leaderboard.copy()

    # --- Main Content ---
    st.markdown(f"**Active dataset:** {dataset_label}")

    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏅 Elo Rankings",
        "📈 Elo Rating History",
        "📊 Daily Leaderboard",
        "👤 Player Tracker",
        "🏆 Top 10 History",
        "⚔️ Player Duel",
        "❓ FAQ"
    ])

    # --- Tab 3: Daily Leaderboard ---
    with tab3:

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

    # --- Tab 2: Elo Rating History ---
    with tab2:

        if df_history is not None and df_ratings is not None:
            # Get top 10 players by rating as default
            top_players_default = df_ratings.head(10)['player_name'].tolist()

            # Player filter (above graph)
            selected_players = st.multiselect(
                "Select players to compare",
                options=all_players,
                default=top_players_default,
                placeholder="Default: top 10 by rating"
            )

            if selected_players:
                # Filter history for selected players
                df_hist_filtered = df_history[
                    df_history['player_name'].isin(selected_players)
                ].copy()

                # Filter to only active periods (days with Active Rank)
                if 'active_rank' in df_hist_filtered.columns:
                    df_hist_filtered = df_hist_filtered[df_hist_filtered['active_rank'].notna()]

                # Filter to only days when players actually played
                if 'score' in df_hist_filtered.columns:
                    df_hist_filtered = df_hist_filtered[df_hist_filtered['score'].notna()]
            else:
                df_hist_filtered = pd.DataFrame()

            if not df_hist_filtered.empty:
                # Get latest rating for each player to sort legend
                latest_ratings = df_hist_filtered.groupby('player_name')['rating'].last().sort_values(ascending=False)
                players_sorted_by_rating = latest_ratings.index.tolist()

                # Line chart with sorted legend
                fig = px.line(
                    df_hist_filtered,
                    x='date',
                    y='rating',
                    color='player_name',
                    markers=True,
                    labels={
                        'date': 'Date',
                        'rating': 'Elo Rating',
                        'player_name': 'Player'
                    },
                    title="Rating Over Time",
                    category_orders={'player_name': players_sorted_by_rating}
                )
                fig.update_traces(
                    hovertemplate='%{fullData.name}: %{y:.0f}<extra></extra>'
                )
                fig.update_layout(
                    hovermode='x unified',
                    height=600,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                fig.add_hline(
                    y=1500,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Baseline (1500)"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No history data available for the selected players.")
        else:
            st.warning("Rating history data not available.")

    # --- Tab 1: Current Rankings ---
    with tab1:
        if df_history is not None and 'active_rank' in df_history.columns:
            # Date picker for historical rankings
            available_dates = sorted(df_history['date'].dt.date.unique(), reverse=True)

            selected_ranking_date = st.date_input(
                "Select date",
                value=available_dates[0],  # Default to most recent
                min_value=available_dates[-1],
                max_value=available_dates[0],
                key="ranking_date_picker"
            )

            # Check if viewing current (latest) date
            is_current_date = selected_ranking_date == available_dates[0]

            if is_current_date:
                st.caption(f"Showing current rankings ({selected_ranking_date})")
            else:
                st.caption(f"Showing historical rankings ({selected_ranking_date})")

            # Get history data for selected date
            df_date_history = df_history[df_history['date'].dt.date == selected_ranking_date].copy()

            if df_date_history.empty:
                st.info(f"No ranking data for {selected_ranking_date}. Try another date.")
            else:
                # Separate active and inactive players based on active_rank
                df_active = df_date_history[df_date_history['active_rank'].notna()].copy()
                df_inactive = df_date_history[df_date_history['active_rank'].isna()].copy()

                active_count = len(df_active)
                inactive_count = len(df_inactive)

                # Summary metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Active Players", active_count)
                with col2:
                    st.metric("Hidden Players", inactive_count)
                with col3:
                    if not df_active.empty:
                        st.metric("Highest Rating", f"{df_active['rating'].max():.1f}")
                    else:
                        st.metric("Highest Rating", "N/A")
                with col4:
                    if not df_active.empty:
                        st.metric("Average Rating", f"{df_active['rating'].mean():.1f}")
                    else:
                        st.metric("Average Rating", "N/A")
                with col5:
                    if not df_active.empty:
                        st.metric("Median Rating", f"{df_active['rating'].median():.1f}")
                    else:
                        st.metric("Median Rating", "N/A")

                # All players table
                st.subheader("Elo Ranking Leaderboard")

                # Toggle to show inactive players
                show_inactive = st.toggle("Show Hidden Players", value=False, help="Players inactive >7 days or with <7 ranked games")

                # Determine which data to display
                if show_inactive:
                    df_rankings_to_display = df_date_history.copy()
                else:
                    df_rankings_to_display = df_active.copy()

                # Calculate cumulative player stats UP TO the selected date
                df_leaderboard_filtered = df_leaderboard[df_leaderboard['date'].dt.date <= selected_ranking_date]
                player_stats = df_leaderboard_filtered.groupby('player_name').agg(
                    wins=('rank', lambda x: (x == 1).sum()),
                    top_10s=('rank', lambda x: (x <= 10).sum()),
                    avg_daily_rank=('rank', 'mean'),
                    total_games=('rank', 'count')
                ).reset_index()
                player_stats['avg_daily_rank'] = player_stats['avg_daily_rank'].round(1)
                player_stats['win_rate'] = (player_stats['wins'] / player_stats['total_games'] * 100).round(1)
                player_stats['top_10s_rate'] = (player_stats['top_10s'] / player_stats['total_games'] * 100).round(1)
                player_stats = player_stats.drop(columns=['total_games'])

                # Get history data filtered to selected date for peak rating
                df_history_filtered = df_history[df_history['date'].dt.date <= selected_ranking_date]

                # Calculate advanced metrics per player
                advanced_stats = []
                for player in df_rankings_to_display['player_name'].unique():
                    player_games = df_leaderboard_filtered[
                        df_leaderboard_filtered['player_name'] == player
                    ].sort_values('date', ascending=False)

                    player_history = df_history_filtered[
                        df_history_filtered['player_name'] == player
                    ]

                    # Last 7 avg
                    last7_games = player_games.head(7)
                    avg_last7 = last7_games['rank'].mean() if len(last7_games) > 0 else None

                    # Previous 7 avg (games 8-14)
                    prev7_games = player_games.iloc[7:14] if len(player_games) > 7 else pd.DataFrame()
                    avg_prev7 = prev7_games['rank'].mean() if len(prev7_games) > 0 else None

                    # Trend: compare last 7 vs previous 7 (lower rank = better, so improving = last7 < prev7)
                    if avg_last7 is not None and avg_prev7 is not None:
                        diff = avg_prev7 - avg_last7  # positive = improving
                        if diff > 1.5:
                            trend = "↑"  # Improving
                        elif diff < -1.5:
                            trend = "↓"  # Declining
                        else:
                            trend = "→"  # Stable
                    else:
                        trend = "→"  # Not enough data

                    # Peak rating
                    peak_rating = player_history['rating'].max() if not player_history.empty else None

                    # Days since last win
                    win_games = player_games[player_games['rank'] == 1]
                    if not win_games.empty:
                        last_win_date = win_games.iloc[0]['date'].date()
                        days_since_win = (selected_ranking_date - last_win_date).days
                    else:
                        days_since_win = None  # Never won

                    # Consistency (last 14 games only)
                    last14_games = player_games.head(14)
                    consistency = last14_games['rank'].std() if len(last14_games) >= 2 else None

                    advanced_stats.append({
                        'player_name': player,
                        'last_7': round(avg_last7, 1) if avg_last7 else None,
                        'trend': trend,
                        'peak_rating': round(peak_rating, 1) if peak_rating else None,
                        'days_since_win': days_since_win,
                        'consistency': round(consistency, 1) if consistency else None
                    })

                df_advanced = pd.DataFrame(advanced_stats)
                player_stats = player_stats.merge(df_advanced, on='player_name', how='left')

                # Merge stats with rankings
                df_rankings_display = df_rankings_to_display.merge(player_stats, on='player_name', how='left')

                # Determine columns based on available data
                has_days_inactive = 'days_inactive' in df_rankings_display.columns

                # Select columns to display
                display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'win_rate', 'top_10s', 'top_10s_rate', 'avg_daily_rank', 'last_7', 'consistency']
                if has_days_inactive:
                    display_cols.append('days_inactive')

                # Sort by rating (highest first)
                df_rankings_display = df_rankings_display.sort_values(
                    by='rating',
                    ascending=False
                )

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
                    "consistency": st.column_config.NumberColumn("Consistency", format="%.1f", help="Standard deviation of daily ranks over last 14 games (lower = more consistent)")
                }
                if has_days_inactive:
                    column_config["days_inactive"] = st.column_config.NumberColumn("Inactive", format="%d")

                st.dataframe(
                    df_rankings_display[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config
                )
        elif df_ratings is not None:
            # Fallback if no history data with active_rank
            st.warning("Historical rankings not available. Showing current rankings only.")

            # Activity gating info
            active_count = len(df_ratings)
            total_count = len(df_ratings_all) if df_ratings_all is not None else active_count
            inactive_count = total_count - active_count

            # Summary metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Active Players", active_count)
            with col2:
                st.metric("Inactive Players", inactive_count)
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
                    color_discrete_sequence=['#636EFA']
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
                    line_color="orange",
                    annotation_text=f"Median: {df_ratings['rating'].median():.0f}"
                )
                st.plotly_chart(fig_dist, use_container_width=True)

            # Toggle to show inactive players
            show_inactive = st.toggle("Show Hidden Players", value=False, help="Players inactive >7 days or with <7 ranked games")

            # Determine which ratings to display
            if show_inactive and df_ratings_all is not None:
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
            if has_uncertainty and show_inactive:
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

    # --- Tab 4: Player History ---
    with tab4:

        if df_history is not None:
            # Player selector (single selection) - no default
            selected_player = st.selectbox(
                "Select a player",
                options=all_players,
                index=None,
                placeholder="Choose a player..."
            )

            if selected_player:
                # Filter history for selected player
                df_player_history = df_history[
                    df_history['player_name'] == selected_player
                ].copy()

                if not df_player_history.empty:
                    # Sort by date
                    df_player_history = df_player_history.sort_values('date')

                    # Calculate cumulative stats from leaderboard data
                    df_player_leaderboard = df_leaderboard[
                        df_leaderboard['player_name'] == selected_player
                    ].sort_values('date')

                    # Calculate cumulative wins, top 10s, avg rank, and recent avg for each date
                    cumulative_stats = []
                    total_wins = 0
                    total_top_10s = 0
                    all_ranks = []

                    for _, row in df_player_leaderboard.iterrows():
                        if row['rank'] == 1:
                            total_wins += 1
                        if row['rank'] <= 10:
                            total_top_10s += 1
                        all_ranks.append(row['rank'])

                        # Calculate cumulative average daily rank
                        avg_daily_rank = sum(all_ranks) / len(all_ranks)

                        # Calculate recent avg (last 7 games)
                        recent_ranks = all_ranks[-7:] if len(all_ranks) >= 7 else all_ranks
                        recent_avg = sum(recent_ranks) / len(recent_ranks)

                        # Calculate win rate and top 10 rate
                        total_games = len(all_ranks)
                        win_rate = (total_wins / total_games * 100) if total_games > 0 else 0
                        top_10s_rate = (total_top_10s / total_games * 100) if total_games > 0 else 0

                        # Calculate consistency (last 14 games)
                        last_14_ranks = all_ranks[-14:] if len(all_ranks) >= 2 else all_ranks
                        consistency = np.std(last_14_ranks) if len(last_14_ranks) >= 2 else None

                        cumulative_stats.append({
                            'date': row['date'],
                            'wins': total_wins,
                            'top_10s': total_top_10s,
                            'avg_daily_rank': round(avg_daily_rank, 1),
                            'last_7': round(recent_avg, 1),
                            'win_rate': round(win_rate, 1),
                            'top_10s_rate': round(top_10s_rate, 1),
                            'consistency': round(consistency, 1) if consistency else None
                        })

                    df_cumulative = pd.DataFrame(cumulative_stats)

                    # Merge cumulative stats with player history
                    df_player_display = df_player_history.merge(
                        df_cumulative,
                        on='date',
                        how='left'
                    )

                    # Only show days where the player actually played (score is not null)
                    df_player_display = df_player_display[df_player_display['score'].notna()]

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
                        labels={'date': 'Date', 'rating': 'Elo Rating'}
                    )
                    fig_rating.update_layout(
                        height=250,
                        margin=dict(l=20, r=20, t=30, b=20),
                        showlegend=False
                    )
                    fig_rating.add_hline(
                        y=1500,
                        line_dash="dash",
                        line_color="gray",
                        annotation_text="Baseline"
                    )
                    # Add peak rating marker
                    peak_idx = df_chart['rating'].idxmax()
                    peak_row = df_chart.loc[peak_idx]
                    fig_rating.add_scatter(
                        x=[peak_row['date']],
                        y=[peak_row['rating']],
                        mode='markers',
                        marker=dict(size=12, color='gold', symbol='star'),
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

    # --- Tab 5: Active Rank History ---
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
                    category_orders={'player_name': all_rank1_players}
                )
                fig_rank1.update_traces(
                    line=dict(shape='hv'),  # Step line
                    marker=dict(size=8),
                    hovertemplate='%{y}<br>%{x|%Y-%m-%d}<extra></extra>'
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
                        ticktext=all_rank1_players
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

    # --- Tab 6: Player Duel ---
    with tab6:

        if df_history is not None:
            col_p1, col_p2 = st.columns(2)

            with col_p1:
                player1 = st.selectbox(
                    "Select Player 1",
                    options=all_players,
                    index=None,
                    placeholder="Choose Player 1...",
                    key="duel_player1"
                )

            with col_p2:
                player2 = st.selectbox(
                    "Select Player 2",
                    options=all_players,
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
                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric("Matchups", len(common_dates))
                        with col2:
                            st.metric(f"{player1} Wins", p1_wins)
                        with col3:
                            st.metric(f"{player2} Wins", p2_wins)
                        with col4:
                            ties = len(common_dates) - p1_wins - p2_wins
                            st.metric("Ties", ties)

                        # Win distribution pie chart
                        if len(common_dates) > 0:
                            pie_data = pd.DataFrame({
                                'Result': [player1, player2, 'Tie'],
                                'Count': [p1_wins, p2_wins, ties]
                            })
                            # Filter out zero values
                            pie_data = pie_data[pie_data['Count'] > 0]

                            # WCAG-compliant, colorblind-safe colors with high contrast
                            fig_pie = px.pie(
                                pie_data,
                                values='Count',
                                names='Result',
                                hole=0.4,
                                color_discrete_sequence=['#3B82F6', '#F59E0B', '#10B981']  # Blue, Amber, Emerald
                            )
                            fig_pie.update_traces(
                                textposition='inside',
                                textinfo='percent+value',
                                textfont=dict(color='white', size=14),
                                hovertemplate='%{label}: %{value} wins<extra></extra>'
                            )
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
                                    font=dict(size=12)
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

    # --- Tab 7: FAQ ---
    with tab7:
        st.caption("FAQ content coming soon.")


if __name__ == "__main__":
    main()
