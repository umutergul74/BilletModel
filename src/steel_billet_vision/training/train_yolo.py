from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import argparse
import hashlib
import json
import platform
import sys

# In the supported Windows/Conda runtime, OpenCV must initialize the shared
# Intel OpenMP runtime before PyTorch. Importing torch first can load a second
# libiomp5md.dll and abort the process with OMP Error #15.
import cv2  # noqa: F401
import torch
import ultralytics
import yaml
from ultralytics import YOLO


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _environment() -> dict[str, Any]:
    gpu: dict[str, Any] | None = None
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        gpu = {"name": properties.name, "vram_bytes": properties.total_memory}
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": gpu,
        "ultralytics": ultralytics.__version__,
    }


def train(config_path: Path, smoke: bool = False) -> Path:
    config_path = config_path.resolve()
    root = config_path.parent.parent.parent
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    training = config["training"]
    augmentation = config["augmentation"]
    output = config["output"]
    run_name = output["name"] + ("_smoke_capacity_v2" if smoke else "")
    project = (root / output["project"]).resolve()
    run_dir = project / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    data_yaml = (root / config["data"]["yaml"]).resolve()
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {data_yaml}")
    if config["holdout"]["test_used_for_model_selection"]:
        raise ValueError("The baseline configuration must keep test data locked")

    context = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "smoke_test": smoke,
        "config": config,
        "config_sha256": _sha256(config_path),
        "dataset_yaml_sha256": _sha256(data_yaml),
        "conversion_summary_sha256": _sha256(data_yaml.parent / "conversion_summary.json"),
        "environment": _environment(),
    }
    (run_dir / "experiment_context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")

    model = YOLO(config["model"]["pretrained"])
    model.train(
        data=str(data_yaml),
        epochs=1 if smoke else int(training["epochs"]),
        patience=int(training["patience"]),
        imgsz=int(training["image_size"]),
        batch=int(training["batch"]),
        workers=int(training["workers"]),
        device=training["device"],
        seed=int(training["seed"]),
        deterministic=bool(training["deterministic"]),
        optimizer=training["optimizer"],
        lr0=float(training["initial_learning_rate"]),
        cos_lr=bool(training["cosine_learning_rate"]),
        amp=bool(training["amp"]),
        cache=training["cache"],
        hsv_h=float(augmentation["hsv_h"]),
        hsv_s=float(augmentation["hsv_s"]),
        hsv_v=float(augmentation["hsv_v"]),
        degrees=float(augmentation["degrees"]),
        translate=float(augmentation["translate"]),
        scale=float(augmentation["scale"]),
        shear=float(augmentation["shear"]),
        perspective=float(augmentation["perspective"]),
        flipud=float(augmentation["flip_up_down"]),
        fliplr=float(augmentation["flip_left_right"]),
        mosaic=float(augmentation["mosaic"]),
        close_mosaic=int(augmentation["close_mosaic"]),
        mixup=float(augmentation["mixup"]),
        copy_paste=float(augmentation["copy_paste"]),
        mask_ratio=4,
        overlap_mask=True,
        project=str(project),
        name=run_name,
        exist_ok=True,
        save=True,
        save_period=int(output["save_period"]),
        val=True,
        plots=True,
        verbose=True,
    )
    context["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    context["best_checkpoint"] = str(run_dir / "weights" / "best.pt")
    (run_dir / "experiment_context.json").write_text(json.dumps(context, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the versioned steel-billet YOLO instance-segmentation baseline.")
    parser.add_argument("--config", type=Path, default=Path("configs/training/baseline_yolo26n_seg.yaml"))
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run one epoch at the configured resolution to validate GPU capacity, data, and labels.",
    )
    args = parser.parse_args()
    print(train(args.config, smoke=args.smoke))


if __name__ == "__main__":
    main()
