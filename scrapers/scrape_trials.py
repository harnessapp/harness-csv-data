# scrape_trials.py
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
from bs4 import BeautifulSoup, Tag

# ============================================================
# CONFIG
# ============================================================
REBUILD_ONLY = False          # (optional) keep, but it will do nothing meaningful without merged_file
DAYS_BACK = 35
DISCOVERY_DAYS = 2
RUN_PHASE1 = True # TEMP: set False to skip phase 1 (meeting discovery)
RUN_VISION_RECOVERY = True   # turn back on later



# ------------------------------------------------------------
# YouTube trial probe — DEBUG (single session)
# ------------------------------------------------------------
RUN_YOUTUBE_PROBE = True
YT_MAX_TRIALS_PER_RUN = 10


# Hard-pin to one session so we can troubleshoot safely
YOUTUBE_TARGET_VENUE = "bendigo"
YOUTUBE_TARGET_DATE  = "02/02/2026"   # dd/mm/yyyy

# Matching controls
YOUTUBE_MIN_SCORE   = 20
YOUTUBE_MAX_RESULTS = 12

# Venue allow-list disabled for debug mode
ALLOWED_YT_VENUES = set()


# ------------------------------------------------------------
# YouTube channel-first caching (NEW)
# ------------------------------------------------------------
YOUTUBE_CACHE_DIR = "yt_cache"
YOUTUBE_CACHE_TTL_HOURS = 72           # re-fetch a venue window every 3 days max
YOUTUBE_MAX_UPLOADS_PER_WINDOW = 200   # safety cap per venue/date window
YOUTUBE_FETCH_PAGE_SIZE = 50           # max 50

# Map venue (lowercase) -> YouTube channel id (or @handle if you later want)
# NOTE: fill these in as you confirm each venue channel.
YOUTUBE_CHANNEL_BY_VENUE = {
    "bendigo": "UCO8yEOp_t97xC-8OcQmfsSA",
    "maryborough": "UCAlYbpz1E9si9iKs1RrWBdQ",
    "ararat": "UCvcNM-SQwkH-2vCjuBp-5kw",
    "ballarat": "UCmrkWX7TXCJHkKSMJJ7KJMw",
    "cobram": "UC5O9IOQUgaGGXCC2juOjtaQ",
    "cranbourne": "UCh9-Bs1Gs_vCX2pDgwCn4lw",
    "echuca": "UCm226fkJgebyW8HolrqEZDg",
    "geelong": "UCH9qgjDvVL2z22hEE2Q3pIQ",
    "hamilton": "UCKhV1oPGxHtzbDxnXR8ljJQ",
    "horsham": "UC1Fms1Aca-aah8GZYre8xgg",
    "kilmore": "UCMylHGOdKGdUXg_ENCKnTuw",
    "mildura": "UC0CpQLxRnT6YDKwn7c2TNbA",
    "ouyen": "UCquzbJ5oltepMB0LL8E72LA",
    "shepparton": "UCWRSiJETCAESbd-56yHJmmA",
    "terang": "UCQ-2vMt8SpIDwkbE1rZ0ofA",
    "warragul": "https://www.youtube.com/user/warragulharness",
}



from pathlib import Path

# ============================================================
# PATHS (GitHub-safe + Windows-safe)
# ============================================================
REPO_ROOT = Path(__file__).resolve().parents[1]  # scrapers/ -> repo root

# The ONE source of truth for trial results location
OUTPUT_FILE = str(REPO_ROOT / "trial_results.csv")

# Keep this alias if your code references TRIAL_RESULTS_CSV anywhere
TRIAL_RESULTS_CSV = OUTPUT_FILE

# Backups: default to enabled locally, disabled in GitHub via env vars
BACKUP_ROOT = os.environ.get("BACKUP_ROOT", r"C:\Users\joel\OneDrive\Trotify")
BACKUPS_ENABLED = os.environ.get("BACKUPS_ENABLED", "1").strip() in ("1", "true", "True", "yes", "YES")

print(f"📁 REPO_ROOT = {REPO_ROOT}", flush=True)
print(f"📄 trial_results OUTPUT_FILE = {OUTPUT_FILE}", flush=True)
print(f"📄 exists? {Path(OUTPUT_FILE).exists()}", flush=True)
if Path(OUTPUT_FILE).exists():
    print(f"📄 size = {Path(OUTPUT_FILE).stat().st_size} bytes", flush=True)



# ============================================================
# MASTER OUTPUT SCHEMA (Phase 1 drives this)
# ============================================================
MASTER_COLS = [
    # --- Phase 1 keys (as produced by parse_race_results results.append({...})) ---
    "RaceAnchor",
    "Venue",
    "Date",
    "Race No",
    "Placing",
    "Horse",
    "Distance",
    "Barrier",
    "Trainer",
    "Driver",
    "Margin",
    "StewardsComments",
    "Comments",
    "LeadTime",
    "TrialWinner",
    "1st Quarter",
    "2nd Quarter",
    "3rd Quarter",
    "4th Quarter",
    "Video Link",
    "RaceAnchorFull",
    "RunnerAnchor",
    "Gait",
    "Start",
    "LastHalf",
    "MileRate",

    # --- Vision columns (must exist for BOTH phases) ---
    "VisionURL",
    "VisionTitle",
    "VisionSource",
    "VisionMatchConfidence",

    # --- Optional: keep traceability when Phase 2 is pitchforked in ---
    "TrialId",
    "TrialNo",
    "TrialClass",
    "Gross Time",
    "Last Mile",
    "Last Quarter",
    "Saddlecloth",
    "Handicap",
    "URL",
]




SHRINK_K = 100                      # (can remove if you want)
IGNORE_WIDTHS = {"TO"}              # (can remove if you want)

print(f"🔧 REBUILD_ONLY={REBUILD_ONLY}")


# Only try suffix variants for specific venues you care about (manually editable)
VENUE_SUFFIX_OVERRIDES = {
    "AP": ["", "T", "N", "D"],
    "AY": ["", "T", "N", "D"],
    "BY": ["", "T", "N", "D"],
    "EY": ["", "T", "N", "D"],
    "NR": ["", "T", "N", "D"],
    "PK": ["", "T", "N", "D"],
    "RE": ["", "T", "N", "D"],
    "UG": ["", "T", "D"],
}




def build_trial_id_urls_from_csv(
    csv_path: str,
    back: int = 5,
    forward: int = 20,
) -> list[str]:

    if not os.path.exists(csv_path):
        return []

    df = pd.read_csv(csv_path, dtype=str, low_memory=False)

    if "RaceAnchor" not in df.columns:
        return []

    anchors = df["RaceAnchor"].fillna("").astype(str)

    existing_ids = (
        anchors.str.extract(r"TRIAL(\d+)", expand=False)
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if not existing_ids:
        return []

    max_id = max(existing_ids)
    start_id = max(1, max_id - back)
    end_id = max_id + forward

    # Full window
    window_ids = list(range(start_id, end_id + 1))

    # Only scrape ones NOT already in CSV
    ids_to_scrape = [tid for tid in window_ids if tid not in existing_ids]

    urls = [
        f"https://www.harness.org.au/racing/trials/trial-results/?trialId={tid}"
        for tid in ids_to_scrape
    ]

    print(
        f"🎯 Window {start_id}-{end_id} | "
        f"{len(existing_ids)} existing | "
        f"{len(urls)} new to scrape"
    )

    return urls



# Build the list you’ll scrape each run
TRIAL_ID_URLS = build_trial_id_urls_from_csv(TRIAL_RESULTS_CSV, back=5, forward=20)



TRIAL_RESULTS_CSV = r"C:\harness_scraper\harness_api\trial_results.csv"

# Build the list you’ll scrape each run (max-5 .. max+20)
TRIAL_ID_URLS = build_trial_id_urls_from_csv(TRIAL_RESULTS_CSV, back=5, forward=20)

# Optional: add any manual “must scrape” trialIds here
MANUAL_TRIAL_ID_URLS = [
    # "https://www.harness.org.au/racing/trials/trial-results/?trialId=22560",
]

# Merge + de-dupe + sort by trialId
def _trial_id(u: str) -> int:
    m = re.search(r"trialId=(\d+)", u)
    return int(m.group(1)) if m else -1

TRIAL_ID_URLS = sorted(set(TRIAL_ID_URLS + MANUAL_TRIAL_ID_URLS), key=_trial_id)

print(f"🧪 Phase 2 (trialId list): {len(TRIAL_ID_URLS)} URLs")
if TRIAL_ID_URLS:
    print(f"   first={_trial_id(TRIAL_ID_URLS[0])} last={_trial_id(TRIAL_ID_URLS[-1])}")


# Phase 2 trial metadata
TRIAL_META = {}


TRIAL_META.update({
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22555": {
        "Venue": "Bendigo",
        "State": "VIC",
        "Date": "02/02/2026"
    }
})



TRIAL_META = {
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22557": {"Venue": "Maryborough", "State": "VIC", "Date": "04/02/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22555": {"Venue": "Bendigo", "State": "VIC", "Date": "02/02/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22554": {"Venue": "Gawler", "State": "SA", "Date": "01/02/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22556": {"Venue": "Kyabram", "State": "VIC", "Date": "01/02/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22549": {"Venue": "Bacchus Marsh", "State": "VIC", "Date": "31/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22548": {"Venue": "Mount Gambier", "State": "SA", "Date": "28/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22547": {"Venue": "Globe Derby", "State": "SA", "Date": "25/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22545": {"Venue": "Echuca", "State": "VIC", "Date": "25/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22546": {"Venue": "Maryborough", "State": "VIC", "Date": "25/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22544": {"Venue": "Bacchus Marsh", "State": "VIC", "Date": "24/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22543": {"Venue": "Shepparton", "State": "VIC", "Date": "22/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22538": {"Venue": "Ballarat", "State": "VIC", "Date": "20/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22541": {"Venue": "Terang", "State": "VIC", "Date": "20/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22542": {"Venue": "Globe Derby", "State": "SA", "Date": "19/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22535": {"Venue": "Bendigo", "State": "VIC", "Date": "19/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22537": {"Venue": "Geelong", "State": "VIC", "Date": "19/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22536": {"Venue": "Mildura", "State": "VIC", "Date": "19/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22534": {"Venue": "Kyabram", "State": "VIC", "Date": "18/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22533": {"Venue": "Maryborough", "State": "VIC", "Date": "18/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22531": {"Venue": "Cobram", "State": "VIC", "Date": "15/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22532": {"Venue": "Mount Gambier", "State": "SA", "Date": "14/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22530": {"Venue": "Bendigo", "State": "VIC", "Date": "12/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22528": {"Venue": "Maryborough", "State": "VIC", "Date": "12/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22529": {"Venue": "Globe Derby", "State": "SA", "Date": "10/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22525": {"Venue": "Bacchus Marsh", "State": "VIC", "Date": "10/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22521": {"Venue": "Shepparton", "State": "VIC", "Date": "08/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22522": {"Venue": "Terang", "State": "VIC", "Date": "06/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22518": {"Venue": "Globe Derby", "State": "SA", "Date": "05/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22517": {"Venue": "Bendigo", "State": "VIC", "Date": "05/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22524": {"Venue": "Horsham", "State": "VIC", "Date": "05/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22523": {"Venue": "Mildura", "State": "VIC", "Date": "05/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22516": {"Venue": "Mount Gambier", "State": "SA", "Date": "04/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22515": {"Venue": "Kyabram", "State": "VIC", "Date": "04/01/2026"},
    "https://www.harness.org.au/racing/trials/trial-results/?trialId=22520": {"Venue": "Maryborough", "State": "VIC", "Date": "04/01/2026"},
}




