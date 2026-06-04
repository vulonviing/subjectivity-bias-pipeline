# Cleaning Audit Results v2 (Step 6)

**Date:** 2026-06-02  
**Corpus:** `data/processed/articles_clean.jsonl` (300 articles, post-Step-5 cleaning)  
**Sample set:** `data/analysis/audit_samples_v2/` — seed=7, 5 articles/outlet, 40 total  
**Scope:** Part A = Step-5 risk verification (data-driven); Part B = third independent audit pass

---

## Part A — Step 5 Risk Verification

### Risk 1: Email Regex — Aşırı Agresif mi?

**Result: MOSTLY PASS — 1 partial false positive, 1 coverage gap found**

Total email-containing lines dropped: **24 lines** across the full 300-article corpus.

| Outlet | Lines Dropped | Assessment |
|---|---|---|
| dailycaller | 10 | All DCNF syndication text (`All content created by DCNF...licensing@...`) ✓ |
| foxnews | 4 | Column intros with email CTAs, Outkick author contact lines ✓ |
| washingtontimes | 5 | AI disclosure notes (×3 articles), author bio with email, WT committee line ✓ |
| theguardian | 1 | Newsletter footer `newsletters@theguardian.com` ✓ |

**Partial false positive — foxnews `edd7b0279069`:**  
Original line 17: *"Here's some free advice for everyone when it comes to dealing with wild animals. Stay a safe distance away, especially when dealing with an animal that can easily weigh north of 800 pounds. Yet, I know that advice will be ignored, and the content will keep flowing. Wouldn't have it any other way. Let me know your thoughts on the video at David.Hookstead@outkick.com."*  
→ First ~3 sentences are editorial content, last sentence is an email CTA. The whole line is dropped, losing the editorial content. This is 1 sentence pair in an Outkick columnist piece. **Accepted — marginal content loss from columnist commentary.**

**Coverage gap — washingtontimes AI disclosure:**  
3 articles have "This article was constructed with the assistance of artificial intelligence and published by a member of The Washington Times' AI News Desk team..." containing `sfink@washingtontimes.com`. The email regex is catching this incidentally. If AI disclosure ever appears without an email (or email is removed from the disclosure), the line would remain. **Recommended fix:** Add `"constructed with the assistance of artificial intelligence"` to `OUTLET_BLACKLIST["washingtontimes"]` explicitly.

**Verdict:** Email regex is performing correctly for 23/24 drops. One partial content loss (1 columnist sentence) is acceptable. Coverage gap in WashTimes AI disclosure should be made explicit.

---

### Risk 2: "Caller" Source-Restricted Alias — False Positive Check

**Result: FULL PASS — 0 false positives**

All 28 `[OUTLET]` token occurrences in dailycaller clean bodies were examined. Every instance is an outlet self-reference:
- Attribution patterns: "told [OUTLET]", "tells [OUTLET]", "[OUTLET] reported", "obtained by [OUTLET]"
- Request patterns: "[OUTLET]'s request for comment", "response to [OUTLET]"  
- Branded program: `"[OUTLET] Sunday"` — correctly masked cross-reference to Fox News Sunday (appearing in a WashTimes article, correctly masked in both sources)

No instances of "Caller" used as a common noun (phone caller, 911 caller) were found in the 20 dailycaller articles. **Alias is safe at current scope.**

---

### Risk 3: MORE LINKS Block-Drop Guard (10-line limit)

**Result: FULL PASS — limit not reached**

Only **1 article** in the entire 300-article corpus contains "MORE LINKS": `75eef60a5706` (dailycaller). Block size after marker: **6 lines** — well within the 10-line guard.

All 6 lines are cross-promotional teasers and were correctly dropped. Guard is sufficient for current corpus.

---

## Part B — Third Sample Audit (seed=7)

### Section 1: New Outlet Leakage Findings

#### FOX NEWS — CRITICAL: 2 instances (1 article dominates)

