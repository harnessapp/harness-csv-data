import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# --- PATH SETUP ---
REPO_ROOT = Path(__file__).resolve().parents[1]

MERGED_FILE = REPO_ROOT / "merged_file.csv"
OUTPUT_FILE = REPO_ROOT / "Cold Trainers 30.csv"

# --- CONFIG ---
DAYS_BACK = 30
MIN_STARTS = 10
STATE_FILTER = "NSW"  # label only unless you implement real state filtering

# --- LOAD ---
merged_df = pd.read_csv(MERGED_FILE, low_memory=False)

merged_df.columns = merged_df.columns.str.strip()
print("Columns in merged_df:", merged_df.columns)

# --- CLEAN TYPES ---
merged_df["Date"] = pd.to_datetime(merged_df["Date"], dayfirst=True, errors="coerce")
merged_df = merged_df[merged_df["Date"].notna()]

merged_df["P&L"] = pd.to_numeric(merged_df["P&L"], errors="coerce")
merged_df["Spend"] = pd.to_numeric(merged_df["Spend"], errors="coerce")

merged_df["Placing"] = pd.to_numeric(merged_df["Placing"], errors="coerce")
merged_df = merged_df[merged_df["Placing"].notna()]

# --- WINDOW FILTER ---
current_date = datetime.today()
window_start = current_date - timedelta(days=DAYS_BACK)

merged_df = merged_df[merged_df["Date"] >= window_start]

# Sort to ensure latest first within trainer
merged_df = merged_df.sort_values(by=["Trainer", "Date"], ascending=[True, False])

# --- BUILD STATS ---
cold_trainers = []

for trainer, trainer_df in merged_df.groupby("Trainer"):
    last_30 = trainer_df  # already filtered to last 30 days

    if len(last_30) < MIN_STARTS:
        continue

    starts = len(last_30)
    wins = (last_30["Placing"] == 1).sum()
    seconds = (last_30["Placing"] == 2).sum()
    thirds = (last_30["Placing"] == 3).sum()

    total_spend = last_30["Spend"].sum(skipna=True)
    total_pnl = last_30["P&L"].sum(skipna=True)

    roi_percent = (total_pnl / total_spend) * 100 if total_spend and total_spend != 0 else 0.0

    cold_trainers.append({
        "Trainer": trainer,
        "Starts": int(starts),
        "Wins": int(wins),
        "2nds": int(seconds),
        "3rds": int(thirds),
        "Spend": float(total_spend) if pd.notna(total_spend) else 0.0,
        "P&L": float(total_pnl) if pd.notna(total_pnl) else 0.0,
        "ROI %": float(roi_percent),
    })

cold_trainers_df = pd.DataFrame(cold_trainers)

# --- SORT / OUTPUT ---
if cold_trainers_df.empty:
    print(f"⚠️ No trainers met criteria (last {DAYS_BACK} days, MIN_STARTS={MIN_STARTS}). Writing empty CSV.")
    cold_trainers_df = pd.DataFrame(
        columns=["Trainer", "Starts", "Wins", "2nds", "3rds", "Spend", "P&L", "ROI %"]
    )
else:
    # Cold first: fewer wins, then more starts, then more minor placings
    cold_trainers_df = cold_trainers_df.sort_values(
        by=["Wins", "Starts", "2nds", "3rds"],
        ascending=[True, False, True, True]
    )

print(f"Saving output (labelled {STATE_FILTER}) -> {OUTPUT_FILE}")
cold_trainers_df.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Cold Trainers (Last {DAYS_BACK} Days) CSV created!")
