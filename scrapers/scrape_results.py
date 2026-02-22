# scrape_results.py
import os
import sys
import re
import time
import random
from datetime import datetime, timedelta
import shutil
import glob


import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

# ============================================================
# CONFIG
# ============================================================
REBUILD_ONLY = False          # True = rebuild-only (no scraping)
DAYS_BACK = 1               # when scraping: how many days back to check (from yesterday)
DISCOVERY_DAYS = 1          # all venues (yesterday + day before)
BACKFILL_EXTRA_DAYS = 0     # further back, but only meetings already in merged_file.csv

OUTPUT_FILE = "extra_results.csv"
MERGED_FILE = "merged_file.csv"

SHRINK_K = 100
IGNORE_WIDTHS = {"TO"}      # rows with Width in this set are excluded from Step 3 context build

print(f"🔧 REBUILD_ONLY={REBUILD_ONLY}")


BACKUP_ROOT = os.environ.get("BACKUP_ROOT", "backups")  # GitHub-safe default
BACKUPS_ENABLED = os.environ.get("BACKUPS_ENABLED", "1").strip() in ("1", "true", "True", "yes", "YES")


def backup_file(
    path: str,
    backups_root: str = BACKUP_ROOT,
    keep_last: int = 7,
) -> str | None:
    r"""
    Creates 1 backup per day (overwrites same-day), stored under:
      <backups_root>\backups\<filename>.YYYYMMDD.bak

    Also prunes to keep only the most recent `keep_last` daily backups.
    """

    if not BACKUPS_ENABLED:
        return None

    if not os.path.exists(path):
        return None
        
    backups_dir = os.path.join(backups_root, "backups")
    os.makedirs(backups_dir, exist_ok=True)

    base = os.path.basename(path)
    day = datetime.now().strftime("%Y%m%d")  # once-per-day key
    backup_path = os.path.join(backups_dir, f"{base}.{day}.bak")

    # Copy (will overwrite if same day already exists)
    try:
        shutil.copy2(path, backup_path)
    except Exception as e:
        print(f"⚠️ Backup failed for {path}: {e}")
        return None

    # Prune: keep last N daily backups for this file
    pattern = os.path.join(backups_dir, f"{base}.*.bak")
    backups = sorted(glob.glob(pattern), reverse=True)  # newest first by filename

    if keep_last is not None and keep_last > 0 and len(backups) > keep_last:
        for old in backups[keep_last:]:
            try:
                os.remove(old)
            except Exception:
                pass

    return backup_path

def backup_python_script_daily(src_file: str, backup_dir: str, keep_last: int = 7):
    """
    Backs up the python script to the specified backup directory and keeps the last 'keep_last' backups.

    :param src_file: The path to the source file (scrape_results.py)
    :param backup_dir: The backup directory where the file will be saved
    :param keep_last: Number of backups to keep
    """
    # Ensure backup directory exists
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # Get the current date to append to the backup filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"scrape_results_{current_date}.py"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Copy the source file to the backup directory
    shutil.copy2(src_file, backup_path)  # copy2 preserves metadata like timestamps
    
    # Manage the number of backups (delete older ones if exceeding the limit)
    backup_files = sorted(
        [f for f in os.listdir(backup_dir) if f.startswith("scrape_results_")],
        reverse=True
    )
    
    # If there are more than 'keep_last' backups, remove the oldest ones
    if len(backup_files) > keep_last:
        for old_backup in backup_files[keep_last:]:
            os.remove(os.path.join(backup_dir, old_backup))
        print(f"Removed older backups, keeping the latest {keep_last} backups.")
    else:
        print(f"Backup created: {backup_filename}")


def stamp_published_market_into_merged(
    merged_csv="merged_file.csv",
    published_csv="published_markets.csv",
    odds_src_col="Fair Odds",
    pct_src_col="Fair %",
    overround_src_col="RaceOverround",
    placing_col="Placing",
    sp_col="SP",
):
    """
    Stamps FINAL 'closest to jump' published odds into merged_file.csv using RunnerAnchor,
    then calculates:
      Published Spend = 100 / Published Odds
      Published P&L   = if Placing==1 -> Spend*(SP-1) else -Spend

    'Closest to jump' is defined as the latest PublishedAt <= RaceStartDT,
    where RaceStartDT is built from:
      - Date from published_markets.csv
      - Time from merged_file.csv (since you said merged_file has Time)
    """

    import os
    import pandas as pd
    import numpy as np

    if not os.path.exists(merged_csv):
        print(f"⚠️ stamp_published_market_into_merged: missing {merged_csv}")
        return
    if not os.path.exists(published_csv):
        print(f"⚠️ stamp_published_market_into_merged: missing {published_csv}")
        return

    mrg = pd.read_csv(merged_csv, dtype=str).fillna("")
    pub = pd.read_csv(published_csv, dtype=str).fillna("")

    if "RunnerAnchor" not in mrg.columns or "RunnerAnchor" not in pub.columns:
        print("⚠️ stamp_published_market_into_merged: RunnerAnchor missing in one of the files")
        return

    if "PublishedAt" not in pub.columns:
        print("⚠️ stamp_published_market_into_merged: PublishedAt missing in published_markets.csv")
        return

    # ---- parse PublishedAt ----
    pub["_PublishedAtDT"] = pd.to_datetime(pub["PublishedAt"], errors="coerce")
    pub = pub[pub["_PublishedAtDT"].notna()].copy()
    if pub.empty:
        print("⚠️ stamp_published_market_into_merged: no valid PublishedAt rows to use")
        return

    # ---- RaceStartDT ----
    # Use Date from published_markets.csv + Time from merged_file.csv via RunnerAnchor
    if "Date" not in pub.columns:
        print("⚠️ stamp_published_market_into_merged: Date missing in published_markets.csv")
        return
    if "Time" not in mrg.columns:
        print("⚠️ stamp_published_market_into_merged: Time missing in merged_file.csv")
        return

    mrg_time = mrg[["RunnerAnchor", "Time"]].drop_duplicates("RunnerAnchor")
    pub = pub.merge(mrg_time, on="RunnerAnchor", how="left")

    dt_str = (pub["Date"].astype(str).str.strip() + " " + pub["Time"].astype(str).str.strip()).str.strip()
    pub["_RaceStartDT"] = pd.to_datetime(dt_str, errors="coerce", dayfirst=True)

    # Keep only rows where we could compute RaceStartDT
    pub = pub[pub["_RaceStartDT"].notna()].copy()
    if pub.empty:
        print("⚠️ stamp_published_market_into_merged: could not build RaceStartDT for any rows")
        return

    # Only snapshots at or before jump time
    pub = pub[pub["_PublishedAtDT"] <= pub["_RaceStartDT"]].copy()
    if pub.empty:
        print("⚠️ stamp_published_market_into_merged: no snapshots before jump (PublishedAt <= RaceStartDT)")
        return

    # Exclude scratched snapshots (matches your conventions)
    if "Barrier" in pub.columns:
        pub = pub[pub["Barrier"].astype(str).str.upper().str.strip() != "SCR"].copy()
    if "Driver" in pub.columns:
        pub = pub[pub["Driver"].astype(str).str.upper().str.strip() != "SCRATCHED"].copy()

    # Pick closest-to-jump: latest PublishedAt per RunnerAnchor
    pub = pub.sort_values("_PublishedAtDT").drop_duplicates(subset=["RunnerAnchor"], keep="last").copy()

    # ---- prepare stamp columns ----
    STAMP = {
        odds_src_col: "Published Odds",
        pct_src_col: "Published %",
        overround_src_col: "Published Overround",
        "PublishedAt": "Published At",
    }

    # Ensure target cols exist in merged
    for tgt in STAMP.values():
        if tgt not in mrg.columns:
            mrg[tgt] = ""

    # Reduce pub to needed cols
    keep = ["RunnerAnchor"] + [c for c in STAMP.keys() if c in pub.columns]
    pub_small = pub[keep].copy()

    # Merge
    out = mrg.merge(pub_small, on="RunnerAnchor", how="left", suffixes=("", "_snap"))

    # Fill blanks only (don’t overwrite if already set)
    for src, tgt in STAMP.items():
        # prefer snapshot column if present
        snap_col = f"{src}_snap"
        use_col = snap_col if snap_col in out.columns else (src if src in out.columns else None)
        if use_col is None:
            continue

        blank = out[tgt].astype(str).str.strip() == ""
        out.loc[blank, tgt] = out.loc[blank, use_col].astype(str)

        # drop the snapshot helper column (leave original merged cols alone)
        if snap_col in out.columns:
            out.drop(columns=[snap_col], inplace=True, errors="ignore")

    print("---- Stamp sanity ----")
    print("Published Odds nonblank:", (out["Published Odds"].astype(str).str.strip() != "").sum())
    print("Published Spend nonblank:", (out["Published Spend"].astype(str).str.strip() != "").sum())
    print("Published P&L nonblank:", (out["Published P&L"].astype(str).str.strip() != "").sum())



    # ---- Published Spend & Published P&L (net) ----
    spend_col = "Published Spend"
    pl_col = "Published P&L"

    if spend_col not in out.columns:
        out[spend_col] = ""
    if pl_col not in out.columns:
        out[pl_col] = ""

    odds = pd.to_numeric(out["Published Odds"], errors="coerce")
    sp_raw = out.get(sp_col, "").astype(str).str.replace("\u00A0", " ", regex=False).str.strip()

    # Extract numeric part (handles "$3.30", "3.30F", etc.)
    sp_clean = sp_raw.str.extract(r"(\d+(?:\.\d+)?)")[0]

    sp = pd.to_numeric(sp_clean, errors="coerce")

    placing = out.get(placing_col, "").astype(str).str.strip()
    is_win = placing.eq("1")

    spend = np.where((odds.notna()) & (odds > 0), 100.0 / odds, np.nan)
    pl = np.where(
        (spend == spend) & is_win & sp.notna(),
        spend * (sp - 1.0),
        np.where(spend == spend, -spend, np.nan)
    )

    out[spend_col] = np.where(np.isfinite(spend), spend, "")
    out[pl_col] = np.where(np.isfinite(pl), pl, "")

    # Write back
    bk2 = backup_file(merged_csv)
    if bk2:
        print(f"🧯 Backup created (post-stamp): {bk2}")

    atomic_to_csv(out, merged_csv)
    print("✅ Stamped Published Odds (closest-to-jump) + Published Spend/P&L into merged_file.csv")





def atomic_to_csv(df: pd.DataFrame, path: str):
    """Write to path.tmp then atomically replace path (prevents truncation on crash)."""
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)  # atomic on Windows



# ============================================================
# HELPERS
# ============================================================
def _distance_bucket(d):
    if pd.isna(d):
        return "UNK"
    if d <= 1700:
        return "SHORT"
    elif d <= 2200:
        return "MIDDLE"
    else:
        return "LONG"


def _ensure_datetime_from_date(df: pd.DataFrame, date_col="Date") -> pd.Series:
    """
    Converts Date (dd/mm/yyyy) into a proper datetime Series.
    Never overwrites df[date_col] itself.
    """
    if date_col not in df.columns:
        return pd.to_datetime(pd.Series([pd.NaT] * len(df)), errors="coerce")
    s = df[date_col].astype(str).str.strip()
    s = s.replace({"": np.nan, "nan": np.nan, "NaN": np.nan, "None": np.nan})
    return pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")


