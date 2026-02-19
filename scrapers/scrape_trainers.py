import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import random


# --- CONFIG ---
DAYS_BACK = 180
OUTPUT_FILE = "trainer_results.csv"  # The new output file for trainer data

# --- VENUE CODE AND STATE MAP ---
venue_code_map = {
    "Armidale": "AE",
    "Albury": "AL",
    "Albion Park": "AP",
    "Ararat": "AR",
    "Gawler": "AW",
    "Albany": "AY",
    "Ballarat": "BA",
    "Blayney": "BB",
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
    "South Australia": "DZ",
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
    "Orange at Bathurst": "LH",
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
    "Mildura at Swan Hill": "QA",
    "Wedderburn at Maryborough": "QP",
    "Wangaratta at Shepparton": "QY",
    "St Arnaud at Charlton": "QZ",
    "Redcliffe": "RE",
    "St Arnaud": "SA",
    "Scottsdale": "SC",
    "Shepparton": "SP",
    "Strathalbyn at Globe Derby Park": "SQ",
    "Strathalbyn": "ST",
    "Stawell": "SW",
    "Tamworth": "TA",
    "Terang": "TE",
    "Temora": "TM",
    "Marburg": "UG",
    "Kadina at Port Pirie": "UI",
    "Mooroopna at Shepparton": "VC",
    "Victor Harbor": "VH",
    "Elmore at Bendigo": "VL",
    "Kyabram at Shepparton": "VV",
    "Wagin": "WA",
    "Wedderburn": "WD",
    "West Wyalong": "WE",
    "Wangaratta": "WN",
    "Warragul": "WR",
    "Williams": "WS",
    "Yarra Valley": "YG",
    "Young": "YU",

    # Add rest from your full map
}

def scrape_meeting_results(venue_code, date_str):
    venue_url = f"https://www.harness.org.au/racing/fields/race-fields/?mc={venue_code}{date_str}"
    print(f"✅ Processing {venue_code}{date_str}")
    
    try:
        response = requests.get(venue_url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        h2_tag = soup.find("h2")
        if not h2_tag:
            print(f"⚠️ No <h2> tag found for {venue_code}{date_str}")
            return []

        h2_text = h2_tag.get_text(strip=True)
        venue = h2_text.split("(")[0].strip()
        meeting_time = "Unknown"
        if "(" in h2_text and ")" in h2_text:
            meeting_time = h2_text.split("(")[1].split(")")[0]

        results = parse_race_results(soup, venue, date_str, venue_code, meeting_time)

        # Only sleep if we actually parsed something
        sleep_time = random.uniform(3.5, 6.0)
        print(f"⏳ Sleeping for {sleep_time:.1f} seconds...\n")
        time.sleep(sleep_time)

        return results

    except Exception as e:
        print(f"❌ Failed {venue_code}{date_str}: {e}")
        return []


def parse_race_results(soup, venue, date_str, venue_code, meeting_time):
    results = []

    # Only look for trainer-related data
    runner_tables = soup.find_all("table", class_="raceFieldTable resultTable")

    for runner_table in runner_tables:
        try:
            runner_rows = runner_table.find_all("tr")
            for row in runner_rows:
                trainer_short_tag = row.find("td", class_="trainer-short")
                trainer_full_tag = row.find("td", class_="trainer")
                
                trainer_short = trainer_short_tag.get_text(strip=True) if trainer_short_tag else ""
                trainer_full = trainer_full_tag.get_text(strip=True) if trainer_full_tag else ""

                results.append({
                    "Trainer": trainer_full,
                    "Trainer Short": trainer_short,
                })
        except Exception as e:
            print(f"⚠️ Error parsing row: {e}")
            continue

    return results


# --- MAIN SCRIPT ---
all_results = []

# Use yesterday's date as the anchor
start_date = datetime.today() - timedelta(days=1)

# Adjust loop to go back from the entered date
for delta in range(DAYS_BACK):
    scrape_date = start_date - timedelta(days=delta)
    date_str = scrape_date.strftime("%d%m%y")

    for venue_name, venue_code in venue_code_map.items():
        results = scrape_meeting_results(venue_code, date_str)
        all_results.extend(results)

        # Global pause after every venue scrape (even if nothing parsed)
        time.sleep(random.uniform(1.0, 2.0))  # Adjust if needed

# Convert and Save
if all_results:
    df = pd.DataFrame(all_results)

    # Save the results to the output file
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Saved results to {OUTPUT_FILE} with {len(df)} total rows.")
