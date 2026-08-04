from pathlib import Path

import yaml


def test_test_evaluation_is_one_time_and_not_for_tuning() -> None:
    config = yaml.safe_load(
        Path("configs/evaluation/baseline_yolo26n_seg_test.yaml").read_text(encoding="utf-8")
    )
    assert config["evaluation"]["policy"] == "ONE_TIME_FROZEN_BASELINE_TEST"
    assert config["evaluation"]["training_configuration_frozen"] is True
    assert config["evaluation"]["use_results_for_hyperparameter_tuning"] is False
    assert config["data"]["split"] == "test"
