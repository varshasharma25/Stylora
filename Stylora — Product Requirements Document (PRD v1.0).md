# Stylora — Product Requirements Document

**Tagline:** Your wardrobe, styled.
**Version:** PRD v1.0 (MVP — final draft for development)
**Product type:** Responsive web application
**Primary stack:** Django · SQLite/PostgreSQL · Gemini API (or equivalent)

---

## 1. Product Overview

Stylora is a responsive web application that digitizes a user's personal wardrobe and provides AI-assisted outfit recommendations through a conversational stylist. Users upload photos of their own clothes and accessories, then describe an occasion, mood or style in natural language and receive coordinated outfits built **only from items they already own**.

**Key principle:** Recommend what the user owns, not random clothes from an online store.

### Example interaction

> "I have a college event tomorrow. Suggest a cute, comfortable outfit with my pink sneakers. I want something casual but well-coordinated."

The app examines the user's wardrobe, selects matching items, shows the outfit visually and explains how to wear the pieces together.

---

## 2. Vision and Objective

**Vision:** Help people decide what to wear by making their existing wardrobe searchable, understandable and easier to style.

**Mission:** Deliver a practical tool where a user can photograph their real clothes, organize them digitally, ask for outfit ideas in plain language, and receive recommendations built only from items they already own — then refine and save those looks through conversation.

**Objective:** Deliver a functional application where a user can upload real clothing photos, organize them, request outfits in natural language, receive recommendations linked to actual wardrobe items, and save preferred combinations.

---

## 3. Problem Statement

People — especially college students and young adults — own enough clothes but still struggle to decide what to wear. The app addresses four compounding problems:

1. **Decision fatigue:** time spent choosing outfits for different occasions.
2. **Poor wardrobe visibility:** users forget items and accessories they already own.
3. **Styling uncertainty:** users are unsure which tops, bottoms, shoes and accessories work together.
4. **Repetitive outfits:** users repeat the same combinations because they do not discover new ways to style existing clothes.

---

## 4. Proposed Solution

A single application combining three core experiences:

- **A. Digital wardrobe:** upload, categorize, organize, search and manage real clothing items with photos, colors, categories and other attributes.
- **B. AI outfit recommendations:** generate coordinated combinations from the user's available clothes based on occasion, theme, comfort and style.
- **C. Conversational personal stylist:** refine recommendations through chat, request alternatives, replace an item and save favorite looks.

### Value Proposition

> **Stylora turns the clothes you already own into outfits you haven't thought of yet.**

Every suggestion is something you can actually wear today — zero shopping links, zero aspirational outfits. Each recommendation comes with a human-readable styling explanation, not just a grid of images.

---

## 5. Target Users

**Primary audience:** the college student or young adult who wants to dress well, save time, experiment with outfits and make better use of clothes they already own.

### User Personas

#### Primary — Priya (21, undergraduate)

- Uses Stylora on her phone (Android) the night before events; also accesses it on her laptop.
- Wardrobe: ~60–80 items, mix of ethnic and Western wear.
- Uploads items gradually (5–10 per session over weeks).
- Values styling explanations and conversational refinement.
- Previously tried a competitor app, hit a paywall after uploading 30 items, and felt trapped.
- Wants help coordinating colors, patterns and accessories she doesn't know how to combine.

#### Secondary — Arjun (24, early-career professional)

- Uses Stylora on his work laptop during downtime.
- Wardrobe: ~40–50 items, mostly Western basics (shirts, chinos, blazers, sneakers).
- Uploads his entire wardrobe in one focused session.
- Saves 3–4 go-to outfits and only returns for new occasions.
- Values speed and directness; prefers utility over social or aesthetic features.

*These personas are fictional archetypes, not real research participants. Assumptions derived from them are flagged for validation in §18.*

### User needs

- Outfit ideas for college, parties, trips, festivals and other occasions.
- Limited time to decide what to wear.
- Help coordinating shoes, jewelry, bags and clothing.
- Practical suggestions using existing clothes.
- A simple interface rather than a complicated fashion tool.
- No paywall on core wardrobe and styling features.
- Works on both phone browsers and laptops without installing a native app.

### User journey

