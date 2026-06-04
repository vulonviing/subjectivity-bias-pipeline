"""Body text cleaning: blacklist-based boilerplate removal and outlet-name masking."""
from __future__ import annotations

import re

OUTLET_TOKEN = "[OUTLET]"

# Case-insensitive substring: any line containing one of these is dropped entirely.
GLOBAL_BLACKLIST: list[str] = [
    "click here",
    "download the fox news app",
    "download now",
    "see more of our coverage in your search results",
    "add page six on google",
    "add the new york post on google",
    "agence france-presse and reuters contributed",
    "reuters contributed to this report",
    "contributed reporting to this story",
    "associated press writer",
    "associated press writers",
    "ap writers",
    "(ap)",
    "(reuters)",
    "(afp)",
    "watch the clip here",
    "recommended stories",
    "if you or someone you know needs help",
    "if you or someone you care about is affected",
    "call samhsa's national helpline",
    "988lifeline.org",
    "dontcallthepolice.com",
    "international association for suicide prevention",
    "loading...",
    "subscribe to",
    "follow him on twitter",
    "follow her on twitter",
    "follow him on x @",
    "follow her on x @",
    "(related:",
    "reporting by",
    "editing by",
    "view this post on",
    "stay up to date with our",
    "pic.twitter.com/",
    "clicking the blue play button",
    "listen to the full story",
    "follow ap's coverage",
    "follow ap's coverage",
]

OUTLET_BLACKLIST: dict[str, list[str]] = {
    "dailycaller": [
        "all content created by the daily caller news foundation",
        "licensing@dailycallernewsfoundation.org",
        "the views and opinions expressed in this commentary are those of the author",
        "spent.*as a media.*reporter with the daily caller",  # regex
        "do not reflect the official position of the daily caller",
        # "more links" is handled by _DROP_BLOCK_MARKERS (drops marker + trailing block)
    ],
    "foxnews": [
        "zero bs. just dakich",
        "take the don't @ me podcast",
        "download now!",
        "like what you're reading?",
        "twitter/x:",
        "youtube:",
        "facebook group:",
        "join the screencaps community",
        "cyberguy",
        "cyberguylive.com",
        "join cyberguy live",
        "register here:",
        "sign up for my free cyberguy report",
        "ultimate scam survival guide",
        "trusted by millions who watch cyberguy",
        "write to us at cyberguy.com",
        "get my best tech tips",
        "exclusive deals delivered straight to your inbox",
    ],
    "huffpost": [
        "call or text 988 or chat 988lifeline.org",
        "find local mental health and crisis resources",
        "outside of the u.s., please visit the international association",
    ],
    "npr": [
        "want the latest stories on the science of healthy living",
        "subscribe to npr's",
        "this newsletter was edited by",
        "you're reading the up first newsletter",
        "subscribe here to get it delivered to your inbox",
        "listen to the up first podcast",
        "good morning. you're reading",
        "accessibility links",
        "copyright ©",
        "copyright (c)",
        "all rights reserved",
        "visit our website terms of use",
        "accuracy and availability",
        "transcript text may be revised",
        "audio on npr.org may be edited",
        "audio on [outlet].org may be edited",
        "authoritative record of npr",
        "authoritative record of [outlet]",
    ],
    "nypost": [
        "add the new york post on google",
        "warning: spoilers ahead",
        "page six reached out to",
        "if you or someone you care about is affected by any of the issues raised in this story",
        "california post news:",
        "california post sports facebook",
        "california post opinion",
        "california post newsletters",
        "california post app",
        "home delivery: sign up here",
        "why trust new york post betting",
        "why trust post wanted by the new york post",
        "why trust post wanted by new york post",
        "page six hollywood: sign up here",
        "commerce streaming reporter",
        "post wanted shopping",
    ],
    "theguardian": [
        "if you want to contact me, please post a message below the line",
        "if you want to flag something up urgently",
        "i find it very helpful when readers point out mistakes",
        "the guardian has given up posting from its official accounts on x",
        "if you're not already signed up, subscribe now",
        "if you're not already signed up, subscribe now",
        "sign up here for a weekly roundup",
        "newsletters team",
        "newsletters@",
    ],
    "washingtonexaminer": [
        "in focus delivers deeper coverage",
        "published daily by senior writers",
        "you can find our full list of in focus pieces here",
        "is a washington examiner contributing writer",
        "find him on x @",
        "find her on x @",
        "he blogs at",
        "she blogs at",
        "he is published in",
        "she is published in",
        "writes frequently about",
        "is a research professor",
        "is the head of",
        "is the executive director",
    ],
    "washingtontimes": [
        "constructed with the assistance of artificial intelligence",
        "ai news desk",
        "- the front page",
        "- threat status",
        "- politically unstable",
        "- the sitdown with alex swoyer",
        "- bold & blunt",
        "- the higher ground",
        "- court watch",
        "- victory over communism",
        "- district of sports",
        "capitol hill show",
        "- the unregulated podcast",
        "- foramerica",
        "- washington times weekly",
        "- god, country & american story",
        "- games",
        "- subscribe",
        "- sign in",
        "subscribe - sign in",
    ],
}

