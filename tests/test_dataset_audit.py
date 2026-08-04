from datetime import datetime

from steel_billet_vision.data.audit import UnionFind, hamming, parse_capture_time


def test_filename_timestamp_and_hamming() -> None:
    assert parse_capture_time("20260729_103953(0).jpg") == datetime(2026, 7, 29, 10, 39, 53)
    assert parse_capture_time("other.jpg") is None
    assert hamming(0b1010, 0b0011) == 2


def test_union_find_groups_items() -> None:
    groups = UnionFind(["a", "b", "c"])
    groups.union("a", "b")
    assert groups.find("a") == groups.find("b")
    assert groups.find("a") != groups.find("c")
