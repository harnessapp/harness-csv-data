#!/usr/bin/env python3
"""
Batch update multiple files (CSVs + metadata JSON) to GitHub in a SINGLE commit,
skipping the commit if nothing changed.

Requirements:
  - requests
  - pandas
  - env var: GITHUB_TOKEN
Optional:
  - env vars:
      REPO_OWNER, REPO_NAME, BRANCH
      CSV_SOURCE_DIR
      COMMIT_MESSAGE, GIT_AUTHOR_NAME, GIT_AUTHOR_EMAIL
      DELETE_MISSING
      BUILD_MERGED_META (1/0)
      MERGED_CSV_PATH (path to local merged_file.csv)
"""

import os
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

import requests

# ------------------ CONFIG ------------------
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")  # REQUIRED
REPO_OWNER   = os.environ.get("REPO_OWNER", "harnessapp")
REPO_NAME    = os.environ.get("REPO_NAME", "harness-csv-data")
BRANCH       = os.environ.get("BRANCH", "main")

# Where to read local files from (CSVs + meta JSON):
SOURCE_DIR = Path(os.environ.get("CSV_SOURCE_DIR", r"C:\Users\joel\FlutterProjects\harness_app\assets")).resolve()

# Build merged_meta.json from merged_file.csv before upload?
BUILD_MERGED_META = os.environ.get("BUILD_MERGED_META", "1").strip() in ("1", "true", "True", "yes", "YES")

# Where is merged_file.csv (the big local file)?
# Default assumes you run this script from harness_api where merged_file.csv exists, otherwise set env var.
MERGED_CSV_PATH = Path(os.environ.get("MERGED_CSV_PATH", "merged_file.csv")).resolve()

# (local_filename in SOURCE_DIR, repo_path)
FILES: List[Tuple[str, str]] = [
    ("upcoming_fields.csv", "upcoming_fields.csv"),
    ("unicorn_tiers_refined.csv", "unicorn_tiers_refined.csv"),
    ("Cold Drivers 30.csv", "Cold Drivers 30.csv"),
    ("Cold Drivers.csv",    "Cold Drivers.csv"),
    ("Cold Trainers 30.csv","Cold Trainers 30.csv"),
    ("Cold Trainers.csv",   "Cold Trainers.csv"),
    ("Hot Drivers 30.csv",  "Hot Drivers 30.csv"),
    ("Hot Drivers.csv",     "Hot Drivers.csv"),
    ("Hot Trainers 30.csv", "Hot Trainers 30.csv"),
    ("Hot Trainers.csv",    "Hot Trainers.csv"),
    ("model_metrics.csv",    "model_metrics.csv"),


    # ✅ NEW: tiny metadata file for app banner
    ("merged_meta.json",    "merged_meta.json"),
]

COMMIT_MSG   = os.environ.get("COMMIT_MESSAGE", "🔄 Auto-update CSVs")
BOT_NAME     = os.environ.get("GIT_AUTHOR_NAME", "Harness Bot")
BOT_EMAIL    = os.environ.get("GIT_AUTHOR_EMAIL", "bot@harnessapp.local")

# If True, missing local files will DELETE paths from the repo.
# If False, we skip missing locals (safer).
DELETE_MISSING = os.environ.get("DELETE_MISSING", "0").strip() in ("1", "true", "True", "yes", "YES")
# -------------------------------------------

if not GITHUB_TOKEN:
    print("❌ GITHUB_TOKEN not set.")
    sys.exit(1)

BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "harness-csv-batch-updater",
}

def req(method: str, url: str, **kwargs):
    r = requests.request(method, url, headers=HEADERS, **kwargs)
    if r.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {r.status_code} {r.text}")
    return r.json()

def git_blob_sha(data: bytes) -> str:
    """Compute Git's blob SHA1: sha1(b"blob {len}\\0" + data)."""
    h = hashlib.sha1()
    h.update(f"blob {len(data)}\0".encode("utf-8"))
    h.update(data)
    return h.hexdigest()

