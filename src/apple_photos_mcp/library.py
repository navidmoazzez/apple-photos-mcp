"""Reading the Photos library.

Photos keeps far more than filenames. Every asset carries an on-device machine
learning record: scene labels, text read out of the image, the kind of activity
it looks like, the kind of venue it was taken at, and a reverse-geocoded place.
All of it is written into the library's SQLite by Apple, on the Mac, and none of
it needs Photos.app to be running to read.

``osxphotos`` exposes that record. This module turns it into one flat, cheap
document per asset so a query can be answered without walking 37,000 objects
again. The document is cached on disk and rebuilt only when the library changes.
"""

from __future__ import annotations

import collections
import gzip
import hashlib
import json
import logging
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config

log = logging.getLogger(__name__)

#: Bumped whenever the shape of a cached document changes, so old caches are
#: discarded instead of being read with the wrong field names.
INDEX_VERSION = 3


@dataclass
class Asset:
    """One photo or video, flattened to exactly what search and display need."""

    uuid: str
    filename: str
    date: str | None = None
    is_video: bool = False
    favorite: bool = False
    hidden: bool = False
    in_trash: bool = False
    screenshot: bool = False
    selfie: bool = False
    portrait: bool = False
    live: bool = False
    raw: bool = False
    width: int = 0
    height: int = 0
    duration: float = 0.0
    #: False when the asset lives only in iCloud and has no local pixels yet.
    local: bool = True
    title: str | None = None
    description: str | None = None
    keywords: list[str] = field(default_factory=list)
    persons: list[str] = field(default_factory=list)
    albums: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    venues: list[str] = field(default_factory=list)
    place: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    #: Words Apple's OCR read inside the image, lowercased and de-duplicated.
    text: list[str] = field(default_factory=list)
    #: Everything above, lowercased and joined. Built once; never serialized.
    haystack: str = ""

    def summary(self) -> dict[str, Any]:
        """The compact form returned in search results."""
        out: dict[str, Any] = {
            "uuid": self.uuid,
            "filename": self.filename,
            "date": self.date,
            "kind": "video" if self.is_video else "photo",
        }
        if self.title:
            out["title"] = self.title
        if self.persons:
            out["persons"] = self.persons
        if self.place:
            out["place"] = self.place
        if self.labels:
            out["labels"] = self.labels[:8]
        if self.favorite:
            out["favorite"] = True
        if not self.local:
            out["icloud_only"] = True
        return out

    def details(self) -> dict[str, Any]:
        """Everything known about the asset, for ``photo_info``."""
        out = self.summary()
        out.update(
            {
                "description": self.description,
                "keywords": self.keywords,
                "albums": self.albums,
                "labels": self.labels,
                "activities": self.activities,
                "venues": self.venues,
                "city": self.city,
                "state": self.state,
                "country": self.country,
                "dimensions": f"{self.width}x{self.height}" if self.width else None,
                "favorite": self.favorite,
                "hidden": self.hidden,
                "media": [
                    k
                    for k, v in (
                        ("screenshot", self.screenshot),
                        ("selfie", self.selfie),
                        ("portrait", self.portrait),
                        ("live", self.live),
                        ("raw", self.raw),
                    )
                    if v
                ],
                "downloaded_to_mac": self.local,
            }
        )
        if self.is_video and self.duration:
            out["duration_seconds"] = round(self.duration, 1)
        if self.text:
            out["text_in_image"] = self.text[:60]
        return {k: v for k, v in out.items() if v not in (None, [], "")}


def _text_words(detected: Any) -> list[str]:
    """Normalize osxphotos' OCR payload, which is a str on some versions and a
    list on others, into a de-duplicated list of lowercase words."""
    if not detected:
        return []
    if isinstance(detected, str):
        parts: Iterable[str] = detected.replace("\n", " ").split()
    else:
        parts = []
        for item in detected:
            # Some versions yield (text, confidence) pairs instead of plain text.
            value = item[0] if isinstance(item, (list, tuple)) and item else item
            if isinstance(value, str):
                parts.extend(value.split())
    seen: dict[str, None] = {}
    for word in parts:
        w = word.strip().strip(".,:;!?\"'()[]{}").lower()
        if len(w) > 1:
            seen.setdefault(w, None)
    return list(seen)