1. The user creates an account and opens their wardrobe.
2. They upload photos of tops, bottoms, shoes and accessories.
3. The app suggests likely categories and colors for confirmation.
4. The user opens the AI stylist and describes an occasion.
5. The stylist retrieves wardrobe items and suggests suitable combinations with styling explanations.
6. The user views the items, reads the styling advice, swaps pieces if desired, and saves the look.

**Design goal:** First useful outfit in under 10 minutes with ≤ 5 uploaded items.

---

## 6. User Stories

### Must Have (MVP — blocks core value)

| ID | User story | PRD req |
| --- | --- | --- |
| US-01 | As a user, I want to create an account and log in so that my wardrobe is private and persistent. | FR-01 |
| US-02 | As a user, I want to upload a clothing photo and set its category, color, pattern, season and name so I can build my digital wardrobe. | FR-02 |
| US-03 | As a user, I want to view my wardrobe as a filterable gallery so I can find items quickly. | FR-02 |
| US-04 | As a user, I want to edit or delete a clothing item so my wardrobe stays accurate. | FR-02 |
| US-05 | As a user, I want to describe an occasion and receive an outfit made from my own clothes, with a styling explanation, so I can decide what to wear. | FR-04 |
| US-06 | As a user, I want to send follow-up messages to refine the outfit ("keep the shoes, change the top") so I can get exactly what I want without starting over. | FR-05 |
| US-07 | As a user, I want to save an outfit with a name so I can find and reuse it later. | FR-06 |

### Should Have (strengthens UX)

| ID | User story | PRD req |
| --- | --- | --- |
| US-08 | As a user, I want the app to suggest a likely category and color when I upload a photo so tagging is faster. | FR-03 |
| US-09 | As a user, I want to see a helpful message when my wardrobe is too small for a full outfit so I know what to do next. | NFR-Reliability |
| US-10 | As a user, I want a clear explanation of how my photos are used so I feel safe uploading personal images. | NFR-Privacy |
| US-11 | As a user, I want the app to work well on my phone browser so I can use it without installing anything. | NFR-Usability |

### Could Have (nice-to-have for MVP)

| ID | User story | PRD req |
| --- | --- | --- |
| US-12 | As a user, I want to view my past styling conversations so I can revisit previous suggestions. | FR-05 |
| US-13 | As a user, I want to specify items to include or exclude ("use my pink sneakers", "not the black jacket") in my request. | FR-04 |
| US-14 | As a user, I want to delete my account and all associated data so I maintain control over my information. | NFR-Privacy |

---

## 7. Success Criteria

### Functional checkpoints

- A user can add, view, edit and delete clothing items.
- AI-generated recommendations reference valid items in that user's wardrobe.
- Each recommendation contains a styling explanation.
- A user can refine an outfit through follow-up chat messages.
- Saved outfits can be reopened later.
- Core workflows work on desktop and mobile browsers.

### Measurable test targets

| Metric | Target | When to measure |
| --- | --- | --- |
| First-session upload count | Median ≥ 5 items | User testing |
| Time to first saved outfit (new user) | ≤ 10 minutes | User testing |
| AI recommendation validity rate | 100% of returned IDs belong to the current user | Automated test |
| AI suggestion correction rate | < 40% of AI-suggested metadata changed by user | Post-FR-03 testing |
| Chat follow-up usage | ≥ 20% of sessions include ≥ 2 messages | Analytics |
| 7-day return rate | To be baselined | Post-launch |

---

## 8. Functional Requirements

| ID | Requirement | Details | Priority |
| --- | --- | --- | --- |
| FR-01 | User accounts | Register, log in and log out securely. Each user's wardrobe and saved outfits remain private. | Must have |
| FR-02 | Clothing management | Upload photos; select or correct category; add name, color, pattern, season and optional notes; edit or delete items; filter the wardrobe. | Must have |
| FR-03 | Image understanding | An image-capable AI model suggests category, visible colors and patterns. The user confirms or corrects before saving. | Should have (manual entry comes first) |
| FR-04 | Outfit generation | Accept occasion, theme, style, comfort preferences, required items and exclusions. Return combinations using wardrobe item IDs with a styling explanation. | Must have |
| FR-05 | AI stylist chat | Support follow-ups such as "Make it more formal", "Keep the same shoes" and "Replace the bag". Preserve context of the current styling conversation. | Must have |
| FR-06 | Saved outfits | Save a look with name, item references, styling explanation and creation date. View and delete saved looks. | Must have |

