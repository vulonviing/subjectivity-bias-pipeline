# Cleaning Audit Results

**Date:** 2026-06-02  
**Audited corpus:** `data/processed/articles_clean.jsonl` (300 articles, post-cleaning)  
**Sample set:** `data/analysis/audit_samples/` — outlet başına 5 makale, `random.seed(99)`, toplam 40 dosya  
**Two independent audit passes:** Stage 2 = outlet identity leakage, Stage 3 = boilerplate  
**Critical bug found and fixed during audit** (word-boundary masking failure — see Section 3)

---

## Summary

| Audit Type | Findings | Severity Distribution |
|---|---|---|
| Outlet Leakage | 14 instances (3 outlets critical) | 10 HIGH, 3 MEDIUM, 1 LOW |
| Boilerplate | 22 instances (9 categories) | 11 HIGH, 8 MEDIUM, 3 LOW |
| Masking Bug (fixed) | 17 articles corrupted | CRITICAL (fixed in same session) |
| **TOTAL** | **36 unique findings** | — |

---

## Section 1: Outlet Identity Leakage Findings

### DAILY CALLER — CRITICAL: 9 instances, 1 file

**File:** `dailycaller_1.txt`  
**article_id:** `e8cc2232cd89ed0694bab6eb58a0169cfe7573ba`

Pattern: `"the Caller"` — possessive/article form preceding outlet name was not matched by the existing alias `"Daily Caller"` (because alias requires the full "Daily Caller" string, not abbreviated "the Caller").

Exact instances:
1. `"a former Justice official tells the Caller"`
2. `"Mike Davis, Trump ally and founder of the Article III project, told the Caller"`
3. `"the former official told the Caller"`
4. `"a former DOJ official told the Caller"`
5. `"A DOJ official told the Caller"`
6. `"the DOJ official told the Caller"`
7. `"he told the Caller"`
8. `"a former DOJ official told the Caller"`
9. `"White House spokeswoman Abigail Jackson told the Caller"`

**Root cause:** `"the Caller"` is a common attribution shorthand in Daily Caller articles. Not in alias list.  
**Fix:** Add `"the Caller"` to `OUTLET_ALIASES["dailycaller"]`.

---

### FOX NEWS — HIGH: 3 instances (branded column), 1 file

**File:** `foxnews_3.txt`  
**article_id:** `dcc8101e8abd84c32ad2d7ee415b039e62ce4484`

Pattern: `"Screencaps"` — a Fox News / Outkick branded newsletter column ("Screencaps with Joe Kinsey"). The column name is a strong outlet identity signal.

Exact instances:
1. `"Monday Screencaps is dialed in"`
2. `"I've been telling Screencaps readers about Rachel"`
3. `"With the help of Screencaps Jr."`
4. `"Mrs. Screencaps' drip irrigation system"`
5. `"Screencaps Page"` / `"Screencaps with Joe Kinsey"` / `"Screencaps reader Travel Ball Hardo"`
6. `"@[OUTLET]Screencaps"` — partial masking (Outkick was masked but "Screencaps" remained)

Also: `"📧 Email: joe.kinsey@[OUTLET].com"` — email with full name reveals identity. This article is an Outkick branded newsletter piece; the entire article is high-boilerplate (see Section 2-H).

**Fix:** Add `"Screencaps"` to `OUTLET_ALIASES["foxnews"]`. Consider blacklisting this article type entirely (branded newsletter column, not editorial content).

---

### NY POST — HIGH: 1 instance, 1 file

**File:** `nypost_4.txt`  
**article_id:** `c31f7c6ec571bc71d3a7e74fc540af58dc158fb7`

Pattern: `"Decider"` — Decider.com is a TV/streaming guide site. NYPost URL headers include `decider.com` URLs.

Exact instance:
- `"Stay tuned for more Not Suitable for Work coverage from Decider."` (line 52)

**Fix:** Add `"Decider"` to `OUTLET_ALIASES["nypost"]`.

---

### HUFFPOST — Clean
No leakage found.

### NPR — Clean
No leakage found.

### THE GUARDIAN — Clean in article bodies
One email artifact found in body text (see Section 2-H): `"mail newsletters@the[OUTLET].com"` — a newsletter subscription address where the domain leaked partially. After word-boundary fix, the Guardian's name was masked correctly in running text; this email artifact is a boilerplate line that should be dropped by blacklist.

### WASHINGTON EXAMINER — Clean
No leakage found.

### WASHINGTON TIMES — MEDIUM: 1 instance (technically masked, contextually identifying)

**File:** `washingtontimes_1.txt`  
**article_id:** `59e21efd9be9144de292f08a2bbaa3ab6ca07bf2`

