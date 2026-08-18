# 🍁 Toronto Job Scraper

An automated job scraper that collects junior/entry-level postings from multiple platforms daily, deduplicates them, and delivers a formatted email digest — purpose-built for a Healthcare IT / Data Analytics job search in Toronto.

> Feeds the **[Toronto Job Market Dashboard](https://github.com/YiFanEvonL/job-market-dashboard)** · 1,100+ jobs tracked · Running since May 2026

---

## ✨ Features

- **Multi-platform scraping** — Indeed, LinkedIn (RSS), Greenhouse, Lever, Job Bank Canada
- **Smart deduplication** — SQLite-backed; never sends the same job twice
- **Targeted keyword sets** — tuned for Healthcare IT, Clinical Informatics, Data Analytics, Junior Dev, and Admin roles
- **Title filtering** — automatically excludes senior/lead/manager roles and unrelated industries (food service, real estate, etc.)
- **Daily email digest** — HTML email with clickable job links, grouped by platform
- **ATS keyword checker** — `ats_checker.py` scans your résumé `.docx` against a job's required keywords and reports hit rate
- **Dashboard integration** — outputs feed directly into `prepare_dashboard_data.py` → `dashboard.html`
- **Flexible scheduling** — cron, Python scheduler, or Windows Task Scheduler

---

## 🛠️ Tech Stack

| | |
|---|---|
| Language | Python 3.11 |
| HTTP | `requests` |
| Storage | SQLite3 |
| Email | `smtplib` · Gmail App Password |
| Scheduling | `schedule` · cron |
| ATS checker | `python-docx` |
| Dashboard ETL | `pandas` |

---

## 🚀 Quick Start

### 1. Install dependencies

```bash
pip install requests schedule python-docx pandas python-dotenv
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env`:
```
EMAIL_FROM=your_gmail@gmail.com
EMAIL_TO=your_gmail@gmail.com
EMAIL_APPPASS=xxxx xxxx xxxx xxxx
```

> **How to get a Gmail App Password:**
> Google Account → Security → 2-Step Verification → App Passwords → Create

### 3. Run once (test)

```bash
python job_scraper.py
```

Check your inbox — you should receive an email with today's new jobs.

### 4. Schedule daily runs

**macOS / Linux (cron):**
```bash
crontab -e
# Add:
0 8 * * * /usr/bin/python3 /path/to/job_scraper.py
```

**Python scheduler (cross-platform):**
```bash
python scheduler.py   # runs at 08:00 daily, keep window open
```

---

## 🎯 Customise Search Queries

Edit `SEARCH_QUERIES` in `job_scraper.py`:

```python
SEARCH_QUERIES = [
    "junior developer Toronto",
    "health informatics analyst Toronto",
    "healthcare data analyst Toronto entry level",
    "EHR analyst Toronto entry level",
    # add your own:
    "clinical data analyst Toronto",
]
```

Add exclusions to `EXCLUDE_TITLE_WORDS` or `EXCLUDE_INDUSTRY_WORDS` to filter noise.

---

## 🧪 ATS Keyword Checker

Check how well your résumé matches a job posting's required keywords:

```bash
python ats_checker.py "Yi-Fan Lin Resume.docx" "Python,ETL,SQL,PHIPA,clinical informatics"
```

Output:
```
  ✅  Python
  ✅  ETL
  ✅  SQL
  ❌  PHIPA
  ❌  clinical informatics

ATS hit rate: 3/5 (60%)
```

---

## 📁 Repo Structure

```
├── job_scraper.py            # Main scraper — multi-platform, dedup, email
├── scheduler.py              # Daily scheduler wrapper
├── ats_checker.py            # Résumé keyword hit-rate checker
├── prepare_dashboard_data.py # ETL: seen_jobs.db → CSV + dashboard.html
├── .env.example              # Credential template
├── .gitignore
└── README.md
```

> `seen_jobs.db`, `scraper.log`, and `application_log.csv` are git-ignored (local only).

---

## 🔗 Related

- **[job-market-dashboard](https://github.com/YiFanEvonL/job-market-dashboard)** — interactive HTML dashboard visualising scraper output

---

## 👤 Author

**Yi-Fan Lin** — RN turned software developer · Toronto, ON
[GitHub](https://github.com/YiFanEvonL) · [LinkedIn](https://linkedin.com/in/yifanlin)