**File:** `foxnews_1.txt`  
**article_id:** `255f62b3af249a9a04e4e48f196d77e6b9145236`  
**Brand: "CyberGuy"** — Kurt the CyberGuy is a Fox News technology correspondent. Entire article is a branded "CyberGuy" column. Multiple occurrences:
- `"Kurt the CyberGuy will walk you step by step through simple phone security fixes"`
- `"visit CyberGuy.com – trusted by millions who watch CyberGuy on TV daily"`
- `"Copyright 2026 CyberGuy.com"`
- `"Join CyberGuy Live"`, `"CyberGuyLive.com"`  
Confidence: **HIGH**. CyberGuy is a uniquely identifiable Fox News brand; the entire article is a promotional columnist piece.

**File:** `foxnews_3.txt`  
**article_id:** `c88516fb4e0a480e951271649764dda0102554bb`  
`"WASHINGTON POST BLASTS RENT CONTROL AS 'FAILED POLICY'..."` — cross-outlet reference to Washington Post (not in our 8-outlet set, not masked). Confidence: **HIGH**.  
Fix: "Washington Post" and "New York Times" should be added to the cross-outlet masking list even though they're not in our corpus — they appear as cross-references.

#### NPR — HIGH: 1 article, 2 signal types

**File:** `npr_5.txt`  
**article_id:** `b7b8d803fd4ecfe2326054ee902d7528d854c432`  
1. `"[OUTLET]'s Greg Myre tells Up First"` — "Up First" is an NPR-branded podcast. Combined with the journalist name Greg Myre (NPR correspondent), this strongly identifies NPR.  
2. `"[OUTLET]'s Newsmakers"` + journalist name "Leila Fadel" — "Newsmakers" is NPR-branded; Leila Fadel is an NPR correspondent.  
Confidence: **HIGH**. Show names + journalist names = strong NPR identity signal.  
Fix: Add `"Up First"`, `"Newsmakers"` (as NPR-specific), `"Morning Edition"`, `"All Things Considered"` to `SOURCE_RESTRICTED_ALIASES["npr"]`.

#### NPR — MEDIUM: cross-outlet reference