# ------------------------------------------------------------
# VIC trialId pages are a different HTML structure.
# Start in PROBE mode: print table headers so we can map fields safely.
# ------------------------------------------------------------
TRIALID_PROBE_ONLY = True



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

# --- PHASE 1: Discovery (targeted re-check of existing meeting codes for a time frame loop) ---
def _get_date_ranges(start_date, range_1_days, range_2_days):
    """
    start_date should be 'yesterday' if you want windows relative to yesterday.

    Range 1: start_date, start_date-1, ... for range_1_days
    Range 2: the NEXT block older than range 1, for range_2_days
             i.e. starts at start_date-range_1_days and goes back.
    """
    range_1_dates = [
        (start_date - timedelta(days=delta)).strftime("%d%m%y")
        for delta in range(range_1_days)
    ]

    range_2_dates = [
        (start_date - timedelta(days=delta)).strftime("%d%m%y")
        for delta in range(range_1_days, range_1_days + range_2_days)
    ]

    return range_1_dates, range_2_dates


def phase_1_discovery(venue_code_map):
    print("🧭 Phase 1 Discovery: 2-day full scan + 5-day targeted recheck...")

    discovered_meetings = set()

    # Yesterday as anchor
    anchor = datetime.today() - timedelta(days=1)

    # ✅ Your intended windows:
    # Range 1: yesterday + day before (2 days)
    # Range 2: next 5 days back (3–7 days ago)
    range_1_dates, range_2_dates = _get_date_ranges(
        start_date=anchor,
        range_1_days=2,
        range_2_days=5
    )

    print(f"🗓️ Full venue scan dates (2): {sorted(range_1_dates)}")
    print(f"🗓️ Targeted recheck dates (5): {sorted(range_2_dates)}")


    # Process the first range (2 days) from scrape
    print(f"Processing first time frame (2 days):")
    for date_str in range_1_dates:
        for venue_name, venue_code in venue_code_map.items():
            suffixes = VENUE_SUFFIX_OVERRIDES.get(venue_code, [""])
            for suf in suffixes:
                # Build the unique meeting identifier for checking
                meeting_id = f"{venue_code}{date_str}{suf}"

                # Skip if this meeting has already been processed
                if meeting_id in discovered_meetings:
                    continue

                results = scrape_meeting_results(venue_code, date_str, suffix=suf)
                if results is None:
                    print("🛑 Stopping scrape due to rate limit. Try again later.")
                    sys.exit(0)
                if results:
                    all_results.extend(results)
                    discovered_meetings.add(meeting_id)
                    time.sleep(0.25 + random.uniform(0.0, 0.25))
                else:
                    time.sleep(1.2 + random.uniform(0.0, 1.0))

    # Process the second range (5 days) from CSV
    print(f"Processing second time frame (5 days):")
    targets = _existing_meeting_codes_for_dates(OUTPUT_FILE, range_2_dates)

    if not targets:
        print("🚨 WARNING: No existing meeting codes found for the recheck window (5 days).")
        print("🚨 This should not happen — check OUTPUT_FILE path, RaceAnchor format, and date parsing.")
    else:
        print(f"🎯 Target meetings to re-check: {len(targets)}")
        for (venue_code, date_str, suf) in targets:
            meeting_id = f"{venue_code}{date_str}{suf}"

            if meeting_id in discovered_meetings:
                continue

            results = scrape_meeting_results(venue_code, date_str, suffix=suf)
            if results is None:
                print("🛑 Stopping scrape due to rate limit. Try again later.")
                sys.exit(0)

            if results:
                all_results.extend(results)
                discovered_meetings.add(meeting_id)

            time.sleep(random.uniform(1.2, 2.2))



        print(f"Phase 1 Discovery Complete: {len(all_results)} results collected.")


def get_largest_trial_id(output_file):
    """
    This function checks the trial_results.csv for the largest TrialId.
    It returns the largest trialId found.
    """
    try:
        # Read the CSV into a DataFrame
        df = pd.read_csv(output_file)
        
        # Extract the TrialId from the RaceAnchor column
        df['TrialId'] = df['RaceAnchor'].str.extract(r"TRIAL(\d+)").astype(int)
        
        # Find the maximum TrialId
        max_trial_id = df['TrialId'].max()
        return max_trial_id
    except Exception as e:
        print(f"Error reading {output_file}: {e}")
        return None

def generate_trial_urls(largest_trial_id, num_range=10):
    """
    This function generates trial URLs for a range of trialId before and after the given largest_trial_id.
    """
    trial_urls = []
    # Generate trial IDs before and after the largest_trial_id
    for trial_id in range(largest_trial_id - num_range, largest_trial_id + num_range + 1):
        if trial_id > 0:  # Ensure valid trial IDs (positive numbers)
            url = f"https://www.harness.org.au/racing/trials/trial-results/?trialId={trial_id}"
            trial_urls.append(url)
    
    return trial_urls

def _score_candidate(title, venue, trial_no, ddmmyyyy, distance, start):
    """
    Calculate a match score for a YouTube video based on its title.
    
    The score is calculated based on how well the title matches the expected details.
    For simplicity, this example uses a basic scoring system based on keyword presence.
    """
    score = 0

    # Normalize the title and query components
    title = title.lower()
    venue = venue.lower()
    trial_no = str(trial_no).lower()
    ddmmyyyy = ddmmyyyy.lower()
    distance = distance.lower()
    start = start.lower()

    # Check for matching keywords
    if venue in title:
        score += 5
    if trial_no in title:
        score += 3
    if ddmmyyyy in title:
        score += 2
    if distance in title:
        score += 1
    if start in title:
        score += 1

    return score



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


