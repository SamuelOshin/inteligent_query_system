"""
Natural language query parser for the /api/profiles/search endpoint.

Strategy:
  - Lowercase + tokenize the input string
  - Scan for gender keywords
  - Scan for age_group keywords
  - Scan for "from/in <country>" patterns → map to ISO country_id
  - Scan for "above/over/older than <number>" → min_age
  - If zero filters extracted → raise ValueError so route returns 400

Supported examples:
    "young males from nigeria"        → gender=male, min_age=16, max_age=24, country_id=NG
  "females above 30"                → gender=female, min_age=30
  "people from angola"              → country_id=AO
    "adult males from kenya"          → gender=male, age_group=adult, country_id=KE
    "male and female teenagers above 17" → age_group=teenager, min_age=17
  "adult males"                     → gender=male, age_group=adult

Limitations (documented for README):
  - No negation support ("not male", "excluding nigeria")
  - No "between X and Y" age ranges
  - No typo correction
  - Country matching is exact name match only (no partial/fuzzy)
  - Only one country per query supported
"""

import re
from typing import Optional

# ─── Keyword Maps ─────────────────────────────────────────────────────────────

GENDER_KEYWORDS: dict[str, str] = {
    "male": "male",
    "males": "male",
    "men": "male",
    "man": "male",
    "female": "female",
    "females": "female",
    "women": "female",
    "woman": "female",
    "girl": "female",
    "girls": "female",
    "boy": "male",
    "boys": "male",
}

AGE_GROUP_KEYWORDS: dict[str, str] = {
    "child": "child",
    "children": "child",
    "teen": "teenager",
    "teens": "teenager",
    "teenager": "teenager",
    "teenagers": "teenager",
    "adult": "adult",
    "adults": "adult",
    "senior": "senior",
    "seniors": "senior",
    "elderly": "senior",
    "old": "senior",
}

# Country name → ISO 2-letter code
# Covers countries most likely to appear given genderize/nationalize API data
COUNTRY_NAME_TO_ID: dict[str, str] = {
    "nigeria": "NG",
    "ghana": "GH",
    "kenya": "KE",
    "ethiopia": "ET",
    "south africa": "ZA",
    "egypt": "EG",
    "tanzania": "TZ",
    "uganda": "UG",
    "cameroon": "CM",
    "ivory coast": "CI",
    "senegal": "SN",
    "angola": "AO",
    "mozambique": "MZ",
    "zimbabwe": "ZW",
    "zambia": "ZM",
    "mali": "ML",
    "burkina faso": "BF",
    "niger": "NE",
    "benin": "BJ",
    "togo": "TG",
    "rwanda": "RW",
    "somalia": "SO",
    "sudan": "SD",
    "chad": "TD",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "france": "FR",
    "germany": "DE",
    "spain": "ES",
    "italy": "IT",
    "brazil": "BR",
    "india": "IN",
    "china": "CN",
    "japan": "JP",
    "canada": "CA",
    "australia": "AU",
    "mexico": "MX",
    "argentina": "AR",
    "colombia": "CO",
    "indonesia": "ID",
    "pakistan": "PK",
    "bangladesh": "BD",
    "russia": "RU",
    "turkey": "TR",
    "iran": "IR",
    "iraq": "IQ",
    "saudi arabia": "SA",
    "malaysia": "MY",
    "thailand": "TH",
    "vietnam": "VN",
    "philippines": "PH",
    "dr congo": "CD",
    "drc": "CD",
    "democratic republic of congo": "CD",
    "republic of congo": "CG",
    "congo": "CG",
    "liberia": "LR",
    "sierra leone": "SL",
    "guinea": "GN",
    "eritrea": "ER",
    "namibia": "NA",
    "botswana": "BW",
    "malawi": "MW",
    "madagascar": "MG",
    "mauritius": "MU",
    "seychelles": "SC",
    "cape verde": "CV",
    "gambia": "GM",
    "guinea-bissau": "GW",
    "equatorial guinea": "GQ",
    "gabon": "GA",
    "central african republic": "CF",
    "south sudan": "SS",
    "djibouti": "DJ",
    "comoros": "KM",
    "lesotho": "LS",
    "eswatini": "SZ",
    "swaziland": "SZ",
    "libya": "LY",
    "algeria": "DZ",
    "morocco": "MA",
    "tunisia": "TN",
}


# ─── Parser ───────────────────────────────────────────────────────────────────

def parse_nl_query(q: str) -> dict:
    """
    Parse a natural language query string into a filter dict.
    Raises ValueError if no filters could be extracted.

    Returns dict with any subset of:
            gender, age_group, country_id, min_age, max_age
    """
    # Strip first — whitespace-only strings pass FastAPI's min_length=1
    # but contain no meaningful content
    text = q.strip()
    if not text:
        raise ValueError("Unable to interpret query")

    text = text.lower()

    filters: dict = {}

    # 1. min_age detection FIRST — patterns: "above 30", "over 25", "older than 40"
    # Must run before tokenization because "older" also matches age_group "old" keyword.
    # Detecting this first prevents "older than 40" from setting age_group=senior.
    age_pattern = re.search(
        r"\b(?:above|over|older\s+than)\s+(\d+)\b", text
    )
    if age_pattern:
        filters["min_age"] = int(age_pattern.group(1))
        # Remove the matched portion so "older" doesn't double-match as age_group
        text = text[:age_pattern.start()] + text[age_pattern.end():]

    # Tokenize after age removal — use word chars only (handles hyphenated names
    # at token level; country matching uses full string regex below)
    tokens = re.findall(r"\b\w+\b", text)

    # 2. Gender detection
    # If both genders are present (e.g., "male and female teenagers"),
    # don't force a gender filter.
    found_genders = {
        GENDER_KEYWORDS[token] for token in tokens if token in GENDER_KEYWORDS
    }
    if len(found_genders) == 1:
        filters["gender"] = next(iter(found_genders))

    # 2b. "young" is parsing-only and maps to ages 16-24.
    # It is never stored as age_group.
    if ("young" in tokens or "youth" in tokens) and "min_age" not in filters:
        filters["min_age"] = 16
        filters["max_age"] = 24

    # 3. Age group detection — runs after age_pattern removal so "older" is gone
    for token in tokens:
        if token in AGE_GROUP_KEYWORDS:
            filters["age_group"] = AGE_GROUP_KEYWORDS[token]
            break

    # 4. Country detection — scan "from <phrase>" or "in <phrase>"
    # Uses the original lowercased text (pre-token) to capture multi-word and
    # hyphenated country names like "guinea-bissau", "burkina faso", "south africa"
    country_pattern = re.search(r"\b(?:from|in)\s+(.+?)(?:\s*$|\s+(?:and|with|who)\b)", text)
    if country_pattern:
        candidate = country_pattern.group(1).strip()

        # Try longest match first (sort by name length desc)
        matched = False
        for country_name in sorted(COUNTRY_NAME_TO_ID.keys(), key=len, reverse=True):
            if country_name in candidate:
                filters["country_id"] = COUNTRY_NAME_TO_ID[country_name]
                matched = True
                break

        # Exact match fallback in case sorted scan missed it
        if not matched and candidate in COUNTRY_NAME_TO_ID:
            filters["country_id"] = COUNTRY_NAME_TO_ID[candidate]

    if not filters:
        raise ValueError("Unable to interpret query")

    return filters
