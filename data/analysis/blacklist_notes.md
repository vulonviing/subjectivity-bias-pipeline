# Blacklist Pattern Notes (Manuel İnceleme — 5 sample/outlet, seed=42)

Patterns below are encoded in `src/cleaning.py`. This file is reference/scratch; truth is in code.

## GLOBAL (2+ outlets)
- "Click here" / "CLICK HERE" — CTA, tüm Fox makalelerinde, genel web kalıbı
- "See more of our coverage in your search results" — HuffPost/NYPost SEO CTA
- "Add [Outlet] on Google" — HuffPost/NYPost Google News CTA
- "Agence France-Presse and Reuters contributed" — wire byline, HuffPost/Guardian/NPR
- "Reporting by … ; Editing by …" — Reuters byline
- "contributed reporting to this story" — NPR/Guardian byline
- "Watch the clip here" — HuffPost/NYPost
- "Recommended Stories" — WashExaminer interstitial başlık
- "If you or someone you know needs help" / "If you or someone you care about is affected" — mental health disclaimer, HuffPost/NYPost
- "call SAMHSA's National Helpline" — substance abuse disclaimer
- "Loading..." — interactive placeholder
- "Subscribe to" — newsletter CTA
- "Follow" — follow/social CTA
- "(RELATED:" — DC inline link kalıbı

## PER-OUTLET

### dailycaller
- "All content created by the Daily Caller News Foundation" — DCNF syndication boilerplate (her zaman son paragraf)
- "licensing@dailycallernewsfoundation.org" — tek satırda, drop et
- "The views and opinions expressed in this commentary are those of the author" — görüş reddi
- "Follow him on Twitter @" / "Follow her on Twitter @" — author social CTA
- "spent [time] as a media & politics reporter with the Daily Caller" — author bio kuyruk
- "(RELATED:" — inline link kalıbı

### foxnews
- "CLICK HERE TO DOWNLOAD THE FOX NEWS APP"
- "CLICK HERE TO GET THE FOX NEWS APP"
- "CLICK HERE TO SIGN UP FOR THE ENTERTAINMENT NEWSLETTER"
- "CLICK HERE FOR MORE SPORTS COVERAGE ON FOXNEWS.COM"
- "LIKE WHAT YOU'RE READING? CLICK HERE"
- "ZERO BS. JUST DAKICH." — podcast promo
- "TAKE THE DON'T @ ME PODCAST ON THE ROAD" — podcast promo
- "DOWNLOAD NOW!" — app/podcast CTA

### huffpost
- "If you or someone you know needs help, call or text 988 or chat 988lifeline.org"
- "you can find local mental health and crisis resources at dontcallthepolice.com"
- "Outside of the U.S., please visit the International Association for Suicide Prevention"

### npr
- "Want the latest stories on the science of healthy living? Subscribe to NPR's Health newsletter."
- "Subscribe to NPR's" — any NPR newsletter promo
- "This newsletter was edited by" — newsletter editor sign-off
- "You're reading the Up First newsletter" — newsletter chrome
- "Subscribe here to get it delivered to your inbox" — newsletter CTA
- "listen to the Up First podcast" — podcast CTA

### nypost
- "Add Page Six on Google" — Google News CTA
- "Add The New York Post on Google" — Google News CTA
- "Warning: Spoilers ahead! Do not proceed unless you've watched" — entertainment warning
- "Page Six reached out to the network for comment" — boilerplate attribution (sık tekrar)
- "If you or someone you care about is affected by any of the issues" — substance/mental health disclaimer

### theguardian
- "If you want to contact me, please post a message below the line" — live blog engagement
- "If you want to flag something up urgently, it is best to use social media" — engagement CTA
- "I find it very helpful when readers point out mistakes" — editorial solicitation
- "The Guardian has given up posting from its official accounts on X" — meta-editorial bleed

### washingtonexaminer
- "Recommended Stories" — nav interstitial (5/5 örnekte çıktı)
- "is a Washington Examiner contributing writer" — author bio kuyruk
- "Find him on X @" / "Find her on X @" — social CTA

### washingtontimes
- Örneklerde belirgin tek satır boilerplate az; satır-bazlı temizlik yerine
  pattern match yeterli (global "Click here", "Subscribe" kalıpları yeterli)
