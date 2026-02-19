import pandas as pd
from datetime import datetime, timedelta
import os

# --- CONFIG ---
DAYS_BACK = 30  # Filter last 30 days
output_dir = os.path.join("C:\\", "Users", "joel", "FlutterProjects", "harness_app", "assets")  # Add the backslash after C
file_name = "Hot Drivers 30.csv"  # Ensure this is your intended output file
OUTPUT_FILE = os.path.join(output_dir, file_name)


# --- VENUE CODE AND STATE MAP ---
venue_code_map = {
    "Albion Park": "AP",
    # Add rest from your full map
}

# Load the merged file and strip any extra whitespace from column names
merged_df = pd.read_csv('merged_file.csv')

# Strip any extra whitespace from column names
merged_df.columns = merged_df.columns.str.strip()

# Print column names to verify
print("Columns in merged_df:", merged_df.columns)

# Ensure Date is in datetime format
merged_df['Date'] = pd.to_datetime(merged_df['Date'], format='%d/%m/%Y')

# Convert P&L and Spend to numeric, forcing errors to NaN (so we don't get string errors)
merged_df['P&L'] = pd.to_numeric(merged_df['P&L'], errors='coerce')
merged_df['Spend'] = pd.to_numeric(merged_df['Spend'], errors='coerce')

# Filter for the last 30 days of results
current_date = datetime.today()
thirty_days_ago = current_date - timedelta(days=DAYS_BACK)

# Filter out rows older than 30 days
merged_df = merged_df[merged_df['Date'] >= thirty_days_ago]

# Strip out rows where 'Placing' is blank or invalid
merged_df['Placing'] = pd.to_numeric(merged_df['Placing'], errors='coerce')
merged_df = merged_df[merged_df['Placing'].notna()]

# Sort the DataFrame by Driver and Date
merged_df = merged_df.sort_values(by=['Driver', 'Date'], ascending=[True, False])

# Create a new DataFrame for Hot Drivers (last 30 days)
hot_drivers = []

# Loop through each driver and calculate their stats
for driver, driver_df in merged_df.groupby('Driver'):
    # Get the races within the last 30 days for the driver
    last_30 = driver_df[driver_df['Date'] >= thirty_days_ago]
    
    # Only include drivers with results in the last 30 days
    if len(last_30) == 0:
        continue  # Skip this driver if they have no results in the last 30 days

    # Calculate the metrics
    starts = len(last_30)
    wins = (last_30['Placing'] == 1).sum()
    seconds = (last_30['Placing'] == 2).sum()
    thirds = (last_30['Placing'] == 3).sum()

    # Calculate Spend and P&L for the last 30 days
    total_spend = last_30['Spend'].sum()
    total_pnl = last_30['P&L'].sum()

    # Calculate ROI % (P&L / Spend)
    roi_percent = (total_pnl / total_spend) * 100 if total_spend != 0 else 0

    # Append the stats to the list
    hot_drivers.append({
        'Driver': driver,
        'Starts': starts,
        'Wins': wins,
        '2nds': seconds,
        '3rds': thirds,
        'Spend': total_spend,  # Add total Spend
        'P&L': total_pnl,      # Add total P&L
        'ROI %': roi_percent
    })

# Convert to a DataFrame
hot_drivers_df = pd.DataFrame(hot_drivers)

# Sort by Wins, then 2nds, then 3rds
hot_drivers_df = hot_drivers_df.sort_values(by=['Wins', '2nds', '3rds'], ascending=False)

# --- Optional: Add state filter ---
# Ensure state_filter is always defined
state_filter = "NSW"  # Set your default state filter here, or make it user-defined

# Check if 'State' column exists before filtering by State
if 'State' in hot_drivers_df.columns:
    hot_drivers_df = hot_drivers_df[hot_drivers_df['State'] == state_filter]

# Save to a new CSV
hot_drivers_df.to_csv(OUTPUT_FILE, index=False)

print(f"Hot Drivers (Last 30 Days) CSV has been created, filtered by {state_filter}!")
