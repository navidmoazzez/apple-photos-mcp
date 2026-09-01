from apple_photos_mcp.search import Filters, search, tokenize


def test_tokenize_drops_filler_words():
    assert tokenize("show me photos of the sunset") == ["sunset"]


def test_tokenize_keeps_a_query_that_is_all_filler_empty():
    assert tokenize("show me the photos") == []


def test_a_real_photo_outranks_a_screenshot_that_only_mentions_the_words(lib):
    """The whole point of the ranking rules.

    Asset B is a screenshot whose OCR text contains both "sunset" and "beach".
    Asset A is an actual photo of a sunset at a beach. A must win.
    """
    out = search(lib, "sunset beach", Filters(), limit=5)
    assert out["results"][0]["uuid"] == "A"


def test_screenshots_can_be_excluded(lib):
    out = search(lib, "sunset beach", Filters(screenshots=False), limit=5)
    assert all(r["uuid"] != "B" for r in out["results"])


def test_screenshot_only_mode_returns_just_screenshots(lib):
    out = search(lib, "sunset", Filters(screenshots=True), limit=5)
    assert [r["uuid"] for r in out["results"]] == ["B"]


def test_place_matches_through_the_city_field(lib):
    out = search(lib, "dinner stockholm", Filters(), limit=5)
    assert out["results"][0]["uuid"] == "D"


def test_kind_filter_separates_photos_from_videos(lib):
    assert all(r["kind"] == "photo" for r in search(lib, "", Filters(kind="photo"))["results"])
    assert all(r["kind"] == "video" for r in search(lib, "", Filters(kind="video"))["results"])


def test_person_filter(lib):
    out = search(lib, "", Filters(person="anna"), limit=5)
    assert [r["uuid"] for r in out["results"]] == ["E"]


def test_year_filter(lib):
    out = search(lib, "", Filters(year=2025), limit=5)
    assert [r["uuid"] for r in out["results"]] == ["C"]


def test_date_range_is_inclusive(lib):
    out = search(lib, "", Filters(date_from="2024-05-01", date_to="2024-06-01"), limit=9)
    assert sorted(r["uuid"] for r in out["results"]) == ["A", "B"]


def test_empty_query_browses_newest_first(lib):
    out = search(lib, "", Filters(), limit=3)
    assert [r["uuid"] for r in out["results"]] == ["C", "D", "B"]


def test_a_word_apple_never_heard_of_is_reported_not_silently_dropped(lib):
    """The guard against confidently wrong answers."""
    out = search(lib, "sunset smiling", Filters(), limit=5)
    assert "smiling" in out["unmatched_terms"]
    assert "sunset" not in out.get("unmatched_terms", [])


def test_ocr_text_alone_does_not_count_as_understanding_a_word(lib):
    """"hotel" appears only inside a screenshot's OCR, so it is not vocabulary."""
    out = search(lib, "hotel", Filters(), limit=5)
    assert "hotel" in out["unmatched_terms"]


def test_a_place_name_counts_as_understood(lib):
    out = search(lib, "vietnam", Filters(), limit=5)
    assert not out.get("unmatched_terms")


def test_no_match_returns_a_hint_rather_than_a_bare_empty_list(lib):
    out = search(lib, "zzzznotathing", Filters(), limit=5)
    assert out["results"] == []
    assert "hint" in out


def test_limit_is_respected(lib):
    assert len(search(lib, "", Filters(), limit=2)["results"]) == 2
