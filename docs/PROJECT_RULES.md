# Stylora — Project Development Rules & Coding Standards

**Version:** 1.0  
**Status:** Active & Enforced  
**Date:** 2026-10-18  
**Applicability:** All contributors, subagents, and automated workflows on Stylora.

---

## 1. Django Architecture & Naming Conventions

### 1A. App Scope & Separation of Concerns
Stylora follows the single-responsibility modular monolith architecture:
- **`apps.accounts`**: User registration, session authentication, password management, profile data, account deletion.
- **`apps.wardrobe`**: Digital closet inventory, photo uploads, categories, filters, item CRUD.
- **`apps.stylist`**: Conversational chat sessions, prompt composition, AI communication, recommendation validation.
- **`apps.outfits`**: Saved outfit collections, lookbook rendering, outfit card persistence.
- **`services/`**: Pure Python utilities (`ai_service.py`, `image_service.py`). No database queries or request handling.

### 1B. Naming Standards
- **Apps:** Lowercase, plural nouns where sensible (`accounts`, `wardrobe`, `stylist`, `outfits`).
- **Models:** PascalCase, singular (`ClothingItem`, `Outfit`, `ChatSession`, `ChatMessage`).
- **Database Tables:** Auto-generated Django standard (`<app>_<model>`, e.g., `wardrobe_clothingitem`).
- **Model Fields:** `snake_case` (`primary_color`, `is_active`, `thumbnail_image`).
- **Foreign Keys:** Explicit naming (`user`, `category`, `clothing_item`). Always specify `related_name`.
- **Views:** Class-Based Views (CBVs) preferred for standard CRUD (`ClothingItemCreateView`, `WardrobeGalleryView`). PascalCase with `View` suffix.
- **URL Names:** Lowercase with hyphens or colons for namespacing (`wardrobe:gallery`, `wardrobe:item-add`, `stylist:chat`).
- **Templates:** Lowercase with underscores, grouped by app (`wardrobe/item_list.html`, `stylist/chat.html`).

---

## 2. Folder Organization

```
Stylora/
├── docs/                        # Specifications, PRD, rules, and architectural decisions
│   ├── PROJECT_RULES.md
│   └── ...
├── stylora/                     # Root Django project configuration
│   ├── __init__.py
│   ├── settings.py              # Configured strictly via django-environ
│   ├── urls.py                  # Master routing
│   ├── wsgi.py
│   └── asgi.py
├── apps/                        # Custom Django domain apps
│   ├── accounts/
│   ├── wardrobe/
│   ├── stylist/
│   └── outfits/
├── services/                    # Decoupled business logic & external integrations
│   ├── __init__.py
│   ├── ai_service.py            # Gemini client & schema enforcement
│   └── image_service.py         # Pillow image validation & thumbnailing
├── static/                      # Global static CSS, Vanilla JS, and SVG icons
│   ├── css/
│   │   ├── tokens.css           # Design tokens (colors, typography, elevation)
│   │   └── main.css             # Base styles & layout
│   └── js/
│       ├── chat.js              # Stylist chat stream & DOM handler
│       └── upload.js            # Image preview & validation handler
├── templates/                   # Base and reusable layout templates
│   ├── base.html
│   ├── components/
│   │   ├── navbar.html
│   │   ├── footer.html
│   │   └── outfit_card.html
│   └── errors/
│       ├── 400.html
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
├── media/                       # Protected uploaded media (strictly gitignored)
├── tests/                       # Global/integration test suites
├── .env.example                 # Committed template for required environment variables
├── .gitignore                   # Comprehensive exclusions
├── manage.py
└── requirements.txt             # Locked project dependencies
```

---

## 3. Python Formatting, Linting & Code Quality

1. **Style Standard:** Follow PEP 8 strictly. Maximum line length is **100 characters** (pragmatic for modern displays).
2. **Type Hints:** Use standard Python type annotations (`str`, `int`, `list[int]`, `Optional[str]`) on all service methods and utility functions.
3. **Docstrings:** All public functions, model methods, and view classes must have clear, concise docstrings explaining their purpose, parameters, and return types.
4. **Imports:** Grouped in PEP 8 order with single-blank-line separation:
   1. Standard library imports (e.g., `import os`, `from pathlib import Path`)
   2. Third-party library imports (e.g., `from django.db import models`, `from pydantic import BaseModel`)
   3. Local application imports (e.g., `from apps.wardrobe.models import ClothingItem`)

---

## 4. Environment Variables & Secrets Management

1. **Zero Committed Secrets:** Never hardcode or commit API keys, database credentials, passwords, or secret keys.
2. **12-Factor Configuration:** All dynamic configuration must be read via `django-environ`.
3. **`.env.example` Mandatory:** Maintain an up-to-date `.env.example` file with mock values. When adding a new variable, immediately document it in `.env.example`.
4. **Fail-Fast on Missing Secrets:** In production, critical variables (`SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`) must raise an immediate startup error if unset, rather than defaulting to insecure fallbacks.
5. **Git Exclusion:** Ensure `.env`, `.env.local`, and `.env.*` (except `.env.example`) are in `.gitignore`.

---

## 5. Git Branching & Commit Conventions

### 5A. Branch Strategy
- `main`: Production-ready, stable codebase. Direct pushes are forbidden.
- `develop`: Integration branch for active phase features.
- `feature/<name>`: Dedicated feature branches (e.g., `feature/wardrobe-models`, `feature/ai-service`).
- `fix/<name>`: Bug fixes and patches.

### 5B. Commit Messages (Conventional Commits)
All commit messages must follow the structured format:
`<type>(<scope>): <short imperative summary>`

