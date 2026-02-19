# race_anchor_lookup.py
import sys
import pandas as pd

CSV_PATH = "upcoming_fields.csv"

def norm(s):
    return str(s).strip().upper()

def main():
    try:
        df = pd.read_csv(CSV_PATH, low_memory=False)
    except FileNotFoundError:
        print(f"❌ {CSV_PATH} not found in this folder")
        sys.exit(1)

    if "RaceAnchorFull" not in df.columns:
        print("❌ Column 'RaceAnchorFull' not found in upcoming_fields.csv")
        print("Available columns:")
        print(list(df.columns))
        sys.exit(1)

    # Normalised column for matching
    df["_RAF"] = df["RaceAnchorFull"].astype(str).map(norm)

    print("Enter RaceAnchorFull (e.g. GD280126_R4)")
    print("Type q to quit\n")

    while True:
        try:
            val = input("RaceAnchorFull> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not val:
            continue
        if val.lower() in ("q", "quit", "exit"):
            print("Bye.")
            break

        key = norm(val)
        race = df[df["_RAF"] == key].copy()

        if race.empty:
            print(f"❌ No rows found for {val}")

            # Helpful partial matches
            partial = df[df["_RAF"].str.contains(key, na=False)]
            if not partial.empty:
                print("Closest matches:")
                for v in partial["RaceAnchorFull"].drop_duplicates().head(10):
                    print(" ", v)
            print()
            continue

        # Sort runners logically
        if "Barrier" in race.columns:
            race["_ord"] = pd.to_numeric(race["Barrier"], errors="coerce")
        else:
            race["_ord"] = range(len(race))

        race = race.sort_values("_ord", na_position="last")

        # Columns to print (only if they exist)
        cols = [
            "RaceAnchorFull",
            "Venue", "Date", "Race No",
            "Horse No", "Horse",
            "Driver",
            "Fair Odds",
            "Rating",
            "ExpectedRatingIndHalf",
            
        ]
        cols = [c for c in cols if c in race.columns]

        # Numeric formatting
        for c in ["Fair Odds", "Fair %"]:
            if c in race.columns:
                race[c] = pd.to_numeric(race[c], errors="coerce")

        # Ensure Horse No is numeric for correct sorting
        if "Horse No" in race.columns:
            race["Horse No"] = pd.to_numeric(race["Horse No"], errors="coerce")

        # Sort by Horse No
        race = race.sort_values("Horse No", na_position="last")

        print()
        print(race[cols].to_string(index=False))
        print()


if __name__ == "__main__":
    main()
