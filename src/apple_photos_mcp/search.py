"""Ranking assets against a natural-language phrase.

The useful thing about a Photos library is that Apple has already done the hard
part: every asset carries scene labels, OCR text, an activity guess, a venue
type and a place. What is missing is a way to ask for them in one phrase.

So a query is split into words, and each word is scored against each field with
a weight that reflects how much that field means. A word matching a person's
name is worth far more than the same word appearing in OCR noise. Assets that
match more of the distinct query words rank above assets that match one word
many times, which is what stops a single spammy field from winning.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .library import Asset, PhotosLibrary

#: Words carrying no discriminating power. Kept short on purpose: over-filtering
#: hurts more than it helps once field weighting is doing the real work.
STOPWORDS = {
    "a", "an", "and", "any", "are", "at", "be", "can", "did", "do", "does", "find",
    "for", "from", "get", "give", "has", "have", "i", "in", "is", "it", "its", "me",
    "my", "of", "on", "or", "our", "photo", "photos", "pic", "pics", "picture",
    "pictures", "show", "some", "that", "the", "their", "them", "there", "they",
    "this", "to", "was", "were", "what", "when", "where", "which", "with", "you",
    "your",
}

#: Field weights. Tuned so an explicit human signal (a face, a place you named,
#: a caption you wrote) always outranks an incidental one (a word Apple's OCR
#: happened to read in the background of a receipt).
WEIGHTS: list[tuple[str, float, Callable[[Asset], list[str]]]] = [
    ("person", 10.0, lambda a: a.persons),
    ("title", 8.0, lambda a: [a.title] if a.title else []),
    ("keyword", 7.0, lambda a: a.keywords),
    ("description", 6.0, lambda a: [a.description] if a.description else []),
    ("album", 5.0, lambda a: a.albums),
    ("place", 5.0, lambda a: [x for x in (a.place, a.city, a.state, a.country) if x]),
    ("label", 4.0, lambda a: a.labels),
    ("activity", 3.5, lambda a: a.activities),
    ("venue", 3.0, lambda a: a.venues),
    ("filename", 2.0, lambda a: [a.filename]),
    ("text", 1.2, lambda a: a.text),
]


@dataclass
class Filters:
    """Structured narrowing applied before ranking."""

    kind: str | None = None           # "photo" | "video"
    favorite: bool | None = None
    person: str | None = None
    album: str | None = None
    place: str | None = None
    year: int | None = None
    date_from: str | None = None      # ISO date, inclusive
    date_to: str | None = None        # ISO date, inclusive
    screenshots: bool | None = None   # None = include, False = exclude, True = only
    include_hidden: bool = False
    downloaded_only: bool = False

    def keep(self, a: Asset) -> bool:
        if a.hidden and not self.include_hidden:
            return False
        if self.kind == "photo" and a.is_video:
            return False
        if self.kind == "video" and not a.is_video:
            return False
        if self.favorite is not None and a.favorite is not self.favorite:
            return False
        if self.screenshots is True and not a.screenshot:
            return False
        if self.screenshots is False and a.screenshot:
            return False
        if self.downloaded_only and not a.local:
            return False
        if self.person:
            needle = self.person.lower()
            if not any(needle in p.lower() for p in a.persons):
                return False
        if self.album:
            needle = self.album.lower()
            if not any(needle in al.lower() for al in a.albums):
                return False
        if self.place:
            needle = self.place.lower()
            hay = " ".join(x for x in (a.place, a.city, a.state, a.country) if x).lower()
            if needle not in hay:
                return False
        if self.year is not None and (not a.date or not a.date.startswith(str(self.year))):
            return False
        if self.date_from and (not a.date or a.date[:10] < self.date_from):
            return False
        if self.date_to and (not a.date or a.date[:10] > self.date_to):
            return False
        return True


def tokenize(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", query.lower())
    kept = [w for w in words if w not in STOPWORDS and len(w) > 1]
    # A query made entirely of stopwords ("show me the photos") should still
    # return the filtered set rather than nothing at all.
    return kept


def _field_score(word: str, values: list[str], weight: float) -> float:
    """Exact token match scores full weight; a prefix match scores half.

    Substring-anywhere matching is deliberately not used: it makes "art" match
    "heart" and "Sparta", which is the single fastest way to make a search feel
    broken.
    """
    best = 0.0
    for value in values:
        if not value:
            continue
        for token in re.findall(r"[a-z0-9']+", value.lower()):
            if token == word:
                return weight
            if len(word) > 3 and token.startswith(word):
                best = max(best, weight * 0.5)
    return best


#: Words that mean the user is deliberately after screenshots, documents or
#: text, rather than a photograph of something.
TEXTUAL_INTENT = {
    "screenshot", "screenshots", "screen", "document", "documents", "receipt",
    "receipts", "invoice", "invoices", "ticket", "tickets", "text", "note",
    "notes", "email", "message", "chat", "page", "pdf", "form", "passport",
    "id", "card", "whiteboard", "slide", "slides", "quote", "tweet", "post",
}


def score(asset: Asset, words: list[str]) -> tuple[float, list[str]]:
    """Return the asset's score and which fields earned it."""
    total = 0.0
    matched_words = 0
    why: set[str] = set()
    text_only = True
    for word in words:
        best = 0.0
        best_field = ""
        for field_name, weight, getter in WEIGHTS:
            s = _field_score(word, getter(asset), weight)
            if s > best:
                best, best_field = s, field_name
        if best > 0:
            total += best
            matched_words += 1
            why.add(best_field)
            if best_field != "text":
                text_only = False
    if not matched_words:
        return 0.0, []

    # Covering more of the query is worth more than scoring high on one word,
    # but only mildly, a strong bonus per extra word lets a screenshot full of
    # OCR noise beat a photograph that actually shows the thing asked for.
    coverage = matched_words / len(words)
    total *= 0.4 + 0.6 * coverage
    total *= 1 + 0.2 * (matched_words - 1)

    wants_text = bool(TEXTUAL_INTENT & set(words))

    # A screenshot is rarely what "find my photo of X" means. Unless the query
    # itself is textual, it competes at a discount.
    if asset.screenshot and not wants_text:
        total *= 0.45

    # Matching purely on words Apple's OCR read is the weakest evidence there
    # is: it means the phrase appeared *written inside* the image, not that the
    # image depicts it. Only trust it when the query was asking about text.
    if text_only and not wants_text:
        total *= 0.35

    return total, sorted(why)


