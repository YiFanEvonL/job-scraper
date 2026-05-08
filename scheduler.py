"""
Daily scheduler — run this once and leave it running.
It will call job_scraper.py every day at 8:00 AM.
"""
import schedule
import time
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "job_scraper.py"
RUN_AT = "08:00"   # ✏️ change this time if you prefer


def run_scraper():
    print(f"[scheduler] Running scraper at {RUN_AT}...")
    result = subprocess.run([sys.executable, str(SCRIPT)])
    if result.returncode == 0:
        print("[scheduler] Scraper finished successfully.")
    else:
        print("[scheduler] Scraper exited with errors.")


schedule.every().day.at(RUN_AT).do(run_scraper)
print(f"[scheduler] Waiting — will run job scraper every day at {RUN_AT}")
print("[scheduler] Press Ctrl+C to stop.\n")

while True:
    schedule.run_pending()
    time.sleep(30)
