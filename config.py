# ============================================================
#  Job Application Agent — Configuration
#  Edit this file with YOUR details before running
# ============================================================

import os

# ── Personal Details ────────────────────────────────────────
PROFILE = {
    "full_name":     os.environ.get("BOT_FULL_NAME", "Your Name"),
    "email":         os.environ.get("BOT_EMAIL", "your.email@example.com"),
    "phone":         os.environ.get("BOT_PHONE", "+91 9999999999"),
    "location":      os.environ.get("BOT_LOCATION", "City, Country"),
    "linkedin_url":  os.environ.get("BOT_LINKEDIN_URL", "https://linkedin.com/in/yourprofile"),
    "github_url":    os.environ.get("BOT_GITHUB_URL", "https://github.com/yourusername"),
    "portfolio_url": os.environ.get("BOT_PORTFOLIO_URL", "https://yourwebsite.com"),

    # Path to your resume PDF
    "resume_path":   "resume.pdf",

    # Cover letter — use {company}, {role}, {platform} as placeholders
    "cover_letter": (
        "Dear Hiring Team at {company},\n\n"
        "I am a passionate Computer Science student, "
        "applying for the {role} position via {platform}. I have strong hands-on "
        "experience with React, Node.js, Python, and SQL, and I enjoy building "
        "scalable, user-friendly products.\n\n"
        "I would love the opportunity to contribute to your team and grow as a "
        "developer. Please find my resume attached.\n\n"
        "Thank you for your consideration."
    ),

    # Common answers for application forms
    "graduation_year":  "2026",
    "degree":           "B.Tech Computer Science",
    "college":          "Rajasthan Technical University",
    "cgpa":             "8.5",
    "notice_period":    "Immediately",
    "expected_stipend": "15000",
    "skills":           "React, Node.js, Python, SQL, Git, REST APIs",
    "languages":        "Hindi, English",
}

# ── Job Search Criteria ──────────────────────────────────────
SEARCH = {
    "keywords":     ["Software Engineer Intern", "Frontend Intern",
                     "Full Stack Intern", "React Developer Intern",
                     "Node.js Intern"],

    # Fallback keywords — tried automatically if primary keywords find 0 results
    "fallback_keywords": [
        "Web Development", "Python", "JavaScript",
        "Software Development", "Computer Science",
        "Mobile App Development", "Backend Development",
        "React", "Angular", "Data Entry",
        "IT", "Developer", "Programming",
    ],

    "location":     "Jaipur",
    "remote":       True,           # Also search remote jobs
    "max_per_run":  20,             # Max applications per day
    "delay_min":    4,              # Min seconds between actions
    "delay_max":    9,              # Max seconds (human-like pacing)
}

# ── Platform Toggles ────────────────────────────────────────
PLATFORMS = {
    "internshala": True,
    "linkedin":    True,
    "indeed":      True,
}

# ── Internshala Credentials ─────────────────────────────────
INTERNSHALA = {
    "email":    os.environ.get("INTERNSHALA_EMAIL", ""),
    "password": os.environ.get("INTERNSHALA_PASSWORD", ""),
}

# ── LinkedIn Credentials ─────────────────────────────────────
LINKEDIN = {
    "email":    os.environ.get("LINKEDIN_EMAIL", ""),
    "password": os.environ.get("LINKEDIN_PASSWORD", ""),
}

# ── Indeed Credentials ───────────────────────────────────────
INDEED = {
    "email":    os.environ.get("INDEED_EMAIL", ""),
    "password": os.environ.get("INDEED_PASSWORD", ""),
}

# ── Filters ──────────────────────────────────────────────────
FILTERS = {
    "exclude_keywords": ["paid", "fresher", "junior", "fresher",
                         "manager", "lead", "architect"],
    "min_stipend":      0,          # 0 = no minimum filter
    # "easy_apply_only":  True,       # Skip jobs without Easy Apply
    # "verified_only":    False,
}

# ── Output ────────────────────────────────────────────────────
LOG_FILE   = "applications.log"
CSV_FILE   = "applications.csv"
# Auto-detect: headless on server (PORT env set by Railway), visible locally
HEADLESS   = os.environ.get("HEADLESS", "true" if os.environ.get("PORT") else "false").lower() == "true"