---

## 9. Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Security | Protect user data, enforce ownership checks on every wardrobe and outfit operation, keep API keys server-side and validate uploaded files (size, format, content). |
| Performance | Load wardrobe pages efficiently. Resize large photos into web-friendly thumbnails (≤ 100 KB). Lazy-load gallery images below the fold. |
| Usability | Clear navigation, useful empty states, readable text and responsive layouts. Touch targets ≥ 44×44 px on mobile. Single-column layout on narrow screens. |
| Reliability | Handle API errors, invalid images, missing wardrobe items and network failures gracefully. Show user-friendly messages; never crash. |
| Privacy | Let users delete their clothing photos and associated records. Explain how uploaded images are processed. Serve media through auth-checked views, not public URLs. |
| Maintainability | Modular Django apps, environment variables, documented setup, `requirements.txt` and version control. |
| Accessibility | Image alt text (auto-generated: "{Name} — {Color} {Category}"), keyboard-navigable controls, visible focus indicators, form labels, sufficient contrast (WCAG 1.4.3 minimum 4.5:1), and semantic HTML for outfit cards. |

These are initial quality goals; measurable performance targets will be refined during testing.

---

## 10. Scope

### Included in the MVP

- User authentication.
- Clothing photo uploads and wardrobe CRUD operations.
- Clothing categories, color tags and basic filters.
- AI-assisted clothing metadata (should-have; manual entry always available).
- Natural-language outfit requests.
- Recommendations based on actual wardrobe inventory.
- Outfit cards with styling explanations.
- Chat-based refinements and saved outfits.
- Responsive web design for desktop and mobile browsers.
- Graceful empty states and error handling.
- Privacy explanation at upload time.

### Deferred to later versions

- AI-generated images of a person wearing the outfit.
- Realistic virtual try-on.
- Automatic weather integration.
- Outfit calendars and wear-frequency analytics.
- Social sharing and public profiles.
- E-commerce integrations and shopping suggestions.
- AI background removal (clean photo guidance + manual approach first).
- Purchase import via email or retailer integrations.
- Cost-per-wear analytics.
- Community or marketplace features.

**Why defer virtual try-on?** Generating an image of a person wearing a combination of garments is a different and much harder problem than selecting items from a wardrobe. The core recommendation system must be reliable first.

**Why defer social and marketplace features?** Competitive research shows that social feeds create clutter complaints, and shopping integrations contradict the "use what you own" positioning. These are post-MVP considerations.

---

## 11. Acceptance Criteria

### Clothing upload

- The user can upload a supported image format.
- Invalid files and oversized uploads are rejected with a clear message.
- The saved item appears in the correct user's wardrobe.
- The user can edit or delete it.
- The image is not publicly accessible without authorization.

### Outfit recommendation

- The user can describe an occasion and specify preferences.
- Each recommended item has a valid database ID belonging to the current user.
- The recommendation contains a styling explanation.
- The user receives a useful message if there are not enough suitable items.
- The user can replace a selected item and request another option.

### Chat

- Follow-up messages retain relevant conversation context.
- Requests such as "keep the shoes" preserve the selected shoes.
- The system never accepts a fabricated clothing ID from the model as a valid item.
- API failures do not crash the application.

### Saved outfits

- A saved outfit stores the name, item references, styling explanation and creation date.
- Saved outfits can be viewed and deleted.
- Deleted wardrobe items are handled gracefully in saved outfits (e.g., marked as removed).

---

## 12. Research and Differentiation

Competitive analysis was conducted against existing apps (Whering, Acloset, Stylebook, Indyx, minniie and other AI styling products), examining features, free-vs-paid tiers, recommendation approaches and common user frustrations.

### Key research findings

