"""
resume_parser.py — Reads your resume PDF and auto-fills config

How it works:
  1. Extracts all text from resume.pdf using pdfplumber
  2. Detects your domain (software, design, finance, etc.)
  3. Extracts skills, name, email, phone, education
  4. Generates smart job search keywords for your domain
  5. Returns a dict that overrides config.py at runtime

Usage:
  from resume_parser import parse_resume
  profile, search = parse_resume("resume.pdf")
"""

import re
import os
import sys

# ── Domain keyword maps ────────────────────────────────────────────────────────
# Each domain: list of signals (words found in resume) → job search keywords

DOMAIN_SIGNALS = {
    "software": {
        "signals": [
            "python", "javascript", "java", "c++", "react", "node", "django",
            "flask", "spring", "html", "css", "typescript", "golang", "rust",
            "software engineer", "developer", "backend", "frontend", "full stack",
            "devops", "cloud", "aws", "docker", "kubernetes", "git", "api",
            "database", "sql", "mongodb", "postgresql", "redis", "microservices",
        ],
        "keywords": [
            "Software Engineer Intern",
            "Full Stack Developer Intern",
            "Backend Developer Intern",
            "Frontend Developer Intern",
            "Software Development Intern",
        ],
        "roles": ["Software Engineer", "Developer", "SDE", "Programmer"],
    },
    "data_science": {
        "signals": [
            "machine learning", "deep learning", "tensorflow", "pytorch", "keras",
            "scikit", "pandas", "numpy", "matplotlib", "data science", "nlp",
            "computer vision", "neural network", "ai", "artificial intelligence",
            "data analyst", "tableau", "power bi", "statistics", "r language",
            "regression", "classification", "clustering", "lstm", "transformer",
        ],
        "keywords": [
            "Data Science Intern",
            "Machine Learning Intern",
            "AI Intern",
            "Data Analyst Intern",
            "ML Engineer Intern",
        ],
        "roles": ["Data Scientist", "ML Engineer", "AI Researcher", "Data Analyst"],
    },
    "design": {
        "signals": [
            "figma", "sketch", "adobe xd", "photoshop", "illustrator", "indesign",
            "ui", "ux", "user experience", "user interface", "wireframe", "prototype",
            "design thinking", "interaction design", "visual design", "branding",
            "typography", "color theory", "after effects", "motion design",
        ],
        "keywords": [
            "UI UX Design Intern",
            "Product Design Intern",
            "Graphic Design Intern",
            "Visual Design Intern",
            "Interaction Design Intern",
        ],
        "roles": ["UI/UX Designer", "Product Designer", "Graphic Designer"],
    },
    "finance": {
        "signals": [
            "finance", "accounting", "investment", "banking", "equity", "portfolio",
            "financial modeling", "valuation", "dcf", "excel", "bloomberg",
            "cfa", "ca", "chartered accountant", "audit", "tax", "balance sheet",
            "profit", "loss", "revenue", "budget", "forecasting", "derivatives",
            "mutual fund", "stock market", "trading", "risk management",
        ],
        "keywords": [
            "Finance Intern",
            "Investment Banking Intern",
            "Equity Research Intern",
            "Financial Analyst Intern",
            "Accounting Intern",
        ],
        "roles": ["Financial Analyst", "Investment Analyst", "Accountant"],
    },
    "marketing": {
        "signals": [
            "marketing", "seo", "sem", "google ads", "facebook ads", "social media",
            "content marketing", "email marketing", "brand", "campaign", "analytics",
            "hubspot", "mailchimp", "copywriting", "digital marketing", "influencer",
            "market research", "consumer behavior", "growth hacking", "crm",
        ],
        "keywords": [
            "Digital Marketing Intern",
            "Marketing Intern",
            "Social Media Intern",
            "Content Marketing Intern",
            "SEO Intern",
        ],
        "roles": ["Marketing Executive", "Digital Marketer", "Brand Manager"],
    },
    "hr": {
        "signals": [
            "human resources", "hr", "recruitment", "talent acquisition", "payroll",
            "employee relations", "training", "development", "onboarding",
            "performance management", "hris", "labor law", "compensation",
        ],
        "keywords": [
            "HR Intern",
            "Human Resources Intern",
            "Talent Acquisition Intern",
            "Recruitment Intern",
        ],
        "roles": ["HR Executive", "HR Generalist", "Recruiter"],
    },
    "mechanical": {
        "signals": [
            "mechanical", "autocad", "solidworks", "catia", "ansys", "matlab",
            "thermodynamics", "fluid mechanics", "manufacturing", "cad", "cam",
            "cnc", "3d printing", "robotics", "automation", "hydraulics",
        ],
        "keywords": [
            "Mechanical Engineering Intern",
            "Design Engineer Intern",
            "Manufacturing Intern",
            "CAD Engineer Intern",
        ],
        "roles": ["Mechanical Engineer", "Design Engineer", "Production Engineer"],
    },
    "civil": {
        "signals": [
            "civil", "structural", "construction", "autocad", "staad", "etabs",
            "concrete", "steel", "geotechnical", "surveying", "project management",
            "site engineer", "architecture", "revit", "primavera",
        ],
        "keywords": [
            "Civil Engineering Intern",
            "Site Engineer Intern",
            "Structural Engineer Intern",
            "Construction Intern",
        ],
        "roles": ["Civil Engineer", "Site Engineer", "Structural Engineer"],
    },
    "law": {
        "signals": [
            "law", "legal", "advocate", "llb", "llm", "contract", "litigation",
            "corporate law", "intellectual property", "patent", "trademark",
            "compliance", "regulatory", "legal research", "court", "barrister",
        ],
        "keywords": [
            "Legal Intern",
            "Law Intern",
            "Legal Research Intern",
            "Advocate Trainee",
            "Corporate Law Intern",
        ],
        "roles": ["Legal Associate", "Advocate", "Legal Counsel"],
    },
    "content": {
        "signals": [
            "content writer", "copywriter", "blog", "article", "journalism",
            "editing", "proofreading", "creative writing", "content creation",
            "wordpress", "seo writing", "technical writing", "screenplay",
        ],
        "keywords": [
            "Content Writing Intern",
            "Copywriting Intern",
            "Technical Writer Intern",
            "Content Creator Intern",
        ],
        "roles": ["Content Writer", "Copywriter", "Technical Writer"],
    },
}

