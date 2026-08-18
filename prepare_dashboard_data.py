"""
Reads seen_jobs.db + application_log.csv
Outputs jobs_dashboard.csv + dashboard.html
"""

import sqlite3
import json
import pandas as pd
from pathlib import Path

DB_FILE  = Path(__file__).parent / "seen_jobs.db"
OUT_CSV  = Path(__file__).parent / "jobs_dashboard.csv"
OUT_HTML = Path(__file__).parent / "dashboard.html"
APP_LOG  = Path(__file__).parent / "application_log.csv"


def detect_source(job_id: str) -> str:
    if job_id.startswith("linkedin_"):   return "LinkedIn"
    if job_id.startswith("greenhouse_"): return "Greenhouse"
    if job_id.startswith("lever_"):      return "Lever"
    if job_id.startswith("indeed_"):     return "Indeed"
    if job_id.startswith("jobbank_"):    return "Job Bank CA"
    return "Other"


CATEGORY_RULES = [
    ("Co-op / Intern",         ["co-op", "coop", "intern"]),
    ("Software / Tech",        ["developer", "programmer", "engineer", "software", "it role"]),
    ("Data / Analytics",       ["data analyst", "data engineer", "data coordinator", "analytics", "data quality"]),
    ("Health Informatics",     ["informatics", "ehr", "clinical systems"]),
    ("Health Admin / Records", ["health information", "health records", "medical records",
                                 "registration coordinator", "patient registration", "patient access"]),
    ("Admin / Clerical",       ["administrative assistant", "clerical", "unit clerk",
                                 "medical office assistant", "scheduling coordinator",
                                 "scheduling and registration", "team assistant"]),
    ("Clinical / Nursing",     ["clinical", "nursing", "patient"]),
    ("Analyst / BA / SA",      ["analyst", "business analyst", "systems analyst"]),
]

def categorize(title: str) -> str:
    t = title.lower()
    for cat, kws in CATEGORY_RULES:
        if any(k in t for k in kws):
            return cat
    return "Other"


HEALTH_MERGE = {"Health Informatics", "Clinical / Nursing", "Health Admin / Records"}

CAT_COLOR_MAP = {
    "Software / Tech":          "#1a56db",
    "Other":                    "#94a3b8",
    "Analyst / BA / SA":        "#3b82f6",
    "Healthcare IT / Clinical": "#10b981",
    "Co-op / Intern":           "#93c5fd",
    "Data / Analytics":         "#60a5fa",
    "Admin / Clerical":         "#bfdbfe",
}

STATUS_ORDER = ["Applied", "Phone Screen", "Interview", "Offer", "Rejected"]
STATUS_COLORS = {
    "Applied":      "#1a56db",
    "Phone Screen": "#f59e0b",
    "Interview":    "#8b5cf6",
    "Offer":        "#10b981",
    "Rejected":     "#94a3b8",
}


