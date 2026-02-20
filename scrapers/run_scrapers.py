import subprocess
import sys
from pathlib import Path

# Force all scripts to run as if they were launched from the repo root,
# so relative outputs land in the repo root (not in scrapers/).
REPO_ROOT = Path(__file__).resolve().parents[1]  # scrapers/ -> repo root

def run(script_name: str):
    script_path = REPO_ROOT / "scrapers" / script_name
    print(f"▶️ Starting {script_name}...", flush=True)
    subprocess.run([sys.executable, str(script_path)], cwd=str(REPO_ROOT), check=True)
    print(f"✅ Finished {script_name}.\n", flush=True)

def debug_after_scrape_results():
    repo_root = REPO_ROOT
    print("🔎 DEBUG: listing repo root after scrape_results...", flush=True)
    print(f"Repo root: {repo_root}", flush=True)

    print("Files in repo root:", flush=True)
    for p in sorted(repo_root.iterdir()):
        if p.is_file():
            print(f"  - {p.name} ({p.stat().st_size} bytes)", flush=True)

    print("🔎 DEBUG: searching for merged_file.csv under repo root...", flush=True)
    found = list(repo_root.rglob("merged_file.csv"))
    if found:
        for p in found[:20]:
            print(f"  ✅ found: {p} ({p.stat().st_size} bytes)", flush=True)
    else:
        print("  ❌ merged_file.csv not found anywhere under repo root.", flush=True)

def main():
    run("scrape_trials.py")
    run("scrape_results.py")

    # ✅ debug right here (after scrape_results)
    debug_after_scrape_results()

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

    run("upload_csv_to_github.py")

if __name__ == "__main__":
    main()
