import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="DFTL Leaderboard & Elo Ratings",
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
    st.title("🎮 DFTL Daily Leaderboard & Elo Ratings")
    st.markdown("---")

    # Check for available datasets
    available_datasets = get_available_datasets()
    if not available_datasets:
        st.error("No data files found in the output folder. Please run the data pipeline first.")
        return

    # --- Sidebar ---
    with st.sidebar:
        st.header("🔧 Filters")

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
        st.caption(f"Total ranked players: {len(all_players)}")

    # Use full date range
    df_filtered = df_leaderboard.copy()

    # --- Main Content ---
    st.markdown(f"**Active dataset:** {dataset_label}")

    # Create tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "🏅 Current Rankings",
        "📈 Elo Rating History",
        "📊 Daily Leaderboard",
        "👤 Player History",
        "🏆 Active Rank History",
        "❓ FAQ"
    ])

    # --- Tab 3: Daily Leaderboard ---
    with tab3:
        st.header(f"Daily Leaderboard (last update: {max_date})")

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
                    column_config["active_rank"] = st.column_config.NumberColumn("Active Rank", format="%d")

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
        st.header(f"Elo Rating History (last update: {max_date})")

        if df_history is not None and df_ratings is not None:
            # Create containers for layout (graph first, selectors below)
            graph_container = st.container()
            selectors_container = st.container()

            # Render selectors first (to get values), but they appear below due to container order
            with selectors_container:
                # Toggle to include inactive players
                show_inactive_history = st.toggle(
                    "Include inactive players in selection",
                    value=False,
                    key="history_inactive_toggle"
                )

                # Choose which ratings to use for top N selection
                if show_inactive_history and df_ratings_all is not None:
                    df_ratings_for_selection = df_ratings_all
                else:
                    df_ratings_for_selection = df_ratings

                # Top N slider
                max_players = min(len(df_ratings_for_selection), 30)
                top_n = st.slider(
                    "Show top N players",
                    min_value=5,
                    max_value=max_players,
                    value=min(10, max_players),
                    step=5
                )

                # Get top N players by rating as default
                top_players_default = df_ratings_for_selection.head(top_n)['player_name'].tolist()

                # Player filter
                selected_players = st.multiselect(
                    "Select players (or use top N default)",
                    options=all_players,
                    default=top_players_default
                )

                # Toggle to show only days when players actually played
                show_only_play_days = st.toggle(
                    "Show only days when players played",
                    value=False,
                    key="history_play_days_toggle"
                )

            # Render graph in the first container (appears at top)
            with graph_container:
                if selected_players:
                    # Filter history for selected players
                    df_hist_filtered = df_history[
                        df_history['player_name'].isin(selected_players)
                    ].copy()

                    # Filter to only active periods (days with Active Rank)
                    if 'active_rank' in df_hist_filtered.columns:
                        df_hist_filtered = df_hist_filtered[df_hist_filtered['active_rank'].notna()]

                    # Optionally filter to only days when players actually played
                    if show_only_play_days and 'score' in df_hist_filtered.columns:
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
                "Select date for rankings",
                value=available_dates[0],  # Default to most recent
                min_value=available_dates[-1],
                max_value=available_dates[0],
                key="ranking_date_picker"
            )

            # Check if viewing current (latest) date
            is_current_date = selected_ranking_date == available_dates[0]

            if is_current_date:
                st.header(f"Current Elo Rankings ({selected_ranking_date})")
            else:
                st.header(f"Historical Elo Rankings ({selected_ranking_date})")

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
                    st.metric("Inactive Players", inactive_count)
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

                # Toggle to show inactive players
                show_inactive = st.toggle("Show inactive players (no activity in last 7 days)", value=False)

                # Determine which data to display
                if show_inactive:
                    df_rankings_to_display = df_date_history.copy()
                else:
                    df_rankings_to_display = df_active.copy()

                # All players table
                st.subheader("Ranked Players")

                # Calculate cumulative player stats UP TO the selected date
                df_leaderboard_filtered = df_leaderboard[df_leaderboard['date'].dt.date <= selected_ranking_date]
                player_stats = df_leaderboard_filtered.groupby('player_name').agg(
                    wins=('rank', lambda x: (x == 1).sum()),
                    podiums=('rank', lambda x: (x <= 3).sum()),
                    top_10s=('rank', lambda x: (x <= 10).sum()),
                    avg_score=('score', 'mean'),
                    best_daily_rank=('rank', 'min')
                ).reset_index()
                player_stats['avg_score'] = player_stats['avg_score'].round(0).astype(int)

                # Calculate best active rank from history up to the selected date
                df_history_filtered = df_history[df_history['date'].dt.date <= selected_ranking_date]
                best_active_ranks = df_history_filtered.groupby('player_name')['active_rank'].min().reset_index()
                best_active_ranks.columns = ['player_name', 'best_active_rank']
                player_stats = player_stats.merge(best_active_ranks, on='player_name', how='left')

                # Merge stats with rankings
                df_rankings_display = df_rankings_to_display.merge(player_stats, on='player_name', how='left')

                # Determine columns based on available data
                has_days_inactive = 'days_inactive' in df_rankings_display.columns

                # Select columns to display
                display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'podiums', 'top_10s', 'avg_score', 'best_daily_rank', 'best_active_rank']
                if has_days_inactive:
                    display_cols.append('days_inactive')

                # Sort by rating (highest first)
                df_rankings_display = df_rankings_display.sort_values(
                    by='rating',
                    ascending=False
                )

                column_config = {
                    "active_rank": st.column_config.NumberColumn("Active Rank", format="%d"),
                    "player_name": st.column_config.TextColumn("Player"),
                    "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                    "games_played": st.column_config.NumberColumn("Ranked Games", format="%d"),
                    "wins": st.column_config.NumberColumn("Wins", format="%d"),
                    "podiums": st.column_config.NumberColumn("Podiums", format="%d"),
                    "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                    "avg_score": st.column_config.NumberColumn("Avg Score", format="%d"),
                    "best_daily_rank": st.column_config.NumberColumn("Best Daily Rank", format="%d"),
                    "best_active_rank": st.column_config.NumberColumn("Best Active Rank", format="%d")
                }
                if has_days_inactive:
                    column_config["days_inactive"] = st.column_config.NumberColumn("Days Inactive", format="%d")

                st.dataframe(
                    df_rankings_display[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config=column_config
                )
        elif df_ratings is not None:
            # Fallback if no history data with active_rank
            st.header(f"Current Elo Rankings (last update: {max_date})")
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

            # Toggle to show inactive players
            show_inactive = st.toggle("Show inactive players (no activity in last 7 days)", value=False)

            # Determine which ratings to display
            if show_inactive and df_ratings_all is not None:
                df_ratings_to_display = df_ratings_all.copy()
            else:
                df_ratings_to_display = df_ratings.copy()

            # All players table
            st.subheader("Ranked Players")

            # Calculate player stats from leaderboard data
            player_stats = df_leaderboard.groupby('player_name').agg(
                wins=('rank', lambda x: (x == 1).sum()),
                podiums=('rank', lambda x: (x <= 3).sum()),
                top_10s=('rank', lambda x: (x <= 10).sum()),
                avg_score=('score', 'mean')
            ).reset_index()
            player_stats['avg_score'] = player_stats['avg_score'].round(0).astype(int)

            # Merge stats with ratings
            df_ratings_display = df_ratings_to_display.merge(player_stats, on='player_name', how='left')

            # Determine columns based on whether we have uncertainty data
            has_uncertainty = 'uncertainty' in df_ratings_display.columns
            has_days_inactive = 'days_inactive' in df_ratings_display.columns

            # Select columns to display (use active_rank instead of rank)
            display_cols = ['active_rank', 'player_name', 'rating', 'games_played', 'wins', 'podiums', 'top_10s', 'avg_score', 'last_seen']
            if has_days_inactive:
                display_cols.insert(-1, 'days_inactive')
            if has_uncertainty and show_inactive:
                display_cols.insert(-1, 'uncertainty')

            column_config = {
                "active_rank": st.column_config.NumberColumn("Active Rank", format="%d"),
                "player_name": st.column_config.TextColumn("Player"),
                "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                "games_played": st.column_config.NumberColumn("Ranked Games", format="%d"),
                "wins": st.column_config.NumberColumn("Wins", format="%d"),
                "podiums": st.column_config.NumberColumn("Podiums", format="%d"),
                "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                "avg_score": st.column_config.NumberColumn("Avg Score", format="%d"),
                "last_seen": st.column_config.DateColumn("Last Seen", format="YYYY-MM-DD")
            }
            if has_days_inactive:
                column_config["days_inactive"] = st.column_config.NumberColumn("Days Inactive", format="%d")
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
        st.header(f"Player History (last update: {max_date})")

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

                    # Calculate cumulative wins, podiums, top 10s for each date
                    cumulative_stats = []
                    total_wins = 0
                    total_podiums = 0
                    total_top_10s = 0

                    for _, row in df_player_leaderboard.iterrows():
                        if row['rank'] == 1:
                            total_wins += 1
                        if row['rank'] <= 3:
                            total_podiums += 1
                        if row['rank'] <= 10:
                            total_top_10s += 1

                        cumulative_stats.append({
                            'date': row['date'],
                            'wins': total_wins,
                            'podiums': total_podiums,
                            'top_10s': total_top_10s
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

                    # Select columns for display (use active_rank from history data)
                    display_cols = ['player_name', 'date', 'rank', 'score', 'rating', 'rating_change']
                    if has_active_rank:
                        display_cols.append('active_rank')
                    display_cols.extend(['games_played', 'wins', 'podiums', 'top_10s'])

                    # Sort by date descending (most recent first)
                    df_player_display = df_player_display.sort_values('date', ascending=False)

                    column_config = {
                        "player_name": st.column_config.TextColumn("Player"),
                        "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                        "rank": st.column_config.NumberColumn("Daily Rank", format="%d"),
                        "score": st.column_config.NumberColumn("Score", format="%d"),
                        "rating": st.column_config.NumberColumn("Elo Rating", format="%.1f"),
                        "rating_change": st.column_config.NumberColumn("Rating Change", format="%+.1f"),
                        "games_played": st.column_config.NumberColumn("Ranked Games", format="%d"),
                        "wins": st.column_config.NumberColumn("Wins", format="%d"),
                        "podiums": st.column_config.NumberColumn("Podiums", format="%d"),
                        "top_10s": st.column_config.NumberColumn("Top 10s", format="%d")
                    }
                    if has_active_rank:
                        column_config["active_rank"] = st.column_config.NumberColumn("Active Rank", format="%d")

                    st.dataframe(
                        df_player_display[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config=column_config
                    )
                else:
                    st.info(f"No history data available for {selected_player}.")
            else:
                st.info("Select a player to view their history.")
        else:
            st.warning("History data not available.")

    # --- Tab 5: Active Rank History ---
    with tab5:
        st.header(f"Active Rank History (last update: {max_date})")

        if df_history is not None and 'active_rank' in df_history.columns:
            # Use pre-computed active_rank from history data
            # Filter to players with an active_rank (only active players have ranks)
            df_history_active = df_history[df_history['active_rank'].notna()].copy()

            # Filter to top 10 active ranks only
            df_top10 = df_history_active[df_history_active['active_rank'] <= 10].copy()

            # Pivot to get ranks as columns
            df_pivot = df_top10.pivot(
                index='date',
                columns='active_rank',
                values='player_name'
            ).reset_index()

            # Rename columns
            df_pivot.columns = ['Date'] + [f'Rank {int(i)}' for i in df_pivot.columns[1:]]

            # Sort by date descending (most recent first)
            df_pivot = df_pivot.sort_values('Date', ascending=False)

            # Build column config dynamically
            column_config = {
                "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD")
            }
            for i in range(1, 11):
                col_name = f'Rank {i}'
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

    # --- Tab 6: FAQ ---
    with tab6:
        st.header("Frequently Asked Questions")
        st.info("FAQ content coming soon.")


if __name__ == "__main__":
    main()
