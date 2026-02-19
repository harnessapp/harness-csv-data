import subprocess

print("▶️ Starting scrape_fields.py...")
subprocess.run(["python", "scrape_fields.py"])
print("✅ Finished scrape_fields.py.")

print("🚀 Uploading to GitHub...")
subprocess.run(["python", "upload_csv_to_github.py"])
print("✅ Upload complete.")