def _fmt_mtime(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "unknown"



# ------------------ NEW: build merged_meta.json ------------------

def build_merged_meta_json(merged_csv_path: Path, output_json_path: Path, date_col: str = "Date") -> None:
    """
    Compute data_from/data_to from merged_file.csv (chunked; safe for big files)
    and write merged_meta.json for the app to display.
    Assumes AU-style dates commonly in d/m/Y -> dayfirst=True.
    """
    import pandas as pd
    import json as _json

    if not merged_csv_path.is_file():
        raise FileNotFoundError(f"merged CSV not found: {merged_csv_path}")

    min_date = None
    max_date = None

    for chunk in pd.read_csv(merged_csv_path, usecols=[date_col], chunksize=200_000):
        s = pd.to_datetime(chunk[date_col], errors="coerce", dayfirst=True).dropna()
        if s.empty:
            continue

        cmin = s.min().date()
        cmax = s.max().date()

        min_date = cmin if min_date is None else min(min_date, cmin)
        max_date = cmax if max_date is None else max(max_date, cmax)

    if min_date is None or max_date is None:
        raise RuntimeError(f"No valid dates found in column '{date_col}' of {merged_csv_path}")

    from datetime import datetime
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Australia/Hobart")
    except Exception:
        tz = None  # fallback

    last_updated = (
        datetime.now(tz).strftime("%Y-%m-%d %H:%M")
        if tz
        else datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    # --- NEW: preserve existing keys if file already exists ---
    existing = {}
    if output_json_path.is_file():
        try:
            existing = _json.loads(output_json_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}

    # --- NEW: compute runs (row count) and races (unique race anchor) ---
    runs = 0
    race_set = set()
    race_col = "RaceAnchorFull"  # preferred; falls back below if missing

    # detect available columns cheaply
    header = pd.read_csv(merged_csv_path, nrows=0)
    cols = set(header.columns)

    if race_col not in cols:
        if "RaceAnchor" in cols:
            race_col = "RaceAnchor"
        else:
            race_col = None

    usecols = [date_col]
    if race_col:
        usecols.append(race_col)

    for chunk in pd.read_csv(merged_csv_path, usecols=usecols, chunksize=200_000):
        runs += len(chunk)
        if race_col:
            race_set.update(chunk[race_col].dropna().astype(str).tolist())

    races = len(race_set) if race_col else existing.get("races")

    # --- build meta, preserving anything else that already exists ---
    meta = dict(existing)
    meta.update({
        "data_from": min_date.isoformat(),
        "data_to": max_date.isoformat(),
        "last_updated": last_updated,
        "runs": int(runs),
        "runners": int(runs),   # <-- add this line for backward compatibility
        "races": int(races) if races is not None else None,
    })

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(_json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(f"🧾 Built merged_meta.json -> {output_json_path}")
    print(f"    data_from={meta['data_from']}  data_to={meta['data_to']}")
    print(f"    races={meta.get('races')}  runs={meta.get('runs')}")


# ---------------------------------------------------------------

def load_local_files() -> Dict[str, Optional[bytes]]:
    """
    Returns map of repo_path -> bytes (or None if DELETE_MISSING and missing).
    Reads from SOURCE_DIR.
    """
    locals_map: Dict[str, Optional[bytes]] = {}

    print(f"📁 SOURCE_DIR: {SOURCE_DIR}")
    if not SOURCE_DIR.exists():
        print(f"❌ SOURCE_DIR does not exist: {SOURCE_DIR}")
        sys.exit(1)

    for local_filename, repo_path in FILES:
        p = (SOURCE_DIR / local_filename).resolve()

        if not p.is_file():
            if DELETE_MISSING:
                locals_map[repo_path] = None
                print(f"🗑️  Will delete (missing locally): {repo_path}  (expected at {p})")
            else:
                print(f"⚠️  Skipping missing local file: {local_filename}  (expected at {p})")
            continue

        data = p.read_bytes()
        locals_map[repo_path] = data

        print(f"✅ Found: {local_filename}  | size={len(data)} bytes | mtime={_fmt_mtime(p)}")

    return locals_map

def get_branch_commit_and_tree():
    ref = req("GET", f"{BASE}/git/refs/heads/{BRANCH}")
    commit_sha = ref["object"]["sha"]
    commit = req("GET", f"{BASE}/git/commits/{commit_sha}")
    tree_sha = commit["tree"]["sha"]
    tree = req("GET", f"{BASE}/git/trees/{tree_sha}?recursive=1")
    return commit_sha, tree_sha, tree.get("tree", [])

def map_tree_paths(tree_items) -> Dict[str, str]:
    """Map repo path → blob sha for files (type=='blob')."""
    out = {}
    for item in tree_items:
        if item.get("type") == "blob":
            out[item["path"]] = item["sha"]
    return out

def main():
    # 0) NEW: Build merged_meta.json into SOURCE_DIR before uploading
    if BUILD_MERGED_META:
        try:
            out_meta = (SOURCE_DIR / "merged_meta.json").resolve()
            build_merged_meta_json(MERGED_CSV_PATH, out_meta, date_col="Date")
        except Exception as e:
            print(f"❌ Failed to build merged_meta.json: {e}")
            sys.exit(1)
    else:
        print("ℹ️ BUILD_MERGED_META disabled; skipping meta generation.")

    # 1) Load local files
    local_map = load_local_files()
    if not local_map:
        print("❌ No local files to process.")
        sys.exit(1)

    # 2) Get current branch commit and full tree
    commit_sha, base_tree_sha, tree_items = get_branch_commit_and_tree()
    path_to_sha = map_tree_paths(tree_items)
    print(f"Base commit: {commit_sha[:7]} (tree {base_tree_sha[:7]})")

    # 3) Figure out which files actually changed
    to_create_blobs: List[Tuple[str, str]] = []  # (repo_path, blob_sha)
    to_delete_paths: List[str] = []              # paths to delete (if enabled)
    changed_paths: List[str] = []

    for repo_path, data in local_map.items():
        if data is None:
            if DELETE_MISSING and repo_path in path_to_sha:
                to_delete_paths.append(repo_path)
                changed_paths.append(repo_path)
            continue

        new_blob_oid = git_blob_sha(data)
        old_blob_oid = path_to_sha.get(repo_path)

        if old_blob_oid == new_blob_oid:
            print(f"⏭️  No change: {repo_path}")
            continue

        # IMPORTANT: Use base64 encoding for arbitrary bytes? For CSV/JSON utf-8 is fine.
        blob = req("POST", f"{BASE}/git/blobs", json={
            "content": data.decode("utf-8", errors="replace"),
            "encoding": "utf-8",
        })
        blob_sha = blob["sha"]
        to_create_blobs.append((repo_path, blob_sha))
        changed_paths.append(repo_path)
        action = "new" if old_blob_oid is None else "update"
        print(f"📝 {action}: {repo_path} (blob {blob_sha[:7]})")

    if not changed_paths:
        print("✅ No changes detected; skipping commit.")
        sys.exit(0)

    # 4) Build a new tree with updates (and deletions if any)
    tree_entries = []

    for path, blob_sha in to_create_blobs:
        tree_entries.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": blob_sha,
        })

    for path in to_delete_paths:
        tree_entries.append({
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": None,
        })

    new_tree = req("POST", f"{BASE}/git/trees", json={
        "base_tree": base_tree_sha,
        "tree": tree_entries,
    })
    new_tree_sha = new_tree["sha"]

    # 5) Create a new commit with the new tree
    new_commit = req("POST", f"{BASE}/git/commits", json={
        "message": COMMIT_MSG,
        "tree": new_tree_sha,
        "parents": [commit_sha],
        "author": {"name": BOT_NAME, "email": BOT_EMAIL},
        "committer": {"name": BOT_NAME, "email": BOT_EMAIL},
    })
    new_commit_sha = new_commit["sha"]
    print(f"✅ Created commit {new_commit_sha[:7]} with {len(changed_paths)} file(s)")

    # 6) Move the branch ref to the new commit
    req("PATCH", f"{BASE}/git/refs/heads/{BRANCH}", json={"sha": new_commit_sha})
    print(f"📌 {BRANCH} -> {new_commit_sha[:7]}")






if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
