import json
import re
import pandas as pd
from pathlib import Path

# --- CONFIG ---
DATA_FOLDER = Path(r"C:\Users\Nicol\DFTL_score_system\assets")  # folder with your JSON files
MIN_DATE = "2025-11-10"
AUTHOR_NAME = "DFTL_BOT"

# --- Regex patterns ---
# Date format: `date: DD/MM/YYYY` (backticks around the whole thing)
DATE_RE = re.compile(r"`date:\s*(\d{2}/\d{2}/\d{4})`")
# Rank 1: :crown_dftl: **PlayerName** - 12345 (names may contain hyphens)
RANK1_RE = re.compile(r":crown_dftl:\s*\*\*(.+)\*\*\s+-\s+(\d+)\s*$")
# Ranks 2-30: #2 **PlayerName** - 12345 (names may contain hyphens)
RANK_RE = re.compile(r"#(\d+)\s+\*\*(.+)\*\*\s+-\s+(\d+)\s*$")

def strip_markdown(name):
    """Remove **bold**, `backticks`, and leading/trailing spaces"""
    return re.sub(r"[*`]", "", name).strip()

def parse_leaderboard_content(content):
    """Parse one leaderboard message content into a list of rows"""
    lines = content.splitlines()
    leaderboard_rows = []
    date_found = None

    for line in lines:
        # Extract date
        if not date_found:
            m_date = DATE_RE.search(line)
            if m_date:
                date_found = m_date.group(1)
        
        # Extract rank 1
        m1 = RANK1_RE.match(line)
        if m1:
            name, score = m1.groups()
            leaderboard_rows.append((date_found, strip_markdown(name), 1, int(score)))
            continue

        # Extract ranks 2-30
        m = RANK_RE.match(line)
        if m:
            rank, name, score = m.groups()
            leaderboard_rows.append((date_found, strip_markdown(name), int(rank), int(score)))
    
    return leaderboard_rows

# --- Auto-discover JSON files ---
JSON_FILES = list(DATA_FOLDER.glob("*.json"))
print(f"Found {len(JSON_FILES)} JSON files in {DATA_FOLDER}")

# --- Load and parse all JSON files ---
all_rows = []

for json_file in JSON_FILES:
    with open(json_file, "r", encoding="utf-8") as f:
        json_data = json.load(f)

    # Handle dict with "messages" key or plain list
    if isinstance(json_data, dict) and "messages" in json_data:
        messages_list = json_data["messages"]
    elif isinstance(json_data, list):
        messages_list = json_data
    else:
        print(f"Skipping {json_file} — unrecognized format")
        continue

    for msg in messages_list:
        # Skip if author is not the bot
        author = msg.get("author")
        if not isinstance(author, dict) or author.get("name") != AUTHOR_NAME:
            continue

        content = msg.get("content")
        if not content or "Top 30 Daily Leaderboard" not in content:
            continue

        try:
            rows = parse_leaderboard_content(content)
            all_rows.extend(rows)
        except Exception as e:
            print(f"Failed to parse message id {msg.get('id')}: {e}")

# --- Create DataFrame ---
df = pd.DataFrame(all_rows, columns=["date", "player_name", "rank", "score"])

# --- Clean and convert dates ---
df['date'] = df['date'].astype(str).str.strip(" `")  # remove backticks and whitespace
df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')  # convert to datetime

# --- Optional: check for parsing issues ---
if df['date'].isna().any():
    print("Warning: Some dates could not be parsed. Check your data.")

# --- Sort and reset index ---
df = df.sort_values(by=["date", "rank"]).reset_index(drop=True)

