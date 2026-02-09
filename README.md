# DFTL Ranking Dashboard

A competitive Elo rating system and analytics dashboard for **Die For The Lich** (DFTL) Daily Run leaderboards. This project tracks player performance over time, computes skill-based rankings using an advanced Elo algorithm, and presents the data through an interactive Streamlit dashboard.

![Dashboard Preview](https://raw.githubusercontent.com/NPrime808/DFTL_Ranking_Dashboard/main/images/Dashboard_preview_001_20260201.png)

## Features

- **Elo Rating System** - Pairwise comparison model that evaluates every player matchup each day
- **Dynamic K-Factor** - New players gain/lose rating faster; established players have more stable ratings
- **Activity Gating** - Only players active in the last 7 days with 7+ games appear in rankings
- **Hybrid Compression** - Prevents rating inflation while allowing top players to reach high ratings
- **Interactive Dashboard** - Responsive web UI with player search, rankings, and detailed stats
- **Dark Mode Design** - Optimized dark theme for reduced eye strain
- **Mobile-First Design** - Card-based layout optimized for all screen sizes
- **Multiple Data Views** - Track Steam Demo era, Early Access, or combined datasets

## How It Works

### The Elo Algorithm

Each day, every pair of players on the leaderboard is compared. If Player A finishes above Player B:
- Player A's expected win probability is calculated based on their rating difference
- Ratings are adjusted based on whether the result was expected or an upset
- Score gaps between players influence the magnitude of rating changes

The system uses several enhancements over standard Elo:

| Feature | Description |
|---------|-------------|
| **Dynamic K** | K-factor of 1.5x for new players (<10 games), 1.2x for provisional (10-30 games) |
| **Uncertainty** | Inactive players accumulate uncertainty, amplifying their next rating change |
| **Floor Protection** | Ratings cannot drop below 1000; winners gain less when beating low-rated players |
| **Ceiling Compression** | Logarithmic compression toward 2700, tanh asymptote at 3000 |

### Rating Scale

| Rating | Tier |
|--------|------|
| 2500+  | Elite |
| 2200-2499 | Expert |
| 1900-2199 | Advanced |
| 1600-1899 | Intermediate |
| 1300-1599 | Developing |
| 1000-1299 | Beginner |

## Installation

### Prerequisites

- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/NPrime808/DFTL_Ranking_Dashboard.git
cd DFTL_Ranking_Dashboard

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Running the Dashboard

```bash
streamlit run streamlit_dashboard.py
```

The dashboard will open in your browser at `http://localhost:8501`.

### Data Pipeline

The system supports two ingestion methods:

#### 1. Discord JSON Export (Bulk Import)

Parse exported Discord channel JSON containing DFTL_BOT leaderboard messages:

```bash
python -m src.ingestion.discord_parser
```

#### 2. Paste Mode (Daily Updates)

Quickly add a single day's leaderboard by pasting the Discord message:

```bash
python -m src.ingestion.paste_mode
```

#### 3. Recompute Elo Ratings

After adding new data, recompute all ratings:

```bash
python -m src.elo.engine
```

## Project Structure

```
DFTL_Ranking_Dashboard/
├── streamlit_dashboard.py   # Main dashboard application
├── src/
│   ├── config.py            # Central configuration
│   ├── utils.py             # Shared utilities
│   ├── elo/
│   │   ├── compression.py   # Rating compression functions
│   │   ├── engine.py        # Elo computation engine
│   │   └── rivalries.py     # Head-to-head rivalry statistics
│   └── ingestion/
│       ├── discord_parser.py    # JSON export parser
│       └── paste_mode.py        # Daily paste ingestion
├── data/
│   ├── raw/                 # Discord JSON exports
│   └── processed/           # Generated CSV files
└── requirements.txt
```

## Configuration

Key parameters in `src/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `BASELINE_RATING` | 1500 | Starting rating for new players |
| `K_FACTOR` | 180 | Base K-factor (higher = faster changes) |
| `MIN_GAMES_FOR_RANKING` | 7 | Games required to appear in rankings |
| `ACTIVITY_WINDOW_DAYS` | 7 | Days of inactivity before becoming unranked |
| `SOFT_TARGET` | 2700 | Rating where log compression begins |
| `HARD_CEILING` | 3000 | Theoretical maximum rating |

## Data & Privacy

This project follows data minimization principles:

| Published | Not Published |
|-----------|---------------|
| In-game player names | Discord user IDs |
| Daily ranks and scores | Discord message IDs |
| Derived Elo ratings | Platform metadata |
| Activity metrics | Raw message content |

**How it works:**
- Raw Discord exports are used only as an ingestion source (not published)
- The parser extracts only game-level data: date, player name, rank, score
- All Discord platform identifiers are discarded during processing
- Published datasets contain only leaderboard data and derived analytics

## Tech Stack

- **Python 3.11** - Core language
- **Streamlit** - Dashboard framework
- **Pandas** - Data manipulation
- **Plotly** - Interactive charts
- **NumPy** - Numerical operations

## FAQ

### What is Elo rating?

**Elo** is a rating system originally designed for chess that measures relative skill levels. Here, I use a modified pairwise Elo system that compares players based on their daily leaderboard performance.

- **Starting Rating**: All players begin at **1500** (the baseline/median)
- **Rating Range**: From **1000** (floor) to **3000** (theoretical ceiling)
- **How it works**: When you finish higher than another player on the daily leaderboard, you "win" against them. Your rating increases, theirs decreases. The amount depends on the rating difference and score margin.

### What do the ratings mean?

Ratings reflect actual skill gaps between players (the better the player the higher the rating), and roughly match with expected performance:

| Rating | Typical Rank |
|--------|--------------|
| **2800+** | Top 1 |
| **2500-2800** | Top 5 |
| **2000-2500** | Top 10 |
| **1500** | ~Rank 15-20 |
| **1200-1500** | Rank 20-25 |
| **1000-1200** | Rank 25-30 |

### How are Elo Rankings calculated?

Each day, all players on the leaderboard are compared pairwise:
1. Player A finishes 5th. They beat the 25 players below them, and lost to the 4 above
2. Rating changes are calculated using a modified Elo formula
3. Score is taken into account. Domination means more points, narrow wins mean less
4. Players with more games have more stable ratings (dynamic K-factor)
5. Uncertainty increases with inactivity, so you'll face big rating swings on return

After 7 daily leaderboard appearances, you become **Ranked**. Your Elo rank is determined by your rating compared to the other Ranked players.

After 7 days without a leaderboard appearance, you are considered inactive, and you become **Unranked**. Don't worry, your rating is preserved. At this point, a single top 30 result is enough to get you back in the rankings.

### Why did my rating change so much/little?

Several factors:
- **Opponent ratings**: Beating higher-rated players = bigger gains
- **Score margin**: Dominating performances give more weight
- **Games played**: New players (<10 games) have larger swings to find their true rating
- **Your rating level**: Gains shrink as you climb
- **Number of opponents**: Placing #1 means you beat 29 opponents, #30 means you beat none

### Why use Elo instead of other rating systems?

The true answer is that I'm a former chess player and I'll always be biased in favor of the Elo system. I did consider and/or try several other rating systems though:

| System | Pros | Why I didn't use it |
|--------|------|---------------------|
| **Glicko/Glicko-2** | Popular, tracks rating uncertainty | Designed for 1v1 matches, not 30-player daily competitions |
| **TrueSkill** | Robust skill-based matchmaking algorithm | Overkill for our use case. Also it's patented by Microsoft and I don't have "Microsoft lawyer" money |
| **Simple averages** | Easy to understand, easy to implement | "Underkill" for our use case. Doesn't account for opponent strength or improvement over time |
| **ELO** | Battle-tested, intuitive | Not quite perfect without some tweaks |

**Why Pairwise Elo works here:**
- Chess proved that Elo accurately ranks players over time through repeated competition
- My pairwise adaptation treats each daily leaderboard as 435 simultaneous "matches" (30 players = 30×29/2 pairs)
- The system is self-correcting: beat strong players, gain more; lose to weak players, lose more
- It's popular and intuitive: everyone understands "higher number = better"

### Why pairwise comparisons instead of just using daily rank?

Skill comparisons felt important to highlight. Daily rank is simply less effective for those evaluations:

- Finishing 1st against 29 weak players = same as 1st against 29 strong players
- A rank of 5th tells you nothing about who you beat or lost to
- No way to compare across different days with different player pools

**Why pairwise works better:**
- Beat a 2500-rated player? Big gain.
- Lose to a 1200-rated player? Big loss.
- The gains and losses depend on *who* you competed against.

### How do you handle only seeing the top 30 each day?

That shaped the system design a lot actually.

**The limitation:** Players ranked 31st or lower are invisible: I don't know their scores, their identities, or even how many of them there are.

**Why this is actually fine for Elo:** The pairwise system only compares players *who both appear on the same day*. If you're in the top 30, you get compared to the other 29 players. If you're not, you simply don't participate that day.

**Key implications:**
- **No penalty for missing days**: If you don't appear, your rating stays untouched
- **Appearing matters**: To gain or lose rating, you must show up in the top 30
- **Bottom of top 30 is meaningful**: Rank 30 means you made it, but barely. There is still some road ahead

**What I *can't* measure:**
- Players who never crack the top 30
- How much above the rest of the field the top 30 is
- The "true" skill of players who rarely appear

### What's the deal with rating compression?

Raw Elo scores are processed and then compressed using a hybrid system:
- Below 2700: Gentle logarithmic scaling (diminishing returns)
- Above 2700: Hyperbolic tangent compression toward the 3000 ceiling

This allows the high end of the distribution curve to mimic chess Elo, in the sense that:
- **2800+** is genuinely elite
- **2900** is legendary
- **3000** is the theoretical limits of human ability

While mostly aesthetics (compared to the raw ratings), it prevents runaway ratings while preserving meaningful differences.

### How do rivalries work?

The **Rivalries** feature identifies the most significant head-to-head matchups between players. A rivalry forms when two players have competed on the same daily leaderboard at least **7 times**.

**Three categories of rivalries:**

| Category | What it measures |
|----------|------------------|
| **Most Battles** | Pairs with the most head-to-head encounters |
| **Closest Rivals** | Pairs with the tightest win records (closest to 50-50) |
| **Elite Showdowns** | Top players who frequently battle each other at high ranks |

**How "closeness" is calculated:**

The closeness score combines two factors:
1. **Win ratio**: How close to 50-50 is the head-to-head record? (1.0 = perfectly even)
2. **Gap penalty**: Large absolute win gaps feel less competitive than small ones

```
closeness = (1 - |wins_diff| / total) × (1 / (1 + |wins_diff| / 20))
```

This means a 36-24 record (gap=12) scores as "closer" than 72-48 (gap=24), even though both are 60-40 ratios. The intuition: a 24-game lead feels more decisive than a 12-game lead.

**Top Rivals on Player Tracker:**

Each player's profile shows their top 6 rivals—opponents with competitive (closeness ≥ 0.5) head-to-head records, ranked by total encounters. The more history you share with someone, the more meaningful the rivalry.

## Glossary

| Term | Definition |
|------|------------|
| **Ranked** | Players in the main leaderboard (active + enough games) |
| **Unranked** | Players not in main leaderboard (<7 games or inactive >7 days) |
| **Elo Rank** | Your position among ranked players by Elo rating |
| **Rating** | Your compressed Elo score (higher = better) |
| **Raw Rating** | Your uncompressed Elo score (used internally) |
| **Daily Runs** | Number of top 30 finishes (appearances on the daily leaderboard) |
| **Daily #1** | Number of times you finished 1st on the daily leaderboard |
| **Daily #1 (%)** | Win rate: Daily #1 ÷ Daily Runs × 100 |
| **Daily Top10** | Number of times you finished in the top 10 |
| **Daily Top10 (%)** | Top 10 rate: Daily Top10 ÷ Daily Runs × 100 |
| **Daily Avg** | Average daily rank across all your runs |
| **7-Game Avg** | Average daily rank over your last 7 runs |
| **Daily Variance** | Standard deviation of your daily ranks (lower = more consistent) |
| **Daily Rank** | Your position on a specific day's leaderboard |
| **Rating Change** | How much your Elo changed that day |
| **Baseline** | The starting/median rating of 1500 |
| **Compression** | System that maps raw ratings to display ratings |
| **Rivalry** | A significant head-to-head matchup (≥7 encounters) |
| **Encounters** | Days where both players appeared on the same leaderboard |
| **Closeness** | How competitive a rivalry is (higher = more evenly matched) |
| **Top Rivals** | A player's 6 most competitive frequent opponents |

## License

- **Code**: MIT License - see [LICENSE](LICENSE)
- **Data**: CC-BY 4.0 for derived analytics - see [DATA_LICENSE.md](DATA_LICENSE.md)

Game data and leaderboard content belong to their respective owners.

---

*Built with 🫶 by N Prime, for the Die For The Lich community*
