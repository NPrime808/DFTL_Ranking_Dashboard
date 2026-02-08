# Rivalries Tab Implementation Plan

## Overview

A new "🔥 Rivalries" tab showcasing the greatest head-to-head matchups between players. Features three categories highlighting different aspects of competitive relationships.

## Categories

### 1. Most Battles
- **Metric:** Total encounters (days both players participated)
- **Display:** "104 battles"
- **Purpose:** Highlights long-standing competitive relationships

### 2. Closest Rivals
- **Metric:** `closeness = 1 - abs(wins_p1 - wins_p2) / total_encounters`
- **Display:** "98.2% close" or "55-53 record"
- **Filter:** Minimum 7 encounters to qualify
- **Purpose:** Highlights evenly-matched competitors

### 3. Elite Showdowns
- **Metric:** `elite_score = total_encounters / avg_combined_rank`
- **Display:** "Avg rank: 3.2" or "Elite score: 12.4"
- **Purpose:** Highlights top players who frequently battle each other at the top

## UI Design

### Layout
- Card grid matching Hall of Fame style
- 3 cards (one per category), each showing top 5 rivalries

### Rivalry Row Format
```
🥇 Player A  vs  Player B
   55 - 49  •  104 battles  →
```

### Interactions
- Clicking a rivalry → navigates to Duels tab with both players pre-selected
- URL format: `?tab=duels&player1=PlayerA&player2=PlayerB`

## Data Requirements

### Pre-computed Files

**✅ IMPLEMENTED:** `src/elo/rivalries.py` module generates rivalry data during the Elo pipeline.

#### Output Files
- `data/processed/early_access_rivalries_YYYYMMDD.csv`
- `data/processed/full_rivalries_YYYYMMDD.csv`

#### Schema
```csv
player1,player2,total_encounters,p1_wins,p2_wins,p1_avg_rank,p2_avg_rank,avg_combined_rank,closeness,elite_score
```

| Column | Type | Description |
|--------|------|-------------|
| `player1` | str | First player (alphabetically ordered) |
| `player2` | str | Second player (alphabetically ordered) |
| `total_encounters` | int | Days both players participated |
| `p1_wins` | int | Games where player1 ranked higher |
| `p2_wins` | int | Games where player2 ranked higher |
| `p1_avg_rank` | float | Player1's average rank when they met |
| `p2_avg_rank` | float | Player2's average rank when they met |
| `avg_combined_rank` | float | Average of both players' ranks |
| `closeness` | float | 1 - abs(p1_wins - p2_wins) / total (0-1) |
| `elite_score` | float | total_encounters / avg_combined_rank |

#### Usage
```bash
python -m src.elo.rivalries
```

Or import in code:
```python
from src.elo.rivalries import compute_rivalries, process_rivalries
```

#### Statistics (as of 2026-02-08)
| Dataset | Total Pairs | Qualifying Rivalries (≥7 encounters) |
|---------|-------------|--------------------------------------|
| Early Access | 17,954 | 855 |
| Full | 36,434 | 2,149 |

## Implementation Steps

### Phase 1: Data Pipeline ✅ COMPLETE

**Module:** `src/elo/rivalries.py`

- ✅ `compute_rivalries(df_history)` - Core computation function
- ✅ `get_top_rivalries(df_rivalries, n=10)` - Get top N per category
- ✅ `process_rivalries(history_csv, output_prefix, label)` - Process and export
- ✅ `find_latest_history(pattern)` - Auto-detect latest history file
- ✅ `main()` - Process both datasets

**Design decisions:**
- Ties (same rank) count as neither player's win
- All qualifying pairs included (no inactive player filter)
- Separate file per dataset (early_access, full)

### Phase 2: Dashboard ✅ COMPLETE

- ✅ `load_rivalries_data(dataset_prefix)` - Cached data loader
- ✅ `generate_rivalry_cards(df_rivalries)` - Card generator with 3 categories
- ✅ Added "🔥 Rivalries" tab to navigation
- ✅ Tab content with rivalry cards grid
- ✅ Click-to-navigate to Duels tab with both players pre-selected

### Phase 3: Styling ✅ COMPLETE

- ✅ `.rivalry-cards-grid` CSS class with responsive breakpoints
- ✅ Matches Hall of Fame card styling (glass effects, theme-adaptive)
- ✅ Hover states on clickable rivalry rows
- ✅ Responsive layout: 3 columns (desktop) → 2 columns (tablet) → 1 column (mobile)

## Open Questions (Resolved)

1. ~~Should ties (same rank on a day) count as 0.5 wins each, or be excluded?~~
   **Decision:** Ties excluded (neither player gets a win)
2. ~~Include inactive players in rivalries, or filter to recent activity?~~
   **Decision:** Include all qualifying pairs
3. ~~Dataset toggle - show rivalries for selected dataset only?~~
   **Decision:** Yes, separate files per dataset, dashboard respects dataset toggle

## Performance Notes

- 900+ players = 36k+ active pairs (players who met at least once)
- After filtering (≥7 encounters): 855 (Early Access), 2,149 (Full)
- Pre-computation makes dashboard loading instant
- Pipeline runtime: ~1 second for both datasets combined

## Future Enhancements

- "Rivalry of the Month" - most active recent rivalry
- Head-to-head trend chart (win rate over time)
- "Nemesis" feature - show each player's top rival on their Tracker page
- Lead change tracking ("Most Dramatic" category)
