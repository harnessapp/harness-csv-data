import os
import shutil
import pandas as pd
import numpy as np

INPUT_CSV = "upcoming_fields.csv"
OUTPUT_CSV = "unicorn_tiers_refined.csv"

EVENT_KEY = "RaceAnchorFull"
MIN_HORSE_QTY = 6   # "Horse Qty" > 5

# Where to copy the output after building it
COPY_TARGET_DIRS = [
    r"C:\Users\joel\FlutterProjects\harness_app\assets",
    r"C:\Users\joel\FlutterProjects\harness_app\assets\assets",
]

# -----------------------------
# Helpers
# -----------------------------
def to_num(x):
    if x is None:
        return np.nan
    s = str(x).strip()
    if s == "" or s.lower() in {"null", "nan", "none"}:
        return np.nan
    s = s.replace("%", "").replace("$", "").replace(",", "")
    try:
        return float(s)
    except:
        return np.nan

def has_fr(x):
    return "FR" in str(x).upper()

def safe_mkdir(path: str):
    os.makedirs(path, exist_ok=True)

def copy_output_to_targets(src_path: str, target_dirs: list[str]):
    src_abs = os.path.abspath(src_path)
    if not os.path.exists(src_abs):
        raise FileNotFoundError(f"Output file not found: {src_abs}")

    for d in target_dirs:
        safe_mkdir(d)
        dst = os.path.join(d, os.path.basename(src_abs))
        shutil.copy2(src_abs, dst)
        print(f"📌 Copied -> {dst}")

# -----------------------------
# Load
# -----------------------------
df = pd.read_csv(INPUT_CSV, dtype=str).fillna("")

required_cols = [
    EVENT_KEY, "Barrier", "Ld %", "Dth %",
    "Br ROI %", "Dr L/100 ROI %", "Tr L/100 ROI %", "Fair Odds",
    "Horse Qty"
]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    raise SystemExit("Missing required columns:\n" + "\n".join(f"- {c}" for c in missing))

# Parse numeric fields
for col in ["Ld %", "Dth %", "Br ROI %", "Fair Odds",
            "Dr L/100 ROI %", "Tr L/100 ROI %", "Horse Qty"]:
    df[col + "__num"] = df[col].map(to_num)

df["hasFR"] = df["Barrier"].map(has_fr)

# -----------------------------
# Structural gate (event-level)
# -----------------------------
df["fr_ld_flag"] = df["hasFR"] & (df["Ld %__num"] > 15)
df["dth15_flag"] = df["Dth %__num"] > 15

grp = df.groupby(EVENT_KEY)
event_fr_ld = grp["fr_ld_flag"].sum().rename("fr_ld_count")
event_dth   = grp["dth15_flag"].sum().rename("dth15_count")

df = df.merge(event_fr_ld, on=EVENT_KEY).merge(event_dth, on=EVENT_KEY)

df["structural_ok"] = (df["fr_ld_count"] == 1) & (df["dth15_count"] < 2)

# Only keep the single structural leader in each qualifying event
candidates = df[df["structural_ok"] & df["fr_ld_flag"]].copy()
print("Structural leader candidates:", len(candidates))

# -----------------------------
# Sample-size guard
# -----------------------------
candidates = candidates[candidates["Horse Qty__num"] >= MIN_HORSE_QTY].copy()
print(f"After Horse Qty >= {MIN_HORSE_QTY}: {len(candidates)}")

# -----------------------------
# Quality points (3)
# -----------------------------
candidates["cond_br"] = candidates["Br ROI %__num"] > -10
candidates["cond_l100"] = (
    (candidates["Dr L/100 ROI %__num"] > 0) |
    (candidates["Tr L/100 ROI %__num"] > 0)
)
candidates["cond_odds"] = candidates["Fair Odds__num"] < 5  # informational but scored

quality_cols = ["cond_br", "cond_l100", "cond_odds"]
candidates["quality_score"] = candidates[quality_cols].sum(axis=1)

def tier(score):
    if score == 3:
        return "Tier 3 🦄🦄🦄"
    elif score == 2:
        return "Tier 2 🦄🦄"
    elif score == 1:
        return "Tier 1 🦄"
    else:
        return ""

candidates["UnicornTier"] = candidates["quality_score"].apply(tier)

# Keep Tier 1+
candidates = candidates[candidates["quality_score"] >= 1].copy()

# Sort strongest first, then shortest odds, then best Br ROI
candidates = candidates.sort_values(
    by=["quality_score", "Fair Odds__num", "Br ROI %__num"],
    ascending=[False, True, False],
    na_position="last"
)

# Save (local)
candidates.to_csv(OUTPUT_CSV, index=False)
print(f"\n✅ Saved -> {OUTPUT_CSV}")

# Copy to both app asset folders
copy_output_to_targets(OUTPUT_CSV, COPY_TARGET_DIRS)

print("\nTier breakdown:")
print(candidates["UnicornTier"].value_counts())

# -----------------------------
# Console output: show who they are
# -----------------------------
print("\n==============================")
print("🦄 UNICORN RESULTS")
print("==============================")

if len(candidates) == 0:
    print("No unicorns found.")
else:
    for tier_name in ["Tier 3 🦄🦄🦄", "Tier 2 🦄🦄", "Tier 1 🦄"]:
        tier_df = candidates[candidates["UnicornTier"] == tier_name]
        if len(tier_df) == 0:
            continue

        print(f"\n{tier_name} ({len(tier_df)})")
        print("-" * 70)

        cols = [
            EVENT_KEY,
            "Race No" if "Race No" in candidates.columns else None,
            "Horse" if "Horse" in candidates.columns else None,
            "Barrier",
            "Horse Qty",
            "Ld %",
            "Dth %",
            "Fair Odds",
            "Br ROI %",
            "Dr L/100 ROI %",
            "Tr L/100 ROI %",
            "cond_br",
            "cond_l100",
            "cond_odds",
            "quality_score",
        ]
        cols = [c for c in cols if c is not None and c in candidates.columns]

        print(tier_df[cols].to_string(index=False))

print("\n==============================")
print(f"Total Unicorns: {len(candidates)}")
print("==============================\n")