# After blacklist-line removal, drop contiguous blocks that follow these markers
# (up to MAX_BLOCK_DROP_LINES lines or until a blank line, whichever comes first).
_DROP_BLOCK_MARKERS: dict[str, list[str]] = {
    "dailycaller": ["more links"],
}
_MAX_BLOCK_DROP_LINES = 10

# Regex patterns: any line matching is dropped entirely.
_GLOBAL_REGEX: list[re.Pattern] = [
    re.compile(r"\S+@\S+\.\S+"),  # email addresses (author contact / newsletter footer)
    # Standalone tweet attribution line: "- Name (@handle) Month DD, YYYY"
    # Em-dashes are normalized to hyphen-minus before this runs (see clean_body).
    re.compile(r"^-\s+.+\(@\w+\)\s+\w+\s+\d+,\s*\d{4}\s*$"),
    re.compile(r"^-+$"),
    re.compile(r"^[--]\s+.+\(@\w+\).+\w+\s+\d+,\s*\d{4}\s*$"),
    re.compile(r"^https?://\S+\s+[--]\s+.+\(@\w+\).+\w+\s+\d+,\s*\d{4}\s*$"),
    re.compile(r"#{5,}"),
    # Lines starting with (optional "- ") + pictographic emoji (e.g. NPR audio chapter markers: "- 🎧 …")
    re.compile(r"^-?\s*[\U0001F300-\U0001FAFF\U00002600-\U000027BF]"),
]

_TRAILING_SHORTLINK = re.compile(r"\s+https?://t\.co/\S+\s*$", re.I)
_NYPOST_CALIFORNIA_PREFIX = re.compile(r"^add the california post on google\s*", re.I)
_INLINE_SEPARATOR = re.compile(r"\s*_{3,}\s*")
_SOUNDBITE_OF_MUSIC = re.compile(r"\s*\(SOUNDBITE OF MUSIC\)\s*", re.I)
_WT_INLINE_NAV_TAIL = re.compile(r"\s+-\s+Commentary\s+-\s+Corrections\b.*$", re.I)
_TRAILING_DANGLING_HYPHEN = re.compile(r"\s+-\s*$")
_READ_IN_FULL = re.compile(r"^read .{0,100} in full here\.?$", re.I)
_NPR_STANDALONE_HEADINGS = {
    "today's top stories",
    "watch this",
    "picture show",
    "the claim",
    "the evidence",
    "cautions and alternatives",
    "the bottom line",
}
_GUARDIAN_STANDALONE_HEADINGS = {
    "the front pages",
    "today in focus",
    "the upside",
    "bored at work?",
    "power for profit",
    "an administration uninhibited",
    "the new normal?",
    "the global atelier",
}
_WT_STANDALONE_HEADINGS = {
    "joining a political shift in the americas",
    "a blow to cepeda",
    "a warming relationship with the u.s. draws criticism",
    "maduro's ouster prompts power struggle",
    "loyalists discuss possible betrayal of maduro",
    "the election records fight",
    "the judicial discipline case",
    "the 2020 georgia election case",
    "the justice department's arguments",
}
_GUARDIAN_LIVEBLOG_META_PREFIX = re.compile(
    r"^(?:first published on\s+)?mon\s+\d+\s+\w+\s+\d{4}\s+\d+(?:\.\d+)?\s+cest",
    re.I,
)

