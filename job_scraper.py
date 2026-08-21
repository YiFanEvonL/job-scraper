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
import random
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
    # ── Track A/B/C: Healthcare IT / Data / Junior Tech (existing) ──
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

    # ── Entry-level Health Information Management / Records ──
    "health information management coordinator Toronto",
    "health information clerk Toronto",
    "health records clerk Toronto",
    "data coordinator hospital Toronto",
    "data quality coordinator health Toronto",
    "medical records clerk Toronto",

    # ── Entry-level Clerical / Administrative (hospital & health org) ──
    "clerical assistant hospital Toronto",
    "administrative assistant healthcare Toronto",
    "team assistant healthcare Toronto",
    "unit clerk hospital Toronto",
    "patient registration coordinator Toronto",
    "patient access coordinator Toronto",
    "scheduling coordinator healthcare Toronto",
    "scheduling and registration coordinator Toronto",
    "medical office assistant Toronto",

    # ── Help Desk / IT Support (stepping stone into Healthcare IT) ──
    "IT support analyst Toronto",
    "help desk analyst Toronto",
    "service desk analyst Toronto",
    "desktop support Toronto",
    "application support analyst Toronto",
    "IT technician Toronto entry level",
    "level 1 IT support Toronto",
    "level 2 IT support Toronto",
    "healthcare IT support Toronto",

    # ── Data / ETL ──
    "junior data analyst Toronto",
    "ETL developer junior Toronto",
    "BI analyst Toronto entry level",
    "reporting analyst Toronto",
    "junior SQL developer Toronto",

    # ── QA / Junior Dev ──
    "QA analyst Toronto",
    "QA tester Toronto entry level",
    "test analyst Toronto",
    "junior software QA engineer Toronto",
]

# If ANY of these appear in a job title, it will be EXCLUDED
EXCLUDE_TITLE_WORDS = [
    "senior", "sr.", "lead", "manager", "director",
    "principal", "staff", "vice president", "vp",
]

# If ANY of these appear in a job title, it will be EXCLUDED regardless of
# other matches — used to filter out unrelated industries/roles that get
# picked up by broad keyword matches (e.g. "assistant", "coordinator")
EXCLUDE_INDUSTRY_WORDS = [
    # Food & hospitality
    "expeditor", "server", "bartender", "cook", "chef", "barista",
    "host/hostess", "hostess", "waiter", "waitress", "dishwasher",
    "kitchen", "restaurant", "banquet", "catering", "sommelier",

    # Sales / Marketing / Real Estate
    "sales representative", "sales associate", "account executive",
    "marketing coordinator", "real estate", "leasing", "realtor",

    # Enterprise SaaS / IT system admin (different track — NetSuite, Salesforce, etc.)
    "enterprise application", "netsuite", "salesforce administrator",
    "salesforce admin", "sap administrator", "workday administrator",

    # Trades / Retail / Other unrelated
    "warehouse", "forklift", "driver", "delivery driver",
    "construction", "electrician", "plumber", "cashier",
    "stylist", "esthetician", "personal trainer", "fitness instructor",
]

# Keywords that, if found in a job title alongside a generic word like
# "assistant" / "coordinator" / "admin", confirm relevance to your target tracks
RELEVANT_CONTEXT_WORDS = [
    "health", "healthcare", "hospital", "clinical", "medical",
    "patient", "nursing", "informatics", "records", "registration",
    "scheduling", "data", "research", "pharmacy", "laboratory",
    "support", "help desk", "service desk", "it support", "desktop",
    "application support", "qa", "quality assurance", "test", "sql",
    "etl", "reporting", "bi",
]

# Keywords to match in job titles when scraping company career pages
COMPANY_JOB_KEYWORDS = [
    # Technical / informatics
    "developer", "programmer", "engineer", "software",
    "analyst", "informatics", "data", "ehr", "healthcare",
    "health", "clinical", "nursing", "systems",
    "junior", "entry", "associate", "intern",

    # Health Information Management / Records
    "health information", "medical records", "registration coordinator", "data coordinator",

    # Clerical / Administrative (kept specific to avoid false positives
    # like "Enterprise Application Administrator" or restaurant "Assistant Manager")
    "clerical assistant", "administrative assistant", "medical office assistant",
    "patient access", "unit clerk", "scheduling coordinator",
    "scheduling and registration",

    # Help Desk / IT Support
    "help desk", "service desk", "it support", "desktop support",
    "application support", "it technician", "technical support",

    # Data / ETL / QA
    "etl", "reporting analyst", "bi analyst", "sql developer",
    "qa analyst", "qa tester", "test analyst", "quality assurance",
]

# Accepted locations for company career pages (substring match, case-insensitive)
ACCEPTED_LOCATIONS = ["toronto", "ontario", "canada", "remote"]

