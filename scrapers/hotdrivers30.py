import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# --- PATH SETUP ---
REPO_ROOT = Path(__file__).resolve().parents[1]

MERGED_FILE = REPO_ROOT / "merged_file.csv"
OUTPUT_FILE = REPO_ROOT / "Hot Drivers 30.csv"

# --- CONFIG ---
DAYS_BACK = 30
MIN_STARTS = 1           # keep behaviour: include anyone with >=1 start in window
STATE_FILTER = "NSW"     # label only unless you implement real state filtering

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

# Sort so latest runs appear first per driver
merged_df = merged_df.sort_values(by=["Driver", "Date"], ascending=[True, False])

# --- BUILD STATS ---
hot_drivers = []

for driver, driver_df in merged_df.groupby("Driver"):
    last_30 = driver_df  # already filtered to last 30 days

    if len(last_30) < MIN_STARTS:
        continue

    starts = len(last_30)
    wins = (last_30["Placing"] == 1).sum()
    seconds = (last_30["Placing"] == 2).sum()
    thirds = (last_30["Placing"] == 3).sum()

    total_spend = last_30["Spend"].sum(skipna=True)
    total_pnl = last_30["P&L"].sum(skipna=True)

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
    print(f"⚠️ No drivers found in last {DAYS_BACK} days. Writing empty CSV.")
    hot_drivers_df = pd.DataFrame(
        columns=["Driver", "Starts", "Wins", "2nds", "3rds", "Spend", "P&L", "ROI %"]
    )
else:
    hot_drivers_df = hot_drivers_df.sort_values(
        by=["Wins", "2nds", "3rds"],
        ascending=[False, False, False]
    )

print(f"Saving output (labelled {STATE_FILTER}) -> {OUTPUT_FILE}")
hot_drivers_df.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Hot Drivers (Last {DAYS_BACK} Days) CSV created!")