| Finding | Source | Status |
| --- | --- | --- |
| Every major competitor is a native mobile app; none offer a web-based experience. | App Store listings, product websites | Verified |
| Acloset caps free tier at ~100 items; users report feeling "held hostage" after investing time uploading. | Reddit, App Store reviews | Verified |
| Onboarding friction (the "cataloging mountain") is the #1 drop-off point across all wardrobe apps. | UX research, Reddit, App Store reviews | Verified |
| No competitor clearly provides multi-turn conversational refinement with per-outfit styling explanations. | Feature documentation review | Hypothesis (needs hands-on testing) |
| Users complain about AI fixating on the same items and ignoring large wardrobe sections. | Reddit (Acloset feedback) | Verified |
| Shopping and social features in wardrobe apps frustrate users seeking anti-consumerist tools. | Reddit (Whering feedback) | Verified |

### Differentiation hypothesis (to be validated)

A free, web-based, conversational stylist that:
1. Works exclusively with the user's own wardrobe (no shopping links).
2. Explains its recommendations in plain language.
3. Lets the user refine outfits naturally through multi-turn chat.
4. Imposes no item caps or paywalls on core features.

We must test whether users value this combination enough to return regularly.

---

## 13. Technology Stack

| Layer | Choice |
| --- | --- |
| Backend | Python + Django (auth, routing, ORM models, forms, admin, business logic) |
| Frontend | HTML, CSS, JavaScript + Django templates |
| Database | SQLite locally; PostgreSQL for deployment |
| AI | Gemini API or suitable alternative (model, pricing and availability to be verified before final choice) |
| Image storage | Django media in development; persistent private object storage in production |

Django's built-in authentication and ORM are used. A separate React frontend or Django REST API is not needed for the initial version.

---

## 14. Architecture

**Flow:** Browser UI (Django templates, CSS, JS) → Django application → Database (users, items, outfits, chats) + Media storage (photos, thumbnails) + AI service (image analysis and styling).

**Django apps:**

- `accounts` — authentication and user settings.
- `wardrobe` — clothing uploads, categories and inventory.
- `stylist` — chat, prompts and outfit-generation logic.
- `outfits` — generated and saved outfit combinations.

AI calls live in a dedicated **service layer**, separate from models and views, so the provider can be swapped later.

### Grounding approach

Send the model a compact list of the user's items (ID, category, color, pattern, season, name) and require structured JSON output. Validate the response server-side: every returned ID must exist and belong to the current user, otherwise it is rejected or retried.

### Image handling

- Uploaded images are validated for file type, size and basic content.
- Large images are resized into web-friendly thumbnails on save.
- Images are served through Django views with ownership checks (not publicly accessible URLs).
- Production will use persistent private object storage.

---

## 15. Design Direction

- Clean, premium wardrobe interface.
- White and soft-blue backgrounds with subtle pastel accents.
- Visual clothing gallery with filters for tops, bottoms, shoes and accessories.
- Dedicated stylist chat page with outfit cards.
- Clear primary actions: **Add clothes**, **Style an outfit**, **Save look**.
- Responsive layouts for laptop and mobile.

**Accessibility note:** Every pastel color choice must be tested against WCAG 1.4.3 (minimum 4.5:1 contrast ratio). Pastel-on-white is a common contrast failure.

Wireframes to create before frontend work: dashboard, wardrobe gallery, upload form, stylist chat and saved outfits.

---

## 16. Project Rules

1. Follow Django conventions; each app owns one clear feature.
2. Keep API keys in environment variables; never commit secrets.
3. Validate uploads by file size, format and image content.
4. Enforce ownership checks on every wardrobe and outfit operation.
5. Treat AI responses as untrusted input; validate structure and referenced item IDs.
6. Use migrations for schema changes.
7. Document dependencies in `requirements.txt`.
8. Commit to Git with clear, descriptive messages.
9. Test important business logic and access controls.
10. Never treat a feature as complete just because its page looks correct.

---

## 17. Milestones

| Milestone | Deliverable |
| --- | --- |
| M1 | Project setup, Git repository and Django skeleton |
| M2 | Authentication and responsive base layout |
| M3 | Clothing upload, storage and database models |
| M4 | Wardrobe gallery, categories, filters and editing |
| M5 | AI image analysis and metadata confirmation |
| M6 | Wardrobe-grounded outfit recommendations |
| M7 | Conversational refinement and saved outfits |
| M8 | Testing, security review and deployment |

Follow-on workflow: setup, development, testing, security review, code review, preview deployment, QA, production deployment, monitoring and iteration.

---