# Reject if location explicitly names a non-Canadian country/region
# (takes precedence over "remote" — e.g. "US - Remote" is still rejected)
REJECTED_LOCATIONS = [
    "united states", "usa", " us,", "us -", ", us)",
    "united kingdom", "u.k.", " uk,", "uk -", ", uk)",
    "australia", "germany", "france", "netherlands",
    "hungary", "belgium", "japan", "india", "mexico",
    "brazil", "singapore", "ireland",
]

# ── Companies using Greenhouse ATS ──
# Find more at: https://boards.greenhouse.io/{slug}
GREENHOUSE_COMPANIES = {
    "hootsuite":    "Hootsuite",
    "d2l":          "D2L (Brightspace)",
    "tulip":        "Tulip Retail",
    "flipp":        "Flipp",
    "mejuri":       "Mejuri",           # Toronto
    "ecobee":       "Ecobee",           # Toronto smart home
    "faire":        "Faire",
}

# ── Companies using Lever ATS ──
# Find more at: https://jobs.lever.co/{slug}
LEVER_COMPANIES = {
    "pointclickcare":   "PointClickCare",  # Toronto health IT — great fit!
    "fullscript":       "Fullscript",      # Ottawa health tech
    "mednow":           "MedNow",          # Canada pharmacy tech
}

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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS skipped_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            source TEXT,
            skip_reason TEXT,
            skipped_at TEXT
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


def log_skipped_job(conn, job_id, title, company, source, reason):
    if conn is None:
        return
    conn.execute(
        "INSERT OR IGNORE INTO skipped_jobs VALUES (?,?,?,?,?,?)",
        (job_id, title, company, source, reason, datetime.now().isoformat())
    )
    conn.commit()


def is_excluded(title):
    title_lower = title.lower()
    if any(word in title_lower for word in EXCLUDE_TITLE_WORDS):
        return True
    if any(word in title_lower for word in EXCLUDE_INDUSTRY_WORDS):
        return True
    return False


def get_exclusion_reason(title):
    """Return 'excluded_title', 'excluded_industry', or None."""
    title_lower = title.lower()
    if any(word in title_lower for word in EXCLUDE_TITLE_WORDS):
        return "excluded_title"
    if any(word in title_lower for word in EXCLUDE_INDUSTRY_WORDS):
        return "excluded_industry"
    return None


# Generic title words that are ambiguous on their own — if a title contains
# ONE of these AND nothing from RELEVANT_CONTEXT_WORDS, it's likely an
# unrelated role (e.g. "Administrative Assistant" at a law firm, "Assistant
# Manager" at a retail store) and gets filtered out.
AMBIGUOUS_GENERIC_WORDS = [
    "assistant", "coordinator", "administrator", "admin", "clerk",
]


def passes_relevance_filter(title):
    """Return True if the title should be kept.

    Titles containing a generic word (assistant/coordinator/admin/clerk)
    must also contain at least one relevant-context word (health, clinical,
    data, records, etc.) to be kept. Titles without any ambiguous generic
    word pass through unaffected (e.g. "Junior Developer Toronto").
    """
    title_lower = title.lower()
    has_generic = any(word in title_lower for word in AMBIGUOUS_GENERIC_WORDS)
    if not has_generic:
        return True
    return any(word in title_lower for word in RELEVANT_CONTEXT_WORDS)


def is_relevant_title(title):
    title_lower = title.lower()
    return any(kw in title_lower for kw in COMPANY_JOB_KEYWORDS)


def is_accepted_location(location):
    if not location:
        return True
    loc_lower = location.lower()
    # Reject if explicitly a non-Canadian location (even if "remote" is present)
    if any(rej in loc_lower for rej in REJECTED_LOCATIONS):
        if not any(can in loc_lower for can in ["canada", "toronto", "ontario"]):
            return False
    return any(loc in loc_lower for loc in ACCEPTED_LOCATIONS)


# ── Indeed (public RSS feed) ──────────────────
def scrape_indeed(query, conn=None):
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

            if title:
                exc_reason = get_exclusion_reason(title)
                if exc_reason:
                    log_skipped_job(conn, job_id, title, company, "Indeed", exc_reason)
                elif not passes_relevance_filter(title):
                    log_skipped_job(conn, job_id, title, company, "Indeed", "failed_relevance")
                else:
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