# ── HTML template (raw string — no escaping needed for CSS/JS braces) ──────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Toronto Job Search Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f4f8; color: #1a202c; min-height: 100vh;
    }
    header {
      background: linear-gradient(135deg, #1a56db 0%, #1e3a8a 100%);
      color: white; padding: 28px 40px;
    }
    header h1 { font-size: 1.75rem; font-weight: 700; }
    header p  { margin-top: 6px; opacity: 0.85; font-size: 0.95rem; }

    .stats-row {
      display: flex; gap: 20px; padding: 28px 40px 0; flex-wrap: wrap;
    }
    .stat-card {
      background: white; border-radius: 12px; padding: 20px 28px;
      flex: 1; min-width: 160px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
      border-top: 4px solid #1a56db;
    }
    .stat-card .value { font-size: 2rem; font-weight: 700; color: #1a56db; }
    .stat-card .label { font-size: 0.8rem; color: #64748b; margin-top: 4px;
                        text-transform: uppercase; letter-spacing: .05em; }

    .grid {
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 24px; padding: 28px 40px 0;
    }
    .card {
      background: white; border-radius: 12px; padding: 24px;
      box-shadow: 0 1px 4px rgba(0,0,0,.08);
    }
    .card.full { grid-column: 1 / -1; }
    .card h2 {
      font-size: 1rem; font-weight: 600; color: #374151;
      margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9;
    }
    .chart-wrap { position: relative; }
    .chart-wrap.tall  { height: 300px; }
    .chart-wrap.short { height: 270px; }
    .chart-note {
      margin-top: 10px; font-size: 0.78rem; color: #94a3b8; font-style: italic;
    }

    /* Application Tracker */
    .tracker-wrap { padding: 0 40px 40px; }
    .tracker-card {
      background: white; border-radius: 12px; padding: 24px;
      box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-top: 24px;
    }
    .tracker-card h2 {
      font-size: 1rem; font-weight: 600; color: #374151;
      margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #f1f5f9;
    }
    .app-summary {
      display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
    }
    .app-stat {
      border-radius: 8px; padding: 12px 20px; text-align: center;
      flex: 1; min-width: 100px;
    }
    .app-stat .s-value { font-size: 1.6rem; font-weight: 700; }
    .app-stat .s-label { font-size: 0.75rem; margin-top: 2px; opacity: 0.85; }
    .app-stat.applied      { background: #eff6ff; color: #1a56db; }
    .app-stat.phone-screen { background: #fffbeb; color: #b45309; }
    .app-stat.interview    { background: #f5f3ff; color: #7c3aed; }
    .app-stat.offer        { background: #ecfdf5; color: #059669; }
    .app-stat.rejected     { background: #f8fafc; color: #64748b; }

    .app-table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    .app-table th {
      text-align: left; padding: 10px 12px; border-bottom: 2px solid #e5e7eb;
      color: #374151; font-weight: 600; background: #f9fafb;
    }
    .app-table td { padding: 10px 12px; border-bottom: 1px solid #f1f5f9; color: #374151; }
    .app-table tr:last-child td { border-bottom: none; }
    .app-table tr:hover td { background: #f9fafb; }
    .notes-cell { color: #94a3b8; font-style: italic; }
    .empty-msg  { text-align: center; color: #94a3b8; padding: 24px; }

    .badge {
      display: inline-block; padding: 3px 10px; border-radius: 99px;
      font-size: 0.75rem; font-weight: 600;
    }
    .badge-applied      { background: #dbeafe; color: #1a56db; }
    .badge-phone-screen { background: #fef3c7; color: #b45309; }
    .badge-interview    { background: #ede9fe; color: #7c3aed; }
    .badge-offer        { background: #d1fae5; color: #059669; }
    .badge-rejected     { background: #f1f5f9; color: #64748b; }

    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .card.full { grid-column: auto; }
      header, .stats-row, .grid, .tracker-wrap { padding-left: 20px; padding-right: 20px; }
    }
  </style>
</head>
<body>

<header>
  <h1>🍁 Toronto Job Search Dashboard</h1>
  <p>Junior &amp; entry-level positions · Healthcare IT · Informatics · Admin</p>
</header>

<div class="stats-row">
  <div class="stat-card">
    <div class="value">%%TOTAL_JOBS%%</div>
    <div class="label">Total Jobs Tracked</div>
  </div>
  <div class="stat-card">
    <div class="value">%%DAYS_MONITORED%%</div>
    <div class="label">Days Monitored</div>
  </div>
  <div class="stat-card">
    <div class="value">%%AVG_PER_DAY%%</div>
    <div class="label">Avg Jobs / Day</div>
  </div>
  <div class="stat-card">
    <div class="value">%%APPS_SUBMITTED%%</div>
    <div class="label">Applications Sent</div>
  </div>
</div>

<div class="grid">

  <div class="card full">
    <h2>📅 Daily New Jobs</h2>
    <div class="chart-wrap tall">
      <canvas id="chartDaily"></canvas>
    </div>
    <p class="chart-note">
      Weekday peaks reflect active job posting patterns;
      scraper has been running daily since May 8, 2026
    </p>
  </div>

  <div class="card">
    <h2>🔵 Source Distribution</h2>
    <div class="chart-wrap short">
      <canvas id="chartPie"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>📊 Job Category Breakdown</h2>
    <div class="chart-wrap short">
      <canvas id="chartBar"></canvas>
    </div>
  </div>

  <div class="card full">
    <h2>📈 Weekly Trend</h2>
    <div class="chart-wrap tall">
      <canvas id="chartWeekly"></canvas>
    </div>
  </div>

</div>

<div class="tracker-wrap">
  <div class="tracker-card">
    <h2>📋 Application Tracker</h2>
    <div class="app-summary">
      %%APP_SUMMARY_CARDS%%
    </div>
    <table class="app-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Job Title</th>
          <th>Applied</th>
          <th>Source</th>
          <th>Status</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        %%APP_ROWS%%
      </tbody>
    </table>
  </div>
</div>

<script>
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
Chart.defaults.font.size   = 12;
Chart.defaults.color       = "#64748b";

const dailyLabels  = %%DAILY_LABELS%%;
const dailyCounts  = %%DAILY_COUNTS%%;
const sourceLabels = %%SOURCE_LABELS%%;
const sourceCounts = %%SOURCE_COUNTS%%;
const catLabels    = %%CAT_LABELS%%;
const catCounts    = %%CAT_COUNTS%%;
const catColors    = %%CAT_COLORS%%;
const weekLabels   = %%WEEK_LABELS%%;
const weekCounts   = %%WEEK_COUNTS%%;

const BLUE = "#1a56db";

// Chart 1: Daily
new Chart(document.getElementById("chartDaily"), {
  type: "line",
  data: {
    labels: dailyLabels,
    datasets: [{
      label: "New Jobs",
      data: dailyCounts,
      borderColor: BLUE,
      backgroundColor: "rgba(26,86,219,.08)",
      borderWidth: 2.5,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: BLUE,
      fill: true,
      tension: 0.35,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      datalabels: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y} new jobs` } }
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxRotation: 45 } },
      y: { beginAtZero: true, grid: { color: "#f1f5f9" }, ticks: { stepSize: 10 } }
    }
  }
});

// Chart 2: Pie — percentages shown on slices + legend
const pieTotal = sourceCounts.reduce((a, b) => a + b, 0);
new Chart(document.getElementById("chartPie"), {
  type: "doughnut",
  plugins: [ChartDataLabels],
  data: {
    labels: sourceLabels,
    datasets: [{
      data: sourceCounts,
      backgroundColor: ["#1a56db", "#f59e0b", "#10b981"],
      borderWidth: 2,
      borderColor: "#fff",
      hoverOffset: 8,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "right",
        labels: {
          padding: 16,
          usePointStyle: true,
          generateLabels: chart => {
            const ds = chart.data.datasets[0];
            const total = ds.data.reduce((a, b) => a + b, 0);
            return chart.data.labels.map((label, i) => ({
              text: `${label}  ${((ds.data[i] / total) * 100).toFixed(1)}%`,
              fillStyle: ds.backgroundColor[i],
              strokeStyle: "#fff",
              lineWidth: 2,
              pointStyle: "circle",
              hidden: false,
              index: i,
            }));
          }
        }
      },
      datalabels: {
        color: "#fff",
        font: { weight: "bold", size: 14 },
        formatter: (value) => {
          const pct = ((value / pieTotal) * 100).toFixed(1);
          return pct + "%";
        },
        display: ctx => (ctx.dataset.data[ctx.dataIndex] / pieTotal) > 0.04,
      },
      tooltip: {
        callbacks: {
          label: ctx => {
            const pct = ((ctx.parsed / pieTotal) * 100).toFixed(1);
            return ` ${ctx.label}: ${ctx.parsed.toLocaleString()} (${pct}%)`;
          }
        }
      }
    }
  }
});

// Chart 3: Bar (horizontal)
new Chart(document.getElementById("chartBar"), {
  type: "bar",
  data: {
    labels: catLabels,
    datasets: [{
      label: "Jobs",
      data: catCounts,
      backgroundColor: catColors,
      borderRadius: 6,
      borderSkipped: false,
    }]
  },
  options: {
    indexAxis: "y",
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      datalabels: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.x} jobs` } }
    },
    scales: {
      x: { beginAtZero: true, grid: { color: "#f1f5f9" } },
      y: { grid: { display: false } }
    }
  }
});

// Chart 4: Weekly
new Chart(document.getElementById("chartWeekly"), {
  type: "line",
  data: {
    labels: weekLabels,
    datasets: [{
      label: "Jobs per Week",
      data: weekCounts,
      borderColor: "#f59e0b",
      backgroundColor: "rgba(245,158,11,.08)",
      borderWidth: 2.5,
      pointRadius: 6,
      pointHoverRadius: 8,
      pointBackgroundColor: "#f59e0b",
      fill: true,
      tension: 0.3,
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      datalabels: { display: false },
      tooltip: { callbacks: { label: ctx => ` ${ctx.parsed.y} jobs that week` } }
    },
    scales: {
      x: { grid: { display: false } },
      y: { beginAtZero: true, grid: { color: "#f1f5f9" }, ticks: { stepSize: 50 } }
    }
  }
});
</script>
</body>
</html>
"""


def make_html(data: dict) -> str:
    html = HTML_TEMPLATE
    for key, val in data.items():
        html = html.replace(f"%%{key}%%", val)
    return html


def main():
    # ── Read DB ──────────────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(
        "SELECT job_id, title, company, added_at FROM seen_jobs ORDER BY added_at", conn
    )
    conn.close()

    df["source"]       = df["job_id"].apply(detect_source)
    df["job_category"] = df["title"].apply(categorize)
    df["date"]         = pd.to_datetime(df["added_at"]).dt.date

    df.to_csv(OUT_CSV, index=False)
    print(f"Exported {len(df)} rows → {OUT_CSV}")

    # ── Chart data ───────────────────────────────────────────────────────────────
    daily = df.groupby("date").size()
    daily_labels = [d.strftime("%b %d") for d in daily.index]
    daily_counts = daily.tolist()

    source_vc    = df["source"].value_counts()
    source_labels = source_vc.index.tolist()
    source_counts = source_vc.tolist()

    # Merge health categories
    cat_vc = df["job_category"].value_counts()
    health_total = sum(int(cat_vc.get(k, 0)) for k in HEALTH_MERGE)
    cat_merged = cat_vc.drop([k for k in HEALTH_MERGE if k in cat_vc.index])
    cat_merged["Healthcare IT / Clinical"] = health_total
    cat_merged = cat_merged.sort_values(ascending=False)

    cat_labels = cat_merged.index.tolist()
    cat_counts = [int(v) for v in cat_merged.tolist()]
    cat_colors = [CAT_COLOR_MAP.get(c, "#93c5fd") for c in cat_labels]

    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W")
    weekly = df.groupby("week").size()
    week_labels = [
        f"{p.start_time.strftime('%b %d')}–{p.end_time.strftime('%b %d')}"
        for p in weekly.index
    ]
    week_counts = weekly.tolist()

    # ── Application log ──────────────────────────────────────────────────────────
    app_data = []
    if APP_LOG.exists():
        app_df = pd.read_csv(APP_LOG)
        app_data = app_df.fillna("").to_dict("records")

    status_counts = {s: 0 for s in STATUS_ORDER}
    for row in app_data:
        s = str(row.get("status", "Applied")).strip()
        if s in status_counts:
            status_counts[s] += 1

    summary_cards = ""
    for status in STATUS_ORDER:
        css_class = status.lower().replace(" ", "-")
        summary_cards += f"""<div class="app-stat {css_class}">
          <div class="s-value">{status_counts[status]}</div>
          <div class="s-label">{status}</div>
        </div>"""

    if app_data:
        app_rows = ""
        for row in app_data:
            s   = str(row.get("status", "Applied")).strip()
            css = s.lower().replace(" ", "-")
            app_rows += f"""<tr>
          <td>{row.get('company', '')}</td>
          <td>{row.get('job_title', '')}</td>
          <td>{row.get('applied_date', '')}</td>
          <td>{row.get('source', '')}</td>
          <td><span class="badge badge-{css}">{s}</span></td>
          <td class="notes-cell">{row.get('notes', '')}</td>
        </tr>"""
    else:
        app_rows = '<tr><td colspan="6" class="empty-msg">No applications logged yet — add entries to application_log.csv and re-run this script.</td></tr>'

    # ── Stats ────────────────────────────────────────────────────────────────────
    total_jobs     = len(df)
    days_monitored = len(daily)
    avg_per_day    = round(total_jobs / days_monitored, 1)
    apps_submitted = len(app_data)

    # ── Generate HTML ─────────────────────────────────────────────────────────────
    html = make_html({
        "TOTAL_JOBS":        str(f"{total_jobs:,}"),
        "DAYS_MONITORED":    str(days_monitored),
        "AVG_PER_DAY":       str(avg_per_day),
        "APPS_SUBMITTED":    str(apps_submitted),
        "DAILY_LABELS":      json.dumps(daily_labels),
        "DAILY_COUNTS":      json.dumps(daily_counts),
        "SOURCE_LABELS":     json.dumps(source_labels),
        "SOURCE_COUNTS":     json.dumps(source_counts),
        "CAT_LABELS":        json.dumps(cat_labels),
        "CAT_COUNTS":        json.dumps(cat_counts),
        "CAT_COLORS":        json.dumps(cat_colors),
        "WEEK_LABELS":       json.dumps(week_labels),
        "WEEK_COUNTS":       json.dumps(week_counts),
        "APP_SUMMARY_CARDS": summary_cards,
        "APP_ROWS":          app_rows,
    })

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Generated dashboard → {OUT_HTML}")

    print("\nSource breakdown:")
    print(source_vc.to_string())
    print("\nCategory breakdown (merged):")
    print(cat_merged.to_string())
    print(f"\nApplications: {apps_submitted} total")
    for s, c in status_counts.items():
        if c: print(f"  {s}: {c}")


if __name__ == "__main__":
    main()