`"former [OUTLET] host Steve Hilton are considered the front-runners"`  
→ Technically masked correctly (`[OUTLET]` replaces the outlet name). But `Steve Hilton` is uniquely associated with Fox News. Masking is correct; this is a **cross-outlet mention**, not self-reference. Confidence: MEDIUM — Steve Hilton is well-known enough that readers/models might infer Fox News.  
**Fix:** No action needed (correct masking already applied; journalist name not in scope per plan).

---

## Section 2: Boilerplate Findings

### A. CTA Lines — None found

### B. Newsletter / Subscription / App Prompts — 3 instances (MEDIUM)

All in `foxnews_3.txt` (`dcc8101e8abd84c32ad2d7ee415b039e62ce4484`) — an Outkick branded newsletter article:
1. `"🗞️ Newsletter: 👉 Subscribe here"` — explicit subscribe CTA
2. `"📬 Mail (Thursday Night Mowing League): 27072 Carronade Dr, Unit A 155 Perrysburg, OH 43551"` — mailing address for reader submissions
3. `"📧 Email: joe.kinsey@[OUTLET].com"` — author contact email (also outlet leakage)

**Fix:** This entire article is a branded newsletter (Screencaps); the body is predominantly boilerplate. Blacklist `"Subscribe here"`, emoji-prefixed contact blocks. Or drop the full article from corpus as non-editorial.

### C. Author Bio / Byline Tail Paragraphs — 4 instances (3 HIGH, 1 MEDIUM)

1. **[washingtonexaminer] `6a3989882ecdf71513a3b3f60bbc3b97bf7d2999`** — `washingtonexaminer_2.txt`  
   `"Joshua Kresh is a research professor and the executive director of the IP Policy Institute at the University of Akron School of Law.\nMelanie Whittington is the head of the Center for Pharmacoeconomics, MEDACorp, an affiliate of Leerink Partners."`  
   Severity: **HIGH**. Two-author bio block not caught by bio heuristic (heuristic looks for solo trailing paragraph; this is a two-author block mid-article tail).  
   Fix: Bio heuristic needs to handle multi-author bio blocks; or blacklist `"is the head of"`, `"is a research professor"` patterns for tail paragraphs.

2. **[washingtonexaminer] `406d5f6ab701716f1940691eb3aa03901a40de6c`** — `washingtonexaminer_5.txt`  
   `"Mark Whittington, who writes frequently about space policy, has published a political study of space exploration entitled Why is It So Hard to Go Back to the Moon? as well as The Moon, Mars and Beyond, and, most recently, Why is America Going Back to the Moon? He blogs at Curmudgeons Corner. He is published in the Wall Street Journal, Forbes, The Hill, USA Today, the LA Times, and the Washington Post, among other venues."`  
   Severity: **HIGH**. Multi-sentence author bio with book titles and publication list. Bio heuristic missed it (paragraph > 300 chars; heuristic has a 300-char limit).  
   Fix: Raise bio heuristic char limit, or add `"He blogs at"`, `"He is published in"`, `"writes frequently about"` to `OUTLET_BLACKLIST["washingtonexaminer"]`.

3. **[huffpost] `7df27080b5110001d4a6a013441e3edac7bad3db`** — `huffpost_1.txt`  
   `"Associated Press writers Jamie Stengle in Dallas and Mary Claire Jalonick and Joey Cappelletti contributed to this report."`  
   Severity: **HIGH**. Named AP contributor byline — different form than the global pattern `"contributed reporting to this story"`. Current global blacklist catches unnamed forms but not "Associated Press writers [names]... contributed to this report."  
   Fix: Add `"associated press writers"` and `"ap writers"` to global blacklist.

4. **[foxnews] `dcc8101e8abd84c32ad2d7ee415b039e62ce4484`** — `foxnews_3.txt`  
   `"👥 Facebook Group: Join the Screencaps Community\n📬 Mail...\n🗞️ Newsletter: 👉 Subscribe here"`  
   Severity: **MEDIUM**. Author community/contact block (overlaps with B above).

### D. Wire Service / Syndication Bylines — 1 instance (HIGH)

**[huffpost] `7df27080b5110001d4a6a013441e3edac7bad3db`** — `huffpost_1.txt`  
`"WASHINGTON (AP) -"` at article opening (AP dateline).  
Severity: **HIGH**. Wire service dateline at body start — pattern `"(AP)"` and `"(Reuters)"` inline should be blacklisted.  
Fix: Add `"(AP)"`, `"(Reuters)"`, `"(AFP)"`, `"(Bloomberg)"` as global blacklist entries. Also `" AP) "` — note the space pattern for inline wire labels.

### E. Cross-Promotion / Related Content — 3 instances

