import subprocess
import sys
from pathlib import Path

# Force all scripts to run as if they were launched from the repo root,
# so relative outputs land in the repo root (not in scrapers/).
REPO_ROOT = Path(__file__).resolve().parents[1]  # scrapers/ -> repo root

def run(script_name: str):
    script_path = REPO_ROOT / "scrapers" / script_name
    print(f"▶️ Starting {script_name}...")
    subprocess.run([sys.executable, str(script_path)], cwd=str(REPO_ROOT), check=True)
    print(f"✅ Finished {script_name}.\n")

def main():
    run("scrape_trials.py")
    run("scrape_results.py")

    run("cold_drivers.py")
    run("colddrivers30.py")
    run("coldtrainers.py")
    run("coldtrainers30.py")

    run("hot_drivers.py")
    run("hotdrivers30.py")
    run("hot_trainers.py")
    run("hottrainers30.py")

    run("scrape_fields.py")
    run("scrape_unicorns.py")
    run("calc_model_metrics.py")

    # Your uploader (uploads from repo root to harness-csv-data repo root)
    run("upload_csv_to_github.py")

if __name__ == "__main__":
    main()