def _ensure_horse_runs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures 'Horse Runs' exists and is calculated as
    number of prior runs for the horse (chronological, prior-only).

    First run = 0
    Second run = 1
    etc.
    """
    out = df.copy()

    # Required columns
    if "Horse" not in out.columns:
        out["Horse"] = ""

    if "DateEffective" not in out.columns:
        out["DateEffective"] = _ensure_datetime_from_date(out, "Date")

    if "RunnerAnchor" not in out.columns:
        out["RunnerAnchor"] = ""

    # Clean horse key
    out["_horse_key"] = (
        out["Horse"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Ensure datetime
    out["DateEffective"] = pd.to_datetime(out["DateEffective"], errors="coerce")

    # Stable chronological ordering
    out = out.sort_values(
        ["_horse_key", "DateEffective", "RunnerAnchor"],
        kind="mergesort"
    )

    # Compute prior-only count
    out["Horse Runs"] = (
        out.groupby("_horse_key", sort=False)
           .cumcount()
    )

    # Restore original row order
    out = out.sort_index()

    out.drop(columns=["_horse_key"], inplace=True)

    return out



def _split_meeting_code(meeting_code: str):
    """
    meeting_code like 'AP310126' => ('AP', '310126')
    Safe for junk values.
    """
    mc = str(meeting_code or "").strip().upper()
    if len(mc) < 8:
        return None, None
    return mc[:2], mc[2:]


def _existing_meetings_in_date_window(master_csv: str, start_dt: datetime, end_dt: datetime) -> list[str]:
    """
    Returns unique RaceAnchor meeting codes in merged_file.csv whose Date falls in [start_dt, end_dt].
    start_dt/end_dt are datetime objects (date part used).
    """
    if not os.path.exists(master_csv):
        return []

    try:
        dfm = pd.read_csv(master_csv, dtype=str, low_memory=False)
    except Exception as e:
        print(f"⚠️ Could not read {master_csv} for backfill targets: {e}")
        return []

    if "RaceAnchor" not in dfm.columns or "Date" not in dfm.columns:
        return []

    dt = _ensure_datetime_from_date(dfm, "Date")
    if dt.isna().all():
        return []

    # Normalise to date (no time)
    d0 = start_dt.date()
    d1 = end_dt.date()

    mask = dt.dt.date.between(d0, d1)
    if not mask.any():
        return []

    meetings = (
        dfm.loc[mask, "RaceAnchor"]
        .astype(str)
        .str.strip()
        .str.upper()
        .replace({"": np.nan, "NAN": np.nan, "NONE": np.nan, "NULL": np.nan})
        .dropna()
        .unique()
        .tolist()
    )
    return sorted(set(meetings))



def _clean_person_name(s: str) -> str:
    if not s:
        return s
    # remove any trailing parenthetical like "(C,cl)", "(C)", "(cl)" incl. surrounding spaces
    return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()


# --- MarginClean logic (used for Ind Half denom) ---
_MARGIN_MAP = {
    "SHFHD": 0.1,
    "HFHD": 0.2,
    "HD": 0.4,
    "HFNK": 0.5,
    "NK": 1.0,
    "": 0.0,
}


def _norm_sc(series: pd.Series) -> pd.Series:
    """
    Normalise StewardsComments for consistent matching:
    - convert NBSP to space
    - lower
    - remove punctuation -> spaces
    - compress whitespace
    """
    s = series.astype(str).fillna("")
    s = s.str.replace("\u00A0", " ", regex=False)
    s = s.str.lower()
    s = s.str.replace(r"[^a-z0-9\s]", " ", regex=True)
    s = s.str.replace(r"\s+", " ", regex=True).str.strip()
    return s



def _placing_is_numeric(s) -> bool:
    """
    True only if placing is a plain integer like '1', '2', '10'.
    False for 'r', 'd', '', 'nan', etc.
    """
    if s is None:
        return False
    t = str(s).strip().lower()
    if t in ("", "nan", "none", "null"):
        return False
    return bool(re.fullmatch(r"\d+", t))


def _compute_margin_clean(series: pd.Series) -> pd.Series:
    def clean_one(value):
        if pd.isna(value):
            return 0.0
        v = str(value).strip().upper().replace("M", "")
        if v in _MARGIN_MAP:
            return _MARGIN_MAP[v]
        try:
            return float(v)
        except ValueError:
            return 0.0
    return series.apply(clean_one)


# --- BellPosition -> Half Distance / Width mappings ---
_HALF_DIST_MAPPING = {
    "LEAD": 0.0, "B/LEAD": 4.0, "DEATH": 2.0,
    "1X1": 6.0, "1X2": 10.0, "1X3": 14.0, "1X4": 18.0, "1X5": 22.0, "1X6": 26.0,
    "1X7": 30.0, "1X8": 34.0, "1X9": 38.0,
    "3PEGS": 8.0, "4PEGS": 12.0, "5PEGS": 16.0, "6PEGS": 20.0, "7PEGS": 24.0, "8PEGS": 28.0, "9PEGS": 32.0,
    "3WIDE": 3.0,
    "3X1": 7.0, "3X2": 11.0, "3X3": 15.0, "3X4": 19.0, "3X5": 23.0,
    "TO": 99.0,
    "Not coded": np.nan,
    "0": np.nan,
}

_WIDTH_MAPPING = {
    "LEAD": "PEGS",
    "B/LEAD": "PEGS",
    "3PEGS": "PEGS", "4PEGS": "PEGS", "5PEGS": "PEGS", "6PEGS": "PEGS", "7PEGS": "PEGS", "8PEGS": "PEGS", "9PEGS": "PEGS",
    "DEATH": "DEATH",
    "1X1": "R/LINE", "1X2": "R/LINE", "1X3": "R/LINE", "1X4": "R/LINE", "1X5": "R/LINE", "1X6": "R/LINE", "1X7": "R/LINE", "1X8": "R/LINE",
    "3WIDE": "R/LINE", "3X1": "R/LINE", "3X2": "R/LINE", "3X3": "R/LINE", "3X4": "R/LINE", "3X5": "R/LINE",
    "TO": "TO",
}


def _ensure_race_stats(master: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures Race First Half / Race Last Half / Race Last Mile / Race Mile Rate and VenDistGaitStart exist.
    """
    df = master.copy()

    # Required for race stats
    for col in ["1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter", "LeadTime", "Distance"]:
        if col not in df.columns:
            df[col] = np.nan

    for col in ["1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter", "LeadTime", "Distance"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Race First Half"] = df["1st Quarter"] + df["2nd Quarter"]
    df["Race Last Half"] = df["3rd Quarter"] + df["4th Quarter"]
    df["Race Last Mile"] = df["1st Quarter"] + df["2nd Quarter"] + df["3rd Quarter"] + df["4th Quarter"]

    # Mile Rate (LeadTime + quarters) / Distance * 1609
    denom = df["Distance"].replace(0, np.nan)
    df["Race Mile Rate"] = (df["LeadTime"] + df["Race Last Mile"]) / denom * 1609

    # VenDistGaitStart
    for col in ["Venue", "Gait", "Start"]:
        if col not in df.columns:
            df[col] = ""

    if "VenDistGaitStart" not in df.columns:
        df["VenDistGaitStart"] = ""

    df["VenDistGaitStart"] = (
        df["Venue"].astype(str).str.strip() + "_" +
        df["Distance"].astype(str).str.strip() + "_" +
        df["Gait"].astype(str).str.lower().str.strip() + "_" +
        df["Start"].astype(str).str.lower().str.strip()
    )

    return df


def _ensure_half_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures 'Half Time' exists and is backfilled.

    # Debugging: Check the columns in the DataFrame before doing any work
    print("Columns in the DataFrame:", df.columns)

    Definition (horse-specific 'to the 800m' mile rate, rounded to nearest full second):
      Half Time = (LeadTime + 1st Quarter + 2nd Quarter) / (Distance - Half Distance - 800) * 1609

    Notes:
    - Requires Distance >= 1609 (otherwise blank)
    - Requires denom > 0 (Distance - Half Distance - 800)
    - Fills Half Distance from BellPosition mapping when missing
    - Blanks Half Time for obvious non-performances (TO / Margin>99 / non-numeric placing)
    """
    out = df.copy()

    # Ensure required columns exist (so we never crash)
    for col in ["LeadTime", "1st Quarter", "2nd Quarter", "Distance", "Half Distance", "BellPosition", "Margin", "Placing"]:
        if col not in out.columns:
            out[col] = np.nan

    if "Half Time" not in out.columns:
        out["Half Time"] = np.nan

    # Normalise BellPosition
    out["BellPosition"] = out["BellPosition"].astype(str).str.strip().str.upper()

    # Half Distance: if blank/NaN, fill from BellPosition map
    hd = pd.to_numeric(out["Half Distance"], errors="coerce")
    hd_missing = hd.isna()

    if hd_missing.any():
        mapped = out.loc[hd_missing, "BellPosition"].map(_HALF_DIST_MAPPING)

        # Debugging: Print the first few mapped values
        print(f"Mapped values for Half Distance: {mapped.head()}")

        # Ensure 'mapped' is a valid string or NaN (convert numeric to strings or NaN)
        mapped = mapped.apply(lambda x: str(x) if pd.notna(x) else np.nan)  # Convert non-NaN values to strings, leave NaN as is

        # Assign cleaned mapped values to "Half Distance"
        out.loc[hd_missing, "Half Distance"] = mapped

    out["Half Distance"] = pd.to_numeric(out["Half Distance"], errors="coerce")


    # Numeric inputs
    lt = pd.to_numeric(out["LeadTime"], errors="coerce")
    q1 = pd.to_numeric(out["1st Quarter"], errors="coerce")
    q2 = pd.to_numeric(out["2nd Quarter"], errors="coerce")
    dist = pd.to_numeric(out["Distance"], errors="coerce")
    hd2 = pd.to_numeric(out["Half Distance"], errors="coerce")

    # Denominator: metres travelled from start to the horse's 800m point
    denom = dist - hd2 - 800

    # Non-performance / junk guards (consistent with your other invalid_perf logic)
    margin_num = pd.to_numeric(out["Margin"], errors="coerce")
    placing_numeric = out["Placing"].apply(_placing_is_numeric)

    invalid = (
        (out["BellPosition"] == "TO") |
        (margin_num > 99) |
        (dist.notna() & (dist < 1609)) |
        (~placing_numeric)
    )

    # Only compute where all inputs exist AND denom > 0 AND not invalid
    ok = (~invalid) & lt.notna() & q1.notna() & q2.notna() & dist.notna() & hd2.notna() & (denom > 0)

    # Mile rate to the 800m point (seconds per 1609m), rounded to nearest whole second
    half_time = ((lt + q1 + q2) / denom) * 1609
    half_time_rounded = np.round(half_time)

    out.loc[ok, "Half Time"] = half_time_rounded.loc[ok]
    out.loc[~ok, "Half Time"] = np.nan  # force blanks when not computable

    return out


def _parse_sp_to_float(sp: str):
    """
    Robust SP parser:
    accepts '3.9', '$   2.70fav', '2.70 fav', '$2.70', etc.
    returns float or np.nan.
    """
    s = str(sp or "").strip().lower()
    if s in ("", "nan", "none", "null"):
        return np.nan
    s = s.replace("$", "")
    s = s.replace("fav", "")
    s = re.sub(r"\s+", "", s)
    # keep only digits + dot
    s = re.sub(r"[^0-9.]", "", s)
    try:
        return float(s) if s else np.nan
    except Exception:
        return np.nan


def _ensure_spend_pl(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures Spend and P&L exist and are rebuilt from SP + Placing.

    Spend = 100 / SP
    P&L   = (100 - Spend) if Placing == 1 else -Spend
    """
    out = df.copy()

    if "SP" not in out.columns:
        out["SP"] = ""
    if "Placing" not in out.columns:
        out["Placing"] = ""
    if "Spend" not in out.columns:
        out["Spend"] = np.nan
    if "P&L" not in out.columns:
        out["P&L"] = np.nan

    sp_num = out["SP"].apply(_parse_sp_to_float)
    spend = 100 / sp_num
    spend = spend.replace([np.inf, -np.inf], np.nan)

    # Placing==1 (string-safe)
    placing_is_1 = out["Placing"].astype(str).str.strip().eq("1")

    pl = np.where(placing_is_1, 100 - spend, -spend)

    # Round to 2dp to match your existing style
    out["Spend"] = np.round(spend, 2)
    out["P&L"] = np.round(pl, 2)

    # If SP missing/invalid -> blank Spend/P&L
    bad = sp_num.isna()
    out.loc[bad, ["Spend", "P&L"]] = np.nan

    return out


def _ensure_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures State exists.
    Uses venue code from:
      - 'VenueCode' column if present, else
      - first 2 chars of RaceAnchor (e.g., 'AP310126' -> 'AP')

    Then maps venue code -> Australian state/territory.
    """
    out = df.copy()

    if "State" not in out.columns:
        out["State"] = ""

    # Prefer explicit VenueCode if you have it; else derive from RaceAnchor
    if "VenueCode" in out.columns:
        vc = out["VenueCode"].astype(str).str.strip().str.upper()
    else:
        if "RaceAnchor" not in out.columns:
            out["RaceAnchor"] = ""
        vc = out["RaceAnchor"].astype(str).str.strip().str.upper().str[:2]

    code_to_state = {
        # ACT
        "CB": "NSW",

        # QLD
        "AP": "QLD", "DJ": "QLD", "EQ": "QLD", "IJ": "QLD", "RE": "QLD", "UG": "QLD",

        # NSW
        "AE": "NSW", "AL": "NSW", "BB": "NSW", "BH": "NSW", "BK": "NSW", "BR": "NSW",
        "CA": "NSW", "CL": "NSW", "DU": "NSW", "EU": "NSW", "EY": "NSW", "FB": "NSW",
        "GR": "NSW", "JU": "NSW", "LE": "NSW", "LH": "NSW", "LM": "NSW", "MD": "NSW",
        "NA": "NSW", "NR": "NSW", "PC": "NSW", "PE": "NSW", "PK": "NSW", "TA": "NSW",
        "TM": "NSW", "WE": "NSW", "YU": "NSW",

        # VIC
        "AR": "VIC", "BA": "VIC", "BN": "VIC", "BT": "VIC", "CH": "VIC", "CO": "VIC",
        "CR": "VIC", "EC": "VIC", "GE": "VIC", "GU": "VIC", "HM": "VIC", "HS": "VIC",
        "IR": "VIC", "JY": "VIC", "KI": "VIC", "MH": "VIC", "ML": "VIC", "OU": "VIC",
        "QP": "VIC", "QY": "VIC", "QZ": "VIC", "SA": "VIC", "SP": "VIC", "SW": "VIC",
        "TE": "VIC", "VC": "VIC", "VL": "VIC", "VV": "VIC", "WD": "VIC", "WN": "VIC",
        "WR": "VIC", "YG": "VIC", "MX": "VIC",

        # SA
        "AW": "SA", "DZ": "SA", "GD": "SA", "KP": "SA", "MG": "SA", "PP": "SA",
        "SQ": "SA", "ST": "SA", "UI": "SA", "VH": "SA",

        # WA
        "AY": "WA", "BG": "WA", "BU": "WA", "BY": "WA", "CX": "WA", "GP": "WA",
        "NG": "WA", "NM": "WA", "PA": "WA", "WA": "WA", "WS": "WA", "ZO": "WA",

        # TAS
        "BE": "TAS", "CK": "TAS", "DV": "TAS", "EH": "TAS", "LN": "TAS", "SC": "TAS",
    }

    out["State"] = vc.map(code_to_state).fillna(out["State"]).fillna("").astype(str).str.strip()

    return out



def _ensure_sp_old(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures SP_old exists and is populated from SP.
    This is a safe compatibility column so nothing breaks if something still expects SP_old.
    """
    out = df.copy()

    if "SP" not in out.columns:
        out["SP"] = ""

    if "SP_old" not in out.columns:
        out["SP_old"] = ""

    sp = out["SP"].astype(str).str.strip()
    # Only fill SP_old where it's blank/missing
    sp_old = out["SP_old"].astype(str).str.strip()
    missing = sp_old.eq("") | sp_old.str.lower().isin(["nan", "none", "null"])
    out.loc[missing, "SP_old"] = sp.loc[missing]

    return out


def _ensure_vdwh(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures VDWH exists and is backfilled.
    VDWH = Venue + "_" + Distance + "_" + Width + "_" + Half Time

    Uses the literal column name: "Half Time".
    If any component is missing/blank, VDWH is left blank.
    """
    out = df.copy()

    # Ensure required columns exist (so script never crashes)
    for col in ["Venue", "Distance", "Width", "Half Time"]:
        if col not in out.columns:
            out[col] = ""

    if "VDWH" not in out.columns:
        out["VDWH"] = ""

    venue = out["Venue"].astype(str).str.strip()
    width = out["Width"].astype(str).str.strip().str.upper()

    # Distance -> clean int string (avoid "1690.0")
    dist_num = pd.to_numeric(out["Distance"], errors="coerce")
    dist = dist_num.apply(lambda x: "" if pd.isna(x) else str(int(x))).astype(str)

    # Half Time -> numeric -> clean string (avoid "nan", keep consistent)
    ht_num = pd.to_numeric(out["Half Time"], errors="coerce")
    ht = ht_num.apply(lambda x: "" if pd.isna(x) else f"{float(x):.2f}".rstrip("0").rstrip(".")).astype(str)

    ok = venue.ne("") & dist.ne("") & width.ne("") & ht.ne("")
    out.loc[ok, "VDWH"] = venue[ok] + "_" + dist[ok] + "_" + width[ok] + "_" + ht[ok]
    out.loc[~ok, "VDWH"] = ""

    return out



def _ensure_ind_half_and_horse_delta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures:
      - Half Distance exists (derive from BellPosition if missing/blank)
      - Width exists (derive from BellPosition if missing/blank)
      - MarginClean exists (derive from Margin if missing)
      - Ind Half exists (compute from Q3+Q4 / (800 - MarginClean + HalfDistance) * 800)
      - HorseDelta exists (compute as Ind Half - Race Last Half)

    This is the key fix so Step 3 can build ContextAdjSeconds.
    """
    out = df.copy()

    # Ensure base columns exist
    for col in ["BellPosition", "Half Distance", "Width", "Margin", "MarginClean", "3rd Quarter", "4th Quarter", "Race Last Half", "Ind Half", "HorseDelta"]:
        if col not in out.columns:
            out[col] = np.nan

    # Normalise BellPosition
    out["BellPosition"] = out["BellPosition"].astype(str).str.strip().str.upper()

    # Half Distance: if blank/NaN, fill from BellPosition map
    hd = pd.to_numeric(out["Half Distance"], errors="coerce")
    hd_missing = hd.isna()

    # If there are missing values, map from BellPosition
    if hd_missing.any():
        mapped = out.loc[hd_missing, "BellPosition"].map(_HALF_DIST_MAPPING)

        # Handle invalid mappings (e.g., if the value is not found in the map)
        mapped = mapped.fillna(np.nan)  # Fill missing mappings with NaN (or a default value)
    
        out.loc[hd_missing, "Half Distance"] = mapped

    # Ensure that the "Half Distance" column is numeric, coercing any remaining non-numeric values to NaN
    out["Half Distance"] = pd.to_numeric(out["Half Distance"], errors="coerce")

    # Width: if blank, map from BellPosition
    width_s = out["Width"].astype(str).str.strip().str.upper()
    width_missing = (width_s.eq("")) | (width_s.eq("NAN")) | (width_s.isna())

    if width_missing.any():
        mapped_w = out.loc[width_missing, "BellPosition"].map(_WIDTH_MAPPING)
    
        # Handle invalid mappings for Width (fill with NaN or a default value)
        mapped_w = mapped_w.fillna("UNKNOWN")  # Use a default value like "UNKNOWN"
    
        out.loc[width_missing, "Width"] = mapped_w

    # Ensure that the "Width" column is correctly formatted as a string
    out["Width"] = out["Width"].astype(str).str.strip().str.upper()


    # MarginClean
    if "MarginClean" not in out.columns:
        out["MarginClean"] = np.nan
    mc = pd.to_numeric(out["MarginClean"], errors="coerce")
    mc_missing = mc.isna()
    if mc_missing.any():
        out.loc[mc_missing, "MarginClean"] = _compute_margin_clean(out.loc[mc_missing, "Margin"])
    out["MarginClean"] = pd.to_numeric(out["MarginClean"], errors="coerce").fillna(0.0)

    # Numeric quarters and race last half
    out["3rd Quarter"] = pd.to_numeric(out["3rd Quarter"], errors="coerce")
    out["4th Quarter"] = pd.to_numeric(out["4th Quarter"], errors="coerce")
    out["Race Last Half"] = pd.to_numeric(out["Race Last Half"], errors="coerce")

    # ----------------------------
    # Invalidate non-performances (TO / huge margins)
    # NOTE: apply to *out* (the function's working copy), not df.
    # ----------------------------
    out["BellPosition"] = out["BellPosition"].astype(str).str.upper().str.strip()
    out["Margin"] = pd.to_numeric(out["Margin"], errors="coerce")


    # Ensure Distance numeric (for performance eligibility only)
    if "Distance" not in out.columns:
        out["Distance"] = np.nan
    out["Distance"] = pd.to_numeric(out["Distance"], errors="coerce")

    # Ensure Placing exists (for performance eligibility only)
    if "Placing" not in out.columns:
        out["Placing"] = ""

    placing_numeric = out["Placing"].apply(_placing_is_numeric)

    invalid_perf = (
        (out["BellPosition"] == "TO") |
        (out["Margin"] > 99) |
        (out["Distance"].notna() & (out["Distance"] < 1609)) |
        (~placing_numeric)
    )


    # Only blank what we compute here (don't touch ContextAdjSeconds / RatingIndHalf here)
    for col in ["Ind Half", "HorseDelta"]:
        if col in out.columns:
            out.loc[invalid_perf, col] = np.nan




    # Compute Ind Half (always recompute when we have Q3/Q4; manual edits must flow through)
    denom = 800 - out["MarginClean"].fillna(0.0) + out["Half Distance"].fillna(0.0)
    denom = denom.where(denom > 0)

    q3 = out["3rd Quarter"]
    q4 = out["4th Quarter"]

    ind_half_new = (((q3) + (q4)) / denom) * 800

    # Only write Ind Half where we have usable inputs and it's not an invalid performance
    has_quarters = q3.notna() & q4.notna()
    out.loc[has_quarters & (~invalid_perf), "Ind Half"] = ind_half_new.loc[has_quarters & (~invalid_perf)]

    out["Ind Half"] = pd.to_numeric(out["Ind Half"], errors="coerce")

    # ------------------------------------------------------------
    # NEW: Ignore for rating/analysis if Ind Half < 50
    # (blank Ind Half + HorseDelta so it can't feed Steps 3–6)
    # ------------------------------------------------------------
    bad_ind_half = out["Ind Half"].notna() & (out["Ind Half"] < 50)
    if bad_ind_half.any():
        out.loc[bad_ind_half, ["Ind Half", "HorseDelta"]] = np.nan

    # Compute HorseDelta = Ind Half - Race Last Half (always recompute where possible)
    rlh = pd.to_numeric(out["Race Last Half"], errors="coerce")
    mask_hd = out["Ind Half"].notna() & rlh.notna() & (~invalid_perf)
    out.loc[mask_hd, "HorseDelta"] = out.loc[mask_hd, "Ind Half"] - rlh.loc[mask_hd]

    out["HorseDelta"] = pd.to_numeric(out["HorseDelta"], errors="coerce")


    return out


def _compute_eligible_6in12(df: pd.DataFrame, horse_col: str = "Horse", date_col: str = "DateEffective") -> pd.Series:
    """
    Eligible_6in12 = True if the horse has >= 6 starts in the last 365 days
    up to and including the current row's DateEffective.

    O(n) per horse via two-pointer window, safe for ~650k rows.
    """
    if horse_col not in df.columns or date_col not in df.columns:
        return pd.Series(False, index=df.index)

    tmp = df[[horse_col, date_col]].copy()

    tmp["_horse_key"] = (
        tmp[horse_col].astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )

    dt = pd.to_datetime(tmp[date_col], errors="coerce")
    tmp["_day"] = (dt.astype("int64") // 86_400_000_000_000).astype("Int64")
    tmp["_orig_idx"] = tmp.index

    valid = tmp["_day"].notna() & tmp["_horse_key"].ne("")
    tmp_valid = tmp.loc[valid, ["_horse_key", "_day", "_orig_idx"]].copy()
    tmp_valid.sort_values(["_horse_key", "_day", "_orig_idx"], inplace=True, kind="mergesort")

    eligible_out = pd.Series(False, index=df.index)

    keys = tmp_valid["_horse_key"].to_numpy()
    days = tmp_valid["_day"].to_numpy(dtype=np.int64)
    orig = tmp_valid["_orig_idx"].to_numpy()

    n = len(tmp_valid)
    start = 0
    while start < n:
        end = start
        k = keys[start]
        while end < n and keys[end] == k:
            end += 1

        left = start
        for i in range(start, end):
            while days[i] - days[left] > 365:
                left += 1
            count = i - left + 1
            if count >= 6:
                eligible_out.at[orig[i]] = True

        start = end

    return eligible_out


def _rebuild_steps_3_to_6(master_csv: str, shrink_k: int = 100, ignore_widths=None):
    """
    Rebuilds Step 3–6 columns on the ENTIRE merged_file.csv safely.
    Writes back to the same CSV.
    """
    if ignore_widths is None:
        ignore_widths = {"TO"}

    if not os.path.exists(master_csv):
        print(f"❌ Master file not found: {master_csv}")
        return

    # ------------------------------------------------------------
    # Read master FIRST (df must exist before any df.columns checks)
    # ------------------------------------------------------------
    try:
        df = pd.read_csv(master_csv, low_memory=False, dtype=str)
    except Exception as e:
        print(f"❌ Failed to read master CSV: {master_csv} — {e}")
        return

    print(f"🔁 Rebuilding Steps 3–6 on master: {master_csv} (rows={len(df):,})")

    # ------------------------------------------------------------
    # BACKFILL BellPosition from StewardsComments (REBUILD mode)
    # ------------------------------------------------------------
    bell_position_mapping = {
        ", leader at bell": "LEAD",
        "leader at bell": "LEAD",
        ", leader at the bell": "LEAD",
        "leader at the bell": "LEAD",
        "behind leader at bell": "B/LEAD",
        "behind leader at the bell": "B/LEAD",
        "outside leader at bell": "DEATH",
        "outside leader at the bell": "DEATH",
        "death seat at bell": "DEATH",
        "death seat at the bell": "DEATH",

        "bell lap, leader": "LEAD",
        "bell lap, behind leader": "B/LEAD",
        "bell lap, outside leader": "DEATH",

        "1 out 1 back at bell": "1X1",
        "1 out 2 back at bell": "1X2",
        "1 out 3 back at bell": "1X3",
        "1 out 4 back at bell": "1X4",
        "1 out 5 back at bell": "1X5",
        "1 out 6 back at bell": "1X6",

        "800m, outside leader": "DEATH",
        "800m, behind leader": "B/LEAD",
        "800m, 1 out 1 back": "1X1",
        "800m, 1 out 2 back": "1X2",
        "800m, 1 out 3 back": "1X3",
        "800m, 1 out 4 back": "1X4",
        "800m, 1 out 5 back": "1X5",
        "800m, 1 out 6 back": "1X6",

        "3 back on pegs at bell": "3PEGS",
        "4 back on pegs at bell": "4PEGS",
        "5 back on pegs at bell": "5PEGS",
        "6 back on pegs at bell": "6PEGS",
        "7 back on pegs at bell": "6PEGS",
        "8 back on pegs at bell": "6PEGS",

        "800m, 3 back on pegs": "3PEGS",
        "800m, 4 back on pegs": "4PEGS",
        "800m, 5 back on pegs": "5PEGS",
        "800m, 6 back on pegs": "6PEGS",

        "three wide without cover": "3WIDE",
        "3 wide without cover": "3WIDE",
        "3 wide throughout": "3WIDE",
        "3 wide and 1 back": "3X1",
        "3 wide and 2 back": "3X2",
        "3 out 1 back": "3X1",
        "3 out 2 back": "3X2",

        "tailed off": "TO",
        "tailed out": "TO",
        "disqualified": "TO",
        "failed to finish": "TO",
        "lost driver": "TO",
        "retired": "TO",
        "pulled up": "TO",
    }

    def extract_bell_position(comment: str) -> str:
        import re

        c = str(comment or "").strip().lower()
        if not c or c in ("nan", "none", "null"):
            return "0"

        # Normalise: remove punctuation, compress whitespace
        c_norm = re.sub(r"[^a-z0-9\s]", " ", c)
        c_norm = re.sub(r"\s+", " ", c_norm).strip()

        # --- 1) Strong TO detection first ---
        if any(x in c_norm for x in [
            "tailed off", "tailed out", "disqualified", "failed to finish",
            "lost driver", "pulled up", "retired"
        ]):
            return "TO"

        bell_ref = ("at bell" in c_norm) or ("at the bell" in c_norm) or ("bell lap" in c_norm)

        # --- 2) DEATH / outside leader BEFORE generic leader ---
        if bell_ref and ("outside leader" in c_norm or "death seat" in c_norm):
            return "DEATH"

        # --- 3) Behind leader BEFORE generic leader ---
        if bell_ref and re.search(r"\bbehind\s+leader\b", c_norm):
            return "B/LEAD"

        if bell_ref and (re.search(r"\boutside\s+leader\b", c_norm) or re.search(r"\bdeath\s+seat\b", c_norm)):
            return "DEATH"


        # --- 4) True leader (only after death/behind handled) ---
        if c_norm.startswith("leader at bell") or c_norm.startswith("leader at the bell"):
            return "LEAD"

        # Only treat as LEAD if it's explicitly leader at bell / bell lap leader
        if bell_ref and ("leader at bell" in c_norm or "leader at the bell" in c_norm or "bell lap leader" in c_norm):
            return "LEAD"


        # --- 5) Pegs (handles fence / inside language) ---
        if ("3 back" in c_norm or "3rd fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "3PEGS"
        if ("4 back" in c_norm or "4th fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "4PEGS"
        if ("5 back" in c_norm or "5th fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "5PEGS"
        if ("6 back" in c_norm or "6th fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "6PEGS"
        if ("7 back" in c_norm or "7th fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "6PEGS"
        if ("8 back" in c_norm or "8th fence" in c_norm) and ("pegs" in c_norm or "fence" in c_norm or "inside" in c_norm):
            return "6PEGS"

        # --- 6) 1 out / 1 back ---
        if ("1 out 1 back" in c_norm) or ("one out one back" in c_norm):
            return "1X1"
        if ("1 out 2 back" in c_norm) or ("one out two back" in c_norm):
            return "1X2"
        if ("1 out 3 back" in c_norm) or ("one out three back" in c_norm):
            return "1X3"
        if ("1 out 4 back" in c_norm) or ("one out four back" in c_norm):
            return "1X4"
        if ("1 out 5 back" in c_norm) or ("one out five back" in c_norm):
            return "1X5"
        if ("1 out 6 back" in c_norm) or ("one out six back" in c_norm):
            return "1X6"

        # --- 7) 3-wide variations ---
        if ("three wide" in c_norm or "3 wide" in c_norm) and ("without cover" in c_norm or "throughout" in c_norm):
            return "3WIDE"
        if ("three wide" in c_norm or "3 wide" in c_norm) and ("1 back" in c_norm):
            return "3X1"
        if ("three wide" in c_norm or "3 wide" in c_norm) and ("2 back" in c_norm):
            return "3X2"
        if ("3 out" in c_norm) and ("1 back" in c_norm):
            return "3X1"
        if ("3 out" in c_norm) and ("2 back" in c_norm):
            return "3X2"

        # --- 8) Fallback: phrase mapping table ---
        for phrase, label in bell_position_mapping.items():
            p = str(phrase).lower().strip()
            p_norm = re.sub(r"[^a-z0-9\s]", " ", p)
            p_norm = re.sub(r"\s+", " ", p_norm).strip()
            if p_norm and p_norm in c_norm:
                return label

        return "0"


    def extract_bell_position_last(comment: str) -> str:
        c = str(comment or "").lower()

        if not c or c.strip() in ("nan", "none", "null"):
            return "0"

        # terminal/non-performance first
        if any(x in c for x in [
            "tailed off", "tailed out", "disqualified", "failed to finish",
            "lost driver", "pulled up", "retired", "took no competitive part"
        ]):
            return "TO"

        patterns = [
            (r"behind leader at (?:the )?bell", "B/LEAD"),
            (r"(?:outside leader|death seat) at (?:the )?bell", "DEATH"),
            (r"leader at (?:the )?bell", "LEAD"),

            # bell lap variants
            (r"bell lap,\s*behind leader", "B/LEAD"),
            (r"bell lap,\s*(?:outside leader|death seat)", "DEATH"),
            (r"bell lap,\s*leader", "LEAD"),
        ]

        hits = []
        for pat, lab in patterns:
            for m in re.finditer(pat, c):
                hits.append((m.start(), lab))

        if not hits:
            return "0"

        # choose the LAST bell-phrase in the string
        hits.sort(key=lambda x: x[0])
        return hits[-1][1]





    # ------------------------------------------------------------
    # BellPosition from StewardsComments:
    #   A) Fix missing/blank/0
    #   B) Fix obvious conflicts (LEAD but comment says behind/outside/death AT BELL)
    #   C) Override when explicit bell phrases appear (last-phrase wins)
    #      (only uses explicit "at bell"/"bell lap" phrases; doesn't rewrite generic "outside leader" etc)
    # ------------------------------------------------------------
    if "StewardsComments" in df.columns:
        if "BellPosition" not in df.columns:
            df["BellPosition"] = ""

        # Normalise existing BP
        bp = (
            df["BellPosition"]
            .astype(str)
            .str.replace("\u00A0", " ", regex=False)
            .str.strip()
            .str.upper()
            .replace({"NONE": "", "NAN": "", "NA": "", "NULL": ""})
        )

        # Normalise comments once (for matching)
        sc_raw = df["StewardsComments"].astype(str).fillna("")
        sc_norm = _norm_sc(sc_raw)

        # --- patterns (NON-capturing groups to avoid pandas warning) ---
        pat_explicit_bell = (
            r"(?:"
            r"behind leader at (?:the )?bell|"
            r"(?:outside leader|death seat) at (?:the )?bell|"
            r"leader at (?:the )?bell|"
            r"bell lap,\s*(?:leader|behind leader|outside leader|death seat)"
            r")"
        )

        # A) missing/blank/0
        missing_bp = bp.eq("") | bp.eq("0")

        # B) conflict: BP says LEAD but comment explicitly says behind/outside/death AT BELL
        pat_conflict_lead = (
            r"(?:"
            r"behind leader at (?:the )?bell|"
            r"(?:outside leader|death seat) at (?:the )?bell|"
            r"bell lap,\s*(?:behind leader|outside leader|death seat)"
            r")"
        )
        conflict_lead = bp.eq("LEAD") & sc_norm.str.contains(pat_conflict_lead, na=False, regex=True)

        needs_bp = missing_bp | conflict_lead

        # ---- extractors (work from already-normalised text) ----
        def extract_bell_position_from_norm(c_norm: str) -> str:
            """
            Conservative extractor for general backfill.
            Uses bell-reference guards; avoids misclassifying "outside leader" as LEAD.
            """
            c = str(c_norm or "").strip()
            if not c:
                return "0"

            # TO first
            if any(x in c for x in [
                "tailed off", "tailed out", "disqualified", "failed to finish",
                "lost driver", "pulled up", "retired", "took no competitive part"
            ]):
                return "TO"

            bell_ref = ("at bell" in c) or ("at the bell" in c) or ("bell lap" in c)

            # DEATH/behind before lead
            if bell_ref and ("outside leader" in c or "death seat" in c):
                return "DEATH"
            if bell_ref and ("behind leader" in c):
                return "B/LEAD"

            # LEAD only when explicit
            if bell_ref and ("leader at bell" in c or "leader at the bell" in c or "bell lap leader" in c or "bell lap, leader" in c):
                return "LEAD"

            # 1x1 etc
            if "1 out 1 back" in c or "one out one back" in c:
                return "1X1"
            if "1 out 2 back" in c or "one out two back" in c:
                return "1X2"
            if "1 out 3 back" in c or "one out three back" in c:
                return "1X3"
            if "1 out 4 back" in c or "one out four back" in c:
                return "1X4"
            if "1 out 5 back" in c or "one out five back" in c:
                return "1X5"
            if "1 out 6 back" in c or "one out six back" in c:
                return "1X6"

            # pegs
            if ("3 back" in c or "3rd fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "3PEGS"
            if ("4 back" in c or "4th fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "4PEGS"
            if ("5 back" in c or "5th fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "5PEGS"
            if ("6 back" in c or "6th fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "6PEGS"
            if ("7 back" in c or "7th fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "6PEGS"
            if ("8 back" in c or "8th fence" in c) and ("pegs" in c or "fence" in c or "inside" in c):
                return "6PEGS"

            # 3-wide
            if ("three wide" in c or "3 wide" in c) and ("without cover" in c or "throughout" in c):
                return "3WIDE"
            if ("three wide" in c or "3 wide" in c) and ("1 back" in c):
                return "3X1"
            if ("three wide" in c or "3 wide" in c) and ("2 back" in c):
                return "3X2"
            if ("3 out" in c) and ("1 back" in c):
                return "3X1"
            if ("3 out" in c) and ("2 back" in c):
                return "3X2"

            return "0"

        def extract_bell_position_last_from_norm(c_norm: str) -> str:
            """
            For explicit bell phrases only. If multiple appear, last one wins.
            IMPORTANT: avoid matching 'leader at bell' inside 'behind leader at bell' / 'outside leader at bell'.
            """
            c = str(c_norm or "").strip()
            if not c:
                return "0"

            # TO first
            if any(x in c for x in [
                "tailed off", "tailed out", "disqualified", "failed to finish",
                "lost driver", "pulled up", "retired", "took no competitive part"
            ]):
                return "TO"

            patterns = [
                # Most specific first
                (r"\bbehind\s+leader\s+at\s+(?:the\s+)?bell\b", "B/LEAD"),
                (r"\b(?:outside\s+leader|death\s+seat)\s+at\s+(?:the\s+)?bell\b", "DEATH"),

                # LEAD must NOT be preceded by 'behind ' or 'outside '
                (r"(?<!behind\s)(?<!outside\s)\bleader\s+at\s+(?:the\s+)?bell\b", "LEAD"),

                # bell lap variants (NOTE: your sc_norm removes commas)
                (r"\bbell\s+lap\s+behind\s+leader\b", "B/LEAD"),
                (r"\bbell\s+lap\s+(?:outside\s+leader|death\s+seat)\b", "DEATH"),
                (r"\bbell\s+lap\s+leader\b", "LEAD"),
            ]

            hits = []
            for pat, lab in patterns:
                for m in re.finditer(pat, c):
                    hits.append((m.start(), lab))

            if not hits:
                return "0"

            hits.sort(key=lambda x: x[0])
            return hits[-1][1]


        # --- A/B: fix missing + conflicts ---
        if needs_bp.any():
            df.loc[needs_bp, "BellPosition"] = (
                sc_norm.loc[needs_bp]
                .apply(extract_bell_position_from_norm)
                .astype(str)
                .str.strip()
                .str.upper()
            )

            bp2 = (
                df["BellPosition"].astype(str)
                .str.strip().str.upper()
                .replace({"NONE": "", "NAN": "", "NA": "", "NULL": ""})
            )
            still_missing = int((bp2.eq("") | bp2.eq("0")).sum())

            print(
                "✅ Backfilled/Corrected BellPosition from StewardsComments: "
                f"attempted={int(needs_bp.sum()):,} (missing={int(missing_bp.sum()):,}, conflict_lead={int(conflict_lead.sum()):,}), "
                f"still_missing={still_missing:,}"
            )
        else:
            print("ℹ️ BellPosition backfill/correction skipped — nothing to fix.")

        # --- C: override only when explicit bell phrases exist ---
        has_bell_phrase = sc_norm.str.contains(pat_explicit_bell, na=False, regex=True)
        if has_bell_phrase.any():
            df.loc[has_bell_phrase, "BellPosition"] = (
                sc_norm.loc[has_bell_phrase]
                .apply(extract_bell_position_last_from_norm)
                .astype(str)
                .str.strip()
                .str.upper()
            )
            print(f"✅ BellPosition overridden from explicit bell phrases (last-phrase wins): {int(has_bell_phrase.sum()):,}")

    else:
        print("⚠️ StewardsComments column missing — cannot backfill BellPosition.")


        # sanity check: after override, how many LEAD rows still contain behind/outside/death at bell?
        _check_bad = bp2.eq("LEAD") & sc_norm.str.contains(
            r"(?:\bbehind\s+leader\s+at\s+(?:the\s+)?bell\b|\b(?:outside\s+leader|death\s+seat)\s+at\s+(?:the\s+)?bell\b)",
            na=False,
            regex=True
        )
        print(f"🧪 After override sanity check: LEAD rows with behind/outside/death AT BELL = {int(_check_bad.sum()):,}")





    # Normalise key columns
    for c in ["Venue", "Width", "Start", "Gait", "RunnerAnchor", "Horse", "Distance"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    if "Width" in df.columns:
        df["Width"] = df["Width"].astype(str).str.strip().str.upper()

        # ✅ NEW: ensure VDWH exists/backfilled during rebuilds too
        df = _ensure_vdwh(df)


    # DateEffective always rebuilt from Date
    df["DateEffective"] = _ensure_datetime_from_date(df, "Date")
    df = _ensure_spend_pl(df)
    df = _ensure_state(df)
    df = _ensure_sp_old(df)
    df = _ensure_half_time(df)
    df = _ensure_horse_runs(df)

    # Eligible_6in12: recompute if missing or all-false
    if "Eligible_6in12" in df.columns:
        elig_existing = (
            df["Eligible_6in12"]
              .astype(str)
              .str.strip()
              .str.upper()
              .isin(["TRUE", "1", "YES", "Y", "T"])
        )
    else:
        elig_existing = pd.Series(False, index=df.index)

    if int(elig_existing.sum()) == 0:
        print("   Recomputing Eligible_6in12 from Horse + DateEffective (>=6 starts in last 365 days)...")
        df["Eligible_6in12"] = _compute_eligible_6in12(df, horse_col="Horse", date_col="DateEffective")
        print(f"   Eligible_6in12 recomputed: True={int(df['Eligible_6in12'].sum()):,} / {len(df):,}")
    else:
        df["Eligible_6in12"] = elig_existing

    # Distance numeric + buckets
    if "Distance" in df.columns:
        df["Distance"] = pd.to_numeric(df["Distance"], errors="coerce")
    else:
        df["Distance"] = np.nan
    df["DistanceBucket"] = df["Distance"].apply(_distance_bucket)

    # Ensure needed key fields exist
    for needed in ["Venue", "Start", "Gait", "Width"]:
        if needed not in df.columns:
            df[needed] = ""

    df["ContextKey"] = (
        df["Venue"].astype(str) + "|" +
        df["DistanceBucket"].astype(str) + "|" +
        df["Start"].astype(str) + "|" +
        df["Gait"].astype(str) + "|" +
        df["Width"].astype(str)
    )

    # --- CRITICAL FIX: Ensure Ind Half + HorseDelta exist before Step 3 ---
    # We need Race Last Half + Ind Half + HorseDelta for Step 3 inputs
    # Ensure quarters exist and Race Last Half exists (if missing, will become NaN and IndHalf may still compute if Q3/Q4 exist)
    for col in ["3rd Quarter", "4th Quarter", "Race Last Half"]:
        if col not in df.columns:
            df[col] = np.nan

    # Always recompute Race Last Half from Q3+Q4 (so manual timing edits flow through)
    q3 = pd.to_numeric(df["3rd Quarter"], errors="coerce")
    q4 = pd.to_numeric(df["4th Quarter"], errors="coerce")
    df["Race Last Half"] = (q3 + q4)


    df = _ensure_ind_half_and_horse_delta(df)

    # STEP 3: ContextAdjSeconds + RatingIndHalf
    df["HorseDelta"] = pd.to_numeric(df.get("HorseDelta", np.nan), errors="coerce")
    df["Ind Half"] = pd.to_numeric(df.get("Ind Half", np.nan), errors="coerce")

    

    # Diagnostics
    _c_total = len(df)
    _c_elig = int(df["Eligible_6in12"].fillna(False).sum()) if _c_total else 0
    _c_date = int(df["DateEffective"].notna().sum())
    _c_width = int((~df["Width"].isin(ignore_widths)).sum())
    _c_hdelta = int(df["HorseDelta"].notna().sum())

    print(f"   Step3 inputs: total={_c_total:,} elig_true={_c_elig:,} date_ok={_c_date:,} width_ok={_c_width:,} HorseDelta_notna={_c_hdelta:,}")





    # Ensure types for eligibility filters (CSV was loaded dtype=str)
    df["BellPosition"] = df.get("BellPosition", "").astype(str).str.upper().str.strip()
    df["Margin"] = pd.to_numeric(df.get("Margin", np.nan), errors="coerce")
    df["Placing"] = df.get("Placing", "").astype(str).str.strip()
    placing_numeric = df["Placing"].apply(_placing_is_numeric)


    ind_half_num = pd.to_numeric(df.get("Ind Half", np.nan), errors="coerce")

    eligible = df[
        (df["Eligible_6in12"] == True) &
        (df["DateEffective"].notna()) &
        (~df["Width"].isin(ignore_widths)) &
        (df["BellPosition"] != "TO") &
        (df["Margin"].isna() | (df["Margin"] <= 99)) &
        (df["Distance"].isna() | (df["Distance"] >= 1609)) &
        (placing_numeric) &
        (ind_half_num.isna() | (ind_half_num >= 50))
    ].copy()





    agg = (
        eligible
        .dropna(subset=["HorseDelta"])
        .groupby("ContextKey", as_index=False)
        .agg(
            ContextN=("HorseDelta", "count"),
            ContextMedianDelta=("HorseDelta", "median"),
        )
    )

    if agg.empty:
        # Preserve existing Step 3 outputs if we can't rebuild
        for col in ["ContextN", "ContextMedianDelta", "ShrinkFactor", "ContextAdjSeconds"]:
            if col not in df.columns:
                df[col] = np.nan

        # RatingIndHalf from existing ContextAdjSeconds (treat missing ContextAdjSeconds as 0)
        ctx = pd.to_numeric(df.get("ContextAdjSeconds", np.nan), errors="coerce")
        ind = pd.to_numeric(df.get("Ind Half", np.nan), errors="coerce")
        df["RatingIndHalf"] = ind - ctx.fillna(0.0)

        df.loc[df["Width"].isin(ignore_widths), ["ContextAdjSeconds", "RatingIndHalf"]] = np.nan
        print("⚠️ Step 3: agg empty — preserved existing context columns (recomputed RatingIndHalf using existing ContextAdjSeconds).")
    else:
        agg["ShrinkFactor"] = agg["ContextN"] / (agg["ContextN"] + float(shrink_k))
        agg["ContextAdjSeconds"] = agg["ContextMedianDelta"] * agg["ShrinkFactor"]

        merged = df.merge(
            agg[["ContextKey", "ContextN", "ContextMedianDelta", "ShrinkFactor", "ContextAdjSeconds"]],
            on="ContextKey",
            how="left",
            suffixes=("", "_new"),
            validate="m:1"
        )

        df["ContextN"] = merged["ContextN_new"]
        df["ContextMedianDelta"] = merged["ContextMedianDelta_new"]
        df["ShrinkFactor"] = merged["ShrinkFactor_new"]
        df["ContextAdjSeconds"] = merged["ContextAdjSeconds_new"]

        ctx = pd.to_numeric(df["ContextAdjSeconds"], errors="coerce")
        df["RatingIndHalf"] = pd.to_numeric(df["Ind Half"], errors="coerce") - ctx.fillna(0.0)

        df.loc[df["Width"].isin(ignore_widths), ["ContextAdjSeconds", "RatingIndHalf"]] = np.nan
        print(f"✅ Step 3: Built context adjustments for ContextKey groups={len(agg):,} (rows contributing={len(eligible.dropna(subset=['HorseDelta'])):,}).")



    # Neutralise NON-PERFORMANCE rows so they do NOT affect Step 4/5/6
    df["Placing"] = df.get("Placing", "").astype(str).str.strip()
    placing_numeric = df["Placing"].apply(_placing_is_numeric)

    ind_half_num = pd.to_numeric(df.get("Ind Half", np.nan), errors="coerce")

    invalid_perf = (
        (df.get("BellPosition", "").astype(str).str.upper().str.strip() == "TO") |
        (pd.to_numeric(df.get("Margin", np.nan), errors="coerce") > 99) |
        (
            pd.to_numeric(df.get("Distance", np.nan), errors="coerce").notna() &
            (pd.to_numeric(df.get("Distance", np.nan), errors="coerce") < 1609)
        ) |
        (~placing_numeric) |
        (ind_half_num.notna() & (ind_half_num < 50))
    )




    for col in ["Ind Half", "HorseDelta", "ContextAdjSeconds", "RatingIndHalf"]:
        if col in df.columns:
            df.loc[invalid_perf, col] = np.nan




    # ------------------------------------------------------------
    # STEP 4/5: Recent + Baseline + Expected (rebuilt)
    # ------------------------------------------------------------
    for col in ["HorseRecentRatingIndHalf_5", "HorseBaselineIndHalf",
                "ExpectedRatingIndHalf", "ExpectedRatingSource",
                "ExpectedGapSeconds", "ExpectedGapMetres", "ExpectedGapFlag"]:
        if col in df.columns:
            df.drop(columns=[col], inplace=True)

    df["_horse"] = df["Horse"].astype(str).str.strip()
    df["_dt"] = df["DateEffective"]

    df = df.sort_values(["_horse", "_dt"], kind="mergesort")

    rating = pd.to_numeric(df.get("RatingIndHalf", pd.Series([np.nan] * len(df))), errors="coerce")
    valid = rating.where((rating >= 50) & (rating <= 70))

    def _recent5_mean(s: pd.Series) -> pd.Series:
        return s.shift(1).rolling(window=5, min_periods=1).mean()

    def _recent5_count(s: pd.Series) -> pd.Series:
        return s.shift(1).rolling(window=5, min_periods=1).count()

    def _baseline_expand_mean(s: pd.Series) -> pd.Series:
        return s.shift(1).expanding(min_periods=1).mean()

    df["HorseRecentRatingIndHalf_5"] = (
        valid.groupby(df["_horse"], sort=False)
             .apply(_recent5_mean)
             .reset_index(level=0, drop=True)
    )

    _recent_n = (
        valid.groupby(df["_horse"], sort=False)
             .apply(_recent5_count)
             .reset_index(level=0, drop=True)
    )

    df["HorseBaselineIndHalf"] = (
        valid.groupby(df["_horse"], sort=False)
             .apply(_baseline_expand_mean)
             .reset_index(level=0, drop=True)
    )

    df["ExpectedRatingIndHalf"] = np.where(
        pd.notna(df["HorseRecentRatingIndHalf_5"]),
        df["HorseRecentRatingIndHalf_5"],
        df["HorseBaselineIndHalf"]
    )

    df["ExpectedRatingSource"] = np.where(
        pd.notna(df["HorseRecentRatingIndHalf_5"]),
        "RECENT" + _recent_n.fillna(0).astype(int).clip(0, 5).astype(str),
        np.where(pd.notna(df["HorseBaselineIndHalf"]), "BASELINE", "")
    )

    df.drop(columns=["_horse", "_dt"], inplace=True)
    print("✅ Step 4/5 done (Recent + Baseline + Expected rebuilt).")

    # ------------------------------------------------------------
    # STEP 6: Expected gap (seconds/metres/flag)
    # ------------------------------------------------------------
    df["ExpectedGapSeconds"] = (
        pd.to_numeric(df.get("RatingIndHalf", np.nan), errors="coerce")
        - pd.to_numeric(df.get("ExpectedRatingIndHalf", np.nan), errors="coerce")
    )

    df["ExpectedGapMetres"] = -df["ExpectedGapSeconds"] * 14

    df["ExpectedGapFlag"] = np.select(
        [
            df["ExpectedGapSeconds"].isna(),
            df["ExpectedGapSeconds"] <= -1.0,
            df["ExpectedGapSeconds"] >= 1.0,
        ],
        ["", "BETTER", "WORSE"],
        default="NEUTRAL",
    )

    print("✅ Step 6 done (Expected gaps computed).")

    # Final sort + save
    df["_SortDate"] = df["DateEffective"]
    if "RunnerAnchor" not in df.columns:
        df["RunnerAnchor"] = ""
    df = df.sort_values(["_SortDate", "RunnerAnchor"], na_position="last").drop(columns=["_SortDate"])

    df.to_csv(master_csv, index=False)
    print(f"💾 Master updated with Steps 3–6: {master_csv} (rows={len(df):,})")


# ============================================================
# REBUILD ONLY MODE (NO SCRAPING)
# ============================================================
if REBUILD_ONLY:
    if not os.path.exists(MERGED_FILE):
        raise FileNotFoundError(f"Cannot rebuild: {MERGED_FILE} not found.")

    merged_df = pd.read_csv(MERGED_FILE, low_memory=False)
    # Ensure race stats + VDSG exist first
    merged_df = _ensure_race_stats(merged_df)
    merged_df = _ensure_spend_pl(merged_df)
    merged_df = _ensure_state(merged_df)
    merged_df = _ensure_sp_old(merged_df)


    merged_df = _ensure_half_time(merged_df)
    merged_df = _ensure_vdwh(merged_df)


    # ✅ NEW: backfill VDWH on the master
    merged_df = _ensure_vdwh(merged_df)


    merged_df = _ensure_horse_runs(merged_df)



    backup_file(MERGED_FILE)
    atomic_to_csv(merged_df, MERGED_FILE)
    print("✅ Rebuilt Race stats + VenDistGaitStart on master and saved.")


    # Now rebuild Steps 3–6 (includes IndHalf + HorseDelta self-heal)
    _rebuild_steps_3_to_6(MERGED_FILE, shrink_k=SHRINK_K, ignore_widths=IGNORE_WIDTHS)

    print("✅ Done (rebuild-only).")
    sys.exit(0)


# ============================================================
# SCRAPING MODE (OPTIONAL)
# If you ever flip REBUILD_ONLY=False, this will scrape last DAYS_BACK days and append to master,
# then rebuild Steps 3–6.
# ============================================================

# --- VENUE CODE MAP ---
venue_code_map = {
    "Albion Park": "AP",

}

import time
import random
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
import time
from bs4 import BeautifulSoup

def scrape_meeting_results(venue_code, date_str):
    # URL for the event
    venue_url = f"https://www.harness.org.au/racing/fields/race-fields/?mc={venue_code}{date_str}"
    print(f"🔧 Scraping URL: {venue_url}")  # Log the URL being requested

    # Configure ChromeOptions
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode (no GUI)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Initialize the Chrome WebDriver using WebDriver Manager
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    try:
        # Open the page with Selenium
        driver.get(venue_url)

        # Add a delay to ensure the page is fully loaded
        time.sleep(random.uniform(1, 2))  # Adjust this time as needed for your page

        # Get page content
        html = driver.page_source

        # Parse the page with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Check if the h2 tag exists (venue header)
        h2_tag = soup.find("h2")
        if not h2_tag:
            print(f"⚠️ No <h2> tag found for {venue_code}{date_str}. This may indicate an unexpected page structure.")
            return []

        # Extract venue and meeting time from the h2 tag
        h2_text = h2_tag.get_text(strip=True)
        venue = h2_text.split("(")[0].strip()
        meeting_time = "Unknown"
        if "(" in h2_text and ")" in h2_text:
            meeting_time = h2_text.split("(")[1].split(")")[0]

        print(f"🔧 Found venue: {venue} - Time: {meeting_time}")

        # Parse race results (custom parsing logic here)
        results = parse_race_results(soup, venue, date_str, venue_code, meeting_time)

        # If results were found, log the number of races and runners
        if results:
            print(
                f"✅ {venue_code}{date_str} — {venue} "
                f"({meeting_time}) — races={len(set(r['Race No'] for r in results))}, "
                f"runners={len(results)}"
            )

        # Close the browser after scraping
        driver.quit()

        # Return the results
        return results

    except Exception as e:
        print(f"❌ Failed {venue_code}{date_str}: {e}")
        driver.quit()
        return []





def parse_race_results(soup, venue, date_str, venue_code, meeting_time):

    # -----------------------------------------------------------------
    # Bell Position Mapping (paste-ready)
    # -----------------------------------------------------------------
    bell_position_mapping = {
        ", leader at bell": "LEAD",
        "leader at bell": "LEAD",
        ", leader at the bell": "LEAD",
        "leader at the bell": "LEAD",

        "behind leader at bell": "B/LEAD",
        "behind leader at the bell": "B/LEAD",
        "outside leader at bell": "DEATH",
        "outside leader at the bell": "DEATH",
        "death seat at bell": "DEATH",
        "death seat at the bell": "DEATH",

        "bell lap, leader": "LEAD",
        "bell lap, behind leader": "B/LEAD",
        "bell lap, outside leader": "DEATH",
        "bell lap, 1 out 1 back": "1X1",
        "bell lap, 1 out 2 back": "1X2",
        "bell lap, 1 out 3 back": "1X3",
        "bell lap, 1 out 4 back": "1X4",
        "bell lap, 1 out 5 back": "1X5",
        "bell lap, 1 out 6 back": "1X6",
        "bell lap, 3 back on pegs": "3PEGS",
        "bell lap, 4 back on pegs": "4PEGS",
        "bell lap, 5 back on pegs": "5PEGS",
        "bell lap, 6 back on pegs": "6PEGS",
        "bell lap, 7 back on pegs": "7PEGS",
        "bell lap, 3 back on the pegs": "3PEGS",
        "bell lap, 4 back on the pegs": "4PEGS",
        "bell lap, 5 back on the pegs": "5PEGS",
        "bell lap, 6 back on the pegs": "6PEGS",
        "bell lap, 7 back on the pegs": "7PEGS",



        "1 out 1 back at bell": "1X1",
        "1 out 2 back at bell": "1X2",
        "1 out 3 back at bell": "1X3",
        "1 out 4 back at bell": "1X4",
        "1 out 5 back at bell": "1X5",
        "1 out 6 back at bell": "1X6",
        "1 out 7 back at bell": "1X6",
        "1 out 8 back at bell": "1X6",

        "800m, leader": "LEAD",
        "800m, outside leader": "DEATH",
        "800m, behind leader": "B/LEAD",
        "800m, 1 out 1 back": "1X1",
        "800m, 1 out 2 back": "1X2",
        "800m, 1 out 3 back": "1X3",
        "800m, 1 out 4 back": "1X4",
        "800m, 1 out 5 back": "1X5",
        "800m, 1 out 6 back": "1X6",
        "800m, 1 out 7 back": "1X6",
        "800m, 1 out 8 back": "1X6",

        "3 back on pegs at bell": "3PEGS",
        "4 back on pegs at bell": "4PEGS",
        "5 back on pegs at bell": "5PEGS",
        "6 back on pegs at bell": "6PEGS",
        "7 back on pegs at bell": "6PEGS",
        "8 back on pegs at bell": "6PEGS",

        "800m, 3 back on pegs": "3PEGS",
        "800m, 4 back on pegs": "4PEGS",
        "800m, 5 back on pegs": "5PEGS",
        "800m, 6 back on pegs": "6PEGS",
        "800m, 7 back on pegs": "6PEGS",
        "800m, 8 back on pegs": "6PEGS",

        "800m, 3 back on the pegs": "3PEGS",
        "800m, 4 back on the pegs": "4PEGS",
        "800m, 5 back on the pegs": "5PEGS",
        "800m, 6 back on the pegs": "6PEGS",
        "800m, 7 back on the pegs": "6PEGS",
        "800m, 8 back on the pegs": "6PEGS",

        "3 back pegs at bell": "3PEGS",
        "4 back pegs at bell": "4PEGS",
        "5 back pegs at bell": "5PEGS",
        "6 back pegs at bell": "6PEGS",
        "7 back pegs at bell": "6PEGS",
        "8 back pegs at bell": "6PEGS",

        "bell lap, 3 back on pegs": "3PEGS",
        "bell lap, 4 back on pegs": "4PEGS",
        "bell lap, 5 back on pegs": "5PEGS",
        "bell lap, 6 back on pegs": "6PEGS",
        "bell lap, 7 back on pegs": "6PEGS",
        "bell lap, 8 back on pegs": "6PEGS",

        "bell lap, 3 back on the pegs": "3PEGS",
        "bell lap, 4 back on the pegs": "4PEGS",
        "bell lap, 5 back on the pegs": "5PEGS",
        "bell lap, 6 back on the pegs": "6PEGS",
        "bell lap, 7 back on the pegs": "6PEGS",
        "bell lap, 8 back on the pegs": "6PEGS",

        "3 back on the pegs at bell": "3PEGS",
        "4 back on the pegs at bell": "4PEGS",
        "5 back on the pegs at bell": "5PEGS",
        "6 back on the pegs at bell": "6PEGS",
        "7 back on the pegs at bell": "6PEGS",
        "8 back on the pegs at bell": "6PEGS",

        "3 back inside at bell": "3PEGS",
        "4 back inside at bell": "4PEGS",
        "5 back inside at bell": "5PEGS",
        "6 back inside at bell": "6PEGS",
        "7 back inside at bell": "6PEGS",
        "8 back inside at bell": "6PEGS",

        "3rd fence at bell": "3PEGS",
        "4th fence at bell": "4PEGS",
        "5th fence at bell": "5PEGS",
        "6th fence at bell": "6PEGS",
        "7th fence at bell": "6PEGS",
        "8th fence at bell": "6PEGS",

        "leader 3 wideline at bell": "3WIDE",
        ", 3 wide throughout": "3WIDE",
        "3 wide throughout": "3WIDE",
        "three wide without cover at bell": "3WIDE",
        "3 wide without cover at bell": "3WIDE",
        "checked, three wide without cover": "3WIDE",
        "bell lap, three wide without cover": "3WIDE",

        "3 wide 1 back at bell": "3X1",
        "3 wide 2 back at bell": "3X2",
        "bell lap, 3 wide and 1 back": "3X1",
        "bell lap, 3 wide and 2 back": "3X2",
        "restrained after start, checked, 3 wide and 1 back": "3X1",
        "out of position at start, driver fined $50, starting position, restrained after start, checked, 3 wide and 2 back": "3X2",

        "1st horse 3 wide at bell": "3WIDE",
        "1st horse 4 wide at bell": "3WIDE",
        "2nd horse 3 wide at bell": "3X1",
        "3rd horse 3 wide at bell": "3X2",
        "4 wide at bell": "3WIDE",

        "three wide without cover": "3WIDE",
        "3 wide and 1 back at bell": "3X1",
        "3 wide and 2 back at bell": "3X2",
        "3 out 1 back at bell": "3X1",
        "3 out 2 back at bell": "3X2",
        "3 out 3 back at bell": "3X2",

        "tailed off": "TO",
        "tailed out": "TO",
        "trailed field": "TO",
        "disqualified": "TO",
        "failed to finish": "TO",
        "took no competitive part": "TO",
        "lost driver": "TO",
        ", retired": "TO",
        ", pulled up": "TO",
        "retired": "TO",
        "pulled up": "TO",

        ", led,": "LEAD",
        "bell lap, 1 out 1 back": "1X1",
        "bell lap, 1 out 2 back": "1X2",
        "bell lap, 1 out 3 back": "1X3",
        "bell lap, 1 out 4 back": "1X4",
        "bell lap, 1 out 5 back": "1X5",
        "bell lap, 1 out 6 back": "1X6",
        # add more as needed...
    }

    def extract_bell_position(comment):
        c = str(comment or "").lower().strip()

        if not c or c in ("nan", "none"):
            return "0"

        # --- terminal / non-performance ---
        if any(x in c for x in [
            "tailed off", "tailed out", "trailed field",
            "disqualified", "failed to finish",
            "lost driver", "pulled up", "retired",
            "took no competitive part"
        ]):
            return "TO"

        has_bell = ("bell" in c)

        # --- HARD GUARDS: these must NEVER become LEAD ---
        if has_bell and "behind leader" in c:
            return "B/LEAD"

        if has_bell and ("outside leader" in c or "death seat" in c):
            return "DEATH"

        # --- TRUE LEAD (only if guards above did not fire) ---
        if has_bell and (
            "leader at bell" in c
            or "leader at the bell" in c
            or "bell lap, leader" in c
            or ("bell lap" in c and "leader" in c)
        ):
            return "LEAD"

        # --- fallback phrase map (longest first) ---
        for phrase, label in sorted(
            bell_position_mapping.items(),
            key=lambda x: len(x[0]),
            reverse=True
        ):
            if phrase in c:
                return label

        return "0"




    results = []


    race_blocks = soup.find_all("table", class_="raceMoreInfo")
    runner_tables = soup.find_all("table", class_="raceFieldTable resultTable")
    race_times_tables = soup.find_all("table", class_="raceTimes")

    for race_index, (race_block, runner_table, race_times_table) in enumerate(zip(race_blocks, runner_tables, race_times_tables), start=1):
        try:
            race_number_tag = race_block.find("td", class_="raceNumber")
            race_time_tag = race_block.find("td", class_="raceTime")
            race_title_tag = race_block.find("td", class_="raceTitle")
            race_distance_tag = race_block.find("td", class_="distance")

            race_number = race_number_tag.get_text(strip=True) if race_number_tag else str(race_index)
            race_time = race_time_tag.get_text(strip=True) if race_time_tag else ""
            race_name = race_title_tag.get_text(strip=True) if race_title_tag else ""
            distance = race_distance_tag.get_text(strip=True).replace("M", "") if race_distance_tag else ""

            lead_time = first_qtr = second_qtr = third_qtr = fourth_qtr = ""
            tds = race_times_table.find_all("td")
            for td in tds:
                strong = td.find("strong")
                if strong:
                    label = strong.get_text(strip=True)
                    value = td.get_text(strip=True).replace(label, "").strip()
                    if "Lead Time" in label:
                        lead_time = value
                    elif "First Quarter" in label:
                        first_qtr = value
                    elif "Second Quarter" in label:
                        second_qtr = value
                    elif "Third Quarter" in label:
                        third_qtr = value
                    elif "Fourth Quarter" in label:
                        fourth_qtr = value

            gait = ""
            start = ""
            info_block = race_block.select_one("td.raceInformation")
            if info_block:
                info_text = info_block.get_text(separator=" ").upper()
                if "TROTTERS" in info_text:
                    gait = "TROTTERS"
                elif "PACERS" in info_text:
                    gait = "PACERS"
                if "MOBILE" in info_text:
                    start = "Mobile"
                elif "STAND" in info_text:
                    start = "Stand"

            runner_rows = runner_table.find_all("tr")
            for row in runner_rows:
                horse_td = row.find("td", class_="horse_name")
                if not horse_td:
                    continue

                horse_name_tag = horse_td.find("a", class_="horse_name_link")
                horse_name = horse_name_tag.get_text(strip=True) if horse_name_tag else ""

                placing = row.find("td", class_="horse_number").get_text(strip=True) if row.find("td", class_="horse_number") else ""
                prizemoney = row.find("td", class_="prizemoney").get_text(strip=True) if row.find("td", class_="prizemoney") else ""
                barrier = row.find("td", class_="barrier").get_text(strip=True) if row.find("td", class_="barrier") else ""
                trainer_short = row.find("td", class_="trainer-short").get_text(strip=True) if row.find("td", class_="trainer-short") else ""
                driver = row.find("td", class_="driver").get_text(strip=True) if row.find("td", class_="driver") else ""
                driver = _clean_person_name(driver)
                margin = row.find("td", class_="margin").get_text(strip=True) if row.find("td", class_="margin") else ""

                starting_price = ""
                starting_price_raw = row.find("td", class_="starting_price")
                if starting_price_raw:
                    sp_text = starting_price_raw.get_text(strip=True)
                    starting_price = sp_text.replace("fav", "").replace(" ", "").strip()

                if not starting_price:
                    continue

                stewards_comments = ""
                comments = ""
                stewards_td = row.find("td", class_="stewards_comments")
                if stewards_td:
                    stewards_span = stewards_td.find("span", class_="stewardsTooltip")
                    if stewards_span:
                        stewards_comments = stewards_span.get("title", "").strip()
                        comments = stewards_span.get_text(strip=True)

                bell_position = extract_bell_position(stewards_comments)

                # Spend
                try:
                    sp_clean = float(starting_price.replace("$", "").replace("fav", "").strip())
                    spend = round(100 / sp_clean, 2)
                except:
                    spend = ""

                photo_tag = soup.select_one("td.photoFinish a")
                photo_link = photo_tag["href"] if photo_tag else ""

                video_tag = soup.select_one("td.lastLapReplay a[href$='.mp4']")
                video_link = video_tag["href"] if video_tag else ""

                race_anchor_full = f"{venue_code}{date_str}_R{race_number}"
                state_from_code = _ensure_state(pd.DataFrame({"RaceAnchor": [f"{venue_code}{date_str}"]}))["State"].iloc[0]
                runner_anchor = f"{race_anchor_full}_{horse_name}"

                results.append({
                    "RaceAnchor": f"{venue_code}{date_str}",
                    "Venue": venue,
                    "Date": datetime.strptime(date_str, "%d%m%y").strftime("%d/%m/%Y"),
                    "MeetingTime": meeting_time,
                    "Race No": race_number,
                    "Time": race_time,
                    "Placing": placing,
                    "Horse": horse_name,
                    "Race Name": race_name,
                    "Distance": distance,
                    "Prizemoney": prizemoney,
                    "Barrier": barrier,
                    "Trainer": trainer_short,
                    "Driver": driver,
                    "Margin": margin,
                    "SP": starting_price,
                    "Spend": spend,
                    "P&L": (round(100 - spend, 2) if str(placing).strip() == "1" and spend != "" else (round(-spend, 2) if spend != "" else "")),
                    "State": state_from_code,
                    "SP_old": starting_price,
                    "StewardsComments": stewards_comments,
                    "Comments": comments,
                    "LeadTime": lead_time,
                    "1st Quarter": first_qtr,
                    "2nd Quarter": second_qtr,
                    "3rd Quarter": third_qtr,
                    "4th Quarter": fourth_qtr,
                    "Photo Link": photo_link,
                    "Video Link": video_link,
                    "RaceAnchorFull": race_anchor_full,
                    "RunnerAnchor": runner_anchor,
                    "Gait": gait,
                    "Start": start,
                    "BellPosition": bell_position,
                    "Half Distance": "",
                    "Width": "",
                    "Half Time": "",
                    "Ind Half": "",
                    "HorseDelta": "",
                })

        except Exception as e:
            print(f"⚠️ Error parsing race {race_index}: {e}")
            continue

    return results


# --- MAIN SCRAPE FLOW ---
all_results = []
start_date = datetime.today() - timedelta(days=1)

# -----------------------------
# PHASE 1: DISCOVERY (last 2 days, all venues)
# -----------------------------
print(f"🧭 Phase 1 (discovery): last {DISCOVERY_DAYS} day(s) across ALL venues")

discovered_meetings = set()  # optional: track meetings we hit (not strictly required)

for delta in range(DISCOVERY_DAYS):
    scrape_date = start_date - timedelta(days=delta)

    # Add this line to log the dates being scraped
    print(f"🔧 Scraping for date: {scrape_date.strftime('%d/%m/%Y')}")  # Log the exact date being scraped

    date_str = scrape_date.strftime("%d%m%y")

    for venue_name, venue_code in venue_code_map.items():
        results = scrape_meeting_results(venue_code, date_str)

        # None means: we got rate limited → stop the whole run
        if results is None:
            print("🛑 Stopping scrape due to rate limit. Try again later.")
            sys.exit(0)

        if results:
            all_results.extend(results)
            discovered_meetings.add(f"{venue_code}{date_str}")
            # tiny extra jitter only; function already slept 3.5–6.0s on hits
            time.sleep(0.25 + random.uniform(0.0, 0.25))
        else:
            # nil: don't hammer the site
            time.sleep(1.2 + random.uniform(0.0, 1.0))  # ~1.2 to 2.2s


# -----------------------------
# PHASE 2: BACKFILL (further 5 days, ONLY existing meetings in merged_file.csv)
# -----------------------------
if BACKFILL_EXTRA_DAYS > 0 and os.path.exists(MERGED_FILE):
    # We want the window: (yesterday - (DISCOVERY_DAYS + BACKFILL_EXTRA_DAYS - 1)) through (yesterday - DISCOVERY_DAYS)
    # Example with DISCOVERY_DAYS=2, BACKFILL_EXTRA_DAYS=5:
    #  - discovery covers days 0..1 back (yesterday and day before)
    #  - backfill covers days 2..6 back (5 additional days)
    backfill_start = start_date - timedelta(days=(DISCOVERY_DAYS + BACKFILL_EXTRA_DAYS - 1))
    backfill_end = start_date - timedelta(days=DISCOVERY_DAYS)

    print(
        f"🧩 Phase 2 (backfill): {BACKFILL_EXTRA_DAYS} extra day(s), "
        f"ONLY meetings already in merged_file.csv, window {backfill_start.date()} → {backfill_end.date()}"
    )

    targets = _existing_meetings_in_date_window(MERGED_FILE, backfill_start, backfill_end)

    # Optional: avoid rescraping meetings already hit in discovery
    if discovered_meetings:
        targets = [mc for mc in targets if mc not in discovered_meetings]

    print(f"🔁 Backfill targets found: {len(targets)}")

    for mc in targets:
        vc, ds = _split_meeting_code(mc)
        if not vc or not ds:
            continue

        results = scrape_meeting_results(vc, ds)

        if results is None:
            print("🛑 Stopping scrape due to rate limit during backfill. Try again later.")
            sys.exit(0)

        if results:
            all_results.extend(results)
            time.sleep(0.25 + random.uniform(0.0, 0.25))
        else:
            time.sleep(1.2 + random.uniform(0.0, 1.0))
else:
    print("ℹ️ Phase 2 (backfill) skipped — no merged_file.csv or BACKFILL_EXTRA_DAYS=0.")





if not all_results:
    print("No results scraped.")
    sys.exit(0)

df_new = pd.DataFrame(all_results)

# This file is not your master, so normal write is fine
df_new.to_csv(OUTPUT_FILE, index=False)
print(f"💾 Wrote {OUTPUT_FILE} ({len(df_new):,} rows)")



# -----------------------------
# Load existing merged and append/dedupe by RunnerAnchor
# -----------------------------
try:
    merged_df = pd.read_csv(MERGED_FILE, dtype=str)
    print(f"📂 Loaded existing merged file with {len(merged_df):,} rows.")
except FileNotFoundError:
    merged_df = pd.DataFrame()
    print("📁 No existing merged file found. Starting fresh.")

if "RunnerAnchor" in df_new.columns and "RunnerAnchor" in merged_df.columns and not merged_df.empty:
    merged_df = merged_df[~merged_df["RunnerAnchor"].isin(df_new["RunnerAnchor"])]

combined = pd.concat([merged_df, df_new], ignore_index=True)

# Ensure race stats + rebuild steps
combined = _ensure_race_stats(combined)
combined = _ensure_spend_pl(combined)
combined = _ensure_state(combined)
combined = _ensure_sp_old(combined)


combined = _ensure_half_time(combined)
combined = _ensure_vdwh(combined)


# ✅ NEW: backfill VDWH (covers existing + newly scraped rows)
combined = _ensure_vdwh(combined)

combined = _ensure_horse_runs(combined)



# -----------------------------
# ROW-COUNT SAFETY GUARD (prevents accidental truncation overwrite)
# -----------------------------
if not merged_df.empty:
    old_rows = len(merged_df)
    new_rows = len(combined)

    # If new file is suspiciously small, refuse to overwrite the master.
    # (Tune the 0.95 threshold if you like; 0.95 = allow up to 5% shrink)
    if new_rows < int(old_rows * 0.95):
        print("🚨 REFUSING to overwrite merged_file.csv — new row count is far smaller than the existing master.")
        print(f"   Old rows: {old_rows:,}  New rows: {new_rows:,}")
        review_path = "merged_file_REVIEW.csv"
        combined.to_csv(review_path, index=False)
        print(f"📝 Wrote review file instead: {review_path}")
        sys.exit(1)

# -----------------------------
# SAFE MASTER WRITE (backup + atomic replace)
# -----------------------------
bk = backup_file(MERGED_FILE)
if bk:
    print(f"🧯 Backup created: {bk}")

atomic_to_csv(combined, MERGED_FILE)
print(f"💾 Safely updated master: {MERGED_FILE} ({len(combined):,} rows)")

_rebuild_steps_3_to_6(MERGED_FILE, shrink_k=SHRINK_K, ignore_widths=IGNORE_WIDTHS)
print("✅ Done (scrape + rebuild).")


# ✅✅✅ ADD THIS BLOCK RIGHT HERE (before the diagnostic reads merged_file.csv)
stamp_published_market_into_merged(
    merged_csv=MERGED_FILE,
    published_csv="published_markets.csv",
)


# =============================
# DIAGNOSTIC (tight)
# =============================
df = pd.read_csv(MERGED_FILE, dtype=str, low_memory=False)

df["BellPosition"] = df.get("BellPosition", "").astype(str).str.replace("\u00A0", " ", regex=False).str.upper().str.strip()

if "StewardsComments" not in df.columns:
    print("⚠️ No StewardsComments column found — can't run diagnostic.")
else:
    sc_norm = _norm_sc(df["StewardsComments"])

    pat_bad = r"(?:behind leader at (?:the )?bell|outside leader at (?:the )?bell|death seat at (?:the )?bell)"
    x = df[(df["BellPosition"] == "LEAD") & (sc_norm.str.contains(pat_bad, na=False, regex=True))]

    print("LEAD rows containing TRUE bell position phrases (behind/outside/death at bell):", len(x))
    print(x[["BellPosition", "StewardsComments"]].head(30).to_string(index=False))


    backup_python_script_daily(
        src_file=r"C:\harness_scraper\harness_api\scrape_results.py",  # Replace with the actual path to your script
        backup_dir=r"C:\Users\joel\OneDrive\Trotify\backups",
        keep_last=7  # Keep the last 7 backups
    )


