# ── LinkedIn (HTML scraping — guest search page) ──
def scrape_linkedin_rss(query, conn=None):
    jobs = []
    url = "https://www.linkedin.com/jobs/search"
    params = {
        "keywords": query,
        "location": "Toronto, Ontario, Canada",
        "f_TPR": "r86400",
        "f_E": "1,2",
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
        job_ids = re.findall(r'data-entity-urn="urn:li:jobPosting:(\d+)"', r.text)
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
            if not title:
                continue
            exc_reason = get_exclusion_reason(title)
            if exc_reason:
                log_skipped_job(conn, f"linkedin_{jid}", title, company, "LinkedIn", exc_reason)
                continue
            if not passes_relevance_filter(title):
                log_skipped_job(conn, f"linkedin_{jid}", title, company, "LinkedIn", "failed_relevance")
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
    time.sleep(random.uniform(3, 5))
    return jobs


# ── Job Bank Canada (official government job board) ──
def scrape_jobbank(query, conn=None):
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
            if title and job_id:
                exc_reason = get_exclusion_reason(title)
                if exc_reason:
                    log_skipped_job(conn, job_id, title, company, "Job Bank CA", exc_reason)
                elif not passes_relevance_filter(title):
                    log_skipped_job(conn, job_id, title, company, "Job Bank CA", "failed_relevance")
                else:
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


# ── Greenhouse ATS (public JSON API) ─────────────────────────────────────────
def scrape_greenhouse(slug, company_name, conn=None):
    jobs = []
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"   Greenhouse [{slug}] HTTP {r.status_code}")
            return jobs
        for job in r.json().get("jobs", []):
            title    = job.get("title", "").strip()
            location = job.get("location", {}).get("name", "")
            link     = job.get("absolute_url", "")
            job_id   = f"greenhouse_{slug}_{job.get('id', '')}"

            if not title:
                continue
            exc_reason = get_exclusion_reason(title)
            if exc_reason:
                log_skipped_job(conn, job_id, title, company_name, "Company Pages", exc_reason)
                continue
            if not is_relevant_title(title):
                continue
            if not is_accepted_location(location):
                continue

            jobs.append({
                "id":      job_id,
                "title":   title,
                "company": company_name,
                "link":    link,
                "source":  "Company Pages",
                "snippet": location,
            })
    except Exception as e:
        print(f"   Greenhouse [{slug}] error: {e}")
    return jobs


# ── Lever ATS (public JSON API) ──────────────────────────────────────────────
def scrape_lever(slug, company_name, conn=None):
    jobs = []
    url = f"https://api.lever.co/v0/postings/{slug}"
    params  = {"mode": "json"}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"   Lever [{slug}] HTTP {r.status_code}")
            return jobs
        for job in r.json():
            title    = job.get("text", "").strip()
            location = job.get("categories", {}).get("location", "")
            link     = job.get("hostedUrl", "")
            job_id   = f"lever_{slug}_{job.get('id', '')}"

            if not title:
                continue
            exc_reason = get_exclusion_reason(title)
            if exc_reason:
                log_skipped_job(conn, job_id, title, company_name, "Company Pages", exc_reason)
                continue
            if not is_relevant_title(title):
                continue
            if not is_accepted_location(location):
                continue

            jobs.append({
                "id":      job_id,
                "title":   title,
                "company": company_name,
                "link":    link,
                "source":  "Company Pages",
                "snippet": location,
            })
    except Exception as e:
        print(f"   Lever [{slug}] error: {e}")
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
        Healthcare Data Analyst · Junior BA/SA · Health Information Management Coordinator ·
        Health Records / Data Coordinator · Clerical / Administrative / Team Assistant (Healthcare) ·
        Help Desk / IT Support · Junior Data / ETL / BI Analyst · QA Analyst / Tester
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
        ("LinkedIn", scrape_linkedin_rss),
        ("Job Bank", scrape_jobbank),
    ]

    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        for source_name, scraper_fn in scrapers:
            try:
                jobs = scraper_fn(query, conn)
                print(f"   {source_name}: {len(jobs)} results")
                for job in jobs:
                    if job["id"] not in seen_ids and is_new(conn, job["id"]):
                        all_jobs.append(job)
                        seen_ids.add(job["id"])
            except Exception as e:
                print(f"   {source_name} error: {e}")
            time.sleep(1.5)   # be polite to servers
        time.sleep(2)

    # ── Company career pages (Greenhouse + Lever) ──
    print("\n🏢 Scraping company career pages...")
    for slug, name in GREENHOUSE_COMPANIES.items():
        jobs = scrape_greenhouse(slug, name, conn)
        print(f"   Greenhouse [{name}]: {len(jobs)} matched")
        for job in jobs:
            if job["id"] not in seen_ids and is_new(conn, job["id"]):
                all_jobs.append(job)
                seen_ids.add(job["id"])
        time.sleep(1)

    for slug, name in LEVER_COMPANIES.items():
        jobs = scrape_lever(slug, name, conn)
        print(f"   Lever [{name}]: {len(jobs)} matched")
        for job in jobs:
            if job["id"] not in seen_ids and is_new(conn, job["id"]):
                all_jobs.append(job)
                seen_ids.add(job["id"])
        time.sleep(1)

    print(f"\n📋 {len(all_jobs)} new jobs found across all platforms")

    # Save all new jobs to DB
    for job in all_jobs:
        mark_seen(conn, job["id"], job["title"], job["company"])

    conn.close()
    send_email(all_jobs)
    print("\nDone! ✨\n")


if __name__ == "__main__":
    main()