def search(
    lib: PhotosLibrary,
    query: str = "",
    filters: Filters | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    filters = filters or Filters()
    words = tokenize(query)
    candidates = [a for a in lib.assets if filters.keep(a)]

    if not words:
        # Pure browse: newest first is the only ordering that makes sense.
        ranked = sorted(candidates, key=lambda a: a.date or "", reverse=True)
        rows = [a.summary() for a in ranked[:limit]]
        return {
            "query": query,
            "matched": len(candidates),
            "returned": len(rows),
            "results": rows,
            "note": "No search terms, showing the most recent matches for the filters.",
        }

    scored: list[tuple[float, list[str], Asset]] = []
    for a in candidates:
        s, why = score(a, words)
        if s > 0:
            scored.append((s, why, a))
    # Highest score first; newest first among ties.
    scored.sort(key=lambda t: (t[0], t[2].date or ""), reverse=True)

    rows = []
    for _score, why, a in scored[:limit]:
        row = a.summary()
        row["matched_on"] = why
        rows.append(row)

    out: dict[str, Any] = {
        "query": query,
        "searched": len(candidates),
        "matched": len(scored),
        "returned": len(rows),
        "results": rows,
    }

    # Apple's label vocabulary is a fixed set of about 1,500 words that its
    # on-device classifier was trained on. "smiling", "cosy" and "aesthetic" are
    # not in it, and no amount of rephrasing the same idea will find them. Words
    # that matched nothing are far more useful to report than a bare zero, so
    # every unmatched word gets checked against the vocabulary that does exist.
    unmatched = [w for w in words if not _understood(w, lib)]
    if unmatched:
        suggestions = suggest_terms(lib, unmatched)
        if suggestions:
            out["did_you_mean"] = suggestions
        out["unmatched_terms"] = unmatched

    if not rows:
        out["hint"] = (
            "Nothing matched. Apple indexes what a photo looks like, not what you "
            "call it, try a scene word ('sunset', 'document', 'beach'), a place, a "
            "person's name, or a word that would literally appear inside the image. "
            "Call list_vocabulary to see the words this library actually knows."
        )
    return out


def _understood(word: str, lib: PhotosLibrary) -> bool:
    """Does this library have a *visual* or *structured* meaning for the word?

    Appearing in OCR text does not count. "smiling" turns up inside the text of
    some screenshot in almost any library, and treating that as understanding is
    exactly how a search convinces someone it looked when it did not.
    """
    if word in lib.structured_terms():
        return True
    return any(
        word == v or v.startswith(word + " ") or (" " + word) in v
        for v in lib.vocabulary()
    )


def suggest_terms(lib: PhotosLibrary, words: list[str], per_word: int = 4) -> dict[str, list[str]]:
    """For each word Apple has never heard of, offer the closest words it has.

    This is what turns a dead end into a next step: the agent learns that this
    library knows "Crowd" and "Audience" but not "keynote", and can ask again.
    """
    vocab = lib.vocabulary()
    out: dict[str, list[str]] = {}
    for word in words:
        near = difflib.get_close_matches(word, vocab, n=per_word, cutoff=0.72)
        prefix = [v for v in vocab if v.startswith(word) and v not in near][:per_word]
        combined = (near + prefix)[:per_word]
        if combined:
            out[word] = combined
    return out
