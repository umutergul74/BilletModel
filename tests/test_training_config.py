from pathlib import Path

import yaml


def test_baseline_locks_test_holdout() -> None:
    config = yaml.safe_load(Path("configs/training/baseline_yolo26n_seg.yaml").read_text(encoding="utf-8"))
    assert config["holdout"]["test_used_for_model_selection"] is False
    assert config["model"]["pretrained"].endswith("-seg.pt")
    assert config["augmentation"]["flip_up_down"] == 0.0