def probe_youtube_trials(rows, max_results=12, verbose=False):
    """
    Populate VisionURL/VisionTitle/VisionSource/VisionMatchConfidence for trials by probing YouTube.

    Designed to run AFTER Phase 1 + Phase 2 have been combined (i.e. it can work whether TrialNo exists or not).
    It ONLY targets rows where VisionURL is blank.

    Requirements:
      - env var YOUTUBE_API_KEY must be set (YouTube Data API v3)
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print("⚠️ YOUTUBE_API_KEY not set — skipping YouTube probe")
        return

    # --- DEBUG pin (set to None to disable) ---
    YT_DEBUG_VENUE = None
    YT_DEBUG_DATE  = None

    # ---------------- helpers ----------------
    def _norm(s: str) -> str:
        s = (s or "").lower()
        s = s.replace("&amp;", "&")
        s = re.sub(r"[^a-z0-9\s]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _digits(s: str) -> str:
        return re.sub(r"[^\d]", "", (s or ""))

    def _parse_date_ddmmyyyy(s: str) -> str:
        s = (s or "").strip()
        # allow 4/2/2026 or 04/02/2026
        try:
            dt = datetime.strptime(s, "%d/%m/%Y")
            return dt.strftime("%d/%m/%Y")
        except Exception:
            try:
                dt = datetime.strptime(s, "%d/%m/%y")
                return dt.strftime("%d/%m/%Y")
            except Exception:
                # last resort: return as-is
                return s

    def _query_date_tokens(ddmmyyyy: str) -> str:
        # we query with "dd mm yy" because that tends to appear in YT titles
        try:
            dt = datetime.strptime(ddmmyyyy, "%d/%m/%Y")
            return dt.strftime("%d %m %y")
        except Exception:
            return ""

    def _trial_no_from_row(r: dict):
        # Prefer TrialNo (Phase 2), else Race No (Phase 1)
        for k in ("TrialNo", "Race No", "RaceNo", "Race"):
            v = r.get(k, "")
            if v is None:
                continue
            t = str(v).strip()
            if t == "":
                continue
            if t.isdigit():
                return int(t)
            # sometimes "1A" etc — ignore
        return None

    def _youtube_search(q: str, venue: str, trial_date: str):
        """
        Now includes filtering by venue-specific YouTube channel and video upload date (within 6 days of trial date).
        """
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            print("⚠️ YOUTUBE_API_KEY not set — skipping YouTube probe")
            return None, None

        # Get the channel ID from the venue code
        channel_id = YOUTUBE_CHANNEL_BY_VENUE.get(venue.lower())
        if not channel_id:
            print(f"⚠️ No YouTube channel for venue {venue} — skipping YouTube search")
            return None, None

        # Prepare search parameters
        params = {
            "part": "snippet,contentDetails",
            "q": q,
            "channelId": channel_id,  # Restrict the search to this channel
            "type": "video",
            "maxResults": 12,
            "key": api_key,
        }

        try:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                timeout=15,
            )

            if resp.status_code != 200:
                return None, resp

            data = resp.json()

            # Now filter the results by the upload date (within 6 days of the trial date)
            valid_videos = []
            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId")
                if not video_id:
                    continue

                # Extract the video upload date
                upload_date = item.get("snippet", {}).get("publishedAt")
                if upload_date:
                    upload_date = datetime.strptime(upload_date, "%Y-%m-%dT%H:%M:%SZ")
                    trial_date_obj = datetime.strptime(trial_date, "%d/%m/%Y")

                    # Check if the video was uploaded within 6 days before or after the trial date
                    if abs((upload_date - trial_date_obj).days) <= 6:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        valid_videos.append((video_url, item.get("snippet", {}).get("title", "")))

            return valid_videos, resp

        except requests.exceptions.RequestException as e:
            print(f"⚠️ YouTube API request failed: {e}")
            return None, None  # Return None in case of request failure


    # ---------------- select eligible rows ----------------
    eligible = []
    for r in rows:
        # Only fill blanks — never overwrite existing VisionURL
        vurl_raw = r.get("VisionURL", "")
        vurl = str("" if vurl_raw is None else vurl_raw).strip()
        if vurl and vurl.lower() != "nan":
            continue


        venue = str(r.get("Venue", "") or "").strip().lower()

        # Existing allow-list behaviour (keep it)
        if ALLOWED_YT_VENUES and venue and (venue not in ALLOWED_YT_VENUES):
            continue

        # DEBUG: hard-pin to one venue/date (safe; YouTube only)
        if YT_DEBUG_VENUE and venue != YT_DEBUG_VENUE:
            continue

        date_raw = str(r.get("Date", "") or "").strip()
        ddmmyyyy = _parse_date_ddmmyyyy(date_raw)
        if YT_DEBUG_DATE and ddmmyyyy != YT_DEBUG_DATE:
            continue

        tn = _trial_no_from_row(r)
        if tn is None:
            continue

        eligible.append(r)

    if not eligible:
        print("ℹ️ No eligible blank VisionURL rows for YouTube probe")
        return

    # group by (RaceAnchor, trial_no) to avoid repeating API calls
    groups = {}
    for r in eligible:
        race_anchor = str(r.get("RaceAnchor", "") or "").strip()
        trial_no = _trial_no_from_row(r)
        if trial_no is None:
            continue
        groups.setdefault((race_anchor, trial_no), []).append(r)

    # --- NEW: cap trials per run to protect YouTube quota ---
    if YT_MAX_TRIALS_PER_RUN and len(groups) > YT_MAX_TRIALS_PER_RUN:
        limited_keys = sorted(groups.keys())[:YT_MAX_TRIALS_PER_RUN]
        groups = {k: groups[k] for k in limited_keys}

    print(f"🔍 YouTube probe: {len(eligible)} runners across {len(groups)} trials")

    matched = 0

    for (race_anchor, trial_no), group_rows in groups.items():
        r0 = group_rows[0]

        venue_name = str(r0.get("Venue", "") or "").strip()
        date_raw = str(r0.get("Date", "") or "").strip()
        ddmmyyyy = _parse_date_ddmmyyyy(date_raw)
        date_str = _query_date_tokens(ddmmyyyy)

        distance = str(r0.get("Distance", "") or "").strip()
        start = str(r0.get("Start", "") or "").strip()

        q = f"{venue_name} Harness Trial {trial_no}"
        if date_str:
            q += f" {date_str}"
        if distance:
            q += f" {distance}"
        if start:
            q += f" {start}"

        # Pass the trial_date (ddmmyyyy) to _youtube_search
        data, resp = _youtube_search(q, venue_name, ddmmyyyy)  # Add trial_date here

        if data is None:
            print(f"⚠️ YouTube API error for {venue_name} Trial {trial_no} ({race_anchor}) — No response.")
            continue

        items = data.get("items", []) or []

        best = None  # (score, url, title)
        scored = []

        for it in items:
            title = it.get("snippet", {}).get("title", "") or ""
            vid = it.get("id", {}).get("videoId", "")
            if not vid:
                continue
            url = f"https://www.youtube.com/watch?v={vid}"

            sc = _score_candidate(
                title=title,
                venue=venue_name,
                trial_no=trial_no,
                ddmmyyyy=ddmmyyyy,
                distance=distance,
                start=start,
            )
            scored.append((sc, url, title))
            if best is None or sc > best[0]:
                best = (sc, url, title)

        vision_url = ""
        vision_title = ""
        vision_score = ""

        # Threshold: require trial number + at least some other signal
        if best and best[0] >= 0:
            vision_url = best[1]
            vision_title = best[2]
            vision_score = str(best[0])

        for rr in group_rows:
            rr["VisionURL"] = vision_url
            rr["VisionTitle"] = vision_title
            rr["VisionSource"] = "YouTube" if vision_url else (rr.get("VisionSource", "") or "")
            rr["VisionMatchConfidence"] = vision_score

        if vision_url:
            matched += 1
            print(f"✅ {venue_name} Trial {trial_no} — matched ({vision_score})")
            if verbose:
                print(f"   {vision_title}")
                print(f"   {vision_url}")
        else:
            print(f"❌ {venue_name} Trial {trial_no} — no confident match (query: {q})")
            if verbose and scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                print("   Top candidates:")
                for sc, url, title in scored[:8]:
                    print(f"   • [{sc:>3}] {title}")
                    print(f"     {url}")

    print(f"🎯 YouTube matches: {matched}/{len(groups)} trials")



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

def _clean_person_name(s: str) -> str:
    if not s:
        return s
    # remove any trailing parenthetical like "(C,cl)", "(C)", "(cl)" incl. surrounding spaces
    return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()



import re

def _extract_trial_meta_from_page_text(full_text: str) -> dict:
    """
    Returns dict keyed by trial number (int) with per-trial fields like:
      StartType, ClassText, Distance, GrossTime, MileRate, Margins, LastMile, LastHalf, LastQuarter
    Works on the flattened page text that contains:
      "Trial 1 MOBILE START ... Gross Time: ... Mile Rate: ... Margins: ... Last Mile: ... Last Half: ... Last Quarter: ..."
    """
    if not full_text:
        return {}

    # Normalize spacing, including handling non-breaking spaces (&nbsp;)
    t = str(full_text).replace("\u00A0", " ")  # Convert non-breaking spaces to regular spaces
    t = re.sub(r"\s+", " ", t).strip()

    # Extract venue and date from the <h2> tag (e.g., "MARYBOROUGH Sunday, 15 February 2026")
    venue_date_match = re.search(r"<h2>(.*?)</h2>", t)
    venue = None
    date = None

    if venue_date_match:
        venue_date_text = venue_date_match.group(1)
        # Split the text by the first occurrence of the date pattern
        venue_date_parts = re.split(r"(\d{1,2}\s\w+\s\d{4})", venue_date_text)
        
        if len(venue_date_parts) > 1:
            venue = venue_date_parts[0].strip()  # Venue is before the date part
            date = venue_date_parts[1].strip()   # Date is after the venue part

    # Split into Trial blocks
    pattern = re.compile(r"(Trial\s+(\d+)\s+.*?)(?=\s+Trial\s+\d+\s+|$)", re.IGNORECASE)
    blocks = list(pattern.finditer(t))

    meta = {}
    for m in blocks:
        block = m.group(1)
        trial_no = int(m.group(2))

        # Start type
        start_type = ""
        if re.search(r"\bMOBILE\s+START\b", block, re.IGNORECASE):
            start_type = "Mobile"
        elif re.search(r"\bSTANDING\s+START\b", block, re.IGNORECASE):
            start_type = "Stand"

        # Distance (first occurrence of "#### METRES")
        dist = ""
        m_dist = re.search(r"\b(\d{3,4})\s*METRES\b", block, re.IGNORECASE)
        if m_dist:
            dist = m_dist.group(1).strip()

        # "Class: ..." (everything after Class: up to distance)
        class_text = ""
        m_class = re.search(r"\bClass:\s*(.*?)(?=\s+\d{3,4}\s*METRES\b)", block, re.IGNORECASE)
        if m_class:
            class_text = m_class.group(1).strip()

        # Per-trial summary fields (these are the ones you want)
        def _grab(label, until_label=None):
            if until_label:
                r = re.search(rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\s+\b{re.escape(until_label)}\s*:|$)", block, re.IGNORECASE)
            else:
                r = re.search(rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\s+\b[A-Za-z ]+\s*:|$)", block, re.IGNORECASE)
            return r.group(1).strip() if r else ""

        gross_time = _grab("Gross Time", "Mile Rate")
        mile_rate  = _grab("Mile Rate", "Margins")
        margins    = _grab("Margins", "Last Mile")
        last_mile  = _grab("Last Mile", "Last Half")
        last_half  = _grab("Last Half", "Last Quarter")
        last_qtr   = _grab("Last Quarter")

        # Clean up a couple of common punctuation issues
        gross_time = gross_time.replace(".", ":") if re.fullmatch(r"\d+\.\d+\.\d+", gross_time) else gross_time
        mile_rate = mile_rate.replace(".", ":") if re.fullmatch(r"\d+\.\d+\.\d+", mile_rate) else mile_rate

        meta[trial_no] = {
            "TrialNo": trial_no,
            "StartType": start_type,
            "ClassText": class_text,
            "Distance": dist,
            "GrossTime": gross_time,
            "MileRateText": mile_rate,
            "MarginsText": margins,
            "LastMileText": last_mile,
            "LastHalfText": last_half,
            "LastQuarterText": last_qtr,
            "Venue": venue,
            "Date": date,
        }

    return meta



def _page_text_for_trials(soup: BeautifulSoup) -> str:
    """
    Best-effort: pull the page text in a way that retains the 'Trial X ... Gross Time ...' sequence.
    """
    # Often the meaningful content is inside the main content area; but safest is whole page text.
    return soup.get_text(" ", strip=True)


# --- margin token mapping (treat small margins as 1) ---
_SMALL_MARGIN_TOKENS = {
    "NOSE": 1.0, "NS": 1.0,
    "SHHD": 1.0, "S/HD": 1.0, "SH": 1.0,
    "HFHD": 1.0, "H/HD": 1.0,
    "HD": 1.0, "HEAD": 1.0,
    "NK": 1.0, "NECK": 1.0,
    "HFNK": 1.0, "H/NK": 1.0,
}

def _parse_margins_list(margins_text: str) -> list[float]:
    """
    Takes race-level Margins text like:
      "1 x 6", "2x3", "2x3x2x7x6", "hd x 3", "1/2 hd x 3"
    Returns a list of leg margins as floats: [1.0, 6.0], etc.
    Anything like hd/nk/head/etc -> 1.0
    Ignores blanks/unparseables.
    """
    if margins_text is None:
        return []

    s = str(margins_text).strip().upper()
    if not s or s in ("NAN", "NONE", "NULL"):
        return []

    # normalise separators to 'x'
    s = s.replace("\u00A0", " ")
    s = re.sub(r"\s*×\s*", "x", s)          # times symbol
    s = re.sub(r"\s*[X]\s*", "x", s)        # X
    s = re.sub(r"\s*-\s*", "x", s)          # sometimes "2-3" style (rare)
    s = re.sub(r"\s+", " ", s).strip()

    # split on x, allowing "1 x 6" or "2x3x2"
    parts = [p.strip() for p in re.split(r"\s*x\s*", s) if p.strip()]
    out: list[float] = []

    for p in parts:
        # handle fractions like "1/2 HD"
        p2 = p.replace(" ", "")
        # token-only cases
        if p2 in _SMALL_MARGIN_TOKENS:
            out.append(_SMALL_MARGIN_TOKENS[p2])
            continue

        # "1/2HD", "1/2", etc -> treat as 1
        if re.search(r"\d+\s*/\s*\d+", p):
            out.append(1.0)
            continue

        # cases like "HD" embedded (e.g. "0.5HD") -> treat as 1
        if any(tok in p2 for tok in _SMALL_MARGIN_TOKENS):
            out.append(1.0)
            continue

        # numeric (allow decimals)
        m = re.search(r"(\d+(?:\.\d+)?)", p2)
        if m:
            try:
                out.append(float(m.group(1)))
            except:
                pass

    return out

def _margin_for_placing(placing_raw: str, margins_raw: str) -> str:
    """
    Returns:
      - "0" for placing 1
      - cumulative numeric margin as string for placings we can calculate
      - "<cum>+" for placings beyond the provided margins list
      - "" if placing isn't a number (SCR, D, R etc)
    Rules:
      - separators: x, ×, -, commas, spaces
      - words like hd/nk/neck/sh/short treated as 1
    """
    # placing must be numeric
    try:
        p = int(str(placing_raw).strip())
    except Exception:
        return ""

    if p <= 1:
        return "0"

    s = (margins_raw or "").strip().lower()
    if not s:
        return ""

    # normalise separators
    s = s.replace("×", "x").replace("-", "x")
    s = re.sub(r"\s*x\s*", " x ", s)  # space around x
    tokens = re.split(r"[,\s]+", s)

    vals = []
    for tok in tokens:
        if tok in {"x", "", "m"}:
            continue

        # treat common "small" margins as 1
        if tok in {"hd", "head", "nk", "neck", "sh", "short", "nose"}:
            vals.append(1)
            continue

        # strip trailing 'm' if present e.g. "3m"
        tok2 = tok.replace("m", "")

        # numeric?
        if re.fullmatch(r"\d+", tok2):
            vals.append(int(tok2))
            continue

        # sometimes "1/2" etc — just treat as 1 for now
        if "/" in tok2:
            vals.append(1)
            continue

    # vals represent margins between 1-2, 2-3, 3-4, ...
    # placing=2 uses vals[0], placing=3 uses vals[0]+vals[1], etc
    need = p - 1  # how many "steps" behind the winner
    if not vals:
        return ""

    if need <= len(vals):
        return str(sum(vals[:need]))
    else:
        return f"{sum(vals)}+"


def _strip_footer_disclaimer(s: str) -> str:
    if not s:
        return ""
    # Cut off any appended site/footer junk
    cut_markers = [
        "DISCLAIMER:",
        "DISCLAIMER",
        "Help Advertise",
        "Privacy",
        "Terms Of Use",
        "Contact Us",
        "Powered by",
        "Racing Information Services",
        "Â©",  # occasional encoding noise
        "©",
    ]
    out = str(s)
    upper = out.upper()
    best = None
    for m in cut_markers:
        pos = upper.find(m.upper())
        if pos != -1:
            best = pos if best is None else min(best, pos)
    if best is not None:
        out = out[:best]
    return out.strip()



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
    out["BellPosition"] = out["BellPosition"].astype(str).str.strip()

    # Half Distance: if blank/NaN, fill from BellPosition map
    hd = pd.to_numeric(out["Half Distance"], errors="coerce")
    hd_missing = hd.isna()
    if hd_missing.any():
        mapped = out.loc[hd_missing, "BellPosition"].map(_HALF_DIST_MAPPING)
        out.loc[hd_missing, "Half Distance"] = mapped

    out["Half Distance"] = pd.to_numeric(out["Half Distance"], errors="coerce")

    # Width: if blank, map from BellPosition
    width_s = out["Width"].astype(str).str.strip().str.upper()
    width_missing = (width_s.eq("")) | (width_s.eq("NAN")) | (width_s.isna())
    if width_missing.any():
        mapped_w = out.loc[width_missing, "BellPosition"].map(_WIDTH_MAPPING)
        out.loc[width_missing, "Width"] = mapped_w
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



# --- VENUE CODE MAP ---
venue_code_map = {
    "Armidale": "AE",
    "Albury": "AL",
    "Albion Park": "AP",
    "Ararat": "AR",
    "Gawler": "AW",
    "Albany": "AY",
    "Ballarat": "BA",
    "Blayney": "BB",
    "Byford": "BD",
    "Burnie": "BE",
    "Bridgetown": "BG",
    "Bathurst": "BH",
    "Bankstown": "BK",
    "Bendigo": "BN",
    "Broken Hill": "BR",
    "Boort": "BT",
    "Busselton": "BU",
    "Bunbury": "BY",
    "Cowra": "CA",
    "Canberra": "CB",
    "Charlton": "CH",
    "Carrick": "CK",
    "Coolamon": "CL",
    "Cobram": "CO",
    "Cranbourne": "CR",
    "Collie": "CX",
    "Darling Downs at Warwick": "DJ",
    "Dubbo": "DU",
    "Devonport": "DV",
    "Echuca": "EC",
    "Hobart": "EH",
    "Lockyer": "EQ",
    "Eugowra": "EU",
    "Wagga at Riverina Paceway": "EY",
    "Forbes": "FB",
    "Swan Hill": "FD",
    "Globe Derby Park": "GD",
    "Geelong": "GE",
    "Gloucester Park": "GP",
    "Griffith": "GR",
    "Gunbower": "GU",
    "Hamilton": "HM",
    "Horsham": "HS",
    "Kilcoy": "IJ",
    "Birchip": "IR",
    "Junee": "JU",
    "Kilmore": "KI",
    "Kapunda": "KP",
    "Leeton": "LE",
    "Goulburn": "LM",
    "Launceston": "LN",
    "Maitland": "MD",
    "Tabcorp Pk Menangle": "ME",
    "Mount Gambier": "MG",
    "Maryborough": "MH",
    "Mildura": "ML",
    "Melton": "MX",
    "Narrabri": "NA",
    "Narrogin": "NG",
    "Northam": "NM",
    "Newcastle": "NR",
    "Ouyen": "OU",
    "Pinjarra": "PA",
    "Nswhrc at Tabcorp Pk Menangle": "PC",
    "Penrith": "PE",
    "Parkes": "PK",
    "Port Pirie": "PP",
    "Redcliffe": "RE",
    "St Arnaud": "SA",
    "Scottsdale": "SC",
    "Shepparton": "SP",
    "Strathalbyn": "ST",
    "Stawell": "SW",
    "Tamworth": "TA",
    "Terang": "TE",
    "Temora": "TM",
    "Marburg": "UG",
    "Victor Harbor": "VH",
    "Wagin": "WA",
    "Wedderburn": "WD",
    "West Wyalong": "WE",
    "Wangaratta": "WN",
    "Wanneroo": "WQ",
    "Warragul": "WR",
    "Williams": "WS",
    "Yarra Valley": "YG",
    "Young": "YU",
    "Central Wheatbelt": "ZO",
}

def scrape_meeting_results(venue_code, date_str, suffix=""):
    venue_url = f"https://www.harness.org.au/racing/fields/race-fields/?mc={venue_code}{date_str}{suffix}"


    try:
        response = requests.get(venue_url, timeout=15)

        # -----------------------------
        # Rate limit / access denied
        # -----------------------------
        if response.status_code in (429, 403):
            retry_after = response.headers.get("Retry-After")
            wait_s = 60
            if retry_after and str(retry_after).strip().isdigit():
                wait_s = int(retry_after)

            print(f"🚫 {venue_code}{date_str} — RATE LIMITED (HTTP {response.status_code}). Stopping for {wait_s}s.")
            time.sleep(wait_s)
            return None

        if response.status_code != 200:
            print(f"⚠️ {venue_code}{date_str}{suffix} — HTTP {response.status_code}")
            return []

        html = response.text


        if "rate limit exceeded" in html.lower() or "access denied" in html.lower():
            print(f"🚫 {venue_code}{date_str} — RATE LIMITED (body). Stopping for 60s.")
            time.sleep(60)
            return None

        soup = BeautifulSoup(html, "html.parser")

        h2_tag = soup.find("h2")
        if not h2_tag:
            return []

        h2_text = h2_tag.get_text(strip=True)
        venue = h2_text.split("(")[0].strip()
        meeting_time = "Unknown"
        if "(" in h2_text and ")" in h2_text:
            meeting_time = h2_text.split("(")[1].split(")")[0]

        results = parse_race_results(
            soup,
            venue,
            date_str,
            venue_code,
            meeting_time,
            suffix=suffix,
            page_url=venue_url,   # ✅ NEW: keep traceable URL
        )



        if results:
            print(
                f"✅ {venue_code}{date_str} — {venue} "
                f"({meeting_time}) — races={len(set(r['Race No'] for r in results))}, "
                f"runners={len(results)}"
            )

        time.sleep(random.uniform(3.5, 6.0))
        return results

    except Exception as e:
        print(f"❌ Failed {venue_code}{date_str}: {e}")
        return []




def parse_race_results(soup, venue, date_str, venue_code, meeting_time, suffix="", page_url=""):






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

                if starting_price:
                    continue

                stewards_comments = ""
                comments = ""
                stewards_td = row.find("td", class_="stewards_comments")
                if stewards_td:
                    stewards_span = stewards_td.find("span", class_="stewardsTooltip")
                    if stewards_span:
                        stewards_comments = stewards_span.get("title", "").strip()
                        comments = stewards_span.get_text(strip=True)



                # ✅ Per-race photo/video (scope to THIS race, not whole page)
                photo_tag = race_block.select_one("td.photoFinish a[href]")
                photo_link = photo_tag["href"].strip() if photo_tag and photo_tag.get("href") else ""

                video_tag = race_block.select_one("td.lastLapReplay a[href]")
                video_link = video_tag["href"].strip() if video_tag and video_tag.get("href") else ""


                # suffix is already passed into parse_race_results(..., suffix=...)
                suffix = (suffix or "").strip()

                race_anchor = f"{venue_code}{date_str}{suffix}"
                race_anchor_full = f"{race_anchor}_R{race_number}"

                # runner anchor must be defined
                runner_anchor = f"{race_anchor_full}_{horse_name}".strip()


                # --- NEW: LastHalf + MileRate (safe numeric calc) ---
                try:
                    q3 = float(third_qtr) if str(third_qtr).strip() != "" else None
                except:
                    q3 = None

                try:
                    q4 = float(fourth_qtr) if str(fourth_qtr).strip() != "" else None
                except:
                    q4 = None

                last_half = ""
                if (q3 is not None) and (q4 is not None):
                    last_half = f"{(q3 + q4):.1f}"


                # Lead Time: treat blank as 0.0
                try:
                    lt = float(lead_time) if str(lead_time).strip() != "" else 0.0
                except:
                    lt = 0.0


                try:
                    q1 = float(first_qtr) if str(first_qtr).strip() != "" else None
                except:
                    q1 = None

                try:
                    q2 = float(second_qtr) if str(second_qtr).strip() != "" else None
                except:
                    q2 = None

                try:
                    dist_m = float(distance) if str(distance).strip() != "" else None
                except:
                    dist_m = None

                if None not in (q1, q2, q3, q4, dist_m) and dist_m and dist_m > 0:
                    mile_rate = f"{(((lt + q1 + q2 + q3 + q4) / dist_m) * 1609):.1f}"
                else:
                    mile_rate = ""




                results.append({
                    "RaceAnchor": race_anchor,
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
                    "LastHalf": last_half,
                    "MileRate": mile_rate,
                    "URL": page_url,  # ✅ NEW: store scraped page url for Phase 1
                    "VisionURL": video_link or "",  # ✅ NEW: default vision to harness replay
                    "VisionTitle": "",
                    "VisionSource": "HarnessReplay" if (video_link or "") else "",
                    "VisionMatchConfidence": "",
                })

        except Exception as e:
            print(f"⚠️ Error parsing race {race_index}: {e}")
            continue

    return results



from urllib.parse import urlparse, parse_qs

def _trial_id_from_url(url: str) -> str:
    try:
        qs = parse_qs(urlparse(url).query)
        return str(qs.get("trialId", [""])[0])
    except Exception:
        return ""


def scrape_trial_id_page(url: str):
    """
    TrialId pages (especially VIC) have a different structure.
    In PROBE mode we print table headers so we can map the real extractor safely.
    Returns:
      - [] on success but no rows (or probe mode)
      - None if rate-limited (so caller can stop run)
      - list[dict] rows once we implement parse_trial_id_results()
    """
    try:
        response = requests.get(url, timeout=20)

        # rate limit / access denied handling (same style as your mc scraper)
        if response.status_code in (429, 403):
            retry_after = response.headers.get("Retry-After")
            wait_s = 60
            if retry_after and str(retry_after).strip().isdigit():
                wait_s = int(retry_after)
            print(f"🚫 trialId={_trial_id_from_url(url)} — RATE LIMITED (HTTP {response.status_code}). Sleeping {wait_s}s.")
            time.sleep(wait_s)
            return None

        if response.status_code != 200:
            print(f"⚠️ trialId={_trial_id_from_url(url)} — HTTP {response.status_code}")
            return []

        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        # Attempt to fetch venue and date from TRIAL_META, fall back to parsing from the page if not available
        meta = TRIAL_META.get(url, {})
        venue = meta.get("Venue", "")
        date_ddmmyyyy = meta.get("Date", "")

        # If the venue or date is missing from TRIAL_META, try to extract from the page itself
        if not venue or not date_ddmmyyyy:
            venue, date_ddmmyyyy = _extract_trial_meta_from_page_text(html)
            if not venue or not date_ddmmyyyy:
                print(f"⚠️ Failed to extract venue and date for trial {url}")
                return []

        if TRIALID_PROBE_ONLY:
            tables = soup.find_all("table")
            print(f"🔎 PROBE trialId={_trial_id_from_url(url)} — tables found: {len(tables)}")

            # print up to first 12 tables with headers (usually enough)
            shown = 0
            for i, t in enumerate(tables, start=1):
                ths = [th.get_text(" ", strip=True) for th in t.find_all("th")]
                if ths:
                    print(f"   table#{i} headers: {ths}")
                    shown += 1
                    if shown >= 12:
                        break

            return []  # probe mode -> no extraction yet

        # real extraction (this part extracts race and trial details)
        results = parse_trial_id_results(soup, url)

        # Now, you can use the `venue` and `date_ddmmyyyy` values within the results or wherever they are needed
        for result in results:
            result['Venue'] = venue
            result['Date'] = date_ddmmyyyy

        return results

    except Exception as e:
        print(f"❌ Failed trialId scrape: {e} — {url}")
        return []


def parse_trial_id_results(soup: BeautifulSoup, url: str):
    """
    Placeholder.
    We implement this AFTER you paste the PROBE output for a VIC page + an SA page.
    """
    return []

def _headers_of_table(tbl):
    ths = tbl.find_all("th")
    return [th.get_text(strip=True) for th in ths]

def _text_near_table(tbl, max_chars=500):
    # grab a chunk of nearby text above the table (often contains "Trial 1" / distance)
    parts = []
    # walk backwards over prior elements
    for el in tbl.find_all_previous(["h1","h2","h3","h4","p","div"], limit=25):
        t = el.get_text(" ", strip=True)
        if t:
            parts.append(t)
        if len(" ".join(parts)) >= max_chars:
            break
    return " ".join(reversed(parts))[-max_chars:]

def _extract_trial_no_and_distance(near_text: str):
    # very forgiving: finds "Trial 1" etc and "1609m" etc
    trial_no = ""
    dist = ""
    m1 = re.search(r"\bTrial\s*(\d+)\b", near_text, flags=re.IGNORECASE)
    if m1:
        trial_no = m1.group(1)

    m2 = re.search(r"\b(\d{3,4})\s*m\b", near_text, flags=re.IGNORECASE)
    if m2:
        dist = m2.group(1)

    return trial_no, dist

def probe_trialid_tables(html: str):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    print(f"🔎 tables found: {len(tables)}")

    target_headers = ["Placing", "Horse", "Trainer", "Driver", "Class", "Saddlecloth", "Handicap"]

    runner_idxs = []
    for i, tbl in enumerate(tables):
        hdr = _headers_of_table(tbl)
        if hdr == target_headers:
            runner_idxs.append(i)

    print(f"✅ runner tables matched: {len(runner_idxs)} -> {runner_idxs}")

    for i in runner_idxs:
        tbl = tables[i]
        near = _text_near_table(tbl)
        trial_no, dist = _extract_trial_no_and_distance(near)

        print(f"\n--- Runner table #{i} ---")
        print(f"Nearest-text (tail): {near[-250:]}")
        print(f"Parsed TrialNo={trial_no or '(blank)'}  Distance={dist or '(blank)'}")

        if i - 1 >= 0:
            print(f"Prev table #{i-1} headers: {_headers_of_table(tables[i-1])}")
        if i + 1 < len(tables):
            print(f"Next table #{i+1} headers: {_headers_of_table(tables[i+1])}")
        if i + 2 < len(tables):
            print(f"Next+1 table #{i+2} headers: {_headers_of_table(tables[i+2])}")




# --- MAIN SCRAPE FLOW ---
all_results = []
start_date = datetime.today() - timedelta(days=1)

# -----------------------------
# PHASE 1: DISCOVERY (targeted re-check of already-known meeting codes)
# -----------------------------
def _parse_meeting_code(code: str):
    """
    Takes something like:
      'BN040226' or 'BN040226T' or 'ME040226N'
    Returns (venue_code, date_str, suffix)
      venue_code = 'BN'
      date_str   = '040226'
      suffix     = '' / 'T' / 'N' / 'D' etc
    """
    code = (code or "").strip()
    m = re.match(r"^([A-Z]{2})(\d{6})([A-Z]*)$", code)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3)  # suffix may be ""


def _existing_meeting_codes_for_dates(output_csv, date_strs):
    """
    Return meeting-code targets (venue_code, date_str, suffix) for Phase 1 re-check.

    NEW behaviour (debug-friendly):
      - Only returns meetings where at least one row has blank VisionURL
      - Still only returns Phase-1 style RaceAnchors (2 letters + 6 digits + optional suffix)
      - Still only returns meetings whose date_str is in date_strs
    """
    if not os.path.exists(output_csv):
        return []

    try:
        df = pd.read_csv(output_csv, dtype=str, low_memory=False)
    except Exception:
        return []

    if "RaceAnchor" not in df.columns:
        return []

    # If VisionURL exists, only consider rows where it is blank.
    # If VisionURL doesn't exist, fall back to the old behaviour (everything).
    if "VisionURL" in df.columns:
        df_use = df[
            df["VisionURL"].fillna("").astype(str).str.strip() == ""
        ].copy()
    else:
        df_use = df

    anchors = (
        df_use["RaceAnchor"]
        .fillna("")
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    out = []
    seen = set()

    for a in anchors:
        parsed = _parse_meeting_code(a)
        if not parsed:
            continue

        vc, ds, suf = parsed
        if ds not in date_strs:
            continue

        key = (vc, ds, suf)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)

    return out



if RUN_PHASE1:
    # Call phase 1 discovery to start scraping
    phase_1_discovery(venue_code_map)
else:
    print("⏭️  Skipping Phase 1 (discovery) — RUN_PHASE1=False")




# ------------------------------------------------------------
# Ensure Phase 1 rows have Vision columns (even if blank)
# ------------------------------------------------------------
for r in all_results:
    r.setdefault("VisionURL", "")
    r.setdefault("VisionTitle", "")
    r.setdefault("VisionSource", "")
    r.setdefault("VisionMatchConfidence", "")
    # also keep these traceability fields present (blank for Phase 1)
    r.setdefault("TrialId", "")
    r.setdefault("TrialNo", "")
    r.setdefault("TrialClass", "")
    r.setdefault("Gross Time", "")
    r.setdefault("Last Mile", "")
    r.setdefault("Last Quarter", "")
    r.setdefault("Saddlecloth", "")
    r.setdefault("Handicap", "")
    r.setdefault("URL", "")



def _norm_header_list(ths):
    return [t.get_text(" ", strip=True) for t in ths]

def _is_runner_table(table):
    # Match your observed header signature
    want = ['Placing', 'Horse', 'Trainer', 'Driver', 'Class', 'Saddlecloth', 'Handicap']
    ths = table.find_all("th")
    got = _norm_header_list(ths)
    return got == want

def _nearest_trial_heading_text(table):
    """
    Walk backwards from the table to find a nearby heading/label that might identify the trial.
    This is intentionally loose — we’ll refine once we see what VIC pages look like.
    """
    # Look at a handful of previous elements
    prev = table
    for _ in range(30):
        prev = prev.find_previous()
        if prev is None:
            break
        if prev.name in ("h1", "h2", "h3", "h4"):
            txt = prev.get_text(" ", strip=True)
            if txt:
                return txt
        # Sometimes label is in a strong/div/p
        if prev.name in ("div", "p", "strong", "span"):
            txt = prev.get_text(" ", strip=True)
            if txt and ("trial" in txt.lower() or "metre" in txt.lower() or "m " in txt.lower()):
                return txt
    return ""

def _extract_page_meta(soup):
    """
    Best-effort: pull Venue/Date from page heading if present.
    If we can’t, return blanks and you still get runner rows.
    """
    venue = ""
    date_ddmmyyyy = ""

    # Try h1/h2 text
    h1 = soup.find("h1")
    h2 = soup.find("h2")
    header = ""
    if h1:
        header = h1.get_text(" ", strip=True)
    elif h2:
        header = h2.get_text(" ", strip=True)

    # Common patterns might include date like 04/02/2026 or 4 Feb 2026
    # Keep it simple for now — we’ll refine once we see exact header text.
    if header:
        # try dd/mm/yyyy
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", header)
        if m:
            date_ddmmyyyy = m.group(1)

    # Venue might be the first chunk of header before a dash/pipe
    if header:
        venue = header.split("|")[0].split("-")[0].strip()

    return venue, date_ddmmyyyy


def _ensure_master_cols(df: pd.DataFrame) -> pd.DataFrame:
    for c in MASTER_COLS:
        if c not in df.columns:
            df[c] = ""
    return df[MASTER_COLS]


def _phase2_to_master_row(tr: dict) -> dict:
    trial_id = str(tr.get("TrialId", "")).strip()
    trial_no = str(tr.get("TrialNo", "")).strip()

    horse = (tr.get("Horse") or "").strip()
    saddle = (tr.get("Saddlecloth") or "").strip()

    race_anchor = f"TRIAL{trial_id}" if trial_id else ""
    race_anchor_full = f"{race_anchor}_T{trial_no}" if race_anchor and trial_no else race_anchor

    runner_anchor = ""
    if race_anchor_full and horse:
        runner_anchor = f"{race_anchor_full}_{saddle or 'NA'}_{_slug(horse)}"

    row = {c: "" for c in MASTER_COLS}

    row["RaceAnchor"] = race_anchor
    row["RaceAnchorFull"] = race_anchor_full
    row["RunnerAnchor"] = runner_anchor

    row["Venue"] = tr.get("Venue", "")
    row["State"] = tr.get("State", "")
    row["Date"] = tr.get("Date", "")  # keep as dd/mm/yyyy here; we’ll normalise later

    row["Race No"] = trial_no
    row["Placing"] = tr.get("Placing", "")
    row["Horse"] = horse
    row["Distance"] = tr.get("Distance", "")

    # saddlecloth as barrier proxy
    row["Barrier"] = saddle

    row["Trainer"] = tr.get("Trainer", "")
    row["Driver"] = tr.get("Driver", "")
    row["Margin"] = tr.get("Margin", "")

    row["Start"] = tr.get("Start", "")
    row["TrialId"] = trial_id
    row["TrialClass"] = tr.get("TrialClass", "")

    row["Gross Time"] = tr.get("Gross Time", "")
    row["Last Mile"] = tr.get("Last Mile", "")
    row["Last Quarter"] = tr.get("Last Quarter", "")

    # IMPORTANT: map VIC trial block values into the correct master keys:
    row["LastHalf"] = tr.get("Last Half", "")
    row["MileRate"] = tr.get("Mile Rate", "")

    row["Saddlecloth"] = saddle
    row["Handicap"] = tr.get("Handicap", "")
    row["URL"] = tr.get("URL", "")

    row["VisionURL"] = tr.get("VisionURL", "")
    row["VisionTitle"] = tr.get("VisionTitle", "")
    row["VisionSource"] = tr.get("VisionSource", "")
    row["VisionMatchConfidence"] = tr.get("VisionMatchConfidence", "")

    return row


def _extract_trialid_page_venue_state_date(soup: BeautifulSoup) -> tuple[str, str, str]:
    """
    Extract Venue, State, Date (dd/mm/yyyy) from a trialId page header.

    Typical header patterns on harness.org.au include things like:
      "MARYBOROUGH (VIC) Sunday, 4 February 2026"
      "GLOBE DERBY (SA) 25 January 2026"
      "BENDIGO (VIC) Monday, 02 February 2026"

    Returns ("", "", "") if not found.
    """
    def _cw(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ")).strip()

    header_el = soup.find("h2") or soup.find("h1")
    if not header_el:
        return "", "", ""

    header = _cw(header_el.get_text(" ", strip=True))
    if not header:
        return "", "", ""

    # State inside parentheses, e.g. (VIC)
    state = ""
    m_state = re.search(r"\(([A-Z]{2,3})\)", header)
    if m_state:
        state = m_state.group(1).strip()

    # Date pattern: "4 February 2026"
    date_ddmmyyyy = ""
    m_date = re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", header)
    if m_date:
        raw = m_date.group(1).strip()
        try:
            dt = datetime.strptime(raw, "%d %B %Y")
            date_ddmmyyyy = dt.strftime("%d/%m/%Y")
        except Exception:
            # leave blank if we can't parse month name
            date_ddmmyyyy = ""

    # Venue is everything before "(STATE)" if present, else before the date chunk if present
    venue = header

    # Remove everything from first "(" onward (e.g. remove state + trailing text)
    if "(" in venue:
        venue = venue.split("(", 1)[0]

    # Remove anything after a dash (e.g. "- Monday")
    if "-" in venue:
        venue = venue.split("-", 1)[0]

    venue = venue.strip(" -|,")


    return venue.title(), state, date_ddmmyyyy

def _mile_rate_to_seconds(s: str) -> str:
    """
    Convert Mile Rate strings like:
      '01:59.2' -> '119.2'
      '2:05.3'  -> '125.3'
      '01:59:2' -> '119.2'   (treat last chunk as decimal)
      '01:59:20'-> '119.20'  (still works)
    Returns '' if it can't parse.
    """
    if s is None:
        return ""
    t = str(s).strip()
    if not t or t.lower() in ("nan", "none", "null"):
        return ""

    # normalise whitespace
    t = re.sub(r"\s+", "", t)

    # Case A: mm:ss.s  (contains one colon, seconds may have decimals)
    if t.count(":") == 1:
        mm, ss = t.split(":", 1)
        try:
            total = int(mm) * 60 + float(ss)
            # keep 1–2 decimals if present; don't force formatting too hard
            return str(total)
        except Exception:
            return ""

    # Case B: mm:ss:ds  (two colons, last part is decimal digits)
    if t.count(":") == 2 and "." not in t:
        mm, ss, frac = t.split(":", 2)
        if not (mm.isdigit() and ss.isdigit() and frac.isdigit()):
            return ""
        try:
            base = int(mm) * 60 + int(ss)
            total = base + float("0." + frac)
            return str(total)
        except Exception:
            return ""

    # If it’s something else (rare), bail safely
    return ""


# -----------------------------
# PHASE 2: trialId pages (manual list, includes VIC)
# -----------------------------
print(f"🧪 Phase 2 (trialId list): {len(TRIAL_ID_URLS)} URLs")

def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\u00A0", " ")).strip()

def _slice_trial_block(page_blob: str, trial_no: int) -> str:
    """
    Given the big 'Trial 1 ... Trial 7 ...' blob, return only the block for Trial N.
    """
    blob = _collapse_ws(page_blob)
    if not blob:
        return ""

    # Find "Trial N"
    start_pat = re.compile(rf"\bTrial\s+{trial_no}\b", re.IGNORECASE)
    m1 = start_pat.search(blob)
    if not m1:
        return ""

    start = m1.start()

    # End at next "Trial N+1" if it exists
    end = len(blob)
    next_pat = re.compile(rf"\bTrial\s+{trial_no + 1}\b", re.IGNORECASE)
    m2 = next_pat.search(blob, m1.end())
    if m2:
        end = m2.start()

    return blob[start:end].strip()

def _slug(s: str) -> str:
    s = _collapse_ws(s).upper()
    s = re.sub(r"[^A-Z0-9]+", "_", s).strip("_")
    return s

def _ddmmyyyy_to_yyyy_mm_dd(d: str) -> str:
    d = (d or "").strip()
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", d)
    if not m:
        return d  # leave as-is if unexpected
    dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
    return f"{yyyy}-{mm}-{dd}"




def _extract_trial_fields_from_block(block: str) -> dict:
    """
    Extract the per-trial summary fields from a single trial block.
    Returns strings (blank if not found).
    """
    b = _collapse_ws(block)
    if not b:
        return {
            "Start": "",
            "TrialClass": "",
            "Distance": "",
            "Gross Time": "",
            "Mile Rate": "",
            "Margins": "",
            "Last Mile": "",
            "Last Half": "",
            "Last Quarter": "",
        }

    # Start type
    start = ""
    if re.search(r"\bMOBILE\s+START\b", b, re.IGNORECASE):
        start = "Mobile"
    elif re.search(r"\bSTANDING\s+START\b", b, re.IGNORECASE):
        start = "Stand"

    # Distance (first occurrence like "2150 METRES")
    dist = ""
    m = re.search(r"\b(\d{3,4})\s*METRES\b", b, re.IGNORECASE)
    if m:
        dist = m.group(1)

    # Class text (between 'Class:' and '<distance> METRES' if possible)
    trial_class = ""
    m = re.search(r"\bClass:\s*(.*?)\s+\d{3,4}\s*METRES\b", b, re.IGNORECASE)
    if m:
        trial_class = m.group(1).strip()

    # Summary fields (they appear near the end of each trial block)
    def grab(label: str) -> str:
        # capture up to next known label or end
        pat = re.compile(
            rf"\b{re.escape(label)}\s*:\s*(.*?)(?=\bGross Time\b|\bMile Rate\b|\bMargins\b|\bLast Mile\b|\bLast Half\b|\bLast Quarter\b|$)",
            re.IGNORECASE
        )
        mm = pat.search(b)
        return (mm.group(1).strip() if mm else "")

    gross_time = grab("Gross Time")
    mile_rate  = grab("Mile Rate")
    mile_rate = _mile_rate_to_seconds(mile_rate)
    margins    = grab("Margins")
    last_mile  = grab("Last Mile")
    last_half  = grab("Last Half")
    last_qtr   = _strip_footer_disclaimer(grab("Last Quarter"))


    return {
        "Start": start,
        "TrialClass": trial_class,
        "Distance": dist,
        "Gross Time": gross_time,
        "Mile Rate": mile_rate,
        "Margins": margins,
        "Last Mile": last_mile,
        "Last Half": last_half,
        "Last Quarter": last_qtr,
    }


trial_rows = []

for url in TRIAL_ID_URLS:
    try:
        m = re.search(r"trialId=(\d+)", url)
        trial_id = m.group(1) if m else ""

        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"⚠️ trialId={trial_id} — HTTP {r.status_code}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        venue, state, date_ddmmyyyy = _extract_trialid_page_venue_state_date(soup)

        if not venue or not date_ddmmyyyy:
            print(f"⚠️ trialId={trial_id} — could not parse Venue/Date from header")
            # you can continue anyway (rows will be created but blank venue/date)


        # Big page blob (contains Trial 1..N text)
        page_blob = _collapse_ws(_page_text_for_trials(soup))

        # Find runner tables
        tables = soup.find_all("table")
        matched_tables = []
        for i, t in enumerate(tables):
            if _is_runner_table(t):
                matched_tables.append((i, t))

        print(f"🔎 trialId={trial_id} — runner tables matched: {len(matched_tables)}")
        if not matched_tables:
            continue

        for trial_no, (idx, table) in enumerate(matched_tables, start=1):
            # Slice ONLY Trial N text and extract fields from it
            block = _slice_trial_block(page_blob, trial_no)
            tf = _extract_trial_fields_from_block(block)


            # Parse runner rows
            trs = table.find_all("tr")
            for tr in trs[1:]:  # skip header
                tds = tr.find_all("td")
                if len(tds) < 7:
                    continue

                placing     = tds[0].get_text(" ", strip=True)
                placing = placing.strip().upper()

                # Skip scratched runners entirely
                if placing.startswith("SCR"):
                    continue

                horse       = tds[1].get_text(" ", strip=True)
                trainer     = tds[2].get_text(" ", strip=True)
                driver      = tds[3].get_text(" ", strip=True)
                cls         = tds[4].get_text(" ", strip=True)
                saddlecloth = tds[5].get_text(" ", strip=True)
                handicap    = tds[6].get_text(" ", strip=True)

                driver = _clean_person_name(driver)

                margin = _margin_for_placing(placing, tf.get("Margins", ""))
                # If winner has margin 0, blank it out
                if placing == "1" and str(margin).strip() == "0":
                    margin = ""



                trial_rows.append({
                    "TrialId": trial_id,
                    "URL": url,
                    "Venue": venue,
                    "State": state,
                    "Date": date_ddmmyyyy,
                    "TrialNo": str(trial_no),

                    "Start": tf.get("Start", ""),
                    "TrialClass": tf.get("TrialClass", ""),
                    "Distance": tf.get("Distance", ""),
                    "Gross Time": tf.get("Gross Time", ""),
                    "Mile Rate": tf.get("Mile Rate", ""),
                    "Margins": tf.get("Margins", ""),
                    "Last Mile": tf.get("Last Mile", ""),
                    "Last Half": tf.get("Last Half", ""),
                    "Last Quarter": tf.get("Last Quarter", ""),

                    "Placing": placing,
                    "Margin": margin,   # <-- ADD THIS LINE
                    "Horse": horse,
                    "Trainer": trainer,
                    "Driver": driver,
                    "Class": cls,
                    "Saddlecloth": saddlecloth,
                    "Handicap": handicap,
                    "VisionURL": "",
                    "VisionSource": "",
                    "VisionMatchConfidence": "",
                })

        time.sleep(random.uniform(5.0, 10.0))

    except Exception as e:
        print(f"❌ trialId page failed: {url} — {e}")
        continue

# If BOTH phases produced nothing, then exit
if not trial_rows and not all_results:
    print("No results scraped (Phase 1 and Phase 2 both empty).")
    sys.exit(0)

# If Phase 2 is empty, still continue and write Phase 1 results
if not trial_rows:
    print("⚠️ Phase 2 produced 0 rows — continuing with Phase 1 only.")


def recover_url_and_vision(df: pd.DataFrame, max_meetings_fetch: int = 40) -> pd.DataFrame:
    """
    RUN_VISION_RECOVERY = False   # ✅ set True when you actually want to run recovery
    Recovery/backfill:
      - URL:
          * Phase 1 (mc anchors): rebuild https://www.harness.org.au/racing/fields/race-fields/?mc=<RaceAnchor>
          * Phase 2 (trialId): rebuild https://www.harness.org.au/racing/trials/trial-results/?trialId=<TrialId>
      - VisionURL (Phase 1):
          If missing, refetch the mc page for that meeting (limited) and re-extract lastLapReplay links
          per Race No, then write VisionURL for rows in that race.
    """
    out = df.copy()

    # Ensure columns exist
    for c in ["URL", "VisionURL", "VisionSource", "RaceAnchor", "Race No", "TrialId"]:
        if c not in out.columns:
            out[c] = ""

    # ---------- URL recovery ----------
    ra = out["RaceAnchor"].fillna("").astype(str).str.strip()
    tid = out["TrialId"].fillna("").astype(str).str.strip()
    url = out["URL"].fillna("").astype(str).str.strip()

    # Phase 2 URLs (trialId)
    mask_trial = url.eq("") & tid.ne("")
    out.loc[mask_trial, "URL"] = "https://www.harness.org.au/racing/trials/trial-results/?trialId=" + tid[mask_trial]

    # Phase 1 URLs (mc-style anchors: 2 letters + 6 digits + optional suffix letters)
    # Example: BN040226, BN040226T
    mc_like = ra.str.match(r"^[A-Z]{2}\d{6}[A-Z]*$", na=False)
    mask_mc = url.eq("") & ra.ne("") & mc_like
    out.loc[mask_mc, "URL"] = "https://www.harness.org.au/racing/fields/race-fields/?mc=" + ra[mask_mc]

    # ---------- VisionURL recovery (Phase 1 only) ----------
    # We'll only refetch a limited number of meetings to avoid hammering the site.
    vurl = out["VisionURL"].fillna("").astype(str).str.strip()
    rno = out["Race No"].fillna("").astype(str).str.strip()

    # --------------------------------------------------
    # Build list of meetings needing Vision recovery
    # (FOCUS MODE: restrict to these meetings only)
    # --------------------------------------------------
    FOCUS_MEETINGS = set()  # add/remove while testing

    vision = out["VisionURL"].fillna("").astype(str).str.strip()
    ra     = out["RaceAnchor"].fillna("").astype(str).str.strip()
    rno    = out["Race No"].fillna("").astype(str).str.strip()

    # rows that genuinely need Vision recovery (blank only; allow "nan" string too)
    need_vision = ((vision == "") | (vision.str.lower() == "nan"))
    # hard exclude known no-vision rows
    need_vision = need_vision & (vision != "_noVision")
    # must have meeting + trial no
    need_vision = need_vision & ra.ne("") & rno.ne("")

    # restrict to focus meetings only (while testing)
    if FOCUS_MEETINGS:
        need_vision = need_vision & ra.isin(FOCUS_MEETINGS)

    meetings = (
        out.loc[need_vision, "RaceAnchor"]
          .drop_duplicates()
          .head(max_meetings_fetch)
          .tolist()
    )

    if meetings:
        print(f"🛠️ Recover VisionURL: refetching up to {len(meetings)} meeting(s) (cap={max_meetings_fetch})")
    else:
        return out


    # Debug switch: allow turning off the network-heavy Vision recovery loop
    if not RUN_VISION_RECOVERY:
        print("⏭️ Vision recovery disabled (debug)")
        return out




    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})



    def _extract_race_video_map(soup: BeautifulSoup, meeting_anchor: str = "") -> dict:
        """
        Returns { trial_no_str: video_link_or_token }

        Supports:
        - Direct MP4 links (akamaized): https://...mp4
        - Brightcove modal triggers: playBrightcoveVideo('MXQ03022611', 2)
          -> stored as: BRIGHTCOVE:MXQ03022611
        - Tasracing links (TAS): https://form.tasracing.com.au/... or http(s)://tasracing.com.au/replays/
          (NOTE: some TAS meets only provide the generic /replays/ link per trial; we keep duplicates)
        - Vimeo links (WA): progressive_redirect / manage/videos / player.vimeo.com etc.

        Key fix:
        - Some pages contain MULTIPLE <div id="results"> blocks (one per trial).
          We extract ONE replay token per results-block (trial) in display order.
          This avoids global de-duping wiping out trials that share the same link.
        """
        import re

        def _clean_href(href: str) -> str:
            href = (href or "").strip()
            if not href:
                return ""

            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.harness.org.au" + href

            return href

        def _normalise_angle_suffix(url: str) -> str:
            """
            Convert multi-angle links like ..._1.mp4, ..._2.mp4 -> ....mp4
            Keeps everything else unchanged.
            """
            if not url:
                return ""
            return re.sub(r'_(\d+)(?=\.mp4$)', '', url, flags=re.IGNORECASE)

        def _extract_brightcove_id(onclick: str) -> str:
            onclick = (onclick or "").strip()
            m = re.search(r"playBrightcoveVideo\(\s*'([^']+)'\s*,", onclick)
            if not m:
                m = re.search(r'playBrightcoveVideo\(\s*"([^"]+)"\s*,', onclick)
            return m.group(1).strip() if m else ""

        def _first_href(root, selector: str) -> str:
            el = root.select_one(selector)
            if not el:
                return ""
            if el.has_attr("href"):
                return _clean_href(el.get("href"))
            if el.has_attr("src"):
                return _clean_href(el.get("src"))
            return ""

        # IMPORTANT: grab ALL results blocks (not just the first)
        results_blocks = soup.select("#results")
        if not results_blocks:
            results_blocks = [soup]

        tokens_in_order = []

        for root in results_blocks:
            token = ""

            # 1) Direct MP4 links
            mp4 = _first_href(root, 'a[href*=".mp4"], a[href*=".MP4"]')
            if mp4:
                mp4 = _normalise_angle_suffix(mp4)
                token = mp4

            # 2) MP4 <source> tags
            if not token:
                src = _first_href(root, 'source[src*=".mp4"], source[src*=".MP4"]')
                if src:
                    src = _normalise_angle_suffix(src)
                    token = src

            # 3) Brightcove onclick triggers
            if not token:
                el = root.select_one('[onclick*="playBrightcoveVideo"]')
                if el:
                    bc_id = _extract_brightcove_id(el.get("onclick"))
                    if bc_id:
                        token = f"BRIGHTCOVE:{bc_id}"

            # 4) Tasracing direct links (keep even if generic /replays/)
            if not token:
                a = root.select_one('a[href*="tasracing.com.au"]')
                if a and a.get("href"):
                    token = _clean_href(a.get("href"))

            # 5) Vimeo links (WA edge case)
            if not token:
                a = root.select_one('a[href*="vimeo.com"]')
                if a and a.get("href"):
                    token = _clean_href(a.get("href"))

            if token:
                tokens_in_order.append(token)

        if not tokens_in_order:
            return {}

        video_by_trial = {}
        for i, token in enumerate(tokens_in_order, start=1):
            video_by_trial[str(i)] = token

        return video_by_trial










    for meeting_anchor in meetings:
        meeting_url = f"https://www.harness.org.au/racing/fields/race-fields/?mc={meeting_anchor}"

        try:
            resp = session.get(meeting_url, timeout=20)
            if resp.status_code != 200:
                print(f"⚠️ Vision recovery: {meeting_anchor} HTTP {resp.status_code}")
                continue

            html = resp.text
            if "rate limit exceeded" in html.lower() or "access denied" in html.lower():
                print(f"🚫 Vision recovery: {meeting_anchor} rate-limited (body). Stopping.")
                break

            soup = BeautifulSoup(html, "html.parser")
            video_map = _extract_race_video_map(soup, meeting_anchor)
            print(f"DEBUG {meeting_anchor} mp4 count:", len(video_map))
            if video_map:
                print("DEBUG first 3:", dict(list(video_map.items())[:3]))



            if not video_map:
                print(f"ℹ️ Vision recovery: {meeting_anchor} no replay links found")
            else:
                print(f"✅ Vision recovery: {meeting_anchor} found replay links for {len(video_map)} race(s)")

            # Apply to rows in this meeting where VisionURL is truly blank (and not _noVision)
            meet_mask = (out["RaceAnchor"].fillna("").astype(str).str.strip() == meeting_anchor)

            vision = out["VisionURL"].fillna("").astype(str).str.strip()
            blank_mask = (vision == "") | (vision.str.lower() == "nan")
            no_vision_mask = (vision == "_noVision")

            target_mask = meet_mask & blank_mask & (~no_vision_mask)

            for trial_no, vlink in video_map.items():
                trial_mask = (out["Race No"].fillna("").astype(str).str.strip() == str(trial_no))
                m = target_mask & trial_mask
                if m.any():
                    out.loc[m, "VisionURL"] = vlink
                    # set VisionSource only where it's blank
                    vs = out.get("VisionSource")
                    if vs is not None:
                        out.loc[m & (out["VisionSource"].fillna("").astype(str).str.strip() == ""), "VisionSource"] = "HarnessReplay"




            time.sleep(random.uniform(1.2, 2.0))

        except Exception as e:
            print(f"⚠️ Vision recovery error for {meeting_anchor}: {e}")

    return out


# ------------------------------------------------------------
# (YouTube probe moved to run on df_all after combine)
# ------------------------------------------------------------


# ============================================================
# COMBINE PHASE 1 + PHASE 2 INTO ONE MASTER-SCHEMA OUTPUT
# ============================================================

# Phase 1 already produces rows in the master schema (mostly)
df_p1 = pd.DataFrame(all_results, dtype=str) if all_results else pd.DataFrame(columns=MASTER_COLS)
df_p1 = _ensure_master_cols(df_p1)

# Phase 2: convert each Phase 2 runner row into master schema
phase2_master_rows = [_phase2_to_master_row(tr) for tr in trial_rows]
df_p2 = pd.DataFrame(phase2_master_rows, dtype=str) if phase2_master_rows else pd.DataFrame(columns=MASTER_COLS)
df_p2 = _ensure_master_cols(df_p2)

# New batch (this run)
df_new = pd.concat([df_p1, df_p2], ignore_index=True)
df_new = _ensure_master_cols(df_new)

# Read existing master output
if os.path.exists(OUTPUT_FILE):
    try:
        df_old = pd.read_csv(OUTPUT_FILE, dtype=str, low_memory=False)
    except Exception:
        df_old = pd.DataFrame(columns=MASTER_COLS)
else:
    df_old = pd.DataFrame(columns=MASTER_COLS)

df_old = _ensure_master_cols(df_old)

# Append
df_all = pd.concat([df_old, df_new], ignore_index=True)
df_all = _ensure_master_cols(df_all)

# ------------------------------------------------------------
# DEDUPE RULE (single row per runner within a "race/trial container")
# Use RaceAnchorFull + Horse as the stable unique key across both phases.
# ------------------------------------------------------------
dedupe_cols = ["RaceAnchorFull", "Horse"]
for c in dedupe_cols:
    if c not in df_all.columns:
        df_all[c] = ""

df_all.drop_duplicates(subset=dedupe_cols, keep="last", inplace=True)



# ------------------------------------------------------------
# 🔍 Optional: YouTube probe for trials with blank VisionURL
# (runs on the combined dataset so it can also cover Phase 1-only rows)
# ------------------------------------------------------------
if RUN_YOUTUBE_PROBE:
    df_records = df_all.to_dict("records")
    probe_youtube_trials(df_records, max_results=12, verbose=True)  # ✅ probe the same records you will save
    df_all = pd.DataFrame(df_records, dtype=str)                    # ✅ rebuild df from mutated records
    df_all = _ensure_master_cols(df_all)
else:
    print("⏭️ Skipping YouTube probe — RUN_YOUTUBE_PROBE=False")

# -----------------------------
# POST-PROCESS: merges / drops
# -----------------------------

# (2) Race No merge with TrialNo (if you still keep TrialNo in df_all)
if "Race No" in df_all.columns and "TrialNo" in df_all.columns:
    df_all["Race No"] = df_all["Race No"].fillna("").astype(str)
    df_all["TrialNo"] = df_all["TrialNo"].fillna("").astype(str)
    df_all.loc[df_all["Race No"].str.strip().eq(""), "Race No"] = df_all["TrialNo"]

# (13) RaceAnchor merge with TrialId when blank
if "RaceAnchor" in df_all.columns and "TrialId" in df_all.columns:
    ra = df_all["RaceAnchor"].fillna("").astype(str)
    tid = df_all["TrialId"].fillna("").astype(str)
    df_all.loc[ra.str.strip().eq("") & tid.str.strip().ne(""), "RaceAnchor"] = "TRIAL" + tid

# (9) RaceAnchorFull repair if blank but RaceAnchor + Race No exist
if "RaceAnchorFull" in df_all.columns:
    raf = df_all["RaceAnchorFull"].fillna("").astype(str)
    ra = df_all["RaceAnchor"].fillna("").astype(str)
    rno = df_all["Race No"].fillna("").astype(str)
    df_all.loc[raf.str.strip().eq("") & ra.str.strip().ne("") & rno.str.strip().ne(""),
               "RaceAnchorFull"] = ra + "_R" + rno

# (10) RunnerAnchor repair if blank but RaceAnchorFull + Horse exist
if "RunnerAnchor" in df_all.columns:
    runa = df_all["RunnerAnchor"].fillna("").astype(str)
    raf = df_all["RaceAnchorFull"].fillna("").astype(str)
    horse = df_all["Horse"].fillna("").astype(str)
    df_all.loc[runa.str.strip().eq("") & raf.str.strip().ne("") & horse.str.strip().ne(""),
               "RunnerAnchor"] = raf + "_" + horse.str.strip()

# (8) Video Link merge into VisionURL (if you still have Video Link column in df)
# If you remove Video Link from schema, do this earlier at Phase1 mapping time.
if "VisionURL" in df_all.columns and "Video Link" in df_all.columns:
    vurl = df_all["VisionURL"].fillna("").astype(str)
    vlink = df_all["Video Link"].fillna("").astype(str)
    df_all.loc[vurl.str.strip().eq("") & vlink.str.strip().ne(""), "VisionURL"] = vlink

# Now drop columns you said you don’t want lingering
drop_cols = [
    "MeetingTime", "Time", "Race Name", "Prizemoney", "SP",
    "Photo Link", "Video Link", "TrialNo", "StewardsComments",
    "Comments"
]
df_all.drop(columns=[c for c in drop_cols if c in df_all.columns], inplace=True)


# --- TrialWinner: winner horse name for each RaceAnchorFull (Placing == 1) ---
if "RaceAnchorFull" in df_all.columns and "Placing" in df_all.columns and "Horse" in df_all.columns:
    placing_is_1 = df_all["Placing"].fillna("").astype(str).str.strip().eq("1")

    winners = (
        df_all.loc[placing_is_1 & df_all["RaceAnchorFull"].notna() & (df_all["RaceAnchorFull"].astype(str).str.strip() != ""),
                   ["RaceAnchorFull", "Horse"]]
        .drop_duplicates(subset=["RaceAnchorFull"], keep="first")
    )

    winner_map = dict(zip(winners["RaceAnchorFull"], winners["Horse"]))
    df_all["TrialWinner"] = df_all["RaceAnchorFull"].map(winner_map)
else:
    df_all["TrialWinner"] = ""


# ------------------------------------------------------------
# RECOVERY PASS: backfill URL + VisionURL (safe + capped fetch)
# ------------------------------------------------------------
df_all = recover_url_and_vision(df_all, max_meetings_fetch=40)


# Write safely
backup_file(OUTPUT_FILE)
atomic_to_csv(df_all, OUTPUT_FILE)
print(f"💾 Wrote {OUTPUT_FILE} (new={len(df_new):,}, total={len(df_all):,})")
print(f"   Phase 1 rows this run: {len(df_p1):,}")
print(f"   Phase 2 rows this run: {len(df_p2):,}")