# --- Sanity checks ---
def run_sanity_checks(dataframe, label="DataFrame"):
    """Run validation checks on the leaderboard data"""
    issues = []

    # Check for positive scores
    negative_scores = dataframe[dataframe['score'] <= 0]
    if not negative_scores.empty:
        issues.append(f"Found {len(negative_scores)} rows with non-positive scores")

    # Check each date for 30 ranks and no duplicates
    for date, group in dataframe.groupby('date'):
        date_str = date.strftime('%Y-%m-%d') if pd.notna(date) else str(date)

        # Check rank count
        if len(group) != 30:
            issues.append(f"Date {date_str}: Expected 30 ranks, found {len(group)}")

        # Check for duplicate ranks
        dup_ranks = group[group['rank'].duplicated()]['rank'].unique()
        if len(dup_ranks) > 0:
            issues.append(f"Date {date_str}: Duplicate ranks found: {list(dup_ranks)}")

        # Check rank range (should be 1-30)
        if group['rank'].min() != 1 or group['rank'].max() != 30:
            issues.append(f"Date {date_str}: Rank range is {group['rank'].min()}-{group['rank'].max()}, expected 1-30")

    if issues:
        print(f"\n--- Sanity Check Warnings ({label}) ---")
        for issue in issues[:10]:  # Limit to first 10 warnings
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
    else:
        print(f"\n--- Sanity Check Passed ({label}) ---")

    return len(issues) == 0

run_sanity_checks(df, "Full DataFrame")

# --- Filtered DataFrame for relevant dates ---
# Note: MIN_DATE is in ISO format (YYYY-MM-DD), don't use dayfirst
df_filtered = df[df['date'] >= pd.to_datetime(MIN_DATE)].copy()

# --- Summary ---
print("\n--- Summary ---")
print(f"Full DataFrame shape: {df.shape}")
print(f"Filtered DataFrame shape: {df_filtered.shape}")
print(f"Date range (full): {df['date'].min()} to {df['date'].max()}")
print(f"Date range (filtered): {df_filtered['date'].min()} to {df_filtered['date'].max()}")
print(f"Unique players (filtered): {df_filtered['player_name'].nunique()}")

if not df_filtered.empty:
    run_sanity_checks(df_filtered, "Filtered DataFrame")
    print("\nSample data (first 10 rows):")
    print(df_filtered.head(10).to_string())

# --- Create steam_demo DataFrame (before early access) ---
df_steam_demo = df[df['date'] < pd.to_datetime(MIN_DATE)].copy()
print(f"\nSteam Demo DataFrame shape: {df_steam_demo.shape}")
if not df_steam_demo.empty:
    print(f"Date range (steam_demo): {df_steam_demo['date'].min()} to {df_steam_demo['date'].max()}")
    print(f"Unique players (steam_demo): {df_steam_demo['player_name'].nunique()}")
    run_sanity_checks(df_steam_demo, "Steam Demo DataFrame")

# --- Export to CSV ---
OUTPUT_FOLDER = DATA_FOLDER.parent / "output"
OUTPUT_FOLDER.mkdir(exist_ok=True)

# Get last date for filename (format: YYYYMMDD)
last_date_full = df['date'].max().strftime('%Y%m%d')
last_date_early_access = df_filtered['date'].max().strftime('%Y%m%d') if not df_filtered.empty else last_date_full
last_date_steam_demo = df_steam_demo['date'].max().strftime('%Y%m%d') if not df_steam_demo.empty else "00000000"

full_csv = OUTPUT_FOLDER / f"full_leaderboard_{last_date_full}.csv"
early_access_csv = OUTPUT_FOLDER / f"early_access_leaderboard_{last_date_early_access}.csv"
steam_demo_csv = OUTPUT_FOLDER / f"steam_demo_leaderboard_{last_date_steam_demo}.csv"

df.to_csv(full_csv, index=False)
df_filtered.to_csv(early_access_csv, index=False)
if not df_steam_demo.empty:
    df_steam_demo.to_csv(steam_demo_csv, index=False)

print(f"\n--- Exported CSV files ---")
print(f"Full data: {full_csv}")
print(f"Early access data: {early_access_csv}")
if not df_steam_demo.empty:
    print(f"Steam demo data: {steam_demo_csv}")
