# 🍁 Toronto Job Scraper — 設定說明

針對你的背景量身設計：護理 + 社會學 + Computer Programming
目標職位：Junior Developer、Health Informatics、Clinical Analyst、Healthcare Data Analyst、Junior BA/SA

---

## 📦 Step 1：安裝 Python 套件

打開終端機（Terminal / Command Prompt），輸入：

```bash
pip install requests schedule
```

---

## ✏️ Step 2：填入你的 Gmail 設定

打開 `job_scraper.py`，找到最上面這段：

```python
EMAIL_FROM    = "your_gmail@gmail.com"     # ← 改成你的 Gmail
EMAIL_TO      = "your_gmail@gmail.com"     # ← 改成收信的信箱（可以相同）
EMAIL_APPPASS = "xxxx xxxx xxxx xxxx"      # ← 填入 Gmail App Password
```

### 如何取得 Gmail App Password：
1. 前往 https://myaccount.google.com/security
2. 啟用「兩步驟驗證」
3. 搜尋「應用程式密碼」→「建立」
4. 選擇「郵件」+ 你的裝置，複製那 16 個字元
5. 貼入 `EMAIL_APPPASS`

---

## ▶️ Step 3：先手動測試一次

```bash
cd job_scraper
python job_scraper.py
```

成功的話你會看到：
```
==================================================
  Job Scraper started — 2025-01-15 14:30
==================================================
🔍 Searching: junior developer Toronto
   Indeed: 8 results
   LinkedIn: 5 results
   Job Bank: 3 results
...
✅ Email sent: 42 new jobs
```

然後去收信匣確認有收到 email！

---

## ⏰ Step 4：設定每天自動執行

### 方法 A：Python scheduler（簡單，視窗要保持開著）

```bash
python scheduler.py
```

讓這個視窗繼續跑，每天早上 8:00 自動執行。

### 方法 B：macOS/Linux cron（推薦，背景執行）

```bash
crontab -e
```

加入這一行（每天 8:00 AM 執行）：
```
0 8 * * * /usr/bin/python3 /你的路徑/job_scraper/job_scraper.py
```

### 方法 C：Windows 工作排程器
1. 搜尋「工作排程器」→「建立基本工作」
2. 觸發程序：每天 08:00
3. 動作：啟動程式 → `python.exe`
4. 引數：`C:\你的路徑\job_scraper\job_scraper.py`

---

## 📧 Email 長什麼樣子

每天早上你會收到一封信，主旨像：
**🍁 42 New Toronto Jobs — Jan 15**

裡面依平台分組，每個職缺有：
- 職位名稱（點擊直接開啟）
- 公司名稱
- Apply 按鈕

只有「新職缺」才會出現，已經通知過的不會重複。

---

## 🔧 客製化搜尋關鍵字

打開 `job_scraper.py`，找到 `SEARCH_QUERIES` 列表，
可以新增或刪除你想搜尋的關鍵字：

```python
SEARCH_QUERIES = [
    "junior developer Toronto",
    "health informatics analyst Toronto",
    # 可以加你想要的：
    "clinical data analyst Toronto",
    "junior full stack developer Toronto",
]
```

---

## 🗃️ 資料庫

程式會自動建立 `seen_jobs.db`，記錄已通知過的職缺。
如果你想重置（重新收到所有職缺），刪除這個檔案即可。

---

## ❓ 常見問題

**Q: 收不到 email？**
→ 確認 App Password 是否正確（不是你的登入密碼）
→ 確認 Gmail 兩步驟驗證已開啟

**Q: 結果太少？**
→ 修改 `SEARCH_QUERIES` 加入更多關鍵字

**Q: 結果太多不相關？**
→ 修改 `EXCLUDE_TITLE_WORDS` 加入要排除的字，例如 "nurse", "RN"