Types:
- `feat`: A new user-facing feature.
- `fix`: A bug fix.
- `refactor`: Code changes that neither fix a bug nor add a feature.
- `docs`: Documentation updates.
- `test`: Adding or updating test cases.
- `chore`: Build scripts, dependencies, configuration.

*Example:* `feat(wardrobe): add Pillow thumbnail generation and EXIF stripping`

---

## 6. Database Migrations

1. **No Manual Schema Edits:** All database changes must be executed through Django migrations (`makemigrations`).
2. **Review Migrations Before Applying:** Inspect generated migration files before committing. Ensure operations match expectations.
3. **Descriptive Migration Names:** When generating custom data migrations, use meaningful names (e.g., `0002_seed_clothing_categories.py`).
4. **Atomic Operations:** Migrations must be reversible (`dependencies` and reverse operations verified).
5. **Production Verification:** Never drop columns or rename fields in production without a multi-phase migration strategy (add new $\rightarrow$ copy $\rightarrow$ deprecate $\rightarrow$ drop).

---

## 7. File Upload Validation & Image Processing

1. **Size Limit:** Uploads must be strictly validated $\le 10\text{ MB}$. Reject oversized files before buffering into memory.
2. **Format Whitelist:** Accept only `image/jpeg`, `image/png`, and `image/webp`. Validate both MIME type and binary magic numbers using Pillow.
3. **EXIF Sanitization:** All user-uploaded images must have EXIF metadata (GPS location, camera details, timestamps) stripped before saving.
4. **Automated Thumbnailing:** On save, Pillow must generate an optimized $400 \times 400\text{ px}$ thumbnail ($\le 100\text{ KB}$, WebP/JPEG) using `Image.Resampling.LANCZOS`.
5. **Protected Storage:** Media files must never be publicly browsable. Serve user clothing images exclusively through authenticated views checking user ownership.

---

## 8. Authentication, Authorization & User Ownership

1. **Enforce Ownership Universally (Rule 7):** Every query fetching, modifying, or deleting user-owned assets must include `user=request.user`.
2. **Anti-IDOR Requirement:** Never query by ID alone and subsequently check permissions. Always scope the database lookup directly:
   ```python
   # REQUIRED:
   item = get_object_or_404(ClothingItem, pk=pk, user=request.user)
   
   # FORBIDDEN:
   item = ClothingItem.objects.get(pk=pk) # Vulnerable!
   ```
3. **View Protection:** Every internal view must require authentication via `LoginRequiredMixin` or `@login_required`.
4. **Session Security:** Session cookies must have `HttpOnly=True`, `SameSite='Lax'`, and in production `Secure=True`.
5. **CSRF Validation:** CSRF middleware must remain enabled. All POST/DELETE AJAX requests must include the `X-CSRFToken` header.

---

## 9. AI Response Schemas & Untrusted Output Validation

1. **Rule 8 Compliance:** All AI output from Gemini or any external model is **strictly untrusted**.
2. **Schema Enforcement:** AI calls must specify `response_mime_type="application/json"` and enforce output structure using Pydantic models (`OutfitResponseSchema`).
3. **Mandatory ID Ownership Loop:** Before rendering or storing an outfit recommendation, every single returned `item_id` must be validated against the current user's database records:
   ```python
   valid_items = ClothingItem.objects.filter(
       id__in=recommended_ids, 
       user=request.user, 
       is_active=True
   )
   ```
   If an ID does not exist in `valid_items`, it must be immediately rejected and excluded. Never display or store an unverified clothing item.
4. **Retry & Fallback:** If the AI model returns malformed JSON or hallucinates all IDs, retry once with a lower temperature. If it fails again, return a polite, helpful error message. Never crash the view.

---

## 10. Logging & Exception Handling

1. **Structured Logging:** Use Python's built-in `logging` module configured in `settings.py`.
   - `stylora.ai`: AI request latencies, token counts, schema parsing failures, and ID validation drops.
   - `stylora.security`: Failed authentication attempts, unauthorized object access alerts.
2. **Never Log Sensitive Data:** Strictly forbid logging raw API keys, passwords, session tokens, or personally identifiable information.
3. **Specific Exception Handling:** Catch explicit exceptions (`PydanticValidationError`, `UnidentifiedImageError`, `APIError`). Never use bare `except:` clauses.

---

## 11. Testing Standards (Rule 9 & 10)

1. **Verification Rule:** Never claim a feature works unless it has been verified by an automated test or interactive test runner.
2. **Test Categories:**
   - **Unit Tests:** Model validation, Pillow thumbnail generation, Pydantic schema validation.
   - **Access Control Tests:** Attempting to view, edit, or delete another user's item must return `404 Not Found` (never `200` or leaky errors).
   - **AI Grounding Tests:** Unit test the ID verification loop using mock AI payloads containing valid, invalid, and foreign IDs.
   - **Integration Tests:** End-to-end flows for user registration, clothing upload, chat generation, and saving outfits.
3. **Test Execution:** Run all tests locally with `python manage.py test` before pushing to version control.

---

## 12. Dependency Management

1. **Minimal Footprint:** Never add a package unless it solves an explicit, approved PRD requirement.
2. **Locked Dependencies:** Pin version ranges in `requirements.txt`.
3. **Approved Core Stack:**
   - `Django>=5.2,<5.3` (LTS)
   - `Pillow>=10.0`
   - `django-environ>=0.11`
   - `google-genai>=1.0`
   - `pydantic>=2.0`
   - `gunicorn>=22.0` (Production)
   - `psycopg[binary]>=3.1` (Production)
4. **Excluded Tools (Without Prior Approval):** No React, DRF, Celery, Redis, Tailwind, or Bootstrap.
