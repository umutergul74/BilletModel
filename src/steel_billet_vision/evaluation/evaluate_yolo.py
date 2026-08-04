from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import hashlib
import json

# Keep the supported Windows/Conda OpenMP runtime initialization consistent
# with the training entrypoint. See training/train_yolo.py.
import cv2  # noqa: F401
import torch
import ultralytics
import yaml
from ultralytics import YOLO


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(config_path: Path) -> Path:
    config_path = config_path.resolve()
    root = config_path.parent.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    policy = config["evaluation"]
    policy_name = policy["policy"]
    allowed_policies = {"ONE_TIME_FROZEN_BASELINE_TEST", "VALIDATION_CHECKPOINT_AUDIT"}
    if policy_name not in allowed_policies:
        raise ValueError(f"Unsupported evaluation policy: {policy_name}")
    if policy_name == "ONE_TIME_FROZEN_BASELINE_TEST":
        if config["data"]["split"] != "test":
            raise ValueError("The frozen-test policy may only evaluate the test split")
        if not policy["training_configuration_frozen"] or policy["use_results_for_hyperparameter_tuning"]:
            raise ValueError("Test results must not be used for model selection or hyperparameter tuning")
    elif config["data"]["split"] != "val":
        raise ValueError("The validation-audit policy may only evaluate the validation split")

    checkpoint = (root / config["model"]["checkpoint"]).resolve()
    data_yaml = (root / config["data"]["yaml"]).resolve()
    output = config["output"]
    run_dir = (root / output["project"] / output["name"]).resolve()
    if run_dir.exists():
        raise FileExistsError(f"Refusing to repeat or overwrite the evaluation: {run_dir}")
    if not checkpoint.is_file() or not data_yaml.is_file():
        raise FileNotFoundError("Frozen checkpoint or dataset YAML is missing")

    runtime = config["runtime"]
    model = YOLO(str(checkpoint))
    metrics = model.val(
        data=str(data_yaml),
        split=config["data"]["split"],
        imgsz=int(runtime["image_size"]),
        batch=int(runtime["batch"]),
        workers=int(runtime["workers"]),
        device=runtime["device"],
        seed=int(runtime["seed"]),
        deterministic=True,
        plots=True,
        project=str((root / output["project"]).resolve()),
        name=output["name"],
        exist_ok=False,
        verbose=True,
    )
    result = {
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "policy": policy,
        "split": config["data"]["split"],
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "dataset_yaml": str(data_yaml),
        "dataset_yaml_sha256": _sha256(data_yaml),
        "config_sha256": _sha256(config_path),
        "environment": {
            "ultralytics": ultralytics.__version__,
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        },
        "metrics": {key: float(value) for key, value in metrics.results_dict.items()},
        "speed_ms_per_image": {key: float(value) for key, value in metrics.speed.items()},
    }
    (run_dir / "evaluation_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a traceable one-time evaluation of a frozen YOLO baseline.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/evaluation/baseline_yolo26n_seg_test.yaml"),
    )
    args = parser.parse_args()
    print(evaluate(args.config))


if __name__ == "__main__":
    main()
