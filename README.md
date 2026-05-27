# Job Application Agent 🤖

Auto-applies to internships and jobs on **Internshala**, **LinkedIn**, and **Indeed**
using Python + Playwright. Fills forms, uploads resume, writes cover letters — all
without manual effort.

---

## File Structure

```
job_agent/
├── main.py           ← Entry point (run this)
├── config.py         ← YOUR details, credentials, search settings
├── internshala.py    ← Internshala automation
├── linkedin.py       ← LinkedIn Easy Apply automation
├── indeed.py         ← Indeed automation
├── utils.py          ← Logger, CSV tracker, helpers
├── requirements.txt
├── resume.pdf        ← PUT YOUR RESUME HERE
└── applications.csv  ← Auto-created, tracks all applications
```

---

## Setup (5 minutes)

### 1. Install Python 3.10+
Download from https://python.org if not installed.

### 2. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Add your resume
Place your resume PDF in the folder and name it `resume.pdf`
(or update `resume_path` in config.py).

### 4. Edit config.py
Open `config.py` and fill in:
- Your name, email, phone, location
- Internshala / LinkedIn / Indeed passwords
- Job search keywords and preferences
- Cover letter template

### 5. Run the agent
```bash
# Apply on all platforms
python main.py

# Apply only on LinkedIn
python main.py --platform linkedin

# Apply only on Internshala
python main.py --platform internshala

# Apply only on Indeed
python main.py --platform indeed

# View application stats
python main.py --report
```

---

## Scheduling (run every morning automatically)

### Windows — Task Scheduler
1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily at 9:00 AM
3. Action: Start a program
   - Program: `python`
   - Arguments: `C:\path\to\job_agent\main.py`
   - Start in: `C:\path\to\job_agent\`

### Mac / Linux — Cron
```bash
crontab -e
# Add this line (runs at 9 AM every day):
0 9 * * * cd /path/to/job_agent && python main.py >> cron.log 2>&1
```

---

## How It Works

1. Opens Chromium browser (visible by default, set HEADLESS=True to hide)
2. Logs into each platform with your credentials
3. Searches for jobs matching your keywords
4. For each job:
   - Checks if already applied (skips duplicates)
   - Checks for excluded keywords (e.g. "unpaid", "senior")
   - Clicks Apply / Easy Apply
   - Fills every form field with your profile data
   - Uploads your resume
   - Submits the application
5. Logs every action to `applications.csv` and `applications.log`
6. Stops after reaching the daily limit (default: 20)

---

## Tips

- **Start with HEADLESS = False** so you can watch it run and spot issues
- If LinkedIn asks for a CAPTCHA/verification, the agent will pause and let you solve it manually
- Set `easy_apply_only: True` to avoid getting stuck on complex external forms
- Check `applications.csv` daily to follow up on promising applications
- Run `python main.py --report` to see your stats

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Login fails | Double-check credentials in config.py |
| Resume not uploaded | Make sure resume.pdf is in the same folder |
| Bot detected / blocked | Set HEADLESS=False, increase delay_min/delay_max |
| LinkedIn security check | Solve it manually when prompted |
| No jobs found | Try broader keywords in config.py |

---

## Important Notes

- This tool is for personal use only
- Use responsibly — applying to too many jobs too fast may get your account flagged
- LinkedIn's Terms of Service discourage automation; use at your own discretion
- Always review your applications.csv to track where you've applied
