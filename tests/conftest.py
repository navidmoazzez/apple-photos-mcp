"""Fixtures.

None of these tests touch a real Photos library. CI has no Mac with photos on
it, and more importantly the ranking rules are the part worth pinning down, so
the tests build assets by hand and assert on how they are ordered.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apple_photos_mcp.library import Asset, _build_haystack


def make(uuid: str, **kw) -> Asset:
    asset = Asset(uuid=uuid, filename=kw.pop("filename", f"{uuid}.HEIC"), **kw)
    asset.haystack = _build_haystack(asset)
    return asset


@pytest.fixture
def assets() -> list[Asset]:
    return [
        make("A", filename="IMG_1.HEIC", labels=["Sunset", "Beach", "Sea"],
             place="Miami Beach, Florida", city="Miami Beach", date="2024-05-01T10:00:00"),
        make("B", filename="IMG_2.PNG", screenshot=True,
             labels=["Document"], text=["sunset", "beach", "hotel", "booking"],
             date="2024-06-01T10:00:00"),
        make("C", filename="IMG_3.HEIC", labels=["Receipt", "Document"],
             city="Da Nang", country="Vietnam", date="2025-02-15T10:00:00"),
        make("D", filename="IMG_4.MOV", is_video=True, labels=["Dinner", "Food"],
             activities=["Dining"], venues=["Restaurant"], city="Stockholm",
             date="2024-09-23T10:00:00"),
        make("E", filename="IMG_5.HEIC", persons=["Anna"], labels=["People"],
             favorite=True, date="2023-01-01T10:00:00"),
    ]


class FakeLibrary:
    """Stands in for PhotosLibrary without reading a real library."""

    def __init__(self, items):
        self._items = items
        self._vocab = sorted(
            {t.lower() for a in items for t in a.labels + a.activities + a.venues}
        )

    @property
    def assets(self):
        return self._items

    def vocabulary(self):
        return self._vocab

    def structured_terms(self):
        terms = set()
        for a in self._items:
            for v in (*a.persons, *a.albums, *a.keywords, a.place or "",
                      a.city or "", a.state or "", a.country or ""):
                terms.update(str(v).lower().replace(",", " ").split())
        return terms


@pytest.fixture
def lib(assets):
    return FakeLibrary(assets)
