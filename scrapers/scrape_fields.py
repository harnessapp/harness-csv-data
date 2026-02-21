import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
from datetime import timedelta
import numpy as np
import time
from typing import Optional
import os
import random
from pathlib import Path


# -----------------------------
# Pipeline toggles
# -----------------------------
# If you just want fresh *fields* but do NOT want to spend time recalculating
# barrier / driver / trainer stats, set these to False.
#
# Tip: with PRESERVE_PREVIOUS_* enabled, the script will try to carry forward
# those stat columns from the existing upcoming_fields.csv into the newly
# scraped file (matched by RunnerAnchor where possible).
RECALC_BARRIER_STATS = True
RECALC_DRIVER_STATS  = True
RECALC_TRAINER_STATS = True

PRESERVE_PREVIOUS_STATS_WHEN_SKIPPED = True

REPO_ROOT = Path(__file__).resolve().parents[1]  # scrapers/ -> repo root
MERGED_PATH = REPO_ROOT / "merged_file.csv"


# -----------------------------
# HTTP session (headers + timeout helper)
# -----------------------------
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (compatible; HarnessScraper/1.0)"})
REQUEST_TIMEOUT = 15

def http_get(url: str):
    return SESSION.get(url, timeout=REQUEST_TIMEOUT)

# Toggle this if you ever need the raw race HTML dump
DEBUG_HTML = False

BASE_URL = "https://legacy.harness.org.au/fields.cfm?mc="


from pathlib import Path
import shutil
from datetime import datetime

def backup_upcoming_fields_daily(
    src_csv: str = "upcoming_fields.csv",
    backup_dir: str = r"C:\Users\joel\OneDrive\Trotify",
    keep_last: int = 7,
):
    """
    Backup upcoming_fields.csv to a fixed folder:
      - max once per day
      - keep last N (default 7)
      - filename: upcoming_fields_YYYYMMDD.bak
    """
    src = Path(src_csv)
    if not src.exists():
        print(f"ℹ️  No upcoming_fields backup made (missing): {src}")
        return

    bdir = Path(backup_dir)
    bdir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    dst = bdir / f"upcoming_fields_{today}.bak"

    # Max once per day
    if dst.exists():
        print(f"ℹ️  Backup already exists for today: {dst.name}")
        return

    # Create backup
    try:
        shutil.copy2(src, dst)
        print(f"✅ Upcoming_fields backup created: {dst}")
    except Exception as e:
        print(f"⚠️ Upcoming_fields backup failed: {e}")
        return

    # Prune old backups (keep newest keep_last)
    try:
        backups = sorted(
            bdir.glob("upcoming_fields_????????.bak"),
            key=lambda p: p.name,   # YYYYMMDD sorts correctly by name
            reverse=True
        )
        for old in backups[keep_last:]:
            try:
                old.unlink()
            except Exception:
                pass
    except Exception:
        pass



def generate_next_target_dates():
    # Generate the next 7 days' target dates (in the format DDMMYY)
    current_date = datetime.today()
    target_dates = []
    for i in range(7):
        target_day = current_date + timedelta(days=i)
        target_dates.append(target_day.strftime("%d%m%y"))
    return target_dates

venue_code_map = {
    "Armidale": "AE", "Albury": "AL", "Albion Park": "AP", "Ararat": "AR", "Gawler": "AW",
    "Albany": "AY", "Ballarat": "BA", "Blayney": "BB", "Burnie": "BE", "Bridgetown": "BG",
    "Bathurst": "BH", "Bankstown": "BK", "Bendigo": "BN", "Broken Hill": "BR", "Boort": "BT",
    "Busselton": "BU", "Bunbury": "BY", "Cowra": "CA", "Canberra": "CB", "Charlton": "CH",
    "Carrick": "CK", "Coolamon": "CL", "Cobram": "CO", "Cranbourne": "CR", "Collie": "CX",
    "Darling Downs at Warwick": "DJ", "Dubbo": "DU", "Devonport": "DV", "South Australia": "DZ",
    "Echuca": "EC", "Hobart": "EH", "Lockyer": "EQ", "Eugowra": "EU", "Wagga at Riverina Paceway": "EY",
    "Forbes": "FB", "Swan Hill": "FD", "Globe Derby Park": "GD", "Geelong": "GE", "Gloucester Park": "GP",
    "Griffith": "GR", "Gunbower": "GU", "Hamilton": "HM", "Horsham": "HS", "Kilcoy": "IJ",
    "Birchip": "IR", "Junee": "JU", "Bendigo at Melton": "JY", "Kilmore": "KI", "Kapunda": "KP", "Leeton": "LE",
    "Orange at Bathurst": "LH", "Goulburn": "LM", "Launceston": "LN", "Maitland": "MD",
    "Tabcorp Pk Menangle": "ME", "Mount Gambier": "MG", "Maryborough": "MH", "Mildura": "ML",
    "Melton": "MX", "Narrabri": "NA", "Narrogin": "NG", "Northam": "NM", "Newcastle": "NR",
    "Ouyen": "OU", "Pinjarra": "PA", "Nswhrc at Tabcorp Pk Menangle": "PC", "Penrith": "PE",
    "Parkes": "PK", "Port Pirie": "PP", "Mildura at Swan Hill": "QA", "Wedderburn at Maryborough": "QP",
    "Wangaratta at Shepparton": "QY", "St Arnaud at Charlton": "QZ", "Redcliffe": "RE", "St Arnaud": "SA",
    "Scottsdale": "SC", "Shepparton": "SP", "Strathalbyn at Globe Derby Park": "SQ", "Strathalbyn": "ST",
    "Stawell": "SW", "Tamworth": "TA", "Terang": "TE", "Temora": "TM", "Marburg": "UG",
    "Kadina at Port Pirie": "UI", "Mooroopna at Shepparton": "VC", "Victor Harbor": "VH",
    "Elmore at Bendigo": "VL", "Kyabram at Shepparton": "VV", "Wagin": "WA", "Wedderburn": "WD",
    "West Wyalong": "WE", "Wangaratta": "WN", "Warragul": "WR", "Williams": "WS", "Yarra Valley": "YG",
    "Young": "YU", "Central Wheatbelt": "ZO",
}

# Note: duplicates in this map are harmless (last wins), but you can tidy later.
state_map = {
    "AP": "QLD", "RE": "QLD", "SP": "VIC", "BN": "VIC", "YU": "NSW", "BH": "NSW", "NM": "WA",
    "BU": "WA", "EC": "VIC", "LE": "NSW", "NR": "NSW", "AY": "WA", "GD": "SA", "MX": "VIC",
    "PC": "NSW", "BT": "VIC", "EH": "TAS", "TA": "NSW", "MH": "VIC", "PA": "WA", "DZ": "SA",
    "FD": "VIC", "TM": "NSW", "BA": "VIC", "PK": "NSW", "CR": "VIC", "PE": "NSW", "TE": "VIC",
    "CK": "TAS", "GP": "WA", "CO": "VIC", "LM": "NSW", "CH": "VIC", "AL": "NSW", "ML": "VIC",
    "GE": "VIC", "KI": "VIC", "LN": "TAS", "DV": "TAS", "HM": "VIC", "YG": "VIC", "JU": "NSW",
    "IJ": "QLD", "SW": "VIC", "NG": "WA", "BE": "TAS", "WD": "VIC", "CB": "NSW", "HS": "VIC",
    "LH": "NSW", "AR": "VIC", "BY": "WA", "QZ": "VIC", "WS": "WA", "WR": "VIC", "CX": "WA",
    "EY": "NSW", "UG": "QLD", "IR": "VIC", "AW": "SA", "QY": "VIC", "MD": "NSW", "BR": "NSW",
    "DU": "NSW", "BK": "NSW", "BG": "WA", "KP": "SA", "OU": "VIC", "ZO": "WA", "WA": "WA",
    "VH": "SA", "NA": "NSW", "FB": "NSW", "VV": "VIC", "ME": "NSW", "GU": "VIC", "AE": "NSW",
    "CA": "NSW", "VC": "VIC", "QA": "VIC", "WE": "NSW", "GR": "NSW", "BB": "NSW", "ST": "SA",
    "WN": "VIC", "PP": "SA", "MG": "SA", "CL": "NSW", "QP": "VIC", "UI": "SA", "SA": "VIC",
    "VL": "VIC", "SC": "TAS", "SQ": "SA", "EQ": "QLD", "DJ": "QLD",
}

def build_meeting_codes():
    target_dates = generate_next_target_dates()
    codes = []
    for date in target_dates:
        for code in venue_code_map.values():
            codes.append(code + date)
    return codes


def _carry_forward_stats(new_df: pd.DataFrame, old_df: pd.DataFrame) -> pd.DataFrame:
    """Carry forward Br*/Dr*/Tr* stat columns from the previous upcoming_fields.csv.

    Used when you skip recalculating stats.
    Matching: RunnerAnchor first, then (RaceAnchorFull + Horse).
    """

    # Stats columns we preserve
    stat_cols = [c for c in old_df.columns if c.startswith("Br ") or c.startswith("Dr ") or c.startswith("Tr ")]
    if not stat_cols:
        print("ℹ️  No Br/Dr/Tr columns found in old_df to preserve.")
        return new_df

    def _merge_on_keys(keys: list[str]) -> pd.DataFrame:
        old_sub = old_df[keys + stat_cols].drop_duplicates(subset=keys)
        merged = new_df.merge(old_sub, how="left", on=keys, suffixes=("", "__old"))

        for c in stat_cols:
            old_c = c + "__old"
            if old_c not in merged.columns:
                continue

            # If new_df didn't have the column, create it from old
            if c not in merged.columns:
                merged[c] = merged[old_c]
            else:
                # If it exists, fill blanks only
                merged[c] = merged[c].where(~merged[c].isna(), merged[old_c])

        # Drop temp cols
        drop_cols = [c + "__old" for c in stat_cols if (c + "__old") in merged.columns]
        merged.drop(columns=drop_cols, inplace=True, errors="ignore")
        return merged

    # Prefer RunnerAnchor
    if "RunnerAnchor" in new_df.columns and "RunnerAnchor" in old_df.columns:
        print("ℹ️  Preserving stats using key: RunnerAnchor")
        return _merge_on_keys(["RunnerAnchor"])

    # Fallback: RaceAnchorFull + Horse
    if (
        "RaceAnchorFull" in new_df.columns and "RaceAnchorFull" in old_df.columns and
        "Horse" in new_df.columns and "Horse" in old_df.columns
    ):
        print("ℹ️  Preserving stats using keys: RaceAnchorFull + Horse")
        return _merge_on_keys(["RaceAnchorFull", "Horse"])

    print("⚠️  No usable key found to preserve stats (need RunnerAnchor or RaceAnchorFull+Horse).")
    return new_df


# Remove trailing (TR), (Em X), ($x,xxx) tags from horse names
HORSE_SUFFIX_RE_CLEAN = re.compile(r"\s*\((?:TR|[Ee]m\.?\s*\d*|\$[\d,]+)\)\s*$", re.IGNORECASE)

def clean_horse_name(name: str) -> str:
    if name is None:
        return ""
    s = str(name).replace("\u00A0", " ").strip()
    s = HORSE_SUFFIX_RE_CLEAN.sub("", s).strip()
    s = re.sub(r"\s{2,}", " ", s)
    return s



    print("DEBUG clean_horse_name is defined at line", clean_horse_name.__code__.co_firstlineno)


def snapshot_published_markets(
    uf_csv="upcoming_fields.csv",
    out_csv="published_markets.csv",
):
    """
    Append-only snapshot of the market you publish from upcoming_fields.csv.

    Dedupes on (RunnerAnchor, PublishedAt) and also keeps only the latest row per
    (RunnerAnchor) if the same runner is re-priced multiple times in the same run.
    """

    import os
    import pandas as pd
    from datetime import datetime

    if not os.path.exists(uf_csv):
        print(f"⚠️ snapshot_published_markets: missing {uf_csv}")
        return

    uf = pd.read_csv(uf_csv, dtype=str).fillna("")

    if "RunnerAnchor" not in uf.columns:
        print("⚠️ snapshot_published_markets: RunnerAnchor missing in upcoming_fields.csv")
        return

    # Only snapshot rows that actually have a market
    needed = ["Fair Odds", "Fair %", "Fair Prob", "MarketRank", "RaceOverround"]
    has_any = any(c in uf.columns for c in needed)
    if not has_any:
        print("⚠️ snapshot_published_markets: no market cols found (Fair Odds / Fair % / etc). Skipping.")
        return

    published_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Choose some useful context cols if present
    cols = []
    for c in [
        "RunnerAnchor",
        "RaceAnchorFull",
        "Race Anchor",
        "Date",
        "Venue",
        "Race No",
        "Race Name",
        "Horse",
        "Barrier",
        "Driver",
        "Trainer",
        "ModelRating",
        "Rating",
        "Fair Prob",
        "Fair %",
        "Fair Odds",
        "Fair Odds (100)",
        "MarketRank",
        "RaceOverround",
    ]:
        if c in uf.columns:
            cols.append(c)

    snap = uf[cols].copy()
    snap.insert(0, "PublishedAt", published_at)

    # Drop blanks/no RunnerAnchor
    snap["RunnerAnchor"] = snap["RunnerAnchor"].astype(str).str.strip()
    snap = snap[snap["RunnerAnchor"] != ""]

    # If Fair Odds exists, keep only rows with a value
    if "Fair Odds" in snap.columns:
        snap = snap[snap["Fair Odds"].astype(str).str.strip() != ""]

    if snap.empty:
        print("⚠️ snapshot_published_markets: nothing to write (no priced runners).")
        return

    # If you re-run within same second, de-dupe
    snap = snap.drop_duplicates(subset=["PublishedAt", "RunnerAnchor"], keep="last")

    if os.path.exists(out_csv):
        existing = pd.read_csv(out_csv, dtype=str).fillna("")
        combined = pd.concat([existing, snap], ignore_index=True)

        # Optional: keep only the latest snapshot per RunnerAnchor per day
        # (comment out if you want full tick-by-tick history)
        # combined["__dt"] = pd.to_datetime(combined["PublishedAt"], errors="coerce")
        # combined = combined.sort_values("__dt").drop(columns="__dt")
        # combined = combined.drop_duplicates(subset=["RunnerAnchor"], keep="last")

        # Keep it tidy: newest last is fine, but you can sort if you like
        combined.to_csv(out_csv, index=False)
    else:
        snap.to_csv(out_csv, index=False)

    print(f"✅ Snapshot written: {len(snap):,} rows -> {out_csv}")




def backup_python_script_daily(src_file, backup_dir, keep_last=7):
    """
    Daily backup of a python script. Skips automatically when BACKUPS_ENABLED=0
    (e.g. on GitHub Actions).
    """
    import os
    import shutil
    from datetime import datetime

    # ✅ Skip backups when disabled (GitHub Actions)
    if os.getenv("BACKUPS_ENABLED", "1").strip() in ("0", "false", "False", "no", "NO"):
        print("ℹ️ BACKUPS_ENABLED=0 — skipping python script backup.")
        return

    # Resolve to an absolute path if a relative path was provided
    src_file = os.path.abspath(src_file)

    if not os.path.exists(src_file):
        print(f"⚠️ backup_python_script_daily: source file not found: {src_file} — skipping.")
        return

    os.makedirs(backup_dir, exist_ok=True)

    base = os.path.basename(src_file)
    stamp = datetime.now().strftime("%Y%m%d")
    backup_path = os.path.join(backup_dir, f"{base}.{stamp}.bak")

    shutil.copy2(src_file, backup_path)
    print(f"✅ Backed up script to {backup_path}")

    # Keep last N backups for this script
    try:
        backups = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith(base + ".") and f.endswith(".bak")]
        )
        if len(backups) > keep_last:
            for f in backups[: len(backups) - keep_last]:
                try:
                    os.remove(os.path.join(backup_dir, f))
                except Exception:
                    pass
    except Exception:
        pass




def main():
    # If we're skipping stat recalcs, keep a copy of the existing file so we can
    # carry forward Br*/Dr*/Tr* columns into the newly scraped output.
    old_df = None
    want_preserve = (
        PRESERVE_PREVIOUS_STATS_WHEN_SKIPPED and
        (not RECALC_BARRIER_STATS or not RECALC_DRIVER_STATS or not RECALC_TRAINER_STATS) and
        os.path.exists("upcoming_fields.csv")
    )
    if want_preserve:
        try:
            old_df = pd.read_csv("upcoming_fields.csv", low_memory=False)
            print(f"ℹ️  Preserving prior stats: loaded {len(old_df)} rows from existing upcoming_fields.csv")
        except Exception as e:
            print(f"⚠️  Could not read existing upcoming_fields.csv for stat preservation: {e}")
            old_df = None

        # ------------------------------------------------------------
    # Load merged_file.csv ONCE for VenDist Sample lookups
    # ------------------------------------------------------------
    print("📦 Loading merged_file.csv once for VenDist Sample counts...")
    merged_data = pd.read_csv("merged_file.csv", low_memory=False)
    merged_data["VenDist"] = merged_data["Venue"].astype(str) + "_" + merged_data["Distance"].astype(str)
    ven_dist_counts = merged_data["VenDist"].value_counts().to_dict()
    print(f"✅ VenDist keys loaded: {len(ven_dist_counts):,}")



    all_rows = []
    codes = build_meeting_codes()

    for code in codes:
        try:
            rows = parse_meeting(code, ven_dist_counts)

            if rows:
                venue = rows[0].get("Venue", "").strip()
                meeting_time = rows[0].get("MeetingTime", "").strip()
                suffix = f"{venue}" + (f" ({meeting_time})" if meeting_time else "")
                print(f"✅ {code} — {suffix}")

                all_rows.extend(rows)
                time.sleep(0.8)   # real meeting → polite

            else:
                print(f"❌ {code} — nil")
                time.sleep(0.05)  # no meeting → fast skip

        except Exception as e:
            print(f"⚠️ {code} — error: {e}")
            time.sleep(0.2)





    df = pd.DataFrame(all_rows)

    # Optionally carry forward previous stats (Br*/Dr*/Tr*) into the freshly scraped file
    if old_df is not None:
        df = _carry_forward_stats(df, old_df)
        print("✅ Carried forward Br/Dr/Tr stat columns from the previous file")
    df.to_csv("upcoming_fields.csv", index=False)
    print(f"Saved {len(df)} rows to upcoming_fields.csv")


def add_ven_dist_sample():
    # (Kept for compatibility; you can prefer add_ven_dist_gait_start_sample which also sets Gait/Start sample)
    upcoming_fields = pd.read_csv("upcoming_fields.csv")
    merged_data = pd.read_csv("merged_file.csv")

    upcoming_fields['VenDist'] = upcoming_fields['Venue'] + "_" + upcoming_fields['Distance'].astype(str)
    merged_data['VenDist'] = merged_data['Venue'] + "_" + merged_data['Distance'].astype(str)

    unique_merged_data = merged_data.drop_duplicates(subset=['VenDist', 'RaceAnchorFull'])
    ven_dist_counts = unique_merged_data['VenDist'].value_counts()
    upcoming_fields['VenDist Sample'] = upcoming_fields['VenDist'].map(ven_dist_counts).fillna(0).astype(int)

    # Keep only rows with a valid horse number (runner rows)
    upcoming_fields = upcoming_fields[upcoming_fields['Horse No'].notna() & (upcoming_fields['Horse No'] != '')]

    if not upcoming_fields.empty:
        upcoming_fields.to_csv("upcoming_fields.csv", index=False)
        print(f"✅ Saved {len(upcoming_fields)} rows to upcoming_fields.csv")
    else:
        print("❌ No rows to save — upcoming_fields is empty!")

    print(f"Updated file saved as 'upcoming_fields.csv'.")