**File:** `npr_2.txt`  
**article_id:** `670ebb63f73e47befc9a810e58e21f3bb62f4b0b`  
`"the EEOC has accused Nike and The New York Times of discrimination against white employees"` — New York Times named as cross-outlet reference. Confidence: **HIGH** for the reference being real; **MEDIUM** for whether it creates actual bias leakage (NYT is not one of our 8 outlets, it's a third-party named in news).  
Note: Masking all news outlet names globally (including non-corpus outlets) could over-mask legitimate news reporting. Recommend adding major legacy outlets to a "cross-reference mask" list.

#### WASHINGTON TIMES — MEDIUM: cross-outlet show reference

**File:** `washingtontimes_1.txt`  
**article_id:** `978724b1934dce627cd13d5710ee5acae1a98030`  
`'the president said on "My View with Lara Trump."'` — "My View with Lara Trump" is a Fox News program. Cross-outlet reference; outlet name is already masked but show name is not. Confidence: **MEDIUM** (less widely known than Fox News Sunday).

#### DAILY CALLER — LOW: original-text artifact, not a masking failure

**File:** `dailycaller_2.txt`  
**article_id:** `79c0a40f829e261443bce28dce1f0aca6abf1172`  
`"Some demonstrators in the outlet's videos tried physically pushing back..."` — the word "outlet's" appears in the original article text (the reporter generically called Middle East Eye "the outlet" in their own writing). This is NOT a masking artifact — our system produced `[OUTLET]` not `outlet`. The original article simply used "outlet" as a generic term. Confidence: **LOW** (not a masking failure; no action needed).

#### HUFFPOST, NY POST, THE GUARDIAN, WASHINGTON EXAMINER — Clean
No leakage found in any of the 5 samples for these 4 outlets.

---

### Section 2: New Boilerplate Findings

#### A. CTAs — 5 HIGH (all in foxnews_1.txt)

**[foxnews] `255f62b3af249a9a04e4e48f196d77e6b9145236`** — `foxnews_1.txt`  
All 5 are in the same CyberGuy branded article:
1. `"Join CyberGuy Live: Lock Down Your Phone in 30 Minutes (Saturday, June 13, 10 am ET)"` — event promo
2. `"Register here: CyberGuyLive.com."` — registration CTA
3. `"Sign up for my FREE CyberGuy Report — Get my best tech tips, urgent security alerts and exclusive deals delivered straight to your inbox."` — newsletter signup
4. `"For simple, real-world ways to spot scams early and stay protected, visit CyberGuy.com – trusted by millions who watch CyberGuy on TV daily."` — website visit CTA
5. `"Plus, you'll get instant access to my Ultimate Scam Survival Guide free when you join."` — upsell CTA  
Note: This entire article is a promotional columnist piece. The CyberGuy brand issue (Section 1) + CTA concentration suggests this article should be dropped from corpus. It has near-zero editorial content by bias-measurement standards.

**[nypost] `16277b31a61b9545b299b95d48ddffe61eb7adb4`** — `nypost_5.txt`  
`"Add The California Post on Google"` — MEDIUM. "The California Post" appears to be a subsidiary or branded property.

#### B. Newsletter / Subscribe — 1 HIGH

**[npr] `670ebb63f73e47befc9a810e58e21f3bb62f4b0b`** — `npr_2.txt`  
`"Stay up to date with our Politics newsletter, sent weekly."` — newsletter subscribe prompt.  
Fix: Add `"stay up to date with our"` to global blacklist.

#### C. Author Bios — None found ✓

#### D. Wire Service Attributions — 1 HIGH (new variant)

**[huffpost] `42e39becb16b93b3ecdfef5668e48e5175544518`** — `huffpost_2.txt`  
`"Associated Press writer Jill Lawless in London contributed to this report."` — singular "Associated Press writer [name]" form. Current blacklist catches `"associated press writers"` (plural) but NOT the singular `"associated press writer"` form.  
Fix: Add `"associated press writer"` (singular) to `GLOBAL_BLACKLIST`.

#### E. Cross-Promotion — None found ✓
#### F. Photo Credits — None found ✓
#### G. Disclaimers — None found ✓

#### H. Technical Artifacts — 3 HIGH, 2 MEDIUM

1. **[dailycaller] `79c0a40f829e261443bce28dce1f0aca6abf1172`** — `dailycaller_2.txt`  
   `"Don't be this guy. pic.twitter.com/jEIrBmsG88"` — Twitter/X media embed URL remnant. Severity: **HIGH**.  
   Fix: Add `"pic.twitter.com/"` to global blacklist.

2. **[npr] `b7b8d803fd4ecfe2326054ee902d7528d854c432`** — `npr_5.txt`  
   `"Listen to the full story by clicking the blue play button above."` — audio embed player instruction. Severity: **HIGH** (already noted in previous audit as LOW, upgrading to HIGH).  
   Fix: Add `"clicking the blue play button"` to global blacklist (or `"listen to the full story"`).

3. **[npr] `b7b8d803fd4ecfe2326054ee902d7528d854c432`** — `npr_5.txt`  
   `"🎧 The war in Lebanon..."` and `"🎧 Some members of Congress are angry..."` — headphone emoji prefixes on lines, likely stripped from audio story chapters. Severity: **MEDIUM**.  
   Fix: Add emoji-prefixed line pattern to global blacklist OR strip leading emojis.

#### I. Social Media / X Post Artifacts — 2 HIGH, 1 MEDIUM

1. **[dailycaller] `2abb052dd42aa91f98572b03afab5c3ee9679571`** — `dailycaller_1.txt`  
   Full embedded X post: `"Today's decision by Governor Jared Polis to commute Tina Peters' sentence is a long-overdue step toward justice... — Rep. Lauren Boebert (@RepBoebert) May 15, 2026"` — full quoted tweet text with attribution line. Severity: **HIGH** (attribution line `— @handle Month Day, Year` is boilerplate even if quote content is editorial).  
   Fix: Add regex pattern `r"^—\s+\S+\s+\(@\w+\)\s+\w+\s+\d+,\s+\d{4}$"` to global blacklist (standalone tweet attribution line).

2. **[dailycaller] `79c0a40f829e261443bce28dce1f0aca6abf1172`** — `dailycaller_2.txt`  
   `"Alaska Landmine: Dan Sullivan files to run... pic.twitter.com/T7FpheWv9E — Politics & Poll Tracker 📡 (@PollTracker2024) May 29, 2026"` — tweet with pic URL + attribution. Severity: **MEDIUM** (this serves as evidence in journalism but the pic URL + attribution line is chrome).

#### J. Datelines / Metadata — None found ✓

#### K. Washington Times AI Disclosure — Not in this sample set

(Caught by email regex in Part A; dedicated blacklist entry recommended as per Risk 1 findings.)

---

## Section 3: Summary & Recommended Actions for Step 7

### Part A Risks — Final Verdicts

| Risk | Verdict | Action |
|---|---|---|
| Risk 1: Email regex aggression | PASS with 1 false positive | Add WashTimes AI disclosure to explicit blacklist |
| Risk 2: "Caller" alias | FULL PASS — 0 false positives | No change needed |
| Risk 3: MORE LINKS guard | FULL PASS — max block=6 lines | No change needed |

### New Blacklist Additions (HIGH priority)

| Scope | Pattern | Reason |
|---|---|---|
| Global | `"associated press writer"` (singular) | AP byline variant missed (huffpost_2) |
| Global | `"stay up to date with our"` | NPR newsletter subscribe |
| Global | `"pic.twitter.com/"` | Twitter media embed URL |
| Global | `"clicking the blue play button"` | NPR audio embed instruction |
| Global | regex: `^- .+\(@\w+\) \w+ \d+, \d{4}$` | Tweet attribution line |
| `foxnews` | `"CyberGuy"` → SOURCE_RESTRICTED_ALIASES | Fox-specific brand |
| `foxnews` | `"cybergy.com"`, `"CyberGuyLive.com"`, `"Register here:"`, `"Sign up for my FREE"` | CyberGuy article CTAs |
| `foxnews` (or SOURCE_RESTRICTED) | `"Fox Nation"`, `"Fox Business"`, `"Fox & Friends"`, `"Fox Weather"` | Fox sub-brands |
| `npr` → SOURCE_RESTRICTED_ALIASES | `"Up First"`, `"Morning Edition"`, `"All Things Considered"`, `"Newsmakers"`, `"Fresh Air"` | NPR branded programs |
| `washingtontimes` | `"constructed with the assistance of artificial intelligence"` | AI disclosure (explicit, not via email regex) |

### Cross-Outlet Reference Masking (MEDIUM priority)

`"Washington Post"`, `"New York Times"`, `"Wall Street Journal"`, `"ABC News"`, `"CBS News"`, `"NBC News"`, `"CNN"`, `"MSNBC"` — these non-corpus outlets appear as cross-references in articles. For downstream LLM annotation they create identity leakage (e.g., "Fox attacks CNN" → tells the model this is a Fox article). Recommended: add to a `CROSS_OUTLET_ALIASES` list in `OUTLET_ALIASES` (applied to all articles).

### Corpus Quality Note

`foxnews_1.txt` (`255f62b3af249a9a04e4e48f196d77e6b9145236`) is a CyberGuy branded promotional column with near-zero editorial content. It has 5 CTA lines, multiple brand mentions, a newsletter signup, and event registration. **Recommended: drop this article from corpus** (Step 7 decision — check left/right balance impact first).

### Emoji Artifacts

NPR `🎧` prefixes and potential other emoji artifacts from audio-first articles. Recommend adding `re.compile(r'^[\U00010000-\U0010ffff☀-⟿]\s')` (leading emoji pattern) to `_GLOBAL_REGEX`.
