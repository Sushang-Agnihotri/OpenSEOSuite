"""hreflang value validation (ISO 639-1 language, optional ISO 15924 script, optional ISO 3166-1 region)."""
from __future__ import annotations

import re

LANGS = set(
    "aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy da de dv dz ee el "
    "en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu hy hz ia id ie ig ii ik io is it iu "
    "ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na "
    "nb nd ne ng nl nn no nr nv ny oc oj om or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so "
    "sq sr ss st su sv sw ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu".split()
)
REGIONS = set(
    "AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ "
    "CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO "
    "FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE "
    "JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO "
    "MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW "
    "PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM "
    "TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW".split()
)
_PATTERN = re.compile(r"^([A-Za-z]{2})(?:-([A-Za-z]{4}))?(?:-([A-Za-z]{2}|\d{3}))?$")
_LOCALE_SEGMENT = re.compile(r"^/([a-z]{2})(?:[-_]([a-zA-Z]{2}))?(?:/|$)")


def validate_hreflang(value: str) -> str | None:
    """Return an error message, or None when the value is valid."""
    v = (value or "").strip()
    if v.lower() == "x-default":
        return None
    if "_" in v:
        return f"'{v}' uses an underscore; use a hyphen (e.g. en-GB)"
    m = _PATTERN.match(v)
    if not m:
        return f"'{v}' is not a valid language-region code"
    lang, _script, region = m.group(1).lower(), m.group(2), m.group(3)
    if lang not in LANGS:
        return f"'{lang}' is not an ISO 639-1 language code"
    if region and not region.isdigit() and region.upper() not in REGIONS:
        hint = " (use GB for the United Kingdom)" if region.upper() == "UK" else ""
        return f"'{region}' is not an ISO 3166-1 region code{hint}"
    return None


def language_of(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().replace("_", "-").split("-")[0] or None


def locale_from_path(path: str) -> str | None:
    """Guess a locale from a leading path segment such as /de/ or /en-gb/."""
    m = _LOCALE_SEGMENT.match(path or "")
    if m and m.group(1) in LANGS:
        return m.group(1) + (f"-{m.group(2).lower()}" if m.group(2) else "")
    return None