def add_ven_dist_gait_start_sample():
    upcoming_fields = pd.read_csv("upcoming_fields.csv")
    merged_data = pd.read_csv("merged_file.csv", low_memory=False)

    def _clean_dist_value(x):
        s = str(x).strip()
        # "2138.0" -> "2138"
        if s.endswith(".0"):
            s = s[:-2]
        # "1609m" -> "1609" (just in case)
        s = s.replace("m", "").replace("M", "")
        return s

    # Normalise Distance for BOTH frames so keys match
    upcoming_fields["Distance"] = upcoming_fields["Distance"].apply(_clean_dist_value)
    merged_data["Distance"] = merged_data["Distance"].apply(_clean_dist_value)

    # Build VenDist keys
    upcoming_fields["VenDist"] = upcoming_fields["Venue"].astype(str).str.strip() + "_" + upcoming_fields["Distance"]
    merged_data["VenDist"] = merged_data["Venue"].astype(str).str.strip() + "_" + merged_data["Distance"]

    # Build VenDistGaitStart keys
    upcoming_fields["VenDistGaitStart"] = (
        upcoming_fields["Venue"].astype(str).str.strip() + "_" +
        upcoming_fields["Distance"] + "_" +
        upcoming_fields["Gait"].astype(str).str.lower().str.strip() + "_" +
        upcoming_fields["Start"].astype(str).str.lower().str.strip()
    )
    merged_data["VenDistGaitStart"] = (
        merged_data["Venue"].astype(str).str.strip() + "_" +
        merged_data["Distance"] + "_" +
        merged_data["Gait"].astype(str).str.lower().str.strip() + "_" +
        merged_data["Start"].astype(str).str.lower().str.strip()
    )

    unique_merged_data = merged_data.drop_duplicates(subset=["VenDistGaitStart", "RaceAnchorFull"])
    ven_dist_counts = unique_merged_data["VenDist"].value_counts()
    ven_dist_gait_start_counts = unique_merged_data["VenDistGaitStart"].value_counts()

    upcoming_fields["VenDist Sample"] = (
        upcoming_fields["VenDist"].map(ven_dist_counts).fillna(0).astype(int)
    )
    upcoming_fields["VenDistGaitStart Sample"] = (
        upcoming_fields["VenDistGaitStart"].map(ven_dist_gait_start_counts).fillna(0).astype(int)
    )

    upcoming_fields = upcoming_fields[upcoming_fields["Horse No"].notna() & (upcoming_fields["Horse No"] != "")]

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("Updated file saved as 'upcoming_fields.csv'.")


def add_benchmark_quarters():
    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False, na_values=["#DIV/0!"])
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # Build the join key
    for df in [upcoming_fields, merged_data]:
        df["VDSG"] = (
            df["Venue"].str.lower() + "_" +
            df["Distance"].astype(str) + "_" +
            df["Gait"].str.lower() + "_" +
            df["Start"].str.lower()
        )

    # Flexible source detection for lead time + quarters
    quarter_cols = ["1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter"]
    lead_opts = ["LeadTime", "Lead Time"]

    keep_cols = []
    for c in lead_opts + quarter_cols:
        if c in merged_data.columns:
            keep_cols.append(c)

    merged_subset = merged_data[["VDSG"] + keep_cols].copy()
    for col in keep_cols:
        merged_subset[col] = pd.to_numeric(merged_subset[col], errors='coerce')

    bench = merged_subset.groupby("VDSG").mean(numeric_only=True)

    # Build rename map to BM columns
    rename_map = {}
    if "LeadTime" in bench.columns:
        rename_map["LeadTime"] = "BM LT"
    if "Lead Time" in bench.columns:
        rename_map["Lead Time"] = "BM LT"
    for q in quarter_cols:
        if q in bench.columns:
            q_short = q.split()[0].upper()  # "1ST"
            q_label = "Q" + q_short[0]      # 1ST -> Q1
            rename_map[q] = f"BM {q_label}"

    benchmark_averages = bench.rename(columns=rename_map)

    upcoming_fields = upcoming_fields.merge(
        benchmark_averages,
        how="left",
        left_on="VDSG",
        right_index=True
    )

    # Round to 1 dp where present
    for c in ["BM LT", "BM Q1", "BM Q2", "BM Q3", "BM Q4"]:
        if c in upcoming_fields.columns:
            upcoming_fields[c] = upcoming_fields[c].round(1)

    upcoming_fields.drop(columns=["VDSG"], inplace=True)

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with benchmark quarter averages")


# Remove trailing (Em X) or ($x,xxx) from horse names (used elsewhere)
HORSE_SUFFIX_RE_EM = re.compile(r"\s*\((?:[Ee]m\.?\s*\d*|\$[\d,]+)\)\s*$", re.IGNORECASE)


def add_barrier_stats():
    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False, na_values=["#DIV/0!"])

        # Convert Spend and P&L to numeric (strip $ and commas)
        merged_data["Spend"] = (
            merged_data["Spend"].astype(str)
            .str.replace("#DIV/0!", "", regex=False)
            .str.replace(r"[\$,]", "", regex=True)
            .replace("", pd.NA)
            .astype(float)
        )
        merged_data["P&L"] = (
            merged_data["P&L"].astype(str)
            .str.replace("#DIV/0!", "", regex=False)
            .str.replace(r"[\$,]", "", regex=True)
            .replace("", pd.NA)
            .astype(float)
        )

    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    def _clean_dist(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip()
        # "2138.0" -> "2138", "1609m" -> "1609"
        s = s.str.replace(r"\.0$", "", regex=True)
        s = s.str.replace(r"[^\d]", "", regex=True)
        return s.fillna("").astype(str)

    def _clean_barrier(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip().str.lower()
        # "1.0" -> "1"
        s = s.str.replace(r"\.0$", "", regex=True)
        return s

    # Normalize columns for matching
    for df in [upcoming_fields, merged_data]:
        df["_VenueKey"] = df["Venue"].astype(str).str.strip().str.lower()
        df["_DistKey"] = _clean_dist(df["Distance"])
        df["_GaitKey"] = df["Gait"].astype(str).str.strip().str.lower()
        df["_StartKey"] = df["Start"].astype(str).str.strip().str.lower()

        df["VDSG"] = (
            df["_VenueKey"] + "_" +
            df["_DistKey"] + "_" +
            df["_GaitKey"] + "_" +
            df["_StartKey"]
        )

        df["Barrier_str"] = _clean_barrier(df["Barrier"])


    # --- NORMALISE DISTANCE FOR VENUE / VDSG KEYS ---
    def _clean_dist_value(x):
        s = str(x).strip()
        if s.endswith(".0"):
            s = s[:-2]
        s = s.replace("m", "")
        return s

    upcoming_fields["Distance"] = upcoming_fields["Distance"].apply(_clean_dist_value)



    # Merge barrier and VDSG into a single key
    merged_data["VDSG_BARRIER"] = merged_data["VDSG"] + "_" + merged_data["Barrier_str"]
    upcoming_fields["VDSG_BARRIER"] = upcoming_fields["VDSG"] + "_" + upcoming_fields["Barrier_str"]

    # Debug overlap (optional prints retained)
    merged_keys = set(merged_data["VDSG_BARRIER"].dropna().unique())
    upcoming_keys = set(upcoming_fields["VDSG_BARRIER"].dropna().unique())
    overlap = merged_keys & upcoming_keys
    print(f"🔁 Matching VDSG_BARRIER keys: {len(overlap)}")
    if overlap:
        print("Sample keys that matched:", list(overlap)[:5])
    else:
        print("⚠️ No VDSG_BARRIER matches found!")

    print("---- VDSG_BARRIER DEBUG ----")

    print("merged_data rows:", len(merged_data))
    print("upcoming_fields rows:", len(upcoming_fields))

    print(
        "merged VDSG_BARRIER non-empty:",
        merged_data["VDSG_BARRIER"].astype(str).str.strip().ne("").sum()
    )
    print(
        "upcoming VDSG_BARRIER non-empty:",
        upcoming_fields["VDSG_BARRIER"].astype(str).str.strip().ne("").sum()
    )

    print("merged sample VDSG_BARRIER keys:",
          merged_data["VDSG_BARRIER"].dropna().unique()[:5])

    print("upcoming sample VDSG_BARRIER keys:",
          upcoming_fields["VDSG_BARRIER"].dropna().unique()[:5])


    # Normalise numeric fields
    merged_data["P&L"] = pd.to_numeric(merged_data["P&L"], errors="coerce")
    merged_data["Spend"] = pd.to_numeric(merged_data["Spend"], errors="coerce")
    merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    # Pre-calc barrier stats
    stats = merged_data.groupby("VDSG_BARRIER").agg({
        "Barrier": "count",
        "Placing": [
            lambda x: (x == 1).sum(),
            lambda x: ((x == 2) | (x == 3)).sum()
        ],
        "P&L": "sum",
        "Spend": "sum"
    })

    stats.columns = ["Br Sts", "Br Wins", "Br Places", "Br P&L", "Br Spend"]
    stats = stats.reset_index()

    # Merge into upcoming_fields
    upcoming_fields = upcoming_fields.merge(stats, how="left", on="VDSG_BARRIER")

    # Replace NaNs with 0s for counts and sums
    for c in ["Br Sts", "Br Wins", "Br Places", "Br P&L", "Br Spend"]:
        if c in upcoming_fields.columns:
            upcoming_fields[c] = upcoming_fields[c].fillna(0)

    # % columns
    upcoming_fields["Br Win %"] = upcoming_fields.apply(
        lambda row: round(row["Br Wins"] / row["Br Sts"] * 100, 2) if row["Br Sts"] > 0 else 0.0,
        axis=1
    )
    upcoming_fields["Br Pla %"] = upcoming_fields.apply(
        lambda row: round((row["Br Wins"] + row["Br Places"]) / row["Br Sts"] * 100, 2) if row["Br Sts"] > 0 else 0.0,
        axis=1
    )

    # ROI
    upcoming_fields["Br P&L"] = pd.to_numeric(upcoming_fields["Br P&L"], errors="coerce").fillna(0)
    upcoming_fields["Br Spend"] = pd.to_numeric(upcoming_fields["Br Spend"], errors="coerce").fillna(0)
    upcoming_fields["Br ROI %"] = upcoming_fields.apply(
        lambda row: round(row["Br P&L"] / row["Br Spend"] * 100, 2) if row["Br Spend"] > 0 else 0.0,
        axis=1
    )

    # Drop helpers
    upcoming_fields.drop(columns=["VDSG", "VDSG_BARRIER", "Barrier_str", "Br P&L", "Br Spend"], inplace=True)

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with barrier stats")


def add_barrier_recent_stats():
    import numpy as np
    import pandas as pd

    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False, na_values=["#DIV/0!"])
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    merged_data["Date"] = pd.to_datetime(merged_data["Date"], errors="coerce", dayfirst=True)
    upcoming_fields["Date"] = pd.to_datetime(upcoming_fields["Date"], errors="coerce")

    # Clean numeric fields
    for col in ["Spend", "P&L"]:
        merged_data[col] = (
            merged_data[col].astype(str)
            .str.replace("#DIV/0!", "", regex=False)
            .str.replace(r"[\$,]", "", regex=True)
            .replace("", np.nan)
            .astype(float)
        )
    merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    # Build VDSG + Barrier key
    for df in [upcoming_fields, merged_data]:
        df["VDSG"] = (
            df["Venue"].astype(str).str.lower().str.strip() + "_" +
            df["Distance"].astype(str).str.strip() + "_" +
            df["Gait"].astype(str).str.lower().str.strip() + "_" +
            df["Start"].astype(str).str.lower().str.strip()
        )
        df["Barrier_str"] = df["Barrier"].astype(str).str.strip().str.lower()
        df["VDSG_BARRIER"] = df["VDSG"] + "_" + df["Barrier_str"]

    windows = {
        "Br 30": 30, "Br 90": 90, "Br 180": 180, "Br 365": 365, "Br All": 0, "Br L/100": None
    }

    needed = set(upcoming_fields["VDSG_BARRIER"].dropna().unique())
    md = merged_data[
        merged_data["VDSG_BARRIER"].notna()
        & merged_data["Date"].notna()
        & merged_data["VDSG_BARRIER"].isin(needed)
    ].copy()

    md["win_flag"] = (md["Placing"] == 1).astype(int)
    md["place_flag"] = ((md["Placing"] == 2) | (md["Placing"] == 3)).astype(int)
    md["Spend"] = md["Spend"].fillna(0.0)
    md["P&L"] = md["P&L"].fillna(0.0)

    md.sort_values(["VDSG_BARRIER", "Date"], inplace=True)

    index = {}
    for key, g in md.groupby("VDSG_BARRIER", sort=False):
        dates = g["Date"].to_numpy(dtype="datetime64[ns]")
        win_cum = np.concatenate([[0], g["win_flag"].to_numpy(dtype=np.int64).cumsum()])
        pla_cum = np.concatenate([[0], g["place_flag"].to_numpy(dtype=np.int64).cumsum()])
        spd_cum = np.concatenate([[0], g["Spend"].to_numpy(dtype=np.float64).cumsum()])
        pnl_cum = np.concatenate([[0], g["P&L"].to_numpy(dtype=np.float64).cumsum()])
        index[key] = (dates, win_cum, pla_cum, spd_cum, pnl_cum)

    for label in windows.keys():
        upcoming_fields[f"{label} Sts"] = 0
        upcoming_fields[f"{label} Win"] = 0
        upcoming_fields[f"{label} Pla"] = 0
        upcoming_fields[f"{label} Win %"] = 0.0
        upcoming_fields[f"{label} Pla %"] = 0.0
        upcoming_fields[f"{label} ROI %"] = 0.0

    for key, uf_idx in upcoming_fields.groupby("VDSG_BARRIER").groups.items():
        if key not in index:
            continue
        dates, win_cum, pla_cum, spd_cum, pnl_cum = index[key]

        row_dates = upcoming_fields.loc[uf_idx, "Date"].to_numpy(dtype="datetime64[ns]")
        end = np.searchsorted(dates, row_dates, side="left")

        for label, days in windows.items():
            if days is None:
                start = np.maximum(0, end - 100)
            else:
                if days <= 0:
                    start = np.zeros_like(end)
                else:
                    cutoff = row_dates - np.timedelta64(days, "D")
                    start = np.searchsorted(dates, cutoff, side="left")

            sts = (end - start).astype(np.int64)
            win = (win_cum[end] - win_cum[start]).astype(np.int64)
            pla = (pla_cum[end] - pla_cum[start]).astype(np.int64)
            spd = (spd_cum[end] - spd_cum[start]).astype(np.float64)
            pnl = (pnl_cum[end] - pnl_cum[start]).astype(np.float64)

            win_pct = np.where(sts > 0, np.round(win / sts * 100, 2), 0.0)
            pla_pct = np.where(sts > 0, np.round((win + pla) / sts * 100, 2), 0.0)
            roi_pct = np.where(spd > 0, np.round(pnl / spd * 100, 2), 0.0)

            upcoming_fields.loc[uf_idx, f"{label} Sts"] = sts
            upcoming_fields.loc[uf_idx, f"{label} Win"] = win
            upcoming_fields.loc[uf_idx, f"{label} Pla"] = pla
            upcoming_fields.loc[uf_idx, f"{label} Win %"] = win_pct
            upcoming_fields.loc[uf_idx, f"{label} Pla %"] = pla_pct
            upcoming_fields.loc[uf_idx, f"{label} ROI %"] = roi_pct

    # Drop helpers to keep the file clean (matches your current intent)
    upcoming_fields.drop(columns=["VDSG", "Barrier_str", "VDSG_BARRIER"], inplace=True, errors="ignore")

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with all barrier recent stats (FAST)")




def add_driver_stats():
    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False)

        merged_data["Spend"] = merged_data["Spend"].replace(r'[\$,]', '', regex=True)
        merged_data["P&L"] = merged_data["P&L"].replace('[\\$,]', '', regex=True)

        merged_data["Spend"] = pd.to_numeric(merged_data["Spend"], errors="coerce")
        merged_data["P&L"] = pd.to_numeric(merged_data["P&L"], errors="coerce")
        merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    merged_data["VenueDriver"] = merged_data["Venue"].str.lower().str.strip() + "_" + merged_data["Driver"].str.lower().str.strip()
    upcoming_fields["VenueDriver"] = upcoming_fields["Venue"].str.lower().str.strip() + "_" + upcoming_fields["Driver"].str.lower().str.strip()

    driver_stats = merged_data.groupby("VenueDriver").agg({
        "Driver": "count",
        "Placing": [
            lambda x: (x == 1).sum(),
            lambda x: ((x == 2) | (x == 3)).sum()
        ],
        "P&L": "sum",
        "Spend": "sum"
    })

    driver_stats.columns = ["Dr Sts", "Dr Win", "Dr Pla", "Dr P&L", "Dr Spend"]
    driver_stats = driver_stats.reset_index()

    upcoming_fields = upcoming_fields.merge(driver_stats, how="left", on="VenueDriver")

    upcoming_fields[["Dr Sts", "Dr Win", "Dr Pla", "Dr P&L", "Dr Spend"]] = upcoming_fields[
        ["Dr Sts", "Dr Win", "Dr Pla", "Dr P&L", "Dr Spend"]
    ].fillna(0)

    upcoming_fields["Dr Win%"] = upcoming_fields.apply(
        lambda row: round(row["Dr Win"] / row["Dr Sts"] * 100, 2) if row["Dr Sts"] > 0 else 0.0,
        axis=1
    )
    upcoming_fields["Dr Pla%"] = upcoming_fields.apply(
        lambda row: round((row["Dr Win"] + row["Dr Pla"]) / row["Dr Sts"] * 100, 2) if row["Dr Sts"] > 0 else 0.0,
        axis=1
    )
    upcoming_fields["Dr ROI%"] = upcoming_fields.apply(
        lambda row: round(row["Dr P&L"] / row["Dr Spend"] * 100, 2) if row["Dr Spend"] > 0 else 0.0,
        axis=1
    )

    upcoming_fields.drop(columns=["VenueDriver", "Dr P&L", "Dr Spend"], inplace=True)

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with driver stats")


def add_trainer_stats():
    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False)

        merged_data["Spend"] = merged_data["Spend"].replace(r'[\$,]', '', regex=True)
        merged_data["P&L"] = merged_data["P&L"].replace('[\\$,]', '', regex=True)

        merged_data["Spend"] = pd.to_numeric(merged_data["Spend"], errors="coerce")
        merged_data["P&L"] = pd.to_numeric(merged_data["P&L"], errors="coerce")
        merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    merged_data["VenueTrainer"] = merged_data["Venue"].str.lower().str.strip() + "_" + merged_data["Trainer"].str.lower().str.strip()
    upcoming_fields["VenueTrainer"] = upcoming_fields["Venue"].str.lower().str.strip() + "_" + upcoming_fields["Trainer"].str.lower().str.strip()

    trainer_stats = merged_data.groupby("VenueTrainer").agg({
        "Trainer": "count",
        "Placing": [
            lambda x: (x == 1).sum(),
            lambda x: ((x == 2) | (x == 3)).sum()
        ],
        "P&L": "sum",
        "Spend": "sum"
    })

    trainer_stats.columns = ["Tr Sts", "Tr Win", "Tr Pla", "Tr P&L", "Tr Spend"]
    trainer_stats = trainer_stats.reset_index()

    upcoming_fields = upcoming_fields.merge(trainer_stats, how="left", on="VenueTrainer")

    upcoming_fields[["Tr Sts", "Tr Win", "Tr Pla", "Tr P&L", "Tr Spend"]] = upcoming_fields[
        ["Tr Sts", "Tr Win", "Tr Pla", "Tr P&L", "Tr Spend"]
    ].fillna(0)

    upcoming_fields["Tr Win%"] = upcoming_fields.apply(
        lambda row: round(row["Tr Win"] / row["Tr Sts"] * 100, 2) if row["Tr Sts"] > 0 else 0.0,
        axis=1
    )
    upcoming_fields["Tr Pla%"] = upcoming_fields.apply(
        lambda row: round((row["Tr Win"] + row["Tr Pla"]) / row["Tr Sts"] * 100, 2) if row["Tr Sts"] > 0 else 0.0,
        axis=1
    )
    upcoming_fields["Tr ROI%"] = upcoming_fields.apply(
        lambda row: round(row["Tr P&L"] / row["Tr Spend"] * 100, 2) if row["Tr Spend"] > 0 else 0.0,
        axis=1
    )

    upcoming_fields.drop(columns=["VenueTrainer", "Tr P&L", "Tr Spend"], inplace=True)

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with trainer stats")