1. **[dailycaller] `75eef60a570655cb9688f6615884b0eb6ddb3bfe`** — `dailycaller_3.txt`  
   ```
   MORE LINKS
   The DOJ Was Already Primed. Todd Blanche Lit the Fuse
   A change in management.
   Clock Ticking On GOP To Pass Literally Anything As Midterms Loom
   Where is Congress at, exactly?
   Lesbian Minister Cancels July 4 Celebrations In Political Protest
   SMH
   ```  
   Severity: **HIGH**. Explicit "MORE LINKS" cross-promotion section with editorial teaser descriptions.  
   Fix: Add `"MORE LINKS"` to `OUTLET_BLACKLIST["dailycaller"]`. The subsequent 2–3 lines (article titles + one-line teasers) need a consecutive-line heuristic or explicit blacklisting.

2. **[nypost] `c31f7c6ec571bc71d3a7e74fc540af58dc158fb7`** — `nypost_4.txt`  
   `"Is There A Not Suitable for Work Trailer?\nYou bet! Get your first look at your new favorite hangout comedy in Hulu's official Not Suitable for Work trailer here."`  
   Severity: **MEDIUM**. Promotional trailer description masquerading as editorial content.

3. **[nypost] `c31f7c6ec571bc71d3a7e74fc540af58dc158fb7`** — `nypost_4.txt`  
   `"Stay tuned for more Not Suitable for Work coverage from Decider."` (also logged in Section 1 — outlet leakage)  
   Severity: **MEDIUM**.

### F. Photo / Media Credits — None found

### G. Disclaimers / Notices — 1 instance (LOW)

**[theguardian] `12a6b2641cd5fba63a00f5fe08708c5216d2240a`** — `theguardian_1.txt`  
`"[OUTLET]'s Adrian Florido spoke with aid workers... Listen to the full story by clicking the blue play button above."`  
Severity: **LOW**. This is an editorial note about a multimedia story format — arguably legitimate content that explains the article's format. Keeping as LOW, no blacklist action needed.

### H. Interactive / Technical Artifacts — 4 instances (3 HIGH, 1 MEDIUM)

1. **[dailycaller] `e30372e90daa494323fd15f2a2938e4f08e12c5f`** — `dailycaller_4.txt`  
   `"View this post on Instagram\nView this post on Instagram"`  
   Severity: **HIGH**. Instagram embed placeholder text. Content scraper artifact.  
   Fix: Add `"View this post on Instagram"`, `"View this post on Facebook"`, `"View this post on"` to global blacklist.

2. **[foxnews] `dcc8101e8abd84c32ad2d7ee415b039e62ce4484`** — `foxnews_3.txt`  
   ```
   📩 Email: joe.kinsey@[OUTLET].com Send photos, stories, tips, rants-whatever you've got.
   📰 Screencaps Page: 👉 Read the latest Screencaps
   ▶️ YouTube: Screencaps with Joe Kinsey Subscribe for videos, rants, and behind-the-scenes.
   🐦 Twitter/X: @JoeKinseyexp Tag me or drop a DM.
   📸 Instagram: @[OUTLET]Screencaps You guys need to start tagging me on content you're seeing.
   ```  
   Severity: **HIGH**. Author social media promotion block with emoji formatting.  
   Fix: Add `"Twitter/X:"`, `"YouTube:"` (when standalone line), emoji-prefixed contact patterns. Or blacklist the whole foxnews_3 article type.

3. **[theguardian] `e71fb8da23a6...`** — body contained email address `"mail newsletters@the[OUTLET].com"`.  
   Severity: **HIGH**. Email address with outlet domain leaked in body (newsletter footer bleed).  
   Fix: Add `"newsletters@"`, `"@the"` (email context) patterns to Guardian blacklist. Better: add global pattern `\S+@\S+\.\S+` (any email address in body line) → drop line.

4. **[nypost] `c31f7c6ec571bc71d3a7e74fc540af58dc158fb7`** — `nypost_4.txt` cast list:  
   ```
   - Ella Hunt as AJ Pascarelli
   - Avantika as Abhinaya "Abby" Chilukuri
   - Nicholas Duvernay as Kel Washington
   - Jack Martin as Josh Teitelbaum
   ```  
   Severity: **MEDIUM**. Structured cast list — legitimate editorial content for an entertainment article. No action needed.

### I. Social Media Artifacts — 2 instances (MEDIUM)

1. **[washingtontimes] `21d6688b0ce1f540f3198ae500ce1481cdf4c3d6`** — `washingtontimes_2.txt`  
   `"- Spencer Pratt (@spencerpratt) January 8, 2026"`  
   Severity: **MEDIUM**. Embedded X/Twitter attribution with handle and timestamp. This is a standard embedded tweet citation — arguably legitimate sourcing.

