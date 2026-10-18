# Stylora — AI Virtual Wardrobe & Personal Stylist

> **"Your wardrobe, styled."**

Stylora lets users photograph and digitize their own clothes, organize them into a private digital closet, and chat with an AI stylist that creates personalized outfit combinations built **strictly from items they already own**.

---

## Technology Stack

- **Backend:** Python 3.14 · Django 5.2 LTS
- **Frontend:** Server-rendered Django templates, modern responsive CSS (WCAG 2.1 AA), Vanilla JavaScript
- **Database:** SQLite (local development) / PostgreSQL (production)
- **AI Engine:** Google Gemini Flash API via official `google-genai` Python SDK
- **Image Processing:** Pillow (EXIF sanitization, $400\times400\text{ px}$ thumbnailing)
- **Configuration:** 12-Factor environment variables via `django-environ`

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+ (Python 3.14 compatible)
- Git

### 2. Clone and Setup Environment
```bash
# Clone the repository
git clone <repo-url>
cd Stylora

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
```bash
# Copy example configuration to .env
cp .env.example .env

# Edit .env and supply your Gemini API key (optional for local setup testing)
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Run Verification & Automated Tests
```bash
# Verify system integrity
python manage.py check

# Run test suite
python manage.py test
```

### 6. Start Local Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/health/` to verify the application status.

---

## Project Structure

```
Stylora/
├── apps/
│   ├── accounts/       # User registration, login, profile & privacy
│   ├── wardrobe/       # Clothing inventory, categories, uploads & gallery
│   ├── stylist/        # Conversational AI stylist chat & grounding logic
│   └── outfits/        # Saved outfit lookbooks & outfit cards
├── services/
│   ├── ai_service.py   # Gemini Flash client & Pydantic schema validation
│   └── image_service.py # Pillow thumbnail generation & EXIF stripping
├── stylora/            # Project configuration (settings, master URLs, wsgi)
├── docs/               # Specifications & development guidelines
│   └── PROJECT_RULES.md # Code standards, security rules, and git hygiene
├── templates/          # HTML templates & partials
├── static/             # CSS tokens & JavaScript assets
└── media/              # User-uploaded clothing images (strictly protected)
```

---

## Preview & Staging Deployment (e.g. Render)

Stylora is production-ready for deployment on Linux PaaS platforms such as Render, Railway, or Heroku.

### 1. Build & Run Configuration
- **Build Command:** `./build.sh` (or `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`)
- **Start Command:** `gunicorn stylora.wsgi:application`
- **Health Check Path:** `/health/`

### 2. Required Production Environment Variables
| Variable | Description | Example / Recommended Value |
| :--- | :--- | :--- |
| `DEBUG` | Disables debug mode in staging/production | `False` |
| `SECRET_KEY` | Strong 50+ character cryptographic random key | Secure random token |
| `ALLOWED_HOSTS` | Comma-separated list of allowed host domains | `stylora-preview.onrender.com,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for HTTPS form submissions | `https://stylora-preview.onrender.com` |
| `DATABASE_URL` | PostgreSQL connection string | `postgres://user:password@hostname:5432/dbname` |
| `GEMINI_API_KEY` | Google Gemini API key for vision & stylist AI | API key from Google AI Studio |
| `SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS (default: True) | `True` |

---

## Documentation Links
- [PRD v1.0](Stylora%20%E2%80%94%20Product%20Requirements%20Document%20%28PRD%20v1.0%29.md)
- [Project Rules & Coding Standards](docs/PROJECT_RULES.md)

