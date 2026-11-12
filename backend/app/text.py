"""Small text-analysis helpers shared by the keyword, content and competitor modules (no ML dependencies)."""
from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*", re.UNICODE)
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“(])|\n{2,}")

STOPWORDS = set(
    "a about above after again against all also am an and any are aren't as at be because been before being below "
    "between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few "
    "for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him "
    "himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my "
    "myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd "
    "she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's "
    "these they they'd they'll they're they've this those through to too under until up very was wasn't we we'd "
    "we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with "
    "won't would wouldn't you you'd you'll you're you've your yours yourself yourselves will just get got one two "
    "may might much many via per etc us new use used using like make made within without however therefore".split()
)
QUESTION_WORDS = ("who", "what", "when", "where", "why", "how", "which", "can", "does", "do", "is", "are", "will", "should")


def tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokens(text) if t not in STOPWORDS and len(t) > 1 and not t.isdigit()]


def stem(word: str) -> str:
    """Very light English stemmer (plurals, -ing, -ed); enough to group keyword variants."""
    w = word.lower()
    if len(w) <= 3:
        return w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and w[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return w[:-2]  # boxes -> box, classes -> class
    if w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]  # shoes -> shoe, tools -> tool
    for suffix in ("ing", "ed"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def ngrams(toks: list[str], n: int) -> list[str]:
    return [" ".join(toks[i : i + n]) for i in range(len(toks) - n + 1)]


def term_counts(text: str, max_n: int = 2) -> Counter:
    """Counts of content unigrams plus n-grams that do not start or end with a stopword."""
    toks = tokens(text)
    counts: Counter = Counter(t for t in toks if t not in STOPWORDS and len(t) > 2 and not t.isdigit())
    for n in range(2, max_n + 1):
        for i in range(len(toks) - n + 1):
            gram = toks[i : i + n]
            if gram[0] in STOPWORDS or gram[-1] in STOPWORDS or any(len(g) < 2 or g.isdigit() for g in gram):
                continue
            counts[" ".join(gram)] += 1
    return counts


def top_terms(text: str, limit: int = 20, max_n: int = 2) -> list[tuple[str, int]]:
    return term_counts(text, max_n).most_common(limit)


def tfidf_terms(docs: list[str], limit: int = 40, max_n: int = 2) -> list[dict]:
    """Terms ranked by how many documents use them and how often; for 'what do ranking pages talk about'."""
    per_doc = [term_counts(d, max_n) for d in docs if d]
    if not per_doc:
        return []
    df: Counter = Counter()
    total: Counter = Counter()
    for c in per_doc:
        df.update(c.keys())
        total.update(c)
    n = len(per_doc)
    min_df = 1 if n < 3 else max(2, math.ceil(n * 0.3))
    rows = []
    for term, d in df.items():
        if d < min_df:
            continue
        avg = total[term] / d
        rows.append({"term": term, "documents": d, "share": round(d / n, 2), "avg_count": round(avg, 1),
                     "score": round((d / n) * math.log1p(avg) * (1.3 if " " in term else 1.0), 4)})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.split(text or "") if len(s.strip()) > 1]


def count_syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def readability(text: str) -> dict:
    """Flesch Reading Ease and Flesch-Kincaid grade. The formulas are calibrated for English."""
    sents = sentences(text)
    words = _WORD.findall(text or "")
    if not words or not sents:
        return {"words": len(words), "sentences": len(sents), "flesch_reading_ease": None, "flesch_kincaid_grade": None,
                "avg_sentence_length": 0, "long_sentence_share": 0, "label": "n/a"}
    syllables = sum(count_syllables(w) for w in words)
    wps = len(words) / len(sents)
    spw = syllables / len(words)
    ease = round(206.835 - 1.015 * wps - 84.6 * spw, 1)
    grade = round(0.39 * wps + 11.8 * spw - 15.59, 1)
    long_share = round(sum(1 for s in sents if len(_WORD.findall(s)) > 25) / len(sents), 2)
    label = ("very easy" if ease >= 80 else "easy" if ease >= 70 else "fairly easy" if ease >= 60 else
             "standard" if ease >= 50 else "fairly difficult" if ease >= 30 else "difficult")
    return {"words": len(words), "sentences": len(sents), "flesch_reading_ease": ease, "flesch_kincaid_grade": grade,
            "avg_sentence_length": round(wps, 1), "long_sentence_share": long_share, "label": label}


def is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.endswith("?") or t.split(" ", 1)[0] in QUESTION_WORDS