_OUTLET_REGEX: dict[str, list[re.Pattern]] = {
    "dailycaller": [
        re.compile(r"spent .{0,60} as a (media|politics|reporter|political)", re.I),
    ],
    "foxnews": [
        # Related-story headline bleed: pure all-caps lines embedded in article body
        re.compile(r"^(?=.{12,160}$)(?=.*[A-Z])(?=.*\s)[A-Z0-9][A-Z0-9\s,.'\"""?!:;()&/-]+$"),
    ],
    "npr": [
        # Anchor/byline introduction lines: "ADRIAN FLORIDO, HOST:" / "ERIC MCDANIEL, BYLINE:"
        re.compile(r"^[A-Z][A-Z\s.\-']{2,40},\s+(HOST|BYLINE|CORRESPONDENT|REPORTER):\s*$"),
        # Bare speaker heading: "MCDANIEL:" - entire line is just the speaker label
        re.compile(r"^[A-Z][A-Z.\-']{2,30}:\s*$"),
        # Speaker utterance: "FLORIDO: Is the president going to..." - NPR-scoped only
        # so DC "WATCH:", WT "OPINION:", Fox "MORNING GLORY:" are unaffected
        re.compile(r"^[A-Z][A-Z.\-']{2,30}(\s+[A-Z][A-Z.\-']{2,30})?:\s+\S"),
        # Pure stage direction: "(SOUNDBITE OF JET ENGINE ROARING)"
        re.compile(r"^\(SOUNDBITE OF [^)]+\)\s*$"),
        # Stage direction fused with speaker tag: "(SOUNDBITE OF MUSIC) ROSE: ..."
        re.compile(r"^\(SOUNDBITE OF [^)]+\)\s+[A-Z]"),
        # Unidentified speaker patterns
        re.compile(r"^UNIDENTIFIED (PERSON|MAN|WOMAN|VOICE)(\s+#\d+)?:\s*"),
    ],
    "theguardian": [
        re.compile(r"^get in touch\.?$", re.I),
    ],
    "washingtonexaminer": [
        re.compile(r"^(?=.{12,160}$)(?=.*[A-Z])(?=.*\s)[A-Z0-9][A-Z0-9\s,.'\"""?!:;()&/-]+$"),
    ],
    "washingtontimes": [
        re.compile(
            r"^(commentary|video/podcasts|- (policy|commentary main|corrections|"
            r"editorials|letters|cheryl k\. chumley|tim constantine|joseph curl|"
            r"joseph r\. detrani|clifford d\. may|stephen moore|tim murtaugh|"
            r"peter navarro|everett piper|cal thomas|scott walker|miles yu|"
            r"books|cartoons|sports|events))$",
            re.I,
        ),
        re.compile(
            r"^-\s+(news|policy|commentary|tom basile|daniel n\. hoffman|"
            r"gene marks|kelly sadler|don feder|david keene|jed babbin|"
            r"billy hallowell|robert knight|michael mckenna|"
            r"black voices|to the republic)\b",
            re.I,
        ),
        re.compile(r"^-.+\b(sponsored|video/podcasts|all videos|all podcasts)\b", re.I),
    ],
}

# Outlet name variants for [OUTLET] masking (applied to ALL articles).
# Longest variants first to avoid partial matches.
OUTLET_ALIASES: dict[str, list[str]] = {
    "dailycaller": [
        "Daily Caller News Foundation",
        "The Daily Caller",
        "Daily Caller",
        "DCNF",
    ],
    "foxnews": [
        "Fox News Digital",
        "FOXNEWS.COM",
        "FOX NEWS APP",
        "Fox News",
        "OutKick",
    ],
    "huffpost": [
        "The Huffington Post",
        "Huffington Post",
        "HuffPost",
    ],
    "npr": [
        "National Public Radio",
        "NPR",
    ],
    "nypost": [
        "The New York Post",
        "New York Post",
        "Page Six",
        "NY Post",
    ],
    "theguardian": [
        "The Guardian",
        "Guardian",
    ],
    "washingtonexaminer": [
        "The Washington Examiner",
        "Washington Examiner",
    ],
    "washingtontimes": [
        "The Washington Times",
        "Washington Times",
    ],
}

# Source-restricted aliases: too ambiguous as common nouns in other articles,
# but unambiguous within the outlet's own content.
SOURCE_RESTRICTED_ALIASES: dict[str, list[str]] = {
    "dailycaller": ["the Caller", "Caller"],
    "foxnews": ["Screencaps"],
    "nypost": ["Decider"],
}

# Pre-compiled masking patterns: (pattern, replacement) pairs per source.
_mask_cache: dict[str, list[tuple[re.Pattern, str]]] = {}


def _get_mask_patterns(source: str) -> list[tuple[re.Pattern, str]]:
    if source in _mask_cache:
        return _mask_cache[source]
    patterns: list[tuple[re.Pattern, str]] = []
    # Apply ALL outlet aliases across all articles (cross-outlet leakage prevention).
    for aliases in OUTLET_ALIASES.values():
        for alias in aliases:
            # \b on both sides: prevents matching inside words
            # (e.g. NPR in "nonprofit", FOX NEWS APP in "Fox News appearance").
            pat = re.compile(r'\b' + re.escape(alias) + r'\b', re.I)
            patterns.append((pat, OUTLET_TOKEN))
    # Add source-restricted aliases (only for this article's own outlet).
    for alias in SOURCE_RESTRICTED_ALIASES.get(source, []):
        pat = re.compile(r'\b' + re.escape(alias) + r'\b', re.I)
        patterns.append((pat, OUTLET_TOKEN))
    _mask_cache[source] = patterns
    return patterns


