# fair_odds_lookup.py
import sys
import pandas as pd

CSV_PATH = "upcoming_fields.csv"

def norm(s: str) -> str:
    return str(s).strip().upper()

def main():
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
    except FileNotFoundError:
        print(f"❌ Can't find {CSV_PATH} in the current folder.")
        sys.exit(1)

    # Basic column checks
    if "Horse" not in df.columns:
        print("❌ Column 'Horse' not found in upcoming_fields.csv")
        print(f"   Columns: {list(df.columns)}")
        sys.exit(1)

    if "Fair Odds" not in df.columns:
        print("❌ Column 'Fair Odds' not found in upcoming_fields.csv")
        fair_like = [c for c in df.columns if "fair" in c.lower() or "odds" in c.lower()]
        print(f"   Closest columns: {fair_like}")
        sys.exit(1)

    # Precompute normalised horse names once (fast lookups)
    horse_norm = df["Horse"].astype(str).map(norm)

    print("Type a horse name and press Enter. Type 'q' to quit.\n")

    while True:
        try:
            name = input("Horse> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return

        if not name:
            continue
        if name.lower() in ("q", "quit", "exit"):
            print("Bye.")
            return

        key = norm(name)
        matches = df[horse_norm == key]

        if matches.empty:
            # Helpful: show partial matches
            partial = df[df["Horse"].astype(str).str.upper().str.contains(key, na=False)]
            print(f"❌ Not found: {name}")
            if not partial.empty:
                print("   Partial matches:")
                for h in partial["Horse"].dropna().astype(str).head(10):
                    print(f"   - {h}")
            continue

        # If multiple rows, show them all with some context
        show_cols = [c for c in ["Venue", "Race No", "Time", "Horse", "Fair Odds", "Fair %"] if c in matches.columns]
        out = matches[show_cols].copy()

        # Make Fair Odds numeric where possible, but keep original if not
        try:
            out["Fair Odds"] = pd.to_numeric(out["Fair Odds"], errors="coerce")
        except Exception:
            pass

        print(out.to_string(index=False))
        print()

if __name__ == "__main__":
    main()
