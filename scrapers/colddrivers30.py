import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# --- PATH SETUP ---
# Repo root = one level up from /scrapers
REPO_ROOT = Path(__file__).resolve().parents[1]

# Input file (big local file lives in repo root; keep it in .gitignore)
MERGED_FILE = REPO_ROOT / "merged_file.csv"

# Output file (repo root)
OUTPUT_FILE = REPO_ROOT / "Cold Drivers 30.csv"

# --- CONFIG ---
DAYS_BACK = 30          # Filter last 30 days
MIN_STARTS = 10         # Only include drivers with at least 10 starts in window
STATE_FILTER = "NSW"    # Optional label only (see note below)

# --- LOAD ---
merged_df = pd.read_csv(MERGED_FILE, low_memory=False)

# Strip any extra whitespace from column names
merged_df.columns = merged_df.columns.str.strip()

print("Columns in merged_df:", merged_df.columns)

# --- CLEAN / TYPES ---
# Parse Date safely (handles weird rows)
merged_df["Date"] = pd.to_datetime(merged_df["Date"], dayfirst=True, errors="coerce")
merged_df = merged_df[merged_df["Date"].notna()]

# Convert P&L and Spend to numeric
merged_df["P&L"] = pd.to_numeric(merged_df["P&L"], errors="coerce")
merged_df["Spend"] = pd.to_numeric(merged_df["Spend"], errors="coerce")

# Placing numeric and valid
merged_df["Placing"] = pd.to_numeric(merged_df["Placing"], errors="coerce")
merged_df = merged_df[merged_df["Placing"].notna()]

# --- WINDOW FILTER ---
current_date = datetime.today()
window_start = current_date - timedelta(days=DAYS_BACK)

merged_df = merged_df[merged_df["Date"] >= window_start]

# Sort to ensure "latest first" within driver (not strictly required, but consistent)
merged_df = merged_df.sort_values(by=["Driver", "Date"], ascending=[True, False])

# --- BUILD STATS ---
cold_drivers = []

for driver, driver_df in merged_df.groupby("Driver"):
    # driver_df is already limited to last 30 days by merged_df filter
    last_30 = driver_df

    if len(last_30) < MIN_STARTS:
        continue

    starts = len(last_30)
    wins = (last_30["Placing"] == 1).sum()
    seconds = (last_30["Placing"] == 2).sum()
    thirds = (last_30["Placing"] == 3).sum()

    total_spend = last_30["Spend"].sum(skipna=True)
    total_pnl = last_30["P&L"].sum(skipna=True)

    roi_percent = (total_pnl / total_spend) * 100 if total_spend and total_spend != 0 else 0.0

    cold_drivers.append({
        "Driver": driver,
        "Starts": int(starts),
        "Wins": int(wins),
        "2nds": int(seconds),
        "3rds": int(thirds),
        "Spend": float(total_spend) if pd.notna(total_spend) else 0.0,
        "P&L": float(total_pnl) if pd.notna(total_pnl) else 0.0,
        "ROI %": float(roi_percent),
    })

cold_drivers_df = pd.DataFrame(cold_drivers)

# --- SORT / OUTPUT ---
if cold_drivers_df.empty:
    print(f"⚠️ No drivers met criteria (last {DAYS_BACK} days, MIN_STARTS={MIN_STARTS}). Writing empty CSV.")
    cold_drivers_df = pd.DataFrame(columns=["Driver", "Starts", "Wins", "2nds", "3rds", "Spend", "P&L", "ROI %"])
else:
    # Cold first: fewer wins, and within that more starts (so “proven cold” rises)
    cold_drivers_df = cold_drivers_df.sort_values(
        by=["Wins", "Starts"],
        ascending=[True, False]
    )

# NOTE: Your original “State” filter never actually worked because cold_drivers_df
# doesn't contain a 'State' column (you didn’t carry it through).
# Keeping this as a label only, unless you want to implement per-state attribution.
print(f"Saving output (labelled {STATE_FILTER}) -> {OUTPUT_FILE}")

cold_drivers_df.to_csv(OUTPUT_FILE, index=False)
print(f"✅ Cold Drivers (Last {DAYS_BACK} Days) CSV created!")
