"""
Toronto Junior Job Scraper
Tailored for: Nursing + Sociology + Computer Programming background
Searches: Indeed, LinkedIn (RSS), Glassdoor, Job Bank Canada
Sends daily email digest of new matching jobs
"""

import requests
import sqlite3
import smtplib
import json
import time
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

# ─────────────────────────────────────────────
# ✏️  YOUR SETTINGS — edit this section only
# ─────────────────────────────────────────────
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_TO      = os.getenv("EMAIL_TO")
EMAIL_APPPASS = os.getenv("EMAIL_APPPASS")

# Job keywords tuned to your background
SEARCH_QUERIES = [
    "junior developer Toronto",
    "junior software developer Toronto",
    "health informatics analyst Toronto",
    "clinical informatics Toronto",
    "healthcare data analyst Toronto entry level",
    "junior systems analyst Toronto",
    "junior business analyst healthcare Toronto",
    "nursing informatics Toronto",
    "junior programmer Toronto",
    "EHR analyst Toronto entry level",
]

# If ANY of these appear in a job title, it will be EXCLUDED
EXCLUDE_TITLE_WORDS = [
    "senior", "sr.", "lead", "manager", "director",
    "principal", "staff", "vice president", "vp",
]

DB_FILE = Path(__file__).parent / "seen_jobs.db"
# ─────────────────────────────────────────────


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id TEXT PRIMARY KEY,
            title  TEXT,
            company TEXT,
            added_at TEXT
        )
    """)
    conn.commit()
    return conn


def is_new(conn, job_id):
    cur = conn.execute("SELECT 1 FROM seen_jobs WHERE job_id=?", (job_id,))
    return cur.fetchone() is None


def mark_seen(conn, job_id, title, company):
    conn.execute(
        "INSERT OR IGNORE INTO seen_jobs VALUES (?,?,?,?)",
        (job_id, title, company, datetime.now().isoformat())
    )
    conn.commit()


def is_excluded(title):
    title_lower = title.lower()
    return any(word in title_lower for word in EXCLUDE_TITLE_WORDS)


# ── Indeed (public RSS feed) ──────────────────
def scrape_indeed(query):
    jobs = []
    url = "https://ca.indeed.com/rss"
    params = {
        "q": query,
        "l": "Toronto, ON",
        "radius": "25",
        "sort": "date",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            return jobs
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:20]:
            title   = item.findtext("title", "").strip()
            link    = item.findtext("link", "").strip()
            company = item.findtext("source", "Unknown").strip()
            desc    = item.findtext("description", "").strip()
            # strip HTML tags from description
            desc = re.sub(r"<[^>]+>", "", desc)[:300]
            job_id  = "indeed_" + link[-40:].replace("/", "_")

            if title and not is_excluded(title):
                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "link": link,
                    "source": "Indeed",
                    "snippet": desc,
                })
    except Exception as e:
        print(f"Indeed error: {e}")
    return jobs


# ── LinkedIn (guest API — more reliable) ──
def scrape_linkedin(query):
    jobs = []
    url = "https://www.linkedin.com/jobs/search"
    params = {
        "keywords": query,
        "location": "Toronto, Ontario, Canada",
        "f_TPR": "r86400",   # past 24 hours
        "f_E": "1,2",        # entry level + internship
        "position": "1",
        "pageNum": "0",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-CA,en;q=0.9",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)

        # Extract job IDs
        job_ids = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d+)"', r.text)
        # Extract titles — LinkedIn uses these class patterns
        titles = re.findall(
            r'class="base-search-card__title"[^>]*>\s*([^<]+?)\s*<', r.text
        )
        companies = re.findall(
            r'class="base-search-card__subtitle"[^>]*>.*?<a[^>]*>\s*([^<]+?)\s*<',
            r.text, re.DOTALL
        )

        for i, jid in enumerate(job_ids[:15]):
            title   = titles[i].strip()   if i < len(titles)    else ""
            company = companies[i].strip() if i < len(companies) else "Unknown"
            if not title or is_excluded(title):
                continue
            jobs.append({
                "id": f"linkedin_{jid}",
                "title": title,
                "company": company,
                "link": f"https://www.linkedin.com/jobs/view/{jid}",
                "source": "LinkedIn",
                "snippet": "",
            })
    except Exception as e:
        print(f"LinkedIn error: {e}")
    return jobs


# ── Job Bank Canada (official government job board) ──
def scrape_jobbank(query):
    jobs = []
    url = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
    params = {
        "searchstring": query,
        "locationstring": "Toronto",
        "fsrc": "21",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)",
        "Accept-Language": "en-CA,en;q=0.9",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        # Extract job listings from Job Bank HTML
        job_blocks = re.findall(
            r'<article[^>]*class="[^"]*resultJobItem[^"]*"[^>]*>(.*?)</article>',
            r.text, re.DOTALL
        )
        for block in job_blocks[:15]:
            title_m   = re.search(r'<span[^>]*class="[^"]*noctitle[^"]*"[^>]*>([^<]+)</span>', block)
            company_m = re.search(r'<li[^>]*class="[^"]*business[^"]*"[^>]*>([^<]+)</li>', block)
            link_m    = re.search(r'href="(/en/job/\d+[^"]*)"', block)
            title   = title_m.group(1).strip()   if title_m   else ""
            company = company_m.group(1).strip() if company_m else "Unknown"
            link    = ("https://www.jobbank.gc.ca" + link_m.group(1)) if link_m else ""
            job_id  = "jobbank_" + re.search(r'/(\d+)', link).group(1) if link and re.search(r'/(\d+)', link) else ""
            if title and job_id and not is_excluded(title):
                jobs.append({
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "link": link,
                    "source": "Job Bank CA",
                    "snippet": "",
                })
    except Exception as e:
        print(f"Job Bank error: {e}")
    return jobs


def build_email_html(new_jobs):
    """Build a clean HTML email digest."""
    count = len(new_jobs)
    date_str = datetime.now().strftime("%B %d, %Y")

    # Group by source
    by_source = {}
    for job in new_jobs:
        by_source.setdefault(job["source"], []).append(job)

    rows = ""
    for source, jobs in by_source.items():
        rows += f"""
        <tr><td colspan="3" style="background:#f0f4ff;padding:8px 12px;font-weight:600;
            color:#3355aa;border-top:2px solid #c8d8ff;">{source} ({len(jobs)} jobs)</td></tr>
        """
        for j in jobs:
            snippet = f"<br><span style='color:#888;font-size:12px'>{j['snippet'][:200]}…</span>" if j.get("snippet") else ""
            rows += f"""
        <tr>
          <td style="padding:10px 12px;vertical-align:top;border-bottom:1px solid #eee">
            <a href="{j['link']}" style="color:#1a56db;font-weight:600;text-decoration:none">{j['title']}</a>
            {snippet}
          </td>
          <td style="padding:10px 12px;vertical-align:top;border-bottom:1px solid #eee;
              color:#555;white-space:nowrap">{j['company']}</td>
          <td style="padding:10px 12px;vertical-align:top;border-bottom:1px solid #eee">
            <a href="{j['link']}" style="background:#1a56db;color:#fff;padding:5px 12px;
               border-radius:4px;text-decoration:none;font-size:12px">Apply →</a>
          </td>
        </tr>
        """

    html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;color:#333">
      <div style="background:#1a56db;color:white;padding:20px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">🍁 Toronto Job Digest — {date_str}</h2>
        <p style="margin:6px 0 0;opacity:0.85">{count} new junior/entry-level jobs matching your profile</p>
      </div>

      <div style="background:#fff5e6;padding:12px 20px;border-left:4px solid #f59e0b;margin:16px 0">
        <strong>Your target roles:</strong> Junior Developer · Health Informatics · Clinical Analyst ·
        Healthcare Data Analyst · Junior BA/SA
      </div>

      <table width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
        <thead>
          <tr style="background:#f9fafb">
            <th style="text-align:left;padding:10px 12px;border-bottom:2px solid #e5e7eb">Job Title</th>
            <th style="text-align:left;padding:10px 12px;border-bottom:2px solid #e5e7eb">Company</th>
            <th style="padding:10px 12px;border-bottom:2px solid #e5e7eb"></th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>

      <p style="color:#888;font-size:12px;margin-top:16px;text-align:center">
        Auto-generated by your Toronto Job Scraper · Only new listings shown each day
      </p>
    </body></html>
    """
    return html


