import pytest

from apple_photos_mcp.config import Config
from apple_photos_mcp.writes import TooManyItems, Writer, WritesDisabled


class DummyLib:
    def get(self, ref):
        return None

    def load(self, force=False):
        return []


def test_writes_work_by_default():
    """A flag nobody can avoid setting is not a safeguard, it is a habit."""
    assert Config().read_only is False


def test_read_only_mode_blocks_every_write():
    w = Writer(Config(read_only=True), DummyLib())
    for call in (
        lambda: w.set_favorite(["x"]),
        lambda: w.set_title("x", "t"),
        lambda: w.set_description("x", "d"),
        lambda: w.add_keywords(["x"], ["k"]),
        lambda: w.add_to_album("Album", ["x"]),
        lambda: w.archive(["x"], confirm=True),
    ):
        with pytest.raises(WritesDisabled):
            call()


def test_archive_does_nothing_without_confirm():
    w = Writer(Config(), DummyLib())
    out = w.archive(["x"])
    assert out["confirmed"] is False
    assert out["would_archive"] == 1
    assert "confirm=true" in out["message"]


def test_reversible_writes_do_not_ask_for_confirmation():
    """Confirming everything trains the reflex the confirm exists to prevent."""
    w = Writer(Config(), DummyLib())
    assert "confirmed" not in w.set_favorite(["x"])
    assert "confirmed" not in w.add_to_album("A", ["x"])


def test_oversized_batches_are_refused():
    w = Writer(Config(write_batch_max=10), DummyLib())
    with pytest.raises(TooManyItems):
        w.set_favorite([str(i) for i in range(11)])


def test_batch_at_the_limit_is_allowed():
    w = Writer(Config(write_batch_max=10), DummyLib())
    assert w.set_favorite([str(i) for i in range(10)])["changed"] == 0


def test_there_is_no_delete_tool():
    assert not any("delete" in name.lower() for name in dir(Writer))


def test_audit_log_records_a_blocked_write(tmp_path):
    import json

    log = tmp_path / "writes.jsonl"
    w = Writer(Config(read_only=True, audit_log=log), DummyLib())
    with pytest.raises(WritesDisabled):
        w.set_favorite(["x"])
    line = json.loads(log.read_text().strip())
    assert line["allowed"] is False


def test_a_broken_audit_path_never_breaks_the_write(tmp_path):
    """The log is a record, not a control."""
    unwritable = tmp_path / "file.txt"
    unwritable.write_text("x")
    w = Writer(Config(audit_log=unwritable / "nested" / "log.jsonl"), DummyLib())
    assert w.set_favorite(["x"])["changed"] == 0