## 18. Risks, Open Questions and Assumptions to Validate

### Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| AI recommends items the user does not own | Server-side ID validation; reject and retry invalid output. |
| Wrong clothing tags from image analysis | User confirmation and editing before saving; manual entry first. |
| Uploading a full wardrobe feels tedious | Quick-start onboarding flow (first outfit in < 10 min with 5 items). AI auto-suggested tags reduce tagging effort. |
| Privacy concerns about personal photos | Clear explanation of processing at upload time. Easy deletion. Auth-checked media serving. |
| AI cost and rate limits | Thumbnails for image analysis. Caching where appropriate. Limits on prompt size. Verify pricing before launch. |
| Unproven differentiation | Test with real students; measure repeat usage. |
| AI fixates on same items, ignoring wardrobe sections | Monitor recommendation diversity. Tune prompts to encourage variety. |

### Open questions (decisions deferred)

| Question | Status |
| --- | --- |
| Which exact AI model and pricing tier to use? | Verify Gemini API availability, pricing, vision capabilities and structured output support before M5. If unsuitable, evaluate alternatives and present comparison before switching. |
| What is the maximum upload file size? | To be determined during M3 (propose 10 MB as starting point). |
| How is chat context managed when conversations grow long? | Keep full conversation history per session; define a token-limit strategy when sending context to the AI model. Decide during M6. |
| Should bulk upload be an MVP feature? | Design single-item upload first; ensure UI supports bulk upload later without rework. Not MVP scope. |
| What happens to saved outfits when a clothing item is deleted? | Handle gracefully: mark item as removed in the outfit, don't break the saved look. Decide exact UX during M7. |

### Assumptions to validate with real users

| # | Assumption | Risk if wrong | Proposed validation |
| --- | --- | --- | --- |
| T1 | Users will upload ≥ 5 items in their first session. | AI can't generate meaningful outfits. Core value blocked. | Track first-session upload count. If median < 5, redesign onboarding. |
| T2 | Users value styling explanations, not just outfit grids. | Investing in a feature nobody reads. | A/B test: card with explanation vs. without. Measure save rate. |
| T3 | Multi-turn chat refinement is preferred over a "regenerate" button. | Chat UI is unnecessary complexity. | Track % of sessions with ≥ 2 messages. If < 20%, add one-click shuffle. |
| T4 | A responsive web app is sufficient; users don't need a native mobile app. | Mobile experience feels sluggish; users abandon. | Monitor mobile vs. desktop split. Collect qualitative feedback. |
| T5 | Users will return for new occasions, not just use Stylora once. | Product not viable long-term. | Measure 7-day and 30-day return rate. |
| T6 | AI-suggested metadata is accurate enough to save time vs. adding friction. | Users waste more time correcting than typing manually. | Track correction rate. If > 40%, tune prompts or default to manual. |
| T7 | The "no paywall" model is a meaningful differentiator for college students. | Positioning doesn't matter if users don't compare apps on pricing. | Ask early users what drew them to Stylora. |
| T8 | Users are comfortable uploading personal clothing photos to a web app. | Privacy hesitation blocks uploads; entire product breaks. | Monitor signup-to-first-upload conversion. If < 50%, investigate. |

---

## 19. Name

**Chosen name: Stylora** — distinctive, style-forward, and approachable for a student audience.

**Tagline: "Your wardrobe, styled."**

The following alternatives were considered during the naming process: Closetly, Wearwise, Drapely, Fitly, Stylr, Dressique. Stylora was selected as the final name.

---

## Appendix A. Change Log

| Version | Date | Changes |
| --- | --- | --- |
| v1.0 (original draft) | Pre-2026-10-18 | Initial PRD under the name "Closetly". |
| v1.0 (finalized) | 2026-10-18 | Renamed to Stylora. Added: mission statement, value proposition, user personas, expanded user stories (14, prioritized by MoSCoW), measurable test targets, accessibility requirements (WCAG-mapped), research findings from Phase 2 competitive analysis, image handling details, saved-outfit edge cases, expanded deferred-features rationale, assumptions-to-validate table. All original approved requirements, architecture, tech stack, milestones and project rules preserved without modification. Original file backed up as `.archive_Closetly_PRD_v1.0_original.md`. |