# ── Skill extraction patterns ──────────────────────────────────────────────────
KNOWN_SKILLS = [
    # Programming languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Go",
    "Rust", "Ruby", "PHP", "Swift", "Kotlin", "R", "Scala", "MATLAB",
    # Web
    "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask",
    "FastAPI", "Spring Boot", "Laravel", "HTML", "CSS", "SASS", "jQuery",
    # Data
    "TensorFlow", "PyTorch", "Keras", "Scikit-learn", "Pandas", "NumPy",
    "Matplotlib", "Tableau", "Power BI", "Spark", "Hadoop",
    # Databases
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite", "Oracle", "SQL",
    # Cloud & DevOps
    "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Git", "GitHub",
    "Jenkins", "CI/CD", "Linux", "Bash",
    # Design
    "Figma", "Sketch", "Adobe XD", "Photoshop", "Illustrator",
    # Other tools
    "Excel", "AutoCAD", "SolidWorks", "MATLAB", "Tableau",
]


# ── Main parser ───────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from PDF. Tries pdfplumber first, falls back to pypdf."""
    text = ""

    # Method 1: pdfplumber (better layout handling)
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception as e:
        print(f"[ResumeParser] pdfplumber failed: {e}")

    # Method 2: pypdf fallback
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except ImportError:
        print("[ResumeParser] Neither pdfplumber nor pypdf installed.")
        print("  Run: pip install pdfplumber pypdf")
        return ""
    except Exception as e:
        print(f"[ResumeParser] pypdf failed: {e}")
        return ""


