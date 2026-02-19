import pandas as pd
from datetime import datetime, timedelta

# ---------- helpers ----------
def to_num(series: pd.Series) -> pd.Series:
    """
    Convert money/odds strings like '$3.30', '3.30', '1,234.56', '-', '' to float.
    """
    s = series.astype(str).str.strip()

    # common null-ish
    s = s.replace({"": None, "nan": None, "None": None, "NULL": None, "-": None})

    # remove currency symbols/commas/extra spaces
    s = s.str.replace(r"[\$,]", "", regex=True)

    # sometimes odds/sp come like '3.30*' or '3.30 (F)' etc — keep only number-like chars
    s = s.str.replace(r"[^0-9\.\-]", "", regex=True)

    return pd.to_numeric(s, errors="coerce")

def pick_date_col(df: pd.DataFrame) -> str:
    # prefer an ISO Date column if you have it; otherwise 'Date'
    for c in ["ISODate", "DateISO", "RaceDateISO", "Date"]:
        if c in df.columns:
            return c
    raise KeyError("No date column found (expected something like 'Date').")

# ---------- load ----------
df = pd.read_csv("merged_file.csv", low_memory=False)

date_col = pick_date_col(df)

# parse date (AU day-first is common in your pipeline)
df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)

# numeric conversions
for col in ["Published P&L", "Published Spend", "Published Odds", "SP"]:
    if col in df.columns:
        df[col] = to_num(df[col])
    else:
        print(f"⚠️ Missing column: {col}")

# ---------- filter to last 30 days ----------
cutoff = pd.Timestamp.now() - pd.Timedelta(days=30)
df_30 = df[df[date_col] >= cutoff].copy()

# ---------- diagnostics ----------
print("---- Diagnostics ----")
print(f"Total rows: {len(df):,}")
print(f"Rows with valid {date_col}: {df[date_col].notna().sum():,}")
print(f"Rows in last 30 days: {len(df_30):,}")
for col in ["Published Spend", "Published P&L", "Published Odds", "SP"]:
    if col in df.columns:
        print(f"Non-null {col} (30d): {df_30[col].notna().sum():,}")

# Keep only rows where we actually have a published bet (spend > 0)
df_pub = df_30[df_30["Published Spend"].fillna(0) > 0].copy()
print(f"Rows with Published Spend > 0 (30d): {len(df_pub):,}")

# ---------- model ROI ----------
model_spend = df_pub["Published Spend"].sum()
model_pl = df_pub["Published P&L"].sum()
model_roi = (model_pl / model_spend) if model_spend > 0 else 0.0

# ---------- overlay ROI ----------
# Overlay rule: Published Odds < SP (both numeric now)
overlay_df = df_pub[
    df_pub["Published Odds"].notna()
    & df_pub["SP"].notna()
    & (df_pub["Published Odds"] < df_pub["SP"])
].copy()

overlay_spend = overlay_df["Published Spend"].sum()
overlay_pl = overlay_df["Published P&L"].sum()
overlay_roi = (overlay_pl / overlay_spend) if overlay_spend > 0 else 0.0

print(f"Overlay rows (30d): {len(overlay_df):,}")

# percentage outputs
model_roi_pct = round(model_roi * 100, 1)
overlay_roi_pct = round(overlay_roi * 100, 1)

metrics = pd.DataFrame([{
    "AsOfDate": datetime.now().strftime("%Y-%m-%d"),
    "ModelRoi30": model_roi_pct,
    "OverlayRoi30": overlay_roi_pct,
    "Rows30d": int(len(df_pub)),
    "OverlayRows30d": int(len(overlay_df)),
}])

metrics.to_csv("model_metrics.csv", index=False)

print("\nSaved model_metrics.csv")
print(metrics)
