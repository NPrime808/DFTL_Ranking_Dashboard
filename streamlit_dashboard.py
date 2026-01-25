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
    "Early Access Only": "early_access",
    "Steam Demo Only": "steam_demo"
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
    """Load the most recent Elo ratings CSV for the given dataset."""
    pattern = f"{dataset_prefix}_elo_ratings_*.csv"
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
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏅 Current Rankings",
        "📈 Elo Rating History",
        "📊 Daily Leaderboard",
        "👤 Player History",
        "🏆 Elo Rank History"
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

                # Merge with history data for rating and rating_change
                if df_history is not None:
                    # Get history for the selected date and calculate Elo rank
                    df_day_history = df_history[df_history['date'].dt.date == selected_date][
                        ['player_name', 'rating', 'rating_change']
                    ].copy()
                    # Calculate Elo rank based on rating for that date
                    df_day_history['elo_rank'] = df_day_history['rating'].rank(ascending=False, method='min').astype(int)
                    df_day = df_day.merge(df_day_history, on='player_name', how='left')
                    display_cols = ['rank', 'player_name', 'score', 'rating', 'rating_change', 'elo_rank']
                else:
                    display_cols = ['rank', 'player_name', 'score']

                # Display table
                st.dataframe(
                    df_day[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "rank": st.column_config.NumberColumn("Daily Rank", format="%d"),
                        "player_name": st.column_config.TextColumn("Player"),
                        "score": st.column_config.NumberColumn("Score", format="%d"),
                        "rating": st.column_config.NumberColumn("Elo Rating", format="%.1f"),
                        "rating_change": st.column_config.NumberColumn("Rating Change", format="%+.1f"),
                        "elo_rank": st.column_config.NumberColumn("Rank (Elo)", format="%d")
                    }
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
                # Top N slider
                max_players = min(len(df_ratings), 30)
                top_n = st.slider(
                    "Show top N players",
                    min_value=5,
                    max_value=max_players,
                    value=min(10, max_players),
                    step=5
                )

                # Get top N players by rating as default
                top_players_default = df_ratings.head(top_n)['player_name'].tolist()

                # Player filter
                selected_players = st.multiselect(
                    "Select players (or use top N default)",
                    options=all_players,
                    default=top_players_default
                )

            # Render graph in the first container (appears at top)
            with graph_container:
                if selected_players:
                    # Filter history for selected players
                    df_hist_filtered = df_history[
                        df_history['player_name'].isin(selected_players)
                    ].copy()
                else:
                    df_hist_filtered = pd.DataFrame()

                if not df_hist_filtered.empty:
                    # Line chart
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
                        title="Rating Over Time"
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
        st.header(f"Current Elo Rankings (last update: {max_date})")

        if df_ratings is not None:
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Ranked Players", len(df_ratings))
            with col2:
                st.metric("Highest Rating", f"{df_ratings['rating'].max():.1f}")
            with col3:
                st.metric("Average Rating", f"{df_ratings['rating'].mean():.1f}")
            with col4:
                st.metric("Median Rating", f"{df_ratings['rating'].median():.1f}")

            # All players table
            st.subheader("All Ranked Players")

            # Calculate player stats from leaderboard data
            player_stats = df_leaderboard.groupby('player_name').agg(
                wins=('rank', lambda x: (x == 1).sum()),
                podiums=('rank', lambda x: (x <= 3).sum()),
                top_10s=('rank', lambda x: (x <= 10).sum()),
                avg_score=('score', 'mean')
            ).reset_index()
            player_stats['avg_score'] = player_stats['avg_score'].round(0).astype(int)

            # Merge stats with ratings
            df_ratings_display = df_ratings.merge(player_stats, on='player_name', how='left')

            # Select columns to display
            display_cols = ['rank', 'player_name', 'rating', 'games_played', 'wins', 'podiums', 'top_10s', 'avg_score', 'last_seen']
            st.dataframe(
                df_ratings_display[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "rank": st.column_config.NumberColumn("Rank (Elo)", format="%d"),
                    "player_name": st.column_config.TextColumn("Player"),
                    "rating": st.column_config.NumberColumn("Rating", format="%.1f"),
                    "games_played": st.column_config.NumberColumn("Ranked Games", format="%d"),
                    "wins": st.column_config.NumberColumn("Wins", format="%d"),
                    "podiums": st.column_config.NumberColumn("Podiums", format="%d"),
                    "top_10s": st.column_config.NumberColumn("Top 10s", format="%d"),
                    "avg_score": st.column_config.NumberColumn("Avg Score", format="%d"),
                    "last_seen": st.column_config.DateColumn("Last Seen", format="YYYY-MM-DD")
                }
            )
        else:
            st.warning("Ratings data not available.")

    # --- Tab 4: Player History ---
    with tab4:
        st.header(f"Player History (last update: {max_date})")

        if df_history is not None:
            # Player selector (single selection)
            selected_player = st.selectbox(
                "Select a player",
                options=all_players,
                index=0
            )

            if selected_player:
                # Filter history for selected player
                df_player_history = df_history[
                    df_history['player_name'] == selected_player
                ].copy()

                if not df_player_history.empty:
                    # Sort by date
                    df_player_history = df_player_history.sort_values('date')

                    # Calculate Elo rank for each date (rank all players by rating)
                    df_history_ranked = df_history.copy()
                    df_history_ranked['elo_rank'] = df_history_ranked.groupby('date')['rating'].rank(
                        ascending=False, method='min'
                    ).astype(int)

                    # Get Elo rank for selected player
                    df_player_elo_rank = df_history_ranked[
                        df_history_ranked['player_name'] == selected_player
                    ][['date', 'elo_rank']].copy()

                    # Calculate Elo rank change (previous rank - current rank, positive = improved)
                    df_player_elo_rank = df_player_elo_rank.sort_values('date')
                    df_player_elo_rank['elo_rank_change'] = -df_player_elo_rank['elo_rank'].diff()

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

                    # Merge Elo rank data
                    df_player_display = df_player_display.merge(
                        df_player_elo_rank,
                        on='date',
                        how='left'
                    )

                    # Only show days where the player actually played (score is not null)
                    df_player_display = df_player_display[df_player_display['score'].notna()]

                    # Select and rename columns for display
                    display_cols = ['player_name', 'date', 'rank', 'score', 'rating', 'rating_change', 'elo_rank', 'elo_rank_change', 'games_played', 'wins', 'podiums', 'top_10s']

                    # Sort by date descending (most recent first)
                    df_player_display = df_player_display.sort_values('date', ascending=False)

                    st.dataframe(
                        df_player_display[display_cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "player_name": st.column_config.TextColumn("Player"),
                            "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                            "rank": st.column_config.NumberColumn("Daily Rank", format="%d"),
                            "score": st.column_config.NumberColumn("Score", format="%d"),
                            "rating": st.column_config.NumberColumn("Elo Rating", format="%.1f"),
                            "rating_change": st.column_config.NumberColumn("Rating Change", format="%+.1f"),
                            "elo_rank": st.column_config.NumberColumn("Rank (Elo)", format="%d"),
                            "elo_rank_change": st.column_config.NumberColumn("Elo Rank Change", format="%+.0f"),
                            "games_played": st.column_config.NumberColumn("Ranked Games", format="%d"),
                            "wins": st.column_config.NumberColumn("Wins", format="%d"),
                            "podiums": st.column_config.NumberColumn("Podiums", format="%d"),
                            "top_10s": st.column_config.NumberColumn("Top 10s", format="%d")
                        }
                    )
                else:
                    st.info(f"No history data available for {selected_player}.")
        else:
            st.warning("History data not available.")

    # --- Tab 5: Elo Rank History ---
    with tab5:
        st.header(f"Elo Rank History (last update: {max_date})")

        if df_history is not None:
            # Calculate Elo rank for each date (rank all players by rating)
            df_history_ranked = df_history.copy()
            df_history_ranked['elo_rank'] = df_history_ranked.groupby('date')['rating'].rank(
                ascending=False, method='min'
            ).astype(int)

            # Filter to top 10 ranks only
            df_top10 = df_history_ranked[df_history_ranked['elo_rank'] <= 10].copy()

            # Pivot to get ranks as columns
            df_pivot = df_top10.pivot(
                index='date',
                columns='elo_rank',
                values='player_name'
            ).reset_index()

            # Rename columns
            df_pivot.columns = ['Date'] + [f'Rank {i}' for i in range(1, len(df_pivot.columns))]

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
            st.warning("History data not available.")


if __name__ == "__main__":
    main()
