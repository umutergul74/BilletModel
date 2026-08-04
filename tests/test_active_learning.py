from steel_billet_vision.active_learning.curate_batch import select_scene_representatives
from steel_billet_vision.active_learning.select_batch import _rank_percentiles, _select_diverse


def test_rank_percentiles_are_bounded_and_ordered() -> None:
    ranks = _rank_percentiles([10.0, 5.0, 20.0])
    assert ranks == [0.5, 0.0, 1.0]


def test_diverse_selection_limits_scenes_zeros_and_near_duplicates() -> None:
    records = [
        {"filename": "a", "scene_group": "s1", "selection_score": 1.0, "detection_count_low": 0, "phash_hex": "0000000000000000"},
        {"filename": "b", "scene_group": "s1", "selection_score": 0.9, "detection_count_low": 2, "phash_hex": "00000000000000ff"},
        {"filename": "c", "scene_group": "s2", "selection_score": 0.8, "detection_count_low": 2, "phash_hex": "000000000000ffff"},
        {"filename": "d", "scene_group": "s3", "selection_score": 0.7, "detection_count_low": 3, "phash_hex": "0000000000ff00ff"},
    ]

    selected = _select_diverse(records, target_count=3, max_per_scene=1, max_zero=1, near_duplicate_threshold=2)

    assert len(selected) == 3
    assert len({item["scene_group"] for item in selected}) == 3
    assert sum(item["detection_count_low"] == 0 for item in selected) == 1


def test_scene_curation_penalizes_excessive_annotation_workload() -> None:
    records = [
        {
            "filename": "crowded.jpg",
            "scene_group": "scene-a",
            "selection_score": "0.80",
            "detection_count_standard": "140",
            "phash_hex": "0000000000000000",
        },
        {
            "filename": "manageable.jpg",
            "scene_group": "scene-a",
            "selection_score": "0.65",
            "detection_count_standard": "50",
            "phash_hex": "ffffffffffffffff",
        },
    ]

    selected = select_scene_representatives(records, 40, 0.0025, 6)

    assert [row["filename"] for row in selected] == ["manageable.jpg"]