def send_email(new_jobs):
    if not new_jobs:
        print("No new jobs today — skipping email.")
        return

    html = build_email_html(new_jobs)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🍁 {len(new_jobs)} New Toronto Jobs — {datetime.now().strftime('%b %d')}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_APPPASS)
            server.send_message(msg)
        print(f"✅ Email sent: {len(new_jobs)} new jobs")
    except Exception as e:
        print(f"❌ Email failed: {e}")


def main():
    print(f"\n{'='*50}")
    print(f"  Job Scraper started — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    conn = init_db()
    all_jobs = []
    seen_ids = set()

    scrapers = [
        ("Indeed",   scrape_indeed),
        ("LinkedIn", scrape_linkedin),
        ("Job Bank", scrape_jobbank),
    ]

    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        for source_name, scraper_fn in scrapers:
            try:
                jobs = scraper_fn(query)
                print(f"   {source_name}: {len(jobs)} results")
                for job in jobs:
                    if job["id"] not in seen_ids and is_new(conn, job["id"]):
                        all_jobs.append(job)
                        seen_ids.add(job["id"])
            except Exception as e:
                print(f"   {source_name} error: {e}")
            time.sleep(1.5)   # be polite to servers
        time.sleep(2)

    print(f"\n📋 {len(all_jobs)} new jobs found across all platforms")

    # Save all new jobs to DB
    for job in all_jobs:
        mark_seen(conn, job["id"], job["title"], job["company"])

    conn.close()
    send_email(all_jobs)
    print("\nDone! ✨\n")


if __name__ == "__main__":
    main()