def add_trainer_recent_stats():
    import numpy as np
    import pandas as pd

    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    merged_data["Date"] = pd.to_datetime(merged_data["Date"], errors="coerce", dayfirst=True)
    upcoming_fields["Date"] = pd.to_datetime(upcoming_fields["Date"], errors="coerce")

    upcoming_fields["Trainer_clean"] = upcoming_fields["Trainer"].astype(str).str.strip().str.lower()
    merged_data["Trainer_clean"] = merged_data["Trainer"].astype(str).str.strip().str.lower()

    merged_data["Spend"] = (
        merged_data["Spend"].astype(str)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace(r"[\$,]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )
    merged_data["P&L"] = (
        merged_data["P&L"].astype(str)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace(r"[\$,]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )
    merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    windows = {
        "Tr 30": 30, "Tr 90": 90, "Tr 180": 180, "Tr 365": 365, "Tr All": 0, "Tr L/100": None
    }

    needed = set(upcoming_fields["Trainer_clean"].dropna().unique())
    md = merged_data[
        merged_data["Trainer_clean"].notna()
        & merged_data["Date"].notna()
        & merged_data["Trainer_clean"].isin(needed)
    ].copy()

    md["win_flag"] = (md["Placing"] == 1).astype(int)
    md["place_flag"] = ((md["Placing"] == 2) | (md["Placing"] == 3)).astype(int)
    md["Spend"] = md["Spend"].fillna(0.0)
    md["P&L"] = md["P&L"].fillna(0.0)

    md.sort_values(["Trainer_clean", "Date"], inplace=True)

    index = {}
    for trn, g in md.groupby("Trainer_clean", sort=False):
        dates = g["Date"].to_numpy(dtype="datetime64[ns]")
        win_cum = np.concatenate([[0], g["win_flag"].to_numpy(dtype=np.int64).cumsum()])
        pla_cum = np.concatenate([[0], g["place_flag"].to_numpy(dtype=np.int64).cumsum()])
        spd_cum = np.concatenate([[0], g["Spend"].to_numpy(dtype=np.float64).cumsum()])
        pnl_cum = np.concatenate([[0], g["P&L"].to_numpy(dtype=np.float64).cumsum()])
        index[trn] = (dates, win_cum, pla_cum, spd_cum, pnl_cum)

    for label in windows.keys():
        upcoming_fields[f"{label} Sts"] = 0
        upcoming_fields[f"{label} Win"] = 0
        upcoming_fields[f"{label} Pla"] = 0
        upcoming_fields[f"{label} Win %"] = 0.0
        upcoming_fields[f"{label} Pla %"] = 0.0
        upcoming_fields[f"{label} ROI %"] = 0.0

    for trn, uf_idx in upcoming_fields.groupby("Trainer_clean").groups.items():
        if trn not in index:
            continue
        dates, win_cum, pla_cum, spd_cum, pnl_cum = index[trn]

        row_dates = upcoming_fields.loc[uf_idx, "Date"].to_numpy(dtype="datetime64[ns]")
        end = np.searchsorted(dates, row_dates, side="left")

        for label, days in windows.items():
            if days is None:
                start = np.maximum(0, end - 100)
            else:
                if days <= 0:
                    start = np.zeros_like(end)
                else:
                    cutoff = row_dates - np.timedelta64(days, "D")
                    start = np.searchsorted(dates, cutoff, side="left")

            sts = (end - start).astype(np.int64)
            win = (win_cum[end] - win_cum[start]).astype(np.int64)
            pla = (pla_cum[end] - pla_cum[start]).astype(np.int64)
            spd = (spd_cum[end] - spd_cum[start]).astype(np.float64)
            pnl = (pnl_cum[end] - pnl_cum[start]).astype(np.float64)

            win_pct = np.where(sts > 0, np.round(win / sts * 100, 2), 0.0)
            pla_pct = np.where(sts > 0, np.round((win + pla) / sts * 100, 2), 0.0)
            roi_pct = np.where(spd > 0, np.round(pnl / spd * 100, 2), 0.0)

            upcoming_fields.loc[uf_idx, f"{label} Sts"] = sts
            upcoming_fields.loc[uf_idx, f"{label} Win"] = win
            upcoming_fields.loc[uf_idx, f"{label} Pla"] = pla
            upcoming_fields.loc[uf_idx, f"{label} Win %"] = win_pct
            upcoming_fields.loc[uf_idx, f"{label} Pla %"] = pla_pct
            upcoming_fields.loc[uf_idx, f"{label} ROI %"] = roi_pct

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with all trainer recent stats (FAST)")



def add_driver_recent_stats():
    import numpy as np
    import pandas as pd
    from datetime import timedelta

    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # -----------------------------
    # Parse dates
    # -----------------------------
    merged_data["Date"] = pd.to_datetime(merged_data["Date"], errors="coerce", dayfirst=True)
    upcoming_fields["Date"] = pd.to_datetime(upcoming_fields["Date"], errors="coerce")

    # -----------------------------
    # Clean key
    # -----------------------------
    upcoming_fields["Driver_clean"] = upcoming_fields["Driver"].astype(str).str.strip().str.lower()
    merged_data["Driver_clean"] = merged_data["Driver"].astype(str).str.strip().str.lower()

    # -----------------------------
    # Clean numeric fields
    # -----------------------------
    merged_data["Spend"] = (
        merged_data["Spend"].astype(str)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace(r"[\$,]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )
    merged_data["P&L"] = (
        merged_data["P&L"].astype(str)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace(r"[\$,]", "", regex=True)
        .replace("", np.nan)
        .astype(float)
    )
    merged_data["Placing"] = pd.to_numeric(merged_data["Placing"], errors="coerce")

    # -----------------------------
    # Fast engine: prefix sums per driver
    # -----------------------------
    windows = {
        "Dr 30": 30, "Dr 90": 90, "Dr 180": 180, "Dr 365": 365, "Dr All": 0, "Dr L/100": None
    }

    # Only build groups for drivers that actually appear in upcoming_fields
    needed = set(upcoming_fields["Driver_clean"].dropna().unique())
    md = merged_data[
        merged_data["Driver_clean"].notna()
        & merged_data["Date"].notna()
        & merged_data["Driver_clean"].isin(needed)
    ].copy()

    # Prepare flags & numeric-safe values
    md["win_flag"] = (md["Placing"] == 1).astype(int)
    md["place_flag"] = ((md["Placing"] == 2) | (md["Placing"] == 3)).astype(int)
    md["Spend"] = md["Spend"].fillna(0.0)
    md["P&L"] = md["P&L"].fillna(0.0)

    # Sort once
    md.sort_values(["Driver_clean", "Date"], inplace=True)

    # Build prefix sums dict: driver -> arrays
    index = {}
    for drv, g in md.groupby("Driver_clean", sort=False):
        dates = g["Date"].to_numpy(dtype="datetime64[ns]")
        # prefix sums with leading zero so slice sum is cum[end] - cum[start]
        win_cum = np.concatenate([[0], g["win_flag"].to_numpy(dtype=np.int64).cumsum()])
        pla_cum = np.concatenate([[0], g["place_flag"].to_numpy(dtype=np.int64).cumsum()])
        spd_cum = np.concatenate([[0], g["Spend"].to_numpy(dtype=np.float64).cumsum()])
        pnl_cum = np.concatenate([[0], g["P&L"].to_numpy(dtype=np.float64).cumsum()])
        index[drv] = (dates, win_cum, pla_cum, spd_cum, pnl_cum)

    # Allocate output columns
    for label in windows.keys():
        upcoming_fields[f"{label} Sts"] = 0
        upcoming_fields[f"{label} Win"] = 0
        upcoming_fields[f"{label} Pla"] = 0
        upcoming_fields[f"{label} Win %"] = 0.0
        upcoming_fields[f"{label} Pla %"] = 0.0
        upcoming_fields[f"{label} ROI %"] = 0.0

    # Compute per driver group (fast; no giant masks)
    for drv, uf_idx in upcoming_fields.groupby("Driver_clean").groups.items():
        if drv not in index:
            continue
        dates, win_cum, pla_cum, spd_cum, pnl_cum = index[drv]

        row_dates = upcoming_fields.loc[uf_idx, "Date"].to_numpy(dtype="datetime64[ns]")
        # end = count of prior runs strictly before row_date
        end = np.searchsorted(dates, row_dates, side="left")

        for label, days in windows.items():
            if days is None:
                start = np.maximum(0, end - 100)
            else:
                if days <= 0:
                    start = np.zeros_like(end)
                else:
                    cutoff = row_dates - np.timedelta64(days, "D")
                    start = np.searchsorted(dates, cutoff, side="left")

            sts = (end - start).astype(np.int64)
            win = (win_cum[end] - win_cum[start]).astype(np.int64)
            pla = (pla_cum[end] - pla_cum[start]).astype(np.int64)
            spd = (spd_cum[end] - spd_cum[start]).astype(np.float64)
            pnl = (pnl_cum[end] - pnl_cum[start]).astype(np.float64)

            win_pct = np.where(sts > 0, np.round(win / sts * 100, 2), 0.0)
            pla_pct = np.where(sts > 0, np.round((win + pla) / sts * 100, 2), 0.0)
            roi_pct = np.where(spd > 0, np.round(pnl / spd * 100, 2), 0.0)

            upcoming_fields.loc[uf_idx, f"{label} Sts"] = sts
            upcoming_fields.loc[uf_idx, f"{label} Win"] = win
            upcoming_fields.loc[uf_idx, f"{label} Pla"] = pla
            upcoming_fields.loc[uf_idx, f"{label} Win %"] = win_pct
            upcoming_fields.loc[uf_idx, f"{label} Pla %"] = pla_pct
            upcoming_fields.loc[uf_idx, f"{label} ROI %"] = roi_pct

    upcoming_fields.to_csv("upcoming_fields.csv", index=False)
    print("✅ Saved updated upcoming_fields.csv with all driver recent stats (FAST)")



def add_bell_position_stats():
    try:
        upcoming_fields = pd.read_csv("upcoming_fields.csv")
        merged_data = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # First pass: horse-level %s from BellPosition history
    upcoming_fields["Horse_clean"] = upcoming_fields["Horse"].astype(str).str.strip().str.lower()
    merged_data["Horse_clean"] = merged_data["Horse"].astype(str).str.strip().str.lower()
    merged_data["BellPosition"] = merged_data["BellPosition"].astype(str).str.strip().str.upper()

    total_starts = merged_data.groupby("Horse_clean").size()
    lead_counts = merged_data[merged_data["BellPosition"] == "LEAD"].groupby("Horse_clean").size()
    death_counts = merged_data[merged_data["BellPosition"] == "DEATH"].groupby("Horse_clean").size()
    bl_counts = merged_data[merged_data["BellPosition"] == "B/LEAD"].groupby("Horse_clean").size()

    bell_stats = pd.DataFrame({
        "Total Starts": total_starts,
        "LEAD": lead_counts,
        "DEATH": death_counts,
        "B/LEAD": bl_counts
    }).fillna(0)

    bell_stats["Ld %"] = round(bell_stats["LEAD"] / bell_stats["Total Starts"] * 100, 1)
    bell_stats["Dth %"] = round(bell_stats["DEATH"] / bell_stats["Total Starts"] * 100, 1)
    bell_stats["BL %"] = round(bell_stats["B/LEAD"] / bell_stats["Total Starts"] * 100, 1)

    upcoming_fields = upcoming_fields.merge(
        bell_stats[["Ld %", "Dth %", "BL %"]],
        how="left",
        left_on="Horse_clean",
        right_index=True
    )
    upcoming_fields[["Ld %", "Dth %", "BL %"]] = upcoming_fields[["Ld %", "Dth %", "BL %"]].fillna(0)
    upcoming_fields.drop(columns=["Horse_clean"], inplace=True)

    # Second pass: horse-specific ROI splits by BellPosition (optional block retained)
    upcoming = upcoming_fields
    merged = pd.read_csv("merged_file.csv", low_memory=False)
    for col in ["Horse", "BellPosition", "Spend", "P&L"]:
        if col not in merged.columns:
            raise ValueError(f"Missing column in merged_file.csv: {col}")

    merged["Spend"] = pd.to_numeric(merged["Spend"], errors="coerce")
    merged["P&L"] = pd.to_numeric(merged["P&L"], errors="coerce")

    def get_bell_stats(horse_name):
        horse_data = merged[merged["Horse"] == horse_name]
        bell_data = horse_data[horse_data["BellPosition"].notna()]
        total_sts = len(bell_data)

        def stats_for(position):
            subset = bell_data[bell_data["BellPosition"] == position]
            count = len(subset)
            pct = count / total_sts * 100 if total_sts > 0 else 0
            roi = subset["P&L"].sum() / subset["Spend"].sum() * 100 if subset["Spend"].sum() > 0 else 0
            return count, round(pct, 1), round(roi, 1)

        lead_count, lead_pct, lead_roi = stats_for("LEAD")
        bl_count, bl_pct, bl_roi = stats_for("B/LEAD")
        dth_count, dth_pct, dth_roi = stats_for("DEATH")

        return pd.Series([
            total_sts,
            lead_count, lead_pct, lead_roi,
            bl_count, bl_pct, bl_roi,
            dth_count, dth_pct, dth_roi
        ])

    upcoming[[
        "Bell Pos Sts",
        "Bell Pos Lead", "Bell Pos Lead %", "Bell Pos Lead ROI %",
        "Bell Pos BL", "Bell Pos BL %", "Bell Pos BL ROI %",
        "Bell Pos Dth", "Bell Pos Dth %", "Bell Pos Dth ROI %"
    ]] = upcoming["Horse"].apply(get_bell_stats)

    upcoming.to_csv("upcoming_fields.csv", index=False)
    try:
        upcoming.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("✅ Horse-specific Bell stats added to upcoming_fields.csv")


def compress_odds(
    raw_odds: float,
    min_odds: float = 1.8,
    max_odds: float = 120.0,
    power: float = 0.85,
):
    import math

    if raw_odds is None or raw_odds <= 0 or math.isnan(raw_odds) or math.isinf(raw_odds):
        return max_odds

    # soften extremes
    compressed = raw_odds ** power

    # clamp
    compressed = max(min_odds, min(max_odds, compressed))

    # nice rounding
    if compressed < 10:
        return round(compressed, 2)
    elif compressed < 50:
        return round(compressed, 1)
    else:
        return round(compressed)



# --- NEW: AEST + Horse Qty -----------------------------------------------

_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([ap]m)\s*$", re.IGNORECASE)

def _time_str_to_minutes(t: str) -> int | None:
    """Convert 'h:mmam/pm' to minutes [0..1439], or None if unparsable."""
    if not isinstance(t, str):
        return None
    m = _TIME_RE.match(t)
    if not m:
        return None
    hh = int(m.group(1))
    mm = int(m.group(2))
    ap = m.group(3).lower()
    if hh == 12:
        hh = 0
    if ap == "pm":
        hh += 12
    return hh * 60 + mm

def _minutes_to_time_str(total: int) -> str:
    """Return 'h:mm AM/PM' to match the Time column format."""
    total = total % (24 * 60)
    hh = total // 60
    mm = total % 60
    ap = "AM" if hh < 12 else "PM"
    h12 = hh % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{mm:02d} {ap}"

def add_aest_and_horse_qty():
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        merged = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # --- AEST column ---
    # Offsets in minutes (AEST relative to local state time)
    state_offset_min = {
        "WA": 180,   # +2 hours
        "SA": 30,    # +0.5 hours
        "QLD": 60     # +0 hours (placeholder for future DST logic)
        # Others default to 0
    }

    def compute_aest(row):
        tmin = _time_str_to_minutes(str(row.get("Time", "")).strip())
        if tmin is None:
            return row.get("Time", "")
        st = str(row.get("State", "")).strip().upper()
        offset = state_offset_min.get(st, 0)
        return _minutes_to_time_str(tmin + offset)

    uf["AEST"] = uf.apply(compute_aest, axis=1)

    # --- Horse Qty column ---
    # Normalise horse names using same cleaner, then count in merged_file
    merged["Horse"] = merged["Horse"].astype(str).fillna("")
    merged["Horse_clean_key"] = merged["Horse"].map(clean_horse_name).str.strip().str.lower()
    horse_counts = merged["Horse_clean_key"].value_counts()

    uf["Horse"] = uf["Horse"].astype(str).fillna("")
    uf["Horse_clean_key"] = uf["Horse"].map(clean_horse_name).str.strip().str.lower()
    uf["Horse Qty"] = uf["Horse_clean_key"].map(horse_counts).fillna(0).astype(int)
    uf.drop(columns=["Horse_clean_key"], inplace=True, errors="ignore")

    uf.to_csv("upcoming_fields.csv", index=False)
    print("✅ Added AEST and Horse Qty to upcoming_fields.csv")


# --- NEW: Bell-position WIN/PLA counts per horse --------------------------
def add_bell_position_win_pla_counts():
    """
    Adds six columns to upcoming_fields.csv:
      - Ld Win, Ld Pla, BL Win, BL Pla, Dth Win, Dth Pla

    Logic:
      - Match upcoming_fields.Horse to merged_file.Horse (using the same cleaner)
      - Filter merged_file by BellPosition in {"LEAD","B/LEAD","DEATH"}
      - Count wins (Placing==1) and placings (Placing in {2,3}) per BellPosition
      - Merge counts back to upcoming_fields by cleaned horse key
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # Normalise horse keys
    uf["Horse"] = uf["Horse"].astype(str).fillna("")
    uf["Horse_clean_key"] = uf["Horse"].map(clean_horse_name).str.strip().str.lower()

    mf["Horse"] = mf["Horse"].astype(str).fillna("")
    mf["Horse_clean_key"] = mf["Horse"].map(clean_horse_name).str.strip().str.lower()

    # Normalise BellPosition + Placing
    if "BellPosition" not in mf.columns:
        print("⚠️ 'BellPosition' not found in merged_file.csv; skipping add_bell_position_win_pla_counts()")
        return

    mf["BellPosition"] = mf["BellPosition"].astype(str).str.strip().str.upper()
    mf["Placing"] = pd.to_numeric(mf.get("Placing", pd.Series(dtype=float)), errors="coerce")

    # Build wins and placings indicators
    mf["is_win"] = (mf["Placing"] == 1).astype(int)
    mf["is_pla"] = ((mf["Placing"] == 2) | (mf["Placing"] == 3)).astype(int)

    # Group by horse + bell position
    grp = mf.groupby(["Horse_clean_key", "BellPosition"], as_index=False)[["is_win", "is_pla"]].sum()

    # Pivot to have one row per horse, columns per BellPosition
    wins_pivot = grp.pivot(index="Horse_clean_key", columns="BellPosition", values="is_win").fillna(0).astype(int)
    pla_pivot  = grp.pivot(index="Horse_clean_key", columns="BellPosition", values="is_pla").fillna(0).astype(int)

    # Build a compact DataFrame with our six outputs; if a column is missing, default to 0
    out = pd.DataFrame(index=wins_pivot.index.union(pla_pivot.index))

    def col_or_zero(pvt, col):
        return pvt[col] if col in pvt.columns else 0

    out["Ld Win"]  = col_or_zero(wins_pivot, "LEAD")
    out["Ld Pla"]  = col_or_zero(pla_pivot,  "LEAD")
    out["BL Win"]  = col_or_zero(wins_pivot, "B/LEAD")
    out["BL Pla"]  = col_or_zero(pla_pivot,  "B/LEAD")
    out["Dth Win"] = col_or_zero(wins_pivot, "DEATH")
    out["Dth Pla"] = col_or_zero(pla_pivot,  "DEATH")

    # Merge back to uf on cleaned key
    uf = uf.merge(out, how="left", left_on="Horse_clean_key", right_index=True)

    # Fill NA with zeros and cast to int
    for c in ["Ld Win", "Ld Pla", "BL Win", "BL Pla", "Dth Win", "Dth Pla"]:
        if c in uf.columns:
            uf[c] = uf[c].fillna(0).astype(int)

    # Tidy
    uf.drop(columns=["Horse_clean_key"], inplace=True, errors="ignore")

    # Save
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added Ld/BL/Dth Win/Pla counts to upcoming_fields.csv")



def add_horse_win_place_counts():
    """
    Adds two columns to upcoming_fields.csv:
      - Horse W : number of wins (Placing == 1)
      - Horse P : number of placings (Placing in {2,3})

    Logic:
      - Normalise horse names using clean_horse_name()
      - Count occurrences in merged_file.csv by horse
      - Merge back to upcoming_fields
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # --- Normalise horse names ---
    uf["Horse"] = uf["Horse"].astype(str).fillna("")
    uf["Horse_clean_key"] = uf["Horse"].map(clean_horse_name).str.strip().str.lower()

    mf["Horse"] = mf["Horse"].astype(str).fillna("")
    mf["Horse_clean_key"] = mf["Horse"].map(clean_horse_name).str.strip().str.lower()

    # --- Normalise Placing ---
    mf["Placing"] = pd.to_numeric(mf.get("Placing", pd.Series(dtype=float)), errors="coerce")

    # --- Build counts ---
    horse_wins = mf[mf["Placing"] == 1].groupby("Horse_clean_key").size()
    horse_places = mf[mf["Placing"].isin([2, 3])].groupby("Horse_clean_key").size()

    stats = pd.DataFrame({
        "Horse W": horse_wins,
        "Horse P": horse_places
    }).fillna(0).astype(int)

    # --- Merge back ---
    uf = uf.merge(stats, how="left", left_on="Horse_clean_key", right_index=True)

    # Fill missing values with 0
    uf["Horse W"] = uf["Horse W"].fillna(0).astype(int)
    uf["Horse P"] = uf["Horse P"].fillna(0).astype(int)

    # Clean up helper col
    uf.drop(columns=["Horse_clean_key"], inplace=True, errors="ignore")

    # Save
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added Horse W and Horse P counts to upcoming_fields.csv")



# --------------------------------------------------------------------------

def parse_meeting(code, ven_dist_counts):
    url = BASE_URL + code
    res = http_get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    venue = "Unknown"
    date = datetime.strptime(code[-6:], "%d%m%y").strftime("%Y-%m-%d")
    session = ""

    header_tag = soup.find("h2")
    if header_tag:
        raw_header = header_tag.get_text()
        header_text = " ".join(raw_header.split())
        try:
            venue_part, date_part = header_text.split(" - ", 1)
            venue_match = re.search(r"^(.*?)\s*\((Day|Night|Twilight)\)", venue_part.strip())
            if venue_match:
                venue = venue_match.group(1).strip()
                venue = re.sub(r",\s*[A-Z]{2,3}$", "", venue)
                venue = re.sub(r"[\n\r\t]+", " ", venue).strip()
                session = venue_match.group(2).strip()
            else:
                venue = venue_part.strip()
            date = datetime.strptime(date_part.strip(), "%A, %d %b %Y").strftime("%Y-%m-%d")
        except Exception:
            return []

    state = state_map.get(code[:2], "")
    rows = []

    race_divs = soup.find_all("div", id=re.compile(r"race\d+"))
    for race_div in race_divs:
        race_id_match = re.search(r"race(\d+)", race_div.get("id", ""))
        race_num = race_id_match.group(1) if race_id_match else None

        more_info = race_div.find("table", class_="raceMoreInfo")
        if not more_info:
            continue

        if DEBUG_HTML:
            print(f"[{code} | Race {race_num}] DEBUG race_div:\n{race_div.prettify()}")

        header_text = more_info.get_text(" ", strip=True)

        race_header = race_div.find("table", class_="raceHeader")
        race_time_tag = race_header.find("td", class_="raceTime") if race_header else None
        race_time = race_time_tag.text.strip() if race_time_tag else ""

        # fallback scan for time
        for td in more_info.find_all("td"):
            td_classes = " ".join(td.get("class", []))
            if "raceTime" in td_classes and re.search(r"\d{1,2}:\d{2}[ap]m", td.text.strip()):
                race_time = td.text.strip()
                break

        # distance
        distance_tag = more_info.find("td", class_=re.compile(r"distance"))
        distance = re.search(r"(\d{4})", distance_tag.text.strip()).group(1) if distance_tag else ""

        # prizemoney
        prizemoney = ""
        prize_tag = race_div.find("td", class_="cPrize")
        if prize_tag:
            strong = prize_tag.find("strong")
            if strong:
                raw_prizemoney = strong.get_text(strip=True)
                digits_only = re.sub(r"[^\d]", "", raw_prizemoney)
                if digits_only.isdigit():
                    prizemoney = f"${int(digits_only):,}"
        # skip trials
        if prizemoney == "$0":
            continue

        # gait
        gait = ""
        info_tag = more_info.find("td", class_="cPrize") if more_info else None
        if info_tag:
            info_text = info_tag.get_text(" ", strip=True).upper()
            match = re.search(r'\b(TROTTERS|PACERS)\b', info_text)
            if match:
                gait = match.group(1)
        # override by race name if needed
        race_header = race_div.find("table", class_="raceHeader")
        race_title_tag = race_header.find("td", class_="raceTitle") if race_header else None
        race_name = race_title_tag.get_text(strip=True) if race_title_tag else f"Race {race_num}"
        if "TROT" in race_name.upper() or "TROTTERS" in race_name.upper():
            gait = "TROTTERS"
        else:
            gait = "PACERS" if gait == "" else gait

        # start
        start = "Mobile" if "MOBILE" in header_text.upper() else ("Stand" if "STANDING" in header_text.upper() else "")

        # VenDist Sample (now that distance is known)
        ven_dist_key = f"{venue}_{distance}"
        ven_dist_sample_count = int(ven_dist_counts.get(ven_dist_key, 0))


        # race-level row (kept as in your original)
        rows.append({
            "Race Anchor": f"{code}_R{race_num}",
            "Venue": venue,
            "Date": date,
            "MeetingTime": session,
            "Race No": race_num,
            "Time": race_time,
            "State": state,
            "VenDist Sample": ven_dist_sample_count
        })

        # runners
        runner_table = more_info.find_next_sibling("table")
        if not runner_table:
            continue

        for tr in runner_table.find_all("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue

            horse_no = tds[0].text.strip()
            horse_raw = tds[2].text.strip()
            horse = clean_horse_name(horse_raw)

            if "CONNIES PRESIDENT" in horse_raw:
                print("DEBUG horse name")
                print(f"  raw   = [{horse_raw}]")
                print(f"  clean = [{horse}]")


            if not horse.strip():
                continue

            trainer = tds[3].text.strip()
            driver = tds[5].text.strip()
            # remove driver suffix like (C), (C,cl), (C,5)
            driver = re.sub(r"\s?\(C(?:,.*)?\)", "", driver).strip()

            barrier = tds[-1].text.strip()

            race_anchor = code
            race_anchor_full = f"{race_anchor}_R{race_num}"
            runner_anchor = f"{race_anchor}_R{race_num}_{horse}"


            # --- DEBUG: confirm what we're about to write ---
            if "CONNIES PRESIDENT" in horse_raw or "CONNIES PRESIDENT" in horse:
                print("DEBUG about to write row")
                print(f"  horse_raw     = [{horse_raw}]")
                print(f"  horse_clean   = [{horse}]")
                print(f"  runner_anchor = [{runner_anchor}]")
                print(f"  race_anchor   = [{race_anchor}]  race_no={race_num}")


            rows.append({
                "Race Anchor": race_anchor,
                "Venue": venue,
                "Date": date,
                "MeetingTime": session,
                "Race No": race_num,
                "Time": race_time,
                "Horse No": horse_no,
                "Horse": horse,
                "Race Name": race_name,
                "Distance": distance,
                "Prizemoney": prizemoney,
                "Barrier": barrier,
                "Trainer": trainer,
                "Driver": driver,
                "RaceAnchorFull": race_anchor_full,
                "RunnerAnchor": runner_anchor,
                "Gait": gait,
                "Start": start,
                "State": state
            })

    return rows


def add_lead_summary_columns():
    """
    Adds 36 columns to upcoming_fields.csv, summarising BellPosition outcomes
    (counts + ROI %) at three levels (VDSG, Venue, All) for each of:
      - LEAD  (prefix 'Lead')
      - B/LEAD (prefix 'BL')
      - DEATH (prefix 'Dth')

    Per position (e.g. Lead) the columns are:
      VDSG Lead All / W / P / ROI %
      Venue Lead All / W / P / ROI %
      All Lead All / W / P / ROI %
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # --- Normalise keys on both dataframes (matches your other helpers) ---
    for df in (uf, mf):
        df["VDSG"] = (
            df["Venue"].astype(str).str.lower().str.strip() + "_" +
            df["Distance"].astype(str).str.strip() + "_" +
            df["Gait"].astype(str).str.lower().str.strip() + "_" +
            df["Start"].astype(str).str.lower().str.strip()
        )
        df["Venue_norm"] = df["Venue"].astype(str).str.lower().str.strip()

    # --- Normalise fields used for filters/calcs on merged_file ---
    mf["BellPosition"] = mf.get("BellPosition", "").astype(str).str.strip().str.upper()
    # Clean 'Spend' and 'P&L' to numeric (strip $, commas, "#DIV/0!", blanks)
    for col in ["Spend", "P&L"]:
        mf[col] = (
            mf.get(col, pd.Series(dtype=object))
              .astype(str)
              .str.replace("#DIV/0!", "", regex=False)
              .str.replace(r"[\$,]", "", regex=True)
              .replace({"": np.nan})
        )
        mf[col] = pd.to_numeric(mf[col], errors="coerce")
    mf["Placing"] = pd.to_numeric(mf.get("Placing", pd.Series(dtype=float)), errors="coerce")

    # ---- Helper to calculate counts + ROI for a given BellPosition ----
    def build_summary(pos: str, prefix: str):
        subset = mf[mf["BellPosition"] == pos].copy()
        if subset.empty:
            # If no rows, create zero columns directly
            uf[f"VDSG {prefix} All"] = 0
            uf[f"VDSG {prefix} W"] = 0
            uf[f"VDSG {prefix} P"] = 0
            uf[f"VDSG {prefix} ROI %"] = 0.0

            uf[f"Venue {prefix} All"] = 0
            uf[f"Venue {prefix} W"] = 0
            uf[f"Venue {prefix} P"] = 0
            uf[f"Venue {prefix} ROI %"] = 0.0

            uf[f"All {prefix} All"] = 0
            uf[f"All {prefix} W"] = 0
            uf[f"All {prefix} P"] = 0
            uf[f"All {prefix} ROI %"] = 0.0
            return

        subset["is_win"] = (subset["Placing"] == 1).astype(int)
        subset["is_pla"] = (subset["Placing"].isin([2, 3])).astype(int)

        # --- By VDSG ---
        g_vdsg = subset.groupby("VDSG").agg(
            all_cnt=("BellPosition", "size"),
            w_cnt=("is_win", "sum"),
            p_cnt=("is_pla", "sum"),
            pnl_sum=("P&L", "sum"),
            spend_sum=("Spend", "sum"),
        )
        # ROI safe division
        g_vdsg["roi_pct"] = np.where(
            g_vdsg["spend_sum"] > 0,
            (g_vdsg["pnl_sum"] / g_vdsg["spend_sum"]) * 100.0,
            0.0
        )

        # --- By Venue ---
        g_venue = subset.groupby("Venue_norm").agg(
            all_cnt=("BellPosition", "size"),
            w_cnt=("is_win", "sum"),
            p_cnt=("is_pla", "sum"),
            pnl_sum=("P&L", "sum"),
            spend_sum=("Spend", "sum"),
        )
        g_venue["roi_pct"] = np.where(
            g_venue["spend_sum"] > 0,
            (g_venue["pnl_sum"] / g_venue["spend_sum"]) * 100.0,
            0.0
        )

        # --- Global (All) ---
        all_all = int(len(subset))
        all_w   = int(subset["is_win"].sum())
        all_p   = int(subset["is_pla"].sum())
        all_pnl = float(subset["P&L"].sum(skipna=True))
        all_spd = float(subset["Spend"].sum(skipna=True))
        all_roi = (all_pnl / all_spd * 100.0) if all_spd > 0 else 0.0

        # --- Map to uf (fill with zeros, ROI rounded to 2dp) ---
        uf[f"VDSG {prefix} All"] = uf["VDSG"].map(g_vdsg["all_cnt"]).fillna(0).astype(int)
        uf[f"VDSG {prefix} W"]   = uf["VDSG"].map(g_vdsg["w_cnt"]).fillna(0).astype(int)
        uf[f"VDSG {prefix} P"]   = uf["VDSG"].map(g_vdsg["p_cnt"]).fillna(0).astype(int)
        uf[f"VDSG {prefix} ROI %"] = uf["VDSG"].map(g_vdsg["roi_pct"]).fillna(0.0).round(2)

        uf[f"Venue {prefix} All"] = uf["Venue_norm"].map(g_venue["all_cnt"]).fillna(0).astype(int)
        uf[f"Venue {prefix} W"]   = uf["Venue_norm"].map(g_venue["w_cnt"]).fillna(0).astype(int)
        uf[f"Venue {prefix} P"]   = uf["Venue_norm"].map(g_venue["p_cnt"]).fillna(0).astype(int)
        uf[f"Venue {prefix} ROI %"] = uf["Venue_norm"].map(g_venue["roi_pct"]).fillna(0.0).round(2)

        uf[f"All {prefix} All"] = all_all
        uf[f"All {prefix} W"]   = all_w
        uf[f"All {prefix} P"]   = all_p
        uf[f"All {prefix} ROI %"] = round(all_roi, 2)

    # Build for each BellPosition bucket
    build_summary("LEAD", "Lead")
    build_summary("B/LEAD", "BL")
    build_summary("DEATH", "Dth")

    # Clean up helper columns
    uf.drop(columns=["VDSG", "Venue_norm"], inplace=True, errors="ignore")

    # Save results
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("✅ Added counts + ROI % for Lead / BL / Dth at VDSG, Venue, and All levels")


def add_venue_level_stats():
    """
    Adds the following venue-scoped columns to upcoming_fields.csv:

    Horse:
      - Venue Horse Sts, Venue Horse W, Venue Horse WSR, Venue Horse P, Venue Horse PSR, Venue Horse ROI %
    Trainer:
      - Venue Trainer Sts, Venue Trainer W, Venue Trainer WSR, Venue Trainer P, Venue Trainer PSR, Venue Trainer ROI %
    Driver:
      - Venue Driver Sts, Venue Driver W, Venue Driver WSR, Venue Driver P, Venue Driver PSR, Venue Driver ROI %

    Definitions (scoped to merged_file rows where Venue == [row.Venue] AND entity == current row entity):
      Sts = count rows
      W   = count rows with Placing == 1
      P   = count rows with Placing in {2,3}
      WSR = (W / Sts) * 100
      PSR = ((W + P) / Sts) * 100
      ROI % = (sum(P&L) / sum(Spend)) * 100
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # ---- Normalise keys (match your existing conventions) ----
    uf["Venue_norm"]    = uf["Venue"].astype(str).str.strip().str.lower()
    uf["Horse_norm"]    = uf["Horse"].astype(str).fillna("").map(clean_horse_name).str.strip().str.lower()
    uf["Trainer_norm"]  = uf["Trainer"].astype(str).fillna("").str.strip().str.lower()
    uf["Driver_norm"]   = uf["Driver"].astype(str).fillna("").str.strip().str.lower()

    mf["Venue_norm"]    = mf["Venue"].astype(str).str.strip().str.lower()
    mf["Horse_norm"]    = mf["Horse"].astype(str).fillna("").map(clean_horse_name).str.strip().str.lower()
    mf["Trainer_norm"]  = mf["Trainer"].astype(str).fillna("").str.strip().str.lower()
    mf["Driver_norm"]   = mf["Driver"].astype(str).fillna("").str.strip().str.lower()

    # Numerics
    mf["Placing"] = pd.to_numeric(mf.get("Placing", pd.Series(dtype=float)), errors="coerce")
    for col in ["Spend", "P&L"]:
        mf[col] = (
            mf.get(col, pd.Series(dtype=object))
              .astype(str)
              .str.replace("#DIV/0!", "", regex=False)
              .str.replace(r"[\$,]", "", regex=True)
              .replace({"": np.nan})
        )
        mf[col] = pd.to_numeric(mf[col], errors="coerce")

    # Helper flags
    mf["is_win"] = (mf["Placing"] == 1).astype(int)
    mf["is_pla"] = (mf["Placing"].isin([2, 3])).astype(int)

    def _build_and_merge(entity: str, out_prefix: str):
        """
        entity in {"Horse_norm","Trainer_norm","Driver_norm"}
        Produces columns:
          [out_prefix] Sts, [out_prefix] W, [out_prefix] WSR, [out_prefix] P, [out_prefix] PSR, [out_prefix] ROI %
        """
        key = f"VK_{entity}"
        uf[key] = uf["Venue_norm"] + "|" + uf[entity]
        mf[key] = mf["Venue_norm"] + "|" + mf[entity]

        grp = mf.groupby(key).agg(
            Sts=("Placing", "size"),
            W=("is_win", "sum"),
            P=("is_pla", "sum"),
            pnl_sum=("P&L", "sum"),
            spend_sum=("Spend", "sum"),
        ).reset_index()

        # Rates and ROI (safe division)
        grp["WSR"] = np.where(grp["Sts"] > 0, (grp["W"] / grp["Sts"]) * 100.0, 0.0)
        grp["PSR"] = np.where(grp["Sts"] > 0, ((grp["W"] + grp["P"]) / grp["Sts"]) * 100.0, 0.0)
        grp["ROI %"] = np.where(grp["spend_sum"] > 0, (grp["pnl_sum"] / grp["spend_sum"]) * 100.0, 0.0)

        # Select & round/fill
        out = grp[[key, "Sts", "W", "WSR", "P", "PSR", "ROI %"]].copy()
        out["WSR"] = out["WSR"].round(2)
        out["PSR"] = out["PSR"].round(2)
        out["ROI %"] = out["ROI %"].round(2)

        # Merge to uf
        uf_merge = uf.merge(out, how="left", on=key, suffixes=("", "_calc"))
        # Rename to requested labels
        uf_merge.rename(columns={
            "Sts": f"{out_prefix} Sts",
            "W": f"{out_prefix} W",
            "WSR": f"{out_prefix} WSR",
            "P": f"{out_prefix} P",
            "PSR": f"{out_prefix} PSR",
            "ROI %": f"{out_prefix} ROI %",
        }, inplace=True)

        # Fill NaNs with 0, cast counts to int
        for c in [f"{out_prefix} Sts", f"{out_prefix} W", f"{out_prefix} P"]:
            if c in uf_merge.columns:
                uf_merge[c] = uf_merge[c].fillna(0).astype(int)
        for c in [f"{out_prefix} WSR", f"{out_prefix} PSR", f"{out_prefix} ROI %"]:
            if c in uf_merge.columns:
                uf_merge[c] = uf_merge[c].fillna(0.0)

        # Drop temp key col before returning
        uf_merge.drop(columns=[key], inplace=True, errors="ignore")
        return uf_merge

    # Build for each entity type
    uf = _build_and_merge("Horse_norm",   "Venue Horse")
    uf = _build_and_merge("Trainer_norm", "Venue Trainer")
    uf = _build_and_merge("Driver_norm",  "Venue Driver")

    # Tidy helper cols
    uf.drop(columns=["Venue_norm", "Horse_norm", "Trainer_norm", "Driver_norm"], inplace=True, errors="ignore")

    # Save
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added Venue-level Horse/Trainer/Driver stats (Sts, W, WSR, P, PSR, ROI %) to upcoming_fields.csv")


def add_exp_half(use_adj: bool = True):
    """
    Adds 'Exp Half' to upcoming_fields.csv.

    If use_adj=True → uses 'AdjIndHalf' from merged_file.csv
    Else → uses 'Ind Half'

    Logic:
    - For each upcoming runner, take the mean of prior 6 months' values (strictly before race date),
      restricted to [50, 70].
    - If none available → 60
    - Round to 2 dp
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    uf["Date"] = pd.to_datetime(uf.get("Date"), errors="coerce")
    mf["Date"] = pd.to_datetime(mf.get("Date"), errors="coerce", dayfirst=True)

 

    # Prefer ACTUAL performance-based half metrics (not "Expected..." columns)
    perf_priority = ["RatingIndHalf", "AdjIndHalf", "Ind Half"]
    col = next((c for c in perf_priority if c in mf.columns), None)

    if col is None:
        print("⚠️ None of RatingIndHalf / AdjIndHalf / Ind Half found in merged_file.csv — setting Exp Half = 60")
        uf["Exp Half"] = 60.0
        uf.to_csv("upcoming_fields.csv", index=False)
        try:
            uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
        except Exception:
            pass
        return




    if col not in mf.columns:
        print(f"⚠️ '{col}' not found in merged_file.csv — setting Exp Half = 60")
        uf["Exp Half"] = 60.0
        uf.to_csv("upcoming_fields.csv", index=False)
        return

    # Normalise horse key
    uf["Horse_key"] = uf["Horse"].astype(str).map(clean_horse_name).str.lower()
    mf["Horse_key"] = mf["Horse"].astype(str).map(clean_horse_name).str.lower()

    mf[col] = pd.to_numeric(mf[col], errors="coerce")
    mf = mf[(mf[col].notna()) & (mf[col] >= 50) & (mf[col] <= 70)]

    mf_by_horse = {
        hk: g.dropna(subset=["Date"]).sort_values("Date")[["Date", col]].reset_index(drop=True)
        for hk, g in mf.groupby("Horse_key")
    }
    mf_max_date = mf["Date"].max()

    def _exp_half_for_row(row):
        hk = row["Horse_key"]
        ref_date = row["Date"] if pd.notna(row["Date"]) else mf_max_date
        if hk not in mf_by_horse or pd.isna(ref_date):
            return 60.0
        g = mf_by_horse[hk]
        window = g[(g["Date"] >= ref_date - pd.DateOffset(months=6)) & (g["Date"] < ref_date)][col]
        if window.empty:
            return 60.0
        m = window.mean()
        return round(m if pd.notna(m) and m != 0 else 60.0, 2)

    print(f"➡️ Calculating Exp Half using {col} …")
    uf["Exp Half"] = uf.apply(_exp_half_for_row, axis=1)

    uf.drop(
        columns=["Horse_key", "_LR_Date_dt", "_RaceDate_dt"],
        inplace=True,
        errors="ignore",
    )

    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added/updated 'Exp Half' in upcoming_fields.csv")



def add_rating():
    """
    Adds per-race ratings to upcoming_fields.csv.

    Rating logic (per race):
      - Use the smallest (fastest) half-time as the reference.
      - Fastest gets 100.
      - Others: rating = 100 - 13 * (half_time - best_half_time)
      - NaN values become 0
      - Rounded to nearest integer

    Source column priority:
      1) ModelEffectiveIndHalf   (preferred)
      2) Ind Half
      3) Exp Half
    Also writes:
      - ModelRating (same as Rating, but kept as a stable "preferred" column)
    """
    try:
        import pandas as _pd  # avoids any accidental local 'pd' shadowing
        uf = _pd.read_csv("upcoming_fields.csv")
    except Exception as e:
        print(f"⚠️ Failed to read upcoming_fields.csv: {e}")
        return

    # ---- choose source column ----
    if "ModelEffectiveIndHalf" in uf.columns:
        source_col = "ModelEffectiveIndHalf"
    elif "Ind Half" in uf.columns:
        source_col = "Ind Half"
    elif "Exp Half" in uf.columns:
        source_col = "Exp Half"
    else:
        print("⚠️ No 'ModelEffectiveIndHalf', 'Ind Half', or 'Exp Half' found; skipping add_rating()")
        return

    # ---- race key ----
    race_key = "RaceAnchorFull" if "RaceAnchorFull" in uf.columns else (
        "Race Anchor" if "Race Anchor" in uf.columns else None
    )
    if race_key is None:
        print("⚠️ No race key column ('RaceAnchorFull' or 'Race Anchor') found; skipping add_rating()")
        return

    # ---- ensure numeric ----
    uf[source_col] = (
        uf[source_col]
        .astype(str)
        .str.replace("#DIV/0!", "", regex=False)
        .str.replace(r"[^\d\.\-]", "", regex=True)
        .replace({"": np.nan})
    )
    uf[source_col] = pd.to_numeric(uf[source_col], errors="coerce")

    def _rate_group(g: pd.DataFrame) -> pd.Series:
        vals = pd.to_numeric(g[source_col], errors="coerce")
        best = vals.min(skipna=True)
        if pd.isna(best):
            return pd.Series([0] * len(g), index=g.index, dtype=int)

        rating = 100 - 13 * (vals - best)
        rating = rating.fillna(0)

        # Optional: clip extreme negatives (keeps things sane)
        rating = rating.clip(lower=0)

        return rating.round().astype(int)

    print(f"➡️ Calculating Rating from '{source_col}' (fastest in race = 100)…")
    uf["Rating"] = uf.groupby(race_key, group_keys=False).apply(_rate_group)

    # Keep a dedicated preferred column for the market step
    uf["ModelRating"] = uf["Rating"]

    # Save
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("✅ Added 'Rating' and 'ModelRating' to upcoming_fields.csv")



def _pct(s: pd.Series) -> pd.Series:
    # robust percentile: rank/len with ties handled
    n = len(s)
    if n <= 1:
        return pd.Series([0.5] * n, index=s.index, dtype=float)
    ranks = s.rank(method="average", na_option="keep")
    return ((ranks - 1) / (n - 1)).astype(float)



def add_market_from_rating(
    uf: pd.DataFrame,
    method: str = "exp",
    beta: float = 2.0,
    target_book_pct: float = 125.0,          # 100 = true probs, 125 = overround book
    use_compressed_odds: bool = True,        # True => use compress_odds() for Fair Odds
) -> None:
    """
    Build a within-race "fair market" from a rating-like column.

    Outputs (per runner):
      - Fair Prob       (0..1)          sums to 1 per race (active runners)
      - Fair %          (0..target)     sums to target_book_pct per race (active runners)
      - Fair Odds       (decimal)       book odds (based on Fair %)
      - Fair Odds (100) (decimal)       true odds (100% market)
      - MarketRank      (1 = top)
      - RaceOverround   (sum of Fair % per race; ~= target_book_pct)
      - MarketWeight    (internal)

    Notes:
      - Prefers ModelRating if present, otherwise Rating.
      - Skips scratched runners if Barrier == 'SCR' or Driver == 'SCRATCHED' (if cols exist).
      - Missing ratings get ~0 weight.
    """
    import numpy as np
    import pandas as pd

    # ---- pick race key ----
    race_key = "RaceAnchorFull" if "RaceAnchorFull" in uf.columns else (
        "Race Anchor" if "Race Anchor" in uf.columns else None
    )
    if race_key is None:
        print("⚠️ No race key column found; skipping add_market_from_rating()")
        return

    # ---- pick rating column ----
    rating_col = "ModelRating" if "ModelRating" in uf.columns else ("Rating" if "Rating" in uf.columns else None)
    if rating_col is None:
        print("⚠️ No 'ModelRating' or 'Rating' column found; run add_rating() first.")
        return

    uf[rating_col] = pd.to_numeric(uf[rating_col], errors="coerce")

    eps = 1e-12

    # --- scratch mask (optional) ---
    scratched = pd.Series(False, index=uf.index)
    if "Barrier" in uf.columns:
        scratched |= uf["Barrier"].astype(str).str.strip().str.upper().eq("SCR")
    if "Driver" in uf.columns:
        scratched |= uf["Driver"].astype(str).str.strip().str.upper().eq("SCRATCHED")

    def _weights(g: pd.DataFrame) -> pd.Series:
        r = pd.to_numeric(g[rating_col], errors="coerce").fillna(-np.inf)

        if method == "linear":
            w = r.clip(lower=0).astype(float)
            w = w.replace([np.inf, -np.inf], 0.0).fillna(0.0) + eps
            return pd.Series(w, index=g.index)

        if method == "exp":
            # Ratings: best ~100. Convert deficit into seconds-ish using k=13.
            k = 13.0
            dt = (100.0 - r) / k
            w = np.exp(-beta * dt)
            w = pd.Series(w, index=g.index).replace([np.inf, -np.inf], 0.0).fillna(0.0) + eps
            return w

        raise ValueError("method must be 'linear' or 'exp'")

    def _process_race(g: pd.DataFrame) -> pd.DataFrame:
        # Start blank for the whole race
        for c in ["MarketWeight", "Fair Prob", "Fair %", "Fair Odds", "Fair Odds (100)", "MarketRank", "RaceOverround"]:
            if c not in g.columns:
                g[c] = np.nan
            else:
                g[c] = np.nan

        # Only price active (non-scratched) runners
        active_mask = ~scratched.loc[g.index]
        active = g.loc[active_mask].copy()

        if active[rating_col].notna().sum() == 0:
            return g

        w = _weights(active).astype(float)
        s = float(np.nansum(w))
        if not np.isfinite(s) or s <= 0:
            return g

        # True probs (sum to 1)
        prob = (w / s).astype(float)

        # Book % (sum to target_book_pct)
        fair_pct = prob * float(target_book_pct)

        # True odds (100% market)
        true_odds_100 = np.where(prob > 0, 1.0 / prob, np.nan)

        # Book odds derived from Fair % (e.g. 8.0% => 12.50)
        odds_book = np.where(fair_pct > 0, 100.0 / fair_pct, np.nan)

        if use_compressed_odds:
            fair_odds = pd.Series(odds_book, index=active.index).apply(compress_odds).astype(float)
        else:
            fair_odds = pd.Series(odds_book, index=active.index).astype(float)

        fair_odds_100 = pd.Series(true_odds_100, index=active.index).astype(float)

        # write back
        g.loc[active.index, "MarketWeight"] = w
        g.loc[active.index, "Fair Prob"] = prob
        g.loc[active.index, "Fair %"] = fair_pct
        g.loc[active.index, "Fair Odds"] = fair_odds
        g.loc[active.index, "Fair Odds (100)"] = fair_odds_100

        # ranks (1 = top)
        g.loc[active.index, "MarketRank"] = (
            g.loc[active.index, "Fair Prob"].rank(ascending=False, method="min")
        )

        # race-level overround (active only)
        over = float(g.loc[active.index, "Fair %"].sum(skipna=True))
        g["RaceOverround"] = over

        return g

    print(f"➡️ Building market from '{rating_col}' using method='{method}', beta={beta}, book={target_book_pct} …")
    uf[:] = uf.groupby(race_key, group_keys=False).apply(_process_race)

    if "MarketRank" in uf.columns:
        uf["MarketRank"] = pd.to_numeric(uf["MarketRank"], errors="coerce")


    # -------------------------
    # DEBUG: random race check
    # -------------------------
    try:
        # Pick a random race that actually has Fair % populated
        race_ids = (
            uf.loc[uf["Fair %"].notna(), race_key]
              .dropna()
              .astype(str)
              .unique()
              .tolist()
        )

        if race_ids:
            rid = np.random.choice(race_ids)

            g = uf[uf[race_key].astype(str) == str(rid)].copy()

            # Active only (same scratch rules)
            active_mask = pd.Series(True, index=g.index)
            if "Barrier" in g.columns:
                active_mask &= ~g["Barrier"].astype(str).str.strip().str.upper().eq("SCR")
            if "Driver" in g.columns:
                active_mask &= ~g["Driver"].astype(str).str.strip().str.upper().eq("SCRATCHED")

            ga = g.loc[active_mask].copy()

            over = float(pd.to_numeric(ga["Fair %"], errors="coerce").sum(skipna=True))
            n_active = int(ga.shape[0])
            n_total = int(g.shape[0])

            # Show a quick summary + top 6 by probability
            ga["Fair Prob"] = pd.to_numeric(ga["Fair Prob"], errors="coerce")
            ga["Fair Odds"] = pd.to_numeric(ga["Fair Odds"], errors="coerce")

            top = (
                ga.sort_values("Fair Prob", ascending=False)
                  .loc[:, [c for c in ["Horse", "Barrier", "MarketRank", "Fair Prob", "Fair %", "Fair Odds"] if c in ga.columns]]
                  .head(6)
            )

            print("\n🎲 RANDOM RACE OVERROUND CHECK")
            print(f"Race: {rid}")
            print(f"Active runners: {n_active} (total rows: {n_total})")
            print(f"RaceOverround (sum Fair % active): {over:.2f}  | target: {float(target_book_pct):.2f}  | diff: {over - float(target_book_pct):+.2f}")
            print(top.to_string(index=False))
            print("")
        else:
            print("ℹ️ Debug: no races with Fair % populated yet (nothing to sample).")

    except Exception as e:
        print(f"⚠️ Debug random-race check failed: {e}")



    print("✅ add_market_from_rating(): wrote Fair Prob / Fair % / Fair Odds / Fair Odds (100) / MarketRank / RaceOverround")






def add_market_from_merged_model(
    target_book_pct: float = 125.0,
    method: str = "exp",
    beta: float = 1.50,
    edge_weight: float = 0.50,
    recent_n: int = 5,
    debug_horse: Optional[str] = None,
):
    """
    Build Fair % / Fair Odds using the master model signals in merged_file.csv.

    Key idea:
      - Price runners off *seconds* gaps (ModelEffectiveIndHalf), not rank-compressed ratings.
      - This makes a 1.5s gap actually matter (should blow odds out / tighten favs accordingly).

    For each upcoming runner we look up (by Horse) from merged_file.csv:
      - HorseRecentRatingIndHalf_5 (preferred baseline ability; lower = better)
        fallback to RatingIndHalf if HorseRecentRatingIndHalf_5 is missing
      - ExpectedGapSeconds (mean of last `recent_n` runs; negative = better than expected)

    We then build:
      ModelBaseIndHalf
      ContextAdjSeconds_Up (already in upcoming_fields.csv from earlier steps; defaults to 0 if missing)
      ModelEdgeSeconds_{recent_n}
      ModelEffectiveIndHalf = ModelBaseIndHalf + ContextAdjSeconds_Up + edge_weight * ModelEdgeSeconds_{recent_n}

    Market:
      - EXP method uses weights = exp(-beta * ((eff - best_eff) / tau))
        where tau is a seconds scale (we use 1.0s).
      - This means: +1.0s slower => weight * exp(-beta)
    """
    import os
    import pandas as _pd  # ✅ use ONLY _pd inside this function to avoid pd scoping bugs

    # ----------------------------
    # Load upcoming_fields
    # ----------------------------
    try:
        uf = _pd.read_csv("upcoming_fields.csv")

        # --- Ensure RaceAnchorFull exists: "{Race Anchor}_R{Race No}" e.g. "AP200226_R1" ---
        # Do NOT remove or rename "Race Anchor" — you want both.
        if "RaceAnchorFull" not in uf.columns:
            uf["RaceAnchorFull"] = ""

        # Normalise inputs
        ra = uf["Race Anchor"].astype(str).fillna("").str.strip() if "Race Anchor" in uf.columns else _pd.Series("", index=uf.index)
        rn = uf["Race No"].astype(str).fillna("").str.strip() if "Race No" in uf.columns else _pd.Series("", index=uf.index)

        # Fill only missing/blank RaceAnchorFull
        raf = uf["RaceAnchorFull"].astype(str).fillna("").str.strip()
        missing = (raf == "") | (raf.str.lower() == "nan")

        # Build
        built = (ra + "_R" + rn).str.strip()

        # Only assign where we have both parts
        ok = missing & (ra != "") & (rn != "")
        uf.loc[ok, "RaceAnchorFull"] = built.loc[ok]

        print(
            "✅ RaceAnchorFull present. Non-empty %:",
            round((uf["RaceAnchorFull"].astype(str).str.strip() != "").mean() * 100, 1)
        )

    except Exception as e:
        print(f"⚠️ Failed to read upcoming_fields.csv: {e}")
        return

    # Race key (must exist in the *current uf* at runtime)
    if "RaceAnchorFull" in uf.columns:
        race_key = "RaceAnchorFull"
    elif "Race Anchor" in uf.columns:
        race_key = "Race Anchor"
    else:
        print("⚠️ No race key column found in uf; skipping add_market_from_merged_model()")
        print("DEBUG available columns (first 80):", list(uf.columns)[:80])
        return

    # Defensive: fail early if pandas would KeyError anyway
    if race_key not in uf.columns:
        print(f"⚠️ race_key='{race_key}' not found in uf.columns; cannot group.")
        print("DEBUG available columns (first 80):", list(uf.columns)[:80])
        return

    if "Horse" not in uf.columns:
        print("⚠️ 'Horse' column not found in upcoming_fields.csv; skipping add_market_from_merged_model()")
        return

    # Ensure ContextAdjSeconds_Up exists (created elsewhere in your pipeline, but be defensive)
    if "ContextAdjSeconds_Up" not in uf.columns:
        uf["ContextAdjSeconds_Up"] = 0.0
    uf["ContextAdjSeconds_Up"] = _pd.to_numeric(uf["ContextAdjSeconds_Up"], errors="coerce").fillna(0.0)

    # ----------------------------
    # Load only columns needed from merged_file
    # ----------------------------
    mf_cols = [
        "Horse", "Date",
        "HorseRecentRatingIndHalf_5", "RatingIndHalf", "ExpectedGapSeconds",
        "MarginClean", "BellPosition"
    ]

    try:
        mf = _pd.read_csv("merged_file.csv", low_memory=False, usecols=lambda c: c in mf_cols)
    except Exception as e:
        print(f"⚠️ Failed to read merged_file.csv for model market: {e}")
        return

    # Normalise horse keys
    uf["HorseKey"] = uf["Horse"].astype(str).fillna("").map(clean_horse_name).str.lower().str.strip()
    mf["HorseKey"] = mf["Horse"].astype(str).fillna("").map(clean_horse_name).str.lower().str.strip()

    if debug_horse:
        hk = clean_horse_name(debug_horse).lower().strip()
        d = mf[mf["HorseKey"] == hk][["Date","RatingIndHalf","HorseRecentRatingIndHalf_5","ExpectedGapSeconds","MarginClean","BellPosition"]].tail(12)
        print("\n🧪 merged_file history for", debug_horse)
        print(d.to_string(index=False))

    # Dates + numeric coercion
    mf["Date"] = _pd.to_datetime(mf.get("Date"), errors="coerce", dayfirst=True)
    for c in ["HorseRecentRatingIndHalf_5", "RatingIndHalf", "ExpectedGapSeconds"]:
        if c in mf.columns:
            mf[c] = _pd.to_numeric(mf[c], errors="coerce")

    # Sort so tail() works as "most recent"
    mf = mf.sort_values(["HorseKey", "Date"], kind="mergesort")

    # --- build a stable baseline from *recent valid RatingIndHalf* only ---
    base = _pd.Series(dtype=float)

    if "RatingIndHalf" in mf.columns:
        m = mf["RatingIndHalf"].notna()

        if "MarginClean" in mf.columns:
            m &= (_pd.to_numeric(mf["MarginClean"], errors="coerce").fillna(0) < 99)

        if "BellPosition" in mf.columns:
            m &= (~mf["BellPosition"].astype(str).str.upper().isin(["TO"]))

        mf_valid = mf.loc[m].copy()

        # DEBUG: confirm which race id columns are present at this stage
        print(
            "DEBUG id columns present:",
            "RaceAnchorFull" in uf.columns,
            "Race Anchor" in uf.columns
        )

        base = (
            mf_valid.groupby("HorseKey", sort=False)
                    .tail(recent_n)
                    .groupby("HorseKey")["RatingIndHalf"]
                    .mean()
        )

    # --- stable baseline from Exp Half ---
    uf["Exp Half"] = _pd.to_numeric(uf.get("Exp Half"), errors="coerce").fillna(60.0)

    # --- horse "ability offset" relative to its own expectation ---
    horse_offset = _pd.to_numeric(uf["HorseKey"].map(base), errors="coerce") - uf["Exp Half"]
    horse_offset = horse_offset.clip(lower=-1.2, upper=1.2)  # tune bounds
    uf["ModelBaseIndHalf"] = uf["Exp Half"] + horse_offset

    # Recent mean ExpectedGapSeconds per horse (last recent_n valid runs)
    if "ExpectedGapSeconds" in mf.columns:
        m = mf["ExpectedGapSeconds"].notna()

        if "MarginClean" in mf.columns:
            m &= (_pd.to_numeric(mf["MarginClean"], errors="coerce").fillna(0) < 99)

        if "BellPosition" in mf.columns:
            m &= (~mf["BellPosition"].astype(str).str.upper().isin(["TO"]))

        mf_gap_valid = mf.loc[m].copy()

        recent_mean_gap = (
            mf_gap_valid.groupby("HorseKey", sort=False)
                        .tail(recent_n)
                        .groupby("HorseKey")["ExpectedGapSeconds"]
                        .mean()
        )
    else:
        recent_mean_gap = _pd.Series(dtype=float)

    # Map into upcoming
    uf[f"ModelEdgeSeconds_{recent_n}"] = uf["HorseKey"].map(recent_mean_gap)

    uf["ModelBaseIndHalf"] = _pd.to_numeric(uf["ModelBaseIndHalf"], errors="coerce")
    uf[f"ModelEdgeSeconds_{recent_n}"] = _pd.to_numeric(uf[f"ModelEdgeSeconds_{recent_n}"], errors="coerce")

    # Effective (lower is better)
    ctx = _pd.to_numeric(uf.get("ContextAdjSeconds_Up"), errors="coerce").fillna(0.0)
    edge = _pd.to_numeric(uf.get(f"ModelEdgeSeconds_{recent_n}"), errors="coerce").fillna(0.0)

    uf["ModelEffectiveIndHalf"] = (
        uf["ModelBaseIndHalf"]
        + ctx
        + edge_weight * edge
    )

    # Optional: race-local ModelRating for display/debug (best = 100)
    def _add_model_rating(g: _pd.DataFrame) -> _pd.DataFrame:
        eff = _pd.to_numeric(g["ModelEffectiveIndHalf"], errors="coerce")
        if eff.notna().sum() == 0:
            g["ModelRating"] = np.nan
            return g
        ranks = eff.rank(method="dense", ascending=True)  # 1 = best (fastest)
        g["ModelRating"] = 101.0 - ranks
        return g

    uf = uf.groupby(race_key, group_keys=False).apply(_add_model_rating)

    # ----- MARKET BUILDER (seconds-based) -----
    eps = 1e-9
    tau_seconds = 1.6

    def _weights_from_effective_seconds(g: _pd.DataFrame) -> _pd.Series:
        eff = _pd.to_numeric(g["ModelEffectiveIndHalf"], errors="coerce")

        if method == "linear":
            best = eff.min(skipna=True)
            w = (best - eff).clip(lower=0) + eps
            w = w.fillna(0.0) + eps
            print(f"Weights distribution (linear): {w.describe()}")
            return w

        if method == "exp":
            best = eff.min(skipna=True)
            delta = (eff - best) / tau_seconds
            w = np.exp(-beta * delta.fillna(np.inf))
            w = w.replace([np.inf, -np.inf], 0.0).fillna(0.0) + eps
            print(f"Weights distribution (exp): {w.describe()}")
            return w

        raise ValueError("method must be 'linear' or 'exp'")

    def _process_group(g: _pd.DataFrame) -> _pd.DataFrame:
        eff = _pd.to_numeric(g["ModelEffectiveIndHalf"], errors="coerce")

        barrier = g["Barrier"].astype(str).str.strip().str.upper() if "Barrier" in g.columns else None
        driver  = g["Driver"].astype(str).str.strip().str.upper()  if "Driver"  in g.columns else None

        scratched_mask = _pd.Series(False, index=g.index)
        if barrier is not None:
            scratched_mask |= (barrier == "SCR")
        if driver is not None:
            scratched_mask |= (driver == "SCRATCHED")

        mask = eff.notna() & (~scratched_mask)
        active = g.loc[mask].copy()

        # Always start blank; we'll only fill priced runners
        g["Fair %"] = np.nan
        g["Fair Odds"] = np.nan
        g["Fair Odds Display"] = np.nan
        g["RaceOverround"] = np.nan

        g["Fair % (100)"] = np.nan
        g["Fair Odds (100)"] = np.nan
        g["RaceOverround (100)"] = np.nan

        if active.empty:
            return g

        w = _weights_from_effective_seconds(active)
        w = np.asarray(w, dtype="float64").reshape(-1)

        s = float(np.nansum(w))
        if not np.isfinite(s) or s <= 0:
            return g

        probs = w / s

        flatten_power = 1.3
        if flatten_power != 1.0:
            probs = np.power(probs, flatten_power)
            probs = probs / probs.sum()

        # TRUE (100%) MARKET
        fair_pct_100 = probs * 100.0
        odds_100_raw = np.where(fair_pct_100 > 0, 100.0 / fair_pct_100, np.nan)

        # BOOK (target_book_pct) MARKET
        book_pct = float(target_book_pct)
        fair_pct_book = probs * book_pct
        odds_book_raw = np.where(fair_pct_book > 0, 100.0 / fair_pct_book, np.nan)

        odds_book_raw_series = _pd.Series(odds_book_raw, index=active.index).astype(float)
        odds_book_display_series = odds_book_raw_series.apply(compress_odds).astype(float)

        active["Fair % (100)"] = fair_pct_100
        active["Fair Odds (100)"] = _pd.Series(odds_100_raw, index=active.index).astype(float)

        active["Fair %"] = fair_pct_book
        active["Fair Odds"] = odds_book_raw_series
        active["Fair Odds Display"] = odds_book_display_series

        g["RaceOverround"] = float(active["Fair %"].sum())
        g["RaceOverround (100)"] = float(active["Fair % (100)"].sum())

        g.loc[active.index, "Fair %"] = active["Fair %"]
        g.loc[active.index, "Fair Odds"] = active["Fair Odds"]
        g.loc[active.index, "Fair Odds Display"] = active["Fair Odds Display"]
        g.loc[active.index, "RaceOverround"] = g["RaceOverround"].iloc[0]

        g.loc[active.index, "Fair % (100)"] = active["Fair % (100)"]
        g.loc[active.index, "Fair Odds (100)"] = active["Fair Odds (100)"]
        g.loc[active.index, "RaceOverround (100)"] = g["RaceOverround (100)"].iloc[0]

        return g

    # ------------------------------
    # DEBUG + HARD GUARANTEE (race key)
    # ------------------------------

    print("DEBUG groupby keys (initial):", race_key)
    print("DEBUG has RaceAnchorFull (before fix):", "RaceAnchorFull" in uf.columns)
    print("DEBUG columns (first 60):", list(uf.columns)[:60])

    print("DEBUG cwd:", os.getcwd())
    print("DEBUG upcoming_fields.csv exists:", os.path.exists("upcoming_fields.csv"))

    if os.path.exists("upcoming_fields.csv"):
        hdr = _pd.read_csv("upcoming_fields.csv", nrows=0).columns.tolist()
        print("DEBUG file header has RaceAnchorFull:", "RaceAnchorFull" in hdr)
        print("DEBUG file header has Race Anchor:", "Race Anchor" in hdr)
        print("DEBUG file header has Fair Odds:", "Fair Odds" in hdr)

    # --- HARD GUARANTEE: ensure RaceAnchorFull exists in-memory ---
    if "RaceAnchorFull" not in uf.columns:
        print("⚠️ RaceAnchorFull missing in-memory. Rebuilding from Race Anchor + Race No.")

        if "Race Anchor" in uf.columns and "Race No" in uf.columns:
            ra = uf["Race Anchor"].astype(str).fillna("").str.strip()
            rn = uf["Race No"].astype(str).fillna("").str.strip()
            uf["RaceAnchorFull"] = (ra + "_R" + rn).str.strip()
            print("✅ Rebuilt RaceAnchorFull in-memory.")
        else:
            print("❌ Cannot rebuild RaceAnchorFull (missing Race Anchor or Race No). Falling back to Race Anchor.")

    # Final safety: choose grouping key dynamically
    if "RaceAnchorFull" in uf.columns:
        race_key = "RaceAnchorFull"
    elif "Race Anchor" in uf.columns:
        race_key = "Race Anchor"
    else:
        print("❌ No usable race key found. Aborting market build.")
        return

    print("DEBUG groupby keys (final):", race_key)
    print("DEBUG has RaceAnchorFull (after fix):", "RaceAnchorFull" in uf.columns)

    # ------------------------------
    # SAFE GROUPBY
    # ------------------------------
    uf = uf.groupby(race_key, group_keys=False).apply(_process_group)

    # --- DEBUG PRINT (single runner) ---
    if debug_horse:
        dh = debug_horse.strip().lower()
        hit = uf[uf["Horse"].astype(str).str.lower().str.strip() == dh].copy()
        if hit.empty:
            print(f"🟡 Fair Odds debug: '{debug_horse}' not found in upcoming_fields.csv")
        else:
            cols = [c for c in [
                race_key,
                "Horse",
                "ModelBaseIndHalf",
                "ContextAdjSeconds_Up",
                f"ModelEdgeSeconds_{recent_n}",
                "ModelEffectiveIndHalf",
                "ModelRating",
                "Fair %",
                "Fair Odds",
            ] if c in hit.columns]
            print("\n🎯 Fair Odds debug for:", debug_horse)
            print(hit[cols].to_string(index=False))
            print()

    try:
        uf.drop(columns=["HorseKey"], inplace=True, errors="ignore")
        uf.to_csv("upcoming_fields.csv", index=False)
        print("✅ Updated Fair % / Fair Odds (seconds-based, context-adjusted) in upcoming_fields.csv")
    except Exception as e:
        print(f"⚠️ Failed to write updated upcoming_fields.csv: {e}")





def add_last_run_details_columns():
    """
    Adds LR columns to upcoming_fields.csv using merged_file.csv, based on the latest run:

      LR Placing  (from merged_file['Placing'])
      LR Venue    (from merged_file['Venue'])
      LR Date     (from merged_file['Date'])
      LR SP       (from merged_file['SP'])
      LR Trainer  (from merged_file['Trainer'])
      LR Driver   (from merged_file['Driver'])

    Plus:
      LR Dist     (from merged_file['Distance'])
      LR Br       (from merged_file['Barrier'])
      LR Mgn      (from merged_file['Margin'])
      LR Pos      (from merged_file['Bell Pos'] / 'BellPosition' / 'Bell Position')
      LR Winner   (look up merged_file rows with same RaceAnchorFull and Placing==1, return that Horse)

    Notes:
    - Horse matching uses clean_horse_name(), lowercased/trimmed.
    - If upcoming_fields.Date is missing/NaT, uses latest-ever in merged_file.
    - If a horse has no runs in merged_file, values are blank.
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # --- Dates ---
    uf["Date"] = pd.to_datetime(uf.get("Date"), errors="coerce")
    mf["Date"] = pd.to_datetime(mf.get("Date"), errors="coerce", dayfirst=True)

    # --- Normalise horse keys (match your other helpers) ---
    uf["Horse"] = uf.get("Horse", "").astype(str).fillna("")
    uf["Horse_key"] = uf["Horse"].map(clean_horse_name).str.strip().str.lower()

    mf["Horse"] = mf.get("Horse", "").astype(str).fillna("")
    mf["Horse_key"] = mf["Horse"].map(clean_horse_name).str.strip().str.lower()

    # --- Ensure expected columns exist in mf (fill blanks if missing) ---
    base_needed_cols = ["Placing", "Venue", "SP", "Trainer", "Driver", "RaceAnchorFull", "Distance", "Barrier", "Margin"]
    for c in base_needed_cols:
        if c not in mf.columns:
            mf[c] = ""

    # Bell position column name can vary across your pipeline
    bell_pos_col = None
    for cand in ["Bell Pos", "BellPosition", "Bell Position", "BellPos"]:
        if cand in mf.columns:
            bell_pos_col = cand
            break
    if bell_pos_col is None:
        mf["Bell Pos"] = ""
        bell_pos_col = "Bell Pos"

    # --- tidy string helpers ---
    mf["Venue_str"] = mf["Venue"].astype(str).fillna("").str.strip()
    mf["SP_str"] = mf["SP"].astype(str).fillna("").str.strip()
    mf["Trainer_str"] = mf["Trainer"].astype(str).fillna("").str.strip()
    mf["Driver_str"] = mf["Driver"].astype(str).fillna("").str.strip()
    mf["RaceAnchorFull_str"] = mf["RaceAnchorFull"].astype(str).fillna("").str.strip()
    mf["Barrier_str"] = mf["Barrier"].astype(str).fillna("").str.strip()
    mf["Margin_str"] = mf["Margin"].astype(str).fillna("").str.strip()
    mf["BellPos_str"] = mf[bell_pos_col].astype(str).fillna("").str.strip()

    def _num_to_str(x):
        if pd.isna(x):
            return ""
        s = str(x).strip()
        if s == "" or s.lower() == "null":
            return ""
        # pull first numeric chunk (handles "2050m" / "$3.40" / etc)
        s2 = re.sub(r"[^0-9\.\-]", "", s)
        if s2 == "":
            return s
        try:
            v = float(s2)
            # if it's a whole number like 2050.0 -> 2050
            if abs(v - round(v)) < 1e-9:
                return str(int(round(v)))
            return str(v)
        except Exception:
            return s

    # Placing -> tidy string (e.g. 1,2,3,...)
    def _placing_to_str(x):
        if pd.isna(x):
            return ""
        s = str(x).strip()
        s = re.sub(r"[^\d\.]", "", s)
        if s == "":
            return ""
        try:
            v = float(s)
            return str(int(round(v)))
        except Exception:
            return s

    mf["Placing_str"] = mf["Placing"].apply(_placing_to_str)
    mf["Distance_str"] = mf["Distance"].apply(_num_to_str)

    # --- Build LR Winner lookup: RaceAnchorFull -> winner Horse (placing == 1) ---
    # Use Horse as-is from mf (not cleaned) for display.
    mf["Horse_str"] = mf["Horse"].astype(str).fillna("").str.strip()

    winners = (
        mf[mf["Placing_str"] == "1"]
        .dropna(subset=["RaceAnchorFull_str"])
        .groupby("RaceAnchorFull_str", as_index=True)["Horse_str"]
        .first()
        .to_dict()
    )

    # Pre-sort mf by Horse_key then Date descending so "latest" is easy
    mf = mf.dropna(subset=["Horse_key"])
    mf_sorted = mf.sort_values(["Horse_key", "Date"], ascending=[True, False])

    def _resolve_lr(row):
        hk = row.get("Horse_key", "")
        race_date = row.get("Date", pd.NaT)

        sub = mf_sorted[mf_sorted["Horse_key"] == hk]
        if sub.empty:
            return pd.Series({
                "LR Placing": "",
                "LR Venue": "",
                "LR Date": "",
                "LR SP": "",
                "LR Trainer": "",
                "LR Driver": "",
                "LR Dist": "",
                "LR Br": "",
                "LR Mgn": "",
                "LR Pos": "",
                "LR Winner": "",
            })

        # Prefer latest run strictly before upcoming race date (if we have a date)
        if pd.notna(race_date):
            sub2 = sub[sub["Date"] < race_date]
            pick = sub2.iloc[0] if not sub2.empty else sub.iloc[0]
        else:
            pick = sub.iloc[0]

        lr_date = ""
        try:
            if pd.notna(pick["Date"]):
                lr_date = pick["Date"].strftime("%Y-%m-%d")
        except Exception:
            lr_date = str(pick.get("Date", "") or "")

        ra = (pick.get("RaceAnchorFull_str", "") or "").strip()
        lr_winner = winners.get(ra, "") if ra else ""

        return pd.Series({
            "LR Placing": pick.get("Placing_str", "") or "",
            "LR Venue": pick.get("Venue_str", "") or "",
            "LR Date": lr_date,
            "LR SP": pick.get("SP_str", "") or "",
            "LR Trainer": pick.get("Trainer_str", "") or "",
            "LR Driver": pick.get("Driver_str", "") or "",
            "LR Dist": pick.get("Distance_str", "") or "",
            "LR Br": pick.get("Barrier_str", "") or "",
            "LR Mgn": pick.get("Margin_str", "") or "",
            "LR Pos": pick.get("BellPos_str", "") or "",
            "LR Winner": lr_winner or "",
        })

    print("➡️ Resolving latest run details (LR Placing/Venue/Date/SP/Trainer/Driver/Dist/Br/Mgn/Pos/Winner)…")
    out = uf.apply(_resolve_lr, axis=1)

    for c in out.columns:
        uf[c] = out[c].fillna("")

    # Tidy helper
    uf.drop(columns=["Horse_key"], inplace=True, errors="ignore")

    # Save
    try:
        uf.to_csv("upcoming_fields.csv", index=False)
        print("✅ Added LR columns to upcoming_fields.csv")
    except Exception as e:
        print(f"⚠️ Failed to write upcoming_fields.csv: {e}")

    # Optional: also write into Flutter assets folder (ignore if path missing)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
        print("✅ Also saved into Flutter assets folder")
    except Exception:
        pass






def add_last_media_links():
    """
    Adds 6 columns to upcoming_fields.csv using merged_file.csv:

      Last Run Video Text : "Last Run: [Placing]"   (most recent run < this race's Date, if available)
      Last Run Video URL  : [Video Link]

      Last Win Video Text : "Last Win: [Venue]"     (most recent win < this race's Date)
      Last Win Video URL  : [Video Link]

      Last Win Photo Text : "Last Win Photo"
      Last Win Photo URL  : [Photo Link]

    Notes:
    - Horse matching uses clean_horse_name(), lowercased/trimmed.
    - If upcoming_fields.Date is missing/NaT, we fall back to "latest ever" in merged_file.
    - If a link is missing, URL is blank and Text still populated (so the UI can show disabled/greyed state).
    - NEW: Only consider merged_file rows where 50 <= Ind Half <= 70.
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # Ensure dates
    uf["Date"] = pd.to_datetime(uf.get("Date"), errors="coerce")
    mf["Date"] = pd.to_datetime(mf.get("Date"), errors="coerce", dayfirst=True)

    # 🔎 Filter merged_file by Ind Half range
    if "Ind Half" in mf.columns:
        mf["Ind Half"] = pd.to_numeric(mf["Ind Half"], errors="coerce")
        mf = mf[(mf["Ind Half"] >= 50) & (mf["Ind Half"] <= 70)]

    # Normalise horse keys
    uf["Horse"] = uf["Horse"].astype(str).fillna("")
    uf["Horse_key"] = uf["Horse"].map(clean_horse_name).str.strip().str.lower()

    mf["Horse"] = mf["Horse"].astype(str).fillna("")
    mf["Horse_key"] = mf["Horse"].map(clean_horse_name).str.strip().str.lower()

    # Normalise useful fields from merged_file
    def _to_placing_str(x):
        if pd.isna(x): 
            return "-"
        s = str(x).strip()
        s = re.sub(r"[^\d\.]", "", s)
        if s == "":
            return "-"
        try:
            v = float(s)
            i = int(round(v))
            return str(i)
        except:
            return s

    mf["Placing_str"] = mf.get("Placing", "").apply(_to_placing_str)
    mf["Venue_str"] = mf.get("Venue", "").astype(str).str.strip()
    for col in ["Video Link", "Photo Link"]:
        if col not in mf.columns:
            mf[col] = ""
        mf[col] = mf[col].astype(str).fillna("").str.strip()

    def _resolve_links(row):
        hk = row.get("Horse_key", "")
        race_date = row.get("Date", pd.NaT)
        sub = mf[mf["Horse_key"] == hk]
        if sub.empty:
            return pd.Series({
                "Last Run Video Text": "",
                "Last Run Video URL": "",
                "Last Win Video Text": "",
                "Last Win Video URL": "",
                "Last Win Photo Text": "",
                "Last Win Photo URL": "",
            })

        if not pd.isna(race_date):
            sub = sub[sub["Date"] < race_date]

        if sub.empty:
            latest = mf[mf["Horse_key"] == hk].sort_values("Date", ascending=False).head(1)
        else:
            latest = sub.sort_values("Date", ascending=False).head(1)

        if not latest.empty:
            lr_place = latest["Placing_str"].iloc[0]
            lr_video = latest["Video Link"].iloc[0]
        else:
            lr_place, lr_video = "-", ""

        win_pool = sub if not sub.empty else mf[mf["Horse_key"] == hk]
        win_pool = win_pool[pd.to_numeric(win_pool.get("Placing", pd.Series(dtype=float)), errors="coerce") == 1]
        win_pool = win_pool.sort_values("Date", ascending=False)

        if not win_pool.empty:
            lw = win_pool.iloc[0]
            lw_text = f"Last Win: {lw['Venue_str']}" if lw["Venue_str"] else "Last Win"
            lw_video = lw["Video Link"]
            lw_photo = lw["Photo Link"]
        else:
            lw_text, lw_video, lw_photo = "Last Win", "", ""

        lr_text = f"Last Run: {lr_place}" if lr_place != "-" else "Last Run"

        return pd.Series({
            "Last Run Video Text": lr_text,
            "Last Run Video URL": lr_video,
            "Last Win Video Text": lw_text,
            "Last Win Video URL": lw_video,
            "Last Win Photo Text": "Last Win Photo",
            "Last Win Photo URL": lw_photo,
        })

    print("➡️ Resolving Last Run / Last Win media links…")
    out = uf.apply(_resolve_links, axis=1)

    for c in out.columns:
        uf[c] = out[c].fillna("")

    uf.drop(columns=["Horse_key"], inplace=True, errors="ignore")

    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added Last Run/Win media link columns to upcoming_fields.csv")


def add_ven_peg_adj_formula_version():
    """
    VenPegAdj = AVERAGEIFS(IndHalf, 50..70) - AVERAGEIFS(IndHalf, 50..70, Venue=row.Venue, Width=row.Width)
    AdjIndHalf = Ind Half + VenPegAdj

    - Both VenPegAdj and AdjIndHalf rounded to 2 dp
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # Ensure required columns
    for col in ["Venue", "Width"]:
        if col not in uf.columns:
            print(f"⚠️ '{col}' missing from upcoming_fields.csv; cannot compute VenPegAdj.")
            return
    for col in ["Venue", "Width", "Ind Half"]:
        if col not in mf.columns:
            print(f"⚠️ '{col}' missing from merged_file.csv; cannot compute VenPegAdj.")
            return

    # Normalise keys
    uf["Venue_norm"]  = uf["Venue"].astype(str).str.strip()
    uf["Width_norm"]  = uf["Width"].astype(str).str.strip().str.upper()
    mf["Venue_norm"]  = mf["Venue"].astype(str).str.strip()
    mf["Width_norm"]  = mf["Width"].astype(str).str.strip().str.upper()

    # Clean numeric + filter Ind Half ∈ [50, 70]
    mf["Ind Half"] = pd.to_numeric(mf["Ind Half"], errors="coerce")
    mf_filt = mf[(mf["Ind Half"].notna()) & (mf["Ind Half"] >= 50.0) & (mf["Ind Half"] <= 70.0)]

    if mf_filt.empty:
        print("ℹ️ No rows in merged_file with 50 ≤ Ind Half ≤ 70; setting VenPegAdj = 0.0 for all.")
        uf["VenPegAdj"] = 0.0
    else:
        # Global average
        global_avg = mf_filt["Ind Half"].mean()

        # Venue+Width averages
        vw_means = mf_filt.groupby(["Venue_norm", "Width_norm"])["Ind Half"].mean()

        # Map per row; rows with no match → NaN → 0 diff
        per_row_mean = uf.set_index(["Venue_norm", "Width_norm"]).index.map(vw_means)
        per_row_mean = pd.Series(per_row_mean, index=uf.index, dtype="float64")

        uf["VenPegAdj"] = (global_avg - per_row_mean).fillna(0.0)

    # Round VenPegAdj
    uf["VenPegAdj"] = uf["VenPegAdj"].round(2)

    # --- AdjIndHalf = Ind Half + VenPegAdj (2 dp) ---
    if "Ind Half" in uf.columns:
        uf["Ind Half"] = pd.to_numeric(uf["Ind Half"], errors="coerce")
        uf["AdjIndHalf"] = (uf["Ind Half"].fillna(0.0) + uf["VenPegAdj"].fillna(0.0)).round(2)
    else:
        uf["AdjIndHalf"] = uf["VenPegAdj"].fillna(0.0).round(2)

    # Tidy + save
    uf.drop(columns=["Venue_norm", "Width_norm"], inplace=True, errors="ignore")
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("✅ VenPegAdj and AdjIndHalf (rounded to 2 dp) added to upcoming_fields.csv")


def add_predicted_bell_positions(lookback_starts: int = 8):
    """
    Adds the following columns to upcoming_fields.csv for each runner:
      - AvgBellIndex          : mean BellIndex over last N starts (default 8)
      - BarrierNorm           : barrier scaled 0..1 within each race (per group)
      - RowClass              : 0 = Front Row (FR), 1 = Second Row (SR), 2 = Other (e.g., stand/unknown)
      - PredictedBellScore    : lower = more forward at the bell
      - PredictedBellPos      : 1..N within the race (sorted by Score)
      - Predicted Lane        : "Inside"/"Outside" alternating after sort

    FR/SR handling:
      - If Barrier is text like "FR1"/"SR2" → use that directly.
      - Else if numeric + Start == "Mobile" → barriers > 8 are SR, else FR.
      - Else (e.g., "Stand" or unknown) → RowClass = 0 (no penalty).

    Notes:
      - If a horse has no BellIndex history, uses 5.0 (midfield-ish).
      - Score formula is simple and explainable; tune weights later if desired.
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        mf = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # --- Basic column existence checks ---
    if "Horse" not in uf.columns:
        print("⚠️ 'Horse' not found in upcoming_fields.csv; skipping add_predicted_bell_positions()")
        return
    for c in ["Horse", "Date", "BellIndex"]:
        if c not in mf.columns:
            print(f"⚠️ '{c}' not found in merged_file.csv; skipping add_predicted_bell_positions()")
            return

    # --- Clean & types ---
    uf["Horse"] = uf["Horse"].astype(str).fillna("")
    mf["Horse"] = mf["Horse"].astype(str).fillna("")
    mf["BellIndex"] = pd.to_numeric(mf["BellIndex"], errors="coerce")

    # Dates for lookback
    uf["Date"] = pd.to_datetime(uf.get("Date"), errors="coerce")
    mf["Date"] = pd.to_datetime(mf.get("Date"), errors="coerce", dayfirst=True)

    # --- Compute AvgBellIndex per horse using last N starts prior to each runner's race date ---
    # We’ll pre-aggregate per horse (global recent N) which is a solid approximation and fast.
    mf_sorted = mf.sort_values(["Horse", "Date"], ascending=[True, False])
    mf_recentN = mf_sorted.groupby("Horse").head(lookback_starts)
    horse_avg = (
        mf_recentN.groupby("Horse")["BellIndex"]
        .mean()
        .rename("AvgBellIndex")
        .reset_index()
    )

    uf = uf.merge(horse_avg, on="Horse", how="left")
    uf["AvgBellIndex"] = uf["AvgBellIndex"].fillna(5.0)  # neutral midfield default

    # --- Barrier parsing (supports "FR1"/"SR2" or plain numbers) ---
    def _parse_barrier(b):
        s = str(b).strip().upper()
        # Text form: FRx / SRx
        m = re.match(r"^(FR|SR)\s*([0-9]+)$", s)
        if m:
            return m.group(1), int(m.group(2))
        # Numeric only
        m2 = re.match(r"^([0-9]+)$", s)
        if m2:
            return "", int(m2.group(1))
        # Fallback
        return "", None

    uf["Barrier_str"] = uf.get("Barrier", "").astype(str).str.strip()
    parsed = uf["Barrier_str"].apply(_parse_barrier)
    uf["BarrierPrefix"] = parsed.apply(lambda t: t[0])
    uf["BarrierNum"] = pd.to_numeric(parsed.apply(lambda t: t[1]), errors="coerce")

    # --- RowClass (FR=0, SR=1, Other=2) ---
    def _row_class(row):
        pref = row.get("BarrierPrefix", "")
        bnum = row.get("BarrierNum", np.nan)
        start = str(row.get("Start", "")).strip().lower()  # "mobile" or "stand" etc.

        if pref == "FR":
            return 0
        if pref == "SR":
            return 1

        # If numeric & Mobile: >8 → SR, else FR
        if pd.notna(bnum) and start.startswith("mobile"):
            return 1 if bnum > 8 else 0

        # Standing start or unknown → no explicit row penalty
        return 0

    uf["RowClass"] = uf.apply(_row_class, axis=1)

    # --- BarrierNorm: within-race scaling 0..1 (lower better) ---
    race_key = "RaceAnchorFull" if "RaceAnchorFull" in uf.columns else ("Race Anchor" if "Race Anchor" in uf.columns else None)
    if race_key is None:
        race_key = "Race No"  # last-ditch; still groups by race number at least

    # Try to use numeric barrier for normalisation; fall back to order-in-race if NA
    def _norm_barrier_group(g: pd.DataFrame) -> pd.Series:
        # Prefer numeric barriers if we have them; else rank by row sequence
        if g["BarrierNum"].notna().any():
            bn = g["BarrierNum"].copy()
            # Fill any missing with max+1 so they get worst norm
            fillv = (bn.max(skipna=True) or 0) + 1
            bn = bn.fillna(fillv)
            mx = bn.max(skipna=True)
            if mx and mx > 0:
                return (bn / mx).astype(float)
        # fallback: sequential
        n = len(g)
        if n > 1:
            return pd.Series(np.linspace(0.0, 1.0, n), index=g.index)
        return pd.Series(0.5, index=g.index, dtype=float)

    uf["BarrierNorm"] = uf.groupby(race_key, group_keys=False).apply(_norm_barrier_group)

    # --- PredictedBellScore ---
    # Simple, explainable weights; tune later:
    #   heavier weight on AvgBellIndex (style), meaningful pushback for SR (RowClass),
    #   and moderate barrier influence via BarrierNorm
    uf["PredictedBellScore"] = (
        (uf["AvgBellIndex"] * 0.70) +
        (uf["BarrierNorm"] * 3.00) +
        (uf["RowClass"] * 3.00)
    )

    # --- Rank within each race & assign lane (alternating after sort) ---
    def _rank_and_lane(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values("PredictedBellScore", ascending=True).copy()
        g["PredictedBellPos"] = np.arange(1, len(g) + 1)
        # lane alternates Inside, Outside, Inside, ...
        g["Predicted Lane"] = np.where((g["PredictedBellPos"] % 2) == 1, "Inside", "Outside")
        return g

    uf = uf.groupby(race_key, group_keys=False).apply(_rank_and_lane)

    # --- Save back ---
    # Tidy helper cols if you don't want them visible; keep useful ones by default.
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass
    print("✅ Added Predicted Bell columns (AvgBellIndex, BarrierNorm, RowClass, PredictedBellScore, PredictedBellPos, Predicted Lane) to upcoming_fields.csv")


def add_predicted_bell_labels_and_preview():
    """
    Uses PredictedBellPos (1..N) and Predicted Lane ('Inside'/'Outside')
    to assign a harness-native bell label, then writes a simple two-lane text
    preview for each race to 'predicted_bell_preview.txt'.
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
    except Exception as e:
        print(f"⚠️ Could not read upcoming_fields.csv: {e}")
        return

    needed = {"Horse", "RaceAnchorFull", "PredictedBellPos", "Predicted Lane"}
    if not needed.issubset(set(uf.columns)):
        print("⚠️ Missing columns for labelling; run add_predicted_bell_positions() first.")
        return

    # Ensure types
    uf["PredictedBellPos"] = pd.to_numeric(uf["PredictedBellPos"], errors="coerce")
    uf["Predicted Lane"] = uf["Predicted Lane"].astype(str)

    # Mapping by (rank, lane). Extend beyond 5 as sensible fallbacks.
    # Rank pairs: (1,Inside)=LEAD, (1,Outside)=DEATH, (2,Inside)=B/LEAD, (2,Outside)=1X1, etc.
    def _label_for(rank: int, lane: str) -> str:
        lane = (lane or "").strip().lower()
        if rank == 1:
            return "LEAD" if lane == "inside" else "DEATH"
        if rank == 2:
            return "B/LEAD" if lane == "inside" else "1X1"
        if rank == 3:
            return "3PEGS" if lane == "inside" else "1X2"
        if rank == 4:
            return "4PEGS" if lane == "inside" else "1X3"
        if rank == 5:
            return "5PEGS" if lane == "inside" else "3WIDE"
        # Sensible extensions when fields are larger:
        if rank == 6:
            return "6PEGS" if lane == "inside" else "3X1"
        if rank == 7:
            return "7PEGS" if lane == "inside" else "3X2"
        if rank == 8:
            return "8PEGS" if lane == "inside" else "3X3"
        if rank == 9:
            return "9PEGS" if lane == "inside" else "3X4"
        # Beyond that, keep extending the 3-wide chain:
        if lane == "inside":
            return "9PEGS"
        else:
            return "3X5"

    uf["PredictedBellLabel"] = uf.apply(
        lambda r: _label_for(int(r["PredictedBellPos"]) if pd.notnull(r["PredictedBellPos"]) else 99,
                             r["Predicted Lane"]),
        axis=1
    )

    # Save column back
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    # Quick two-lane text preview per race
    lines = []
    race_key = "RaceAnchorFull" if "RaceAnchorFull" in uf.columns else ("Race Anchor" if "Race Anchor" in uf.columns else None)
    if race_key is None:
        race_key = "Race No"

    def _fmt(r):
        # e.g. "#3 Centofellie (FR2)" if you have Barrier text; else just number/name.
        barrier = str(r.get("Barrier", "")).strip()
        return f"{r.get('Horse','')} [{r.get('PredictedBellLabel','')}] {('• '+barrier) if barrier else ''}"

    for race_id, g in uf.groupby(race_key):
        g = g.sort_values("PredictedBellPos", ascending=True)
        inside = [ _fmt(r) for _, r in g[g["Predicted Lane"]=="Inside"].iterrows() ]
        outside = [ _fmt(r) for _, r in g[g["Predicted Lane"]=="Outside"].iterrows() ]
        lines.append(f"=== {race_id} ===")
        lines.append("Inside lane (pegs):")
        lines.append("  " + "  →  ".join(inside) if inside else "  (none)")
        lines.append("Outside lane (running line):")
        lines.append("  " + "  →  ".join(outside) if outside else "  (none)")
        lines.append("")

    preview_path = "predicted_bell_preview.txt"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"🖼️  Wrote quick preview to {preview_path}")



import re, numpy as np, pandas as pd

def add_constrained_bell_map_and_preview():
    """
    Constrained bell-map assignment with domain-driven pools:

    - Enforces paired sequence: LEAD, DEATH, B/LEAD, 1X1, 3PEGS, 1X2, 4PEGS, 1X3, 5PEGS, 1X4, 6PEGS, 1X5, ...
    - B/LEAD: prefers SR(n) behind the predicted FR(n) leader; else FR2 if leader FR1; else nearest small-number FR (FR3...).
      Avoids FR4/FR5 by default unless nothing else fits.
    - DEATH: prefers wide FR (FR8, FR7, FR6, FR5). Avoid FR2 if any other FR can take death.
    - Outside labels never use 3-wide; we cap at 1X4, 1X5, ... instead.
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
    except Exception as e:
        print(f"⚠️ Could not read upcoming_fields.csv: {e}")
        return

    need = {"Horse", "PredictedBellScore", "AvgBellIndex", "Barrier"}
    if not need.issubset(uf.columns):
        print("⚠️ Missing columns; run add_predicted_bell_positions() first.")
        return

    # Barrier parsing
    def _parse_barrier(b):
        s = str(b).strip().upper()
        m = re.match(r"^(FR|SR)\s*([0-9]+)$", s)
        if m:
            return m.group(1), int(m.group(2))
        m2 = re.match(r"^([0-9]+)$", s)
        if m2:
            return "", int(m2.group(1))
        return "", None

    parsed = uf["Barrier"].astype(str).apply(_parse_barrier)
    uf["BarrierPrefix"] = parsed.apply(lambda t: t[0])
    uf["BarrierNum"] = pd.to_numeric(parsed.apply(lambda t: t[1]), errors="coerce")

    # Which column groups a race?
    race_key = "RaceAnchorFull" if "RaceAnchorFull" in uf.columns else (
        "Race Anchor" if "Race Anchor" in uf.columns else "Race No"
    )

    # ---- Rating percentiles (MUST live inside the function, after uf & race_key) ----
    if "Rating" not in uf.columns:
        uf["Rating"] = np.nan
    try:
        uf["Rating"] = pd.to_numeric(uf["Rating"], errors="coerce")
    except Exception:
        pass

    def _pct(s: pd.Series) -> pd.Series:
        n = len(s)
        if n <= 1:
            return pd.Series([0.5] * n, index=s.index, dtype=float)
        ranks = s.rank(method="average", na_option="keep")
        return (ranks - 1) / (n - 1)

    uf["RatingPct"] = (
        uf.groupby(race_key)["Rating"]
          .transform(_pct)          # preserves original row index
          .astype("float64")
          .fillna(0.5)
    )


    # ---- Helpers (inside the function) ----
    def peg_bias(prefix, num):
        if prefix == "FR":
            return max(0.0, 1.15 - 0.12 * (num - 1))  # FR1 strongest peg claims
        if prefix == "SR":
            return max(0.0, 0.60 - 0.08 * (num - 1))  # SR1/SR2 can follow-through
        return 0.15 if (pd.notna(num) and num <= 3) else 0.0

    def outside_bias(prefix, num):
        if prefix == "FR":
            if num >= 7:
                return 0.90 - 0.05 * (8 - num)  # FR8~0.90, FR7~0.85
            if num == 6:
                return 0.70
            if num == 5:
                return 0.55
            if num == 2:
                return -0.40  # FR2 disfavoured for DEATH
            if num == 1:
                return -0.60  # FR1 almost never DEATH
            return 0.20
        if prefix == "SR":
            return 0.55 - 0.05 * (num - 1)  # SR1 1x2/1x3-ish
        return 0.20

    def _safe_rating_pct_local(s: pd.Series) -> pd.Series:
        n = len(s)
        if n <= 1:
            return pd.Series([0.5] * n, index=s.index, dtype=float)
        ranks = s.rank(method="average", na_option="keep")
        out_local = (ranks - 1) / (n - 1)
        return out_local.fillna(0.5)

    def _lead_gate_adjust(prefix: str, num: float, rating_pct: float, avg_bell: float) -> float:
        """
        Adjustment used ONLY for leader selection:
          + small penalty for FR1 (unless strong)
          + tiny bonuses to FR2/FR3 when well-rated & forwardish.
        Positive value = worse chance to lead (penalise); negative = better chance.
        """
        rp = 0.5 if pd.isna(rating_pct) else float(rating_pct)
        ab = 5.0 if pd.isna(avg_bell) else float(avg_bell)
        style = max(0.0, min(1.0, (5.5 - ab) / 4.5))  # forward → ~1

        if prefix == "FR":
            if num == 1:
                return +0.22 - 0.12 * (rp - 0.5) - 0.12 * style
            if num == 2:
                return -0.10 * max(0.0, rp - 0.5) - 0.06 * style
            if num == 3:
                return -0.06 * max(0.0, rp - 0.5) - 0.04 * style
        return 0.0

    # Sequence with no 3-wide labels on outside
    sequence_tail = [
        ("Outside", "1X1"),
        ("Inside", "3PEGS"),
        ("Outside", "1X2"),
        ("Inside", "4PEGS"),
        ("Outside", "1X3"),
        ("Inside", "5PEGS"),
        ("Outside", "1X4"),
        ("Inside", "6PEGS"),
        ("Outside", "1X5"),
        ("Inside", "7PEGS"),
        ("Outside", "1X6"),
        ("Inside", "8PEGS"),
        ("Outside", "1X7"),
        ("Inside", "9PEGS"),
        ("Outside", "1X8"),
    ]

    rows = []

    for race_id, g in uf.groupby(race_key, group_keys=False):
        g = g.copy()

        # Base scores + biases
        g["InsideScore"] = g.apply(
            lambda r: r["PredictedBellScore"] - peg_bias(r["BarrierPrefix"], r["BarrierNum"]), axis=1
        )
        g["OutsideScore"] = g.apply(
            lambda r: r["PredictedBellScore"] - outside_bias(r["BarrierPrefix"], r["BarrierNum"]), axis=1
        )

        # FOLLOW-THROUGH: SRn behind likely leader (simple version; we can later swap to style+rating aware)
        start_val = str(g["Start"].iloc[0]).strip().lower() if "Start" in g.columns and len(g) else ""
        if start_val.startswith("mobile"):
            fr_mask = (g["BarrierPrefix"] == "FR") & g["BarrierNum"].notna()
            if fr_mask.any():
                leader_idx_tmp = g.loc[fr_mask, "InsideScore"].idxmin()
                lead_num_tmp = g.at[leader_idx_tmp, "BarrierNum"]
                same_sr = (g["BarrierPrefix"] == "SR") & (g["BarrierNum"] == lead_num_tmp)
                adj_sr = (g["BarrierPrefix"] == "SR") & (g["BarrierNum"].isin([lead_num_tmp - 1, lead_num_tmp + 1]))
                g.loc[same_sr, "InsideScore"] -= 1.00
                g.loc[adj_sr, "InsideScore"] -= 0.40
                if lead_num_tmp == 1:
                    g.loc[(g["BarrierPrefix"] == "SR") & (g["BarrierNum"] == 1), "InsideScore"] -= 0.20

        assigned_idx = set()
        out = []

        def pick_death_candidate(rem_df: pd.DataFrame) -> int:
            fr = rem_df[(rem_df["BarrierPrefix"] == "FR") & rem_df["BarrierNum"].notna()].copy()
            if not fr.empty:
                fr["death_priority"] = 999
                fr.loc[fr["BarrierNum"] == 8, "death_priority"] = 1
                fr.loc[fr["BarrierNum"] == 7, "death_priority"] = 2
                fr.loc[fr["BarrierNum"] == 6, "death_priority"] = 3
                fr.loc[fr["BarrierNum"] == 5, "death_priority"] = 4
                fr.loc[fr["BarrierNum"] == 2, "death_priority"] = 50  # avoid FR2 for death
                fr.loc[fr["death_priority"] == 999, "death_priority"] = 10 + fr["BarrierNum"]
                fr = fr.sort_values(["death_priority", "OutsideScore"], ascending=[True, True])
                return fr.index[0]
            return rem_df["OutsideScore"].idxmin()

        def pick_blead_candidate(rem_df: pd.DataFrame, leader_num: int) -> int:
            srn = rem_df[(rem_df["BarrierPrefix"] == "SR") & (rem_df["BarrierNum"] == leader_num)]
            if not srn.empty:
                return srn["InsideScore"].idxmin()
            if leader_num == 1:
                fr2 = rem_df[(rem_df["BarrierPrefix"] == "FR") & (rem_df["BarrierNum"] == 2)]
                if not fr2.empty:
                    return fr2["InsideScore"].idxmin()
            fr_small = rem_df[(rem_df["BarrierPrefix"] == "FR") & (rem_df["BarrierNum"].isin([3, 1]))]
            if not fr_small.empty:
                return fr_small["InsideScore"].idxmin()
            avoid = rem_df[(rem_df["BarrierPrefix"] == "FR") & (rem_df["BarrierNum"].isin([4, 5]))]
            others = rem_df.drop(index=avoid.index, errors="ignore")
            if not others.empty:
                return others["InsideScore"].idxmin()
            return rem_df["InsideScore"].idxmin()

        # 1) LEAD (de-bias FR1; allow FR2/FR3 when warranted)
        rem = g.loc[~g.index.isin(assigned_idx)].copy()
        lead_pool = rem[(rem["BarrierPrefix"] == "FR") & rem["BarrierNum"].notna()].copy()
        if lead_pool.empty:
            lead_idx = rem["InsideScore"].idxmin()
            lead_num = int(g.at[lead_idx, "BarrierNum"]) if pd.notna(g.at[lead_idx, "BarrierNum"]) else None
        else:
            if "Rating" not in lead_pool.columns:
                lead_pool["Rating"] = np.nan
            lead_pool["Rating"] = pd.to_numeric(lead_pool["Rating"], errors="coerce")
            lead_pool["RatingPctLocal"] = _safe_rating_pct_local(lead_pool["Rating"])

            lead_pool = lead_pool.assign(
                LeadSelectScore=[
                    r["InsideScore"]
                    + _lead_gate_adjust(str(r["BarrierPrefix"]), float(r["BarrierNum"]),
                                        float(r["RatingPctLocal"]), float(r.get("AvgBellIndex", 5.0)))
                    for _, r in lead_pool.iterrows()
                ]
            )

            sorted_ls = lead_pool["LeadSelectScore"].sort_values()
            if len(sorted_ls) >= 2:
                gap = float(sorted_ls.iloc[1] - sorted_ls.iloc[0])
                if gap < 0.18:
                    fr1_mask = (lead_pool["BarrierPrefix"] == "FR") & (lead_pool["BarrierNum"] == 1)
                    lead_pool.loc[fr1_mask, "LeadSelectScore"] = (
                        lead_pool.loc[fr1_mask, "LeadSelectScore"] + (0.18 - gap) * 0.6
                    )

            lead_idx = lead_pool["LeadSelectScore"].idxmin()
            lead_num = int(g.at[lead_idx, "BarrierNum"]) if pd.notna(g.at[lead_idx, "BarrierNum"]) else None

        out.append((lead_idx, "Inside", "LEAD"))
        assigned_idx.add(lead_idx)

        # 2) DEATH (wide FR first; avoid FR2)
        rem = g.loc[~g.index.isin(assigned_idx)]
        death_idx = pick_death_candidate(rem)
        out.append((death_idx, "Outside", "DEATH"))
        assigned_idx.add(death_idx)

        # 3) B/LEAD (SR(n) > FR2 if leader FR1 > small FR)
        rem = g.loc[~g.index.isin(assigned_idx)]
        blead_idx = pick_blead_candidate(rem, lead_num if lead_num is not None else 1)
        out.append((blead_idx, "Inside", "B/LEAD"))
        assigned_idx.add(blead_idx)

        # Remaining paired sequence
        for lane, label in sequence_tail:
            rem = g.loc[~g.index.isin(assigned_idx)]
            if rem.empty:
                break
            if lane == "Inside":
                sel_idx = rem["InsideScore"].idxmin()
            else:
                sel_idx = rem["OutsideScore"].idxmin()
            out.append((sel_idx, lane, label))
            assigned_idx.add(sel_idx)

        # Final ordered frame for this race
        seq_df = g.loc[[i for (i, _, _) in out]].copy()
        seq_df["Predicted Lane"] = [lane for (_, lane, _) in out]
        seq_df["PredictedBellLabel"] = [lab for (_, _, lab) in out]
        seq_df["PredictedBellPos"] = np.arange(1, len(seq_df) + 1)
        rows.append(seq_df)

    # Merge new fields back
    new = pd.concat(rows, axis=0).sort_index()
    for c in ["Predicted Lane", "PredictedBellLabel", "PredictedBellPos", "InsideScore", "OutsideScore"]:
        uf[c] = new[c]

    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    # Preview
    lines = []
    def _fmt(r):
        b = str(r.get("Barrier", "")).strip()
        return f"{r.get('Horse','')} [{r.get('PredictedBellLabel','')}]{(' • '+b) if b else ''}"

    for race_id, g2 in uf.groupby(race_key):
        g2 = g2.dropna(subset=["PredictedBellPos"]).sort_values("PredictedBellPos")
        inside = [_fmt(r) for _, r in g2[g2["Predicted Lane"] == "Inside"].iterrows()]
        outside = [_fmt(r) for _, r in g2[g2["Predicted Lane"] == "Outside"].iterrows()]
        lines.append(f"=== {race_id} ===")
        lines.append("Inside lane (pegs):")
        lines.append("  " + "  →  ".join(inside) if inside else "  (none)")
        lines.append("Outside lane (running line):")
        lines.append("  " + "  →  ".join(outside) if outside else "  (none)")
        lines.append("")
    with open("predicted_bell_preview.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("🧭 Constrained map (no 3-wide) applied and preview updated.")



def add_fastest_vdsg_columns_with_date():
    import pandas as pd
    import numpy as np

    try:
        uf = pd.read_csv("upcoming_fields.csv", low_memory=False)
        merged = pd.read_csv("merged_file.csv", low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files: {e}")
        return

    # Safety: ensure key exists
    if "VenDistGaitStart" not in uf.columns:
        print("⚠️ upcoming_fields.csv missing VenDistGaitStart - cannot run fastest VDSG.")
        return
    if "VenDistGaitStart" not in merged.columns:
        print("⚠️ merged_file.csv missing VenDistGaitStart - cannot run fastest VDSG.")
        return

    # ------------------------------------------------------------------
    # Only work on keys that actually exist in upcoming_fields.csv
    # (Biggest speed win if merged_file is huge)
    # ------------------------------------------------------------------
    keys_needed = (
        uf["VenDistGaitStart"]
        .astype(str)
        .replace("nan", np.nan)
        .dropna()
        .unique()
    )

    merged = merged[merged["VenDistGaitStart"].isin(keys_needed)].copy()
    if merged.empty:
        print("⚠️ No merged rows match the VenDistGaitStart keys in upcoming_fields.csv.")
        return

    # Keep only the columns we need (reduces memory + speeds ops)
    needed_cols = {
        "VenDistGaitStart", "Horse", "Date", "BellPosition", "Placing",
        "LeadTime",
        "1st Quarter", "2nd Quarter", "3rd Quarter", "4th Quarter",
        "Race First Half", "Race Last Half", "Race Last Mile", "Race Mile Rate",
    }
    keep = [c for c in merged.columns if c in needed_cols]
    merged = merged[keep].copy()

    # Normalise Placing once
    merged["PlacingNum"] = pd.to_numeric(merged.get("Placing"), errors="coerce")

    # Thresholds
    column_thresholds = {
        "1st Quarter": 25,
        "2nd Quarter": 25,
        "3rd Quarter": 25,
        "4th Quarter": 25,
        "Race First Half": 50,
        "Race Last Half": 50,
        "Race Last Mile": 105,
        "Race Mile Rate": 105,
        "LeadTime": 2,
    }

    # Define what to build (same as your current output)
    columns_to_add = {
        "Fastest VDSG Lead Time": ("LeadTime", "all"),
        "relevant leader Lead Time": ("LeadTime", "leader"),

        "Fastest VDSG First Quarter": ("1st Quarter", "all"),
        "relevant leader First Quarter": ("1st Quarter", "leader"),

        "Fastest VDSG Second Quarter": ("2nd Quarter", "all"),
        "relevant leader Second Quarter": ("2nd Quarter", "leader"),

        "Fastest VDSG Third Quarter": ("3rd Quarter", "all"),
        "relevant winner Third Quarter": ("3rd Quarter", "winner"),

        "Fastest VDSG Fourth Quarter": ("4th Quarter", "all"),
        "relevant winner Fourth Quarter": ("4th Quarter", "winner"),

        "Fastest VDSG First Half": ("Race First Half", "all"),
        "relevant leader First Half": ("Race First Half", "leader"),

        "Fastest VDSG Last Half": ("Race Last Half", "all"),
        "relevant winner Last Half": ("Race Last Half", "winner"),

        "Fastest VDSG Last Mile": ("Race Last Mile", "all"),
        "relevant winner Last Mile": ("Race Last Mile", "winner"),

        "Fastest VDSG Mile Rate": ("Race Mile Rate", "all"),
        "relevant winner Mile Rate": ("Race Mile Rate", "winner"),
    }

    # Pre-convert all metric columns to numeric ONCE
    metric_cols = sorted({col for col, _scope in columns_to_add.values()})
    for col in metric_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    # Helper: compute fastest-per-key for a given scope + column
    def build_fastest_maps(df: pd.DataFrame, key_col: str, value_col: str, threshold: float):
        """
        Returns 3 dicts: value_map, horse_map, date_map
        using groupby idxmin on the numeric column after threshold filtering.
        """
        if value_col not in df.columns:
            return {}, {}, {}

        ok = df[value_col].notna() & (df[value_col] >= threshold)
        sub = df.loc[ok, [key_col, value_col, "Horse", "Date"]].copy()
        if sub.empty:
            return {}, {}, {}

        # idx of min per key
        idx = sub.groupby(key_col, sort=False)[value_col].idxmin()
        best = sub.loc[idx].set_index(key_col)

        return (
            best[value_col].to_dict(),
            best["Horse"].to_dict(),
            best["Date"].to_dict(),
        )

    # Build the 3 scopes once (all/leader/winner)
    df_all = merged
    df_leader = merged[merged.get("BellPosition").astype(str) == "LEAD"]
    df_winner = merged[merged["PlacingNum"] == 1]

    scope_dfs = {
        "all": df_all,
        "leader": df_leader,
        "winner": df_winner,
    }

    # Now fill uf using vectorised mapping (NO uf.apply)
    key_series = uf["VenDistGaitStart"]

    for new_col, (source_col, scope) in columns_to_add.items():
        # Only add if missing (matches your current behaviour)
        if new_col in uf.columns:
            continue

        print(f"➡️ Adding column: {new_col}")
        threshold = column_thresholds.get(source_col, float("-inf"))
        vmap, hmap, dmap = build_fastest_maps(scope_dfs[scope], "VenDistGaitStart", source_col, threshold)

        uf[new_col] = key_series.map(vmap)
        uf[new_col + " Horse"] = key_series.map(hmap)
        uf[new_col + " Date"] = key_series.map(dmap)

    # Save updated file
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("✅ Added the new columns to upcoming_fields.csv")


def add_trial_form_columns(trials_csv="trial_results.csv"):
    """
    Adds 36 columns to upcoming_fields.csv:
      T1* (12 cols), T2* (12 cols), T3* (12 cols)

    For each upcoming_fields row:
      - match by Horse (using clean_horse_name -> lower/trim key)
      - find newest trial(s) for that horse from trial_results.csv
      - if upcoming Date is present, only consider trials with TrialDate <= RaceDate
      - compute T# SinceLR = (T# Date - LR Date) in days
    """
    try:
        uf = pd.read_csv("upcoming_fields.csv")
        tr = pd.read_csv(trials_csv, low_memory=False)
    except Exception as e:
        print(f"⚠️ Failed to read files in add_trial_form_columns: {e}")
        return

    total_rows = len(uf)
    cnt_t1 = 0
    cnt_t2 = 0
    cnt_t3 = 0


    # -------------------------
    # Helpers
    # -------------------------
    def _dt(v):
        # Accept "04/02/2026", "4/02/2026", "2026-02-04", etc.
        return pd.to_datetime(v, errors="coerce", dayfirst=True)

    def _clean_key(s):
        return clean_horse_name(str(s) if s is not None else "").strip().lower()

    # Ensure UF columns exist
    if "Horse" not in uf.columns:
        print("⚠️ upcoming_fields.csv missing 'Horse' column — cannot add trials.")
        return

    # Parse dates WITHOUT overwriting your original Date strings
    uf["_RaceDate_dt"] = _dt(uf.get("Date"))

    # LR Date is created by add_last_run_details_columns() — be defensive
    if "LR Date" in uf.columns:
        uf["_LR_Date_dt"] = _dt(uf["LR Date"])
    else:
        uf["_LR_Date_dt"] = pd.NaT


    tr["Date_dt"] = _dt(tr.get("Date"))
    tr["Horse_key"] = tr.get("Horse", "").astype(str).map(_clean_key)

    uf["Horse_key"] = uf["Horse"].astype(str).map(_clean_key)

    # Sort trials newest first (Date desc, then Race No desc if present)
    if "Race No" in tr.columns:
        tr["_RaceNoInt"] = pd.to_numeric(tr["Race No"], errors="coerce").fillna(0).astype(int)
    else:
        tr["_RaceNoInt"] = 0

    tr = tr.sort_values(["Date_dt", "_RaceNoInt"], ascending=[False, False])

    # Group trials by horse for fast lookup
    trials_by_horse = {}
    for hk, g in tr.groupby("Horse_key", sort=False):
        trials_by_horse[hk] = g

    # Columns to create
    def _ensure_cols(prefix):
        cols = [
            f"{prefix} Venue",
            f"{prefix} Date",
            f"{prefix} Pos",
            f"{prefix} Dist",
            f"{prefix} Mgn",
            f"{prefix} Winner",
            f"{prefix} Start",
            f"{prefix} Rate",
            f"{prefix} Half",
            f"{prefix} Vision",
            f"{prefix} URL",
            f"{prefix} SinceLR",
        ]
        for c in cols:
            if c not in uf.columns:
                uf[c] = ""
        return cols

    for p in ("T1", "T2", "T3"):
        _ensure_cols(p)

    # Fill per row
    for i, row in uf.iterrows():
        hk = row.get("Horse_key", "")
        if not hk:
            continue

        g = trials_by_horse.get(hk)
        if g is None or g.empty:
            continue

        race_date = row.get("_RaceDate_dt")
        # Filter to trials <= race date (if we know the race date)
        if pd.notna(race_date):
            gg = g[g["Date_dt"].notna() & (g["Date_dt"] <= race_date)]
        else:
            gg = g[g["Date_dt"].notna()]

        if gg.empty:
            continue

        top3 = gg.head(3)

        lr_dt = row.get("_LR_Date_dt")

        for rank, (_, t) in enumerate(top3.iterrows(), start=1):
            prefix = f"T{rank}"

            if rank == 1:
                cnt_t1 += 1
            elif rank == 2:
                cnt_t2 += 1
            elif rank == 3:
                cnt_t3 += 1

            t_date = t.get("Date_dt", pd.NaT)

            uf.at[i, f"{prefix} Venue"]  = "" if pd.isna(t.get("Venue")) else str(t.get("Venue"))
            # Force dd/MM/yyyy for T# Date when we can
            if pd.notna(t_date):
                uf.at[i, f"{prefix} Date"] = t_date.strftime("%d/%m/%Y")
            else:
                # fall back to whatever was in the CSV, untouched
                uf.at[i, f"{prefix} Date"] = "" if pd.isna(t.get("Date")) else str(t.get("Date"))
            uf.at[i, f"{prefix} Pos"]    = "" if pd.isna(t.get("Placing")) else str(t.get("Placing"))
            uf.at[i, f"{prefix} Dist"]   = "" if pd.isna(t.get("Distance")) else str(t.get("Distance"))
            uf.at[i, f"{prefix} Mgn"]    = "" if pd.isna(t.get("Margin")) else str(t.get("Margin"))
            uf.at[i, f"{prefix} Winner"] = "" if pd.isna(t.get("TrialWinner")) else str(t.get("TrialWinner"))
            uf.at[i, f"{prefix} Start"]  = "" if pd.isna(t.get("Start")) else str(t.get("Start"))
            uf.at[i, f"{prefix} Rate"]   = "" if pd.isna(t.get("MileRate")) else str(t.get("MileRate"))
            uf.at[i, f"{prefix} Half"]   = "" if pd.isna(t.get("LastHalf")) else str(t.get("LastHalf"))
            uf.at[i, f"{prefix} Vision"] = "" if pd.isna(t.get("VisionURL")) else str(t.get("VisionURL"))
            uf.at[i, f"{prefix} URL"]    = "" if pd.isna(t.get("URL")) else str(t.get("URL"))

            # SinceLR = (trial date - LR date) in days
            if pd.notna(t_date) and pd.notna(lr_dt):
                uf.at[i, f"{prefix} SinceLR"] = str(int((t_date - lr_dt).days))
            else:
                uf.at[i, f"{prefix} SinceLR"] = ""

    # Cleanup helper cols
    uf.drop(columns=["Horse_key", "_LR_Date_dt"], inplace=True, errors="ignore")

    # Save back
    uf.to_csv("upcoming_fields.csv", index=False)
    try:
        uf.to_csv(r"C:/Users/joel/FlutterProjects/harness_app/assets/upcoming_fields.csv", index=False)
    except Exception:
        pass

    print("🧪 Trial form summary:")
    print(f"   Runners total:  {total_rows:,}")
    print(f"   With ≥1 trial:  {cnt_t1:,}")
    print(f"   With ≥2 trials: {cnt_t2:,}")
    print(f"   With ≥3 trials: {cnt_t3:,}")
    print("✅ Added T1/T2/T3 trial-form columns (36) to upcoming_fields.csv")





if __name__ == "__main__":
    main()
    # Prefer the combined gait/start sample builder
    # add_ven_dist_sample()  # optional
    add_ven_dist_gait_start_sample()
    add_benchmark_quarters()

    if RECALC_BARRIER_STATS:
        add_barrier_stats()
        add_barrier_recent_stats()
    else:
        print("⏭️  Skipping barrier stats (RECALC_BARRIER_STATS=False)")

    if RECALC_DRIVER_STATS:
        add_driver_stats()
        add_driver_recent_stats()
    else:
        print("⏭️  Skipping driver stats (RECALC_DRIVER_STATS=False)")

    if RECALC_TRAINER_STATS:
        add_trainer_stats()
        add_trainer_recent_stats()
    else:
        print("⏭️  Skipping trainer stats (RECALC_TRAINER_STATS=False)")

    add_bell_position_stats()
    # --- NEW call for your six columns ---
    add_bell_position_win_pla_counts()
    # NOTE: trainer recent stats are called above when RECALC_TRAINER_STATS=True
    add_aest_and_horse_qty()  # <-- NEW step
    add_horse_win_place_counts()
    add_exp_half()
    add_rating()

    add_market_from_merged_model(
        target_book_pct=125.0,
        method="exp",
        beta=1.50,
        edge_weight=0.50,
        recent_n=5,
        debug_horse="Ideal Bronski",
    )

    try:
        import pandas as pd
        _hdr = pd.read_csv("upcoming_fields.csv", nrows=0).columns.tolist()
        print("DEBUG snapshot call: has Fair Odds?", "Fair Odds" in _hdr)
        print("DEBUG snapshot call: has RaceAnchorFull?", "RaceAnchorFull" in _hdr)
        print("DEBUG snapshot call: has Race Anchor?", "Race Anchor" in _hdr)
    except Exception as e:
        print("DEBUG snapshot call: failed to read header:", e)

    
    # ✅ NEW: lock in what you published before the meeting disappears from upcoming_fields.csv
    snapshot_published_markets(
        uf_csv="upcoming_fields.csv",
        out_csv="published_markets.csv",
    )

    add_lead_summary_columns()
    add_venue_level_stats()
    add_last_run_details_columns()     # <-- NEW
    add_last_media_links()
    add_ven_peg_adj_formula_version()  # ← uses your Excel logic
    add_predicted_bell_positions()
    add_predicted_bell_labels_and_preview()
    add_constrained_bell_map_and_preview()
    add_fastest_vdsg_columns_with_date()
    add_trial_form_columns()


    backup_upcoming_fields_daily(
        src_csv="upcoming_fields.csv",
        backup_dir=r"C:\Users\joel\OneDrive\Trotify",
        keep_last=7
    )

    # Usage example
    backup_python_script_daily(
        src_file=r"C:\harness_scraper\harness_api\scrape_fields.py",  # Replace with the actual path to your script
        backup_dir=r"C:\Users\joel\OneDrive\Trotify\backups",
        keep_last=7  # Keep the last 7 backups
    )
















