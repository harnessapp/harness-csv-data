import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# --- PATH SETUP ---
REPO_ROOT = Path(__file__).resolve().parents[1]

MERGED_FILE = REPO_ROOT / "merged_file.csv"
OUTPUT_FILE = REPO_ROOT / "Hot Drivers.csv"

# --- CONFIG ---
DAYS_BACK = 365
MIN_STARTS = 100
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

# --- DATE WINDOW ---
current_date = datetime.today()
window_start = current_date - timedelta(days=DAYS_BACK)
merged_df = merged_df[merged_df["Date"] >= window_start]

# Sort so most recent runs appear first per driver
merged_df = merged_df.sort_values(by=["Driver", "Date"], ascending=[True, False])

# --- BUILD STATS ---
hot_drivers = []

for driver, driver_df in merged_df.groupby("Driver"):
    last_100 = driver_df.head(100)

    if len(last_100) < MIN_STARTS:
        continue

    starts = len(last_100)
    wins = (last_100["Placing"] == 1).sum()
    seconds = (last_100["Placing"] == 2).sum()
    thirds = (last_100["Placing"] == 3).sum()

    total_spend = last_100["Spend"].sum(skipna=True)
    total_pnl = last_100["P&L"].sum(skipna=True)

    roi_percent = (total_pnl / total_spend) * 100 if total_spend and total_spend != 0 else 0.0

    hot_drivers.append({
        "Driver": driver,
        "Starts": int(starts),
        "Wins": int(wins),
        "2nds": int(seconds),
        "3rds": int(thirds),
        "Spend": float(total_spend) if pd.notna(total_spend) else 0.0,
        "P&L": float(total_pnl) if pd.notna(total_pnl) else 0.0,
        "ROI %": float(roi_percent),
    })

hot_drivers_df = pd.DataFrame(hot_drivers)

# --- SORT / OUTPUT ---
if hot_drivers_df.empty:
    print("⚠️ No drivers met criteria (MIN_STARTS=100 in last 365 days). Writing empty CSV.")
    hot_drivers_df = pd.DataFrame(
        columns=["Driver", "Starts", "Wins", "2nds", "3rds", "Spend", "P&L", "ROI %"]
    )
else:
    # Hot first: more wins/placings
    hot_drivers_df = hot_drivers_df.sort_values(
        by=["Wins", "2nds", "3rds"],
        ascending=[False, False, False]
    )

print(f"Saving output (labelled {STATE_FILTER}) -> {OUTPUT_FILE}")
hot_drivers_df.to_csv(OUTPUT_FILE, index=False)

print("✅ Hot Drivers CSV created!")