2. **[theguardian] `477610b01578156596d9f78d8b56ecc227882aa9`** — `theguardian_5.txt`  
   `"- Spencer Pratt (@spencerpratt) January 8, 2026"` (same X post, syndicated to Guardian)  
   Severity: **MEDIUM**. Same as above.  
   Note: Keeping these as LOW priority — embedded quotes with attribution are editorial sourcing, not boilerplate. Consider dropping lines matching `^- @\w+ \(\w+\) \w+ \d+, \d{4}$` for pure-handle attribution lines.

### J. Dateline / Metadata Bleed — 1 instance (HIGH)

**[huffpost] `7df27080b5110001d4a6a013441e3edac7bad3db`** — `huffpost_1.txt`  
`"WASHINGTON (AP) -"` (also logged in D)  
Severity: **HIGH**. ALL-CAPS dateline at article start. Pattern: `^[A-Z ]+\s*\(AP\)` or `^[A-Z ]+\s*\(Reuters\)`.

---

## Section 3: Masking Bug — Found and Fixed in This Session

### Bug Description

Two distinct sub-bugs in `src/cleaning.py: _get_mask_patterns()`:

**Bug A — Short alias within words (NPR):**  
`re.compile(re.escape("NPR"), re.I)` without word boundaries matched `"NPR"` inside common English words:
- `"uNPRecedented"` → `"unprecedented"` → `"u[OUTLET]ecedented"` (17 articles affected)
- `"noNPRofit"` → `"nonprofit"` → `"no[OUTLET]ofit"`
- `"uNPRedictable"` → `"unpredictable"` → `"u[OUTLET]edictable"`

**Bug B — Multi-word alias as substring (FOX NEWS APP):**  
`"FOX NEWS APP"` (case-insensitive) matched `"Fox News app"` at the start of `"Fox News appearance"`:
- `"Fox News appearance"` → `"[OUTLET]earance"` (1 article)

**Scope:** 17 articles corrupted (15 broken-word + 2 partial overlap).

**Fix applied:** `src/cleaning.py:152` — added `\b` word boundaries:
```python
# Before:
pat = re.compile(re.escape(alias), re.I)
# After:
pat = re.compile(r'\b' + re.escape(alias) + r'\b', re.I)
```

`articles_clean.jsonl` regenerated. Post-fix verification: `broken_word_pattern.search(corpus)` → **0 articles**.

---

## Section 4: Recommended Blacklist Additions for `src/cleaning.py`

Items are grouped by priority. Implementation is the next step (separate from this audit).

### HIGH PRIORITY — Add to `OUTLET_ALIASES`

| Outlet | Add alias |
|---|---|
| `dailycaller` | `"the Caller"` |
| `foxnews` | `"Screencaps"` |
| `nypost` | `"Decider"` |

### HIGH PRIORITY — Add to `OUTLET_BLACKLIST` / `GLOBAL_BLACKLIST`

| Scope | Pattern | Reason |
|---|---|---|
| Global | `"associated press writers"` | AP contributor byline variant |
| Global | `"ap writers"` | Same |
| Global | `"(AP)"` | Inline wire label |
| Global | `"(Reuters)"` | Inline wire label |
| Global | `"(AFP)"` | Inline wire label |
| Global | `"View this post on Instagram"` | Social embed artifact |
| Global | `"View this post on Facebook"` | Social embed artifact |
| Global | any line matching `\S+@\S+\.\S+` | Email addresses in body |
| `dailycaller` | `"MORE LINKS"` | Cross-promotion section header |
| `washingtonexaminer` | `"He blogs at"` | Author bio tail variant |
| `washingtonexaminer` | `"He is published in"` | Author bio tail variant |
| `washingtonexaminer` | `"writes frequently about"` | Author bio tail variant |
| `washingtonexaminer` | `"is a research professor"` | Author bio tail variant |
| `washingtonexaminer` | `"is the head of"` | Author bio tail variant |
| `foxnews` | `"Twitter/X:"` | Author social media block |
| `foxnews` | `"YouTube:"` | Author social media block |
| `theguardian` | `"newsletters@"` | Email footer bleed |

### MEDIUM PRIORITY — Consider

| Issue | Recommendation |
|---|---|
| Washington Examiner bio >300 chars | Raise `_BIO_SIGNALS` heuristic char limit from 300 → 600 |
| Daily Caller "MORE LINKS" trailing article titles | Multi-line heuristic: after "MORE LINKS" drop all lines until blank or end |
| Foxnews_3 Screencaps article | Entire article is newsletter column — consider dropping from corpus |
| Emoji-prefixed contact lines (📧 📬 🗞️) | Add emoji pattern to blacklist (foxnews only) |
| X/Twitter attribution lines `- @handle (date)` | LOW — editorial sourcing, keep |

### MASKING BUG — Fixed (no further action)

Word-boundary fix applied to `src/cleaning.py:152`. `articles_clean.jsonl` regenerated. Verified: 0 broken-word instances.