def _build_haystack(a: Asset) -> str:
    bits = [
        a.filename,
        a.title or "",
        a.description or "",
        a.place or "",
        a.city or "",
        a.state or "",
        a.country or "",
        *a.keywords,
        *a.persons,
        *a.albums,
        *a.labels,
        *a.activities,
        *a.venues,
        *a.text,
    ]
    if a.screenshot:
        bits.append("screenshot")
    if a.selfie:
        bits.append("selfie")
    if a.portrait:
        bits.append("portrait")
    if a.is_video:
        bits.append("video movie clip")
    return " ".join(b for b in bits if b).lower()


class PhotosLibrary:
    """Lazily loads the library, caches a flat index, and answers queries."""

    def __init__(self, config: Config):
        self.config = config
        self._assets: list[Asset] | None = None
        self._by_uuid: dict[str, Asset] = {}
        self._lock = threading.Lock()
        self._loaded_at: float = 0.0
        self._source: str = ""
        self._vocab: list[str] | None = None
        self._structured: set[str] | None = None

    # ---------------------------------------------------------------- loading

    def _library_path(self) -> Path:
        if self.config.library:
            return self.config.library
        import osxphotos

        return Path(osxphotos.utils.get_last_library_path())

    def _cache_file(self, lib: Path) -> Path:
        key = hashlib.sha256(str(lib).encode()).hexdigest()[:12]
        return self.config.preview_dir.parent / "index" / f"{key}-v{INDEX_VERSION}.json.gz"

    def _library_stamp(self, lib: Path) -> float:
        """Newest mtime across the library's SQLite files. Cheap staleness check."""
        newest = 0.0
        for name in ("database/Photos.sqlite", "database/photos.db"):
            p = lib / name
            if p.exists():
                newest = max(newest, p.stat().st_mtime)
        return newest or lib.stat().st_mtime

    def load(self, force: bool = False) -> list[Asset]:
        with self._lock:
            if self._assets is not None and not force:
                return self._assets
            lib = self._library_path()
            cache = self._cache_file(lib)
            stamp = self._library_stamp(lib)

            if not force and cache.exists():
                try:
                    with gzip.open(cache, "rt", encoding="utf-8") as fh:
                        blob = json.load(fh)
                    if blob.get("stamp") == stamp:
                        assets = [Asset(**row) for row in blob["assets"]]
                        for a in assets:
                            a.haystack = _build_haystack(a)
                        self._install(assets, f"cache ({cache.name})")
                        return assets
                except Exception as exc:  # a bad cache must never be fatal
                    log.warning("ignoring unreadable index cache: %s", exc)

            assets = self._scan(lib)
            self._install(assets, "library scan")
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                payload = {
                    "stamp": stamp,
                    "assets": [
                        {k: v for k, v in a.__dict__.items() if k != "haystack"} for a in assets
                    ],
                }
                with gzip.open(cache, "wt", encoding="utf-8") as fh:
                    json.dump(payload, fh)
            except Exception as exc:
                log.warning("could not write index cache: %s", exc)
            return assets

    def _install(self, assets: list[Asset], source: str) -> None:
        self._assets = assets
        self._by_uuid = {a.uuid: a for a in assets}
        self._loaded_at = time.time()
        self._source = source

    def _scan(self, lib: Path) -> list[Asset]:
        import osxphotos

        db = osxphotos.PhotosDB(str(lib))
        out: list[Asset] = []
        for p in db.photos(movies=True, intrash=False):
            si = p.search_info
            place = p.place.name if p.place else None
            a = Asset(
                uuid=p.uuid,
                filename=p.original_filename or p.filename or "",
                date=p.date.isoformat() if p.date else None,
                is_video=bool(p.ismovie),
                favorite=bool(p.favorite),
                hidden=bool(p.hidden),
                in_trash=bool(p.intrash),
                screenshot=bool(p.screenshot),
                selfie=bool(p.selfie),
                portrait=bool(p.portrait),
                live=bool(p.live_photo),
                raw=bool(p.has_raw or p.israw),
                width=int(p.width or 0),
                height=int(p.height or 0),
                duration=float(getattr(p, "duration", 0) or 0),
                # `path` is None precisely when the asset has not been pulled
                # down from iCloud. That is the majority in most libraries.
                local=bool(p.path),
                title=p.title or None,
                description=p.description or None,
                keywords=list(p.keywords or []),
                persons=[x for x in (p.persons or []) if x and x != "_UNKNOWN_"],
                albums=list(p.albums or []),
                labels=list(p.labels or []),
                activities=list(si.activities or []) if si else [],
                venues=list((si.venue_types or []) + (si.venues or [])) if si else [],
                place=place,
                city=(si.city if si else None) or None,
                state=(si.state if si else None) or None,
                country=(si.country if si else None) or None,
                text=_text_words(si.detected_text if si else None),
            )
            a.haystack = _build_haystack(a)
            out.append(a)
        return out

    # ----------------------------------------------------------------- access

    @property
    def assets(self) -> list[Asset]:
        return self.load()

    def get(self, ref: str) -> Asset | None:
        """Resolve a uuid, or fall back to an exact/basename filename match."""
        self.load()
        ref = ref.strip()
        hit = self._by_uuid.get(ref) or self._by_uuid.get(ref.upper())
        if hit:
            return hit
        low = ref.lower()
        for a in self._assets or []:
            if a.filename.lower() == low:
                return a
        return None

    def vocabulary(self) -> list[str]:
        """Every scene label, activity and venue type present in this library.

        Apple's classifier has a closed vocabulary, so this is the definitive
        list of visual words a search can actually hit. Cached after first use.
        """
        if self._vocab is None:
            terms: set[str] = set()
            for a in self.load():
                terms.update(x.lower() for x in a.labels)
                terms.update(x.lower() for x in a.activities)
                terms.update(x.lower() for x in a.venues)
            self._vocab = sorted(terms)
        return self._vocab

    def structured_terms(self) -> set[str]:
        """Words that mean something because a human or Apple's geocoder put
        them there: names, album titles, places, keywords, captions."""
        if self._structured is None:
            terms: set[str] = set()
            for a in self.load():
                for value in (
                    *a.persons, *a.albums, *a.keywords,
                    a.title or "", a.description or "",
                    a.place or "", a.city or "", a.state or "", a.country or "",
                ):
                    for token in str(value).lower().replace(",", " ").split():
                        if len(token) > 1:
                            terms.add(token)
            self._structured = terms
        return self._structured

    def label_counts(self) -> collections.Counter[str]:
        import collections as _c

        counts: _c.Counter[str] = _c.Counter()
        for a in self.load():
            for label in a.labels:
                counts[label] += 1
        return counts

    def stats(self) -> dict[str, Any]:
        assets = self.load()
        videos = sum(1 for a in assets if a.is_video)
        return {
            "library": str(self._library_path()),
            "total": len(assets),
            "photos": len(assets) - videos,
            "videos": videos,
            "favorites": sum(1 for a in assets if a.favorite),
            "screenshots": sum(1 for a in assets if a.screenshot),
            "with_ml_labels": sum(1 for a in assets if a.labels),
            "with_text_in_image": sum(1 for a in assets if a.text),
            "with_place": sum(1 for a in assets if a.place or a.city),
            "named_people": sorted({p for a in assets for p in a.persons}),
            "albums": sorted({al for a in assets for al in a.albums}),
            "not_downloaded_to_mac": sum(1 for a in assets if not a.local),
            "index_source": self._source,
        }
