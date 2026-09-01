from pathlib import Path

from apple_photos_mcp.config import Config


def test_flags_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("APPLE_PHOTOS_READ_ONLY", "1")
    assert Config.from_env().read_only is True


def test_flag_accepts_words_as_well_as_digits(monkeypatch):
    for value in ("true", "TRUE", "yes", "on"):
        monkeypatch.setenv("APPLE_PHOTOS_READ_ONLY", value)
        assert Config.from_env().read_only is True
    for value in ("0", "false", "no", ""):
        monkeypatch.setenv("APPLE_PHOTOS_READ_ONLY", value)
        assert Config.from_env().read_only is False


def test_paths_expand_a_tilde(monkeypatch):
    monkeypatch.setenv("APPLE_PHOTOS_EXPORT_DIR", "~/somewhere")
    assert Config.from_env().export_dir == Path.home() / "somewhere"


def test_a_nonsense_integer_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("APPLE_PHOTOS_PREVIEW_PX", "not-a-number")
    assert Config.from_env().preview_px == 640