def extract_name(text: str) -> str:
    """Extract name — usually the first non-empty line of a resume."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in lines[:5]:
        # Name line: 2-4 words, no numbers, no special chars except spaces
        words = line.split()
        if (2 <= len(words) <= 4
                and all(w.replace(".", "").isalpha() for w in words)
                and len(line) < 50):
            return line.title()
    return ""


def extract_email(text: str) -> str:
    """Extract email address."""
    match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    """Extract Indian phone number."""
    patterns = [
        r"\+91[\s-]?\d{10}",
        r"\+91[\s-]?\d{5}[\s-]?\d{5}",
        r"(?<!\d)\d{10}(?!\d)",
        r"\d{5}[\s-]\d{5}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            phone = re.sub(r"[\s-]", "", match.group(0))
            if not phone.startswith("+91"):
                phone = "+91 " + phone
            return phone
    return ""


def extract_linkedin(text: str) -> str:
    """Extract LinkedIn URL."""
    match = re.search(r"linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
    return "https://" + match.group(0) if match else ""


def extract_github(text: str) -> str:
    """Extract GitHub URL."""
    match = re.search(r"github\.com/[\w-]+", text, re.IGNORECASE)
    return "https://" + match.group(0) if match else ""


def extract_skills(text: str) -> list:
    """Extract known skills mentioned in the resume."""
    text_lower = text.lower()
    found = []
    for skill in KNOWN_SKILLS:
        if skill.lower() in text_lower:
            found.append(skill)
    return found


def extract_education(text: str) -> dict:
    """Extract degree, college, graduation year, CGPA."""
    result = {"degree": "", "college": "", "graduation_year": "", "cgpa": ""}

    # CGPA / GPA
    cgpa_match = re.search(
        r"(?:cgpa|gpa|grade)[:\s]*([0-9]\.[0-9]{1,2})", text, re.IGNORECASE
    )
    if cgpa_match:
        result["cgpa"] = cgpa_match.group(1)

    # Graduation year (4-digit year between 2018-2030)
    years = re.findall(r"\b(20(?:1[89]|2[0-9]|30))\b", text)
    if years:
        result["graduation_year"] = max(years)  # latest year = grad year

    # Degree
    degree_patterns = [
        r"b\.?\s*tech[^\n,]*",
        r"b\.?\s*e\.?[^\n,]*engineering[^\n,]*",
        r"bachelor[^\n,]*",
        r"b\.?\s*sc[^\n,]*",
        r"b\.?\s*com[^\n,]*",
        r"b\.?\s*a\.?[^\n,]*",
        r"m\.?\s*tech[^\n,]*",
        r"mba[^\n,]*",
        r"m\.?\s*sc[^\n,]*",
        r"llb[^\n,]*",
    ]
    for pattern in degree_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result["degree"] = match.group(0).strip()[:60]
            break

    # College — look for "University", "Institute", "College" nearby
    college_match = re.search(
        r"([A-Z][^\n]*(?:University|Institute|College|IIT|NIT|BITS)[^\n]*)",
        text
    )
    if college_match:
        result["college"] = college_match.group(1).strip()[:80]

    return result


def detect_domain(text: str) -> str:
    """Score each domain by how many signal words appear in the resume."""
    text_lower = text.lower()
    scores = {}

    for domain, data in DOMAIN_SIGNALS.items():
        score = sum(1 for signal in data["signals"] if signal in text_lower)
        scores[domain] = score

    best_domain = max(scores, key=scores.get)
    best_score  = scores[best_domain]

    # Need at least 3 signals to be confident
    if best_score < 3:
        return "software"  # safe default

    return best_domain


def generate_cover_letter(name: str, domain: str, skills: list) -> str:
    """Generate a domain-appropriate cover letter template."""
    skill_str = ", ".join(skills[:5]) if skills else "relevant technical skills"

    templates = {
        "software": (
            "Dear Hiring Team at {company},\n\n"
            f"I am {name}, a motivated software engineering student applying for the "
            "{{role}} position via {platform}. I have hands-on experience with "
            f"{skill_str} and enjoy building scalable, impactful products.\n\n"
            "I would love the opportunity to contribute to your team and grow as a developer. "
            "Please find my resume attached.\n\n"
            f"Thank you,\n{name}"
        ),
        "data_science": (
            "Dear Hiring Team at {company},\n\n"
            f"I am {name}, a data science enthusiast applying for the {{role}} position via "
            "{platform}. I have experience with "
            f"{skill_str} and a strong interest in extracting insights from data.\n\n"
            "I am excited about the possibility of contributing to your data-driven initiatives. "
            "Please find my resume attached.\n\n"
            f"Thank you,\n{name}"
        ),
        "design": (
            "Dear Hiring Team at {company},\n\n"
            f"I am {name}, a UI/UX design student applying for the {{role}} position via "
            "{platform}. I have proficiency in "
            f"{skill_str} and a passion for creating intuitive user experiences.\n\n"
            "I would love to bring my design sensibility to your team. "
            "Please find my portfolio and resume attached.\n\n"
            f"Thank you,\n{name}"
        ),
        "finance": (
            "Dear Hiring Team at {company},\n\n"
            f"I am {name}, a finance student applying for the {{role}} position via {platform}. "
            f"I have knowledge of {skill_str} and a keen interest in financial markets and analysis.\n\n"
            "I am eager to contribute to your team and gain practical industry experience. "
            "Please find my resume attached.\n\n"
            f"Thank you,\n{name}"
        ),
    }

    template = templates.get(domain, templates["software"])
    # Replace {role} placeholder with actual placeholder syntax for the agent
    return template.replace("{role}", "{role}").replace("{{role}}", "{role}")


def parse_resume(pdf_path: str) -> tuple:
    """
    Main function. Reads resume PDF and returns (profile_overrides, search_overrides).

    Returns two dicts that can be merged into config.py's PROFILE and SEARCH.
    Any field that couldn't be extracted is returned as empty string (falsy)
    so the caller can fall back to config.py values.
    """
    print(f"\n[ResumeParser] Reading resume: {pdf_path}")

    if not os.path.exists(pdf_path):
        print(f"[ResumeParser] File not found: {pdf_path}")
        return {}, {}

    # Extract raw text
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        print("[ResumeParser] Could not extract text from PDF.")
        print("  If it's a scanned resume, convert to text-based PDF first.")
        return {}, {}

    print(f"[ResumeParser] Extracted {len(text)} characters of text")

    # Parse fields
    name     = extract_name(text)
    email    = extract_email(text)
    phone    = extract_phone(text)
    linkedin = extract_linkedin(text)
    github   = extract_github(text)
    skills   = extract_skills(text)
    edu      = extract_education(text)
    domain   = detect_domain(text)

    print(f"[ResumeParser] Detected domain : {domain}")
    print(f"[ResumeParser] Name found      : {name or '(not found)'}")
    print(f"[ResumeParser] Email found     : {email or '(not found)'}")
    print(f"[ResumeParser] Skills found    : {', '.join(skills[:8]) or '(none)'}")
    print(f"[ResumeParser] Degree          : {edu['degree'] or '(not found)'}")

    # Build profile overrides (only non-empty values override config)
    profile_overrides = {}
    if name:             profile_overrides["full_name"]        = name
    if email:            profile_overrides["email"]            = email
    if phone:            profile_overrides["phone"]            = phone
    if linkedin:         profile_overrides["linkedin_url"]     = linkedin
    if github:           profile_overrides["github_url"]       = github
    if skills:           profile_overrides["skills"]           = ", ".join(skills)
    if edu["degree"]:    profile_overrides["degree"]           = edu["degree"]
    if edu["college"]:   profile_overrides["college"]          = edu["college"]
    if edu["cgpa"]:      profile_overrides["cgpa"]             = edu["cgpa"]
    if edu["graduation_year"]:
                         profile_overrides["graduation_year"]  = edu["graduation_year"]

    # Generate cover letter from detected domain + skills
    cover = generate_cover_letter(
        name or "Applicant", domain, skills
    )
    profile_overrides["cover_letter"] = cover

    # Build search overrides
    domain_data = DOMAIN_SIGNALS.get(domain, DOMAIN_SIGNALS["software"])
    search_overrides = {
        "keywords": domain_data["keywords"],
        "_detected_domain": domain,
        "_detected_roles":  domain_data["roles"],
    }

    print(f"[ResumeParser] Search keywords : {domain_data['keywords']}")
    print(f"[ResumeParser] Done.\n")

    return profile_overrides, search_overrides


def print_summary(profile: dict, search: dict):
    """Print a readable summary of what was detected."""
    print("\n" + "=" * 50)
    print("  Resume Parser — Detected Profile")
    print("=" * 50)
    fields = [
        ("Name",             profile.get("full_name", "")),
        ("Email",            profile.get("email", "")),
        ("Phone",            profile.get("phone", "")),
        ("Domain",           search.get("_detected_domain", "")),
        ("Degree",           profile.get("degree", "")),
        ("College",          profile.get("college", "")),
        ("CGPA",             profile.get("cgpa", "")),
        ("Grad year",        profile.get("graduation_year", "")),
        ("Skills",           profile.get("skills", "")[:60]),
        ("LinkedIn",         profile.get("linkedin_url", "")),
        ("GitHub",           profile.get("github_url", "")),
    ]
    for label, value in fields:
        if value:
            print(f"  {label:15s} {value}")
    print("\n  Search keywords:")
    for kw in search.get("keywords", []):
        print(f"    • {kw}")
    print("=" * 50 + "\n")


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "resume.pdf"
    profile, search = parse_resume(pdf)
    if profile or search:
        print_summary(profile, search)
    else:
        print("Could not parse resume. Check the file path and format.")
