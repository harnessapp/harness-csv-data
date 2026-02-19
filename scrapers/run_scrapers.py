import subprocess

print("▶️ Starting scrape_trials.py...")
subprocess.run(["python", "scrape_trials.py"])
print("✅ Finished scrape_trials.py.\n")

print("▶️ Starting scrape_results.py...")
subprocess.run(["python", "scrape_results.py"])
print("✅ Finished scrape_results.py.\n")

print("▶️ Starting cold_drivers.py...")
subprocess.run(["python", "cold_drivers.py"])
print("✅ Finished cold_drivers.py.\n")

print("▶️ Starting colddrivers30.py...")
subprocess.run(["python", "colddrivers30.py"])
print("✅ Finished colddrivers30.py.\n")

print("▶️ Starting coldtrainers.py...")
subprocess.run(["python", "coldtrainers.py"])
print("✅ Finished coldtrainers.py.\n")

print("▶️ Starting coldtrainers30.py...")
subprocess.run(["python", "coldtrainers30.py"])
print("✅ Finished coldtrainers30.py.\n")

print("▶️ Starting hot_drivers.py...")
subprocess.run(["python", "hot_drivers.py"])
print("✅ Finished hot_drivers.py.\n")

print("▶️ Starting hotdrivers30.py...")
subprocess.run(["python", "hotdrivers30.py"])
print("✅ Finished hotdrivers30.py.\n")

print("▶️ Starting hot_trainers.py...")
subprocess.run(["python", "hot_trainers.py"])
print("✅ Finished hot_trainers.py.\n")

print("▶️ Starting hottrainers30.py...")
subprocess.run(["python", "hottrainers30.py"])
print("✅ Finished hottrainers30.py.\n")

print("▶️ Starting scrape_fields.py...")
subprocess.run(["python", "scrape_fields.py"])
print("✅ Finished scrape_fields.py.")

print("▶️ Starting scrape_unicorns.py...")
subprocess.run(["python", "scrape_unicorns.py"])
print("✅ Finished scrape_unicorns.py.")

print("▶️ Starting calc_model_metrics.py...")
subprocess.run(["python", "calc_model_metrics.py"])
print("✅ Finished calc_model_metrics.py.")

print("🚀 Uploading to GitHub...")
subprocess.run(["python", "upload_csv_to_github.py"])
print("✅ Upload complete.")