def _line_is_boilerplate(line: str, source: str) -> bool:
    lower = line.lower()
    if source == "npr" and lower.strip(" .:") in _NPR_STANDALONE_HEADINGS:
        return True
    if source == "theguardian" and lower.strip(" .:") in _GUARDIAN_STANDALONE_HEADINGS:
        return True
    if source == "washingtontimes" and lower.strip(" .:") in _WT_STANDALONE_HEADINGS:
        return True
    for term in GLOBAL_BLACKLIST:
        if term in lower:
            return True
    for term in OUTLET_BLACKLIST.get(source, []):
        if term.startswith("(?") or "\\" in term or ".*" in term:
            continue  # handled via _OUTLET_REGEX
        if term in lower:
            return True
    for pat in _GLOBAL_REGEX:
        if pat.search(line):
            return True
    if _READ_IN_FULL.search(line):
        return True
    for pat in _OUTLET_REGEX.get(source, []):
        if pat.search(line):
            return True
    return False


def _clean_line_before_drop(line: str, source: str) -> str:
    """Apply conservative in-line cleanup before whole-line boilerplate checks."""
    line = _TRAILING_SHORTLINK.sub("", line).strip()
    line = _INLINE_SEPARATOR.sub(" ", line).strip()
    if source == "npr":
        line = _SOUNDBITE_OF_MUSIC.sub(" ", line).strip()
    if source == "nypost":
        line = _NYPOST_CALIFORNIA_PREFIX.sub("", line).strip()
    if source == "theguardian":
        for _ in range(2):
            cleaned = _GUARDIAN_LIVEBLOG_META_PREFIX.sub("", line).strip()
            if cleaned == line:
                break
            line = cleaned
    if source == "washingtontimes":
        line = _WT_INLINE_NAV_TAIL.sub("", line).strip()
    line = _TRAILING_DANGLING_HYPHEN.sub("", line).strip()
    return line


def clean_body(body: str, source: str) -> str:
    if not body:
        return body

    # Normalize curly quotes and exotic dashes.
    body = body.replace('"', '"').replace('"', '"')
    body = body.replace(''', "'").replace(''', "'")
    body = body.replace('-', '-').replace('-', '-')

    block_markers = _DROP_BLOCK_MARKERS.get(source, [])
    lines = body.splitlines()
    cleaned: list[str] = []
    dropping_block = False
    block_lines_dropped = 0
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # If we're in block-drop mode, skip until blank line or guard limit.
        if dropping_block:
            if lower == "" or block_lines_dropped >= _MAX_BLOCK_DROP_LINES:
                dropping_block = False
                block_lines_dropped = 0
                if lower == "":
                    cleaned.append("")
            else:
                block_lines_dropped += 1
            continue

        # Check if this line is a block-drop marker (drop the marker + subsequent lines).
        if block_markers and any(m in lower for m in block_markers):
            dropping_block = True
            block_lines_dropped = 0
            continue

        if not stripped:
            cleaned.append("")
            continue
        stripped = _clean_line_before_drop(stripped, source)
        if not stripped:
            continue
        if _line_is_boilerplate(stripped, source):
            continue
        if stripped and cleaned and cleaned[-1].strip() == stripped:
            continue
        cleaned.append(stripped)

    # Drop trailing author-bio paragraph: last non-empty block <= 600 chars
    # with bio signals is removed. Limit raised from 300 to catch longer bios.
    _BIO_SIGNALS = re.compile(
        r"\b(is a|writes for|joined|prior to joining|can be found on|op-ed|bylines|"
        r"contributor to|staff writer|senior editor|formerly|worked at|blogs at|"
        r"is published in|writes frequently|research professor|executive director)\b",
        re.I,
    )
    while cleaned:
        last = cleaned[-1].strip()
        if last == "":
            cleaned.pop()
            continue
        if len(last) <= 600 and _BIO_SIGNALS.search(last):
            cleaned.pop()
        else:
            break

    # Mask all outlet names with [OUTLET] token.
    mask_patterns = _get_mask_patterns(source)
    result_lines: list[str] = []
    for line in cleaned:
        for pat, repl in mask_patterns:
            line = pat.sub(repl, line)
        result_lines.append(line)

    # Collapse runs of blank lines to a single blank, strip leading/trailing.
    text = "\n".join(result_lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
